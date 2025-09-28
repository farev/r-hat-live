import React from 'react';
import { cn } from '@/lib/utils';

type GlassCircleButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  color?: 'green' | 'red' | 'neutral';
  size?: number; // diameter in px
};

export function GlassCircleButton({
  color = 'neutral',
  size = 80,
  className,
  children,
  ...props
}: GlassCircleButtonProps) {
  const diameter = `${size}px`;
  const gradientColor =
    color === 'green'
      ? 'bg-gradient-to-b from-emerald-400 to-emerald-700'
      : color === 'red'
      ? 'bg-gradient-to-b from-rose-400 to-rose-700'
      : 'bg-gradient-to-b from-zinc-600 to-zinc-900';

  return (
    <button
      className={cn(
        'relative inline-flex items-center justify-center rounded-full text-white focus:outline-none focus:ring-4 transition-transform duration-200 hover:scale-105',
        gradientColor,
        className
      )}
      style={{ width: diameter, height: diameter }}
      {...props}
    >
      {/* inner glass rim */}
      <span className="pointer-events-none absolute inset-0 rounded-full shadow-[inset_2px_2px_6px_rgba(255,255,255,0.28),inset_-2px_-2px_8px_rgba(0,0,0,0.25)]" />
      {/* subtle outer drop */}
      <span className="pointer-events-none absolute inset-0 rounded-full shadow-[0_12px_26px_rgba(0,0,0,0.35),0_2px_6px_rgba(0,0,0,0.25)]" />
      {/* outer crystal ring */}
      <span className="pointer-events-none absolute inset-0 rounded-full border border-white/25" />
      {/* internal shading for depth */}
      <span className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-b from-white/18 via-transparent to-black/35" />
      {/* specular highlight ellipse */}
      <span
        className="pointer-events-none absolute rounded-full"
        style={{
          top: '-6%',
          left: '-6%',
          right: '35%',
          bottom: '55%',
          background:
            'radial-gradient(120% 100% at 30% 20%, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.28) 35%, rgba(255,255,255,0.05) 60%, rgba(255,255,255,0) 70%)',
        }}
      />
      <span className="relative z-10">{children}</span>
    </button>
  );
}


