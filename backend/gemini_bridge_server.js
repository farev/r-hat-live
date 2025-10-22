/**
 * Gemini Live WebSocket Bridge Server
 * Wraps the TypeScript Gemini service and exposes it via WebSocket
 * This allows the Python app to use the working TypeScript implementation
 */

const WebSocket = require('ws');
const { GoogleGenAI, Modality, Type } = require("@google/genai");

const PORT = 8765;

// WebSocket server
const wss = new WebSocket.Server({ port: PORT });

console.log(`[BRIDGE] Gemini WebSocket Bridge Server started on ws://localhost:${PORT}`);

wss.on('connection', (ws) => {
    console.log('[BRIDGE] Python client connected');

    let geminiSession = null;
    let audioContext = null;
    let videoInterval = null;

    // Handle messages from Python
    ws.on('message', async (message) => {
        try {
            const data = JSON.parse(message);
            const { type, payload } = data;

            switch (type) {
                case 'START_SESSION':
                    await startGeminiSession(ws, payload.apiKey);
                    break;

                case 'SEND_AUDIO':
                    if (geminiSession) {
                        // Audio data comes as base64
                        const audioBlob = Buffer.from(payload.data, 'base64');
                        await geminiSession.sendRealtimeInput({ media: audioBlob });
                    }
                    break;

                case 'SEND_VIDEO':
                    if (geminiSession) {
                        // Video frame comes as base64 JPEG
                        const imageData = payload.data;
                        await geminiSession.sendRealtimeInput({
                            media: { data: imageData, mimeType: 'image/jpeg' }
                        });
                    }
                    break;

                case 'TOOL_RESPONSE':
                    if (geminiSession) {
                        await geminiSession.sendToolResponse({
                            functionResponses: {
                                id: payload.callId,
                                name: 'highlightObject',
                                response: { result: payload.result }
                            }
                        });
                    }
                    break;

                case 'STOP_SESSION':
                    stopGeminiSession();
                    break;

                default:
                    console.log(`[BRIDGE] Unknown message type: ${type}`);
            }
        } catch (error) {
            console.error('[BRIDGE] Error handling message:', error);
            ws.send(JSON.stringify({ type: 'ERROR', error: error.message }));
        }
    });

    ws.on('close', () => {
        console.log('[BRIDGE] Python client disconnected');
        stopGeminiSession();
    });

    async function startGeminiSession(ws, apiKey) {
        console.log('[BRIDGE] Starting Gemini session...');

        const ai = new GoogleGenAI({ apiKey });

        const highlightObjectTool = {
            name: 'highlightObject',
            description: 'Tracks and highlights a specific object in the user\'s camera view',
            parameters: {
                type: Type.OBJECT,
                properties: {
                    object_name: {
                        type: Type.STRING,
                        description: 'The name or description of the object to track',
                    },
                },
                required: ['object_name'],
            },
        };

        try {
            const sessionPromise = ai.live.connect({
                model: 'gemini-2.5-flash-native-audio-preview-09-2025',
                callbacks: {
                    onopen: () => {
                        console.log('[BRIDGE] Gemini session opened');
                        ws.send(JSON.stringify({ type: 'STATUS', status: 'connected' }));
                    },
                    onmessage: (message) => {
                        // Forward Gemini messages to Python
                        handleGeminiMessage(ws, message);
                    },
                    onerror: (error) => {
                        console.error('[BRIDGE] Gemini error:', error);
                        ws.send(JSON.stringify({ type: 'ERROR', error: error.message }));
                    },
                    onclose: () => {
                        console.log('[BRIDGE] Gemini session closed');
                        ws.send(JSON.stringify({ type: 'STATUS', status: 'closed' }));
                    },
                },
                config: {
                    responseModalities: [Modality.AUDIO],
                    inputAudioTranscription: {},
                    outputAudioTranscription: {},
                    speechConfig: {
                        voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
                    },
                    tools: [{ functionDeclarations: [highlightObjectTool] }],
                    systemInstruction: 'You are a friendly and helpful AI assistant that can see and hear. Respond to the user based on what you perceive from their video and audio. Keep your responses concise and conversational. When the user asks you to highlight, track, or show something in their camera view, use the `highlightObject` tool with a clear description of the object.',
                },
            });

            geminiSession = await sessionPromise;
            console.log('[BRIDGE] Gemini session ready');

        } catch (error) {
            console.error('[BRIDGE] Failed to start Gemini session:', error);
            ws.send(JSON.stringify({ type: 'ERROR', error: error.message }));
        }
    }

    function handleGeminiMessage(ws, message) {
        // Tool calls
        if (message.toolCall) {
            for (const fc of message.toolCall.functionCalls) {
                if (fc.name === 'highlightObject') {
                    const { object_name } = fc.args;
                    ws.send(JSON.stringify({
                        type: 'TOOL_CALL',
                        tool: 'highlightObject',
                        args: { object_name },
                        callId: fc.id,
                    }));
                }
            }
        }

        // Transcriptions
        if (message.serverContent?.outputTranscription) {
            ws.send(JSON.stringify({
                type: 'TRANSCRIPTION',
                sender: 'MODEL',
                text: message.serverContent.outputTranscription.text,
            }));
        }

        if (message.serverContent?.inputTranscription) {
            ws.send(JSON.stringify({
                type: 'TRANSCRIPTION',
                sender: 'USER',
                text: message.serverContent.inputTranscription.text,
            }));
        }

        // Audio output
        if (message.serverContent?.modelTurn?.parts) {
            for (const part of message.serverContent.modelTurn.parts) {
                if (part.inlineData?.data) {
                    ws.send(JSON.stringify({
                        type: 'AUDIO_OUTPUT',
                        data: part.inlineData.data, // Base64 PCM audio
                        mimeType: part.inlineData.mimeType,
                    }));
                }
            }
        }

        // Turn complete
        if (message.serverContent?.turnComplete) {
            ws.send(JSON.stringify({ type: 'TURN_COMPLETE' }));
        }

        // AI state
        if (message.toolCall) {
            ws.send(JSON.stringify({ type: 'AI_STATE', state: 'using_tool' }));
        } else if (message.serverContent?.outputTranscription) {
            ws.send(JSON.stringify({ type: 'AI_STATE', state: 'speaking' }));
        } else if (message.serverContent?.inputTranscription) {
            ws.send(JSON.stringify({ type: 'AI_STATE', state: 'listening' }));
        } else if (message.serverContent?.modelTurn && !message.serverContent?.outputTranscription) {
            ws.send(JSON.stringify({ type: 'AI_STATE', state: 'processing' }));
        }
    }

    function stopGeminiSession() {
        if (geminiSession) {
            geminiSession.close();
            geminiSession = null;
        }
        if (videoInterval) {
            clearInterval(videoInterval);
            videoInterval = null;
        }
    }
});

// Handle tool response from Python
wss.on('message', (ws, message) => {
    // This will be handled in the per-client message handler above
});

console.log('[BRIDGE] Waiting for Python client to connect...');
