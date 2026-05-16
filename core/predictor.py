import os
import sys
import numpy as np
import cv2
import logging
from tensorflow.keras.models import load_model
import tensorflow as tf
from tensorflow.keras.applications.resnet50 import preprocess_input

# ── Reinhard Normalizer (from your notebook) ───────────────────────────────
class ReinhardNormalizer:
    def __init__(self):
        self.target_means = None
        self.target_stds = None

    def _lab_split(self, I):
        I_lab = cv2.cvtColor(I, cv2.COLOR_RGB2LAB).astype(np.float32)
        I1, I2, I3 = cv2.split(I_lab)
        I1 = I1 / 2.55
        I2 = I2 - 128.0
        I3 = I3 - 128.0
        return I1, I2, I3

    def _merge_back(self, I1, I2, I3):
        I1 = I1 * 2.55
        I2 = I2 + 128.0
        I3 = I3 + 128.0
        merged = np.clip(cv2.merge((I1, I2, I3)), 0, 255).astype(np.uint8)
        return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)

    def _get_mean_std(self, I):
        I1, I2, I3 = self._lab_split(I)
        m1, s1 = cv2.meanStdDev(I1)
        m2, s2 = cv2.meanStdDev(I2)
        m3, s3 = cv2.meanStdDev(I3)
        return (m1[0][0], m2[0][0], m3[0][0]), (s1[0][0], s2[0][0], s3[0][0])

    def _standardize_brightness(self, I):
        p = np.percentile(I, 95)
        return np.clip(I * 255.0 / p, 0, 255).astype(np.uint8)

    def fit(self, target):
        target = self._standardize_brightness(target)
        self.target_means, self.target_stds = self._get_mean_std(target)
        logging.info("✅ Reinhard Normalizer fitted successfully.")

    def transform(self, I):
        I = self._standardize_brightness(I)
        I1, I2, I3 = self._lab_split(I)
        means, stds = self._get_mean_std(I)

        norm1 = ((I1 - means[0]) * (self.target_stds[0] / stds[0])) + self.target_means[0]
        norm2 = ((I2 - means[1]) * (self.target_stds[1] / stds[1])) + self.target_means[1]
        norm3 = ((I3 - means[2]) * (self.target_stds[2] / stds[2])) + self.target_means[2]

        return self._merge_back(norm1, norm2, norm3)


# ── Constants ─────────────────────────────────────────────────────────────
CLF_SIZE   = 256
GLAND_SIZE = 256
CLF_THRESHOLD = 0.3
SEG_THRESHOLD = 0.3

CONF_HIGH   = 0.75
CONF_MEDIUM = 0.30

GLAND_COLOR = (255, 140, 0)
OVERLAY_ALPHA = 0.40

DICE_GOOD = 0.75
DICE_OK   = 0.50


# ── Default Reinhard Normalizer ───────────────────────────────────────────
def _build_default_reinhard_normalizer() -> ReinhardNormalizer:
    REFERENCE_IMAGE_PATH = "./training_data/colon_n/colonn159.jpeg"
    print(f"Loading reference image for Reinhard normalisation: {REFERENCE_IMAGE_PATH}")
    
    norm = ReinhardNormalizer()
    if os.path.exists(REFERENCE_IMAGE_PATH):
        ref_img = cv2.imread(REFERENCE_IMAGE_PATH)
        ref_img = cv2.cvtColor(ref_img, cv2.COLOR_BGR2RGB)
        try:
            norm.fit(ref_img)
            return norm
        except Exception as e:
            logging.warning(f"Reinhard fit failed: {e}")
    else:
        logging.warning(f"Reference image not found: {REFERENCE_IMAGE_PATH}")
    
    # Fallback: create dummy normalizer
    return norm


_DEFAULT_REINHARD_NORMALIZER = _build_default_reinhard_normalizer()


