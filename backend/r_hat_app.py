"""
R-Hat Desktop Application
Pure Python implementation with PyQt6 GUI
Integrates Gemini Live API + YOLO + CLIP + CSRT Tracking
"""

import sys
import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap, QFont
from dotenv import load_dotenv

from gemini_bridge_client import GeminiBridgeClient
from yolo_service import get_yolo_service
from clip_service import get_clip_service
from tracker_service import get_tracker_service, TrackerInstance

# Load environment variables
load_dotenv()

# Constants
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30


class VideoThread(QThread):
    """Thread for capturing video frames"""
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, cap):
        super().__init__()
        self.running = False
        self.cap = cap

    def run(self):
        """Capture video frames in background thread"""
        self.running = True
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame_ready.emit(frame)
            else:
                break

    def stop(self):
        """Stop video capture"""
        self.running = False


class RHatMainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("R-Hat - AI Visual Assistant")
        self.setGeometry(100, 100, 1200, 800)

        # Services
        self.gemini_session = None
        self.yolo_service = None
        self.clip_service = None
        self.tracker_service = None

        # State
        self.current_frame = None
        self.tracked_objects = {}  # {tracker_id: TrackerInstance}
        self.is_running = False

        # Video capture (initialized in main thread for macOS)
        self.cap = None
        self.video_thread = None

        # Timer for sending frames to Gemini
        self.gemini_frame_timer = QTimer()
        self.gemini_frame_timer.timeout.connect(self._send_frame_to_gemini)

        # Timer for tracking updates (20 FPS)
        self.tracking_timer = QTimer()
        self.tracking_timer.timeout.connect(self._update_tracking)

        # Setup UI
        self._setup_ui()

        # Initialize services
        self._init_services()

    def _setup_ui(self):
        """Setup the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left side - Video and controls
        left_layout = QVBoxLayout()

        # Title
        title_label = QLabel("R-Hat")
        title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title_label)

        # Video display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setMaximumSize(640, 480)
        self.video_label.setStyleSheet("border: 2px solid #333; background-color: black;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.video_label)

        # Controls
        controls_layout = QHBoxLayout()

        self.start_button = QPushButton("Start Session")
        self.start_button.setMinimumHeight(50)
        self.start_button.clicked.connect(self._toggle_session)
        controls_layout.addWidget(self.start_button)

        left_layout.addLayout(controls_layout)

        # Status label
        self.status_label = QLabel("Click 'Start Session' to begin")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        left_layout.addWidget(self.status_label)

        main_layout.addLayout(left_layout)

        # Right side - Transcription panel
        right_layout = QVBoxLayout()

        transcription_label = QLabel("Conversation")
        transcription_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        right_layout.addWidget(transcription_label)

        self.transcription_text = QTextEdit()
        self.transcription_text.setReadOnly(True)
        self.transcription_text.setMinimumWidth(400)
        self.transcription_text.setStyleSheet("background-color: #1a1a1a; color: #ffffff; padding: 10px; border-radius: 5px;")
        right_layout.addWidget(self.transcription_text)

        # AI State indicator
        self.ai_state_label = QLabel("AI: Idle")
        self.ai_state_label.setStyleSheet("padding: 10px; background-color: #333; color: white; border-radius: 5px;")
        self.ai_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.ai_state_label)

        main_layout.addLayout(right_layout)

    def _init_services(self):
        """Initialize AI services"""
        print("[INIT] Loading AI services...")
        self.status_label.setText("Loading AI models...")

        # Load YOLO, CLIP, Tracker
        self.yolo_service = get_yolo_service(model_size='s')
        self.clip_service = get_clip_service(model_name='ViT-B/32')
        self.tracker_service = get_tracker_service()

        print("[INIT] Services loaded successfully")
        self.status_label.setText("Ready! Click 'Start Session' to begin")

    def _toggle_session(self):
        """Start or stop the session"""
        if not self.is_running:
            self._start_session()
        else:
            self._stop_session()

    def _start_session(self):
        """Start Gemini session and video capture"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            self.status_label.setText("Error: API_KEY not found in .env file")
            return

        self.is_running = True
        self.start_button.setText("Stop Session")
        self.status_label.setText("Starting session...")

        # Initialize camera in main thread (required on macOS)
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        # Start Gemini Bridge Client session
        self.gemini_session = GeminiBridgeClient(
            api_key=api_key,
            on_transcription=self._on_transcription,
            on_status=self._on_status,
            on_ai_state=self._on_ai_state,
            on_highlight_object=self._on_highlight_object,
        )
        self.gemini_session.start()

        # Start video capture thread
        self.video_thread = VideoThread(self.cap)
        self.video_thread.frame_ready.connect(self._on_frame_ready)
        self.video_thread.start()

        # Start timers
        self.gemini_frame_timer.start(500)  # Send frame to Gemini every 500ms (2 FPS)
        self.tracking_timer.start(50)  # Update tracking at 20 FPS

        print("[SESSION] Started")

    def _stop_session(self):
        """Stop Gemini session and video capture"""
        self.is_running = False
        self.start_button.setText("Start Session")
        self.status_label.setText("Session stopped. Click 'Start Session' to begin again")

        # Stop timers
        self.gemini_frame_timer.stop()
        self.tracking_timer.stop()

        # Stop Gemini
        if self.gemini_session:
            self.gemini_session.stop()

        # Stop video
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait()

        # Clear trackers
        self.tracked_objects.clear()
        self.tracker_service.remove_all_trackers()

        print("[SESSION] Stopped")

    def _on_frame_ready(self, frame):
        """Called when a new video frame is available"""
        self.current_frame = frame.copy()

        # Display frame with tracking overlays
        display_frame = self._draw_tracking_overlays(frame)

        # Convert to Qt format and display
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qt_image))

    def _draw_tracking_overlays(self, frame):
        """Draw bounding boxes on frame"""
        display_frame = frame.copy()

        for tracker_id, tracker_data in self.tracked_objects.items():
            bbox = tracker_data['bbox']
            label = tracker_data['label']
            confidence = tracker_data['confidence']
            status = tracker_data['status']

            # Convert normalized coords to pixels
            h, w = frame.shape[:2]
            x = int(bbox['x'] * w)
            y = int(bbox['y'] * h)
            width = int(bbox['width'] * w)
            height = int(bbox['height'] * h)

            # Draw rectangle
            color = (0, 255, 0) if status == 'tracking' else (0, 0, 255)
            cv2.rectangle(display_frame, (x, y), (x + width, y + height), color, 2)

            # Draw label
            label_text = f"{label} ({int(confidence * 100)}%)"
            cv2.putText(display_frame, label_text, (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return display_frame

    def _send_frame_to_gemini(self):
        """Send current frame to Gemini Live"""
        if self.current_frame is not None and self.gemini_session:
            self.gemini_session.send_video_frame(self.current_frame)

    def _update_tracking(self):
        """Update all trackers"""
        if self.current_frame is None or not self.tracked_objects:
            return

        # Update trackers in backend service
        updates = self.tracker_service.update_trackers(self.current_frame)

        # Update local state
        for tracker_id, update in updates.items():
            if tracker_id in self.tracked_objects:
                self.tracked_objects[tracker_id].update(update)

        # Remove lost trackers
        self.tracked_objects = {
            tid: data for tid, data in self.tracked_objects.items()
            if data['status'] == 'tracking'
        }

    def _on_transcription(self, sender, text):
        """Called when transcription is received"""
        color = "#00ff00" if sender == "USER" else "#00aaff"
        self.transcription_text.append(f'<span style="color: {color}; font-weight: bold;">{sender}:</span> {text}')

    def _on_status(self, status):
        """Called when status message is received"""
        self.status_label.setText(status)

    def _on_ai_state(self, state):
        """Called when AI state changes"""
        state_colors = {
            'idle': '#666666',
            'listening': '#00ff00',
            'processing': '#ffaa00',
            'speaking': '#00aaff',
            'using_tool': '#ff00ff',
        }
        color = state_colors.get(state, '#666666')
        self.ai_state_label.setText(f"AI: {state.title()}")
        self.ai_state_label.setStyleSheet(f"padding: 10px; background-color: {color}; color: white; border-radius: 5px; font-weight: bold;")

    def _on_highlight_object(self, object_name):
        """Called when Gemini requests to highlight an object"""
        if self.current_frame is None:
            raise Exception("No video frame available")

        print(f"[HIGHLIGHT] Detecting '{object_name}'...")

        # Run YOLO detection
        detections = self.yolo_service.detect(self.current_frame)
        print(f"[YOLO] Found {len(detections)} objects")

        if not detections:
            raise Exception("No objects detected in frame")

        # Use CLIP to find the best match
        result = self.clip_service.identify_object(self.current_frame, detections, object_name)
        print(f"[CLIP] Best match: {result['label']} (confidence: {result['confidence']:.2f})")

        # Create tracker
        tracker_id = self.tracker_service.create_tracker(
            self.current_frame,
            result['bbox'],
            result['label']
        )

        # Add to local tracked objects
        self.tracked_objects[tracker_id] = {
            'bbox': result['bbox'],
            'label': result['label'],
            'confidence': result['confidence'],
            'status': 'tracking'
        }

        print(f"[TRACKER] Created tracker {tracker_id} for '{object_name}'")

    def closeEvent(self, event):
        """Handle window close"""
        if self.is_running:
            self._stop_session()

        # Release camera
        if self.cap:
            self.cap.release()

        event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show main window
    window = RHatMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
