
import React, { useEffect, useRef } from 'react';

interface VideoFeedProps {
  mediaStream: MediaStream | null;
  videoRef: React.RefObject<HTMLVideoElement>;
}

export const VideoFeed: React.FC<VideoFeedProps> = ({ mediaStream, videoRef }) => {
  useEffect(() => {
    if (videoRef.current && mediaStream) {
      videoRef.current.srcObject = mediaStream;
    }
  }, [mediaStream, videoRef]);

  return (
    <div className="relative w-full h-full bg-black rounded-lg overflow-hidden shadow-2xl">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-cover transform scaleX-[-1]"
      />
    </div>
  );
};
