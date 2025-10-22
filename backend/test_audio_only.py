"""
Test ONLY audio capture - no Gemini connection
This will help us isolate if the issue is with audio or with Gemini
"""

import sounddevice as sd
import time
import queue

audio_queue = queue.Queue()
chunks_received = [0]

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Status: {status}")
    chunks_received[0] += 1
    if chunks_received[0] == 1:
        print(f"✅ FIRST AUDIO CHUNK RECEIVED!")
    if chunks_received[0] % 10 == 0:
        print(f"Received {chunks_received[0]} audio chunks")
    audio_queue.put(indata.copy())

print("=" * 60)
print("AUDIO CAPTURE TEST")
print("=" * 60)

print("\n1. Listing audio devices:")
print(sd.query_devices())

print("\n2. Default input device:")
print(sd.default.device)

print("\n3. Starting audio capture...")
print("   Sample rate: 16000 Hz")
print("   Channels: 1 (mono)")
print("   Speak into your microphone NOW!")

try:
    with sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype='float32',
        blocksize=4096,
        callback=audio_callback
    ) as stream:
        print(f"   Stream active: {stream.active}")
        print("\n4. Recording for 10 seconds...")
        time.sleep(10)

    print(f"\n5. RESULTS:")
    print(f"   Total audio chunks received: {chunks_received[0]}")
    print(f"   Queue size: {audio_queue.qsize()}")

    if chunks_received[0] == 0:
        print("\n❌ NO AUDIO CAPTURED!")
        print("   This means:")
        print("   - Microphone permission not granted")
        print("   - No microphone available")
        print("   - Microphone blocked by another app")
    else:
        print(f"\n✅ SUCCESS! Audio is being captured properly")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
