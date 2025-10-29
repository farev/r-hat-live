import React from 'react';
import { ChecklistItem } from '../types/tools';

interface ChecklistPanelProps {
  title?: string;
  items: ChecklistItem[];
  onToggle: (id: string) => void;
  onClear?: () => void;
}

export const ChecklistPanel: React.FC<ChecklistPanelProps> = ({ title, items, onToggle, onClear }) => {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="hud-glass bg-black/65 backdrop-blur-sm rounded-2xl p-4 shadow-lg space-y-3 border border-white/10">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-[0.16em] uppercase text-white/80">
          {title ?? 'Checklist'}
        </h2>
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            className="text-xs text-white/50 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded-md px-2 py-1 transition"
          >
            Clear
          </button>
        )}
      </div>

      <ul className="space-y-2 text-sm">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onToggle(item.id)}
              className="w-full flex items-center gap-3 text-left group focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded-xl px-2 py-2 transition-colors duration-150 hover:bg-white/5"
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-lg border transition-colors duration-150 ${
                  item.completed
                    ? 'border-emerald-400 bg-emerald-400/80 shadow-[0_0_12px_rgba(16,185,129,0.45)] text-black'
                    : 'border-white/30 bg-black/30 text-white/70'
                }`}
                aria-hidden="true"
              >
                {item.completed && (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="h-4 w-4"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.2 7.282a1 1 0 0 1-1.424-.005L3.29 9.175a1 1 0 1 1 1.42-1.408l4.257 4.3 6.486-6.567a1 1 0 0 1 1.25-.21z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
              </span>
              <span
                className={`flex-1 leading-tight ${
                  item.completed ? 'text-white/60 line-through' : 'text-white'
                }`}
              >
                {item.label}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
