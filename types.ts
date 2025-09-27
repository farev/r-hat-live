
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
