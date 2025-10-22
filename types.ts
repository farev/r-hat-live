
export enum Sender {
  User = 'USER',
  Model = 'MODEL',
  System = 'SYSTEM',
}

export interface TranscriptionEntry {
  sender: Sender;
  text: string;
  timestamp: number;
}

export type AIState = 'idle' | 'listening' | 'processing' | 'speaking' | 'using_tool';

export interface ActiveHighlight {
  id: string;
  object_name: string;
  annotated_image: string; // base64 encoded
  timestamp: number;
}

export interface BoundingBox {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
}

export interface TrackedObject {
  tracker_id: string;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  label: string;
  confidence: number;
  status: 'tracking' | 'lost';
}
