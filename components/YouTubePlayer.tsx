import React, { useMemo } from 'react';
import { cn } from "@/lib/utils";
import { YouTubeVideo } from '../types/tools';

interface YouTubePlayerProps {
  video: YouTubeVideo;
  onClose: () => void;
  className?: string;
}

export const YouTubePlayer: React.FC<YouTubePlayerProps> = ({ video, onClose, className }) => {
  const startTime = Math.max(0, Math.floor(video.start_time ?? 0));

  const embedSrc = useMemo(() => {
    const base = `https://www.youtube.com/embed/${encodeURIComponent(video.video_id)}`;
    const params = new URLSearchParams({
      autoplay: '1',
      start: startTime.toString(),
      rel: '0',
      modestbranding: '1',
    });
    return `${base}?${params.toString()}`;
  }, [video.video_id, startTime]);

  return (
    <div
      className={cn(
        "hud-elev rounded-2xl overflow-hidden relative border border-white/10 bg-black/80 backdrop-blur w-full max-w-sm",
        className
      )}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute top-3 right-3 text-white/80 hover:text-white transition-colors z-20"
        aria-label="Close video"
      >
        ×
      </button>

      <div className="aspect-video relative">
        <iframe
          title={video.title}
          src={embedSrc}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          className="w-full h-full"
        />
      </div>

      <div className="p-4 space-y-1">
        <h3 className="text-white text-sm font-semibold leading-snug">{video.title}</h3>
        {video.channel_title && (
          <p className="text-xs text-white/60">from {video.channel_title}</p>
        )}
        <div className="flex justify-between items-center text-xs text-white/60 pt-2">
          <span>Starts at {startTime}s</span>
          <a
            href={`${video.url}&t=${startTime}s`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-300 hover:text-blue-200 transition-colors"
          >
            Open in YouTube
          </a>
        </div>
      </div>
    </div>
  );
};
