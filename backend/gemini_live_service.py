"""
Gemini Live API Service - Python Implementation
Handles WebSocket connection to Gemini Live API with audio/video streaming
"""

import asyncio
import base64
import json
import os
import threading
import queue
from typing import Callable, Optional, Dict, Any
from google import genai
from google.genai import types
import sounddevice as sd
import numpy as np
import cv2

# Audio configuration (matching TypeScript implementation)
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
FRAME_RATE = 2  # Send 2 frames per second to Gemini
JPEG_QUALITY = 70  # 0-100

# Audio settings
CHUNK_SIZE = 4096
CHANNELS = 1


class GeminiLiveSession:
    """Manages Gemini Live API session with audio/video streaming"""

    def __init__(
        self,
        api_key: str,
        on_transcription: Optional[Callable[[str, str], None]] = None,  # (sender, text)
        on_status: Optional[Callable[[str], None]] = None,
        on_ai_state: Optional[Callable[[str], None]] = None,  # 'listening', 'processing', 'speaking', 'using_tool'
        on_highlight_object: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize Gemini Live session

        Args:
            api_key: Google AI API key
            on_transcription: Callback for transcription updates (sender, text)
            on_status: Callback for status messages
            on_ai_state: Callback for AI state changes
            on_highlight_object: Callback when highlightObject tool is called
        """
        self.api_key = api_key
        self.on_transcription = on_transcription or (lambda s, t: None)
        self.on_status = on_status or (lambda s: None)
        self.on_ai_state = on_ai_state or (lambda s: None)
        self.on_highlight_object = on_highlight_object or (lambda o: None)

        # Session state
        self.client = None
        self.session = None
        self.running = False

        # Audio streams
        self.input_stream = None
        self.output_stream = None

        # Queues for thread-safe communication
        self.audio_input_queue = queue.Queue()
        self.video_frame_queue = queue.Queue(maxsize=2)  # Limit queue size
        self.audio_output_queue = queue.Queue()

        # Threads
        self.video_sender_thread = None
        self.audio_output_thread = None
        self.gemini_thread = None

        # Transcription buffers
        self.current_input_transcription = ""
        self.current_output_transcription = ""

    def start(self):
        """Start the Gemini Live session"""
        if self.running:
            print("Session already running")
            return

        self.running = True
        self.on_status("Initializing Gemini Live...")

        # Start audio input capture
        self._start_audio_input()

        # Start audio output playback
        self._start_audio_output()

        # Start Gemini session in separate thread
        self.gemini_thread = threading.Thread(target=self._run_gemini_session, daemon=True)
        self.gemini_thread.start()

        self.on_status("Connected! You can start talking.")
        self.on_ai_state('listening')

    def stop(self):
        """Stop the Gemini Live session"""
        self.running = False

        # Stop audio streams (sounddevice uses .stop() and .close())
        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()

        # Note: session cleanup is handled automatically when the async context exits

        self.on_status("Session stopped")

    def _start_audio_input(self):
        """Start capturing audio from microphone"""
        try:
            audio_chunks_received = [0]  # Use list to allow modification in nested function

            def audio_callback(indata, frames, time, status):
                """Callback for audio input"""
                if status:
                    print(f"[AUDIO] Input status: {status}")
                if self.running:
                    # Convert float32 to int16 PCM
                    audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                    audio_bytes = audio_int16.tobytes()
                    self.audio_input_queue.put(audio_bytes)
                    audio_chunks_received[0] += 1
                    if audio_chunks_received[0] == 1:
                        print(f"[AUDIO] First audio chunk captured! Size: {len(audio_bytes)} bytes")
                    if audio_chunks_received[0] % 100 == 0:
                        print(f"[AUDIO] Captured {audio_chunks_received[0]} chunks from microphone")

            # List available devices
            print(f"[AUDIO] Available input devices:")
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    print(f"  {i}: {dev['name']} (inputs: {dev['max_input_channels']})")

            # Get default input device
            default_device = sd.default.device[0]
            print(f"[AUDIO] Using default input device: {default_device}")

            self.input_stream = sd.InputStream(
                samplerate=INPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype='float32',
                blocksize=CHUNK_SIZE,
                callback=audio_callback
            )
            self.input_stream.start()
            print(f"[AUDIO] Started microphone capture at {INPUT_SAMPLE_RATE}Hz")
            print(f"[AUDIO] Stream active: {self.input_stream.active}")
        except Exception as e:
            print(f"[ERROR] Failed to start audio input: {e}")
            import traceback
            traceback.print_exc()
            self.on_status(f"Microphone error: {e}")

    def _start_audio_output(self):
        """Start audio output stream for Gemini responses"""
        try:
            self.output_stream = sd.OutputStream(
                samplerate=OUTPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=CHUNK_SIZE
            )
            self.output_stream.start()

            # Start playback thread
            self.audio_output_thread = threading.Thread(target=self._audio_output_worker, daemon=True)
            self.audio_output_thread.start()

            print(f"[AUDIO] Started audio output at {OUTPUT_SAMPLE_RATE}Hz")
        except Exception as e:
            print(f"[ERROR] Failed to start audio output: {e}")

    def _audio_output_worker(self):
        """Worker thread for playing audio output"""
        while self.running:
            try:
                audio_chunk = self.audio_output_queue.get(timeout=0.1)
                if audio_chunk and self.output_stream:
                    # Convert bytes to numpy array
                    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                    self.output_stream.write(audio_array)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ERROR] Audio playback error: {e}")

    def send_video_frame(self, frame: np.ndarray):
        """
        Send a video frame to Gemini

        Args:
            frame: OpenCV image (BGR format)
        """
        if not self.running:
            return

        # Non-blocking put - drop frame if queue is full
        try:
            self.video_frame_queue.put_nowait(frame.copy())
        except queue.Full:
            pass  # Drop frame if queue is full

    def _run_gemini_session(self):
        """Run Gemini Live session (runs in separate thread)"""
        asyncio.run(self._gemini_session_async())

    async def _gemini_session_async(self):
        """Async Gemini Live session"""
        try:
            # Initialize Gemini client
            self.client = genai.Client(api_key=self.api_key)

            # Define highlightObject tool
            highlight_tool = {
                "function_declarations": [
                    {
                        "name": "highlightObject",
                        "description": "Tracks and highlights a specific object in the user's camera view using computer vision. The system will detect the object, create a bounding box around it, and track it across frames.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "object_name": {
                                    "type": "string",
                                    "description": "The name or description of the object to track and highlight (e.g., 'red drill', 'capacitor', 'multimeter', 'screwdriver'). Be specific if there are multiple similar objects.",
                                }
                            },
                            "required": ["object_name"],
                        },
                    }
                ]
            }

            # Connect to Gemini Live
            config = {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": "Zephyr"}}
                },
                "input_audio_transcription": {},  # Enable input audio transcription
                "output_audio_transcription": {},  # Enable output audio transcription
                "tools": [highlight_tool],
                "system_instruction": "You are a friendly and helpful AI assistant that can see and hear. Respond to the user based on what you perceive from their video and audio. Keep your responses concise and conversational. When the user asks you to highlight, track, or show something in their camera view, use the `highlightObject` tool with a clear description of the object (e.g., 'red drill', 'capacitor', 'multimeter'). The system will automatically detect the object, create a bounding box, and track it across frames.",
            }

            async with self.client.aio.live.connect(
                model="gemini-2.5-flash-native-audio-preview-09-2025",
                config=config,
            ) as session:
                self.session = session
                print("[GEMINI] Connected to Gemini Live API")

                # Start sender tasks
                send_audio_task = asyncio.create_task(self._send_audio_loop(session))
                send_video_task = asyncio.create_task(self._send_video_loop(session))
                receive_task = asyncio.create_task(self._receive_loop(session))

                # Wait for all tasks
                await asyncio.gather(send_audio_task, send_video_task, receive_task)

        except Exception as e:
            print(f"[ERROR] Gemini session error: {e}")
            self.on_status(f"Gemini error: {e}")
            import traceback
            traceback.print_exc()

    async def _send_audio_loop(self, session):
        """Send audio data to Gemini"""
        print(f"[AUDIO] Audio send loop started, self.running={self.running}")
        print(f"[AUDIO] Queue size at start: {self.audio_input_queue.qsize()}")
        audio_count = 0
        empty_count = 0
        iteration = 0
        while self.running:
            iteration += 1
            if iteration % 100 == 0:
                print(f"[AUDIO] Loop iteration {iteration}, self.running={self.running}")
            try:
                # Get audio from queue (non-blocking)
                try:
                    audio_chunk = self.audio_input_queue.get_nowait()
                    # Send using send_realtime_input with types.Blob
                    try:
                        await asyncio.wait_for(
                            session.send_realtime_input(
                                audio=types.Blob(
                                    data=audio_chunk,
                                    mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}"
                                )
                            ),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        print(f"[ERROR] Audio send timeout on chunk {audio_count + 1}")
                        continue
                    audio_count += 1
                    if audio_count <= 10:  # Log first 10 chunks in detail
                        print(f"[AUDIO] Chunk #{audio_count} sent! Size: {len(audio_chunk)} bytes, mime: audio/pcm;rate={INPUT_SAMPLE_RATE}")
                    elif audio_count % 50 == 0:  # Then log every 50 chunks
                        print(f"[AUDIO] Sent {audio_count} audio chunks total")
                except queue.Empty:
                    empty_count += 1
                    if empty_count % 1000 == 0:
                        print(f"[AUDIO] Queue empty {empty_count} times, queue size: {self.audio_input_queue.qsize()}")
                    await asyncio.sleep(0.01)
            except Exception as e:
                print(f"[ERROR] Send audio error: {e}")
                import traceback
                traceback.print_exc()
                break
        print(f"[AUDIO] Audio send loop exited. Sent {audio_count} chunks total")

    async def _send_video_loop(self, session):
        """Send video frames to Gemini"""
        frame_count = 0
        while self.running:
            try:
                # Get frame from queue
                try:
                    frame = self.video_frame_queue.get(timeout=1.0 / FRAME_RATE)

                    # Encode frame as JPEG
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    jpg_bytes = buffer.tobytes()

                    # Send using send_realtime_input with types.Blob
                    await session.send_realtime_input(
                        video=types.Blob(
                            data=jpg_bytes,
                            mime_type="image/jpeg"
                        )
                    )
                    frame_count += 1
                    if frame_count % 10 == 0:  # Log every 10 frames
                        print(f"[VIDEO] Sent {frame_count} frames ({len(jpg_bytes)} bytes each)")

                except queue.Empty:
                    continue

            except Exception as e:
                print(f"[ERROR] Send video error: {e}")
                import traceback
                traceback.print_exc()
                break

    async def _receive_loop(self, session):
        """Receive and process messages from Gemini"""
        print("[GEMINI] Receive loop started, waiting for responses...")
        try:
            async for response in session.receive():
                print(f"[GEMINI] Received response: {type(response)}")
                await self._handle_gemini_response(response, session)
        except Exception as e:
            print(f"[ERROR] Receive loop error: {e}")
            import traceback
            traceback.print_exc()
        print("[GEMINI] Receive loop exited")

    async def _handle_gemini_response(self, response, session):
        """Handle a response from Gemini"""
        try:
            print(f"[DEBUG] Response attributes: {dir(response)}")

            # Handle tool calls
            if hasattr(response, 'tool_call') and response.tool_call:
                self.on_ai_state('using_tool')
                for fc in response.tool_call.function_calls:
                    if fc.name == "highlightObject":
                        object_name = fc.args.get("object_name", "")
                        print(f"[TOOL] highlightObject called: {object_name}")

                        try:
                            # Call the highlight callback
                            self.on_highlight_object(object_name)

                            # Send success response using send_tool_response
                            function_response = types.FunctionResponse(
                                id=fc.id,
                                name=fc.name,
                                response={"result": f"Successfully tracking {object_name}"}
                            )
                            await session.send_tool_response(
                                function_responses=function_response
                            )
                        except Exception as e:
                            # Send error response using send_tool_response
                            function_response = types.FunctionResponse(
                                id=fc.id,
                                name=fc.name,
                                response={"result": f"Error: {str(e)}"}
                            )
                            await session.send_tool_response(
                                function_responses=function_response
                            )

                await asyncio.sleep(0.5)
                self.on_ai_state('listening')

            # Handle transcriptions
            if hasattr(response, 'server_content') and response.server_content:
                content = response.server_content
                print(f"[DEBUG] server_content attributes: {dir(content)}")

                if content.output_transcription:
                    self.current_output_transcription += content.output_transcription.text
                    self.on_ai_state('speaking')

                if content.input_transcription:
                    self.current_input_transcription += content.input_transcription.text
                    self.on_ai_state('listening')

                # Handle turn complete
                if content.turn_complete:
                    if self.current_input_transcription.strip():
                        self.on_transcription("USER", self.current_input_transcription)
                    if self.current_output_transcription.strip():
                        self.on_transcription("MODEL", self.current_output_transcription)

                    self.current_input_transcription = ""
                    self.current_output_transcription = ""

                    await asyncio.sleep(0.5)
                    self.on_ai_state('listening')

                # Handle model turn (processing)
                if content.model_turn and not content.output_transcription:
                    self.on_ai_state('processing')

                # Handle audio output
                if content.model_turn and content.model_turn.parts:
                    for part in content.model_turn.parts:
                        if part.inline_data and part.inline_data.mime_type == "audio/pcm":
                            self.on_ai_state('speaking')
                            # Decode audio and add to playback queue
                            audio_data = base64.b64decode(part.inline_data.data)
                            self.audio_output_queue.put(audio_data)

        except Exception as e:
            print(f"[ERROR] Handle response error: {e}")
            import traceback
            traceback.print_exc()


# Global instance
_gemini_session: Optional[GeminiLiveSession] = None


def get_gemini_session(
    api_key: str,
    on_transcription: Optional[Callable] = None,
    on_status: Optional[Callable] = None,
    on_ai_state: Optional[Callable] = None,
    on_highlight_object: Optional[Callable] = None,
) -> GeminiLiveSession:
    """Get or create global Gemini Live session"""
    global _gemini_session
    if _gemini_session is None:
        _gemini_session = GeminiLiveSession(
            api_key=api_key,
            on_transcription=on_transcription,
            on_status=on_status,
            on_ai_state=on_ai_state,
            on_highlight_object=on_highlight_object,
        )
    return _gemini_session
