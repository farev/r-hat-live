
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
