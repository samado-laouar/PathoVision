# core/morphometrics.py
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GlandMetrics:
    """Per-gland morphometric measurements."""
    gland_id       : int
    area           : float
    perimeter      : float
    circularity    : float   # 4π·area / perimeter²  →  1.0 = perfect circle
    solidity       : float   # area / convex_hull_area
    aspect_ratio   : float   # major_axis / minor_axis
    extent         : float   # area / bounding_rect_area


@dataclass
class ArchitectureMetrics:
    """Tissue-level / spatial metrics."""
    gland_count            : int
    mean_inter_gland_dist  : float   # pixels — crowding indicator
    min_inter_gland_dist   : float
    crowding_index         : float   # fraction of gland pairs closer than threshold
    tumor_bud_count        : int     # small detached clusters (area < bud_area_thresh)
    cribriform_score       : float   # 0–1  (fraction of glands with internal holes)
    total_gland_area       : float
    mean_gland_area        : float
    area_std               : float   # heterogeneity
    mean_circularity       : float
    mean_solidity          : float


@dataclass
class MorphometricReport:
    """Full analysis result returned to the caller."""
    glands             : List[GlandMetrics]
    architecture       : ArchitectureMetrics
    tumor_crop         : np.ndarray          # RGB crop of tumor bounding box
    annotated_image    : np.ndarray          # full image with gland outlines + IDs
    risk_flags         : List[str]           # human-readable warning strings


# ── Thresholds (tunable) ─────────────────────────────────────────────────────
MIN_GLAND_AREA       = 150     # px²  — ignore noise below this
BUD_AREA_THRESH      = 400     # px²  — glands smaller than this = potential bud
CROWDING_DIST_THRESH = 40      # px   — glands closer than this = crowded
CIRCULARITY_LOW      = 0.45    # below → irregular / fragmented
SOLIDITY_LOW         = 0.78    # below → cribriform / hollow
ASPECT_HIGH          = 2.8     # above → stretched / crushed gland
CRIBRIFORM_HOLE_RATIO = 0.15   # internal hole fraction → cribriform flag


def _gland_metrics(contour: np.ndarray, mask_roi: np.ndarray, gland_id: int) -> GlandMetrics:
    """Compute per-gland shape metrics from a single contour."""
    area      = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))

    # Circularity: 1.0 = perfect circle, drops for jagged/branching shapes
    circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
    circularity = min(circularity, 1.0)

    # Solidity: area vs convex hull — drops for cribriform / hollow glands
    hull    = cv2.convexHull(contour)
    hull_a  = float(cv2.contourArea(hull))
    solidity = (area / hull_a) if hull_a > 0 else 0.0

    # Aspect ratio from fitted ellipse (needs ≥ 5 points)
    aspect_ratio = 1.0
    if len(contour) >= 5:
        (_, _), (MA, ma), _ = cv2.fitEllipse(contour)
        aspect_ratio = float(MA / ma) if ma > 0 else 1.0

    # Extent: how much of the bounding box is filled
    x, y, w, h = cv2.boundingRect(contour)
    extent = area / (w * h) if (w * h) > 0 else 0.0

    return GlandMetrics(
        gland_id=gland_id, area=area, perimeter=perimeter,
        circularity=circularity, solidity=solidity,
        aspect_ratio=aspect_ratio, extent=extent,
    )


def _has_internal_holes(contour: np.ndarray, binary_mask: np.ndarray) -> bool:
    """
    Detect cribriform pattern: fill the contour on a blank canvas,
    then check if the actual mask has significant unfilled area inside
    (= internal lumens / sieve-like structure).
    """
    canvas = np.zeros(binary_mask.shape, dtype=np.uint8)
    cv2.drawContours(canvas, [contour], -1, 255, thickness=cv2.FILLED)
    filled_area  = float(np.count_nonzero(canvas))
    actual_area  = float(cv2.contourArea(contour))
    if filled_area == 0:
        return False
    hole_ratio = 1.0 - (actual_area / filled_area)
    return hole_ratio > CRIBRIFORM_HOLE_RATIO


def _centroid(contour: np.ndarray):
    M  = cv2.moments(contour)
    cx = int(M['m10'] / M['m00']) if M['m00'] != 0 else 0
    cy = int(M['m01'] / M['m00']) if M['m00'] != 0 else 0
    return cx, cy


