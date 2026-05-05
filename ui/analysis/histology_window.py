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

_MODELS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "models")
MODEL_PATH       = os.path.join(_MODELS_DIR, "best_resnet50.keras")
GLAND_MODEL_PATH = os.path.join(_MODELS_DIR, "best_model_tf.keras")
print(f"Classifier  : {MODEL_PATH}")
print(f"Gland model : {GLAND_MODEL_PATH}")


# ── Background worker ─────────────────────────────────────────────────────────
class PredictWorker(QThread):
    # Emits: label, prob, confidence_tier, segmented, overlay_rgb (H,W,3 uint8 or None),
    #        gland_dice (float or -1), gland_quality (str)
    finished = Signal(str, float, str, bool, object, float, str)
    error    = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            predictor = Predictor(
                classifier_model_path = MODEL_PATH,
                gland_model_path      = GLAND_MODEL_PATH,
            )
            r = predictor.predict(self.image_path)
            self._gland_mask = r.get('gland_mask')   # store for parent to retrieve
            self.finished.emit(
                r['label'],
                float(r['probability']),
                r['confidence_tier'],
                r['segmented'],
                r['overlay'],
                float(r['gland_dice'])  if r['gland_dice']    is not None else -1.0,
                r['gland_quality']      if r['gland_quality']  is not None else "",
            )
        except Exception as e:
            self.error.emit(str(e))


