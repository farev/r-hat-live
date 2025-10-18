"""
Capture a frame from webcam
Usage: python capture_frame.py [output_filename]
"""

import sys
import cv2

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else "test_frame.jpg"

    print("Opening webcam...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        sys.exit(1)

    print("Webcam opened. Press SPACE to capture, ESC to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read frame")
            break

        # Display frame
        cv2.imshow('Webcam - Press SPACE to capture, ESC to quit', frame)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("Cancelled")
            break
        elif key == 32:  # SPACE
            cv2.imwrite(output_file, frame)
            print(f"Frame saved to: {output_file}")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
