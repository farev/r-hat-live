
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { VideoFeed } from './components/VideoFeed';
import { Controls } from './components/Controls';
import { TranscriptionPanel } from './components/TranscriptionPanel';
import { startSession, stopSession, getCurrentFrame } from './services/geminiService';
import { highlightObject } from './services/highlightService';
import { videoTracker } from './services/trackingService';
import { Sender, TranscriptionEntry, AIState, ActiveHighlight } from './types';
import { HighlightResult } from './types/tools';

type Status = 'IDLE' | 'CONNECTING' | 'ACTIVE' | 'ERROR';

export default function App() {
  const [status, setStatus] = useState<Status>('IDLE');
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [transcriptions, setTranscriptions] = useState<TranscriptionEntry[]>([]);
  const [statusMessage, setStatusMessage] = useState('Click the mic to start');
  const [aiState, setAiState] = useState<AIState>('idle');
  const [activeHighlights, setActiveHighlights] = useState<ActiveHighlight[]>([]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trackingCanvasRef = useRef<HTMLCanvasElement>(null);

  const updateStatus = useCallback((message: string, statusOverride?: Status) => {
    setStatusMessage(message);
    if(statusOverride) setStatus(statusOverride);
  }, []);

  const addTranscriptionEntry = useCallback((entry: TranscriptionEntry) => {
    setTranscriptions(prev => [...prev, entry]);
  }, []);

  const handleHighlight = useCallback(async (objectName: string) => {
    console.log('🎯 App: Handling highlight for:', objectName);

    // Add system message about tool usage
    setTranscriptions(prev => [...prev, {
      sender: Sender.System,
      text: `Starting tracking for ${objectName}...`,
      timestamp: Date.now()
    }]);

    try {
      // Capture current frame - pass canvas ref
      const frameData = await getCurrentFrame(canvasRef.current || undefined);
      if (!frameData) {
        throw new Error('Failed to capture current frame');
      }

      console.log('📸 Frame captured, sending to backend for initial detection...');

      // Call backend API to get initial detection
      const result: HighlightResult = await highlightObject(frameData, objectName);

      if (!result.success || !result.masks || result.masks.length === 0) {
        throw new Error(result.error || `No ${objectName} detected in view`);
      }

      console.log(`✅ Backend returned ${result.masks.length} detections`);

      // Get the first detected bounding box
      const initialBox = result.masks[0].box as [number, number, number, number];

      // Add system message about result
      setTranscriptions(prev => [...prev, {
        sender: Sender.System,
        text: `Now tracking ${objectName} in real-time`,
        timestamp: Date.now()
      }]);

      // Start tracking with canvas overlay
      if (trackingCanvasRef.current && videoRef.current) {
        const trackingId = await videoTracker.startTracking(
          objectName,
          initialBox,
          trackingCanvasRef.current,
          videoRef.current
        );

        // Add to active highlights (for UI badge)
        const highlight: ActiveHighlight = {
          id: trackingId,
          object_name: objectName,
          annotated_image: '', // Not used in tracking mode
          timestamp: Date.now()
        };

        setActiveHighlights(prev => [...prev, highlight]);
      }

    } catch (error) {
      console.error('❌ Highlight error:', error);

      setTranscriptions(prev => [...prev, {
        sender: Sender.System,
        text: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: Date.now()
      }]);
    }
  }, []);

  const handleShowBoundingBox = useCallback(async (objectName: string, x1: number, y1: number, x2: number, y2: number) => {
    console.log(`🎯 App: Showing bounding box for ${objectName} at [${x1}, ${y1}, ${x2}, ${y2}]`);

    // Add system message
    setTranscriptions(prev => [...prev, {
      sender: Sender.System,
      text: `Displaying bounding box for ${objectName}`,
      timestamp: Date.now()
    }]);

    try {
      // Start tracking with the Gemini-provided coordinates
      if (trackingCanvasRef.current && videoRef.current) {
        const box: [number, number, number, number] = [x1, y1, x2, y2];

        const trackingId = await videoTracker.startTracking(
          objectName,
          box,
          trackingCanvasRef.current,
          videoRef.current
        );

        // Add to active highlights
        const highlight: ActiveHighlight = {
          id: trackingId,
          object_name: objectName,
          annotated_image: '',
          timestamp: Date.now()
        };

        setActiveHighlights(prev => [...prev, highlight]);
      }
    } catch (error) {
      console.error('❌ Bounding box display error:', error);

      setTranscriptions(prev => [...prev, {
        sender: Sender.System,
        text: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: Date.now()
      }]);
    }
  }, []);

  const removeHighlight = useCallback((id: string) => {
    // Stop tracking
    videoTracker.stopTracking();

    // Remove from active highlights
    setActiveHighlights(prev => prev.filter(h => h.id !== id));
  }, []);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
      }
      stopSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaStream]);

  const handleStart = async () => {
    setStatus('CONNECTING');
    updateStatus('Requesting permissions...');
    setTranscriptions([{
      sender: Sender.System,
      text: "Starting session... Please grant camera and microphone access.",
      timestamp: Date.now()
    }]);

    try {
      console.log('🔍 Starting media device enumeration...');

      // First, enumerate available devices for debugging
      const devices = await navigator.mediaDevices.enumerateDevices();
      console.log('📹 Available media devices:', devices);

      console.log('🎤 Requesting audio permission...');
      let audioStream;
      try {
        // Try different audio constraints for Linux compatibility
        audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000
          }
        });
        console.log('✅ Audio permission granted', audioStream.getAudioTracks());
      } catch (audioError) {
        console.error('❌ Audio permission failed:', audioError);
        // Fallback to basic audio request
        try {
          audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          console.log('✅ Audio permission granted (fallback)', audioStream.getAudioTracks());
        } catch (fallbackError) {
          console.error('❌ Audio fallback failed:', fallbackError);
          throw new Error(`Audio access failed: ${audioError.message}`);
        }
      }

      console.log('📹 Requesting video permission...');
      let videoStream;
      try {
        // Try different video constraints for Linux compatibility
        videoStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            frameRate: { ideal: 30 }
          }
        });
        console.log('✅ Video permission granted', videoStream.getVideoTracks());
      } catch (videoError) {
        console.error('❌ Video permission failed:', videoError);
        // Fallback to basic video request
        try {
          videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
          console.log('✅ Video permission granted (fallback)', videoStream.getVideoTracks());
        } catch (fallbackError) {
          console.error('❌ Video fallback failed:', fallbackError);
          throw new Error(`Video access failed: ${videoError.message}`);
        }
      }

      // Combine the streams
      const combinedStream = new MediaStream([
        ...audioStream.getAudioTracks(),
        ...videoStream.getVideoTracks()
      ]);

      console.log('🔗 Combined stream created:', combinedStream.getTracks());
      setMediaStream(combinedStream);
      updateStatus('Permissions granted. Connecting to Gemini...');

      if (videoRef.current && canvasRef.current) {
        await startSession(
          videoRef.current,
          canvasRef.current,
          addTranscriptionEntry,
          (msg) => updateStatus(msg, 'ACTIVE'),
          setAiState,
          handleHighlight,
          handleShowBoundingBox
        );
      }
    } catch (error) {
      console.error("❌ Failed to get media devices.", error);
      updateStatus(`Permission denied: ${error.message}`, 'ERROR');
       setTranscriptions(prev => [...prev, {
          sender: Sender.System,
          text: `Could not access camera and microphone: ${error.message}. Please check your browser settings and refresh.`,
          timestamp: Date.now()
        }]);
      setStatus('ERROR');
    }
  };

  const handleStop = () => {
    stopSession();
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      setMediaStream(null);
    }
    setStatus('IDLE');
    setAiState('idle');
    updateStatus('Session ended. Click the mic to start again.');
    setTranscriptions(prev => [...prev, {
      sender: Sender.System,
      text: "Session ended.",
      timestamp: Date.now()
    }]);
  };

  return (
    <div className="h-screen flex flex-col font-sans hud-safe">
      {/* Fixed Header */}
      <header className="flex justify-between items-start p-4 flex-shrink-0">
        {/* Empty space - Top Left */}
        <div className="flex-1"></div>

        {/* Title - Top Center */}
        <div
          className="hud-glass rounded-xl p-4 hud-transition relative flex-shrink-0 flex items-center justify-center"
          style={{
            transform: "translateZ(25px) rotateY(-8deg)",
            transformStyle: "preserve-3d",
            transformOrigin: "center center"
          }}
        >
          <div
            style={{
              transform: "translateZ(10px)",
            }}
          >
            <h1 className="hud-title text-2xl font-semibold text-center">R-Hat</h1>
          </div>

          {/* Depth shadow */}
          <div
            style={{
              transform: "translateZ(-5px)",
            }}
            className="absolute inset-0 bg-black/20 rounded-xl blur-sm pointer-events-none"
          />
        </div>

        {/* Video Feed and Controls - Top Right */}
        <div className="flex-1 flex justify-end">
          <div className="flex flex-col gap-4 relative z-10">
            <div className="hud-elev rounded-2xl overflow-hidden relative aspect-video hud-transition w-300">
              <VideoFeed
                mediaStream={mediaStream}
                videoRef={videoRef}
                highlights={activeHighlights}
                onDismissHighlight={removeHighlight}
                trackingCanvasRef={trackingCanvasRef}
              />
              {!mediaStream && status !== 'CONNECTING' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4">
                  <div className="hud-glass rounded-xl p-6">
                    <svg className="w-12 h-12 text-gray-300 mb-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21.531 6.531a.5.5 0 0 0-.812-.39l-1.637.91a13.91 13.91 0 0 0-3.328-2.121.5.5 0 0 0-.495.882 12.91 12.91 0 0 1 2.978 1.954l-1.637.91a.5.5 0 0 0 .27.925l3.5-1a.5.5 0 0 0 .16-.959Zm-10.463 1.05a.5.5 0 0 0 .5-.5V3a.5.5 0 0 0-1 0v4.081a.5.5 0 0 0 .5.5Zm-8.25-3.05a.5.5 0 0 0 .16.96l3.5 1a.5.5 0 0 0 .27-.926l-1.637-.91a12.912 12.912 0 0 1 2.978-1.954.5.5 0 1 0-.495-.882A13.91 13.91 0 0 0 4.253 5.23l-1.637-.91a.5.5 0 0 0-.812.39Zm-.813 9.423a.5.5 0 0 0 .812.39l1.637-.91a13.91 13.91 0 0 0 3.328 2.121.5.5 0 0 0 .495-.882 12.91 12.91 0 0 1-2.978-1.954l1.637-.91a.5.5 0 0 0-.27-.925l-3.5 1a.5.5 0 0 0-.16.959Zm18.995 0a.5.5 0 0 0-.16.96l-3.5 1a.5.5 0 0 0-.27-.926l1.637-.91a12.912 12.912 0 0 1-2.978-1.954.5.5 0 1 0 .495-.882 13.91 13.91 0 0 0 3.328 2.121l1.637.91a.5.5 0 0 0 .812-.39ZM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-7 4.5a.5.5 0 0 0 .5.5H11v4.5a.5.5 0 0 0 1 0V17.5h5.5a.5.5 0 0 0 .5-.5V14H5v3.5Z"></path></svg>
                    <h2 className="text-lg font-medium">Camera is off</h2>
                    <p className="text-sm text-[color:var(--hud-subtle)]">Press the mic button below to start the conversation.</p>
                  </div>
                </div>
              )}
            </div>

            <div>
              <Controls status={status} aiState={aiState} onStart={handleStart} onStop={handleStop} />
            </div>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <div className="flex-1 flex items-end justify-center p-4">
        {/* Chat Panel - Bottom Center */}
        <div className="w-1/2">
          <div className="w-full h-64">
            <div className="bg-black rounded-2xl h-full flex flex-col overflow-hidden">
              <TranscriptionPanel transcriptions={transcriptions} />
            </div>
          </div>
        </div>
      </div>

      <canvas ref={canvasRef} className="hidden"></canvas>
    </div>
  );
}
