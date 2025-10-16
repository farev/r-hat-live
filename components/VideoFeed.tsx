
import React, { useEffect } from 'react';
import { cn } from "@/lib/utils";
import { BoundingBox } from '../types';

interface VideoFeedProps {
  mediaStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  boundingBoxes?: BoundingBox[];
}

export const VideoFeed: React.FC<VideoFeedProps> = ({ mediaStream, videoRef, boundingBoxes = [] }) => {
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

        {/* Bounding boxes overlay */}
        {boundingBoxes.map((box) => (
          <div
            key={box.id}
            className="absolute border-2 border-yellow-400 z-20 flex justify-center items-center box-border animate-fade-in pointer-events-none"
            style={{
              left: `${box.x * 100}%`,
              top: `${box.y * 100}%`,
              width: `${box.width * 100}%`,
              height: `${box.height * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 bg-yellow-400 text-black text-xs font-bold px-2 py-1 rounded shadow-md">
              {box.label}
            </span>
          </div>
        ))}

        {/* Enhanced inner border */}
        <div className="pointer-events-none absolute inset-0 ring-2 ring-[rgba(255,255,255,0.12)] rounded-xl"></div>
      </div>
    </div>
  );
};
