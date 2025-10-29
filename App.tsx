import React, { useState, useRef, useCallback, useEffect } from 'react';
import { VideoFeed } from './components/VideoFeed';
import { Controls } from './components/Controls';
import { TranscriptionPanel } from './components/TranscriptionPanel';
import { ImageOverlay } from './components/ImageOverlay';
import { YouTubePlayer } from './components/YouTubePlayer';
import { startSession, stopSession } from './services/geminiService';
import { Sender, TranscriptionEntry, AIState, TrackedObject } from './types';
import { DisplayedImage, YouTubeVideo } from './types/tools';
import { highlightObject, updateTrackers, clearAllTrackers, removeTracker, canvasToBase64 } from './services/trackingService';
import { fetchImage } from './services/imageService';

type Status = 'IDLE' | 'CONNECTING' | 'ACTIVE' | 'ERROR';

export default function App() {
  const [status, setStatus] = useState<Status>('IDLE');
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [transcriptions, setTranscriptions] = useState<TranscriptionEntry[]>([]);
  const [statusMessage, setStatusMessage] = useState('Click the mic to start');
  const [aiState, setAiState] = useState<AIState>('idle');
  const [trackedObjects, setTrackedObjects] = useState<TrackedObject[]>([]);
  const [displayedImages, setDisplayedImages] = useState<DisplayedImage[]>([]);
  const [currentVideo, setCurrentVideo] = useState<YouTubeVideo | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trackingIntervalRef = useRef<number | null>(null);

  const updateStatus = useCallback((message: string, statusOverride?: Status) => {
    setStatusMessage(message);
    if(statusOverride) setStatus(statusOverride);
  }, []);

  const addTranscriptionEntry = useCallback((entry: TranscriptionEntry) => {
    setTranscriptions(prev => [...prev, entry]);
  }, []);

  const startTrackingLoop = useCallback(() => {
    if (trackingIntervalRef.current) return;

    console.log('[TRACKING] Starting tracking loop at 10 FPS');

    trackingIntervalRef.current = window.setInterval(async () => {
      if (!canvasRef.current || !videoRef.current) {
        return;
      }

      try {
        // Capture current frame
        const canvas = canvasRef.current;
        const video = videoRef.current;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight);
        const imageBase64 = canvasToBase64(canvas);

        // Update all trackers (use functional update to get latest state)
        setTrackedObjects(prev => {
          if (prev.length === 0) return prev;

          // Get current tracker IDs
          const trackerIds = prev.map(obj => obj.tracker_id);

          // Call update API
          updateTrackers(imageBase64, trackerIds)
            .then(updates => {
              console.log('[TRACKING] Received updates for', Object.keys(updates).length, 'trackers');

              // Update state with new positions
              setTrackedObjects(current =>
                current.map(obj => {
                  const update = updates[obj.tracker_id];
                  if (update) {
                    console.log(`[TRACKING] Updated ${obj.tracker_id}: bbox=${JSON.stringify(update.bbox)}, status=${update.status}`);
                    return {
                      ...obj,
                      bbox: update.bbox,
                      confidence: update.confidence,
                      status: update.status,
                    };
                  }
                  return obj;
                }).filter(obj => obj.status === 'tracking') // Remove lost objects
              );
            })
            .catch(error => {
              console.error('[TRACKING] Update error:', error);
            });

          return prev; // Return unchanged for this update
        });
      } catch (error) {
        console.error('[TRACKING] Tracking loop error:', error);
      }
    }, 50); // Update at ~20 FPS (increased from 100ms/10fps to 50ms/20fps)
  }, []); // Empty deps - only create once

  const handleHighlightObject = useCallback(async (objectName: string, trackingDurationSeconds?: number) => {
    if (!canvasRef.current || !videoRef.current) {
      throw new Error('Video or canvas not ready');
    }

    // Capture current frame
    const canvas = canvasRef.current;
    const video = videoRef.current;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas context not available');

    ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight);
    const imageBase64 = canvasToBase64(canvas);

    // Call backend to detect and track object
    const response = await highlightObject(imageBase64, objectName);
    const trackerId = response.tracker_id;

    // Add new tracked object to state
    const newTrackedObject: TrackedObject = {
      tracker_id: trackerId,
      bbox: response.bbox,
      label: response.label,
      confidence: response.confidence,
      status: 'tracking',
    };

    setTrackedObjects(prev => [...prev, newTrackedObject]);

    // Schedule tracker removal if a duration is provided
    if (trackingDurationSeconds && trackingDurationSeconds > 0) {
      const durationMs = Math.round(trackingDurationSeconds * 1000);
      window.setTimeout(async () => {
        try {
          await removeTracker(trackerId);
        } catch (error) {
          console.error(`[TRACKING] Failed to remove tracker ${trackerId}:`, error);
        } finally {
          setTrackedObjects(current => current.filter(obj => obj.tracker_id !== trackerId));
        }
      }, durationMs);
    }

    // Start tracking loop if not already running
    if (!trackingIntervalRef.current) {
      startTrackingLoop();
    }
  }, [startTrackingLoop]);

  const handleDisplayImage = useCallback(async (query: string) => {
    try {
      const imageData = await fetchImage(query);

      const newImage: DisplayedImage = {
        id: `img-${Date.now()}`,
        ...imageData,
      };

      setDisplayedImages(prev => [...prev, newImage]);
    } catch (error) {
      console.error('Display image error:', error);
      throw error;
    }
  }, []);

  const handlePlayYouTubeVideo = useCallback((video: YouTubeVideo) => {
    const safeStart = Number.isFinite(video.start_time) && video.start_time >= 0
      ? Math.floor(video.start_time)
      : 0;

    setCurrentVideo({
      ...video,
      start_time: safeStart,
    });
  }, []);

  const handleClearVideo = useCallback(() => {
    setCurrentVideo(null);
  }, []);

  useEffect(() => {
    // Stop tracking loop if no objects
    if (trackedObjects.length === 0 && trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current);
      trackingIntervalRef.current = null;
    }
  }, [trackedObjects]);

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
          handleHighlightObject,
          handleDisplayImage,
          handlePlayYouTubeVideo
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

  const handleStop = async () => {
    stopSession();
    handleClearVideo();

    // Stop tracking loop
    if (trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current);
      trackingIntervalRef.current = null;
    }

    // Clear all trackers from backend
    try {
      await clearAllTrackers();
    } catch (error) {
      console.error('Failed to clear trackers:', error);
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      setMediaStream(null);
    }

    setStatus('IDLE');
    setAiState('idle');
    setTrackedObjects([]);
    setDisplayedImages([]);
    updateStatus('Session ended. Click the mic to start again.');
    setTranscriptions(prev => [...prev, {
      sender: Sender.System,
      text: "Session ended.",
      timestamp: Date.now()
    }]);
  };

  return (
    <div className="h-screen flex flex-col font-sans hud-safe relative">
      {/* Image Overlay */}
      <ImageOverlay
        images={displayedImages}
        onClose={(id) => setDisplayedImages(prev => prev.filter(img => img.id !== id))}
      />

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
                trackedObjects={trackedObjects}
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

      {currentVideo && (
        <div className="fixed bottom-6 right-6 w-72 z-40">
          <YouTubePlayer video={currentVideo} onClose={handleClearVideo} />
        </div>
      )}
    </div>
  );
}
