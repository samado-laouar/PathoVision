"""
MaskReviewDialog
────────────────
Shows the original image + the AI-predicted mask overlay.
The doctor can:
  • Confirm  → saves image + mask as-is   → training_data/
  • Redraw   → switches to drawing canvas → saves image + corrected mask

Drawing canvas controls:
  • Left-click / drag  → paint mask (white)
  • Right-click / drag → erase mask (black)
  • Slider             → brush size
  • Clear button       → wipe entire mask
  • Undo button        → step back one stroke
"""

import os
import numpy as np
import cv2
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QSizePolicy, QMessageBox, QStackedWidget,
    QSpacerItem, QToolButton
)
from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor,
    QCursor, QBrush
)

# ── Where confirmed/corrected masks are saved ─────────────────────────────────
_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "training_data"
)


def _save_training_pair(image_path: str, mask_np: np.ndarray, status: str) -> str:
    """
    Save original image + binary mask to data/training_data/.

    Folder layout
    -------------
    data/training_data/
        images/   <timestamp>_<status>_<basename>.png
        masks/    <timestamp>_<status>_<basename>_mask.png
    """
    images_dir = os.path.join(_ROOT, "images")
    masks_dir  = os.path.join(_ROOT, "masks")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(masks_dir,  exist_ok=True)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.splitext(os.path.basename(image_path))[0]
    stem     = f"{ts}_{status}_{basename}"

    img_dst  = os.path.join(images_dir, f"{stem}.png")
    mask_dst = os.path.join(masks_dir,  f"{stem}_mask.png")

    # Copy / convert original image
    src_img = cv2.imread(image_path)
    cv2.imwrite(img_dst, src_img)

    # Save mask as binary PNG (0 / 255)
    mask_bin = (mask_np > 0.5).astype(np.uint8) * 255
    cv2.imwrite(mask_dst, mask_bin)

    return _ROOT


