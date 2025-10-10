"""
R-Hat Backend - Grounded-SAM 2 Highlight Service
FastAPI server for object detection and segmentation
"""

import os
import sys
import base64
import io
import logging
from typing import Optional, List, Dict, Any

import numpy as np
import torch
import cv2
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add Grounded-SAM-2 to path
GROUNDED_SAM_PATH = os.path.join(os.path.dirname(__file__), "Grounded-SAM-2")
sys.path.insert(0, GROUNDED_SAM_PATH)

try:
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from grounding_dino.groundingdino.util.inference import load_model, predict
    import grounding_dino.groundingdino.datasets.transforms as T
    import supervision as sv
except ImportError as e:
    logger.error(f"Failed to import Grounded-SAM-2 dependencies: {e}")
    logger.error("Make sure you've run setup.sh and installed all dependencies")
    sys.exit(1)

# Models
app = FastAPI(title="R-Hat Highlight Service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instances
sam2_predictor: Optional[SAM2ImagePredictor] = None
grounding_model: Optional[Any] = None

# Model paths
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
SAM2_CHECKPOINT = os.path.join(MODELS_DIR, "sam2_hiera_large.pt")
SAM2_CONFIG = "sam2_hiera_l.yaml"
GROUNDING_DINO_CHECKPOINT = os.path.join(MODELS_DIR, "groundingdino_swint_ogc.pth")
GROUNDING_DINO_CONFIG = os.path.join(GROUNDED_SAM_PATH, "grounding_dino", "groundingdino", "config", "GroundingDINO_SwinT_OGC.py")

# Device - use CPU for compatibility with Grounding DINO
# MPS (Metal) and CUDA cause issues with Grounding DINO on some systems
DEVICE = "cpu"
logger.info(f"Using device: {DEVICE}")


class HighlightRequest(BaseModel):
    """Request model for highlight endpoint"""
    image: str  # base64 encoded image
    object_name: str


class MaskInfo(BaseModel):
    """Information about a detected mask"""
    box: List[float]  # [x1, y1, x2, y2]
    confidence: float


class HighlightResponse(BaseModel):
    """Response model for highlight endpoint"""
    success: bool
    object_name: str
    masks: Optional[List[MaskInfo]] = None
    annotated_image: Optional[str] = None  # base64 encoded
    error: Optional[str] = None


def base64_to_image(base64_string: str) -> np.ndarray:
    """Convert base64 string to numpy image array"""
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]

    image_bytes = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(image_bytes))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def image_to_base64(image: np.ndarray) -> str:
    """Convert numpy image array to base64 string"""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def preprocess_image(image_bgr: np.ndarray) -> torch.Tensor:
    """
    Preprocess image for Grounding DINO
    Converts BGR numpy array to normalized tensor
    """
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # Convert to PIL Image
    image_pil = Image.fromarray(image_rgb)

    # Apply transforms
    transform = T.Compose([
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    image_transformed, _ = transform(image_pil, None)
    return image_transformed


def annotate_image(
    image: np.ndarray,
    detections: Any,
    labels: List[str]
) -> np.ndarray:
    """
    Annotate image with bounding boxes and masks
    """
    annotated_image = image.copy()

    # Create annotators with INDEX color lookup to avoid class_id requirement
    box_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.INDEX)
    mask_annotator = sv.MaskAnnotator(color_lookup=sv.ColorLookup.INDEX)
    label_annotator = sv.LabelAnnotator(color_lookup=sv.ColorLookup.INDEX)

    # Annotate
    annotated_image = mask_annotator.annotate(scene=annotated_image, detections=detections)
    annotated_image = box_annotator.annotate(scene=annotated_image, detections=detections)
    annotated_image = label_annotator.annotate(scene=annotated_image, detections=detections, labels=labels)

    return annotated_image


def load_models():
    """Load SAM2 and Grounding DINO models"""
    global sam2_predictor, grounding_model

    logger.info("Loading models...")

    # Check if model files exist
    if not os.path.exists(SAM2_CHECKPOINT):
        raise FileNotFoundError(
            f"SAM2 checkpoint not found at {SAM2_CHECKPOINT}. "
            "Please download it following backend/models/README.md"
        )

    if not os.path.exists(GROUNDING_DINO_CHECKPOINT):
        raise FileNotFoundError(
            f"Grounding DINO checkpoint not found at {GROUNDING_DINO_CHECKPOINT}. "
            "Please download it following backend/models/README.md"
        )

    # Load SAM2
    logger.info("Loading SAM2...")
    sam2_model = build_sam2(SAM2_CONFIG, SAM2_CHECKPOINT, device=DEVICE)
    sam2_predictor = SAM2ImagePredictor(sam2_model)
    logger.info("SAM2 loaded successfully")

    # Load Grounding DINO
    logger.info("Loading Grounding DINO...")
    grounding_model = load_model(
        model_config_path=GROUNDING_DINO_CONFIG,
        model_checkpoint_path=GROUNDING_DINO_CHECKPOINT,
        device=DEVICE
    )
    logger.info("Grounding DINO loaded successfully")

    logger.info("All models loaded!")


@app.on_event("startup")
async def startup_event():
    """Load models on startup"""
    try:
        load_models()
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        logger.error("Server will start but /highlight endpoint will fail")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": sam2_predictor is not None and grounding_model is not None,
        "device": DEVICE
    }


