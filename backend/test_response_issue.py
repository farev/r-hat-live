"""
Test script to diagnose why Gemini isn't responding
Mimics r_hat_app.py usage
"""

import os
import time
import cv2
from dotenv import load_dotenv
from gemini_live_service_v2 import GeminiLiveSession

# Load environment variables
load_dotenv('../.env.local')


def main():
    print("=" * 60)
    print("TESTING GEMINI RESPONSE ISSUE")
    print("=" * 60)

    # Get API key (using GEMINI_API_KEY like r_hat_app.py does)
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        return

    print(f"✅ API Key loaded: {api_key[:10]}...")

    # Setup callbacks
    def on_transcription(sender, text):
        print(f"\n{'='*60}")
        print(f"💬 TRANSCRIPTION [{sender}]: {text}")
        print(f"{'='*60}\n")

    def on_status(status):
        print(f"📊 STATUS: {status}")

    def on_ai_state(state):
        print(f"🤖 AI STATE: {state}")

    def on_highlight_object(obj):
        print(f"🎯 TOOL CALLED: {obj}")

    # Create session (matching r_hat_app.py)
    print("\n1️⃣ Creating Gemini session...")
    session = GeminiLiveSession(
        api_key=api_key,
        on_transcription=on_transcription,
        on_status=on_status,
        on_ai_state=on_ai_state,
        on_highlight_object=on_highlight_object,
    )

    # Start session
    print("\n2️⃣ Starting session...")
    session.start()
    print("✅ Session started")

    # Wait for connection
    print("\n3️⃣ Waiting 3 seconds for connection...")
    time.sleep(3)

    # Open camera
    print("\n4️⃣ Opening camera...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open camera")
        session.stop()
        return

    print("✅ Camera opened")

    # Test for 30 seconds
    print("\n5️⃣ Running for 30 seconds...")
    print("   - Sending video frames")
    print("   - Sending audio from microphone")
    print("   - Please SPEAK INTO YOUR MICROPHONE")
    print("   - Try saying: 'Hello, can you hear me?'")
    print()

    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < 30:
        ret, frame = cap.read()
        if ret:
            # Send frame every 500ms (2 FPS like r_hat_app.py)
            if frame_count % 15 == 0:  # Assuming 30 FPS camera
                session.send_video_frame(frame)
                print(f"📹 Sent frame {frame_count // 15 + 1}")

            frame_count += 1

        time.sleep(1.0 / 30)  # 30 FPS

    # Cleanup
    print("\n6️⃣ Stopping session...")
    cap.release()
    session.stop()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nIf you didn't see any transcriptions:")
    print("1. Check the debug output above for '[DEBUG] Received response'")
    print("2. Check if audio chunks were sent")
    print("3. Check for any errors")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
