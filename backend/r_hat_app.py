"""
R-Hat Live - AI Assistant with Real-time Object Tracking
Main application with PyQt6 UI and Gemini Live API integration
"""

# Fix for PyTorch 2.6 weights_only issue - MUST be set before importing torch
import os
import sys

# Monkey-patch torch.load to use weights_only=False by default for trusted models
import torch
_original_torch_load = torch.load

def _patched_torch_load(f, *args, **kwargs):
    """Patched torch.load that defaults to weights_only=False for compatibility with older models"""
    # If weights_only isn't specified, default to False for backward compatibility
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(f, *args, **kwargs)

# Apply the patch
torch.load = _patched_torch_load

import asyncio
import base64
from io import BytesIO
import cv2
import numpy as np
import sounddevice as sd
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPalette, QColor
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import tracking services (now in same directory)
from yolo_service import YOLOService
from clip_service import CLIPService
from tracker_service import TrackerService

# Load environment variables (go up one directory to find .env.local)
load_dotenv('../.env.local')

# Configuration
MODEL = "models/gemini-2.0-flash-exp"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "tools": [{
        "function_declarations": [{
            "name": "highlight_object",
            "description": "Highlight and track a specific object in the camera view by drawing a bounding box around it",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "The name or description of the object to highlight (e.g., 'red drill', 'coffee mug', 'person')"
                    }
                },
                "required": ["object_name"]
            }
        }]
    }]
}

# Audio settings
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Camera settings
CAMERA_INDEX = 0  # Use camera index 1 based on your test


class GeminiSession(QThread):
    """Background thread for Gemini Live API session"""
    status_changed = pyqtSignal(str)  # Signal for status updates
    function_called = pyqtSignal(str, dict)  # Signal for function calls (name, args)

    def __init__(self):
        super().__init__()
        self.session = None
        self.running = False
        self.audio_out_queue = asyncio.Queue()
        self.video_frame_queue = asyncio.Queue()
        self.audio_input_stream = None
        self.audio_output_stream = None
        self.current_frame = None  # Store current frame for tracking

    def run(self):
        """Run the Gemini session in async event loop"""
        self.running = True
        asyncio.run(self.async_run())

    async def async_run(self):
        """Main async loop for Gemini Live API"""
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.status_changed.emit("Error: No API key")
            return

        self.status_changed.emit("Connecting...")
        client = genai.Client(api_key=api_key)

        try:
            async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
                self.session = session
                self.status_changed.emit("Active")

                # Run concurrent tasks
                await asyncio.gather(
                    self.send_video_frames(),
                    self.send_audio(),
                    self.receive_audio(),
                    self.play_audio()
                )
        except Exception as e:
            self.status_changed.emit(f"Error: {str(e)}")
            print(f"Gemini session error: {e}")

    async def send_video_frames(self):
        """Send video frames to Gemini"""
        while self.running:
            try:
                # Wait for frame from main thread
                if not self.video_frame_queue.empty():
                    frame = await self.video_frame_queue.get()

                    # Convert to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_frame)

                    # Encode to JPEG
                    buffer = BytesIO()
                    pil_image.save(buffer, format="JPEG", quality=70)

                    # Create video blob
                    video_blob = {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(buffer.getvalue()).decode()
                    }

                    # Send to Gemini
                    if self.session:
                        await self.session.send_realtime_input(video=video_blob)

                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Video send error: {e}")

    async def send_audio(self):
        """Send microphone audio to Gemini"""
        audio_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio input status: {status}")
            audio_data = (indata[:, 0] * 32767).astype(np.int16).tobytes()
            asyncio.run_coroutine_threadsafe(audio_queue.put(audio_data), loop)

        # Open input stream
        self.audio_input_stream = sd.InputStream(
            samplerate=SEND_SAMPLE_RATE,
            channels=CHANNELS,
            dtype='float32',
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        )

        self.audio_input_stream.start()

        try:
            while self.running:
                audio_data = await audio_queue.get()
                if self.session:
                    audio_blob = types.Blob(
                        data=audio_data,
                        mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"
                    )
                    await self.session.send_realtime_input(audio=audio_blob)
        finally:
            if self.audio_input_stream:
                self.audio_input_stream.stop()
                self.audio_input_stream.close()

    async def receive_audio(self):
        """Receive audio from Gemini and handle function calls"""
        try:
            while self.running:
                if self.session:
                    turn = self.session.receive()
                    async for response in turn:
                        # Handle audio data
                        if response.data:
                            await self.audio_out_queue.put(response.data)

                        # Handle text responses
                        if response.text:
                            print(f"Gemini: {response.text}")

                        # Handle function calls
                        if response.tool_call:
                            for func_call in response.tool_call.function_calls:
                                print(f"Function called: {func_call.name} with args: {func_call.args}")
                                # Emit signal to main thread
                                self.function_called.emit(func_call.name, dict(func_call.args))

                        # Handle turn completion
                        if response.server_content and response.server_content.turn_complete:
                            self.status_changed.emit("Listening")
        except Exception as e:
            print(f"Audio receive error: {e}")

    async def play_audio(self):
        """Play audio responses from Gemini"""
        self.audio_output_stream = sd.OutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16'
        )
        self.audio_output_stream.start()

        try:
            while self.running:
                audio_data = await self.audio_out_queue.get()
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                await asyncio.to_thread(self.audio_output_stream.write, audio_array)
                self.status_changed.emit("Speaking")
        finally:
            if self.audio_output_stream:
                self.audio_output_stream.stop()
                self.audio_output_stream.close()

    def stop(self):
        """Stop the Gemini session"""
        self.running = False
        self.wait()


class RHatMainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.gemini_session = None
        self.camera = None
        self.timer = QTimer()
        self.current_frame = None
        self.session_active = False
        self.tracked_objects = []  # List of tracked objects with bounding boxes

        # Initialize tracking services
        print("🔧 Initializing tracking services...")
        self.yolo_service = YOLOService(model_size='s', conf_threshold=0.0075)
        self.clip_service = CLIPService(model_name='ViT-B/32')
        self.tracker_service = TrackerService()
        print("✅ Tracking services initialized!")

        self.init_ui()
        self.start_camera()

    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("R-Hat Live - AI Assistant")
        self.setGeometry(100, 100, 1280, 720)

        # Set black background
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.setPalette(palette)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Video display (full screen)
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        main_layout.addWidget(self.video_label)

        # Control panel (top-right overlay)
        self.create_control_panel()

    def create_control_panel(self):
        """Create the control panel in top-right corner"""
        # Create control widget
        control_widget = QWidget(self)
        control_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 10px;
                padding: 15px;
            }
            QPushButton {
                background-color: #1a1a1a;
                color: white;
                border: 1px solid #333;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border: 1px solid #555;
            }
            QPushButton:pressed {
                background-color: #0a0a0a;
            }
            QLabel {
                color: white;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(control_widget)

        # Status indicator
        status_layout = QHBoxLayout()
        self.status_indicator = QLabel("⚪")
        self.status_indicator.setStyleSheet("font-size: 20px;")
        self.status_label = QLabel("Idle")
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_label)
        layout.addLayout(status_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Session")
        self.start_button.clicked.connect(self.start_session)
        self.stop_button = QPushButton("Stop Session")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        # Position in top-right corner
        control_widget.setFixedSize(300, 120)
        control_widget.move(self.width() - 320, 20)
        control_widget.show()

        self.control_widget = control_widget

    def resizeEvent(self, event):
        """Reposition control panel on window resize"""
        super().resizeEvent(event)
        if hasattr(self, 'control_widget'):
            self.control_widget.move(self.width() - 320, 20)

    def start_camera(self):
        """Start camera capture"""
        self.camera = cv2.VideoCapture(CAMERA_INDEX)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)  # ~30 FPS

    def update_frame(self):
        """Update video frame"""
        ret, frame = self.camera.read()
        if ret:
            self.current_frame = frame.copy()

            # Update all active trackers at once
            if self.tracked_objects:
                tracker_results = self.tracker_service.update_trackers(frame)

                # Update each tracked object with its result
                for tracked_obj in self.tracked_objects:
                    if "tracker_id" in tracked_obj:
                        tracker_id = tracked_obj["tracker_id"]
                        if tracker_id in tracker_results:
                            result = tracker_results[tracker_id]
                            # Update bounding box and status
                            tracked_obj["bbox"] = result["bbox"]
                            tracked_obj["confidence"] = result["confidence"]
                            tracked_obj["status"] = result["status"]

            # Draw bounding boxes on frame
            display_frame = frame.copy()
            h, w = display_frame.shape[:2]

            for tracked_obj in self.tracked_objects:
                bbox = tracked_obj["bbox"]
                label = tracked_obj["label"]
                confidence = tracked_obj["confidence"]
                status = tracked_obj.get("status", "tracking")

                # Convert normalized coordinates to pixel coordinates
                # Handle both 'width'/'height' and 'w'/'h' formats
                x = int(bbox["x"] * w)
                y = int(bbox["y"] * h)
                box_w = int(bbox.get("width", bbox.get("w", 0)) * w)
                box_h = int(bbox.get("height", bbox.get("h", 0)) * h)

                # Choose color based on status
                color = (0, 255, 0) if status == "tracking" else (0, 0, 255)  # Green or Red

                # Draw rectangle
                cv2.rectangle(display_frame, (x, y), (x + box_w, y + box_h), color, 2)

                # Draw label background
                label_text = f"{label} ({confidence:.0%})"
                (text_w, text_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(display_frame, (x, y - text_h - 10), (x + text_w, y), color, -1)

                # Draw label text
                cv2.putText(display_frame, label_text, (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Convert to Qt format for display
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            # Scale to window size while maintaining aspect ratio
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)

            # Send frame to Gemini if session active (at 1 FPS)
            if self.session_active and self.gemini_session and hasattr(self, 'frame_counter'):
                self.frame_counter += 1
                if self.frame_counter >= 30:  # Every 30 frames = 1 FPS
                    asyncio.run_coroutine_threadsafe(
                        self.gemini_session.video_frame_queue.put(frame),
                        asyncio.get_event_loop()
                    )
                    self.frame_counter = 0

    @pyqtSlot()
    def start_session(self):
        """Start Gemini Live session"""
        self.session_active = True
        self.frame_counter = 0
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # Start Gemini session thread
        self.gemini_session = GeminiSession()
        self.gemini_session.status_changed.connect(self.update_status)
        self.gemini_session.function_called.connect(self.handle_function_call)
        self.gemini_session.start()

    @pyqtSlot()
    def stop_session(self):
        """Stop Gemini Live session"""
        self.session_active = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if self.gemini_session:
            self.gemini_session.stop()
            self.gemini_session = None

        self.update_status("Idle")

    @pyqtSlot(str)
    def update_status(self, status):
        """Update status indicator"""
        self.status_label.setText(status)

        # Update indicator color
        if "Active" in status:
            self.status_indicator.setText("🟢")
        elif "Listening" in status:
            self.status_indicator.setText("🟡")
        elif "Speaking" in status:
            self.status_indicator.setText("🔵")
        elif "Error" in status:
            self.status_indicator.setText("🔴")
        else:
            self.status_indicator.setText("⚪")

    @pyqtSlot(str, dict)
    def handle_function_call(self, function_name, args):
        """Handle function calls from Gemini"""
        print(f"📞 Function call received: {function_name}({args})")

        if function_name == "highlight_object":
            object_name = args.get("object_name", "")
            print(f"🎯 Highlighting object: {object_name}")

            if self.current_frame is None:
                print("❌ No frame available for detection")
                return

            # Step 1: YOLO Detection
            print(f"🔍 Running YOLO detection...")
            detections = self.yolo_service.detect(self.current_frame)
            print(f"   Found {len(detections)} objects")

            if not detections:
                print("❌ No objects detected in frame")
                return

            # Step 2: CLIP Matching
            print(f"🧠 Running CLIP matching for '{object_name}'...")
            matches = self.clip_service.match_object(
                self.current_frame,
                object_name,
                detections,
                top_k=1
            )

            if not matches:
                print(f"❌ No match found for '{object_name}'")
                return

            best_match, similarity_score = matches[0]
            print(f"   Best match: {best_match['class_name']} (similarity: {similarity_score:.2f})")

            # Check if similarity is high enough
            if similarity_score < 0.15:
                print(f"❌ Similarity too low ({similarity_score:.2f} < 0.15)")
                return

            # Step 3: Initialize CSRT Tracker
            print(f"📍 Initializing tracker...")
            tracker_id = self.tracker_service.create_tracker(
                self.current_frame,
                best_match['bbox'],
                object_name
            )

            # Add to tracked objects list
            self.tracked_objects.append({
                "tracker_id": tracker_id,
                "label": object_name,
                "bbox": best_match['bbox'],
                "confidence": similarity_score,
                "status": "tracking"
            })

            print(f"✅ Tracking started for '{object_name}' (ID: {tracker_id}, confidence: {similarity_score:.2%})")

    def closeEvent(self, event):
        """Clean up on window close"""
        if self.gemini_session:
            self.gemini_session.stop()
        if self.camera:
            self.camera.release()
        event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    window = RHatMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
