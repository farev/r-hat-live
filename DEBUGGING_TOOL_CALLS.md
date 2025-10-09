# Debugging Tool Calls - Gemini Live API

## Issue
Gemini is describing what it would do (providing JSON coordinates in text) instead of actually calling the `highlight_object` function.

## Changes Made

### 1. Enhanced System Instruction
Updated the system instruction to be more forceful and explicit about when to use the function vs. when to describe things.

**Key changes:**
- Added "IMPORTANT TOOL USAGE RULES" section
- Explicitly told the model to NOT provide coordinates in text
- Provided examples of correct and incorrect behavior
- Used stronger language: "you MUST call" instead of "use"

### 2. Added Enhanced Logging
Added comprehensive logging to track:
- Full message structure
- serverContent keys
- modelTurn parts
- Part types for each message

### 3. Verified Tool Registration
Added logging to confirm:
- Tools config is properly formatted
- Tool handler is registered
- highlightToolDeclaration is correct

## Debugging Steps

### Step 1: Check Tool Registration
When you start a session, look for this in the console:

```
🚀 STARTING SESSION WITH CONFIG:
Model: gemini-2.5-flash-native-audio-preview-09-2025
Tools: [
  {
    "google_search": {}
  },
  {
    "function_declarations": [
      {
        "name": "highlight_object",
        "description": "Highlights and identifies objects...",
        "parameters": { ... }
      }
    ]
  }
]
Tool Handler Registered: true
```

✅ Verify:
- `highlight_object` is in the tools array
- `Tool Handler Registered: true`

### Step 2: Check Message Structure
When you ask Gemini to "highlight the headphones", look for:

```
=== GEMINI API MESSAGE ===
📦 serverContent keys: [ 'modelTurn', ... ]
🤖 modelTurn parts count: 1 (or more)
📄 Part type: [ 'functionCall' ] or [ 'text' ] or [ 'inlineData' ]
```

**If you see `functionCall`:**
```
🔧 TOOL CALL DETECTED: {
  name: 'highlight_object',
  id: '...',
  args: { object_name: 'headphones' }
}
📞 Executing tool: highlight_object
```
✅ This means it's working!

**If you see only `text`:**
```
📄 Part type: [ 'text' ]
💬 TEXT PART: "Yes, I can highlight the headphones..."
```
❌ This means the model is not calling the function

### Step 3: Possible Issues & Solutions

#### Issue A: Model Not Calling Function
**Symptoms:** Only seeing text responses with JSON coordinates

**Possible causes:**
1. **Model version doesn't support function calling in Live API**
   - The `gemini-2.5-flash-native-audio-preview-09-2025` model might have limited function calling support in Live mode
   - Solution: Check Gemini docs for which models support function calling in Live API

2. **System instruction not strong enough**
   - Even with explicit instructions, models can ignore function calls
   - Solution: Try even more explicit prompting or use a different approach

3. **Tool declaration format incorrect**
   - The Live API might expect a different format than standard Gemini API
   - Solution: Check the exact schema expected by Live API

#### Issue B: Function Call Not Detected
**Symptoms:** No `🔧 TOOL CALL DETECTED` log even though function was called

**Possible causes:**
1. **Message structure different than expected**
   - Check the "Full message" JSON to see actual structure
   - Compare with expected structure in code

2. **Missing `functionCall` in parts**
   - The function call might be in a different location in the message

## Next Steps to Try

### Option 1: Verify Live API Function Calling Support
Check the Gemini Live API documentation:
- https://ai.google.dev/gemini-api/docs/live-tools

Look for:
- Confirmed models that support function calling in Live mode
- Exact format for function declarations
- Any special configuration needed

### Option 2: Try Manual Mode Configuration
According to the docs, you might need to set the function calling mode:

```typescript
tools: [
  {
    function_declarations: [
      {
        ...highlightToolDeclaration,
        // Try adding mode configuration
      }
    ]
  }
],
// Add tool config
toolConfig: {
  functionCallingConfig: {
    mode: 'AUTO' // or 'ANY' to force function calls
  }
}
```

### Option 3: Test with Simple Function First
Create a simpler test function to isolate the issue:

```typescript
const testToolDeclaration = {
  name: "test_function",
  description: "A simple test function. Call this when user says 'test'.",
  parameters: {
    type: "object",
    properties: {
      message: {
        type: "string",
        description: "A test message"
      }
    },
    required: ["message"]
  }
};
```

Say "test" and see if this gets called.

### Option 4: Check for Tool Config in Response
After session starts, the model might send a setup confirmation. Look for any messages about tools being registered.

## What to Look For in Console

When you test again, please share:

1. **Tool registration logs** (from session start)
2. **Full message structure** when you ask to highlight something
3. **Part types** being received
4. **Any error messages** in console

This will help us understand if:
- Tools are registered correctly ✓
- Messages are structured as expected ✓
- Function calls are being made ✓ or ✗
- Our handler is being invoked ✓ or ✗

## Current Status

✅ Enhanced system instruction with explicit rules
✅ Added comprehensive logging
✅ Tool handler properly registered
✅ Build successful

⏳ Waiting to see console output to determine next steps
