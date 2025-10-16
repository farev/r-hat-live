// FIX: `LiveSession` is not an exported member of `@google/genai`.
import { GoogleGenAI, LiveServerMessage, Modality, FunctionDeclaration, Type } from "@google/genai";
import { decode, decodeAudioData, createPcmBlob, blobToBase64 } from '../utils/audioUtils';
import { Sender, TranscriptionEntry, BoundingBox, AIState } from '../types';

const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;
const FRAME_RATE = 2; // Send 2 frames per second
const JPEG_QUALITY = 0.7;

// FIX: Change type to `any` because `LiveSession` is not exported.
let session: any | null = null;
let sessionPromise: any | null = null;

let inputAudioContext: AudioContext | null = null;
let outputAudioContext: AudioContext | null = null;
let scriptProcessor: ScriptProcessorNode | null = null;
let mediaStreamSource: MediaStreamAudioSourceNode | null = null;
let frameInterval: number | null = null;
let nextStartTime = 0;
const sources = new Set<AudioBufferSourceNode>();

const showBoundingBoxFunctionDeclaration: FunctionDeclaration = {
  name: 'showBoundingBox',
  description: 'Draws a bounding box around a specified object in the user\'s camera view.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      x: {
        type: Type.NUMBER,
        description: 'The normalized horizontal coordinate (from 0.0 to 1.0) of the top-left corner of the box, relative to the video width.',
      },
      y: {
        type: Type.NUMBER,
        description: 'The normalized vertical coordinate (from 0.0 to 1.0) of the top-left corner of the box, relative to the video height.',
      },
      width: {
        type: Type.NUMBER,
        description: 'The normalized width (from 0.0 to 1.0) of the box, relative to the video width.',
      },
      height: {
        type: Type.NUMBER,
        description: 'The normalized height (from 0.0 to 1.0) of the box, relative to the video height.',
      },
      label: {
        type: Type.STRING,
        description: 'A brief text label for the object inside the box.',
      },
    },
    required: ['x', 'y', 'width', 'height', 'label'],
  },
};


