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
import tensorflow as tf

from core.morphometrics import analyze as morpho_analyze, MorphometricReport

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ── Custom objects — names must match the segmentation notebook exactly ──────
#
# Notebook (attention_unet_gland_segmentation_2.ipynb) defines:
#   dice_coefficient(y_true, y_pred)   → metric
#   dice_loss(y_true, y_pred)          → helper
#   hybrid_loss(y_true, y_pred)        → compiled loss  (BCE_WEIGHT*BCE + DICE_WEIGHT*Dice)
#   iou_metric(y_true, y_pred)         → metric
#
# These names are serialised into the .keras file and MUST be registered here.

def dice_coefficient(y_true, y_pred, smooth=1e-6):
    """Sørensen–Dice coefficient — matches notebook dice_coefficient()."""
    K        = tf.keras.backend
    y_true_f = K.cast(K.flatten(y_true), 'float32')
    y_pred_f = K.cast(K.flatten(y_pred), 'float32')
    inter    = K.sum(y_true_f * y_pred_f)
    return (2.0 * inter + smooth) / (K.sum(y_true_f) + K.sum(y_pred_f) + smooth)

def dice_loss(y_true, y_pred):
    """1 − Dice — matches notebook dice_loss()."""
    return 1.0 - dice_coefficient(y_true, y_pred)

def hybrid_loss(y_true, y_pred):
    """
    Hybrid Loss = 0.5 × BCE + 0.5 × Dice-Loss
    Matches notebook hybrid_loss() with CFG['BCE_WEIGHT'] = CFG['DICE_WEIGHT'] = 0.5
    """
    bce = tf.keras.backend.mean(
        tf.keras.losses.binary_crossentropy(y_true, y_pred)
    )
    return 0.5 * bce + 0.5 * dice_loss(y_true, y_pred)

def iou_metric(y_true, y_pred, threshold=0.5, smooth=1e-6):
    """Intersection-over-Union — matches notebook iou_metric()."""
    K        = tf.keras.backend
    y_pred_b = K.cast(y_pred >= threshold, 'float32')
    y_true_f = K.flatten(K.cast(y_true, 'float32'))
    y_pred_f = K.flatten(y_pred_b)
    inter    = K.sum(y_true_f * y_pred_f)
    union    = K.sum(y_true_f) + K.sum(y_pred_f) - inter
    return (inter + smooth) / (union + smooth)

CUSTOM_OBJECTS = {
    'hybrid_loss'       : hybrid_loss,       # compiled loss
    'dice_coefficient'  : dice_coefficient,  # metric
    'dice_loss'         : dice_loss,         # helper used inside hybrid_loss
    'iou_metric'        : iou_metric,        # metric
}

# ── Constants ─────────────────────────────────────────────────────────────────
CLF_SIZE   = 256   # ResNet50 input          — matches classifier notebook IMG_SIZE = 256
GLAND_SIZE = 256   # Attention U-Net input   — matches CFG['IMG_HEIGHT/WIDTH'] = 256

# Classification threshold — 0.3 (sensitivity-first, matches notebook eval cell)
CLF_THRESHOLD = 0.3

# Segmentation binarisation threshold — 0.3
SEG_THRESHOLD = 0.3

# Confidence tiers (based on raw sigmoid probability)
CONF_HIGH   = 0.75   # >= 0.75 → high   → run segmentation
CONF_MEDIUM = 0.30   # >= 0.30 → medium → run segmentation
             #  < 0.30 → low    → skip segmentation

# Overlay colour — orange for gland boundaries
GLAND_COLOR = (255, 140, 0)
OVERLAY_ALPHA = 0.40

# Dice proxy quality thresholds
DICE_GOOD = 0.75
DICE_OK   = 0.50