def _inter_gland_distances(centroids: List[tuple]) -> np.ndarray:
    """Return all pairwise distances between gland centroids."""
    if len(centroids) < 2:
        return np.array([])
    pts = np.array(centroids, dtype=np.float32)
    dists = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dists.append(float(np.linalg.norm(pts[i] - pts[j])))
    return np.array(dists)


def _tumor_crop(img_rgb: np.ndarray, binary_mask: np.ndarray,
                padding: int = 20) -> np.ndarray:
    """
    Crop the image to the bounding box of ALL detected glands combined,
    apply the mask as a white background outside the tumor region.
    """
    coords = cv2.findNonZero(binary_mask)
    if coords is None:
        return img_rgb.copy()
    x, y, w, h = cv2.boundingRect(coords)
    x1 = max(0, x - padding);  y1 = max(0, y - padding)
    x2 = min(img_rgb.shape[1], x + w + padding)
    y2 = min(img_rgb.shape[0], y + h + padding)

    # White out everything outside the mask in the crop window
    crop      = img_rgb[y1:y2, x1:x2].copy()
    mask_crop = binary_mask[y1:y2, x1:x2]
    bg        = np.ones_like(crop) * 255
    result    = np.where(mask_crop[..., np.newaxis] > 0, crop, bg)
    return result.astype(np.uint8)


