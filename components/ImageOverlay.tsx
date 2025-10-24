import React from 'react';
import { cn } from "@/lib/utils";
import { DisplayedImage } from '../types/tools';
import { X } from 'lucide-react';

interface ImageOverlayProps {
  images: DisplayedImage[];
  onClose: (id: string) => void;
}

export const ImageOverlay: React.FC<ImageOverlayProps> = ({ images, onClose }) => {
  if (images.length === 0) {
    return null;
  }

  return (
    <>
      {images.map((image, index) => (
        <div
          key={image.id}
          className="absolute top-4 left-4 z-30 max-w-md animate-in fade-in slide-in-from-left duration-300"
          style={{
            // Stack multiple images with slight offset
            transform: `translateY(${index * 20}px) translateX(${index * 20}px)`,
          }}
        >
          <div
            className={cn(
              "bg-black/90 backdrop-blur-md rounded-lg border border-white/20",
              "shadow-2xl overflow-hidden"
            )}
          >
            {/* Header */}
            <div className="flex justify-between items-start p-3 bg-white/5">
              <div className="flex-1 pr-2">
                <p className="text-white font-medium text-sm line-clamp-2">
                  {image.description}
                </p>
                <p className="text-white/50 text-xs mt-1">
                  {image.attribution}
                </p>
              </div>
              <button
                onClick={() => onClose(image.id)}
                className={cn(
                  "text-white/60 hover:text-white transition-colors",
                  "p-1 rounded hover:bg-white/10 flex-shrink-0"
                )}
                aria-label="Close image"
              >
                <X size={18} />
              </button>
            </div>

            {/* Image */}
            <div className="relative">
              <img
                src={`data:image/jpeg;base64,${image.image_base64}`}
                alt={image.description}
                className="w-full h-auto max-h-[60vh] object-contain"
              />
            </div>
          </div>
        </div>
      ))}
    </>
  );
};
