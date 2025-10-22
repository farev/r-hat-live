# R-Hat - AI Vision Chat Assistant

R-Hat is a real-time AI assistant that can see, hear, and interact with you through live video and audio. Built with Google's Gemini 2.5 Flash with native audio preview, R-Hat provides an immersive conversational experience with web search capabilities.

## ✨ Features

- **Real-time Video & Audio**: Live camera feed with continuous audio streaming
- **AI Vision**: Gemini AI can see and analyze your video feed in real-time
- **Voice Conversation**: Natural speech-to-speech interaction with AI
- **Web Search Integration**: AI can search the web for current information
- **Modern UI**: Beautiful glass-morphism interface with 3D effects
- **Cross-platform**: Works on Windows, macOS, and Linux

## 🎯 Use Cases

- **Hands-on Learning**: Get help with projects, coding, or repairs while AI watches
- **Real-time Research**: Ask questions and get current information from the web
- **Visual Problem Solving**: Show the AI what you're working on for contextual help
- **Interactive Tutorials**: Learn new skills with AI guidance
- **Accessibility**: Voice-controlled AI assistance for various tasks

## 🚀 Quick Start

### Prerequisites
- **Node.js** (v18 or higher)
- **Modern browser** with camera/microphone permissions
- **Gemini API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Installation

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd r-hat-live
   npm install
   ```

2. **Set up environment:**
   - Create a `.env.local` file in the root directory
   - Add your Gemini API key:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open your browser:**
   - Navigate to `http://localhost:5173`
   - Grant camera and microphone permissions when prompted
   - Click the microphone button to start your conversation with R-Hat

## 🛠️ Technology Stack

- **Frontend**: React 19, TypeScript, Tailwind CSS
- **AI Model**: Google Gemini 2.5 Flash (native audio preview)
- **Audio Processing**: Web Audio API with real-time PCM streaming
- **Video Processing**: Canvas API for frame capture
- **UI Components**: Custom glass-morphism components with Framer Motion
- **Build Tool**: Vite
- **Styling**: Tailwind CSS with custom HUD theme

## 📱 Browser Compatibility

- ✅ Chrome/Chromium (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Edge

*Note: Requires modern browser with WebRTC and Web Audio API support*

## 🎨 UI Features

- **3D Glass Interface**: Modern glass-morphism design with depth effects
- **Real-time Status Indicators**: Visual feedback for AI states (listening, processing, speaking)
- **Responsive Layout**: Optimized for desktop and tablet viewing
- **Live Video Feed**: Picture-in-picture style video display
- **Chat Transcription**: Real-time display of conversation history

## 🔧 Development

### Project Structure
```
r-hat-live/
├── components/           # React components
│   ├── ui/              # Reusable UI components
│   ├── VideoFeed.tsx    # Camera feed component
│   ├── Controls.tsx     # Audio controls
│   └── TranscriptionPanel.tsx
├── services/            # API and service layers
│   └── geminiService.ts # Gemini AI integration
├── utils/               # Utility functions
│   └── audioUtils.ts    # Audio processing utilities
└── types.ts             # TypeScript type definitions
```

### Build Commands
```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run preview  # Preview production build
```

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues, feature requests, or pull requests.

## 📄 License

This project is licensed under the MIT License.

---

**View the original AI Studio app**: https://ai.studio/apps/drive/1gMeIChhxCs8b9_Ades6puTvUHXwWSIjs
