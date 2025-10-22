# Gemini Live API Prototype

A basic prototype that streams your camera video and microphone audio to Gemini Live API for real-time conversation.

## Prerequisites

- Python 3.9 or higher
- A Gemini API key (get one at https://aistudio.google.com/apikey)
- Working camera and microphone
- **Headphones recommended** to prevent audio feedback

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements_gemini_live.txt
```

**Note for macOS users:** If you have issues installing PyAudio, you may need to install PortAudio first:

```bash
brew install portaudio
pip install pyaudio
```

**Note for Linux users:**

```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

### 2. Set Up API Key

Export your Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY='your-api-key-here'
```

Or add it to your `.env` file (don't commit this!):

```bash
echo "GEMINI_API_KEY=your-api-key-here" >> .env
```

## Usage

Run the prototype:

```bash
python gemini_live_prototype.py
```

### What to Expect

1. **Video capture starts** - Your camera will activate (you should see the camera light turn on)
2. **Microphone starts** - Audio capture begins
3. **Connection established** - The script connects to Gemini Live API
4. **Start talking!** - Speak naturally, and Gemini will respond with audio

### Tips

- 🎧 **Use headphones** to prevent audio feedback loops
- 📹 **Make sure your camera is visible** - Gemini can see what's in front of your camera
- 🗣️ **Speak clearly** - The microphone captures at 16kHz
- 🛑 **Press Ctrl+C** to stop the program

## Example Conversations

Try asking Gemini:
- "What do you see in front of me?"
- "Can you describe what's on my desk?"
- "What color is the wall behind me?"
- "Help me find my red mug"

## Troubleshooting

### Camera Not Opening

```bash
# Test camera access
python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera FAIL'); cap.release()"
```

### Microphone Issues

```bash
# List available audio devices
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

### API Key Error

Make sure your API key is set:

```bash
echo $GEMINI_API_KEY
```

If nothing shows up, set it again:

```bash
export GEMINI_API_KEY='your-api-key-here'
```

### Model Not Available

If you get an error about the model, try changing the MODEL in the script to:
- `models/gemini-2.0-flash-exp`
- `models/gemini-2.0-flash-live-001`

## Session Limits

- **Audio + Video sessions:** Limited to 2 minutes (Gemini API limitation)
- **Audio-only sessions:** Limited to 15 minutes

The script will automatically disconnect after the time limit.

## What's Next?

Once this prototype works, we'll integrate:
1. YOLO object detection
2. CLIP object identification
3. CSRT tracking
4. Function calling for `highlight_object` tool

This will create the unified Python application with real-time object tracking!

## Technical Details

### Video Pipeline
- Captures frames at 30 FPS (camera native)
- Sends to Gemini at 1 FPS (rate-limited)
- Format: JPEG at 70% quality
- Color space: RGB (converted from OpenCV BGR)

### Audio Pipeline
- **Input:** 16kHz, mono, 16-bit PCM (microphone → Gemini)
- **Output:** 24kHz, mono, 16-bit PCM (Gemini → speakers)
- **Chunk size:** 1024 samples

### Async Tasks
The script runs 4 concurrent tasks:
1. `send_video_frames()` - Camera → Gemini (1 FPS)
2. `send_audio()` - Microphone → Gemini (real-time)
3. `receive_audio()` - Gemini → audio buffer
4. `play_audio()` - Audio buffer → speakers

## Resources

- [Gemini Live API Docs](https://ai.google.dev/gemini-api/docs/live)
- [Google Gemini Cookbook](https://github.com/google-gemini/cookbook)
- [Get Started with Live API](https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py)