# ── Macenko Stain Normaliser ──────────────────────────────────────────────────
class MacenkoNormalizer:
    """
    Macenko stain normalisation for H&E histopathology images.
    Reference: Macenko et al. (2009) — A method for normalizing histology
    slides for quantitative analysis.

    Usage
    -----
    normalizer = MacenkoNormalizer()
    normalizer.fit(reference_image_uint8_rgb)
    normalised = normalizer.transform(input_image_uint8_rgb)
    """

    def __init__(self, alpha: float = 1.0, beta: float = 0.15):
        self.alpha   = alpha
        self.beta    = beta
        self.HERef   = None
        self.maxCRef = None

    @staticmethod
    def _od(img: np.ndarray) -> np.ndarray:
        """Convert uint8 RGB to optical density, clipping near-zero values."""
        img = np.clip(img.astype(np.float64), 1, 255)
        return -np.log(img / 255.0)

    def _get_stain_matrix(self, img: np.ndarray) -> np.ndarray:
        OD        = self._od(img)
        OD_flat   = OD.reshape(-1, 3)
        mask      = np.linalg.norm(OD_flat, axis=1) > self.beta
        OD_tissue = OD_flat[mask]
        if len(OD_tissue) < 10:
            raise ValueError("Too few tissue pixels — check the input image.")
        _, _, Vt  = np.linalg.svd(OD_tissue, full_matrices=False)
        plane     = Vt[:2].T
        coords    = OD_tissue @ plane
        angle     = np.arctan2(coords[:, 1], coords[:, 0])
        phi1      = np.percentile(angle, self.alpha)
        phi2      = np.percentile(angle, 100 - self.alpha)
        v1        = plane @ np.array([np.cos(phi1), np.sin(phi1)])
        v2        = plane @ np.array([np.cos(phi2), np.sin(phi2)])
        HE        = np.column_stack([v1, v2])
        if HE[0, 0] < HE[0, 1]:
            HE = HE[:, ::-1]
        return HE / np.linalg.norm(HE, axis=0)

    def fit(self, target: np.ndarray) -> "MacenkoNormalizer":
        """Fit normaliser to a uint8 RGB reference image."""
        self.HERef   = self._get_stain_matrix(target)
        OD           = self._od(target)
        C            = np.linalg.lstsq(self.HERef, OD.reshape(-1, 3).T, rcond=None)[0]
        self.maxCRef = np.percentile(C, 99, axis=1)
        return self

    def transform(self, img: np.ndarray) -> np.ndarray:
        """Normalise a uint8 RGB image to the reference stain appearance."""
        if self.HERef is None:
            raise RuntimeError("Call .fit() with a reference image first.")
        h, w     = img.shape[:2]
        OD       = self._od(img)
        C        = np.linalg.lstsq(self.HERef, OD.reshape(-1, 3).T, rcond=None)[0]
        maxC     = np.percentile(C, 99, axis=1, keepdims=True)
        C        = C * (self.maxCRef[:, None] / np.clip(maxC, 1e-6, None))
        OD_norm  = self.HERef @ C
        img_norm = np.exp(-OD_norm.T) * 255.0
        img_norm = np.clip(img_norm, 0, 255).astype(np.uint8)
        return img_norm.reshape(h, w, 3)


# ── Build a default synthetic reference (replaced by a real tile ideally) ────
def _build_default_normalizer() -> MacenkoNormalizer:
    """
    Initialise Macenko with a synthetic neutral H&E reference patch.
    For best results, replace with a real well-stained representative tile
    from the training dataset.
    """
    ref = np.ones((64, 64, 3), dtype=np.uint8)
    ref[..., 0] = 210   # R
    ref[..., 1] = 180   # G
    ref[..., 2] = 200   # B
    norm = MacenkoNormalizer()
    try:
        norm.fit(ref)
    except Exception:
        norm = None
    return norm

_DEFAULT_NORMALIZER = _build_default_normalizer()


