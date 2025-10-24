"""
Main API Server for R-Hat Object Tracking
Combines YOLOv10, CLIP, and CSRT tracking
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn
import requests
from dotenv import load_dotenv

from yolo_service import get_yolo_service
from clip_service import get_clip_service
from tracker_service import get_tracker_service, decode_image
from image_service import get_image_service

# Load environment variables from backend/.env for local development
load_dotenv()

app = FastAPI(title="R-Hat Tracking API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class HighlightRequest(BaseModel):
    image: str  # base64 encoded
    text_query: str
    confidence_threshold: float = 0.25

class HighlightResponse(BaseModel):
    tracker_id: str
    bbox: Dict
    label: str
    confidence: float
    yolo_class: str

class TrackUpdateRequest(BaseModel):
    image: str  # base64 encoded
    tracker_ids: Optional[List[str]] = None

class TrackUpdateResponse(BaseModel):
    tracks: Dict[str, Dict]

class RemoveTrackerRequest(BaseModel):
    tracker_id: str

class ImageRequest(BaseModel):
    query: str

class ImageResponse(BaseModel):
    image_base64: str
    description: str
    attribution: str

class YouTubeSearchRequest(BaseModel):
    query: str
    timestamp: Optional[int] = 0

class YouTubeSearchResponse(BaseModel):
    video_id: str
    title: str
    url: str
    start_time: int
    channel_title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None


# Global service instances (initialized on first request)
yolo_service = None
clip_service = None
tracker_service = None
image_service = None


def init_services():
    """Initialize all services"""
    global yolo_service, clip_service, tracker_service

    if yolo_service is None:
        yolo_service = get_yolo_service(model_size='s')

    if clip_service is None:
        clip_service = get_clip_service(model_name='ViT-B/32')

    if tracker_service is None:
        tracker_service = get_tracker_service()


@app.get("/")
async def root():
    return {"message": "R-Hat Tracking API", "version": "1.0.0"}


@app.post("/highlight", response_model=HighlightResponse)
async def highlight_object(request: HighlightRequest):
    """
    Highlight an object in the image

    1. Run YOLOv10 to detect all objects
    2. Use CLIP to match text query to detections
    3. Initialize tracker for the best match
    4. Return tracker ID and bounding box
    """
    try:
        print(f"[DEBUG] /highlight called with text_query: {request.text_query}")

        print("[DEBUG] Initializing services...")
        init_services()
        print("[DEBUG] Services initialized successfully")

        # Decode image
        print("[DEBUG] Decoding image...")
        image = decode_image(request.image)
        print(f"[DEBUG] Image decoded: shape={image.shape}, dtype={image.dtype}")

        # Step 1: Detect all objects with YOLO
        print("[DEBUG] Running YOLO detection...")
        detections = yolo_service.detect(image)
        print(f"[DEBUG] YOLO detections: {len(detections)} objects found")

        if not detections:
            raise HTTPException(status_code=404, detail="No objects detected in the image")

        # Step 2: Use CLIP to find best matching object
        print(f"[DEBUG] Running CLIP matching for query: '{request.text_query}'...")
        matches = clip_service.match_object(
            image,
            request.text_query,
            detections,
            top_k=1
        )
        print(f"[DEBUG] CLIP matches: {len(matches)} found")

        if not matches:
            raise HTTPException(
                status_code=404,
                detail=f"No object found matching '{request.text_query}'"
            )

        best_match, similarity = matches[0]
        print(f"[DEBUG] Best match: {best_match['class_name']} with similarity {similarity:.4f}")

        # Check if similarity is high enough
        if similarity < 0.15:  # Low threshold for CLIP (lowered to 0.15 to catch body parts like "face")
            raise HTTPException(
                status_code=404,
                detail=f"Low confidence match for '{request.text_query}' (score: {similarity:.2f})"
            )

        # Step 3: Initialize tracker
        print("[DEBUG] Creating tracker...")
        tracker_id = tracker_service.create_tracker(
            image,
            best_match['bbox'],
            request.text_query
        )
        print(f"[DEBUG] Tracker created: {tracker_id}")

        response = HighlightResponse(
            tracker_id=tracker_id,
            bbox=best_match['bbox'],
            label=request.text_query,
            confidence=similarity,
            yolo_class=best_match['class_name']
        )
        print(f"[DEBUG] Returning response: {response}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in /highlight: {str(e)}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def fetch_youtube_video(query: str) -> Dict:
    """Fetch the first YouTube video result for a query."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="YouTube search is not configured. Set the YOUTUBE_API_KEY environment variable."
        )

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "key": api_key,
        "safeSearch": "moderate",
        "videoEmbeddable": "true",
    }

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"YouTube API request failed: {exc}"
        ) from exc

    data = response.json()
    items = data.get("items", [])
    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No YouTube videos found for '{query}'."
        )

    item = items[0]
    snippet = item.get("snippet", {})
    thumbnails = snippet.get("thumbnails", {})
    high_thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}

    return {
        "video_id": item["id"]["videoId"],
        "title": snippet.get("title", "YouTube Video"),
        "channel_title": snippet.get("channelTitle"),
        "description": snippet.get("description"),
        "thumbnail_url": high_thumb.get("url"),
    }


