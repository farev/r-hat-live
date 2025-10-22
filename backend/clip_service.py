"""
CLIP Service for Object Identification
Uses CLIP to match text queries with detected objects
"""

import cv2
import numpy as np
import clip
import torch
from PIL import Image
from typing import List, Dict, Tuple, Optional
import base64
from io import BytesIO

class CLIPService:
    def __init__(self, model_name='ViT-B/16', device=None):
        """
        Initialize CLIP model

        Args:
            model_name: CLIP model variant ('ViT-B/32', 'ViT-B/16', 'ViT-L/14', etc.)
            device: Device to run model on ('cuda' or 'cpu')
        """
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Loading CLIP model {model_name} on {self.device}...")
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        print("CLIP model loaded successfully!")

    def match_object(
        self,
        image: np.ndarray,
        text_query: str,
        detections: List[Dict],
        top_k: int = 1
    ) -> List[Tuple[Dict, float]]:
        """
        Match a text query to detected objects using CLIP

        Args:
            image: Full image as numpy array (BGR format)
            text_query: Text description of object to find
            detections: List of detections from YOLO (with bbox, class_name, etc.)
            top_k: Return top K matches

        Returns:
            List of (detection, similarity_score) tuples, sorted by score (highest first)
        """
        if not detections:
            return []

        # Convert image to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img_height, img_width = image.shape[:2]

        # Extract image crops for each detection with expanded context
        crops = []
        expansion_factor = 0.3  # Expand bbox by 30% on each side for more context

        for det in detections:
            bbox = det['bbox']

            # Calculate original bbox in pixels
            x1 = int(bbox['x'] * img_width)
            y1 = int(bbox['y'] * img_height)
            x2 = int((bbox['x'] + bbox['width']) * img_width)
            y2 = int((bbox['y'] + bbox['height']) * img_height)

            # Expand bbox for better context
            width = x2 - x1
            height = y2 - y1
            x1_expanded = x1 - int(width * expansion_factor)
            y1_expanded = y1 - int(height * expansion_factor)
            x2_expanded = x2 + int(width * expansion_factor)
            y2_expanded = y2 + int(height * expansion_factor)

            # Ensure coordinates are within image bounds
            x1_expanded = max(0, x1_expanded)
            y1_expanded = max(0, y1_expanded)
            x2_expanded = min(img_width, x2_expanded)
            y2_expanded = min(img_height, y2_expanded)

            crop = image_rgb[y1_expanded:y2_expanded, x1_expanded:x2_expanded]
            if crop.size > 0:
                crops.append(Image.fromarray(crop))
            else:
                crops.append(None)

        # Prepare text inputs for CLIP with better prompts
        # Use more descriptive prompts that CLIP understands better
        enhanced_query = f"a photo of a {text_query}"
        text_inputs = clip.tokenize([enhanced_query]).to(self.device)

        # Process valid crops
        valid_indices = [i for i, crop in enumerate(crops) if crop is not None]
        if not valid_indices:
            return []

        image_inputs = torch.stack([
            self.preprocess(crops[i]) for i in valid_indices
        ]).to(self.device)

        # Calculate similarities
        with torch.no_grad():
            image_features = self.model.encode_image(image_inputs)
            text_features = self.model.encode_text(text_inputs)

            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calculate cosine similarity
            similarities = (image_features @ text_features.T).squeeze()

            # Handle single detection case
            if len(valid_indices) == 1:
                similarities = similarities.unsqueeze(0)

        # DEBUG: Log CLIP scores for each detection
        print(f"\n[CLIP] Matching query '{text_query}' (enhanced: '{enhanced_query}') against {len(valid_indices)} detections:")
        print(f"[CLIP] Using {expansion_factor*100:.0f}% bbox expansion for context")
        for i, idx in enumerate(valid_indices):
            yolo_class = detections[idx]['class_name']
            query_sim = float(similarities[i])
            bbox = detections[idx]['bbox']
            print(f"  Detection #{idx+1}: YOLO={yolo_class:15s} | "
                  f"CLIP_score={query_sim:.4f} | "
                  f"bbox=({bbox['x']:.3f}, {bbox['y']:.3f}, {bbox['width']:.3f}, {bbox['height']:.3f})")

        # Map similarities back to detections
        results = []
        for idx, sim_score in zip(valid_indices, similarities):
            results.append((detections[idx], float(sim_score)))

        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x[1], reverse=True)

        print(f"[CLIP] Best match: {results[0][0]['class_name']} with CLIP score {results[0][1]:.4f}\n")

        # Return top K matches
        return results[:top_k]

    def match_from_base64(
        self,
        image_b64: str,
        text_query: str,
        detections: List[Dict],
        top_k: int = 1
    ) -> List[Tuple[Dict, float]]:
        """
        Match objects from base64 encoded image

        Args:
            image_b64: Base64 encoded image string
            text_query: Text description of object to find
            detections: List of detections from YOLO
            top_k: Return top K matches

        Returns:
            List of (detection, similarity_score) tuples
        """
        # Decode base64 to image
        image_data = base64.b64decode(image_b64.split(',')[1] if ',' in image_b64 else image_b64)
        image = Image.open(BytesIO(image_data))
        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        return self.match_object(image, text_query, detections, top_k)


# Global instance
_clip_service = None

def get_clip_service(model_name='ViT-L/14') -> CLIPService:
    """Get or create global CLIP service instance"""
    global _clip_service
    if _clip_service is None:
        _clip_service = CLIPService(model_name=model_name)
    return _clip_service
