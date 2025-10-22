"""
Gemini Live WebSocket Bridge Client (Python)
Connects to the Node.js bridge server to use the TypeScript Gemini implementation
"""

import asyncio
import websockets
import json
import base64
import threading
import queue
from typing import Callable, Optional
import numpy as np
import sounddevice as sd


class GeminiBridgeClient:
    """Client that connects to the Node.js Gemini bridge server"""

    def __init__(
        self,
        api_key: str,
        on_transcription: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_ai_state: Optional[Callable[[str], None]] = None,
        on_highlight_object: Optional[Callable[[str], None]] = None,
        on_audio_output: Optional[Callable[[bytes], None]] = None,
    ):
        self.api_key = api_key
        self.on_transcription = on_transcription or (lambda s, t: None)
        self.on_status = on_status or (lambda s: None)
        self.on_ai_state = on_ai_state or (lambda s: None)
        self.on_highlight_object = on_highlight_object or (lambda o: None)
        self.on_audio_output = on_audio_output or (lambda data: None)

        self.ws = None
        self.running = False
        self.bridge_thread = None
        self.ws_uri = "ws://localhost:8765"

        # Audio handling
        self.input_stream = None
        self.output_stream = None
        self.audio_input_queue = queue.Queue()
        self.audio_output_queue = queue.Queue()
        self.audio_output_thread = None

        # Buffers for transcriptions
        self.current_input_transcription = ""
        self.current_output_transcription = ""

    def start(self):
        """Start connection to bridge server"""
        if self.running:
            return

        self.running = True
        self.on_status("Connecting to Gemini bridge...")

        # Start audio I/O
        self._start_audio_input()
        self._start_audio_output()

        # Start bridge client in separate thread
        self.bridge_thread = threading.Thread(
            target=self._run_bridge_client,
            daemon=False,
            name="GeminiBridgeThread"
        )
        self.bridge_thread.start()

    def stop(self):
        """Stop connection to bridge server"""
        self.running = False

        # Stop audio streams
        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()

        if self.ws:
            asyncio.run(self._send_message('STOP_SESSION', {}))
        self.on_status("Bridge connection stopped")

    async def send_audio(self, audio_bytes: bytes):
        """Send audio chunk to Gemini via bridge"""
        if not self.running or not self.ws:
            return

        # Convert audio bytes to base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Send via WebSocket
        await self._send_message('SEND_AUDIO', {'data': audio_b64})

    def send_video_frame(self, frame: np.ndarray):
        """Send video frame to Gemini via bridge"""
        if not self.running or not self.ws:
            return

        import cv2

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        jpg_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

        # Send via WebSocket
        asyncio.run(self._send_message('SEND_VIDEO', {'data': jpg_b64}))

    def send_tool_response(self, call_id: str, result: str):
        """Send tool response back to Gemini"""
        asyncio.run(self._send_message('TOOL_RESPONSE', {
            'callId': call_id,
            'result': result
        }))

    def _run_bridge_client(self):
        """Run WebSocket client (runs in separate thread)"""
        asyncio.run(self._bridge_client_async())

    async def _bridge_client_async(self):
        """Async WebSocket client"""
        try:
            async with websockets.connect(self.ws_uri) as websocket:
                self.ws = websocket
                print(f"[BRIDGE] Connected to {self.ws_uri}")

                # Start session
                await self._send_message('START_SESSION', {'apiKey': self.api_key})
                print("[BRIDGE] Sent START_SESSION message")

                # Create tasks for sending audio and receiving messages
                send_task = asyncio.create_task(self._send_audio_loop())
                receive_task = asyncio.create_task(self._receive_loop(websocket))

                print("[BRIDGE] Started send and receive tasks")

                # Wait for both tasks
                results = await asyncio.gather(send_task, receive_task, return_exceptions=True)
                print(f"[BRIDGE] Tasks completed with results: {results}")

        except Exception as e:
            print(f"[BRIDGE] Error: {e}")
            import traceback
            traceback.print_exc()
            self.on_status(f"Bridge error: {e}")

    async def _send_audio_loop(self):
        """Continuously send audio from queue to bridge"""
        print("[BRIDGE] Audio send loop started")
        audio_count = 0
        while self.running:
            try:
                audio_chunk = self.audio_input_queue.get_nowait()
                # Send audio to bridge
                await self.send_audio(audio_chunk)
                audio_count += 1
                if audio_count % 50 == 0:
                    print(f"[BRIDGE] Sent {audio_count} audio chunks to bridge")
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"[BRIDGE] Error sending audio: {e}")
                import traceback
                traceback.print_exc()
        print(f"[BRIDGE] Audio send loop exited, sent {audio_count} chunks")

    async def _receive_loop(self, websocket):
        """Receive messages from bridge server"""
        while self.running:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                await self._handle_message(json.loads(message))
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("[BRIDGE] Connection closed")
                break

    async def _send_message(self, msg_type: str, payload: dict):
        """Send message to bridge server"""
        if self.ws:
            try:
                message = json.dumps({'type': msg_type, 'payload': payload})
                await self.ws.send(message)
            except Exception as e:
                print(f"[BRIDGE] Failed to send message: {e}")

    async def _handle_message(self, message: dict):
        """Handle message from bridge server"""
        msg_type = message.get('type')

        if msg_type == 'STATUS':
            status = message.get('status')
            if status == 'connected':
                self.on_status("Connected! You can start talking.")
                self.on_ai_state('listening')

        elif msg_type == 'ERROR':
            error = message.get('error')
            print(f"[BRIDGE] Error from server: {error}")
            self.on_status(f"Error: {error}")

        elif msg_type == 'TRANSCRIPTION':
            sender = message.get('sender')
            text = message.get('text')

            if sender == 'USER':
                self.current_input_transcription += text
            elif sender == 'MODEL':
                self.current_output_transcription += text

        elif msg_type == 'TURN_COMPLETE':
            if self.current_input_transcription.strip():
                self.on_transcription("USER", self.current_input_transcription)
            if self.current_output_transcription.strip():
                self.on_transcription("MODEL", self.current_output_transcription)

            self.current_input_transcription = ""
            self.current_output_transcription = ""

        elif msg_type == 'AI_STATE':
            state = message.get('state')
            self.on_ai_state(state)

        elif msg_type == 'TOOL_CALL':
            tool = message.get('tool')
            args = message.get('args')
            call_id = message.get('callId')

            if tool == 'highlightObject':
                object_name = args.get('object_name')
                try:
                    self.on_highlight_object(object_name)
                    self.send_tool_response(call_id, f"Successfully tracking {object_name}")
                except Exception as e:
                    self.send_tool_response(call_id, f"Error: {str(e)}")

        elif msg_type == 'AUDIO_OUTPUT':
            # Audio data is base64 PCM
            audio_b64 = message.get('data')
            audio_bytes = base64.b64decode(audio_b64)
            self.audio_output_queue.put(audio_bytes)

    def _start_audio_input(self):
        """Start capturing audio from microphone"""
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"[AUDIO] Input error: {status}")
            if self.running:
                # Convert float32 to int16 PCM
                audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                self.audio_input_queue.put(audio_bytes)

        try:
            self.input_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='float32',
                blocksize=4096,
                callback=audio_callback
            )
            self.input_stream.start()
            print("[BRIDGE] Audio input started")
        except Exception as e:
            print(f"[BRIDGE] Failed to start audio input: {e}")

    def _start_audio_output(self):
        """Start audio output stream for playback"""
        try:
            self.output_stream = sd.OutputStream(
                samplerate=24000,
                channels=1,
                dtype='int16',
                blocksize=4096
            )
            self.output_stream.start()

            # Start playback worker thread
            self.audio_output_thread = threading.Thread(
                target=self._audio_output_worker,
                daemon=True
            )
            self.audio_output_thread.start()
            print("[BRIDGE] Audio output started")
        except Exception as e:
            print(f"[BRIDGE] Failed to start audio output: {e}")

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
                print(f"[BRIDGE] Audio playback error: {e}")


# Singleton
_bridge_client: Optional[GeminiBridgeClient] = None


def get_gemini_bridge_client(
    api_key: str,
    on_transcription: Optional[Callable] = None,
    on_status: Optional[Callable] = None,
    on_ai_state: Optional[Callable] = None,
    on_highlight_object: Optional[Callable] = None,
    on_audio_output: Optional[Callable] = None,
) -> GeminiBridgeClient:
    """Get or create global bridge client"""
    global _bridge_client
    if _bridge_client is None:
        _bridge_client = GeminiBridgeClient(
            api_key=api_key,
            on_transcription=on_transcription,
            on_status=on_status,
            on_ai_state=on_ai_state,
            on_highlight_object=on_highlight_object,
            on_audio_output=on_audio_output,
        )
    return _bridge_client
