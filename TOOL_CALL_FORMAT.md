# Tool Call Format Specification

## How It Works

The AI is instructed to output tool calls in a specific text format, which our code detects and executes.

## Primary Format (Recommended)

When the AI wants to highlight an object, it should respond with:

```
TOOL_CALL: highlight_object
OBJECT: [object_name]
```

### Examples:

**User:** "highlight the headphones"
**AI Response:**
```
TOOL_CALL: highlight_object
OBJECT: headphones
```

**User:** "show me the cup"
**AI Response:**
```
TOOL_CALL: highlight_object
OBJECT: cup
```

**User:** "where is my laptop"
**AI Response:**
```
TOOL_CALL: highlight_object
OBJECT: laptop
```

The AI can add friendly text after the tool call:
```
TOOL_CALL: highlight_object
OBJECT: headphones
I've highlighted them for you!
```

## Pattern Matching Priority

Our detection system checks for patterns in this order:

### 1. **Structured Format (PRIMARY)** ✅
```regex
/TOOL_CALL:\s*highlight_object\s*(?:\n|\s)+OBJECT:\s*([^\n]+)/i
```
Matches: `TOOL_CALL: highlight_object\nOBJECT: headphones`

### 2. **JSON Format (FALLBACK)**
```regex
/\[\s*\{[^}]*"label"\s*:\s*"([^"]+)"/
```
Matches: `[{"box_2d": [182, 110, 808, 882], "label": "headphones"}]`

This was the format from the original attempt - kept as fallback.

### 3. **Natural Language (FALLBACK)**
```regex
/(?:highlight|highlighting|point out|showing|locating)\s+(?:the\s+)?([a-zA-Z\s]+)/i
```
Matches: "I'll highlight the headphones", "highlighting your cup"

### 4. **Completion Phrase (FALLBACK)**
```regex
/(?:the\s+)?([a-zA-Z\s]+)\s+(?:are|is)\s+now\s+highlighted/i
```
Matches: "the headphones are now highlighted"

## Why This Format?

1. **Explicit & Unambiguous**: Easy to parse, no false positives
2. **Human Readable**: Clear what the AI is trying to do
3. **Debuggable**: Shows in transcription panel for transparency
4. **Extensible**: Easy to add more tool types later

## Console Output

When a tool call is detected, you'll see:

```
🎤 AI Response: TOOL_CALL: highlight_object
OBJECT: headphones
🔍 DETECTED HIGHLIGHT INTENT: { objectName: 'headphones' }
✓ Matched structured format: headphones
📞 Executing synthetic tool call: {...}
✅ Tool executed successfully
```

## Adding New Tools

To add a new tool (e.g., `measure_distance`), follow this pattern:

1. **Update System Instruction:**
```
When user asks to measure distance, respond:
TOOL_CALL: measure_distance
FROM: [object1]
TO: [object2]
```

2. **Add Pattern Matching:**
```typescript
const measureMatch = fullTranscription.match(
  /TOOL_CALL:\s*measure_distance\s*(?:\n|\s)+FROM:\s*([^\n]+)\s*(?:\n|\s)+TO:\s*([^\n]+)/i
);
```

3. **Handle in detection:**
```typescript
if (measureMatch) {
  return {
    toolName: 'measure_distance',
    args: { from: measureMatch[1].trim(), to: measureMatch[2].trim() }
  };
}
```

## Testing

**Test Case 1: Primary Format**
```
Say: "highlight the cup"
Expected AI: "TOOL_CALL: highlight_object\nOBJECT: cup"
Expected Result: ✅ Tool executes, overlay appears
```

**Test Case 2: JSON Fallback**
```
If AI responds with: [{"label": "cup"}]
Expected Result: ✅ Tool still executes (fallback pattern)
```

**Test Case 3: Natural Language Fallback**
```
If AI responds with: "I'll highlight the cup for you"
Expected Result: ✅ Tool still executes (fallback pattern)
```

---

**Status:** ✅ Implemented and ready to test
**Build:** ✅ Successful
**Next:** Test with live session