# ── Drawing canvas ─────────────────────────────────────────────────────────────
class MaskCanvas(QLabel):
    """
    Displays the original image with a semi-transparent editable mask on top.
    Left-drag paints; right-drag erases.
    """
    stroke_finished = Signal()   # emitted on mouse release (for undo stack)

    OVERLAY_COLOR = QColor(255, 140, 0, 140)   # orange, semi-transparent
    ERASE_COLOR   = QColor(0, 0, 0, 0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 400)

        self._orig_rgb : np.ndarray | None = None   # H×W×3  uint8
        self._mask     : np.ndarray | None = None   # H×W    uint8  (0/255)
        self._brush_size = 18
        self._drawing    = False
        self._erasing    = False
        self._last_pt    : QPoint | None = None
        self._undo_stack : list[np.ndarray] = []    # snapshots before each stroke

    # ── public API ────────────────────────────────────────────────────────────

    def load(self, orig_rgb: np.ndarray, mask_np: np.ndarray):
        """
        orig_rgb : (H, W, 3) uint8 RGB
        mask_np  : (H, W)    float32 in [0,1]  OR  uint8 in [0,255]
        """
        self._orig_rgb = orig_rgb.copy()
        if mask_np.dtype != np.uint8:
            self._mask = (mask_np > 0.5).astype(np.uint8) * 255
        else:
            self._mask = mask_np.copy()
        self._undo_stack.clear()
        self._refresh()

    def set_brush_size(self, size: int):
        self._brush_size = size
        # Update cursor to reflect brush size
        self.setCursor(Qt.CrossCursor)

    def undo(self):
        if self._undo_stack:
            self._mask = self._undo_stack.pop()
            self._refresh()

    def clear_mask(self):
        if self._mask is not None:
            self._push_undo()
            self._mask[:] = 0
            self._refresh()

    def fill_mask(self):
        if self._mask is not None:
            self._push_undo()
            self._mask[:] = 255
            self._refresh()

    def get_mask(self) -> np.ndarray | None:
        """Returns current mask as float32 in [0,1]."""
        if self._mask is None:
            return None
        return self._mask.astype(np.float32) / 255.0

    # ── internals ─────────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append(self._mask.copy())
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)

    def _refresh(self):
        if self._orig_rgb is None:
            return
        h, w = self._orig_rgb.shape[:2]

        # Build composite: original + orange overlay where mask == 255
        composite = self._orig_rgb.copy()
        mask_bool = self._mask > 127

        # Orange tint on masked area
        orange = np.array([255, 140, 0], dtype=np.float32)
        alpha  = 0.45
        composite[mask_bool] = (
            composite[mask_bool].astype(np.float32) * (1 - alpha) + orange * alpha
        ).clip(0, 255).astype(np.uint8)

        # Draw contour on top
        contours, _ = cv2.findContours(self._mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(composite, contours, -1, (255, 100, 0), 2)

        qimg = QImage(composite.data, w, h, w * 3, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg)
        self.setPixmap(
            pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _canvas_to_image_pt(self, pos: QPoint) -> tuple[int, int] | None:
        """Map a widget coordinate to image pixel coordinate."""
        if self._orig_rgb is None or self.pixmap() is None:
            return None
        pix  = self.pixmap()
        pw, ph = pix.width(), pix.height()
        ww, wh = self.width(), self.height()
        # Top-left of the centered pixmap inside the label
        ox = (ww - pw) // 2
        oy = (wh - ph) // 2
        ix = pos.x() - ox
        iy = pos.y() - oy
        if ix < 0 or iy < 0 or ix >= pw or iy >= ph:
            return None
        ih, iw = self._orig_rgb.shape[:2]
        px = int(ix * iw / pw)
        py = int(iy * ih / ph)
        return (px, py)

    def _paint_at(self, pos: QPoint, erase: bool):
        pt = self._canvas_to_image_pt(pos)
        if pt is None:
            return
        x, y = pt
        value = 0 if erase else 255
        # Scale brush to image size
        ih, iw = self._orig_rgb.shape[:2]
        pix = self.pixmap()
        scale = iw / pix.width() if pix else 1.0
        r = max(1, int(self._brush_size * scale / 2))
        cv2.circle(self._mask, (x, y), r, value, -1)

        # Draw a line from last point for smooth strokes
        if self._last_pt is not None:
            lpt = self._canvas_to_image_pt(self._last_pt)
            if lpt:
                cv2.line(self._mask, lpt, (x, y), value, r * 2)
        self._last_pt = pos
        self._refresh()

    # ── mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if self._mask is None:
            return
        self._push_undo()
        self._drawing = e.button() == Qt.LeftButton
        self._erasing = e.button() == Qt.RightButton
        self._last_pt = None
        self._paint_at(e.pos(), erase=self._erasing)

    def mouseMoveEvent(self, e):
        if (self._drawing or self._erasing) and self._mask is not None:
            self._paint_at(e.pos(), erase=self._erasing)

    def mouseReleaseEvent(self, e):
        self._drawing = False
        self._erasing = False
        self._last_pt = None
        self.stroke_finished.emit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh()


# ── Main dialog ───────────────────────────────────────────────────────────────
class MaskReviewDialog(QDialog):
    """
    Two pages via QStackedWidget:
      Page 0 — Review: shows overlay, confirm / redraw
      Page 1 — Draw:   interactive canvas with toolbar
    """
    saved = Signal(str)   # emits save folder path

    def __init__(self, image_path: str, orig_rgb: np.ndarray,
                 gland_mask: np.ndarray, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.orig_rgb   = orig_rgb          # (H,W,3) uint8
        self.gland_mask = gland_mask        # (256,256) float32 from model

        self.setWindowTitle("Mask Review")
        self.setMinimumSize(860, 640)
        self._build_ui()
        self._apply_styles()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_review_page())   # 0
        self.stack.addWidget(self._build_draw_page())     # 1
        root.addWidget(self.stack)

    # ── Page 0: Review ────────────────────────────────────────────────────────

    def _build_review_page(self):
        page = QWidget()
        page.setObjectName("reviewPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Review Segmentation Mask")
        title.setObjectName("dialogTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        subtitle = QLabel(
            "The AI has generated the mask below.\n"
            "If it looks correct, confirm it. Otherwise, redraw it manually."
        )
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        # Image preview
        self.review_img = QLabel()
        self.review_img.setObjectName("reviewImg")
        self.review_img.setAlignment(Qt.AlignCenter)
        self.review_img.setMinimumHeight(420)
        self.review_img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.review_img, 1)

        # Legend
        legend = QLabel(
            "🟠 Orange overlay = segmented gland region     "
            "Left panel: original · Right: predicted mask overlay"
        )
        legend.setObjectName("legendLabel")
        legend.setAlignment(Qt.AlignCenter)
        layout.addWidget(legend)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        redraw_btn = QPushButton("✏️   Redraw Mask")
        redraw_btn.setObjectName("secondaryBtn")
        redraw_btn.setFixedHeight(44)
        redraw_btn.setMinimumWidth(160)
        redraw_btn.setCursor(Qt.PointingHandCursor)
        redraw_btn.clicked.connect(self._go_draw)

        confirm_btn = QPushButton("✅   Confirm & Save")
        confirm_btn.setObjectName("confirmBtn")
        confirm_btn.setFixedHeight(44)
        confirm_btn.setMinimumWidth(160)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.clicked.connect(self._confirm_save)

        btn_row.addWidget(redraw_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        # Populate review image (side-by-side: original | overlay)
        self._populate_review()

        return page

    def _populate_review(self):
        h, w = self.orig_rgb.shape[:2]

        # Build overlay
        mask_resized = cv2.resize(
            (self.gland_mask > 0.5).astype(np.uint8) * 255,
            (w, h), interpolation=cv2.INTER_NEAREST
        )
        overlay = self.orig_rgb.copy()
        orange  = np.array([255, 140, 0], dtype=np.float32)
        m_bool  = mask_resized > 127
        overlay[m_bool] = (
            overlay[m_bool].astype(np.float32) * 0.55 + orange * 0.45
        ).clip(0, 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (255, 100, 0), 2)

        # Stitch side by side
        divider = np.ones((h, 4, 3), dtype=np.uint8) * 100   # thin grey bar
        combined = np.concatenate([self.orig_rgb, divider, overlay], axis=1)

        ch, cw = combined.shape[:2]
        qimg = QImage(combined.data, cw, ch, cw * 3, QImage.Format_RGB888)
        self._review_pix = QPixmap.fromImage(qimg)
        # Defer actual display to showEvent / resize
        self._refresh_review()

    def _refresh_review(self):
        if hasattr(self, "_review_pix") and self.review_img.width() > 10:
            self.review_img.setPixmap(
                self._review_pix.scaled(
                    self.review_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )

    def showEvent(self, e):
        super().showEvent(e)
        self._refresh_review()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh_review()

    # ── Page 1: Draw ──────────────────────────────────────────────────────────

    def _build_draw_page(self):
        page = QWidget()
        page.setObjectName("drawPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(56)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(12)

        back_btn = QPushButton("← Back")
        back_btn.setObjectName("backBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        tb.addWidget(back_btn)

        tb.addWidget(self._vsep())

        # Brush size
        tb.addWidget(QLabel("Brush:", objectName="toolLabel"))
        self.brush_slider = QSlider(Qt.Horizontal)
        self.brush_slider.setRange(4, 80)
        self.brush_slider.setValue(18)
        self.brush_slider.setFixedWidth(120)
        self.brush_slider.valueChanged.connect(self._on_brush_change)
        self.brush_size_lbl = QLabel("18 px")
        self.brush_size_lbl.setObjectName("toolLabel")
        self.brush_size_lbl.setFixedWidth(42)
        tb.addWidget(self.brush_slider)
        tb.addWidget(self.brush_size_lbl)

        tb.addWidget(self._vsep())

        undo_btn = QPushButton("↩  Undo")
        undo_btn.setObjectName("toolBtn")
        undo_btn.setFixedHeight(34)
        undo_btn.setCursor(Qt.PointingHandCursor)
        undo_btn.clicked.connect(self._undo)

        clear_btn = QPushButton("🗑  Clear")
        clear_btn.setObjectName("toolBtnDanger")
        clear_btn.setFixedHeight(34)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)

        tb.addWidget(undo_btn)
        tb.addWidget(clear_btn)

        tb.addStretch()

        # Legend
        legend = QLabel(
            "Left-click = Paint mask   |   Right-click = Erase"
        )
        legend.setObjectName("toolLabel")
        tb.addWidget(legend)

        tb.addWidget(self._vsep())

        save_draw_btn = QPushButton("💾  Save Corrected Mask")
        save_draw_btn.setObjectName("confirmBtn")
        save_draw_btn.setFixedHeight(36)
        save_draw_btn.setCursor(Qt.PointingHandCursor)
        save_draw_btn.clicked.connect(self._save_drawn)
        tb.addWidget(save_draw_btn)

        layout.addWidget(toolbar)

        # ── Canvas ──
        self.canvas = MaskCanvas()
        layout.addWidget(self.canvas, 1)

        return page

    def _vsep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setObjectName("vSep")
        return sep

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _go_draw(self):
        """Switch to drawing page and load canvas with the AI mask."""
        h, w = self.orig_rgb.shape[:2]
        mask_full = cv2.resize(
            (self.gland_mask > 0.5).astype(np.uint8) * 255,
            (w, h), interpolation=cv2.INTER_NEAREST
        )
        self.canvas.load(self.orig_rgb, mask_full)
        self.stack.setCurrentIndex(1)

    def _on_brush_change(self, val):
        self.brush_size_lbl.setText(f"{val} px")
        self.canvas.set_brush_size(val)

    def _undo(self):
        self.canvas.undo()

    def _clear(self):
        reply = QMessageBox.question(
            self, "Clear Mask",
            "Are you sure you want to clear the entire mask?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.canvas.clear_mask()

    def _confirm_save(self):
        """Save AI mask as-is (confirmed correct)."""
        try:
            folder = _save_training_pair(self.image_path, self.gland_mask, "confirmed")
            QMessageBox.information(
                self, "Saved",
                f"Image and mask saved to training data folder:\n{folder}"
            )
            self.saved.emit(folder)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_drawn(self):
        """Save the doctor's redrawn mask."""
        mask = self.canvas.get_mask()
        if mask is None:
            return
        if mask.sum() == 0:
            reply = QMessageBox.question(
                self, "Empty Mask",
                "The mask is empty. Save anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        try:
            folder = _save_training_pair(self.image_path, mask, "corrected")
            QMessageBox.information(
                self, "Saved",
                f"Corrected mask saved to training data folder:\n{folder}"
            )
            self.saved.emit(folder)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Styles ────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog, QWidget { font-family: 'Segoe UI'; background: #F8FAFB; }

            #reviewPage, #drawPage { background: #F8FAFB; }

            #dialogTitle { font-size: 20px; font-weight: 700; color: #1A2B45; }
            #subtitleLabel { font-size: 13px; color: #5D6D7E; line-height: 1.5; }
            #legendLabel { font-size: 12px; color: #95A5A6; }

            #reviewImg {
                background: #1A1A2E;
                border-radius: 10px;
                border: 1px solid #2E86C1;
            }

            #confirmBtn {
                background: #1E8449; color: white; border: none;
                border-radius: 8px; font-size: 14px; font-weight: 600;
                padding: 0 20px;
            }
            #confirmBtn:hover { background: #196F3D; }

            #secondaryBtn {
                background: #ECF0F1; color: #2C3E50;
                border: 1.5px solid #D5D8DC; border-radius: 8px;
                font-size: 14px; padding: 0 20px;
            }
            #secondaryBtn:hover { background: #D5D8DC; }

            /* Toolbar */
            #toolbar {
                background: #FFFFFF;
                border-bottom: 1px solid #E5E7EB;
            }
            #toolLabel { font-size: 12px; color: #5D6D7E; font-weight: 600; }
            #toolBtn {
                background: #EBF5FB; color: #2E86C1;
                border: 1px solid #AED6F1; border-radius: 6px;
                font-size: 12px; font-weight: 600; padding: 0 12px;
            }
            #toolBtn:hover { background: #2E86C1; color: white; }

            #toolBtnDanger {
                background: #FDEDEC; color: #C0392B;
                border: 1px solid #F1948A; border-radius: 6px;
                font-size: 12px; font-weight: 600; padding: 0 12px;
            }
            #toolBtnDanger:hover { background: #C0392B; color: white; }

            #backBtn {
                background: none; border: none;
                color: #2E86C1; font-size: 13px; font-weight: 600;
            }
            #backBtn:hover { color: #1A5276; }

            #vSep { color: #E5E7EB; max-width: 1px; }

            QSlider::groove:horizontal {
                height: 4px; background: #D5D8DC; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; margin: -5px 0;
                background: #2E86C1; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #2E86C1; border-radius: 2px; }
        """)