
import React, { useEffect, useRef } from 'react';
import { Sender, TranscriptionEntry } from '../types';

interface TranscriptionPanelProps {
  transcriptions: TranscriptionEntry[];
}

const UserIcon = () => (
    <svg className="w-6 h-6 text-blue-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 8a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm0 2c-3.309 0-6 2.691-6 6v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-1c0-3.309-2.691-6-6-6Zm-4 5a4.004 4.004 0 0 1 4-4 4.004 4.004 0 0 1 4 4v.5H8v-.5Z"></path></svg>
);

const ModelIcon = () => (
    <svg className="w-6 h-6 text-purple-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H10V0H8V2H4V4H2V8H0V10H2V14H4V16H8V18H10V20H14V18H16V16H20V14H22V10H24V8H22V4H20V2H16V0H14V2ZM18 12V8H20V6H18V4H14V6H10V4H6V6H4V8H6V12H4V14H6V16H10V14H14V16H18V14H20V12H18ZM16 12H8V8H16V12Z"></path></svg>
);


export const TranscriptionPanel: React.FC<TranscriptionPanelProps> = ({ transcriptions }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [transcriptions]);

    const getBubbleClass = (sender: Sender) => {
        switch (sender) {
            case Sender.User:
                return 'bg-blue-900/50 self-end';
            case Sender.Model:
                return 'bg-purple-900/50 self-start';
            case Sender.System:
                return 'bg-gray-700/80 self-center text-xs italic';
            default:
                return 'bg-gray-800 self-start';
        }
    };

     const getIcon = (sender: Sender) => {
        switch (sender) {
            case Sender.User:
                return <UserIcon />;
            case Sender.Model:
                return <ModelIcon />;
            default:
                return null;
        }
    };

    return (
        <div ref={scrollRef} className="flex-grow p-4 space-y-4 overflow-y-auto bg-gray-800/50 rounded-lg backdrop-blur-sm">
            {transcriptions.map((entry) => (
                <div key={entry.timestamp} className={`flex items-start gap-3 max-w-xl ${entry.sender === Sender.User ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
                    {entry.sender !== Sender.System && (
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center mt-1">
                            {getIcon(entry.sender)}
                        </div>
                    )}
                    <div className={`px-4 py-2 rounded-lg ${getBubbleClass(entry.sender)}`}>
                        <p>{entry.text}</p>
                    </div>
                </div>
            ))}
        </div>
    );
};