export async function startSession(
    videoElement: HTMLVideoElement,
    canvasElement: HTMLCanvasElement,
    onTranscriptionUpdate: (entry: TranscriptionEntry) => void,
    onStatusUpdate: (status: string) => void,
    onAIStateUpdate: (state: AIState) => void,
    onShowBoundingBox: (box: Omit<BoundingBox, 'id'>) => void,
): Promise<void> {
    onStatusUpdate("Initializing Gemini...");
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });

    let currentInputTranscription = '';
    let currentOutputTranscription = '';

    sessionPromise = ai.live.connect({
        model: 'gemini-2.5-flash-native-audio-preview-09-2025',
        callbacks: {
            onopen: async () => {
                onStatusUpdate("Connected! You can start talking.");
                onAIStateUpdate('listening');
                try {
                    const stream = videoElement.srcObject as MediaStream;
                    if (!stream) {
                        throw new Error('No media stream found on video element');
                    }

                    // FIX: Cast `window` to `any` to access `webkitAudioContext` for older browser compatibility.
                    inputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: INPUT_SAMPLE_RATE });
                    // FIX: Cast `window` to `any` to access `webkitAudioContext` for older browser compatibility.
                    outputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: OUTPUT_SAMPLE_RATE });

                    // Audio input processing
                    mediaStreamSource = inputAudioContext.createMediaStreamSource(stream);
                    scriptProcessor = inputAudioContext.createScriptProcessor(4096, 1, 1);

                    scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
                        const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);
                        const pcmBlob = createPcmBlob(inputData);
                        if (sessionPromise) {
                            sessionPromise.then((s) => s.sendRealtimeInput({ media: pcmBlob }));
                        }
                    };

                    mediaStreamSource.connect(scriptProcessor);
                    scriptProcessor.connect(inputAudioContext.destination);

                    // Video frame processing
                    const ctx = canvasElement.getContext('2d');
                    if (!ctx) return;
                    frameInterval = window.setInterval(() => {
                        canvasElement.width = videoElement.videoWidth;
                        canvasElement.height = videoElement.videoHeight;
                        ctx.drawImage(videoElement, 0, 0, videoElement.videoWidth, videoElement.videoHeight);
                        canvasElement.toBlob(
                            async (blob) => {
                                if (blob && sessionPromise) {
                                    const base64Data = await blobToBase64(blob);
                                    sessionPromise.then((s) => {
                                        s.sendRealtimeInput({ media: { data: base64Data, mimeType: 'image/jpeg' } });
                                    });
                                }
                            },
                            'image/jpeg',
                            JPEG_QUALITY,
                        );
                    }, 1000 / FRAME_RATE);

                } catch (error) {
                    console.error("Media device error:", error);
                    onStatusUpdate("Error accessing media devices. Please check permissions.");
                }
            },
            onmessage: async (message: LiveServerMessage) => {
                if (message.toolCall) {
                    onAIStateUpdate('using_tool');
                    for (const fc of message.toolCall.functionCalls) {
                        if (fc.name === 'showBoundingBox') {
                            const { x, y, width, height, label } = fc.args as { x: number; y: number; width: number; height: number; label: string };

                            // Basic validation for coordinates
                            if (x >= 0 && x <= 1 && y >= 0 && y <= 1 && width > 0 && (x + width) <= 1 && height > 0 && (y + height) <= 1) {
                                onShowBoundingBox({ x, y, width, height, label });
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Drew a box around ${label}` },
                                            }
                                        });
                                    });
                                }
                            } else {
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Error: Invalid coordinates provided for bounding box.` },
                                            }
                                        });
                                    });
                                }
                            }
                        }
                    }
                    setTimeout(() => onAIStateUpdate('listening'), 500);
                }

                if (message.serverContent?.outputTranscription) {
                    currentOutputTranscription += message.serverContent.outputTranscription.text;
                    onAIStateUpdate('speaking');
                } else if (message.serverContent?.inputTranscription) {
                    currentInputTranscription += message.serverContent.inputTranscription.text;
                    onAIStateUpdate('listening');
                }

                if (message.serverContent?.turnComplete) {
                    if (currentInputTranscription.trim()) {
                        onTranscriptionUpdate({ sender: Sender.User, text: currentInputTranscription, timestamp: Date.now() });
                    }
                    if (currentOutputTranscription.trim()) {
                        onTranscriptionUpdate({ sender: Sender.Model, text: currentOutputTranscription, timestamp: Date.now() });
                    }
                    currentInputTranscription = '';
                    currentOutputTranscription = '';
                    setTimeout(() => onAIStateUpdate('listening'), 500);
                }

                if (message.serverContent?.modelTurn && !message.serverContent?.outputTranscription) {
                    onAIStateUpdate('processing');
                }

                const audioData = message.serverContent?.modelTurn?.parts[0]?.inlineData?.data;
                if (audioData && outputAudioContext) {
                    onAIStateUpdate('speaking');
                    nextStartTime = Math.max(nextStartTime, outputAudioContext.currentTime);
                    const audioBuffer = await decodeAudioData(decode(audioData), outputAudioContext, OUTPUT_SAMPLE_RATE, 1);
                    const source = outputAudioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(outputAudioContext.destination);
                    source.addEventListener('ended', () => {
                        sources.delete(source);
                        if (sources.size === 0) {
                            setTimeout(() => onAIStateUpdate('listening'), 200);
                        }
                    });
                    source.start(nextStartTime);
                    nextStartTime += audioBuffer.duration;
                    sources.add(source);
                }
            },
            onerror: (e: ErrorEvent) => {
                console.error("Session error:", e);
                onStatusUpdate("An error occurred with the session.");
            },
            onclose: (e: CloseEvent) => {
                onStatusUpdate("Session closed.");
                cleanUp();
            },
        },
        config: {
            responseModalities: [Modality.AUDIO],
            inputAudioTranscription: {},
            outputAudioTranscription: {},
            speechConfig: {
                voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
            },
            tools: [{ functionDeclarations: [showBoundingBoxFunctionDeclaration] }],
            systemInstruction: 'You are a friendly and helpful AI assistant that can see and hear. Respond to the user based on what you perceive from their video and audio. Keep your responses concise and conversational. When the user asks you to highlight or show a bounding box around something, use the `showBoundingBox` tool with normalized coordinates (0.0 to 1.0) for x, y, width, and height.',
        },
    });

    session = await sessionPromise;
}

function cleanUp() {
    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }
    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }
    if (mediaStreamSource) {
        mediaStreamSource.disconnect();
        mediaStreamSource = null;
    }
    if (inputAudioContext && inputAudioContext.state !== 'closed') {
        inputAudioContext.close();
        inputAudioContext = null;
    }
    if (outputAudioContext && outputAudioContext.state !== 'closed') {
        outputAudioContext.close();
        outputAudioContext = null;
    }
    sources.forEach(source => source.stop());
    sources.clear();
    nextStartTime = 0;
}

export function stopSession() {
    if (session) {
        session.close();
        session = null;
        sessionPromise = null;
    }
    cleanUp();
}
