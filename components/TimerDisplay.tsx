import React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TimerDisplayProps {
  remainingSeconds: number;
  durationSeconds: number;
  onCancel?: () => void;
}

const formatTimer = (totalSeconds: number): string => {
  const clampedSeconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(clampedSeconds / 3600);
  const minutes = Math.floor((clampedSeconds % 3600) / 60);
  const seconds = clampedSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }

  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export const TimerDisplay: React.FC<TimerDisplayProps> = ({
  remainingSeconds,
  durationSeconds,
  onCancel,
}) => {
  if (remainingSeconds <= 0) {
    return null;
  }

  const progress = Math.max(
    0,
    Math.min(1, remainingSeconds / Math.max(1, durationSeconds)),
  );

  return (
    <div className="relative">
      <div
        className={cn(
          'hud-glass rounded-xl px-4 py-3 border border-white/10 shadow-lg flex items-center gap-4',
          'backdrop-blur-md bg-black/70 pointer-events-auto',
        )}
      >
        <div className="flex flex-col items-center gap-1">
          <span className="text-[10px] uppercase tracking-[0.35em] text-white/60">
            Timer
          </span>
          <span className="text-3xl font-semibold text-white tabular-nums leading-none">
            {formatTimer(remainingSeconds)}
          </span>
        </div>

        {onCancel && (
          <button
            className="ml-2 text-white/60 hover:text-white transition-colors rounded-full p-1 hover:bg-white/10"
            onClick={onCancel}
            aria-label="Cancel timer"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="absolute left-0 bottom-0 h-[3px] w-full bg-white/15 rounded-b-lg overflow-hidden">
        <div
          className="h-full bg-white/60 transition-all duration-500 ease-out"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    </div>
  );
};