# ── Predictor Class ───────────────────────────────────────────────────────
class Predictor:
    def __init__(
        self,
        classifier_model_path: str,
        gland_model_path: str = None,
        stain_normalizer: ReinhardNormalizer = None,
    ):
        self.clf_model = load_model(classifier_model_path)
        self.stain_normalizer = stain_normalizer or _DEFAULT_REINHARD_NORMALIZER
        logging.info(f"Classifier loaded: {classifier_model_path}")

        self.gland_model = None
        if gland_model_path and os.path.exists(gland_model_path):
            self.gland_model = load_model(
                gland_model_path,
                custom_objects=CUSTOM_OBJECTS,  # keep your existing custom objects
            )
            logging.info(f"Gland model loaded: {gland_model_path}")
        else:
            logging.warning("Gland model not found — segmentation will be skipped.")

    # ── Image Loading ─────────────────────────────────────────────────────
    def _read_image(self, image_path: str) -> np.ndarray:
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ── Preprocessing for Classifier (NEW - Reinhard) ─────────────────────
    def _preprocess_for_classifier(self, img_rgb: np.ndarray) -> np.ndarray:
        img = img_rgb.copy()
        
        # 1. Resize
        img = cv2.resize(img, (CLF_SIZE, CLF_SIZE), interpolation=cv2.INTER_AREA)
        
        # 2. Reinhard Stain Normalization
        try:
            img = self.stain_normalizer.transform(img)
        except Exception as e:
            logging.warning(f"Reinhard normalization failed, using raw image: {e}")

        # 3. ResNet50 preprocessing (ImageNet stats)
        img = preprocess_input(img.astype(np.float32))
        
        return np.expand_dims(img, axis=0)

    # ── Rest of your methods (unchanged) ──────────────────────────────────
    def _preprocess_for_gland(self, img_rgb: np.ndarray) -> np.ndarray:
        img = cv2.resize(img_rgb, (GLAND_SIZE, GLAND_SIZE), interpolation=cv2.INTER_AREA)
        return np.expand_dims(img.astype(np.float32) / 255.0, axis=0)

    def _apply_overlay(self, img_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        h, w = img_rgb.shape[:2]
        mask_rs = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        mask_bin = (mask_rs > SEG_THRESHOLD).astype(np.uint8)
        colored = np.zeros_like(img_rgb)
        colored[mask_bin == 1] = GLAND_COLOR
        overlay = cv2.addWeighted(img_rgb.copy(), 1.0, colored, OVERLAY_ALPHA, 0)
        contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, GLAND_COLOR, 2)
        return overlay

    @staticmethod
    def _compute_dice_proxy(pred_mask: np.ndarray) -> float:
        pred_bin = (pred_mask > SEG_THRESHOLD).astype(np.float32)
        coverage = pred_bin.mean()
        ideal = 0.35
        proxy = float(1.0 - abs(coverage - ideal) / max(ideal, 1.0 - ideal))
        return max(0.0, min(1.0, proxy))

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

    # ── Main Prediction ───────────────────────────────────────────────────
    def predict(self, image_path: str) -> dict:
        result = {
            "label": None,
            "probability": None,
            "confidence_tier": None,
            "segmented": False,
            "overlay": None,
            "gland_dice": None,
            "gland_quality": None,
            "gland_mask": None,
            "morpho_report": None,
        }

        # Stage 1: Classification
        img_rgb = self._read_image(image_path)
        
        prob = float(
            self.clf_model.predict(
                self._preprocess_for_classifier(img_rgb), verbose=0
            )[0][0]
        )
        
        label = "Pathologique" if prob >= CLF_THRESHOLD else "Non Pathologique"
        tier = self._confidence_tier(prob)

        result.update(
            label=label,
            probability=prob,
            confidence_tier=tier,
            overlay=img_rgb.copy(),
        )

        logging.info(
            f"[{os.path.basename(image_path)}] Stage 1 → {label} | prob={prob:.4f} | tier={tier}"
        )

        # Stage 2 & 3 remain unchanged...
        should_segment = tier in ("high", "medium") and self.gland_model is not None
        if not should_segment:
            return result

        # ... (keep your existing gland segmentation + morphometrics code)
        gland_input = self._preprocess_for_gland(img_rgb)
        gland_out = self.gland_model.predict(gland_input, verbose=0)
        gland_mask = gland_out[0, ..., 0]

        dice = self._compute_dice_proxy(gland_mask)
        quality = self._qualitative_assessment(dice)

        result.update(
            segmented=True,
            overlay=self._apply_overlay(img_rgb, gland_mask),
            gland_dice=dice,
            gland_quality=quality,
            gland_mask=gland_mask,
        )

        # Stage 3: Morphometrics
        try:
            from core.morphometrics import analyze as morpho_analyze
            morpho = morpho_analyze(img_rgb, gland_mask)
            result["morpho_report"] = morpho
        except Exception as e:
            logging.warning(f"Morphometrics failed: {e}")

        return result


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


