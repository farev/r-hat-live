
import React, { useEffect, useRef } from 'react';
import { Sender, TranscriptionEntry } from '../types';

interface TranscriptionPanelProps {
  transcriptions: TranscriptionEntry[];
}

export const TranscriptionPanel: React.FC<TranscriptionPanelProps> = ({ transcriptions }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            // Smooth scroll to bottom when new messages arrive
            scrollRef.current.scrollTo({
                top: scrollRef.current.scrollHeight,
                behavior: 'smooth'
            });
        }
    }, [transcriptions]);

    const getBubbleClass = (sender: Sender) => {
        switch (sender) {
            case Sender.User:
                return 'self-end bg-blue-600 ring-2 ring-blue-400';
            case Sender.Model:
                return 'self-start bg-purple-600 ring-2 ring-purple-400';
            case Sender.System:
                return 'self-center text-xs italic text-gray-400 bg-gray-800 ring-1 ring-gray-600';
            default:
                return 'self-start bg-gray-700 ring-1 ring-gray-500';
        }
    };

    return (
        <div
            ref={scrollRef}
            className="flex-1 p-6 space-y-4 overflow-y-auto backdrop-blur-sm"
            style={{ scrollBehavior: 'smooth' }}
        >
            {transcriptions.length === 0 ? (
                <div className="flex items-center justify-center h-full text-center">
                    <div className="text-[color:var(--hud-subtle)]">
                        <p className="text-lg font-medium mb-2">Start a conversation</p>
                        <p className="text-sm">Press the mic button to begin chatting with Gemini Vision</p>
                    </div>
                </div>
            ) : (
                transcriptions.map((entry) => (
                    <div key={entry.timestamp} className={`flex ${entry.sender === Sender.User ? 'justify-end' : 'justify-start'}`}>
                        <div className={`px-4 py-3 rounded-lg hud-transition max-w-4xl ${getBubbleClass(entry.sender)}`}>
                            <p className="text-[color:var(--hud-text)]">{entry.text}</p>
                        </div>
                    </div>
                ))
            )}
        </div>
    );
};
