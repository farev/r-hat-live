"""
Basic Gemini Live API Prototype
Streams camera video and microphone audio to Gemini Live API
Based on Google's cookbook example: https://github.com/google-gemini/cookbook
"""

import asyncio
import base64
import os
import sys
from io import BytesIO
from pathlib import Path
import cv2
import numpy as np
import sounddevice as sd
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

# Configuration
MODEL = "models/gemini-2.0-flash-exp"
CONFIG = {
    "response_modalities": ["AUDIO"],
}

# Audio settings
CHANNELS = 1
SEND_SAMPLE_RATE = 16000  # Gemini expects 16kHz input
RECEIVE_SAMPLE_RATE = 24000  # Gemini outputs 24kHz
CHUNK_SIZE = 1024

class GeminiLiveClient:
    def __init__(self):
        self.video_queue = asyncio.Queue()
        self.audio_out_queue = asyncio.Queue()
        self.session = None
        self.audio_input_stream = None
        self.audio_output_stream = None

    async def send_video_frames(self):
        """Capture camera frames and send to Gemini at 1 FPS"""
        print("📹 Starting video capture...")
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("❌ Error: Could not open camera")
            return

        print("✅ Camera opened successfully")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️  Failed to read frame")
                    await asyncio.sleep(1.0)
                    continue

                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Convert to PIL Image
                pil_image = Image.fromarray(rgb_frame)

                # Encode to JPEG
                buffer = BytesIO()
                pil_image.save(buffer, format="JPEG", quality=70)

                # Create video blob dict with mime_type and base64 data
                video_blob = {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(buffer.getvalue()).decode()
                }

                # Send to Gemini
                if self.session:
                    await self.session.send_realtime_input(video=video_blob)
                    print("📸 Sent frame to Gemini")

                # Wait 1 second (1 FPS for Gemini)
                await asyncio.sleep(1.0)

        finally:
            cap.release()
            print("📹 Video capture stopped")

    async def send_audio(self):
        """Capture microphone audio and send to Gemini"""
        print("🎤 Starting audio capture...")

        audio_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time, status):
            """Callback for audio input"""
            if status:
                print(f"⚠️  Audio input status: {status}")
            # Convert float32 to int16 PCM
            audio_data = (indata[:, 0] * 32767).astype(np.int16).tobytes()
            # Use the stored loop reference instead of get_event_loop()
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
        print("✅ Microphone opened successfully")

        try:
            while True:
                audio_data = await audio_queue.get()
                if self.session:
                    # Wrap audio in Blob with mime_type
                    audio_blob = types.Blob(
                        data=audio_data,
                        mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"
                    )
                    await self.session.send_realtime_input(audio=audio_blob)

        finally:
            if self.audio_input_stream:
                self.audio_input_stream.stop()
                self.audio_input_stream.close()
            print("🎤 Audio capture stopped")

    async def receive_audio(self):
        """Receive audio responses from Gemini"""
        print("👂 Listening for Gemini responses...")

        try:
            while True:
                turn = self.session.receive()
                async for response in turn:
                    if response.data:
                        await self.audio_out_queue.put(response.data)
                        continue

                    if response.text:
                        print(f"\n💬 Gemini: {response.text}")

                    # Check for end of turn
                    if response.server_content and response.server_content.turn_complete:
                        print("✓ Turn complete")

        except Exception as e:
            print(f"❌ Error receiving audio: {e}")

    async def play_audio(self):
        """Play audio responses from Gemini"""
        print("🔊 Starting audio playback...")

        # Open output stream
        self.audio_output_stream = sd.OutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16'
        )

        self.audio_output_stream.start()

        try:
            while True:
                audio_data = await self.audio_out_queue.get()
                # Convert bytes to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                # Write to output stream
                await asyncio.to_thread(self.audio_output_stream.write, audio_array)

        finally:
            if self.audio_output_stream:
                self.audio_output_stream.stop()
                self.audio_output_stream.close()
            print("🔊 Audio playback stopped")

    async def run(self):
        """Main async loop"""
        # Check for API key
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ Error: GEMINI_API_KEY environment variable not set")
            print("   Set it with: export GEMINI_API_KEY='your-api-key'")
            return

        print("🚀 Starting Gemini Live API client...")
        print(f"📡 Model: {MODEL}")
        print("=" * 60)

        client = genai.Client(api_key=api_key)

        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            self.session = session
            print("✅ Connected to Gemini Live API")
            print("\n💡 Tip: Use headphones to prevent audio feedback")
            print("💡 Speak naturally - Gemini can see your camera feed")
            print("💡 Press Ctrl+C to stop\n")
            print("=" * 60)

            # Run all tasks concurrently
            try:
                await asyncio.gather(
                    self.send_video_frames(),
                    self.send_audio(),
                    self.receive_audio(),
                    self.play_audio()
                )
            except KeyboardInterrupt:
                print("\n\n👋 Shutting down...")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

def main():
    """Entry point"""
    print("\n" + "=" * 60)
    print("  GEMINI LIVE API - CAMERA + MICROPHONE PROTOTYPE")
    print("=" * 60 + "\n")

    client = GeminiLiveClient()

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
