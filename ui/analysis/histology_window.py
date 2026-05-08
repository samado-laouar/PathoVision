import os, shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QMessageBox, QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QFont
import numpy as np
import cv2

from core.predictor import Predictor
from db.patient_dao import add_analysis
from ui.patients.patient_selector import PatientSelector
from ui._style import BASE_QSS, C

_MODELS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "models")
MODEL_PATH       = os.path.join(_MODELS_DIR, "best_resnet50.keras")
GLAND_MODEL_PATH = os.path.join(_MODELS_DIR, "best_model_tf.keras")


# ── Worker ─────────────────────────────────────────────────────────────────────
class PredictWorker(QThread):
    finished = Signal(str, float, str, bool, object, float, str)
    error    = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            predictor = Predictor(
                classifier_model_path=MODEL_PATH,
                gland_model_path=GLAND_MODEL_PATH,
            )
            r = predictor.predict(self.image_path)
            self._gland_mask = r.get("gland_mask")
            self.finished.emit(
                r["label"],
                float(r["probability"]),
                r["confidence_tier"],
                r["segmented"],
                r["overlay"],
                float(r["gland_dice"]) if r["gland_dice"] is not None else -1.0,
                r["gland_quality"] if r["gland_quality"] is not None else "",
            )
        except Exception as e:
            self.error.emit(str(e))


