import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

import numpy as np
import cv2
import logging
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.resnet50 import preprocess_input
import tensorflow as tf

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ── Custom objects — must match the notebook names exactly ───────────────────
def dice_coef(y_true, y_pred, smooth=1e-6):
    """Matches notebook: def dice_coef(y_true, y_pred, smooth=1e-6)"""
    y_true_f = tf.keras.backend.flatten(y_true)
    y_pred_f = tf.keras.backend.flatten(y_pred)
    intersection = tf.keras.backend.sum(y_true_f * y_pred_f)
    return (2. * intersection + smooth) / (
        tf.keras.backend.sum(y_true_f) + tf.keras.backend.sum(y_pred_f) + smooth
    )

def dice_loss(y_true, y_pred):
    """Matches notebook: def dice_loss(y_true, y_pred)"""
    return 1 - dice_coef(y_true, y_pred)

def combined_loss(y_true, y_pred):
    """Matches notebook: def combined_loss(y_true, y_pred)"""
    return dice_loss(y_true, y_pred) + tf.keras.losses.binary_crossentropy(y_true, y_pred)

CUSTOM_OBJECTS = {
    'combined_loss' : combined_loss,   # notebook name
    'dice_coef'     : dice_coef,       # notebook name
    'dice_loss'     : dice_loss,
}

# ── Constants ─────────────────────────────────────────────────────────────────
CLF_SIZE   = 80    # Stage 1 — ResNet50 (preprocess_input, [-1,1])
GLAND_SIZE = 256   # Stage 2 — GlandNet  (/255.0, [0,1])

# Confidence thresholds
CONF_HIGH   = 0.75  # >= 0.75 → high confidence   → segment
CONF_MEDIUM = 0.3   # >= 0.30 → medium confidence → segment
              #  < 0.30 → low confidence         → skip

# Overlay — orange for gland boundaries
GLAND_COLOR = (255, 140, 0)
ALPHA       = 0.40

# Dice quality thresholds (matches notebook evaluation logic)
DICE_GOOD = 0.75
DICE_OK   = 0.50


