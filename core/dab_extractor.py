import cv2
import numpy as np


class DABExtractor:
    def __init__(self, method='multi_threshold'):
        """
        Initialize DAB Extractor
        Args:
            method: 'multi_threshold'
        """
        self.method = method
    
    def detect_tissue_region(self, image):
        # 1. Preprocess
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        blurred = cv2.medianBlur(enhanced, 5)   # median often better than Gaussian here

        # 2. Adaptive thresholding (most reliable for uneven bg)
        binary = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            251,          # large block → good for global illumination changes
            15
        )

        # 3. Stronger cleaning
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25,25))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  kernel, iterations=3)

        # Optional: remove very small components early
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, None

        # Keep only largest → or filter by area
        valid_contours = [c for c in contours if cv2.contourArea(c) > 5000]  # tune
        if not valid_contours:
            return None, None, None

        largest = max(valid_contours, key=cv2.contourArea)

        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [largest], -1, 255, cv2.FILLED)

        x,y,w,h = cv2.boundingRect(largest)
        return mask, largest, (x,y,w,h)
        
    def preview_tissue_detection(self, image_path):
        """
        Preview tissue region detection on the image
        Returns: (preview_image, contour_info) or (None, None) if failed
        """
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            return None, None
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect tissue region
        tissue_mask, contour, bbox = self.detect_tissue_region(image_rgb)
        
        if tissue_mask is None or contour is None:
            return None, None
        
        # Create preview with contour overlay
        preview = image_rgb.copy()
        
        # Draw contour outline (thick green line)
        cv2.drawContours(preview, [contour], -1, (0, 255, 0), 4)
        
        # Draw bounding box
        x, y, w, h = bbox
        cv2.rectangle(preview, (x, y), (x + w, y + h), (255, 0, 0), 3)
        
        # Calculate contour properties
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        # Add text with tissue info
        text1 = f"Area: {int(area)} pixels"
        text2 = f"Bounding Box: {w}x{h}"
        cv2.putText(preview, text1, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(preview, text2, (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        contour_info = {
            'area': area,
            'perimeter': perimeter,
            'bbox': bbox
        }
        
        return preview, contour_info
    
    def multi_threshold_rgb(self, masked_image, tissue_mask):
        """
        Multi-level RGB thresholding for varied brown intensities
        Best for images with strong and varied DAB staining
        """
        R = masked_image[:, :, 0].astype(np.float32)
        G = masked_image[:, :, 1].astype(np.float32)
        B = masked_image[:, :, 2].astype(np.float32)
        
        # Light brown (tan areas)
        light_brown = (R > 100) & (R > B * 1.05) & (R > G * 1.02) & (B < 200)
        
        # Medium brown (typical DAB)
        medium_brown = (R > 100) & (R > B * 1.25) & (R > G * 1.1) & (B < 150)
        
        # Dark brown (strong DAB)
        dark_brown = (R > 80) & (R > B * 1.3) & (G > 50) & (B < 120)
        
        # Exclude very bright white areas (unstained)
        intensity_sum = R + G + B
        not_white = intensity_sum < 720
        
        # Combine all brown intensities
        all_brown = (light_brown | medium_brown | dark_brown) & not_white
        
        dab_mask = np.zeros(masked_image.shape[:2], dtype=np.uint8)
        dab_mask[all_brown] = 255
        dab_mask = cv2.bitwise_and(dab_mask, tissue_mask)
        
        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        dab_mask = cv2.morphologyEx(dab_mask, cv2.MORPH_OPEN, kernel)
        dab_mask = cv2.morphologyEx(dab_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        return dab_mask
    
    # def rgb_to_od(self, img):
    #     """Convert RGB to Optical Density"""
    #     img = img.astype(np.float32) + 1  # Avoid log(0)
    #     od = -np.log(img / 255.0)
    #     return od
    
    # def color_deconvolution_dab(self, masked_image, tissue_mask):
    #     """
    #     Color deconvolution H-DAB separation
    #     Most accurate method for quantitative analysis
    #     """
    #     # Convert to Optical Density
    #     od = self.rgb_to_od(masked_image)
        
    #     # Stain vectors for H-DAB (standard values)
    #     H_vector = np.array([0.650, 0.704, 0.286])   # Hematoxylin
    #     DAB_vector = np.array([0.268, 0.570, 0.776]) # DAB
        
    #     # Normalize vectors
    #     H_vector = H_vector / np.linalg.norm(H_vector)
    #     DAB_vector = DAB_vector / np.linalg.norm(DAB_vector)
        
    #     # Create deconvolution matrix
    #     stain_matrix = np.array([H_vector, DAB_vector]).T
        
    #     # Deconvolve
    #     h, w = od.shape[:2]
    #     od_flat = od.reshape(-1, 3).T
    #     stain_flat = np.linalg.lstsq(stain_matrix, od_flat, rcond=None)[0]
        
    #     # Extract DAB channel
    #     dab_channel = stain_flat[1].reshape(h, w)
        
    #     # Normalize to 0-255
    #     dab_channel = np.clip(dab_channel, 0, None)
    #     if dab_channel.max() > 0:
    #         dab_channel = (dab_channel / dab_channel.max() * 255).astype(np.uint8)
    #     else:
    #         dab_channel = dab_channel.astype(np.uint8)
        
    #     # Threshold DAB
    #     _, dab_mask = cv2.threshold(dab_channel, 20, 255, cv2.THRESH_BINARY)
        
    #     # Apply tissue mask
    #     dab_mask = cv2.bitwise_and(dab_mask, tissue_mask)
        
    #     return dab_mask
    
    # def lab_based_detection(self, masked_image, tissue_mask):
    #     """
    #     Lab color space detection
    #     Alternative method for brown/purple separation
    #     """
    #     # Convert to Lab
    #     lab = cv2.cvtColor(masked_image, cv2.COLOR_RGB2LAB)
    #     L = lab[:, :, 0].astype(np.float32)  # Lightness
    #     a = lab[:, :, 1].astype(np.float32)  # Red-Green
    #     b = lab[:, :, 2].astype(np.float32)  # Yellow-Blue
        
    #     # Brown in Lab: high a (red), high b (yellow), medium L
    #     brown_pixels = (a > 130) & (b > 130) & (L > 30) & (L < 220)
        
    #     dab_mask = np.zeros(masked_image.shape[:2], dtype=np.uint8)
    #     dab_mask[brown_pixels] = 255
        
    #     # Apply tissue mask
    #     dab_mask = cv2.bitwise_and(dab_mask, tissue_mask)
        
    #     return dab_mask
    
    def extract_and_analyze(self, image_path):
        """
        Extract and analyze DAB staining
        Args:
            image_path: path to input image
        Returns:
            tuple: (original, tissue_mask, result, metrics)
        """
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            return None, None, None, {"Error": "Failed to load image"}
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect tissue region
        tissue_mask, contour, bbox = self.detect_tissue_region(image_rgb)
        if tissue_mask is None:
            return image_rgb, None, None, {"Error": "Tissue region not detected"}
        
        # Apply tissue mask
        masked_image = cv2.bitwise_and(image_rgb, image_rgb, mask=tissue_mask)
        
        dab_mask = self.multi_threshold_rgb(masked_image, tissue_mask)
        
        result = cv2.bitwise_and(masked_image, masked_image, mask=dab_mask)
        
        # Calculate metrics
        total_pixels = np.count_nonzero(tissue_mask)
        brown_pixels = np.count_nonzero(dab_mask)
        percentage = (brown_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        
        gray = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)
        dab_values = gray[dab_mask > 0]
        
        if len(dab_values) > 0:
            mean_intensity = np.mean(dab_values)
            std_intensity = np.std(dab_values)
            min_intensity = np.min(dab_values)
            max_intensity = np.max(dab_values)
        else:
            mean_intensity = std_intensity = min_intensity = max_intensity = 0
        
        metrics = {
            "Method": self.method,
            "Image Size": f"{image_rgb.shape[1]}x{image_rgb.shape[0]}",
            "Tissue Area (pixels)": int(total_pixels),
            "Brown Pixels": int(brown_pixels),
            "DAB Coverage (%)": round(float(percentage), 2),
            "Mean Intensity": round(float(mean_intensity), 2),
            "Std Intensity": round(float(std_intensity), 2),
            "Min Intensity": int(min_intensity),
            "Max Intensity": int(max_intensity)
        }
        
        # Draw contours of the brown/DAB regions on the original image
        contour_overlay, num_regions = self.draw_dab_contours(image_rgb, dab_mask)
        metrics["DAB Regions"] = num_regions

        return image_rgb, tissue_mask, result, metrics, contour_overlay

    def extract_and_analyze_whole(self, image_path):
        """
        Extract and analyze DAB staining on the entire image (no tissue detection).
        Returns the same tuple shape as extract_and_analyze so threads stay uniform:
        (original, full_mask, result, metrics, contour_overlay)
        """
        image = cv2.imread(image_path)
        if image is None:
            return None, None, None, {"Error": "Failed to load image"}, None

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Use a full white mask — every pixel is considered tissue
        full_mask = np.ones(image_rgb.shape[:2], dtype=np.uint8) * 255

        dab_mask = self.multi_threshold_rgb(image_rgb, full_mask)

        result = cv2.bitwise_and(image_rgb, image_rgb, mask=dab_mask)

        total_pixels = image_rgb.shape[0] * image_rgb.shape[1]
        brown_pixels = int(np.count_nonzero(dab_mask))
        percentage = (brown_pixels / total_pixels) * 100 if total_pixels > 0 else 0

        gray = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)
        dab_values = gray[dab_mask > 0]
        if len(dab_values) > 0:
            mean_intensity = float(np.mean(dab_values))
            std_intensity  = float(np.std(dab_values))
            min_intensity  = int(np.min(dab_values))
            max_intensity  = int(np.max(dab_values))
        else:
            mean_intensity = std_intensity = min_intensity = max_intensity = 0

        contour_overlay, num_regions = self.draw_dab_contours(image_rgb, dab_mask)

        metrics = {
            "Method": self.method,
            "Image Size": f"{image_rgb.shape[1]}x{image_rgb.shape[0]}",
            "Tissue Area (pixels)": total_pixels,
            "Brown Pixels": brown_pixels,
            "DAB Coverage (%)": round(percentage, 2),
            "DAB Regions": num_regions,
            "Mean Intensity": round(mean_intensity, 2),
            "Std Intensity": round(std_intensity, 2),
            "Min Intensity": min_intensity,
            "Max Intensity": max_intensity,
        }

        return image_rgb, full_mask, result, metrics, contour_overlay

    def draw_dab_contours(self, original_image, dab_mask):
        """
        Find contours of the detected DAB/brown regions and draw them
        on a copy of the original image.
        Args:
            original_image: RGB image (numpy array)
            dab_mask: binary mask of detected DAB pixels
        Returns:
            overlay: original image with DAB region contours drawn on it
        """
        overlay = original_image.copy()

        # Find all external contours in the DAB mask
        contours, _ = cv2.findContours(dab_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter out tiny noise contours (tune area threshold as needed)
        min_area = 50
        significant_contours = [c for c in contours if cv2.contourArea(c) > min_area]

        # Draw filled semi-transparent highlight over DAB regions
        highlight = overlay.copy()
        cv2.drawContours(highlight, significant_contours, -1, (255, 165, 0), cv2.FILLED)
        cv2.addWeighted(highlight, 0.3, overlay, 0.7, 0, overlay)

        # Draw contour outlines on top (bright orange, visible against tissue)
        cv2.drawContours(overlay, significant_contours, -1, (255, 100, 0), 2)

        # Add legend text
        num_regions = len(significant_contours)

        return overlay, num_regions