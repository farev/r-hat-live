// FIX: `LiveSession` is not an exported member of `@google/genai`.
import { GoogleGenAI, LiveServerMessage, Modality, FunctionDeclaration, Type } from "@google/genai";
import { decode, decodeAudioData, createPcmBlob, blobToBase64 } from '../utils/audioUtils';
import { Sender, TranscriptionEntry, AIState } from '../types';

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
let audioQueue: AudioBuffer[] = [];
let isPlayingQueue = false;

// Store canvas reference for getCurrentFrame
let currentCanvasElement: HTMLCanvasElement | null = null;

// Function declaration for highlight tool
const highlightObjectFunctionDeclaration: FunctionDeclaration = {
    name: 'highlight_object',
    description: 'Highlights and identifies objects in the camera view by drawing bounding boxes and segmentation masks around them. Use this when the user asks to show, highlight, point out, or locate specific objects.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            object_name: {
                type: Type.STRING,
                description: 'The name of the object to highlight in the camera view (e.g., "cup", "laptop", "person", "phone")',
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
    onHighlight?: (objectName: string) => void,
): Promise<void> {
    // Store canvas reference
    currentCanvasElement = canvasElement;

    onStatusUpdate("Initializing Gemini...");
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });

    let currentInputTranscription = '';
    let currentOutputTranscription = '';

    const toolsConfig = [
        { google_search: {} },
        { functionDeclarations: [highlightObjectFunctionDeclaration] }
    ];

    console.log('🚀 STARTING SESSION WITH CONFIG:');
    console.log('Model:', 'gemini-2.5-flash-native-audio-preview-09-2025');
    console.log('Tools:', JSON.stringify(toolsConfig, null, 2));
    console.log('Response Modalities:', [Modality.AUDIO]);
    console.log('Highlight handler registered:', !!onHighlight);

    sessionPromise = ai.live.connect({
        model: 'gemini-2.5-flash-native-audio-preview-09-2025',
        callbacks: {
            onopen: async () => {
                console.log('✅ SESSION OPENED - Native function calling enabled');
                onStatusUpdate("Connected! You can start talking.");
                onAIStateUpdate('listening');
                try {
                    console.log('🔍 GeminiService: Getting media stream from video element...');

                    // Get the stream from the video element (already set up in App.tsx)
                    const stream = videoElement.srcObject as MediaStream;
                    if (!stream) {
                        throw new Error('No media stream found on video element');
                    }

                    console.log('📹 GeminiService: Found media stream:', stream.getTracks());

                    const audioTracks = stream.getAudioTracks();
                    const videoTracks = stream.getVideoTracks();

                    if (audioTracks.length === 0) {
                        throw new Error('No audio tracks found in media stream');
                    }
                    if (videoTracks.length === 0) {
                        throw new Error('No video tracks found in media stream');
                    }

                    console.log('🎤 Audio tracks:', audioTracks.map(track => ({
                        id: track.id,
                        label: track.label,
                        kind: track.kind,
                        enabled: track.enabled,
                        readyState: track.readyState,
                        settings: track.getSettings()
                    })));

                    console.log('📹 Video tracks:', videoTracks.map(track => ({
                        id: track.id,
                        label: track.label,
                        kind: track.kind,
                        enabled: track.enabled,
                        readyState: track.readyState,
                        settings: track.getSettings()
                    })));

                    // Get the actual sample rate from the audio track
                    const audioSettings = audioTracks[0].getSettings();
                    const actualSampleRate = audioSettings.sampleRate;

                    console.log('🎵 Detected audio sample rate:', actualSampleRate);

                    // FIX: Cast `window` to `any` to access `webkitAudioContext` for older browser compatibility.
                    try {
                        if (actualSampleRate) {
                            inputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: actualSampleRate });
                            console.log('✅ Created inputAudioContext with detected sample rate:', actualSampleRate);
                        } else {
                            throw new Error('No sample rate detected, using fallback');
                        }
                    } catch (sampleRateError) {
                        console.log('⚠️ Sample rate creation failed, using default AudioContext:', sampleRateError.message);
                        inputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
                    }

                    // FIX: Cast `window` to `any` to access `webkitAudioContext` for older browser compatibility.
                    try {
                        outputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: OUTPUT_SAMPLE_RATE });
                        console.log('✅ Created outputAudioContext with target sample rate:', OUTPUT_SAMPLE_RATE);
                    } catch (outputError) {
                        console.log('⚠️ Output sample rate creation failed, using default:', outputError.message);
                        outputAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
                    }

                    console.log('🔊 Audio contexts created:', {
                        inputSampleRate: inputAudioContext.sampleRate,
                        outputSampleRate: outputAudioContext.sampleRate,
                        inputState: inputAudioContext.state,
                        outputState: outputAudioContext.state
                    });

                    // Audio input processing
                    mediaStreamSource = inputAudioContext.createMediaStreamSource(stream);
                    scriptProcessor = inputAudioContext.createScriptProcessor(4096, 1, 1);

                    console.log('🎧 Audio processing nodes created');

                    scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
                        const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);

                        // Handle sample rate conversion if needed
                        let processedData = inputData;
                        const currentSampleRate = inputAudioContext.sampleRate;

                        if (currentSampleRate !== INPUT_SAMPLE_RATE) {
                            // Simple downsampling (for production, consider using a proper resampling library)
                            const ratio = currentSampleRate / INPUT_SAMPLE_RATE;
                            const newLength = Math.floor(inputData.length / ratio);
                            const resampledData = new Float32Array(newLength);

                            for (let i = 0; i < newLength; i++) {
                                const sourceIndex = Math.floor(i * ratio);
                                resampledData[i] = inputData[sourceIndex];
                            }
                            processedData = resampledData;
                        }

                        const pcmBlob = createPcmBlob(processedData);
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
                // Handle NATIVE function calling (toolCall in message)
                if (message.toolCall) {
                    console.log('🔧 NATIVE TOOL CALL DETECTED:', message.toolCall);
                    onAIStateUpdate('using_tool');

                    for (const fc of message.toolCall.functionCalls) {
                        console.log('📞 Function call:', fc.name, 'with args:', fc.args);

                        if (fc.name === 'highlight_object') {
                            const objectName = fc.args.object_name as string || 'object';
                            console.log(`🎯 Highlighting object: ${objectName}`);

                            // Call the highlight handler
                            if (onHighlight) {
                                onHighlight(objectName);
                            }

                            // Send tool response back to Gemini
                            if (sessionPromise) {
                                sessionPromise.then((s) => {
                                    s.sendToolResponse({
                                        functionResponses: [{
                                            id: fc.id,
                                            name: fc.name,
                                            response: { result: `Successfully highlighted ${objectName}` },
                                        }]
                                    });
                                    console.log('✅ Tool response sent to Gemini');
                                });
                            }
                        }
                    }

                    // Return to listening after tool execution
                    setTimeout(() => onAIStateUpdate('listening'), 500);
                }

                // Handle input transcription (user speaking)
                if (message.serverContent?.inputTranscription) {
                    currentInputTranscription += message.serverContent.inputTranscription.text;
                    onAIStateUpdate('listening');
                }

                // Handle output transcription (AI responding)
                if (message.serverContent?.outputTranscription) {
                    currentOutputTranscription += message.serverContent.outputTranscription.text;
                    onAIStateUpdate('speaking');
                }

                // Handle turn completion
                if (message.serverContent?.turnComplete) {
                    if (currentInputTranscription.trim()) {
                        onTranscriptionUpdate({ sender: Sender.User, text: currentInputTranscription, timestamp: Date.now() });
                    }
                    if (currentOutputTranscription.trim()) {
                        onTranscriptionUpdate({ sender: Sender.Model, text: currentOutputTranscription, timestamp: Date.now() });
                    }
                    currentInputTranscription = '';
                    currentOutputTranscription = '';

                    // Return to listening state after turn completion
                    setTimeout(() => onAIStateUpdate('listening'), 500);
                }

                // Handle model thinking/processing
                if (message.serverContent?.modelTurn && !message.serverContent?.outputTranscription) {
                    onAIStateUpdate('processing');
                }

                // Handle audio playback with better buffering
                const audioData = message.serverContent?.modelTurn?.parts[0]?.inlineData?.data;
                if (audioData && outputAudioContext) {
                    onAIStateUpdate('speaking');

                    try {
                        // Resume audio context if suspended
                        if (outputAudioContext.state === 'suspended') {
                            console.log('🔊 Resuming suspended audio context...');
                            await outputAudioContext.resume();
                        }

                        const audioBuffer = await decodeAudioData(decode(audioData), outputAudioContext, OUTPUT_SAMPLE_RATE, 1);

                        const source = outputAudioContext.createBufferSource();

                        // Add gain node for better volume control
                        const gainNode = outputAudioContext.createGain();
                        gainNode.gain.setValueAtTime(1.0, outputAudioContext.currentTime);

                        source.buffer = audioBuffer;
                        source.connect(gainNode);
                        gainNode.connect(outputAudioContext.destination);

                        // Use smoother playback scheduling
                        const currentTime = outputAudioContext.currentTime;

                        // If this is the first audio chunk, start immediately with small buffer
                        if (sources.size === 0) {
                            nextStartTime = currentTime + 0.05;
                        } else {
                            // For subsequent chunks, ensure smooth continuity
                            nextStartTime = Math.max(nextStartTime, currentTime + 0.02);
                        }

                        source.addEventListener('ended', () => {
                            sources.delete(source);
                            // If this was the last audio source, return to listening
                            if (sources.size === 0) {
                                setTimeout(() => onAIStateUpdate('listening'), 200);
                            }
                        });

                        source.start(nextStartTime);
                        const endTime = nextStartTime + audioBuffer.duration;
                        nextStartTime = endTime;
                        sources.add(source);

                    } catch (audioError) {
                        console.error('❌ Audio playback error:', audioError);
                        // Fallback: still update state even if audio fails
                        setTimeout(() => onAIStateUpdate('listening'), 1000);
                    }
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
            tools: toolsConfig,
            speechConfig: {
                voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
            },
            systemInstruction: `You are R-Hat, a friendly and helpful AI assistant that can see, hear, and search the web. You are an expert engineer that can help with any hands-on task.

You have access to the following tools:
1. Google Search - for looking up current information, videos, or web content
2. highlight_object - for highlighting and identifying objects in the camera view

When users ask you to "show me", "highlight", "point out", "where is", or "find" a specific object in the camera view, use the highlight_object function. For example:
- "highlight the cup" → call highlight_object with object_name="cup"
- "show me the laptop" → call highlight_object with object_name="laptop"
- "where is my phone" → call highlight_object with object_name="phone"

Always be honest about your capabilities. Respond based on what you perceive from video/audio. Keep responses concise and conversational.`,
        },
    });

    session = await sessionPromise;
}

/**
 * Captures the current frame from the canvas as a base64 encoded image
 */
export async function getCurrentFrame(): Promise<string | null> {
    if (!currentCanvasElement) {
        console.error('No canvas element available');
        return null;
    }

    try {
        return new Promise((resolve) => {
            currentCanvasElement!.toBlob(
                async (blob) => {
                    if (blob) {
                        const base64 = await blobToBase64(blob);
                        resolve(base64);
                    } else {
                        resolve(null);
                    }
                },
                'image/jpeg',
                0.9
            );
        });
    } catch (error) {
        console.error('Error capturing frame:', error);
        return null;
    }
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
    audioQueue = [];
    isPlayingQueue = false;
    currentCanvasElement = null;
}

export function stopSession() {
    if (session) {
        session.close();
        session = null;
        sessionPromise = null;
    }
    cleanUp();
}