@app.post("/highlight", response_model=HighlightResponse)
async def highlight_object(request: HighlightRequest):
    """
    Highlight objects in an image based on text prompt
    """
    if sam2_predictor is None or grounding_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        logger.info(f"Processing highlight request for: {request.object_name}")

        # Decode image
        image = base64_to_image(request.image)

        # Preprocess image for Grounding DINO
        image_tensor = preprocess_image(image)

        # Run Grounding DINO to detect objects
        BOX_THRESHOLD = 0.35
        TEXT_THRESHOLD = 0.25

        boxes, confidences, labels = predict(
            model=grounding_model,
            image=image_tensor,
            caption=request.object_name,
            box_threshold=BOX_THRESHOLD,
            text_threshold=TEXT_THRESHOLD,
            device=DEVICE
        )

        if len(boxes) == 0:
            logger.info(f"No objects found for: {request.object_name}")
            return HighlightResponse(
                success=False,
                object_name=request.object_name,
                error=f"No '{request.object_name}' detected in the image"
            )

        logger.info(f"Found {len(boxes)} instances of {request.object_name}")

        # Convert boxes to format SAM2 expects
        h, w, _ = image.shape
        boxes_xyxy = boxes * torch.tensor([w, h, w, h])

        # Run SAM2 to get masks
        sam2_predictor.set_image(image)

        masks_list = []
        for box in boxes_xyxy:
            masks, scores, _ = sam2_predictor.predict(
                box=box.cpu().numpy(),
                multimask_output=False
            )
            # Convert mask to boolean type
            masks_list.append(masks[0].astype(bool))

        # Create detections
        masks_array = np.array(masks_list)
        detections = sv.Detections(
            xyxy=boxes_xyxy.cpu().numpy(),
            mask=masks_array,
            confidence=confidences.cpu().numpy()
        )

        # Create labels
        detection_labels = [
            f"{request.object_name} {conf:.2f}"
            for conf in confidences.cpu().numpy()
        ]

        # Annotate image
        annotated_image = annotate_image(image, detections, detection_labels)

        # Convert to base64
        annotated_base64 = image_to_base64(annotated_image)

        # Create mask info list
        mask_infos = [
            MaskInfo(
                box=box.tolist(),
                confidence=float(conf)
            )
            for box, conf in zip(boxes_xyxy.cpu().numpy(), confidences.cpu().numpy())
        ]

        logger.info(f"Successfully highlighted {len(mask_infos)} objects")

        return HighlightResponse(
            success=True,
            object_name=request.object_name,
            masks=mask_infos,
            annotated_image=annotated_base64
        )

    except Exception as e:
        logger.error(f"Error processing highlight request: {e}", exc_info=True)
        return HighlightResponse(
            success=False,
            object_name=request.object_name,
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