# ── Main window ───────────────────────────────────────────────────────────────
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
        self._gland_mask      = None   # (256,256) float32 — stored after segmentation
        self._build_ui()
        self._apply_styles()

    # ── UI construction ───────────────────────────────────────────────────────

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

        # ── Left: image panel ─────────────────────────────────────────────────
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

        # ── Right: results panel ──────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("panel")
        right.setFixedWidth(340)
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

        # Classification result
        result_frame = QFrame()
        result_frame.setObjectName("subPanel")
        rfl = QVBoxLayout(result_frame)
        rfl.setSpacing(6)
        rfl.addWidget(QLabel("Result", objectName="sectionLabel"))
        self.result_label = QLabel("—")
        self.result_label.setObjectName("resultLabel")
        self.result_label.setAlignment(Qt.AlignCenter)
        rfl.addWidget(self.result_label)

        # Confidence badge (prob + tier)
        self.conf_label = QLabel("")
        self.conf_label.setObjectName("confLabel")
        self.conf_label.setAlignment(Qt.AlignCenter)
        self.conf_label.hide()
        rfl.addWidget(self.conf_label)
        rl.addWidget(result_frame)

        # Gland segmentation panel (hidden until result arrives)
        self.gland_frame = QFrame()
        self.gland_frame.setObjectName("subPanel")
        gfl = QVBoxLayout(self.gland_frame)
        gfl.setSpacing(6)
        gfl.addWidget(QLabel("Gland Segmentation", objectName="sectionLabel"))

        self.dice_label = QLabel("")
        self.dice_label.setObjectName("diceLabel")
        self.dice_label.setAlignment(Qt.AlignCenter)
        gfl.addWidget(self.dice_label)

        self.quality_label = QLabel("")
        self.quality_label.setObjectName("qualityLabel")
        self.quality_label.setWordWrap(True)
        self.quality_label.setAlignment(Qt.AlignCenter)
        gfl.addWidget(self.quality_label)

        # Toggle button: show overlay / show original
        self.toggle_btn = QPushButton("🔬  Show Overlay")
        self.toggle_btn.setObjectName("secondaryBtn")
        self.toggle_btn.setFixedHeight(34)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_overlay)
        gfl.addWidget(self.toggle_btn)

        # Review mask button
        self.review_mask_btn = QPushButton("✏️  Review / Edit Mask")
        self.review_mask_btn.setObjectName("reviewMaskBtn")
        self.review_mask_btn.setFixedHeight(34)
        self.review_mask_btn.setCursor(Qt.PointingHandCursor)
        self.review_mask_btn.clicked.connect(self._open_mask_review)
        gfl.addWidget(self.review_mask_btn)

        self.gland_frame.hide()
        rl.addWidget(self.gland_frame)

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

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if path:
            self.image_path     = path
            self._overlay_array = None
            self._showing_overlay = False
            pix = QPixmap(path)
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.analyze_btn.setEnabled(True)
            self.result_label.setText("—")
            self.conf_label.hide()
            self.gland_frame.hide()
            self.save_btn.setEnabled(False)

    def _select_patient(self):
        dlg = PatientSelector(self.doctor, parent=self)
        dlg.patient_selected.connect(self._on_patient_selected)
        dlg.exec()

    def _on_patient_selected(self, patient):
        self.selected_patient = patient
        name = f"{patient['first_name']} {patient['last_name']}"
        self.patient_display.setText(
            f"{name}\n{patient.get('tissue', '')} · {patient.get('marqueur', '')}"
        )

    def _run_analysis(self):
        if not self.image_path:
            return
        self.analyze_btn.setEnabled(False)
        self.result_label.setText("Analyzing…")
        self.conf_label.hide()
        self.gland_frame.hide()
        self._worker = PredictWorker(self.image_path)
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, label, prob, tier, segmented, overlay_rgb, gland_dice, gland_quality):
        # ── Classification result ─────────────────────────────────────────────
        self.result_label.setText(label)
        self.result_label.setProperty("pathologique", label == "Pathologique")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        # Confidence badge
        tier_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(tier, "")
        self.conf_label.setText(f"{tier_emoji}  {prob * 100:.1f}% — {tier.capitalize()} confidence")
        self.conf_label.show()

        self.analyze_btn.setEnabled(True)
        self._last_label = label
        self._last_prob  = prob
        self.save_btn.setEnabled(self.selected_patient is not None)

        # ── Gland segmentation results ────────────────────────────────────────
        self._overlay_array   = overlay_rgb   # ndarray (H,W,3) or None
        self._gland_mask      = getattr(self._worker, '_gland_mask', None)
        self._showing_overlay = False

        if segmented and overlay_rgb is not None:
            dice_pct = gland_dice * 100
            self.dice_label.setText(f"Dice Score: {dice_pct:.1f}%")
            self.quality_label.setText(gland_quality)
            # Color dice label by quality
            if gland_dice >= 0.75:
                self.dice_label.setStyleSheet("color: #1E8449; font-weight: 700; font-size: 15px;")
            elif gland_dice >= 0.50:
                self.dice_label.setStyleSheet("color: #D68910; font-weight: 700; font-size: 15px;")
            else:
                self.dice_label.setStyleSheet("color: #C0392B; font-weight: 700; font-size: 15px;")
            self.toggle_btn.setText("🔬  Show Overlay")
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
            # Fallback: derive approximate mask from orange regions in the overlay
            diff = self._overlay_array.astype(np.int16) - orig.astype(np.int16)
            orange_channel = diff[:, :, 0] - diff[:, :, 2]
            gland_mask = np.clip(orange_channel, 0, 255).astype(np.float32) / 255.0

        if gland_mask is None:
            QMessageBox.information(self, "No Mask", "No segmentation mask is available yet.")
            return

        dlg = MaskReviewDialog(self.image_path, orig, gland_mask, parent=self)
        dlg.exec()

    def _toggle_overlay(self):
        """Switch the left image panel between the original and the gland overlay."""
        if self._overlay_array is None:
            return

        if not self._showing_overlay:
            self._display_ndarray(self._overlay_array)
            self.toggle_btn.setText("🖼️  Show Original")
            self._showing_overlay = True
        else:
            pix = QPixmap(self.image_path)
            self.image_label.setPixmap(
                pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.toggle_btn.setText("🔬  Show Overlay")
            self._showing_overlay = False

    def _display_ndarray(self, rgb_array: np.ndarray):
        """Convert a (H,W,3) uint8 RGB ndarray to QPixmap and show it."""
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
            patient_id   = patient["id"],
            doctor_id    = self.doctor["id"],
            image_path   = dest_path,
            analysis_type= "Histology",
            result_label = self._last_label,
            result_prob  = self._last_prob,
            notes        = notes or None,
        )
        QMessageBox.information(self, "Saved", "Analysis saved to patient record.")
        self.save_btn.setEnabled(False)

    # ── Styles ────────────────────────────────────────────────────────────────

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
            #resultLabel[pathologique="true"]  { color: #C0392B; }
            #resultLabel[pathologique="false"] { color: #1E8449; }
            #confLabel   { font-size: 12px; color: #5D6D7E; padding-bottom: 4px; }
            #diceLabel   { font-size: 15px; font-weight: 700; padding: 4px 0; }
            #qualityLabel { font-size: 12px; color: #5D6D7E; }
            #notesEdit { border: 1px solid #D5D8DC; border-radius: 6px;
                         font-size: 13px; padding: 6px; }
            #primaryBtn { background: #2E86C1; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 16px; }
            #primaryBtn:hover    { background: #1A5276; }
            #primaryBtn:disabled { background: #AED6F1; }
            #analyzeBtn { background: #1E8449; color: white; border: none;
                          border-radius: 8px; font-size: 13px; font-weight: 600; padding: 0 16px; }
            #analyzeBtn:hover    { background: #196F3D; }
            #analyzeBtn:disabled { background: #A9DFBF; }
            #secondaryBtn { background: #ECF0F1; color: #2C3E50; border: 1px solid #D5D8DC;
                            border-radius: 7px; font-size: 13px; }
            #secondaryBtn:hover { background: #D5D8DC; }
            #reviewMaskBtn { background: #FEF9E7; color: #B7950B; border: 1px solid #F9E79F;
                             border-radius: 7px; font-size: 13px; font-weight: 600; }
            #reviewMaskBtn:hover { background: #F39C12; color: white; border-color: #F39C12; }
        """)