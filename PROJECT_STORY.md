# R-Hat-Live: Real-Time Visual Assistance with AI

## Inspiration

The inspiration for R-Hat-Live came from exploring the capabilities of Google's Gemini Live API for multimodal AI interactions. While experimenting with real-time video analysis and voice commands, we discovered a critical limitation: Gemini's bounding box predictions were often inaccurate, making it unreliable for precise object tracking and augmented reality applications.

We envisioned a hands-free visual assistant that could help users in real-world scenarios—whether it's a technician needing to identify tools, someone organizing their workspace, or accessibility applications for visually impaired users. But for these use cases, precision matters. An AR overlay needs to track objects accurately as they move, not just approximately locate them once.

This challenge inspired us to build a hybrid architecture that combines Gemini's natural language understanding with specialized computer vision models for accurate, real-time object tracking.

## What it does

R-Hat-Live is a real-time visual assistance system that allows users to track objects in their environment using natural voice commands. Here's how it works:

1. **Voice-Activated Detection**: Users speak naturally to Gemini Live (e.g., "Can you highlight my phone?")
2. **Intelligent Object Detection**: The system uses YOLOv8 to detect all objects in the camera frame
3. **Semantic Matching**: CLIP (Contrastive Language-Image Pretraining) matches the voice query to the correct detected object
4. **Real-Time Tracking**: Once identified, OpenCV's CSRT tracker follows the object in real-time at 20 FPS, even as it moves
5. **Interactive Control**: Users can stop tracking individual objects through the UI

The result is a smooth, hands-free experience where objects are precisely highlighted with labeled bounding boxes that follow them as they move through the frame. Each tracked object shows its label, confidence score, and can be dismissed with a simple click.

## How we built it

### Architecture Overview

R-Hat-Live uses a **3-piece computer vision pipeline** to achieve accurate object tracking:

```
Voice Command → Gemini Live API → YOLOv8 → CLIP → CSRT Tracker
     ↓                                              ↑
  (Intent)                                    (20 FPS Loop)
```

### Technical Stack

**Frontend (React + TypeScript)**
- Real-time video streaming using `getUserMedia` API
- React state management with `useCallback` and `useRef` for tracking loop optimization
- Canvas-based frame capture for backend processing
- Normalized coordinate system (0.0-1.0) for resolution-independent tracking

**Backend (FastAPI + Python)**
- **YOLOv8s**: Object detection using Ultralytics' pre-trained model on COCO dataset (80 object classes)
- **CLIP ViT-L/14**: Vision-language model from OpenAI for semantic object matching
- **OpenCV CSRT Tracker**: Discriminative correlation filter tracker for real-time object following
- Asynchronous model preloading on server startup to eliminate first-request delays

### Key Technical Details

**1. YOLO Detection**
```python
# Detects all objects in frame, returns normalized bounding boxes
detections = yolo_service.detect(image)
# Returns: [{'bbox': {x, y, width, height}, 'class_name': 'cell phone', 'confidence': 0.89}]
```

**2. CLIP Matching with Context Expansion**
```python
# Expand bbox by 30% for better context
expansion_factor = 0.3
x1_expanded = x1 - int(width * expansion_factor)
# ...

# Enhanced prompts for better similarity
enhanced_query = f"a photo of a {text_query}"
```

This technique improved CLIP similarity scores from ~0.19 to more reliable matching by giving the model more visual context around objects.

**3. Real-Time Tracking Loop**
```typescript
// Update at 20 FPS using functional state updates to avoid stale closures
trackingIntervalRef.current = window.setInterval(async () => {
  const imageBase64 = canvasToBase64(canvas);

  setTrackedObjects(prev => {
    const trackerIds = prev.map(obj => obj.tracker_id);
    updateTrackers(imageBase64, trackerIds).then(updates => {
      setTrackedObjects(current =>
        current.map(obj => ({...obj, ...updates[obj.tracker_id]}))
        .filter(obj => obj.status === 'tracking')
      );
    });
    return prev;
  });
}, 50); // 20 FPS
```

The tracking loop captures frames continuously and sends them to the backend for position updates, using functional state updates to prevent React closure issues.

## Challenges we ran into

### 1. PyTorch 2.6 Security Changes

**Problem**: After updating dependencies, we encountered:
```
_pickle.UnpicklingError: Weights only load failed.
ultralytics.nn.tasks.DetectionModel was not an allowed global
```

**Root Cause**: PyTorch 2.6 changed the default `weights_only` parameter from `False` to `True` for security reasons when loading model weights.

**Solution**: We needed to set the environment variable *before* importing torch:
```python
# MUST be at the very top of yolo_service.py
import os
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

import torch  # Now torch respects our setting
```

Setting it after imports failed because torch had already initialized with its default settings.

### 2. Low CLIP Similarity Scores

**Problem**: Initial CLIP scores were only ~0.19-0.21, even for correct matches like a phone when querying "phone".

**Root Cause**: Two issues compounding:
- Tight bounding box crops provided insufficient visual context
- Generic single-word prompts didn't align with CLIP's training distribution

**Solution**:
1. **Context Expansion**: Expanded bounding boxes by 30% on all sides before cropping
2. **Prompt Engineering**: Changed from "phone" to "a photo of a phone" to better match CLIP's training format

This improved matching reliability significantly while keeping scores in CLIP's characteristic range.

### 3. React Closure Stale State

**Problem**: Tracking loop wasn't updating—bounding boxes stayed frozen at their initial positions instead of following moving objects.

**Root Cause**: The `startTrackingLoop` callback had `trackedObjects` in its dependency array:
```typescript
useCallback(() => {
  // This closure captures trackedObjects at creation time
  const trackerIds = trackedObjects.map(obj => obj.tracker_id);
}, [trackedObjects]); // ❌ Creates new interval each time, stale state
```

