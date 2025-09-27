
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { VideoFeed } from './components/VideoFeed';
import { Controls } from './components/Controls';
import { TranscriptionPanel } from './components/TranscriptionPanel';
import { startSession, stopSession } from './services/geminiService';
import { Sender, TranscriptionEntry } from './types';

type Status = 'IDLE' | 'CONNECTING' | 'ACTIVE' | 'ERROR';

export default function App() {
  const [status, setStatus] = useState<Status>('IDLE');
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [transcriptions, setTranscriptions] = useState<TranscriptionEntry[]>([]);
  const [statusMessage, setStatusMessage] = useState('Click the mic to start');
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const updateStatus = useCallback((message: string, statusOverride?: Status) => {
    setStatusMessage(message);
    if(statusOverride) setStatus(statusOverride);
  }, []);

  const addTranscriptionEntry = useCallback((entry: TranscriptionEntry) => {
    setTranscriptions(prev => [...prev, entry]);
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
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setMediaStream(stream);
      updateStatus('Permissions granted. Connecting to Gemini...');

      if (videoRef.current && canvasRef.current) {
        await startSession(videoRef.current, canvasRef.current, addTranscriptionEntry, (msg) => updateStatus(msg, 'ACTIVE'));
      }
    } catch (error) {
      console.error("Failed to get media devices.", error);
      updateStatus("Permission denied. Please allow camera and microphone access.", 'ERROR');
       setTranscriptions(prev => [...prev, {
          sender: Sender.System,
          text: "Could not access camera and microphone. Please check your browser settings and refresh.",
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
    updateStatus('Session ended. Click the mic to start again.');
    setTranscriptions(prev => [...prev, {
      sender: Sender.System,
      text: "Session ended.",
      timestamp: Date.now()
    }]);
  };

  return (
    <div className="min-h-screen flex flex-col p-4 bg-gray-900 text-white font-sans">
      <header className="text-center mb-4">
        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-blue-500">
          Gemini Vision Chat
        </h1>
        <p className="text-gray-400">{statusMessage}</p>
      </header>

      <main className="flex-grow flex flex-col md:flex-row gap-4 overflow-hidden">
        <div className="md:w-3/5 w-full h-full flex flex-col gap-4">
           <div className="flex-grow relative">
            <VideoFeed mediaStream={mediaStream} videoRef={videoRef} />
             {!mediaStream && status !== 'CONNECTING' && (
                <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-center p-4 rounded-lg">
                    <svg className="w-16 h-16 text-gray-500 mb-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21.531 6.531a.5.5 0 0 0-.812-.39l-1.637.91a13.91 13.91 0 0 0-3.328-2.121.5.5 0 0 0-.495.882 12.91 12.91 0 0 1 2.978 1.954l-1.637.91a.5.5 0 0 0 .27.925l3.5-1a.5.5 0 0 0 .16-.959Zm-10.463 1.05a.5.5 0 0 0 .5-.5V3a.5.5 0 0 0-1 0v4.081a.5.5 0 0 0 .5.5Zm-8.25-3.05a.5.5 0 0 0 .16.96l3.5 1a.5.5 0 0 0 .27-.926l-1.637-.91a12.912 12.912 0 0 1 2.978-1.954.5.5 0 1 0-.495-.882A13.91 13.91 0 0 0 4.253 5.23l-1.637-.91a.5.5 0 0 0-.812.39Zm-.813 9.423a.5.5 0 0 0 .812.39l1.637-.91a13.91 13.91 0 0 0 3.328 2.121.5.5 0 0 0 .495-.882 12.91 12.91 0 0 1-2.978-1.954l1.637-.91a.5.5 0 0 0-.27-.925l-3.5 1a.5.5 0 0 0-.16.959Zm18.995 0a.5.5 0 0 0-.16.96l-3.5 1a.5.5 0 0 0-.27-.926l1.637-.91a12.912 12.912 0 0 1-2.978-1.954.5.5 0 1 0 .495-.882 13.91 13.91 0 0 0 3.328 2.121l1.637.91a.5.5 0 0 0 .812-.39ZM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-7 4.5a.5.5 0 0 0 .5.5H11v4.5a.5.5 0 0 0 1 0V17.5h5.5a.5.5 0 0 0 .5-.5V14H5v3.5Z"></path></svg>
                    <h2 className="text-xl font-semibold">Camera is off</h2>
                    <p className="text-gray-400">Press the mic button below to start the conversation.</p>
                </div>
            )}
           </div>
           <Controls status={status} onStart={handleStart} onStop={handleStop} />
        </div>
        <div className="md:w-2/5 w-full h-full flex flex-col">
            <TranscriptionPanel transcriptions={transcriptions} />
        </div>
      </main>
      <canvas ref={canvasRef} className="hidden"></canvas>
    </div>
  );
}
