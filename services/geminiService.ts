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

const highlightObjectFunctionDeclaration: FunctionDeclaration = {
  name: 'highlightObject',
  description: 'Tracks and highlights a specific object in the user\'s camera view using computer vision. The system will detect the object, create a bounding box around it, and track it across frames.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      object_name: {
        type: Type.STRING,
        description: 'The name or description of the object to track and highlight (e.g., "red drill", "capacitor", "multimeter", "screwdriver"). Be specific if there are multiple similar objects.',
      },
    },
    required: ['object_name'],
  },
};


export async function startSession(
    videoElement: HTMLVideoElement,
    canvasElement: HTMLCanvasElement,
    onTranscriptionUpdate: (entry: TranscriptionEntry) => void,
    onStatusUpdate: (status: string) => void,
    onAIStateUpdate: (state: AIState) => void,
    onHighlightObject: (objectName: string) => Promise<void>,
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
                        if (fc.name === 'highlightObject') {
                            const { object_name } = fc.args as { object_name: string };

                            try {
                                // Call the backend to highlight the object
                                await onHighlightObject(object_name);

                                // Send success response to Gemini
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Successfully tracking ${object_name}` },
                                            }
                                        });
                                    });
                                }
                            } catch (error) {
                                // Send error response to Gemini
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Error: ${error instanceof Error ? error.message : 'Failed to track object'}` },
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
            tools: [{ functionDeclarations: [highlightObjectFunctionDeclaration] }],
            systemInstruction: 'You are a friendly and helpful AI assistant that can see and hear. Respond to the user based on what you perceive from their video and audio. Keep your responses concise and conversational. When the user asks you to highlight, track, or show something in their camera view, use the `highlightObject` tool with a clear description of the object (e.g., "red drill", "capacitor", "multimeter"). The system will automatically detect the object, create a bounding box, and track it across frames.',
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