def _annotated_image(img_rgb: np.ndarray, contours: list,
                     gland_metrics: List[GlandMetrics],
                     buds: list, cribriform_ids: set) -> np.ndarray:
    """Draw gland outlines, IDs, and color-code by pathology."""
    out = img_rgb.copy()
    for gm, cnt in zip(gland_metrics, contours):
        if gm.gland_id in cribriform_ids:
            color = (255, 50,  50)    # red   — cribriform
        elif gm.area < BUD_AREA_THRESH:
            color = (255, 165,  0)    # orange — bud
        elif gm.circularity < CIRCULARITY_LOW or gm.solidity < SOLIDITY_LOW:
            color = (220,  0, 220)    # purple — irregular
        else:
            color = (0,  200, 80)     # green  — normal-looking
        cv2.drawContours(out, [cnt], -1, color, 2)
        cx, cy = _centroid(cnt)
        cv2.putText(out, str(gm.gland_id), (cx - 6, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    # Mark bud centroids with a cross
    for cnt in buds:
        cx, cy = _centroid(cnt)
        cv2.drawMarker(out, (cx, cy), (255, 165, 0),
                       cv2.MARKER_CROSS, 12, 2, cv2.LINE_AA)
    return out


def _risk_flags(arch: ArchitectureMetrics, glands: List[GlandMetrics]) -> List[str]:
    flags = []
    if arch.mean_circularity < CIRCULARITY_LOW:
        flags.append(f"⚠ Low mean circularity ({arch.mean_circularity:.2f}) — irregular / fragmented glands")
    if arch.mean_solidity < SOLIDITY_LOW:
        flags.append(f"⚠ Low mean solidity ({arch.mean_solidity:.2f}) — possible cribriform pattern")
    if arch.cribriform_score > 0.25:
        flags.append(f"🔴 Cribriform architecture detected ({arch.cribriform_score*100:.0f}% of glands)")
    if arch.crowding_index > 0.35:
        flags.append(f"⚠ High gland crowding index ({arch.crowding_index:.2f}) — reduced inter-glandular stroma")
    if arch.tumor_bud_count > 0:
        flags.append(f"🔴 Tumor budding detected ({arch.tumor_bud_count} bud(s)) — metastasis risk indicator")
    if arch.area_std > arch.mean_gland_area * 0.6:
        flags.append(f"⚠ High gland size heterogeneity (std={arch.area_std:.0f}) — abnormal proliferation")
    high_ar = [g for g in glands if g.aspect_ratio > ASPECT_HIGH]
    if high_ar:
        flags.append(f"⚠ {len(high_ar)} gland(s) with high aspect ratio — possible stromal compression")
    if not flags:
        flags.append("✅ No major morphometric risk flags detected")
    return flags


def analyze(img_rgb: np.ndarray, pred_mask: np.ndarray) -> MorphometricReport:
    """
    Main entry point.

    Parameters
    ----------
    img_rgb   : (H, W, 3) uint8 RGB — original image at any size
    pred_mask : (H, W) float32 in [0,1] — UNet++ sigmoid output

    Returns
    -------
    MorphometricReport
    """
    H, W = img_rgb.shape[:2]

    # 1. Resize mask to match image, binarise
    mask_rs  = cv2.resize(pred_mask, (W, H), interpolation=cv2.INTER_LINEAR)
    binary   = (mask_rs > 0.5).astype(np.uint8) * 255

    # 2. Find all contours (each = one candidate gland)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        empty_arch = ArchitectureMetrics(
            gland_count=0, mean_inter_gland_dist=0, min_inter_gland_dist=0,
            crowding_index=0, tumor_bud_count=0, cribriform_score=0,
            total_gland_area=0, mean_gland_area=0, area_std=0,
            mean_circularity=0, mean_solidity=0,
        )
        return MorphometricReport(
            glands=[], architecture=empty_arch,
            tumor_crop=img_rgb.copy(), annotated_image=img_rgb.copy(),
            risk_flags=["No glands detected in mask."],
        )

    # 3. Filter by minimum area, compute per-gland metrics
    valid_contours, gland_metrics_list = [], []
    gid = 1
    for cnt in contours:
        if cv2.contourArea(cnt) < MIN_GLAND_AREA:
            continue
        gland_metrics_list.append(_gland_metrics(cnt, binary, gid))
        valid_contours.append(cnt)
        gid += 1

    if not valid_contours:
        empty_arch = ArchitectureMetrics(
            gland_count=0, mean_inter_gland_dist=0, min_inter_gland_dist=0,
            crowding_index=0, tumor_bud_count=0, cribriform_score=0,
            total_gland_area=0, mean_gland_area=0, area_std=0,
            mean_circularity=0, mean_solidity=0,
        )
        return MorphometricReport(
            glands=[], architecture=empty_arch,
            tumor_crop=_tumor_crop(img_rgb, binary),
            annotated_image=img_rgb.copy(),
            risk_flags=["Mask detected but no glands passed the minimum area filter."],
        )

    # 4. Separate buds from proper glands
    buds          = [cnt for cnt, gm in zip(valid_contours, gland_metrics_list)
                     if gm.area < BUD_AREA_THRESH]
    proper_glands = [(cnt, gm) for cnt, gm in zip(valid_contours, gland_metrics_list)
                     if gm.area >= BUD_AREA_THRESH]

    # 5. Cribriform detection
    cribriform_ids = set()
    for cnt, gm in proper_glands:
        if _has_internal_holes(cnt, binary):
            cribriform_ids.add(gm.gland_id)

    # 6. Spatial / architectural metrics
    centroids  = [_centroid(cnt) for cnt, _ in proper_glands]
    distances  = _inter_gland_distances(centroids)
    areas      = np.array([gm.area for _, gm in proper_glands])
    circs      = np.array([gm.circularity for _, gm in proper_glands])
    solids     = np.array([gm.solidity    for _, gm in proper_glands])

    crowding_index = float(
        np.mean(distances < CROWDING_DIST_THRESH)
    ) if len(distances) > 0 else 0.0

    arch = ArchitectureMetrics(
        gland_count            = len(proper_glands),
        mean_inter_gland_dist  = float(distances.mean()) if len(distances) > 0 else 0.0,
        min_inter_gland_dist   = float(distances.min())  if len(distances) > 0 else 0.0,
        crowding_index         = crowding_index,
        tumor_bud_count        = len(buds),
        cribriform_score       = len(cribriform_ids) / len(proper_glands) if proper_glands else 0.0,
        total_gland_area       = float(areas.sum()),
        mean_gland_area        = float(areas.mean()),
        area_std               = float(areas.std()),
        mean_circularity       = float(circs.mean()),
        mean_solidity          = float(solids.mean()),
    )

    # 7. Tumor crop (mask-isolated region only)
    crop = _tumor_crop(img_rgb, binary)

    # 8. Annotated full image
    all_valid_cnts = [cnt for cnt, _ in proper_glands] + buds
    all_valid_gms  = [gm  for _, gm  in proper_glands]
    annotated = _annotated_image(img_rgb, all_valid_cnts, all_valid_gms,
                                 buds, cribriform_ids)

    # 9. Risk flags
    flags = _risk_flags(arch, [gm for _, gm in proper_glands])

    return MorphometricReport(
        glands        = [gm for _, gm in proper_glands],
        architecture  = arch,
        tumor_crop    = crop,
        annotated_image = annotated,
        risk_flags    = flags,
    )