# ── Predictor ─────────────────────────────────────────────────────────────────
class Predictor:
    def __init__(
        self,
        classifier_model_path : str,
        gland_model_path      : str = None,
        stain_normalizer      : MacenkoNormalizer = None,
    ):
        """
        2-stage pipeline + morphometric analysis
        -----------------------------------------
        Stage 1 — ResNet50 classifier  (best_resnet50.keras)
            Preprocessing : Macenko stain normalisation → resize 256×256 → /255 → [0,1]
            Threshold     : 0.3  (sensitivity-optimised)
            Output        : 'Pathologique' / 'Non Pathologique'

        Stage 2 — Attention U-Net segmentation  (best_attention_unet.keras)
            Preprocessing : resize 256×256 → /255 → [0,1]   (matches notebook load_sample())
            Threshold     : 0.3  (sensitivity-optimised; notebook eval uses 0.5)
            Triggered     : only when classifier prob ≥ 0.3 (medium / high confidence)
            Custom objects: hybrid_loss, dice_coefficient, dice_loss, iou_metric
            Architecture  : Attention U-Net — filters (64,128,256,512,1024)
                            Additive attention gates on all 4 skip connections
                            SpatialDropout2D, BatchNorm, He-init conv blocks
                            Output: Conv2D(1, sigmoid) — binary mask (H,W,1)

        Stage 3 — Morphometric analysis  (core/morphometrics.py)
            Input  : original RGB image + raw sigmoid mask from Stage 2
            Output : MorphometricReport (gland shapes, architecture, risk flags,
                     annotated image, tumor crop)
        """
        self.clf_model      = load_model(classifier_model_path)
        self.stain_normalizer = stain_normalizer or _DEFAULT_NORMALIZER
        logging.info(f"Classifier loaded  : {classifier_model_path}")

        self.gland_model = None
        if gland_model_path and os.path.exists(gland_model_path):
            self.gland_model = load_model(
                gland_model_path,
                custom_objects=CUSTOM_OBJECTS,
            )
            logging.info(f"Gland model loaded : {gland_model_path}")
        else:
            logging.warning("Gland model not found — segmentation will be skipped.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_image(self, image_path: str) -> np.ndarray:
        """Load image as uint8 RGB, handling 16-bit TIFs gracefully."""
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def _preprocess_for_classifier(self, img_rgb: np.ndarray) -> np.ndarray:
        """
        Classifier preprocessing — matches the notebook macenko_preprocess():
          1. Macenko stain normalisation (uint8 RGB → uint8 RGB)
          2. Resize to 256 × 256 (INTER_AREA)
          3. Divide by 255.0  → [0, 1]  (NOT preprocess_input, matching /255 in notebook)
        """
        # Step 1: Macenko normalisation
        img = img_rgb.copy()
        if self.stain_normalizer is not None:
            try:
                img = self.stain_normalizer.transform(img)
            except Exception as e:
                logging.warning(f"Macenko normalisation failed ({e}), using raw image.")

        # Step 2+3: resize → normalise
        img = cv2.resize(img, (CLF_SIZE, CLF_SIZE), interpolation=cv2.INTER_AREA)
        return np.expand_dims(img.astype(np.float32) / 255.0, axis=0)   # (1,256,256,3)

    def _preprocess_for_gland(self, img_rgb: np.ndarray) -> np.ndarray:
        """
        GlandNet preprocessing — matches notebook load_image() exactly:
            img = cv2.resize(img, (256, 256))
            img = img / 255.0
        No stain normalisation here (segmentation model trained on raw images).
        """
        img = cv2.resize(img_rgb, (GLAND_SIZE, GLAND_SIZE), interpolation=cv2.INTER_AREA)
        return np.expand_dims(img.astype(np.float32) / 255.0, axis=0)   # (1,256,256,3)

    def _apply_overlay(self, img_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Blend orange mask + contour border over the original image."""
        h, w     = img_rgb.shape[:2]
        mask_rs  = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        mask_bin = (mask_rs > SEG_THRESHOLD).astype(np.uint8)
        colored  = np.zeros_like(img_rgb)
        colored[mask_bin == 1] = GLAND_COLOR
        overlay  = cv2.addWeighted(img_rgb.copy(), 1.0, colored, OVERLAY_ALPHA, 0)
        contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, GLAND_COLOR, 2)
        return overlay

    @staticmethod
    def _compute_dice_proxy(pred_mask: np.ndarray) -> float:
        """
        Coverage-based quality proxy (no ground truth at inference).
        Scores near-empty and near-full masks low; peaks at ~35% coverage.
        """
        pred_bin = (pred_mask > SEG_THRESHOLD).astype(np.float32)
        coverage = pred_bin.mean()
        ideal    = 0.35
        proxy    = float(1.0 - abs(coverage - ideal) / max(ideal, 1.0 - ideal))
        proxy    = max(0.0, min(1.0, proxy))
        logging.info(f"  Gland coverage={coverage*100:.1f}%  dice_proxy={proxy:.3f}")
        return proxy

    @staticmethod
    def _confidence_tier(prob: float) -> str:
        if prob >= CONF_HIGH:
            return "high"
        elif prob >= CONF_MEDIUM:
            return "medium"
        return "low"

    @staticmethod
    def _qualitative_assessment(dice: float) -> str:
        if dice >= DICE_GOOD:
            return "Good segmentation — gland boundaries clearly defined"
        elif dice >= DICE_OK:
            return "Acceptable segmentation — minor boundary ambiguity"
        return "Poor segmentation — gland boundaries unclear"

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, image_path: str) -> dict:
        """
        Run the full 3-stage pipeline.

        Returns
        -------
        dict with keys:
            label            str
            probability      float
            confidence_tier  str    'high' / 'medium' / 'low'
            segmented        bool
            overlay          ndarray (H,W,3) uint8
            gland_dice       float | None
            gland_quality    str   | None
            gland_mask       ndarray (256,256) float32 | None
            morpho_report    MorphometricReport | None
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
            morpho_report   = None,
        )

        # ── Stage 1: Classification ───────────────────────────────────────────
        img_rgb = self._read_image(image_path)
        prob    = float(
            self.clf_model.predict(
                self._preprocess_for_classifier(img_rgb), verbose=0
            )[0][0]
        )
        label = "Pathologique" if prob >= CLF_THRESHOLD else "Non Pathologique"
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

        # ── Stage 2: Gland segmentation ───────────────────────────────────────
        should_segment = tier in ("high", "medium") and self.gland_model is not None
        if not should_segment:
            reason = "low confidence" if tier == "low" else "gland model unavailable"
            logging.info(f"  Stage 2 skipped — {reason}")
            return result

        gland_input = self._preprocess_for_gland(img_rgb)               # (1,256,256,3)
        gland_out   = self.gland_model.predict(gland_input, verbose=0)  # (1,256,256,1)
        gland_mask  = gland_out[0, ..., 0]                              # (256,256) float32

        dice    = self._compute_dice_proxy(gland_mask)
        quality = self._qualitative_assessment(dice)

        result.update(
            segmented     = True,
            overlay       = self._apply_overlay(img_rgb, gland_mask),
            gland_dice    = dice,
            gland_quality = quality,
            gland_mask    = gland_mask,
        )
        logging.info(f"  Stage 2 → dice_proxy={dice:.4f} | {quality}")

        # ── Stage 3: Morphometric analysis ────────────────────────────────────
        try:
            morpho = morpho_analyze(img_rgb, gland_mask)
            result["morpho_report"] = morpho
            arch = morpho.architecture
            logging.info(
                f"  Stage 3 → glands={arch.gland_count} "
                f"buds={arch.tumor_bud_count} "
                f"cribriform={arch.cribriform_score:.2f} "
                f"crowding={arch.crowding_index:.2f}"
            )
        except Exception as e:
            logging.warning(f"  Stage 3 morphometrics failed: {e}")
            result["morpho_report"] = None

        return result