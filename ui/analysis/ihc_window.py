import os, shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QMessageBox, QTextEdit, QGridLayout
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import numpy as np
import cv2

from core.dab_extractor import DABExtractor
from db.patient_dao import add_analysis
from ui.patients.patient_selector import PatientSelector


class DABWorker(QThread):
    finished = Signal(object, object, object, dict, object)
    error    = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            extractor = DABExtractor()
            result = extractor.extract_and_analyze(self.image_path)
            self.finished.emit(*result)
        except Exception as e:
            self.error.emit(str(e))


def _np_to_pixmap(arr):
    if arr is None:
        return None
    h, w, c = arr.shape
    img = QImage(arr.data, w, h, w * c, QImage.Format_RGB888)
    return QPixmap.fromImage(img)


class IHCWindow(QWidget):
    go_home = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.selected_patient = None
        self.image_path = None
        self._metrics = {}
        self._worker = None
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Navbar
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(56)
        nl = QHBoxLayout(navbar)
        nl.setContentsMargins(20, 0, 20, 0)
        back = QPushButton("← Home")
        back.setObjectName("backBtn")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self.go_home.emit)
        nl.addWidget(back)
        nl.addSpacing(16)
        nl.addWidget(QLabel("IHC / DAB Analysis", objectName="navTitle"))
        nl.addStretch()
        root.addWidget(navbar)

        # Content
        content = QHBoxLayout()
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(20)

        # ── Left: images (2x2) ──
        left = QFrame()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.img_labels = {}
        configs = [
            ("original",  "Original Image",       0, 0),
            ("tissue",    "Tissue Detection",      0, 1),
            ("dab",       "DAB Extraction",        1, 0),
            ("overlay",   "DAB Overlay",           1, 1),
        ]
        for key, caption, r, c in configs:
            frame = QFrame()
            frame.setObjectName("imgFrame")
            fl = QVBoxLayout(frame)
            fl.setSpacing(4)
            fl.setContentsMargins(6, 6, 6, 6)
            lbl = QLabel(f"[ {caption} ]")
            lbl.setObjectName("imgPlaceholder")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumSize(240, 200)
            cap = QLabel(caption)
            cap.setObjectName("imgCaption")
            cap.setAlignment(Qt.AlignCenter)
            fl.addWidget(lbl, 1)
            fl.addWidget(cap)
            grid.addWidget(frame, r, c)
            self.img_labels[key] = lbl
        ll.addLayout(grid, 1)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("📂  Load Image")
        self.load_btn.setObjectName("primaryBtn")
        self.load_btn.setFixedHeight(40)
        self.load_btn.setCursor(Qt.PointingHandCursor)
        self.load_btn.clicked.connect(self._load_image)
        self.analyze_btn = QPushButton("🔬  Analyze DAB")
        self.analyze_btn.setObjectName("analyzeBtn")
        self.analyze_btn.setFixedHeight(40)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._run_analysis)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.analyze_btn)
        ll.addLayout(btn_row)
        content.addWidget(left, 3)

        # ── Right: metrics + patient ──
        right = QFrame()
        right.setObjectName("panel")
        right.setFixedWidth(300)
        rl = QVBoxLayout(right)
        rl.setSpacing(14)

        # Patient
        pf = QFrame()
        pf.setObjectName("subPanel")
        pfl = QVBoxLayout(pf)
        pfl.setSpacing(6)
        pfl.addWidget(QLabel("Patient", objectName="sectionLabel"))
        self.patient_display = QLabel("No patient selected")
        self.patient_display.setObjectName("patientDisplay")
        self.patient_display.setWordWrap(True)
        sel_btn = QPushButton("Select / Add Patient")
        sel_btn.setObjectName("secondaryBtn")
        sel_btn.setFixedHeight(34)
        sel_btn.clicked.connect(self._select_patient)
        pfl.addWidget(self.patient_display)
        pfl.addWidget(sel_btn)
        rl.addWidget(pf)

        # Metrics
        mf = QFrame()
        mf.setObjectName("subPanel")
        mfl = QVBoxLayout(mf)
        mfl.setSpacing(6)
        mfl.addWidget(QLabel("DAB Metrics", objectName="sectionLabel"))
        self.metric_labels = {}
        for key in ["DAB Coverage (%)", "DAB Regions", "Mean Intensity",
                    "Tissue Area (pixels)", "Brown Pixels"]:
            row = QHBoxLayout()
            k = QLabel(key)
            k.setObjectName("metricKey")
            v = QLabel("—")
            v.setObjectName("metricVal")
            row.addWidget(k)
            row.addStretch()
            row.addWidget(v)
            mfl.addLayout(row)
            self.metric_labels[key] = v
        rl.addWidget(mf)

        # Notes
        nf = QFrame()
        nf.setObjectName("subPanel")
        nfl = QVBoxLayout(nf)
        nfl.addWidget(QLabel("Notes", objectName="sectionLabel"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setObjectName("notesEdit")
        self.notes_edit.setPlaceholderText("Clinical notes...")
        self.notes_edit.setFixedHeight(80)
        nfl.addWidget(self.notes_edit)
        rl.addWidget(nf)

        self.save_btn = QPushButton("💾  Save to Patient Record")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_result)
        rl.addWidget(self.save_btn)
        rl.addStretch()
        content.addWidget(right)

        wrapper = QWidget()
        wrapper.setObjectName("contentArea")
        wrapper.setLayout(content)
        root.addWidget(wrapper, 1)

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if path:
            self.image_path = path
            pix = QPixmap(path)
            lbl = self.img_labels["original"]
            lbl.setPixmap(pix.scaled(lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            for k in ["tissue", "dab", "overlay"]:
                self.img_labels[k].setText(f"[ — ]")
                self.img_labels[k].setPixmap(QPixmap())
            self.analyze_btn.setEnabled(True)
            self.save_btn.setEnabled(False)
            for v in self.metric_labels.values():
                v.setText("—")

    def _select_patient(self):
        dlg = PatientSelector(self.doctor, parent=self)
        dlg.patient_selected.connect(self._on_patient_selected)
        dlg.exec()

    def _on_patient_selected(self, patient):
        self.selected_patient = patient
        name = f"{patient['first_name']} {patient['last_name']}"
        self.patient_display.setText(f"{name}\n{patient.get('tissue','')} · {patient.get('marqueur','')}")

    def _run_analysis(self):
        if not self.image_path:
            return
        self.analyze_btn.setEnabled(False)
        for v in self.metric_labels.values():
            v.setText("…")
        self._worker = DABWorker(self.image_path)
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, original, tissue_mask, dab_result, metrics, overlay):
        self._metrics = metrics

        def _show(key, arr):
            if arr is None:
                return
            lbl = self.img_labels[key]
            pix = _np_to_pixmap(arr)
            if pix:
                lbl.setPixmap(pix.scaled(lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        _show("original", original)

        if tissue_mask is not None:
            vis = cv2.cvtColor(tissue_mask, cv2.COLOR_GRAY2RGB)
            _show("tissue", vis)

        _show("dab", dab_result)
        _show("overlay", overlay)

        for key, lbl in self.metric_labels.items():
            val = metrics.get(key)
            lbl.setText(str(val) if val is not None else "—")

        self.analyze_btn.setEnabled(True)
        self.save_btn.setEnabled(self.selected_patient is not None)

    def _on_error(self, msg):
        QMessageBox.critical(self, "Analysis Error", msg)
        self.analyze_btn.setEnabled(True)

    def _save_result(self):
        if not self.selected_patient:
            QMessageBox.warning(self, "No Patient", "Please select a patient first.")
            return
        patient = self.selected_patient
        folder = patient.get("folder_path", "")
        dest_path = self.image_path
        if folder:
            img_folder = os.path.join(folder, "images")
            os.makedirs(img_folder, exist_ok=True)
            dest_path = os.path.join(img_folder, os.path.basename(self.image_path))
            if not os.path.exists(dest_path):
                shutil.copy2(self.image_path, dest_path)

        notes = self.notes_edit.toPlainText().strip()
        add_analysis(
            patient_id=patient["id"],
            doctor_id=self.doctor["id"],
            image_path=dest_path,
            analysis_type="IHC",
            dab_coverage=self._metrics.get("DAB Coverage (%)"),
            dab_regions=self._metrics.get("DAB Regions"),
            mean_intensity=self._metrics.get("Mean Intensity"),
            notes=notes or None
        )
        QMessageBox.information(self, "Saved", "IHC analysis saved to patient record.")
        self.save_btn.setEnabled(False)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; background: #F0F4F8; }
            #navbar { background: #FFFFFF; border-bottom: 1px solid #E5E7EB; }
            #navTitle { font-size: 16px; font-weight: 700; color: #1A2B45; }
            #backBtn { background: none; border: none; color: #2E86C1;
                       font-size: 14px; font-weight: 600; }
            #backBtn:hover { color: #1A5276; }
            #contentArea { background: #F0F4F8; }
            #panel { background: #FFFFFF; border-radius: 12px;
                     border: 1px solid #E5E7EB; padding: 14px; }
            #subPanel { background: #F7FBFE; border-radius: 8px;
                        border: 1px solid #EBF5FB; padding: 10px; }
            #imgFrame { background: #F7F9FC; border-radius: 8px;
                        border: 1px solid #E5E7EB; }
            #imgPlaceholder { color: #AAB7B8; font-size: 13px;
                              border-radius: 6px; }
            #imgCaption { font-size: 11px; color: #5D6D7E; font-weight: 600; }
            #sectionLabel { font-size: 11px; font-weight: 700; color: #2E86C1;
                             text-transform: uppercase; letter-spacing: 0.5px; }
            #patientDisplay { font-size: 13px; color: #1A2B45; }
            #metricKey { font-size: 12px; color: #5D6D7E; }
            #metricVal { font-size: 13px; font-weight: 600; color: #1A2B45; }
            #notesEdit { border: 1px solid #D5D8DC; border-radius: 6px;
                         font-size: 13px; padding: 4px; }
            #primaryBtn { background: #2E86C1; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 14px; }
            #primaryBtn:hover { background: #1A5276; }
            #primaryBtn:disabled { background: #AED6F1; }
            #analyzeBtn { background: #1A5276; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 14px; }
            #analyzeBtn:hover { background: #154360; }
            #analyzeBtn:disabled { background: #AED6F1; }
            #secondaryBtn { background: #ECF0F1; color: #2C3E50; border: 1px solid #D5D8DC;
                            border-radius: 7px; font-size: 13px; }
            #secondaryBtn:hover { background: #D5D8DC; }
        """)