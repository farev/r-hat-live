"""
Test Object Tracker - Test CSRT tracking on webcam or video
Usage:
  python test_tracker.py               # Use webcam
  python test_tracker.py video.mp4     # Use video file

Controls:
  - Click and drag to draw bounding box around object to track
  - Press 'r' to reset/clear all trackers
  - Press 'q' to quit
"""

import sys
import cv2
import numpy as np
import uuid
from tracker_service import TrackerInstance

# Global variables
drawing = False
start_point = None
current_box = None
trackers = {}
frame_count = 0
fps_history = []

def draw_box(event, x, y, flags, param):
    """Mouse callback for drawing bounding boxes"""
    global drawing, start_point, current_box, frame, trackers

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            current_box = (start_point[0], start_point[1], x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        if start_point:
            x1, y1 = start_point
            x2, y2 = x, y

            # Ensure box has positive width/height
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            if x2 - x1 > 10 and y2 - y1 > 10:  # Minimum box size
                # Convert to normalized coordinates
                h, w = param['frame'].shape[:2]
                bbox = {
                    'x': x1 / w,
                    'y': y1 / h,
                    'width': (x2 - x1) / w,
                    'height': (y2 - y1) / h
                }

                # Create tracker
                tracker_id = str(uuid.uuid4())[:8]
                tracker = TrackerInstance(tracker_id, bbox, f"Object-{len(trackers)+1}")
                tracker.initialize(param['frame'], bbox)
                trackers[tracker_id] = tracker

                print(f"Created tracker {tracker_id} for {tracker.label}")

        current_box = None
        start_point = None


def main():
    global frame, frame_count, fps_history, trackers

    # Open video source
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        print(f"Opening video: {video_path}")
        cap = cv2.VideoCapture(video_path)
    else:
        print("Opening webcam (camera 0)")
        cap = cv2.VideoCapture(0)
        # Try to set reasonable webcam settings
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("Error: Could not open video source")
        sys.exit(1)

    # Try to read a test frame
    ret, test_frame = cap.read()
    if not ret:
        print("Error: Could not read from video source")
        print("Try granting camera permissions in System Settings > Privacy & Security > Camera")
        sys.exit(1)
    print(f"Successfully read test frame: {test_frame.shape}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {width}x{height} @ {fps} FPS")

    # Create window and set mouse callback
    window_name = 'Object Tracker Test'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, draw_box, {'frame': None})

    print("\n" + "="*60)
    print("INSTRUCTIONS:")
    print("  - Click and drag to select object to track")
    print("  - Press 'r' to reset/clear all trackers")
    print("  - Press 'q' to quit")
    print("="*60 + "\n")

    # FPS calculation
    import time
    prev_time = time.time()

    while True:
        ret, frame = cap.read()

        if not ret:
            print("End of video or error reading frame")
            break

        frame_count += 1
        display_frame = frame.copy()

        # Update mouse callback with current frame
        cv2.setMouseCallback(window_name, draw_box, {'frame': frame})

        # Update all trackers
        active_trackers = {}
        for tracker_id, tracker in list(trackers.items()):
            if not tracker.is_active:
                continue

            success, bbox, confidence = tracker.update(frame)

            if success and confidence > 0.3:
                # Convert normalized bbox to pixels
                h, w = frame.shape[:2]
                x = int(bbox['x'] * w)
                y = int(bbox['y'] * h)
                width = int(bbox['width'] * w)
                height = int(bbox['height'] * h)

                # Draw bounding box
                color = (0, 255, 0)  # Green for active tracking
                cv2.rectangle(display_frame, (x, y), (x + width, y + height), color, 2)

                # Draw label
                label = f"{tracker.label} ({confidence:.2f})"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(display_frame, (x, y - label_size[1] - 10),
                            (x + label_size[0], y), color, -1)
                cv2.putText(display_frame, label, (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

                active_trackers[tracker_id] = tracker
            else:
                # Draw lost tracker in red
                h, w = frame.shape[:2]
                x = int(bbox['x'] * w)
                y = int(bbox['y'] * h)
                width = int(bbox['width'] * w)
                height = int(bbox['height'] * h)

                color = (0, 0, 255)  # Red for lost
                cv2.rectangle(display_frame, (x, y), (x + width, y + height), color, 2)
                cv2.putText(display_frame, f"{tracker.label} (LOST)", (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                print(f"Tracker {tracker_id} lost at frame {frame_count}")

        trackers = active_trackers

        # Draw current selection box
        if drawing and current_box:
            x1, y1, x2, y2 = current_box
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

        # Calculate FPS
        curr_time = time.time()
        fps_actual = 1 / (curr_time - prev_time) if curr_time != prev_time else 0
        prev_time = curr_time
        fps_history.append(fps_actual)
        if len(fps_history) > 30:
            fps_history.pop(0)
        avg_fps = sum(fps_history) / len(fps_history)

        # Draw info overlay
        info_text = [
            f"Frame: {frame_count}",
            f"FPS: {avg_fps:.1f}",
            f"Trackers: {len(trackers)} active",
            "",
            "Click & drag to track object",
            "Press 'r' to reset | 'q' to quit"
        ]

        y_offset = 30
        for i, text in enumerate(info_text):
            cv2.putText(display_frame, text, (10, y_offset + i*25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Show frame
        cv2.imshow(window_name, display_frame)

        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            trackers.clear()
            print("All trackers cleared")

    cap.release()
    cv2.destroyAllWindows()

    print(f"\nTracking session complete!")
    print(f"Total frames: {frame_count}")
    if len(fps_history) > 0:
        print(f"Average FPS: {sum(fps_history) / len(fps_history):.1f}")
    else:
        print("No frames processed")


if __name__ == "__main__":
    main()
