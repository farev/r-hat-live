"""
Hardware Test Script
Tests camera and microphone access before running the Gemini Live prototype
"""

import sys
from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv('.env.local')

def test_camera():
    """Test camera access"""
    print("\n" + "=" * 60)
    print("  TESTING CAMERA")
    print("=" * 60)

    try:
        import cv2
        print("✅ OpenCV imported successfully")
    except ImportError:
        print("❌ OpenCV not installed. Run: pip install opencv-python")
        return False

    try:
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            print("❌ Could not open camera (index 0)")
            print("   Try checking camera permissions in System Preferences")
            return False

        print("✅ Camera opened successfully")

        # Try to read a frame
        ret, frame = cap.read()
        if not ret:
            print("❌ Could not read frame from camera")
            cap.release()
            return False

        height, width, channels = frame.shape
        print(f"✅ Frame captured: {width}x{height}, {channels} channels")

        cap.release()
        print("✅ Camera test PASSED")
        return True

    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False


def test_microphone():
    """Test microphone access"""
    print("\n" + "=" * 60)
    print("  TESTING MICROPHONE")
    print("=" * 60)

    try:
        import sounddevice as sd
        import numpy as np
        print("✅ sounddevice imported successfully")
    except ImportError:
        print("❌ sounddevice not installed")
        print("\n   Install with: pip install sounddevice")
        return False

    try:
        # List audio devices
        print("\n📋 Available audio devices:")
        devices = sd.query_devices()
        default_input = sd.query_devices(kind='input')
        print(f"   Default input device: {default_input['name']}")

        # Try to record a short chunk
        print("\n🎤 Testing microphone recording...")
        try:
            duration = 0.5  # Half second test
            sample_rate = 16000
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()  # Wait for recording to finish
            print(f"✅ Recorded {len(recording)} samples")
            print("✅ Microphone test PASSED")
            return True

        except Exception as e:
            print(f"❌ Could not record from microphone: {e}")
            return False

    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False


def test_gemini_sdk():
    """Test Gemini SDK installation and API key"""
    print("\n" + "=" * 60)
    print("  TESTING GEMINI SDK")
    print("=" * 60)

    try:
        from google import genai
        print("✅ google-genai imported successfully")
    except ImportError:
        print("❌ google-genai not installed. Run: pip install google-genai")
        return False

    import os
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        print("\n   Set it with:")
        print("   export GEMINI_API_KEY='your-api-key-here'")
        print("\n   Get an API key at: https://aistudio.google.com/apikey")
        return False

    print(f"✅ GEMINI_API_KEY is set (length: {len(api_key)})")

    # Try to initialize client
    try:
        client = genai.Client(api_key=api_key)
        print("✅ Gemini client initialized")
        print("✅ Gemini SDK test PASSED")
        return True
    except Exception as e:
        print(f"❌ Could not initialize Gemini client: {e}")
        return False


def test_dependencies():
    """Test all required dependencies"""
    print("\n" + "=" * 60)
    print("  TESTING DEPENDENCIES")
    print("=" * 60)

    dependencies = [
        ("Pillow", "PIL"),
        ("asyncio", "asyncio"),
    ]

    all_ok = True
    for name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"✅ {name} is installed")
        except ImportError:
            print(f"❌ {name} is not installed. Run: pip install {name.lower()}")
            all_ok = False

    if all_ok:
        print("✅ All dependencies test PASSED")
    return all_ok


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  GEMINI LIVE PROTOTYPE - HARDWARE TEST")
    print("=" * 60)

    results = {
        "Camera": test_camera(),
        "Microphone": test_microphone(),
        "Gemini SDK": test_gemini_sdk(),
        "Dependencies": test_dependencies()
    }

    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s} {status}")

    print("=" * 60)

    if all(results.values()):
        print("\n🎉 All tests passed! You're ready to run the prototype.")
        print("\n   Run: python gemini_live_prototype.py")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above before running the prototype.")
        sys.exit(1)


if __name__ == "__main__":
    main()
