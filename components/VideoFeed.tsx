
import React, { useEffect, useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";
import { HighlightOverlay } from './HighlightOverlay';
import { ActiveHighlight } from '../types';

interface VideoFeedProps {
  mediaStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
  highlights?: ActiveHighlight[];
  onDismissHighlight?: (id: string) => void;
}

export const VideoFeed: React.FC<VideoFeedProps> = ({ mediaStream, videoRef, highlights = [], onDismissHighlight }) => {
  // --- 3D Tilt Animation Logic ---
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springConfig = { damping: 15, stiffness: 150 };
  const springX = useSpring(mouseX, springConfig);
  const springY = useSpring(mouseY, springConfig);

  const rotateX = useTransform(springY, [-0.5, 0.5], ["8deg", "-8deg"]);
  const rotateY = useTransform(springX, [-0.5, 0.5], ["-8deg", "8deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const { width, height, left, top } = rect;
    const mouseXVal = e.clientX - left;
    const mouseYVal = e.clientY - top;
    const xPct = mouseXVal / width - 0.5;
    const yPct = mouseYVal / height - 0.5;
    mouseX.set(xPct);
    mouseY.set(yPct);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream, videoRef]);

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
        perspective: "1000px"
      }}
      className="relative w-full h-full"
    >
      <div
        style={{
          transform: "translateZ(20px)",
          transformStyle: "preserve-3d",
        }}
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

        {/* Highlight Overlay */}
        {onDismissHighlight && (
          <HighlightOverlay highlights={highlights} onDismiss={onDismissHighlight} />
        )}

        {/* Enhanced inner border for 3D glass effect */}
        <div className="pointer-events-none absolute inset-0 ring-2 ring-[rgba(255,255,255,0.12)] rounded-xl"></div>

        {/* Additional depth layers for 3D effect */}
        <div
          style={{ transform: "translateZ(10px)" }}
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-black/20 rounded-xl"
        ></div>
      </div>
    </motion.div>
  );
};
