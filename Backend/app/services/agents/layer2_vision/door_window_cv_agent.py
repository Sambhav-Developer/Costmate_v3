import cv2
import numpy as np
from typing import List, Dict, Any
from app.core.logging import logger

class DoorWindowCVAgent:
    def __init__(self):
        # In a full deployment, load YOLO / SAM models here
        # self.yolo_model = YOLO("models/door_window_detector.pt")
        # self.sam_predictor = SamPredictor(sam_model)
        pass

    def process_floor_plan(self, image_path: str, sheet_id: str, floor_no: int) -> List[Dict[str, Any]]:
        """Main orchestrator for Agent 2 CV Pipeline."""
        logger.info(f"Agent 2: Processing floor plan for {sheet_id}")
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to load image {image_path}")
            return []
            
        # 1. Mask excluded areas (Task 2.2)
        masked_image, exclusion_mask = self._detect_exclusions(image)
        
        # 2. Detect symbols and geometry (Task 2.1)
        detections = self._detect_symbols(masked_image)
        
        results = []
        for det in detections:
            bbox = det["bbox"]
            
            # 3. Crop tag callout (Task 2.3)
            # The actual crop will be fed to OCR agents 3-5
            crop = self._crop_tag(masked_image, bbox)
            
            # 4. Classify opening mode geometrically (Task 2.4)
            opening_mode = self._classify_opening_mode(det.get("swing_arc_pixels"))
            
            # 5. Wall association & INT/EXT (Task 2.5)
            wall_data = self._associate_wall(image, bbox)
            
            results.append({
                "sheet_id": sheet_id,
                "floor_no": floor_no,
                "bbox": bbox,
                "wall_id": wall_data["wall_id"],
                "wall_type": wall_data["wall_type"],
                "wall_thickness": wall_data["wall_thickness"],
                "int_ext": wall_data["int_ext"],
                "opening_mode": opening_mode,
                "excluded": False, # Handled by mask, but explicit flag if needed
                "confidence": {
                    "wall_association": wall_data["confidence"]
                },
                # We return the crop image array to be processed by OCR agents later
                "tag_crop_image": crop
            })
            
        return results

    def _detect_exclusions(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Detects 'area not in scope' cross-hatch exclusion zones and masks them out.
        Returns the masked image and the mask itself.
        """
        # This is a structural representation. 
        # OpenCV logic: Convert to gray, apply Gabor filters or edge detection 
        # to find dense cross-hatching, then find contours of those areas.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Placeholder mask (all zeros = nothing excluded)
        exclusion_mask = np.zeros_like(gray)
        
        # Apply mask
        masked_image = image.copy()
        masked_image[exclusion_mask > 0] = [255, 255, 255] # White out the excluded areas
        
        return masked_image, exclusion_mask

    def _detect_symbols(self, image: np.ndarray) -> List[Dict]:
        """
        Uses YOLO/SAM to detect door/window symbols and their swing arcs.
        """
        # Placeholder for YOLO inference mapping
        # results = self.yolo_model(image)
        return []

    def _crop_tag(self, image: np.ndarray, bbox: List[int]) -> np.ndarray:
        """
        Crops a tight bounding box around each tag callout.
        Expects bbox in [ymin, xmin, ymax, xmax] format.
        """
        ymin, xmin, ymax, xmax = bbox
        
        # Add slight padding for OCR resilience
        padding = 10
        h, w = image.shape[:2]
        ymin_p = max(0, ymin - padding)
        xmin_p = max(0, xmin - padding)
        ymax_p = min(h, ymax + padding)
        xmax_p = min(w, xmax + padding)
        
        return image[ymin_p:ymax_p, xmin_p:xmax_p].copy()

    def _classify_opening_mode(self, swing_arc_pixels: np.ndarray) -> str:
        """
        Classifies opening mode from swing-arc geometry:
        180° continuous = single
        180° dashed = DA (Double Acting)
        2-leaf = CD (Center Parting / Double Door)
        """
        if swing_arc_pixels is None or len(swing_arc_pixels) == 0:
            return "unknown"
            
        # Example deterministic geometric logic:
        # 1. Fit ellipse/circle to the arc pixels using cv2.fitEllipse()
        # 2. Check if continuous or dashed by looking for pixel gaps along the arc
        # 3. Count connected components or arcs (1 arc = single/DA, 2 opposing arcs = CD)
        
        return "single"

    def _associate_wall(self, image: np.ndarray, bbox: List[int]) -> Dict:
        """
        Associates each instance with its nearest wall segment.
        Derives INT/EXT from wall position.
        """
        # Example deterministic geometry logic:
        # 1. Use line detection (cv2.HoughLinesP) around the bbox to find the nearest wall segment.
        # 2. Calculate thickness from parallel line distance.
        # 3. Ray-cast to determine if wall is on the exterior perimeter vs interior.
        
        return {
            "wall_id": "W-UNKNOWN",
            "wall_type": "Partition",
            "wall_thickness": "Unknown",
            "int_ext": "INT",
            "confidence": 0.5
        }

    def render_color_overlay(self, image_path: str, resolved_instances: List[Dict]) -> str:
        """
        Renders the final color-coded overlay once all instances are resolved:
        yellow = internal, blue = external, pink = storefront
        Returns path to highlighted image.
        """
        image = cv2.imread(image_path)
        if image is None:
            return None
            
        overlay = image.copy()
        for inst in resolved_instances:
            ymin, xmin, ymax, xmax = inst.get("bbox", [0,0,0,0])
            int_ext = str(inst.get("int_ext", "")).upper()
            is_storefront = inst.get("_is_storefront", False)
            
            # Colors in BGR
            if is_storefront:
                color = (203, 192, 255) # Pink
            elif int_ext == "EXT":
                color = (255, 0, 0) # Blue
            else:
                color = (0, 255, 255) # Yellow
                
            # Draw semi-transparent rectangle
            cv2.rectangle(overlay, (xmin, ymin), (xmax, ymax), color, -1)
            
        # Blend overlay with original
        alpha = 0.4
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        
        output_path = image_path.replace(".png", "_highlighted.png").replace(".jpg", "_highlighted.jpg")
        cv2.imwrite(output_path, image)
        logger.info(f"Agent 2: Final color overlay rendered to {output_path}")
        return output_path

cv_agent = DoorWindowCVAgent()
