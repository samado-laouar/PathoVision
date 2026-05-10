import os, shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QMessageBox, QTextEdit, QSizePolicy,
    QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import numpy as np
import cv2

from core.predictor import Predictor
from db.patient_dao import add_analysis
from ui.patients.patient_selector import PatientSelector
from ui._style import BASE_QSS, C

_MODELS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "models")
MODEL_PATH       = os.path.join(_MODELS_DIR, "best_resnet50_256.keras")
GLAND_MODEL_PATH = os.path.join(_MODELS_DIR, "best_attention_unet.keras")


# ── Worker ─────────────────────────────────────────────────────────────────────
class PredictWorker(QThread):
    # label, prob, tier, segmented, overlay, dice, quality, morpho_report
    finished = Signal(str, float, str, bool, object, float, str, object)
    error    = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path   = image_path
        self._gland_mask  = None

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
                float(r["gland_dice"])   if r["gland_dice"]   is not None else -1.0,
                r["gland_quality"]       if r["gland_quality"] is not None else "",
                r["morpho_report"],      # MorphometricReport | None
            )
        except Exception as e:
            self.error.emit(str(e))


# ── Window ─────────────────────────────────────────────────────────────────────
class HistologyWindow(QWidget):
    go_home = Signal()

    # Image view modes
    _MODE_ORIGINAL   = "original"
    _MODE_OVERLAY    = "overlay"
    _MODE_ANNOTATED  = "annotated"
    _MODE_TUMOR_CROP = "tumor_crop"

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
        self._morpho_report   = None
        self._view_mode       = self._MODE_ORIGINAL
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

        # Content row
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
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ll.addWidget(self.image_label, 1)

        # View toggle row (shown after segmentation)
        self.view_row = QFrame()
        self.view_row.setObjectName("viewRow")
        vr = QHBoxLayout(self.view_row)
        vr.setSpacing(6)
        vr.setContentsMargins(0, 0, 0, 0)
        self.btn_original   = self._view_btn("Original",    self._MODE_ORIGINAL)
        self.btn_overlay    = self._view_btn("Overlay",     self._MODE_OVERLAY)
        self.btn_annotated  = self._view_btn("Annotated",   self._MODE_ANNOTATED)
        self.btn_tumor_crop = self._view_btn("Tumor Crop",  self._MODE_TUMOR_CROP)
        for b in (self.btn_original, self.btn_overlay, self.btn_annotated, self.btn_tumor_crop):
            vr.addWidget(b)
        self.view_row.hide()
        ll.addWidget(self.view_row)

        # Load / Analyze buttons
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

        # ── Right: scrollable results panel ────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFixedWidth(330)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right = QFrame()
        right.setObjectName("panel")
        rl = QVBoxLayout(right)
        rl.setSpacing(12)
        rl.setContentsMargins(16, 16, 16, 16)

        # Patient sub-panel
        rl.addWidget(self._subpanel_patient())

        # Classification result sub-panel
        rl.addWidget(self._subpanel_result())

        # Gland segmentation sub-panel (hidden until segmentation runs)
        rl.addWidget(self._subpanel_gland())

        # Morphometrics sub-panel (hidden until morphometrics run)
        rl.addWidget(self._subpanel_morpho())

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
        self.notes_edit.setFixedHeight(72)
        nfl.addWidget(self.notes_edit)
        rl.addWidget(nf)

        # Save button
        self.save_btn = QPushButton("Save to Patient Record")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setEnabled(False)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_result)
        rl.addWidget(self.save_btn)
        rl.addStretch()

        right_scroll.setWidget(right)
        content.addWidget(right_scroll)

        wrapper = QWidget()
        wrapper.setObjectName("contentArea")
        wrapper.setLayout(content)
        root.addWidget(wrapper, 1)

    # ── Sub-panel builders ─────────────────────────────────────────────────────

    def _subpanel_patient(self) -> QFrame:
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
        return pf

    def _subpanel_result(self) -> QFrame:
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
        return rf

    def _subpanel_gland(self) -> QFrame:
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
        self.quality_label.setWordWrap(True)
        gfl.addWidget(self.dice_label)
        gfl.addWidget(self.quality_label)

        # Review mask button
        self.review_btn = QPushButton("Review / Edit Mask")
        self.review_btn.setObjectName("dangerBtn")
        self.review_btn.setFixedHeight(34)
        self.review_btn.setCursor(Qt.PointingHandCursor)
        self.review_btn.clicked.connect(self._open_mask_review)
        gfl.addWidget(self.review_btn)

        self.gland_frame.hide()
        return self.gland_frame

    def _subpanel_morpho(self) -> QFrame:
        self.morpho_frame = QFrame()
        self.morpho_frame.setObjectName("subPanel")
        mfl = QVBoxLayout(self.morpho_frame)
        mfl.setSpacing(6)
        mfl.setContentsMargins(12, 12, 12, 12)
        mfl.addWidget(QLabel("Morphometric Analysis", objectName="sectionLabel"))

        # Metrics grid
        self._morpho_vals = {}
        metrics_frame = QFrame()
        mgrid = QVBoxLayout(metrics_frame)
        mgrid.setSpacing(3)
        mgrid.setContentsMargins(0, 0, 0, 0)
        for key, label in [
            ("gland_count",    "Glands detected"),
            ("tumor_buds",     "Tumor buds"),
            ("cribriform",     "Cribriform score"),
            ("crowding",       "Crowding index"),
            ("mean_circ",      "Mean circularity"),
            ("mean_solid",     "Mean solidity"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(4)
            k_lbl = QLabel(label)
            k_lbl.setObjectName("morphoKey")
            v_lbl = QLabel("—")
            v_lbl.setObjectName("morphoVal")
            row.addWidget(k_lbl)
            row.addStretch()
            row.addWidget(v_lbl)
            mgrid.addLayout(row)
            self._morpho_vals[key] = v_lbl
        mfl.addWidget(metrics_frame)

        # Risk flags area
        mfl.addWidget(QLabel("Risk Flags", objectName="sectionLabel"))
        self.flags_label = QLabel("—")
        self.flags_label.setObjectName("flagsLabel")
        self.flags_label.setWordWrap(True)
        mfl.addWidget(self.flags_label)

        self.morpho_frame.hide()
        return self.morpho_frame

    def _view_btn(self, text: str, mode: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("viewBtn")
        b.setFixedHeight(30)
        b.setCursor(Qt.PointingHandCursor)
        b.setCheckable(True)
        b.clicked.connect(lambda: self._set_view_mode(mode))
        return b

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if not path:
            return
        self.image_path = path
        self._view_mode = self._MODE_ORIGINAL
        pix = QPixmap(path)
        self.image_label.setPixmap(
            pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.analyze_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self.conf_label.hide()
        self.gland_frame.hide()
        self.morpho_frame.hide()
        self.view_row.hide()
        self.result_label.setText("—")
        self._overlay_array = None
        self._morpho_report = None
        self._gland_mask    = None

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
        self.morpho_frame.hide()
        self.view_row.hide()
        self._worker = PredictWorker(self.image_path)
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, label, prob, tier, segmented, overlay_rgb,
                   gland_dice, gland_quality, morpho_report):
        # ── Classification ────────────────────────────────────────────────────
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
        self._morpho_report = morpho_report
        self._gland_mask    = getattr(self._worker, "_gland_mask", None)
        self._view_mode     = self._MODE_ORIGINAL
        self.save_btn.setEnabled(self.selected_patient is not None)

        # ── Gland segmentation panel ──────────────────────────────────────────
        if segmented and overlay_rgb is not None:
            self.dice_label.setText(f"Dice Score: {gland_dice * 100:.1f}%")
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
            self.gland_frame.show()

        # ── Morphometrics panel ───────────────────────────────────────────────
        if morpho_report is not None:
            self._populate_morpho_panel(morpho_report)
            self.morpho_frame.show()

        # ── View toggle row ───────────────────────────────────────────────────
        if segmented:
            self.view_row.show()
            self._set_view_btn_states(self._MODE_ORIGINAL)

    def _populate_morpho_panel(self, report):
        arch = report.architecture

        def _fmt(val, fmt=".2f", suffix=""):
            try:
                return f"{val:{fmt}}{suffix}"
            except Exception:
                return "—"

        self._morpho_vals["gland_count"].setText(str(arch.gland_count))
        self._morpho_vals["tumor_buds"].setText(str(arch.tumor_bud_count))

        crib_pct = arch.cribriform_score * 100
        crib_lbl = self._morpho_vals["cribriform"]
        crib_lbl.setText(f"{crib_pct:.0f}%")
        if arch.cribriform_score > 0.25:
            crib_lbl.setStyleSheet(f"color: {C['danger']}; font-weight: 700;")
        else:
            crib_lbl.setStyleSheet(f"color: {C['ink']};")

        crowd_lbl = self._morpho_vals["crowding"]
        crowd_lbl.setText(_fmt(arch.crowding_index))
        if arch.crowding_index > 0.35:
            crowd_lbl.setStyleSheet(f"color: {C['warning']}; font-weight: 700;")
        else:
            crowd_lbl.setStyleSheet(f"color: {C['ink']};")

        self._morpho_vals["mean_circ"].setText(_fmt(arch.mean_circularity))
        self._morpho_vals["mean_solid"].setText(_fmt(arch.mean_solidity))

        # Risk flags
        flags = report.risk_flags
        if flags:
            # Color-code: lines containing "No major" are green, others amber/red
            lines = []
            for f in flags:
                if "No major" in f:
                    lines.append(f'<span style="color:{C["success"]};">✅ {f.lstrip("✅ ")}</span>')
                elif "Cribriform" in f or "budding" in f:
                    lines.append(f'<span style="color:{C["danger"]};">🔴 {f.lstrip("🔴 ")}</span>')
                else:
                    lines.append(f'<span style="color:{C["warning"]};">⚠ {f.lstrip("⚠ ")}</span>')
            self.flags_label.setText("<br>".join(lines))
        else:
            self.flags_label.setText("—")

    def _on_error(self, msg):
        self.result_label.setText("Error")
        self.conf_label.hide()
        self.analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "Analysis Error", msg)

    # ── View mode ──────────────────────────────────────────────────────────────

    def _set_view_mode(self, mode: str):
        self._view_mode = mode
        self._set_view_btn_states(mode)

        if mode == self._MODE_ORIGINAL:
            if self.image_path:
                pix = QPixmap(self.image_path)
                self.image_label.setPixmap(
                    pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        elif mode == self._MODE_OVERLAY:
            if self._overlay_array is not None:
                self._display_ndarray(self._overlay_array)
        elif mode == self._MODE_ANNOTATED:
            if self._morpho_report is not None and self._morpho_report.annotated_image is not None:
                self._display_ndarray(self._morpho_report.annotated_image)
            elif self._overlay_array is not None:
                self._display_ndarray(self._overlay_array)
        elif mode == self._MODE_TUMOR_CROP:
            if self._morpho_report is not None and self._morpho_report.tumor_crop is not None:
                self._display_ndarray(self._morpho_report.tumor_crop)

    def _set_view_btn_states(self, active_mode: str):
        for btn, mode in [
            (self.btn_original,   self._MODE_ORIGINAL),
            (self.btn_overlay,    self._MODE_OVERLAY),
            (self.btn_annotated,  self._MODE_ANNOTATED),
            (self.btn_tumor_crop, self._MODE_TUMOR_CROP),
        ]:
            btn.setChecked(mode == active_mode)

    def _display_ndarray(self, rgb_array: np.ndarray):
        if rgb_array is None:
            return
        # Handle single-row crops — give them at least 200px height for display
        arr = rgb_array
        h, w = arr.shape[:2]
        if h < 50:
            scale = max(1, 200 // h)
            arr = cv2.resize(arr, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
        h, w, ch = arr.shape
        qimg = QImage(arr.data, w, h, w * ch, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg)
        self.image_label.setPixmap(
            pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    # ── Mask review ────────────────────────────────────────────────────────────

    def _open_mask_review(self):
        from ui.analysis.mask_review_dialog import MaskReviewDialog
        if self.image_path is None:
            return
        orig = cv2.cvtColor(cv2.imread(self.image_path), cv2.COLOR_BGR2RGB)
        gland_mask = self._gland_mask
        if gland_mask is None and self._overlay_array is not None:
            diff           = self._overlay_array.astype(np.int16) - orig.astype(np.int16)
            orange_channel = diff[:, :, 0] - diff[:, :, 2]
            gland_mask     = np.clip(orange_channel, 0, 255).astype(np.float32) / 255.0
        if gland_mask is None:
            QMessageBox.information(self, "No Mask", "No segmentation mask available yet.")
            return
        dlg = MaskReviewDialog(self.image_path, orig, gland_mask, parent=self)
        dlg.exec()

    # ── Save ───────────────────────────────────────────────────────────────────

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

        # Collect morphometric extras for notes
        notes = self.notes_edit.toPlainText().strip()
        if self._morpho_report is not None:
            arch = self._morpho_report.architecture
            morpho_note = (
                f"\n[Morphometrics] glands={arch.gland_count} "
                f"buds={arch.tumor_bud_count} "
                f"cribriform={arch.cribriform_score:.2f} "
                f"crowding={arch.crowding_index:.2f}"
            )
            notes = (notes + morpho_note).strip()

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


# ── Extra styles ────────────────────────────────────────────────────────────────
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
    #diceLabel    {{ font-size: 15px; font-weight: 700; padding: 2px 0; }}
    #qualityLabel {{ font-size: 12px; color: {C['ink_soft']}; }}

    #morphoKey {{ font-size: 12px; color: {C['ink_soft']}; }}
    #morphoVal {{ font-size: 12px; font-weight: 600; color: {C['ink']}; }}
    #flagsLabel {{ font-size: 12px; line-height: 1.6; }}

    #viewRow {{ background: transparent; }}
    #viewBtn {{
        background: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        color: {C['ink_soft']};
        padding: 0 6px;
    }}
    #viewBtn:checked {{
        background: {C['primary']};
        color: white;
        border-color: {C['primary']};
    }}
    #viewBtn:hover:!checked {{ background: {C['border']}; }}
"""