"""
Object Tracking Service
Manages multiple object trackers using OpenCV's CSRT tracker
TODO: Upgrade to OSTrack for better performance
"""

import cv2
import numpy as np
import uuid
from typing import Dict, Optional, Tuple
import base64
from io import BytesIO
from PIL import Image

class TrackerInstance:
    """Single object tracker instance"""

    def __init__(self, tracker_id: str, initial_bbox: Dict, label: str):
        """
        Initialize a tracker instance

        Args:
            tracker_id: Unique identifier for this tracker
            initial_bbox: Initial bounding box {'x', 'y', 'width', 'height'} in normalized coords
            label: Label/name of the tracked object
        """
        self.tracker_id = tracker_id
        self.label = label
        self.bbox = initial_bbox
        self.confidence = 1.0
        self.is_active = True

        # Use CSRT tracker (slower but more accurate than KCF)
        # OpenCV 4.5.1+ moved trackers to legacy module
        try:
            self.tracker = cv2.TrackerCSRT_create()
        except AttributeError:
            self.tracker = cv2.legacy.TrackerCSRT_create()

        self.initialized = False

    def initialize(self, frame: np.ndarray, bbox: Dict):
        """
        Initialize the tracker with the first frame

        Args:
            frame: Initial frame (BGR format)
            bbox: Bounding box in normalized coordinates
        """
        h, w = frame.shape[:2]

        # Convert normalized bbox to pixel coordinates
        x = int(bbox['x'] * w)
        y = int(bbox['y'] * h)
        width = int(bbox['width'] * w)
        height = int(bbox['height'] * h)

        # Ensure bbox is within frame bounds
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        width = max(1, min(width, w - x))
        height = max(1, min(height, h - y))

        # Initialize OpenCV tracker (expects x, y, width, height)
        self.tracker.init(frame, (x, y, width, height))
        self.initialized = True

    def update(self, frame: np.ndarray) -> Tuple[bool, Dict, float]:
        """
        Update tracker with new frame

        Args:
            frame: New frame (BGR format)

        Returns:
            Tuple of (success, bbox_normalized, confidence)
        """
        if not self.initialized:
            return False, self.bbox, 0.0

        # Update tracker
        success, bbox_pixels = self.tracker.update(frame)

        if success:
            # Convert pixel bbox to normalized
            h, w = frame.shape[:2]
            x, y, width, height = bbox_pixels

            self.bbox = {
                'x': max(0, min(x / w, 1.0)),
                'y': max(0, min(y / h, 1.0)),
                'width': max(0, min(width / w, 1.0)),
                'height': max(0, min(height / h, 1.0))
            }

            # Simple confidence based on bbox size (heuristic)
            # If bbox becomes too small or large, confidence drops
            area = self.bbox['width'] * self.bbox['height']
            if area < 0.001 or area > 0.9:
                self.confidence = max(0.3, self.confidence - 0.1)
            else:
                self.confidence = min(1.0, self.confidence + 0.05)

            return True, self.bbox, self.confidence
        else:
            self.is_active = False
            self.confidence = 0.0
            return False, self.bbox, 0.0


class TrackerService:
    """Manages multiple object trackers"""

    def __init__(self):
        self.trackers: Dict[str, TrackerInstance] = {}
        self.last_frame: Optional[np.ndarray] = None

    def create_tracker(self, image: np.ndarray, bbox: Dict, label: str) -> str:
        """
        Create a new tracker instance

        Args:
            image: Initial frame
            bbox: Initial bounding box (normalized)
            label: Object label

        Returns:
            tracker_id: Unique tracker ID
        """
        tracker_id = str(uuid.uuid4())
        tracker = TrackerInstance(tracker_id, bbox, label)
        tracker.initialize(image, bbox)
        self.trackers[tracker_id] = tracker
        self.last_frame = image.copy()

        return tracker_id

    def update_trackers(self, image: np.ndarray) -> Dict:
        """
        Update all active trackers with new frame

        Args:
            image: New frame (BGR format)

        Returns:
            Dictionary of tracker updates:
            {
                tracker_id: {
                    'bbox': {...},
                    'label': str,
                    'confidence': float,
                    'status': 'tracking' | 'lost'
                }
            }
        """
        self.last_frame = image.copy()
        results = {}

        for tracker_id, tracker in list(self.trackers.items()):
            if not tracker.is_active:
                results[tracker_id] = {
                    'bbox': tracker.bbox,
                    'label': tracker.label,
                    'confidence': 0.0,
                    'status': 'lost'
                }
                continue

            success, bbox, confidence = tracker.update(image)

            if success and confidence > 0.3:
                results[tracker_id] = {
                    'bbox': bbox,
                    'label': tracker.label,
                    'confidence': confidence,
                    'status': 'tracking'
                }
            else:
                results[tracker_id] = {
                    'bbox': bbox,
                    'label': tracker.label,
                    'confidence': confidence,
                    'status': 'lost'
                }
                tracker.is_active = False

        return results

    def remove_tracker(self, tracker_id: str) -> bool:
        """
        Remove a tracker

        Args:
            tracker_id: ID of tracker to remove

        Returns:
            Success status
        """
        if tracker_id in self.trackers:
            del self.trackers[tracker_id]
            return True
        return False

    def remove_all_trackers(self):
        """Remove all trackers"""
        self.trackers.clear()

    def get_active_tracker_ids(self):
        """Get list of active tracker IDs"""
        return [tid for tid, t in self.trackers.items() if t.is_active]


# Global tracker service instance
_tracker_service = None

def get_tracker_service() -> TrackerService:
    """Get or create global tracker service instance"""
    global _tracker_service
    if _tracker_service is None:
        _tracker_service = TrackerService()
    return _tracker_service


def decode_image(image_b64: str) -> np.ndarray:
    """Decode base64 image to numpy array"""
    image_data = base64.b64decode(image_b64.split(',')[1] if ',' in image_b64 else image_b64)
    image = Image.open(BytesIO(image_data))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
