"""
Test audio capture and SAVE to file for verification
"""

import sounddevice as sd
import numpy as np
import wave
import time

print("=" * 60)
print("AUDIO CAPTURE + SAVE TEST")
print("=" * 60)

SAMPLE_RATE = 16000
DURATION = 5  # seconds
CHANNELS = 1

print(f"\n1. Recording {DURATION} seconds of audio...")
print("   🎤 SPEAK INTO YOUR MICROPHONE NOW!")
print("   Say something like: 'Hello, this is a test recording'")
print()

# Record audio
audio_data = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    dtype='float32'
)

# Show progress
for i in range(DURATION):
    time.sleep(1)
    print(f"   Recording... {i+1}/{DURATION} seconds")

sd.wait()  # Wait for recording to finish

print("\n2. Recording complete!")
print(f"   Audio shape: {audio_data.shape}")
print(f"   Audio min: {audio_data.min():.4f}")
print(f"   Audio max: {audio_data.max():.4f}")
print(f"   Audio mean: {audio_data.mean():.4f}")

# Check if audio has content (not just silence)
audio_level = np.abs(audio_data).mean()
print(f"   Audio level: {audio_level:.4f}")

if audio_level < 0.001:
    print("\n⚠️  WARNING: Audio level is very low!")
    print("   This might be silence. Try speaking louder.")
else:
    print(f"\n✅ Audio has content (level: {audio_level:.4f})")

# Convert to int16 for WAV file
audio_int16 = (audio_data * 32767).astype(np.int16)

# Save as WAV file
output_file = "test_recording.wav"
print(f"\n3. Saving to {output_file}...")

with wave.open(output_file, 'wb') as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio_int16.tobytes())

print(f"✅ Saved to {output_file}")
print(f"\n4. You can now:")
print(f"   - Play it: afplay {output_file}")
print(f"   - Or open it in any audio player")
print(f"   - Verify you can hear your voice")

print("\n" + "=" * 60)
print("To play the recording now, run:")
print(f"  afplay {output_file}")
print("=" * 60)