**Solution**: Use empty dependencies and functional state updates:
```typescript
useCallback(() => {
  setTrackedObjects(prev => {
    const trackerIds = prev.map(obj => obj.tracker_id); // ✅ Always latest
    // ...
  });
}, []); // ✅ Stable callback, no stale closures
```

### 4. OpenCV Tracker API Changes

**Problem**: `cv2.TrackerCSRT_create()` raised `AttributeError` on some systems.

**Root Cause**: OpenCV 4.5.1+ moved legacy trackers to a separate module.

**Solution**: Added compatibility fallback:
```python
try:
    self.tracker = cv2.TrackerCSRT_create()
except AttributeError:
    self.tracker = cv2.legacy.TrackerCSRT_create()
```

Also switched from `opencv-python` to `opencv-contrib-python` which includes the legacy module.

### 5. Performance Optimization

**Challenge**: Finding the right balance between smoothness and computational efficiency.

**Iterations**:
- Started at 10 FPS (100ms) → felt sluggish
- Increased to 30 FPS (33ms) → smooth but CPU intensive
- Settled on 20 FPS (50ms) → optimal balance

Also experimented with CSS transition timing (`0.03s linear` vs `0.05s ease-out`) to make bounding box movement feel natural rather than jittery.

## Accomplishments that we're proud of

### 1. Hybrid AI Architecture
We successfully integrated three different AI models (Gemini, YOLO, CLIP) into a cohesive pipeline where each component plays to its strengths:
- Gemini for natural language understanding
- YOLO for fast, general object detection
- CLIP for semantic matching without predefined classes

### 2. Real-Time Multi-Object Tracking
Achieved smooth 20 FPS tracking of multiple objects simultaneously with:
- Frame-to-frame position updates
- Automatic lost object removal
- Sub-50ms latency from camera to display

### 3. Context-Aware Computer Vision
The 30% bounding box expansion technique improved CLIP matching by providing visual context, demonstrating that even state-of-the-art models benefit from thoughtful preprocessing.

### 4. Production-Ready Error Handling
- Comprehensive fallback mechanisms for OpenCV compatibility
- PyTorch version resilience
- Graceful degradation when tracking fails
- Detailed logging for debugging

### 5. Clean Separation of Concerns
The frontend handles real-time rendering and state management, while the backend manages computationally intensive CV operations. Models are preloaded on startup, eliminating cold-start delays.

## What we learned

### Computer Vision Pipeline Design

We learned that **accuracy and speed are separate problems** requiring separate solutions:
- YOLO for speed (real-time detection)
- CLIP for accuracy (semantic understanding)
- Classical tracking (CSRT) for efficiency (no need to re-run detection every frame)

The combination gives us the best of all worlds.

### Prompt Engineering for Vision-Language Models

CLIP's performance is highly sensitive to prompt format. The phrase "a photo of a {object}" outperformed single-word prompts because it matches CLIP's training distribution of natural image captions.

### React State Management Patterns

Learned the hard way about closure traps in `useCallback` with `setInterval`. Key takeaway:
- **Never** depend on state variables in callbacks that run continuously
- **Always** use functional updates: `setState(prev => ...)`
- Empty dependency arrays create stable callbacks when combined with functional updates

### PyTorch Ecosystem Evolution

Discovered that security improvements in ML frameworks can break existing code. The weights_only change in PyTorch 2.6 taught us to:
- Read release notes carefully
- Set compatibility environment variables early
- Test model loading in isolation

### Bounding Box Mathematics

Working with normalized coordinates ($x, y, width, height \in [0, 1]$) simplified resolution independence but required careful conversion:

$$
\text{pixel}_x = \text{normalized}_x \times \text{frame}_{\text{width}}
$$

$$
\text{expanded}_{\text{bbox}} = [x - \alpha w, y - \alpha h, (1 + 2\alpha)w, (1 + 2\alpha)h]
$$

where $\alpha = 0.3$ for our 30% expansion factor.

## What's next for R-Hat-Live

### 1. Advanced Tracking Algorithms
Replace CSRT with **OSTrack** (Object Tracking with Transformers) for better occlusion handling and longer tracking persistence. OSTrack is mentioned in our code TODOs and would provide state-of-the-art tracking performance.

### 2. Persistent Object Memory
Implement re-identification when objects return to frame after leaving, using:
- Feature embeddings from CLIP for appearance matching
- Tracking history to predict likely re-entries
- Automatic tracker reinitialization

### 3. Depth and Spatial Understanding
Integrate depth estimation to:
- Provide 3D coordinates for AR applications
- Distinguish between similar objects at different distances
- Enable "pick up the phone on the left" vs "phone on the right" commands

### 4. Hardware Tool Recognition
Expand to specialized domains:
- Fine-tune CLIP on tool datasets
- Add measurement overlays (wrench sizes, wire gauges)
- Create voice-guided repair instructions

### 5. Multi-Modal Interaction
Beyond tracking, enable:
- "What is this?" queries with object description
- "How do I use this?" with instructional overlays
- "Find my [object]" with room-scale scanning

### 6. Edge Deployment
Optimize for edge devices:
- Model quantization (INT8, FP16)
- TensorRT acceleration
- Deploy on devices like Raspberry Pi or AR glasses

### 7. Privacy-First Architecture
All processing currently runs locally with minimal API usage. Future improvements:
- Fully offline mode with local Gemini alternatives
- No cloud storage of video frames
- User-controlled data retention

---

**R-Hat-Live** represents a step toward more natural human-computer interaction where AI understands both what we say and what we see, enabling hands-free assistance in real-world tasks. By combining the strengths of multiple AI models, we've created a system that's both intelligent and precise—ready to help users navigate their physical world with voice and vision.
