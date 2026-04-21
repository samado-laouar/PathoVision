import os, shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QScrollArea, QMessageBox, QTextEdit,
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QFont
import numpy as np
import cv2

from core.predictor import Predictor
from db.patient_dao import add_analysis, get_patient_by_id
from ui.patients.patient_selector import PatientSelector

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "models", "best_colon_cancer_model.keras")
print(f"Loading model from: {MODEL_PATH}")

class PredictWorker(QThread):
    finished = Signal(str, float)
    error    = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            predictor = Predictor(MODEL_PATH)
            label, prob = predictor.predict(self.image_path)
            self.finished.emit(label, float(prob))
        except Exception as e:
            self.error.emit(str(e))


class HistologyWindow(QWidget):
    go_home = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor = doctor
        self.selected_patient = None
        self.image_path = None
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
        title = QLabel("Histology Analysis")
        title.setObjectName("navTitle")
        nl.addWidget(back)
        nl.addSpacing(16)
        nl.addWidget(title)
        nl.addStretch()
        root.addWidget(navbar)

        # Content
        content = QHBoxLayout()
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(20)

        # ── Left: image panel ──
        left = QFrame()
        left.setObjectName("panel")
        left.setMinimumWidth(480)
        ll = QVBoxLayout(left)
        ll.setSpacing(12)

        self.image_label = QLabel("No image loaded\n\nClick 'Load Image' to begin")
        self.image_label.setObjectName("imagePlaceholder")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(360)
        ll.addWidget(self.image_label, 1)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("📂  Load Image")
        self.load_btn.setObjectName("primaryBtn")
        self.load_btn.setFixedHeight(40)
        self.load_btn.setCursor(Qt.PointingHandCursor)
        self.load_btn.clicked.connect(self._load_image)
        self.analyze_btn = QPushButton("🔍  Analyze")
        self.analyze_btn.setObjectName("analyzeBtn")
        self.analyze_btn.setFixedHeight(40)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._run_analysis)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.analyze_btn)
        ll.addLayout(btn_row)
        content.addWidget(left, 3)

        # ── Right: results panel ──
        right = QFrame()
        right.setObjectName("panel")
        right.setFixedWidth(320)
        rl = QVBoxLayout(right)
        rl.setSpacing(14)

        # Patient selector
        patient_frame = QFrame()
        patient_frame.setObjectName("subPanel")
        pfl = QVBoxLayout(patient_frame)
        pfl.setSpacing(6)
        pfl.addWidget(QLabel("Patient", objectName="sectionLabel"))
        self.patient_display = QLabel("No patient selected")
        self.patient_display.setObjectName("patientDisplay")
        self.patient_display.setWordWrap(True)
        select_patient_btn = QPushButton("Select / Add Patient")
        select_patient_btn.setObjectName("secondaryBtn")
        select_patient_btn.setFixedHeight(36)
        select_patient_btn.setCursor(Qt.PointingHandCursor)
        select_patient_btn.clicked.connect(self._select_patient)
        pfl.addWidget(self.patient_display)
        pfl.addWidget(select_patient_btn)
        rl.addWidget(patient_frame)

        # Result
        result_frame = QFrame()
        result_frame.setObjectName("subPanel")
        rfl = QVBoxLayout(result_frame)
        rfl.setSpacing(6)
        rfl.addWidget(QLabel("Result", objectName="sectionLabel"))
        self.result_label = QLabel("—")
        self.result_label.setObjectName("resultLabel")
        self.result_label.setAlignment(Qt.AlignCenter)
        rfl.addWidget(self.result_label)
        rl.addWidget(result_frame)

        # Notes
        notes_frame = QFrame()
        notes_frame.setObjectName("subPanel")
        nfl = QVBoxLayout(notes_frame)
        nfl.addWidget(QLabel("Notes", objectName="sectionLabel"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setObjectName("notesEdit")
        self.notes_edit.setPlaceholderText("Add clinical notes here...")
        self.notes_edit.setFixedHeight(90)
        nfl.addWidget(self.notes_edit)
        rl.addWidget(notes_frame)

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
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.analyze_btn.setEnabled(True)
            self.result_label.setText("—")
            self.save_btn.setEnabled(False)

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
        self.result_label.setText("Analyzing…")
        self._worker = PredictWorker(self.image_path)
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, label, prob):
        self.result_label.setText(label)
        self.result_label.setProperty("pathologique", label == "Pathologique")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        self.analyze_btn.setEnabled(True)
        self._last_label = label
        self._last_prob  = prob
        self.save_btn.setEnabled(self.selected_patient is not None)

    def _on_error(self, msg):
        self.result_label.setText("Error")
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
            analysis_type="Histology",
            result_label=self._last_label,
            result_prob=self._last_prob,
            notes=notes or None
        )
        QMessageBox.information(self, "Saved", "Analysis saved to patient record.")
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
                     border: 1px solid #E5E7EB; padding: 16px; }
            #subPanel { background: #F7FBFE; border-radius: 8px;
                        border: 1px solid #EBF5FB; padding: 12px; }
            #imagePlaceholder {
                background: #F7F9FC; border: 2px dashed #AED6F1;
                border-radius: 10px; color: #AAB7B8; font-size: 14px;
            }
            #sectionLabel { font-size: 12px; font-weight: 700; color: #2E86C1;
                             text-transform: uppercase; letter-spacing: 0.5px; }
            #patientDisplay { font-size: 13px; color: #1A2B45; }
            #resultLabel { font-size: 22px; font-weight: 700; color: #1A2B45; padding: 8px; }
            #resultLabel[pathologique="true"] { color: #C0392B; }
            #resultLabel[pathologique="false"] { color: #1E8449; }
            #probLabel { font-size: 13px; color: #5D6D7E; }
            #notesEdit { border: 1px solid #D5D8DC; border-radius: 6px;
                         font-size: 13px; padding: 6px; }
            #primaryBtn { background: #2E86C1; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 16px; }
            #primaryBtn:hover { background: #1A5276; }
            #primaryBtn:disabled { background: #AED6F1; }
            #analyzeBtn { background: #1E8449; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 16px; }
            #analyzeBtn:hover { background: #196F3D; }
            #analyzeBtn:disabled { background: #A9DFBF; }
            #secondaryBtn { background: #ECF0F1; color: #2C3E50; border: 1px solid #D5D8DC;
                            border-radius: 7px; font-size: 13px; }
            #secondaryBtn:hover { background: #D5D8DC; }
        """)