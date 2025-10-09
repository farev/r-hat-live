
import React from 'react';
import { LiquidButton } from '@/components/ui/liquid-glass-button';
import { PulsingAnimation, ListeningIndicator, ProcessingIndicator, SpeakingIndicator } from '@/components/ui/pulsing-animation';
import { AIState } from '../types';

interface ControlsProps {
  status: 'IDLE' | 'CONNECTING' | 'ACTIVE' | 'ERROR';
  aiState: AIState;
  onStart: () => void;
  onStop: () => void;
}

const MicIcon: React.FC<{className?: string}> = ({ className }) => (
  <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3ZM11 5a1 1 0 0 1 2 0v6a1 1 0 0 1-2 0V5Z"></path>
    <path d="M19 10a1 1 0 0 0-1 1v1a6 6 0 0 1-12 0v-1a1 1 0 0 0-2 0v1a8 8 0 0 0 7 7.93V21a1 1 0 0 0 2 0v-1.07A8 8 0 0 0 20 12v-1a1 1 0 0 0-1-1Z"></path>
  </svg>
);

const StopIcon: React.FC<{className?: string}> = ({ className }) => (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c5.523 0 10 4.477 10 10s-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2Zm-1.5 6.046a.5.5 0 0 0-.5.5v6.908a.5.5 0 0 0 .5.5h3a.5.5 0 0 0 .5-.5V8.546a.5.5 0 0 0-.5-.5h-3Z"></path></svg>
);

export const Controls: React.FC<ControlsProps> = ({ status, aiState, onStart, onStop }) => {
  const isIdle = status === 'IDLE' || status === 'ERROR';
  const isConnecting = status === 'CONNECTING';
  const isActive = status === 'ACTIVE';

  const getButtonVariant = () => {
    if (isIdle) return 'green';
    if (aiState === 'listening') return 'default';
    if (aiState === 'processing') return 'default';
    if (aiState === 'speaking') return 'default';
    if (aiState === 'using_tool') return 'default';
    return 'red';
  };

  const renderStateIndicator = () => {
    switch (aiState) {
      case 'listening':
        return <ListeningIndicator className="absolute -top-8" />;
      case 'processing':
        return <ProcessingIndicator className="absolute -top-8" />;
      case 'speaking':
        return <SpeakingIndicator className="absolute -top-8" />;
      case 'using_tool':
        return <ProcessingIndicator className="absolute -top-8" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-2 relative z-20">
      {/* AI State Indicator */}
      {renderStateIndicator()}
      
      {/* Main Control Button */}
      <PulsingAnimation aiState={aiState}>
        {isIdle ? (
          <LiquidButton
            aria-label="Start"
            onClick={onStart}
            variant="green"
            className="w-20 h-20 rounded-full ring-2 ring-emerald-400"
          >
            <MicIcon className="w-8 h-8"/>
          </LiquidButton>
        ) : (
          <LiquidButton
            aria-label="Stop"
            onClick={onStop}
            disabled={isConnecting}
            variant={getButtonVariant()}
            className="w-20 h-20 rounded-full ring-2 ring-red-400"
          >
            {isConnecting ? (
              <div className="w-8 h-8 border-4 border-t-transparent border-white rounded-full animate-spin"></div>
            ) : (
              <StopIcon className="w-8 h-8"/>
            )}
          </LiquidButton>
        )}
      </PulsingAnimation>
      
      {/* State Label */}
      {aiState !== 'idle' && (
        <div className="mt-2 text-xs text-center">
          <span className={`px-2 py-1 rounded-full text-white ${
            aiState === 'listening' ? 'bg-blue-500/80' :
            aiState === 'processing' ? 'bg-yellow-500/80' :
            aiState === 'speaking' ? 'bg-green-500/80' :
            aiState === 'using_tool' ? 'bg-purple-500/80' : ''
          }`}>
            {aiState === 'using_tool' ? 'Using Tool' : aiState.charAt(0).toUpperCase() + aiState.slice(1)}
          </span>
        </div>
      )}
    </div>
  );
};