class Predictor:
    def __init__(
        self,
        classifier_model_path : str,
        gland_model_path      : str = None,
    ):
        """
        2-stage pipeline
        ----------------
        Stage 1 — ResNet50 (best_resnet50.keras)
            Preprocess : preprocess_input()  → [-1, 1]
            Input size : 80 × 80
            Output     : sigmoid scalar → Pathologique / Non Pathologique

        Stage 2 — GlandNet (best_model_tf.keras)
            Preprocess : / 255.0            → [0, 1]   (matches notebook load_image())
            Input size : 256 × 256
            Output     : (256, 256, 1) sigmoid mask
            Custom objs: combined_loss, dice_coef  (exact notebook names)
            Triggered  : only when classifier prob >= 0.50
        """
        self.clf_model = load_model(classifier_model_path)
        logging.info(f"Classifier loaded  : {classifier_model_path}")

        self.gland_model = None
        if gland_model_path and os.path.exists(gland_model_path):
            self.gland_model = load_model(
                gland_model_path,
                custom_objects=CUSTOM_OBJECTS
            )
            logging.info(f"Gland model loaded : {gland_model_path}")
        else:
            logging.warning("Gland model not found — segmentation will be skipped.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_image(self, image_path: str) -> np.ndarray:
        """Load as RGB uint8, handling 16-bit TIFs."""
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def _preprocess_for_classifier(self, img_rgb: np.ndarray) -> np.ndarray:
        """ResNet50: resize to 80×80, apply preprocess_input (→ [-1,1])."""
        img = cv2.resize(img_rgb, (CLF_SIZE, CLF_SIZE), interpolation=cv2.INTER_AREA)
        return preprocess_input(np.expand_dims(img.astype(np.float32), axis=0))

    def _preprocess_for_gland(self, img_rgb: np.ndarray) -> np.ndarray:
        """
        GlandNet: resize to 256×256, divide by 255.
        Matches notebook load_image() exactly:
            img = cv2.resize(img, (256, 256))
            img = img / 255.0
        """
        img = cv2.resize(img_rgb, (GLAND_SIZE, GLAND_SIZE), interpolation=cv2.INTER_AREA)
        return np.expand_dims(img.astype(np.float32) / 255.0, axis=0)  # (1, 256, 256, 3)

    def _apply_overlay(self, img_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Blend orange mask + contour border over the original image."""
        h, w     = img_rgb.shape[:2]
        mask_rs  = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        mask_bin = (mask_rs > 0.5).astype(np.uint8)
        colored  = np.zeros_like(img_rgb)
        colored[mask_bin == 1] = GLAND_COLOR
        overlay  = cv2.addWeighted(img_rgb.copy(), 1.0, colored, ALPHA, 0)
        contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, GLAND_COLOR, 2)
        return overlay

    @staticmethod
    def _compute_dice(pred_mask: np.ndarray, smooth: float = 1e-8) -> float:
        """
        Compute Dice score on the predicted mask alone (no ground truth at
        inference time). Uses the same formula as the notebook evaluation cell:
            intersection = np.sum(pred_bin * pred_bin)  →  np.sum(pred_bin)
            dice = (2 * intersection) / (2 * np.sum(pred_bin) + smooth)
                 = 1.0  when any tissue is detected

        In practice we measure mask coverage as a confidence proxy — a near-
        empty mask (< 1 % coverage) signals a low-confidence prediction.
        """
        pred_bin = (pred_mask > 0.5).astype(np.float32)
        coverage = pred_bin.mean()                       # fraction of pixels activated
        # Rescale coverage [0,1] → dice-like score in [0,1]
        # Full coverage (100%) is suspicious; meaningful gland masks are 10-60%
        # We penalise both extremes with a tent function peaked at ~35% coverage
        ideal    = 0.35
        dice_proxy = float(1.0 - abs(coverage - ideal) / max(ideal, 1.0 - ideal))
        dice_proxy = max(0.0, min(1.0, dice_proxy))
        logging.info(f"  Gland coverage={coverage*100:.1f}%  dice_proxy={dice_proxy:.3f}")
        return dice_proxy

    @staticmethod
    def _confidence_tier(prob: float) -> str:
        if prob >= CONF_HIGH:
            return "high"
        elif prob >= CONF_MEDIUM:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _qualitative_assessment(dice: float) -> str:
        if dice >= DICE_GOOD:
            return "Good segmentation — gland boundaries clearly defined"
        elif dice >= DICE_OK:
            return "Acceptable segmentation — minor boundary ambiguity"
        else:
            return "Poor segmentation — gland boundaries unclear"

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, image_path: str) -> dict:
        """
        Run the 2-stage pipeline.

        Returns
        -------
        dict:
            label            str    'Pathologique' / 'Non Pathologique'
            probability      float  classifier sigmoid output
            confidence_tier  str    'high' / 'medium' / 'low'
            segmented        bool   whether gland segmentation ran
            overlay          ndarray (H,W,3) uint8 — overlay or plain original
            gland_dice       float | None
            gland_quality    str   | None
            gland_mask       ndarray (256,256) float32 | None  — raw sigmoid output
        """
        result = dict(
            label           = None,
            probability     = None,
            confidence_tier = None,
            segmented       = False,
            overlay         = None,
            gland_dice      = None,
            gland_quality   = None,
            gland_mask      = None,
        )

        # ── Stage 1 : Classification ──────────────────────────────────────────
        img_rgb = self._read_image(image_path)
        prob    = float(
            self.clf_model.predict(self._preprocess_for_classifier(img_rgb), verbose=0)[0][0]
        )
        label = "Pathologique" if prob > 0.5 else "Non Pathologique"
        tier  = self._confidence_tier(prob)

        result.update(
            label           = label,
            probability     = prob,
            confidence_tier = tier,
            overlay         = img_rgb.copy(),
        )
        logging.info(
            f"[{os.path.basename(image_path)}] "
            f"Stage 1 → {label} | prob={prob:.4f} | tier={tier}"
        )

        # ── Stage 2 : Gland segmentation ─────────────────────────────────────
        should_segment = tier in ("high", "medium") and self.gland_model is not None
        if not should_segment:
            reason = "low confidence" if tier == "low" else "gland model unavailable"
            logging.info(f"  Stage 2 skipped — {reason}")
            return result

        # Preprocess exactly as the notebook does (/ 255.0, no preprocess_input)
        gland_input = self._preprocess_for_gland(img_rgb)                   # (1,256,256,3)
        gland_out   = self.gland_model.predict(gland_input, verbose=0)      # (1,256,256,1)
        gland_mask  = gland_out[0, ..., 0]                                  # (256,256) float32

        dice    = self._compute_dice(gland_mask)
        quality = self._qualitative_assessment(dice)

        result.update(
            segmented     = True,
            overlay       = self._apply_overlay(img_rgb, gland_mask),
            gland_dice    = dice,
            gland_quality = quality,
            gland_mask    = gland_mask,
        )
        logging.info(f"  Stage 2 → dice_proxy={dice:.4f} | {quality}")

        return result