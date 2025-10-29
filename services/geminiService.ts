// FIX: `LiveSession` is not an exported member of `@google/genai`.
import { GoogleGenAI, LiveServerMessage, Modality, FunctionDeclaration, Type } from "@google/genai";
import { decode, decodeAudioData, createPcmBlob, blobToBase64 } from '../utils/audioUtils';
import { Sender, TranscriptionEntry, AIState } from '../types';
import { PlayYouTubeArgs, YouTubeVideo, ChecklistUpdateArgs } from '../types/tools';
import { searchYouTubeVideo } from './youtubeService';
import { SYSTEM_INSTRUCTION } from './systemInstruction';

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
      tracking_duration_seconds: {
        type: Type.NUMBER,
        description: 'Optional duration in seconds to keep the tracker active. Use shorter durations for quick callouts and longer durations when the user needs sustained guidance.',
      },
    },
    required: ['object_name'],
  },
};

const displayImageFunctionDeclaration: FunctionDeclaration = {
  name: 'displayImage',
  description: 'Displays an image in the AR overlay as a floating panel. Use this when the user asks to show, display, or pull up an image of something (e.g., "show me an image of a circuit board", "display a picture of Arduino", "pull up a diagram of a transistor").',
  parameters: {
    type: Type.OBJECT,
    properties: {
      query: {
        type: Type.STRING,
        description: 'A search query describing the image to display (e.g., "circuit board", "Arduino Uno", "NPN transistor diagram").',
      },
    },
    required: ['query'],
  },
};

const getVideoFunctionDeclaration: FunctionDeclaration = {
  name: 'getVideo',
  description: 'Searches YouTube for a relevant instructional video and returns a link that can be played from a specific timestamp. Use this when the user asks to watch or learn something from a video.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      query: {
        type: Type.STRING,
        description: 'Search terms that describe the desired video (e.g., "cook carrots tutorial").',
      },
      timestamp: {
        type: Type.NUMBER,
        description: 'Optional start time in seconds.',
      },
    },
    required: ['query'],
  },
};

const updateChecklistFunctionDeclaration: FunctionDeclaration = {
  name: 'updateChecklist',
  description: 'Creates or updates the on-screen checklist so the user can follow along with the current plan. Call this when you want to guide the user with clear steps or when the list changes.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      title: {
        type: Type.STRING,
        description: 'Optional short title that will appear above the checklist (e.g., "Prep Steps").',
      },
      items: {
        type: Type.ARRAY,
        description: 'Ordered list of tasks to display. Provide the full list you want the user to see.',
        items: {
          type: Type.OBJECT,
          properties: {
            id: {
              type: Type.STRING,
              description: 'Stable identifier for the task. Reuse it when updating the same item later.',
            },
            label: {
              type: Type.STRING,
              description: 'User-facing description of the task.',
            },
            completed: {
              type: Type.BOOLEAN,
              description: 'Mark true if this task is already finished so it appears checked.',
            },
          },
          required: ['label'],
        },
      },
      clear: {
        type: Type.BOOLEAN,
        description: 'Set to true to remove the current checklist from the HUD.',
      },
      completed_items: {
        type: Type.ARRAY,
        description: 'List of item labels or IDs that should be marked as completed. Use this when you observe the user finishing a step.',
        items: {
          type: Type.STRING,
        },
      },
      incomplete_items: {
        type: Type.ARRAY,
        description: 'List of item labels or IDs that should be marked as not completed (e.g., when a user reopens or redoes a step).',
        items: {
          type: Type.STRING,
        },
      },
      toggle_items: {
        type: Type.ARRAY,
        description: 'List of item labels or IDs whose completion status should be toggled.',
        items: {
          type: Type.STRING,
        },
      },
    },
  },
};


