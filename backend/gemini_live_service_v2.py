"""
Gemini Live API Service - Python Implementation
Handles real-time audio/video streaming with Gemini Live API
"""

import asyncio
import base64
import queue
import threading
from typing import Callable, Optional
from google import genai
from google.genai import types
import sounddevice as sd
import numpy as np
import cv2

# Audio/Video configuration (matching TypeScript implementation)
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
FRAME_RATE = 2  # frames per second
JPEG_QUALITY = 70  # 0-100 scale
CHUNK_SIZE = 4096
CHANNELS = 1  # mono


class GeminiLiveSession:
    """Manages Gemini Live API session with audio/video streaming"""

    def __init__(
        self,
        api_key: str,
        on_transcription: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_ai_state: Optional[Callable[[str], None]] = None,
        on_highlight_object: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize Gemini Live session

        Args:
            api_key: Google AI API key
            on_transcription: Callback(sender, text) for transcription updates
            on_status: Callback(status) for status messages
            on_ai_state: Callback(state) for AI state changes
            on_highlight_object: Callback(object_name) when tool is called
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

        # Thread-safe queues
        self.audio_input_queue = queue.Queue()
        self.video_frame_queue = queue.Queue(maxsize=2)
        self.audio_output_queue = queue.Queue()

        # Worker threads
        self.audio_output_thread = None
        self.gemini_thread = None

        # Transcription buffers
        self.current_input_transcription = ""
        self.current_output_transcription = ""

    def start(self):
        """Start the Gemini Live session"""
        if self.running:
            return

        self.running = True
        self.on_status("Initializing Gemini...")

        # Start audio I/O
        self._start_audio_input()
        self._start_audio_output()

        # Start Gemini session in separate thread
        self.gemini_thread = threading.Thread(
            target=self._run_gemini_session,
            daemon=False,  # Changed from True - let thread complete properly
            name="GeminiLiveThread"
        )
        self.gemini_thread.start()
        print(f"[DEBUG] Gemini thread started: {self.gemini_thread.name}")

        self.on_status("Connected! You can start talking.")
        self.on_ai_state('listening')

    def stop(self):
        """Stop the Gemini Live session"""
        import traceback
        print("[DEBUG] stop() called! Traceback:")
        traceback.print_stack()
        self.running = False

        # Stop audio streams
        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()

        self.on_status("Session stopped")

    def send_video_frame(self, frame: np.ndarray):
        """
        Send a video frame to Gemini (non-blocking, drops if queue full)

        Args:
            frame: OpenCV image (BGR format)
        """
        if self.running:
            try:
                self.video_frame_queue.put_nowait(frame.copy())
            except queue.Full:
                pass  # Drop frame if queue is full

    # --- Private Methods ---

    def _start_audio_input(self):
        """Start capturing audio from microphone"""
        audio_chunks_captured = [0]  # Use list for closure

        def audio_callback(indata, frames, time, status):
            if status:
                print(f"[AUDIO] Input error: {status}")

            # DEBUG: Check if callback is called at all
            audio_chunks_captured[0] += 1
            if audio_chunks_captured[0] == 1:
                print(f"[DEBUG] Audio callback called! self.running={self.running}")

            if self.running:
                # Convert float32 to int16 PCM
                audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                self.audio_input_queue.put(audio_int16.tobytes())
                if audio_chunks_captured[0] == 1:
                    print(f"[DEBUG] First audio chunk captured and queued!")
                if audio_chunks_captured[0] % 100 == 0:
                    print(f"[DEBUG] Captured {audio_chunks_captured[0]} audio chunks")

        try:
            self.input_stream = sd.InputStream(
                samplerate=INPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype='float32',
                blocksize=CHUNK_SIZE,
                callback=audio_callback
            )
            self.input_stream.start()
            print(f"[DEBUG] Audio input stream started (active: {self.input_stream.active})")
        except Exception as e:
            print(f"Failed to start audio input: {e}")
            self.on_status(f"Microphone error: {e}")

    def _start_audio_output(self):
        """Start audio output stream for playback"""
        try:
            self.output_stream = sd.OutputStream(
                samplerate=OUTPUT_SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=CHUNK_SIZE
            )
            self.output_stream.start()

            # Start playback worker thread
            self.audio_output_thread = threading.Thread(
                target=self._audio_output_worker,
                daemon=True
            )
            self.audio_output_thread.start()
        except Exception as e:
            print(f"Failed to start audio output: {e}")

    def _audio_output_worker(self):
        """Worker thread for playing audio output"""
        while self.running:
            try:
                audio_chunk = self.audio_output_queue.get(timeout=0.1)
                if audio_chunk and self.output_stream:
                    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                    self.output_stream.write(audio_array)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Audio playback error: {e}")

    def _run_gemini_session(self):
        """Run Gemini Live session (runs in separate thread)"""
        print("[DEBUG] Gemini thread started, about to run async session")
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._gemini_session_async())
            finally:
                loop.close()
        except Exception as e:
            print(f"[ERROR] Gemini thread error: {e}")
            import traceback
            traceback.print_exc()

    async def _gemini_session_async(self):
        """Async Gemini Live session"""
        try:
            # Initialize client
            self.client = genai.Client(api_key=self.api_key)

            # Define highlightObject tool
            highlight_tool = {
                "function_declarations": [{
                    "name": "highlightObject",
                    "description": "Tracks and highlights a specific object in the user's camera view using computer vision.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_name": {
                                "type": "string",
                                "description": "Name/description of object to track (e.g., 'red drill', 'capacitor')",
                            }
                        },
                        "required": ["object_name"],
                    },
                }]
            }

            # Configure session
            config = {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": "Zephyr"}
                    }
                },
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "tools": [highlight_tool],
                "system_instruction": (
                    "You are a friendly and helpful AI assistant that can see and hear. "
                    "Respond to the user based on what you perceive from their video and audio. "
                    "Keep your responses concise and conversational. "
                    "When the user asks you to highlight, track, or show something in their camera view, "
                    "use the `highlightObject` tool with a clear description of the object."
                ),
            }

            # Connect to Gemini Live API
            print("[DEBUG] About to connect to Gemini Live API...")
            async with self.client.aio.live.connect(
                model="gemini-2.5-flash-native-audio-preview-09-2025",
                config=config,
            ) as session:
                self.session = session
                print("[DEBUG] Connected to Gemini Live API, session created")

                # Start concurrent tasks for send/receive
                results = await asyncio.gather(
                    self._send_audio_loop(session),
                    self._send_video_loop(session),
                    self._receive_loop(session),
                    return_exceptions=True  # Don't cancel all if one fails
                )

                # Check for exceptions
                print(f"[DEBUG] asyncio.gather() completed, checking results...")
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        task_names = ["audio_send", "video_send", "receive"]
                        print(f"[ERROR] Task {task_names[i]} failed: {result}")
                        import traceback
                        traceback.print_exception(type(result), result, result.__traceback__)

            print("[DEBUG] Exiting async with block (session closing)")

        except Exception as e:
            print(f"[ERROR] Gemini session error: {e}")
            import traceback
            traceback.print_exc()
            self.on_status(f"Error: {e}")

        print("[DEBUG] _gemini_session_async() completed")

    async def _send_audio_loop(self, session):
        """Send audio data to Gemini"""
        print(f"[DEBUG] Audio send loop started, self.running={self.running}")
        audio_count = 0
        iterations = 0

        while self.running:
            iterations += 1
            if iterations == 1:
                print(f"[DEBUG] First iteration of send loop")
            if iterations == 2:
                print(f"[DEBUG] Second iteration of send loop")
            if iterations % 500 == 0:
                print(f"[DEBUG] Send loop iteration {iterations}, sent {audio_count} chunks")

            # Try to get audio chunk without blocking
            try:
                audio_chunk = self.audio_input_queue.get_nowait()
            except queue.Empty:
                # No audio available, sleep briefly and continue
                await asyncio.sleep(0.01)
                continue

            # We have audio, send it
            try:
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=audio_chunk,
                        mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}"
                    )
                )
                audio_count += 1
                if audio_count == 1:
                    print(f"[DEBUG] First audio chunk SENT to Gemini!")
                if audio_count % 50 == 0:
                    print(f"[DEBUG] Sent {audio_count} audio chunks to Gemini")
            except Exception as e:
                print(f"[ERROR] Failed to send audio chunk: {e}")
                import traceback
                traceback.print_exc()

        print(f"[DEBUG] Audio send loop exited. Sent {audio_count} total chunks, iterations={iterations}")

    async def _send_video_loop(self, session):
        """Send video frames to Gemini"""
        while self.running:
            try:
                frame = self.video_frame_queue.get(timeout=1.0 / FRAME_RATE)

                # Encode as JPEG
                _, buffer = cv2.imencode(
                    '.jpg',
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )

                # Send to Gemini
                await session.send_realtime_input(
                    video=types.Blob(
                        data=buffer.tobytes(),
                        mime_type="image/jpeg"
                    )
                )
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Send video error: {e}")
                break

    async def _receive_loop(self, session):
        """Receive and process messages from Gemini"""
        print("[DEBUG] Receive loop started")
        try:
            async for response in session.receive():
                print(f"[DEBUG] Received response type: {type(response)}")
                await self._handle_response(response, session)
        except Exception as e:
            print(f"Receive loop error: {e}")
            import traceback
            traceback.print_exc()

    async def _handle_response(self, response, session):
        """Handle a response from Gemini"""
        try:
            print(f"[DEBUG] Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")

            # Handle tool calls
            if hasattr(response, 'tool_call') and response.tool_call:
                self.on_ai_state('using_tool')

                for fc in response.tool_call.function_calls:
                    if fc.name == "highlightObject":
                        object_name = fc.args.get("object_name", "")

                        try:
                            # Execute tool callback
                            self.on_highlight_object(object_name)

                            # Send success response
                            await session.send_tool_response(
                                function_responses=types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": f"Successfully tracking {object_name}"}
                                )
                            )
                        except Exception as e:
                            # Send error response
                            await session.send_tool_response(
                                function_responses=types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": f"Error: {str(e)}"}
                                )
                            )

                await asyncio.sleep(0.5)
                self.on_ai_state('listening')

            # Handle server content
            if hasattr(response, 'server_content') and response.server_content:
                content = response.server_content
                print(f"[DEBUG] Server content received - has output_transcription: {hasattr(content, 'output_transcription')}, has input_transcription: {hasattr(content, 'input_transcription')}, has model_turn: {hasattr(content, 'model_turn')}")

                # Handle transcriptions
                if content.output_transcription:
                    print(f"[DEBUG] Output transcription: {content.output_transcription.text}")
                    self.current_output_transcription += content.output_transcription.text
                    self.on_ai_state('speaking')

                if content.input_transcription:
                    print(f"[DEBUG] Input transcription: {content.input_transcription.text}")
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

                # Handle model turn (processing state)
                if content.model_turn and not content.output_transcription:
                    self.on_ai_state('processing')

                # Handle audio output
                if content.model_turn and content.model_turn.parts:
                    for part in content.model_turn.parts:
                        if (part.inline_data and
                            part.inline_data.mime_type == "audio/pcm"):
                            self.on_ai_state('speaking')
                            # Decode and queue audio
                            audio_data = base64.b64decode(part.inline_data.data)
                            self.audio_output_queue.put(audio_data)

        except Exception as e:
            print(f"Handle response error: {e}")


# Singleton pattern for session management
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
