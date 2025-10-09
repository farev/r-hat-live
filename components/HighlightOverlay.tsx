import React from 'react';
import { ActiveHighlight } from '../types';

interface HighlightOverlayProps {
  highlights: ActiveHighlight[];
  onDismiss: (id: string) => void;
}

export const HighlightOverlay: React.FC<HighlightOverlayProps> = ({ highlights, onDismiss }) => {
  if (highlights.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none">
      {highlights.map((highlight, index) => (
        <div
          key={highlight.id}
          className="absolute inset-0 animate-fade-in"
          style={{
            zIndex: 10 + index,
          }}
        >
          {/* Annotated image overlay */}
          <img
            src={highlight.annotated_image}
            alt={`Highlight: ${highlight.object_name}`}
            className="w-full h-full object-cover opacity-90"
          />

          {/* Info badge */}
          <div className="absolute top-2 left-2 bg-purple-600/90 text-white px-3 py-1 rounded-full text-xs font-medium pointer-events-auto">
            Highlighted: {highlight.object_name}
          </div>

          {/* Dismiss button */}
          <button
            onClick={() => onDismiss(highlight.id)}
            className="absolute top-2 right-2 bg-red-600/90 hover:bg-red-700 text-white rounded-full w-8 h-8 flex items-center justify-center pointer-events-auto transition-colors"
            aria-label="Dismiss highlight"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};
