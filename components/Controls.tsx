
import React from 'react';

interface ControlsProps {
  status: 'IDLE' | 'CONNECTING' | 'ACTIVE' | 'ERROR';
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

export const Controls: React.FC<ControlsProps> = ({ status, onStart, onStop }) => {
  const isIdle = status === 'IDLE' || status === 'ERROR';
  const isConnecting = status === 'CONNECTING';

  return (
    <div className="flex items-center justify-center p-4">
      {isIdle ? (
        <button
          onClick={onStart}
          className="flex items-center justify-center w-20 h-20 bg-green-500 hover:bg-green-600 text-white rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-4 focus:ring-green-400 focus:ring-opacity-50 shadow-lg"
        >
          <MicIcon className="w-8 h-8"/>
        </button>
      ) : (
        <button
          onClick={onStop}
          disabled={isConnecting}
          className="flex items-center justify-center w-20 h-20 bg-red-500 hover:bg-red-600 text-white rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-4 focus:ring-red-400 focus:ring-opacity-50 shadow-lg disabled:bg-gray-500 disabled:cursor-not-allowed"
        >
            {isConnecting ? (
                <div className="w-8 h-8 border-4 border-t-transparent border-white rounded-full animate-spin"></div>
            ) : (
                <StopIcon className="w-8 h-8"/>
            )}
        </button>
      )}
    </div>
  );
};
