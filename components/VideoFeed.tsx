
import React, { useEffect } from 'react';
import { cn } from "@/lib/utils";
import { TrackedObject } from '../types';

interface VideoFeedProps {
  mediaStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  trackedObjects?: TrackedObject[];
}

export const VideoFeed: React.FC<VideoFeedProps> = ({ mediaStream, videoRef, trackedObjects = [] }) => {
  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream, videoRef]);

  return (
    <div className="relative w-full h-full">
      <div
        className={cn(
          "relative w-full h-full bg-[rgba(10,12,14,0.72)] rounded-xl overflow-hidden shadow-2xl hud-transition",
          "border border-white/10"
        )}
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover transform scaleX-[-1]"
        />

        {/* Tracked objects overlay */}
        {trackedObjects.map((obj) => (
          <div
            key={obj.tracker_id}
            className={cn(
              "absolute border-2 z-20 flex justify-center items-center box-border pointer-events-none transition-all duration-100",
              obj.status === 'tracking' ? 'border-green-400' : 'border-red-400'
            )}
            style={{
              left: `${obj.bbox.x * 100}%`,
              top: `${obj.bbox.y * 100}%`,
              width: `${obj.bbox.width * 100}%`,
              height: `${obj.bbox.height * 100}%`,
            }}
          >
            <span className={cn(
              "absolute -top-6 left-0 text-black text-xs font-bold px-2 py-1 rounded shadow-md",
              obj.status === 'tracking' ? 'bg-green-400' : 'bg-red-400'
            )}>
              {obj.label} ({Math.round(obj.confidence * 100)}%)
            </span>
          </div>
        ))}

        {/* Enhanced inner border */}
        <div className="pointer-events-none absolute inset-0 ring-2 ring-[rgba(255,255,255,0.12)] rounded-xl"></div>
      </div>
    </div>
  );
};
