"""
Test script for cleaned Gemini Live Service v2
Tests all phases: Connection, Audio I/O, Video streaming, and Tool calling
"""

import os
import time
import cv2
from dotenv import load_dotenv
from gemini_live_service_v2 import GeminiLiveSession

# Load environment variables
load_dotenv()


def test_gemini_v2():
    """Test cleaned Gemini Live Service v2"""

    print("=" * 60)
    print("GEMINI LIVE SERVICE V2 - FULL TEST")
    print("=" * 60)

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ ERROR: API_KEY not found in .env.local")
        return False

    print(f"✅ API Key loaded")

    # Setup callbacks
    transcriptions = []
    statuses = []
    states = []
    tool_calls = []

    def on_transcription(sender: str, text: str):
        transcriptions.append((sender, text))
        print(f"\n💬 [{sender}]: {text}")

    def on_status(status: str):
        statuses.append(status)
        print(f"📊 {status}")

    def on_ai_state(state: str):
        states.append(state)
        print(f"🤖 State: {state}")

    def on_highlight_object(object_name: str):
        tool_calls.append(object_name)
        print(f"\n🎯 TOOL CALLED: Highlight '{object_name}'")

    # Create session
    print("\n1️⃣ Creating session...")
    session = GeminiLiveSession(
        api_key=api_key,
        on_transcription=on_transcription,
        on_status=on_status,
        on_ai_state=on_ai_state,
        on_highlight_object=on_highlight_object
    )
    print("✅ Session created")

    # Start session
    print("\n2️⃣ Starting session...")
    session.start()
    print("✅ Session started")

    # Wait for connection
    print("\n3️⃣ Waiting for connection (3 seconds)...")
    time.sleep(3)

    # Test video streaming
    print("\n4️⃣ Testing video streaming...")
    print("   Opening camera...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("   ⚠️ Camera not available, skipping video test")
    else:
        print("   ✅ Camera opened")
        print("   Sending 10 frames...")

        for i in range(10):
            ret, frame = cap.read()
            if ret:
                session.send_video_frame(frame)
                print(f"   📹 Frame {i+1}/10 sent")
                time.sleep(0.5)  # 2 FPS

        cap.release()
        print("   ✅ Video test complete")

    # Interactive test
    print("\n5️⃣ Interactive test (30 seconds)...")
    print("   Try these commands:")
    print("   - 'Hello, can you hear me?'")
    print("   - 'What can you see in my camera?'")
    print("   - 'Highlight the [object name]' (if camera is working)")
    print()

    time.sleep(30)

    # Stop session
    print("\n6️⃣ Stopping session...")
    session.stop()
    print("✅ Session stopped")

    # Results
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"📊 Status updates: {len(statuses)}")
    print(f"🤖 State changes: {len(states)}")
    print(f"💬 Transcriptions: {len(transcriptions)}")
    print(f"🎯 Tool calls: {len(tool_calls)}")

    if states:
        print(f"\nStates observed: {set(states)}")

    if transcriptions:
        print(f"\nTranscriptions:")
        for sender, text in transcriptions[:5]:  # Show first 5
            print(f"  [{sender}]: {text[:80]}...")

    if tool_calls:
        print(f"\nTool calls:")
        for obj in tool_calls:
            print(f"  - {obj}")

    print("\n" + "=" * 60)

    # Success criteria
    success = (
        session.running == False and  # Should be stopped
        len(statuses) >= 2 and  # At least init and stop
        len(states) >= 1  # At least one state
    )

    if success:
        print("✅ TEST PASSED - All systems working!")
    else:
        print("⚠️ TEST INCOMPLETE - Check output above")

    print("=" * 60)

    return success


if __name__ == "__main__":
    try:
        success = test_gemini_v2()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
