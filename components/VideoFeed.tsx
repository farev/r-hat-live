
import React, { useEffect } from 'react';
import { cn } from "@/lib/utils";
import { HighlightOverlay } from './HighlightOverlay';
import { ActiveHighlight } from '../types';

interface VideoFeedProps {
  mediaStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  highlights?: ActiveHighlight[];
  onDismissHighlight?: (id: string) => void;
  trackingCanvasRef?: React.RefObject<HTMLCanvasElement>;
}

export const VideoFeed: React.FC<VideoFeedProps> = ({ mediaStream, videoRef, highlights = [], onDismissHighlight, trackingCanvasRef }) => {
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

        {/* Canvas overlay for tracking annotations */}
        {trackingCanvasRef && (
          <canvas
            ref={trackingCanvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none transform scaleX-[-1]"
            style={{ zIndex: 5 }}
          />
        )}

        {/* Active tracking badges */}
        {highlights.length > 0 && onDismissHighlight && (
          <div className="absolute top-2 left-2 flex flex-col gap-2 pointer-events-auto" style={{ zIndex: 10 }}>
            {highlights.map((highlight) => (
              <div
                key={highlight.id}
                className="flex items-center gap-2 bg-purple-600/90 text-white px-3 py-1 rounded-full text-xs font-medium"
              >
                <span>Tracking: {highlight.object_name}</span>
                <button
                  onClick={() => onDismissHighlight(highlight.id)}
                  className="hover:bg-white/20 rounded-full w-4 h-4 flex items-center justify-center transition-colors"
                  aria-label="Stop tracking"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Enhanced inner border */}
        <div className="pointer-events-none absolute inset-0 ring-2 ring-[rgba(255,255,255,0.12)] rounded-xl"></div>
      </div>
    </div>
  );
};