@app.post("/track/update", response_model=TrackUpdateResponse)
async def update_trackers(request: TrackUpdateRequest):
    """
    Update all active trackers with new frame

    Returns updated bounding boxes for all trackers
    """
    try:
        init_services()

        # Decode image
        image = decode_image(request.image)

        # Update all trackers
        tracks = tracker_service.update_trackers(image)

        # Filter by requested tracker_ids if provided
        if request.tracker_ids:
            tracks = {k: v for k, v in tracks.items() if k in request.tracker_ids}

        return TrackUpdateResponse(tracks=tracks)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/track/remove")
async def remove_tracker(request: RemoveTrackerRequest):
    """Remove a specific tracker"""
    try:
        init_services()
        success = tracker_service.remove_tracker(request.tracker_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Tracker {request.tracker_id} not found")

        return {"success": True, "tracker_id": request.tracker_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/youtube/search", response_model=YouTubeSearchResponse)
async def youtube_search(request: YouTubeSearchRequest):
    """Search YouTube for a video that matches the user's query."""
    video = fetch_youtube_video(request.query)
    start_time = request.timestamp or 0

    return YouTubeSearchResponse(
        video_id=video["video_id"],
        title=video["title"],
        channel_title=video.get("channel_title"),
        description=video.get("description"),
        thumbnail_url=video.get("thumbnail_url"),
        url=f"https://www.youtube.com/watch?v={video['video_id']}",
        start_time=start_time if start_time >= 0 else 0,
    )


@app.post("/track/clear")
async def clear_all_trackers():
    """Remove all trackers"""
    try:
        global tracker_service
        if tracker_service is None:
            tracker_service = get_tracker_service()
        tracker_service.remove_all_trackers()
        return {"success": True, "message": "All trackers removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fetch-image", response_model=ImageResponse)
async def fetch_image(request: ImageRequest):
    """
    Fetch an image based on a search query

    Args:
        query: Search query for the image

    Returns:
        Base64 encoded image with description and attribution
    """
    try:
        global image_service
        if image_service is None:
            image_service = get_image_service()

        result = image_service.get_image(request.query)
        return ImageResponse(
            image_base64=result["image_base64"],
            description=result["description"],
            attribution=result["attribution"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image fetch failed: {str(e)}")


@app.get("/status")
async def get_status():
    """Get service status"""
    init_services()

    active_trackers = tracker_service.get_active_tracker_ids() if tracker_service else []

    return {
        "yolo_loaded": yolo_service is not None,
        "clip_loaded": clip_service is not None,
        "tracker_loaded": tracker_service is not None,
        "active_trackers": len(active_trackers),
        "tracker_ids": active_trackers
    }


@app.on_event("startup")
async def startup_event():
    """Preload all AI models on server startup"""
    print("\n" + "="*60)
    print("🚀 R-Hat Tracking API - Starting Up")
    print("="*60)

    print("\n📦 Loading AI models (this may take a minute)...")

    try:
        # Initialize all services before accepting requests
        init_services()
        print("\n✅ All services loaded successfully!")
        print("   - YOLO: Ready for object detection")
        print("   - CLIP: Ready for object identification")
        print("   - Tracker: Ready for object tracking")
    except Exception as e:
        print(f"\n❌ Error loading services: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠️  Server will start but requests will fail!")

    print("\n" + "="*60)
    print("🟢 Server ready on http://0.0.0.0:8000")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("Starting R-Hat Tracking API...")
    print("Server running on http://0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000)
