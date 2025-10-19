"""
YOLO Object Detection Service
Detects all objects in a frame and returns bounding boxes
Using YOLOv10 (ultralytics will auto-download on first use)
YOLOv10 features NMS-free training for better multi-object detection
"""

# Fix for PyTorch 2.6 weights_only issue - MUST be set before importing torch
import os
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from typing import List, Dict, Tuple

class YOLOService:
    def __init__(self, model_size='s', conf_threshold=0.0075):
        """
        Initialize YOLO model

        Args:
            model_size: Model size ('n', 's', 'm', 'b', 'l', 'x')
                       YOLOv10 adds 'b' (balanced) variant
            conf_threshold: Confidence threshold for detections
        """
        self.conf_threshold = conf_threshold
        # Use YOLOv10 - NMS-free for better multi-object detection
        self.model_path = f'yolov10{model_size}.pt'

        print(f"Loading YOLOv10{model_size} model (will auto-download if needed)...")
        self.model = YOLO(self.model_path)
        print("YOLOv10 model loaded successfully!")

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Detect objects in an image

        Args:
            image: Input image as numpy array (BGR format)

        Returns:
            List of detections, each containing:
            - bbox: [x, y, width, height] in normalized coordinates (0-1)
            - class_id: COCO class ID
            - class_name: Object class name
            - confidence: Detection confidence score
        """
        # Run inference
        results = self.model(image, conf=self.conf_threshold, verbose=False)

        detections = []

        # Parse results
        for result in results:
            boxes = result.boxes
            img_height, img_width = image.shape[:2]

            for box in boxes:
                # Get bounding box coordinates (xyxy format)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                # Convert to normalized xywh format
                x_center = (x1 + x2) / 2 / img_width
                y_center = (y1 + y2) / 2 / img_height
                width = (x2 - x1) / img_width
                height = (y2 - y1) / img_height

                # Get class and confidence
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = self.model.names[class_id]

                detection = {
                    'bbox': {
                        'x': float(x_center - width/2),  # top-left x
                        'y': float(y_center - height/2),  # top-left y
                        'width': float(width),
                        'height': float(height)
                    },
                    'class_id': class_id,
                    'class_name': class_name,
                    'confidence': confidence
                }

                detections.append(detection)

        return detections

    def detect_from_base64(self, image_b64: str) -> List[Dict]:
        """
        Detect objects from base64 encoded image

        Args:
            image_b64: Base64 encoded image string

        Returns:
            List of detections
        """
        import base64
        from io import BytesIO
        from PIL import Image

        # Decode base64 to image
        image_data = base64.b64decode(image_b64.split(',')[1] if ',' in image_b64 else image_b64)
        image = Image.open(BytesIO(image_data))
        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        return self.detect(image)


# Global instance
_yolo_service = None

def get_yolo_service(model_size='s') -> YOLOService:
    """Get or create global YOLO service instance"""
    global _yolo_service
    if _yolo_service is None:
        _yolo_service = YOLOService(model_size=model_size)
    return _yolo_service