# ── Window ─────────────────────────────────────────────────────────────────────
class HistologyWindow(QWidget):
    go_home = Signal()

    def __init__(self, doctor: dict, parent=None):
        super().__init__(parent)
        self.doctor           = doctor
        self.selected_patient = None
        self.image_path       = None
        self._worker          = None
        self._last_label      = None
        self._last_prob       = None
        self._gland_mask      = None
        self._overlay_array   = None
        self._showing_overlay = False
        self._build_ui()
        self.setStyleSheet(BASE_QSS + _HISTO_EXTRA)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Navbar
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(56)
        nl = QHBoxLayout(navbar)
        nl.setContentsMargins(24, 0, 24, 0)
        back = QPushButton("← Home")
        back.setObjectName("backBtn")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self.go_home.emit)
        nav_title = QLabel("Histology Analysis")
        nav_title.setObjectName("navTitle")
        nl.addWidget(back)
        nl.addSpacing(12)
        nl.addWidget(nav_title)
        nl.addStretch()
        root.addWidget(navbar)

        # Content
        content = QHBoxLayout()
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(18)

        # ── Left: image viewer ─────────────────────────────────────────────
        left = QFrame()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setSpacing(12)
        ll.setContentsMargins(16, 16, 16, 16)

        self.image_label = QLabel("No image loaded\n\nClick  Load Image  to begin")
        self.image_label.setObjectName("imagePlaceholder")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(380)
        ll.addWidget(self.image_label, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.load_btn = QPushButton("Load Image")
        self.load_btn.setObjectName("primaryBtn")
        self.load_btn.setFixedHeight(40)
        self.load_btn.setCursor(Qt.PointingHandCursor)
        self.load_btn.clicked.connect(self._load_image)

        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setObjectName("analyzeBtn")
        self.analyze_btn.setFixedHeight(40)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._run_analysis)

        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.analyze_btn)
        ll.addLayout(btn_row)
        content.addWidget(left, 3)

        # ── Right: results ─────────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("panel")
        right.setFixedWidth(320)
        rl = QVBoxLayout(right)
        rl.setSpacing(12)
        rl.setContentsMargins(16, 16, 16, 16)

        # Patient
        pf = QFrame()
        pf.setObjectName("subPanel")
        pfl = QVBoxLayout(pf)
        pfl.setSpacing(6)
        pfl.setContentsMargins(12, 12, 12, 12)
        pfl.addWidget(QLabel("Patient", objectName="sectionLabel"))
        self.patient_display = QLabel("No patient selected")
        self.patient_display.setObjectName("patientDisplay")
        self.patient_display.setWordWrap(True)
        sel_btn = QPushButton("Select / Add Patient")
        sel_btn.setObjectName("secondaryBtn")
        sel_btn.setFixedHeight(34)
        sel_btn.setCursor(Qt.PointingHandCursor)
        sel_btn.clicked.connect(self._select_patient)
        pfl.addWidget(self.patient_display)
        pfl.addWidget(sel_btn)
        rl.addWidget(pf)

        # Result
        rf = QFrame()
        rf.setObjectName("subPanel")
        rfl = QVBoxLayout(rf)
        rfl.setSpacing(6)
        rfl.setContentsMargins(12, 12, 12, 12)
        rfl.addWidget(QLabel("Result", objectName="sectionLabel"))
        self.result_label = QLabel("—")
        self.result_label.setObjectName("resultLabel")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.conf_label = QLabel("")
        self.conf_label.setObjectName("confLabel")
        self.conf_label.setAlignment(Qt.AlignCenter)
        self.conf_label.hide()
        rfl.addWidget(self.result_label)
        rfl.addWidget(self.conf_label)
        rl.addWidget(rf)

        # Gland segmentation
        self.gland_frame = QFrame()
        self.gland_frame.setObjectName("subPanel")
        gfl = QVBoxLayout(self.gland_frame)
        gfl.setSpacing(6)
        gfl.setContentsMargins(12, 12, 12, 12)
        gfl.addWidget(QLabel("Gland Segmentation", objectName="sectionLabel"))
        self.dice_label    = QLabel("—")
        self.dice_label.setObjectName("diceLabel")
        self.quality_label = QLabel("")
        self.quality_label.setObjectName("qualityLabel")
        self.toggle_btn = QPushButton("Show Overlay")
        self.toggle_btn.setObjectName("secondaryBtn")
        self.toggle_btn.setFixedHeight(34)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_overlay)
        self.review_btn = QPushButton("Review Mask")
        self.review_btn.setObjectName("dangerBtn")
        self.review_btn.setFixedHeight(34)
        self.review_btn.setCursor(Qt.PointingHandCursor)
        self.review_btn.clicked.connect(self._open_mask_review)
        gfl.addWidget(self.dice_label)
        gfl.addWidget(self.quality_label)
        seg_row = QHBoxLayout()
        seg_row.addWidget(self.toggle_btn)
        seg_row.addWidget(self.review_btn)
        gfl.addLayout(seg_row)
        self.gland_frame.hide()
        rl.addWidget(self.gland_frame)

        # Notes
        nf = QFrame()
        nf.setObjectName("subPanel")
        nfl = QVBoxLayout(nf)
        nfl.setSpacing(6)
        nfl.setContentsMargins(12, 12, 12, 12)
        nfl.addWidget(QLabel("Notes", objectName="sectionLabel"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setObjectName("notesEdit")
        self.notes_edit.setPlaceholderText("Clinical notes...")
        self.notes_edit.setFixedHeight(80)
        nfl.addWidget(self.notes_edit)
        rl.addWidget(nf)

        self.save_btn = QPushButton("Save to Patient Record")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setEnabled(False)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_result)
        rl.addWidget(self.save_btn)
        rl.addStretch()
        content.addWidget(right)

        wrapper = QWidget()
        wrapper.setObjectName("contentArea")
        wrapper.setLayout(content)
        root.addWidget(wrapper, 1)

    # ── Slots ──────────────────────────────────────────────────────────────────

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
            self.save_btn.setEnabled(False)
            self.conf_label.hide()
            self.gland_frame.hide()
            self.result_label.setText("—")
            self._showing_overlay = False

    def _select_patient(self):
        dlg = PatientSelector(self.doctor, parent=self)
        dlg.patient_selected.connect(self._on_patient_selected)
        dlg.exec()

    def _on_patient_selected(self, patient):
        self.selected_patient = patient
        name = f"{patient['first_name']} {patient['last_name']}"
        self.patient_display.setText(
            f"{name}\n{patient.get('tissue', '')}  ·  {patient.get('marqueur', '')}"
        )

    def _run_analysis(self):
        if not self.image_path:
            return
        self.analyze_btn.setEnabled(False)
        self.result_label.setText("Analyzing...")
        self.conf_label.hide()
        self.gland_frame.hide()
        self._worker = PredictWorker(self.image_path)
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, label, prob, tier, segmented, overlay_rgb, gland_dice, gland_quality):
        self.result_label.setText(label)
        self.result_label.setProperty("pathologique", label == "Pathologique")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        tier_map = {"high": "High", "medium": "Medium", "low": "Low"}
        self.conf_label.setText(f"{prob * 100:.1f}%  —  {tier_map.get(tier, tier)} confidence")
        self.conf_label.show()

        self.analyze_btn.setEnabled(True)
        self._last_label    = label
        self._last_prob     = prob
        self._overlay_array = overlay_rgb
        self._gland_mask    = getattr(self._worker, "_gland_mask", None)
        self._showing_overlay = False
        self.save_btn.setEnabled(self.selected_patient is not None)

        if segmented and overlay_rgb is not None:
            dice_pct = gland_dice * 100
            self.dice_label.setText(f"Dice Score: {dice_pct:.1f}%")
            self.quality_label.setText(gland_quality)
            if gland_dice >= 0.75:
                color = C["success"]
            elif gland_dice >= 0.50:
                color = C["warning"]
            else:
                color = C["danger"]
            self.dice_label.setStyleSheet(
                f"color: {color}; font-weight: 700; font-size: 15px;"
            )
            self.toggle_btn.setText("Show Overlay")
            self.gland_frame.show()
        else:
            self.gland_frame.hide()

    def _on_error(self, msg):
        self.result_label.setText("Error")
        self.conf_label.hide()
        self.analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "Analysis Error", msg)

    def _open_mask_review(self):
        from ui.analysis.mask_review_dialog import MaskReviewDialog
        if self.image_path is None:
            return
        orig = cv2.cvtColor(cv2.imread(self.image_path), cv2.COLOR_BGR2RGB)
        gland_mask = self._gland_mask
        if gland_mask is None and self._overlay_array is not None:
            diff = self._overlay_array.astype(np.int16) - orig.astype(np.int16)
            orange_channel = diff[:, :, 0] - diff[:, :, 2]
            gland_mask = np.clip(orange_channel, 0, 255).astype(np.float32) / 255.0
        if gland_mask is None:
            QMessageBox.information(self, "No Mask", "No segmentation mask available yet.")
            return
        dlg = MaskReviewDialog(self.image_path, orig, gland_mask, parent=self)
        dlg.exec()

    def _toggle_overlay(self):
        if self._overlay_array is None:
            return
        if not self._showing_overlay:
            self._display_ndarray(self._overlay_array)
            self.toggle_btn.setText("Show Original")
            self._showing_overlay = True
        else:
            pix = QPixmap(self.image_path)
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.toggle_btn.setText("Show Overlay")
            self._showing_overlay = False

    def _display_ndarray(self, rgb_array: np.ndarray):
        h, w, ch = rgb_array.shape
        qimg = QImage(rgb_array.data, w, h, w * ch, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg)
        self.image_label.setPixmap(
            pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _save_result(self):
        if not self.selected_patient:
            QMessageBox.warning(self, "No Patient", "Please select a patient first.")
            return
        patient   = self.selected_patient
        folder    = patient.get("folder_path", "")
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
            notes=notes or None,
        )
        QMessageBox.information(self, "Saved", "Analysis saved to patient record.")
        self.save_btn.setEnabled(False)


# ── Extra styles specific to this window ───────────────────────────────────────
_HISTO_EXTRA = f"""
    #contentArea {{ background: {C['surface']}; }}
    #imagePlaceholder {{
        background: {C['surface']};
        border: 2px dashed {C['border']};
        border-radius: 10px;
        color: {C['ink_soft']};
        font-size: 13px;
    }}
    #resultLabel {{
        font-size: 22px; font-weight: 700;
        color: {C['ink']};
        padding: 10px;
        border-radius: 8px;
    }}
    #resultLabel[pathologique="true"]  {{
        color: {C['danger']};
        background: {C['danger_lt']};
    }}
    #resultLabel[pathologique="false"] {{
        color: {C['success']};
        background: {C['success_lt']};
    }}
    #confLabel {{
        font-size: 12px; color: {C['ink_soft']};
        padding-bottom: 4px;
    }}
    #diceLabel  {{ font-size: 15px; font-weight: 700; padding: 2px 0; }}
    #qualityLabel {{ font-size: 12px; color: {C['ink_soft']}; }}
"""