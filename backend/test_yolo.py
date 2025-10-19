"""
Test YOLOv10 Detection - Visualize all detected objects
Usage: python test_yolo.py <path_to_image> [model_size] [conf_threshold]
Model sizes: n, s, m, b, l, x (YOLOv10 adds 'b' for balanced)
"""

import sys
import cv2
import numpy as np
from yolo_service import get_yolo_service

def draw_detections(image, detections):
    """Draw bounding boxes on image"""
    img_copy = image.copy()
    h, w = image.shape[:2]

    print(f"\n{'='*80}")
    print(f"Image size: {w}x{h}")
    print(f"Total detections: {len(detections)}")
    print(f"{'='*80}\n")

    for i, det in enumerate(detections):
        # Convert normalized coordinates to pixels
        x = int(det['bbox']['x'] * w)
        y = int(det['bbox']['y'] * h)
        width = int(det['bbox']['width'] * w)
        height = int(det['bbox']['height'] * h)

        # Draw rectangle
        color = (0, 255, 0)  # Green
        cv2.rectangle(img_copy, (x, y), (x + width, y + height), color, 2)

        # Draw label with confidence
        label = f"{det['class_name']} {det['confidence']:.2f}"
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)

        # Background for text
        cv2.rectangle(img_copy,
                     (x, y - label_size[1] - 10),
                     (x + label_size[0], y),
                     color, -1)

        # Text
        cv2.putText(img_copy, label, (x, y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # Print detection info
        print(f"Detection #{i+1}:")
        print(f"  Class: {det['class_name']} (ID: {det['class_id']})")
        print(f"  Confidence: {det['confidence']:.4f}")
        print(f"  Normalized BBox: x={det['bbox']['x']:.4f}, y={det['bbox']['y']:.4f}, "
              f"w={det['bbox']['width']:.4f}, h={det['bbox']['height']:.4f}")
        print(f"  Pixel BBox: x={x}, y={y}, w={width}, h={height}")
        print()

    return img_copy


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_yolo.py <path_to_image> [model_size] [conf_threshold]")
        print("\nModel sizes:")
        print("  n = nano (fastest, least accurate)")
        print("  s = small (default)")
        print("  m = medium")
        print("  b = balanced (YOLOv10 only)")
        print("  l = large")
        print("  x = extra large (slowest, most accurate)")
        print("\nExamples:")
        print("  python test_yolo.py test_image.jpg")
        print("  python test_yolo.py test_image.jpg m")
        print("  python test_yolo.py test_image.jpg l 0.3")
        sys.exit(1)

    image_path = sys.argv[1]
    model_size = sys.argv[2] if len(sys.argv) > 2 else 's'
    conf_threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25

    print(f"Loading image: {image_path}")
    image = cv2.imread(image_path)

    if image is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)

    print(f"Initializing YOLOv10{model_size} with confidence threshold {conf_threshold}...")
    yolo_service = get_yolo_service(model_size=model_size)
    yolo_service.conf_threshold = conf_threshold

    print("Running YOLOv10 detection (NMS-free for better multi-object detection)...")
    detections = yolo_service.detect(image)

    # Draw detections
    result_image = draw_detections(image, detections)

    # Save result
    output_path = image_path.rsplit('.', 1)[0] + '_yolo_detections.jpg'
    cv2.imwrite(output_path, result_image)
    print(f"{'='*80}")
    print(f"Result saved to: {output_path}")
    print(f"{'='*80}\n")

    # Display if possible
    try:
        cv2.imshow('YOLO Detections (Press any key to close)', result_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except:
        print("(Display not available, but image was saved)")


if __name__ == "__main__":
    main()
