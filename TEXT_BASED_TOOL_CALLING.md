# Text-Based Tool Calling Implementation

## The Problem

The Gemini Live API with audio mode **does not support native function calling**. When you ask the AI to "highlight the headphones", it responds with audio and text describing what it would do, including JSON coordinates:

```
"Yes, I can highlight the headphones. Give me a moment.
[{"box_2d": [182, 110, 808, 882], "label": "headphones"}]
There you go, the headphones are now highlighted."
```

But it never actually calls a `functionCall` - it only sends audio (`inlineData`) in the message parts.

## The Solution: Intent Detection

Instead of waiting for native function calls that never come, we **parse the AI's text responses** to detect when it wants to use a tool, then trigger the tool ourselves.

### How It Works

1. **User speaks**: "Highlight the headphones"

2. **AI responds** (via `outputTranscription`): "I'll highlight the headphones for you"

3. **Our code detects the intent** using pattern matching:
   ```typescript
   detectHighlightIntent(transcriptionText, fullTranscription)
   ```

4. **We create a synthetic function call**:
   ```typescript
   const syntheticCall = {
     name: 'highlight_object',
     id: `synthetic_${Date.now()}`,
     args: { object_name: 'headphones' }
   };
   ```

5. **Execute the tool handler** just as if Gemini had called it natively

6. **Tool runs** and creates the highlight overlay

### Pattern Matching

The `detectHighlightIntent()` function looks for three patterns:

**Pattern 1: JSON format (what we're currently seeing)**
```javascript
/\[\s*\{[^}]*"label"\s*:\s*"([^"]+)"/
```
Matches: `[{"box_2d": [...], "label": "headphones"}]`

**Pattern 2: Natural language - "highlighting the X"**
```javascript
/(?:highlight|highlighting|point out|showing|locating)\s+(?:the\s+)?([a-zA-Z\s]+)/i
```
Matches: "I'll highlight the headphones", "highlighting your cup"

**Pattern 3: Completion phrase - "X are now highlighted"**
```javascript
/(?:the\s+)?([a-zA-Z\s]+)\s+(?:are|is)\s+now\s+highlighted/i
```
Matches: "the headphones are now highlighted"

### Cleaned Up Logging

**Before**: 100+ logs per second (audio chunks, resampling, etc.)

**Now**: Only logs when important events happen:
- 🎤 AI Response text (for debugging)
- 🔍 DETECTED HIGHLIGHT INTENT (when pattern matches)
- 📞 Executing synthetic tool call
- ✅ Tool executed successfully
- ❌ Errors (if any occur)

## Testing

1. **Start the app**: `npm run dev`

2. **Start a session** and say: **"Highlight the headphones"**

3. **Watch the console** for:
   ```
   🎤 AI Response: I'll highlight the headphones for you
   🔍 DETECTED HIGHLIGHT INTENT: { objectName: 'headphones' }
   📞 Executing synthetic tool call: { name: 'highlight_object', id: 'synthetic_...', args: { object_name: 'headphones' } }
   ✅ Tool executed successfully: {...}
   ```

4. **Check the UI**:
   - AI state changes to "Using Tool" (purple)
   - System message appears in transcription
   - Mock highlight overlay displays (ready for Phase 2 backend)

## Why This Approach?

### Alternative Approaches Considered:

1. ❌ **Wait for native function calling** - Doesn't exist in Live API audio mode
2. ❌ **Use text-only Gemini API** - Would lose real-time audio/video capabilities
3. ✅ **Intent detection from responses** - Works with existing Live API

### Benefits:

- ✅ Works with current Gemini Live API limitations
- ✅ Maintains real-time audio/video features
- ✅ User experience is seamless (they don't know the difference)
- ✅ Easy to extend with more tool patterns
- ✅ Ready for Phase 2 (backend integration)

### Drawbacks:

- Pattern matching can have false positives (mitigated with careful regex)
- Relies on AI responding in expected format (handled with multiple patterns)
- Slightly less reliable than native function calling (acceptable tradeoff)

## Next Steps for Phase 2

When you integrate the Grounded-SAM 2 backend:

1. The tool handler in `App.tsx` (line ~54) already captures frames
2. Replace the mock response with actual API call to your FastAPI backend
3. The rest of the flow remains unchanged - synthetic function calls work the same!

## Code Changes

### Modified Files:
- `services/geminiService.ts`:
  - Added `detectHighlightIntent()` function
  - Added intent detection in `outputTranscription` handler
  - Cleaned up verbose logging
  - Simplified system instruction
  - Created synthetic function calls when intent detected

### What We Kept:
- All the tool infrastructure from Phase 1 (still useful!)
- `FunctionCall` and `FunctionResponse` types
- Tool handler in `App.tsx`
- UI feedback system
- Everything else from Phase 1

The native function calling code is kept as a fallback - if Google ever adds support for function calling in Live API audio mode, it will automatically work!

## Build Status
✅ Build successful
✅ TypeScript happy
✅ Ready to test

---

**You were absolutely right!** The Gemini Live API doesn't support native function calling in audio mode, so we detect intent from text responses instead. This is actually a common pattern in agentic systems. 🎯
