import React from 'react';
import { cn } from '@/lib/utils';
import { AIState } from '../../types';

interface PulsingAnimationProps {
  aiState: AIState;
  className?: string;
  children?: React.ReactNode;
}

export const PulsingAnimation: React.FC<PulsingAnimationProps> = ({
  aiState,
  className,
  children
}) => {
  const getAnimationClasses = () => {
    switch (aiState) {
      case 'listening':
        return 'animate-pulse ring-4 ring-blue-400/50 shadow-lg shadow-blue-500/50';
      case 'processing':
        return 'animate-pulse ring-4 ring-yellow-400/50 shadow-lg shadow-yellow-500/50';
      case 'speaking':
        return 'animate-pulse ring-4 ring-green-400/50 shadow-lg shadow-green-500/50';
      default:
        return '';
    }
  };

  const getGlowEffect = () => {
    switch (aiState) {
      case 'listening':
        return 'before:absolute before:inset-0 before:rounded-full before:bg-blue-500/20 before:animate-ping before:duration-1000';
      case 'processing':
        return 'before:absolute before:inset-0 before:rounded-full before:bg-yellow-500/20 before:animate-ping before:duration-500';
      case 'speaking':
        return 'before:absolute before:inset-0 before:rounded-full before:bg-green-500/20 before:animate-ping before:duration-750';
      default:
        return '';
    }
  };

  return (
    <div className={cn('relative', className)}>
      {/* Outer glow ring for active states */}
      {aiState !== 'idle' && (
        <div className="absolute -inset-2 rounded-full opacity-75">
          <div className={cn(
            'w-full h-full rounded-full',
            getAnimationClasses()
          )} />
        </div>
      )}
      
      {/* Ping effect */}
      {aiState !== 'idle' && (
        <div className={cn(
          'absolute -inset-2 rounded-full',
          getGlowEffect()
        )} />
      )}
      
      {/* Main content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
};

// Additional specialized components for different states
export const ListeningIndicator: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('flex items-center space-x-1', className)}>
    <div className="flex space-x-1">
      <div className="w-1 h-4 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
      <div className="w-1 h-4 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
      <div className="w-1 h-4 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
    </div>
  </div>
);

export const ProcessingIndicator: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('flex items-center', className)}>
    <div className="w-4 h-4 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
  </div>
);

export const SpeakingIndicator: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('flex items-center space-x-1', className)}>
    <div className="flex space-x-1">
      <div className="w-1 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <div className="w-1 h-3 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '100ms' }} />
      <div className="w-1 h-4 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '200ms' }} />
      <div className="w-1 h-3 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      <div className="w-1 h-2 bg-green-500 rounded-full animate-bounce" style={{ animationDelay: '400ms' }} />
    </div>
  </div>
);