export async function startSession(
    videoElement: HTMLVideoElement,
    canvasElement: HTMLCanvasElement,
    onTranscriptionUpdate: (entry: TranscriptionEntry) => void,
    onStatusUpdate: (status: string) => void,
    onAIStateUpdate: (state: AIState) => void,
    onHighlightObject: (objectName: string, trackingDurationSeconds?: number) => Promise<void>,
    onDisplayImage: (query: string) => Promise<void>,
    onPlayYouTubeVideo: (video: YouTubeVideo) => void,
    onUpdateChecklist: (update: ChecklistUpdateArgs) => Promise<void> | void,
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

                    // Debug: Log all tool calls
                    console.log('🔧 [TOOL CALL] Agent is using tools:', message.toolCall.functionCalls.length);

                    for (const fc of message.toolCall.functionCalls) {
                        console.log(`🔧 [TOOL CALL] Tool: ${fc.name}`);
                        console.log(`🔧 [TOOL CALL] Parameters:`, JSON.stringify(fc.args, null, 2));

                        if (fc.name === 'highlightObject') {
                            const { object_name, tracking_duration_seconds } = fc.args as { object_name: string; tracking_duration_seconds?: number };

                            try {
                                // Call the backend to highlight the object
                                await onHighlightObject(object_name, tracking_duration_seconds);

                                // Send success response to Gemini
                                console.log(`✅ [TOOL CALL] ${fc.name} succeeded`);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Successfully tracking ${object_name}${tracking_duration_seconds ? ` for ${tracking_duration_seconds} seconds` : ''}` },
                                            }
                                        });
                                    });
                                }
                            } catch (error) {
                                // Send error response to Gemini
                                console.error(`❌ [TOOL CALL] ${fc.name} failed:`, error);
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
                        } else if (fc.name === 'displayImage') {
                            const { query } = fc.args as { query: string };

                            try {
                                // Call the display image function
                                await onDisplayImage(query);

                                // Send success response to Gemini
                                console.log(`✅ [TOOL CALL] ${fc.name} succeeded`);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Successfully displayed image for "${query}"` },
                                            }
                                        });
                                    });
                                }
                            } catch (error) {
                                // Send error response to Gemini
                                console.error(`❌ [TOOL CALL] ${fc.name} failed:`, error);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: { result: `Error: ${error instanceof Error ? error.message : 'Failed to display image'}` },
                                            }
                                        });
                                    });
                                }
                            }
                        } else if (fc.name === 'getVideo') {
                            const { query, timestamp } = fc.args as PlayYouTubeArgs;

                            try {
                                let startTime: number | undefined;

                                if (typeof timestamp === 'number') {
                                    startTime = timestamp;
                                } else if (timestamp !== undefined) {
                                    const numericTimestamp = Number(timestamp);
                                    if (Number.isFinite(numericTimestamp) && numericTimestamp >= 0) {
                                        startTime = numericTimestamp;
                                    }
                                }

                                const video = await searchYouTubeVideo(query, startTime);

                                onPlayYouTubeVideo(video);

                                console.log(`✅ [TOOL CALL] ${fc.name} succeeded`);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: {
                                                    result: {
                                                        video_id: video.video_id,
                                                        title: video.title,
                                                        url: video.url,
                                                        start_time: video.start_time,
                                                        channel_title: video.channel_title,
                                                    },
                                                },
                                            },
                                        });
                                    });
                                }
                            } catch (error) {
                                console.error(`❌ [TOOL CALL] ${fc.name} failed:`, error);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: {
                                                    result: `Error: ${
                                                        error instanceof Error ? error.message : 'Failed to fetch video'
                                                    }`,
                                                },
                                            },
                                        });
                                    });
                                }
                            }
                        }
                        else if (fc.name === 'updateChecklist') {
                            const rawArgs = fc.args as ChecklistUpdateArgs & { items?: unknown };

                            const normalizeTargets = (value: unknown): string[] | undefined => {
                                if (!Array.isArray(value)) return undefined;

                                const normalized = value
                                    .map((entry) => {
                                        if (typeof entry === 'string' || typeof entry === 'number') {
                                            return String(entry).trim();
                                        }

                                        if (typeof entry === 'object' && entry !== null) {
                                            const entryId = typeof (entry as { id?: unknown }).id === 'string'
                                                ? (entry as { id: string }).id.trim()
                                                : '';
                                            const entryLabel = typeof (entry as { label?: unknown }).label === 'string'
                                                ? (entry as { label: string }).label.trim()
                                                : '';
                                            return entryId || entryLabel;
                                        }
                                        return '';
                                    })
                                    .map(item => item.trim())
                                    .filter(item => item.length > 0);

                                return normalized.length > 0 ? normalized : undefined;
                            };

                            const sanitizedItems = Array.isArray(rawArgs.items)
                                ? rawArgs.items
                                    .map((item) => {
                                        if (typeof item === 'string' || typeof item === 'number') {
                                            const label = String(item).trim();
                                            return label.length > 0 ? { label } : null;
                                        }

                                        if (typeof item === 'object' && item !== null) {
                                            const label = typeof (item as { label?: unknown }).label === 'string'
                                                ? (item as { label: string }).label.trim()
                                                : '';
                                            if (label.length === 0) return null;

                                            return {
                                                id: typeof (item as { id?: unknown }).id === 'string'
                                                    && (item as { id: string }).id.trim().length > 0
                                                    ? (item as { id: string }).id.trim()
                                                    : undefined,
                                                label,
                                                completed: typeof (item as { completed?: unknown }).completed === 'boolean'
                                                    ? (item as { completed: boolean }).completed
                                                    : undefined,
                                            };
                                        }

                                        return null;
                                    })
                                    .filter((item): item is { id?: string; label: string; completed?: boolean } => item !== null)
                                : undefined;

                            const updatePayload: ChecklistUpdateArgs = {
                                title: typeof rawArgs.title === 'string' ? rawArgs.title : undefined,
                                clear: rawArgs.clear === true,
                                items: sanitizedItems,
                                completedItems: normalizeTargets((rawArgs as { completed_items?: unknown }).completed_items),
                                incompleteItems: normalizeTargets((rawArgs as { incomplete_items?: unknown }).incomplete_items),
                                toggleItems: normalizeTargets((rawArgs as { toggle_items?: unknown }).toggle_items),
                            };

                            try {
                                await onUpdateChecklist(updatePayload);

                                console.log(`✅ [TOOL CALL] ${fc.name} succeeded`);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: {
                                                    result: updatePayload.clear
                                                        ? 'Checklist cleared.'
                                                        : `Checklist updated with ${(updatePayload.items?.length ?? 0)} item(s).`,
                                                },
                                            },
                                        });
                                    });
                                }
                            } catch (error) {
                                console.error(`❌ [TOOL CALL] ${fc.name} failed:`, error);
                                if (sessionPromise) {
                                    sessionPromise.then((s) => {
                                        s.sendToolResponse({
                                            functionResponses: {
                                                id: fc.id,
                                                name: fc.name,
                                                response: {
                                                    result: `Error: ${error instanceof Error ? error.message : 'Failed to update checklist'}`,
                                                },
                                            },
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
            tools: [
                { functionDeclarations: [highlightObjectFunctionDeclaration, displayImageFunctionDeclaration, getVideoFunctionDeclaration, updateChecklistFunctionDeclaration] },
                { googleSearch: {} }
            ],
            systemInstruction: SYSTEM_INSTRUCTION,
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
