// Tool-related types for Gemini Live API function calling

export interface FunctionCall {
  name: string;
  id: string;
  args: Record<string, any>;
}

export interface FunctionResponse {
  name: string;
  id: string;
  response: {
    result: any;
    error?: string;
  };
}

// Highlight tool specific types
export interface HighlightToolArgs {
  object_name: string;
}

export interface HighlightResult {
  success: boolean;
  object_name: string;
  masks?: Array<{
    box: [number, number, number, number]; // [x1, y1, x2, y2]
    confidence: number;
  }>;
  annotated_image?: string; // base64 encoded image
  error?: string;
}

// Tool declaration for Gemini
export interface ToolDeclaration {
  name: string;
  description: string;
  parameters?: {
    type: string;
    properties: Record<string, any>;
    required: string[];
  };
}

// Highlight tool declaration following Gemini's function calling schema
export const highlightToolDeclaration: ToolDeclaration = {
  name: "highlight_object",
  description: "Highlights and identifies objects in the camera view by drawing bounding boxes and segmentation masks around them. Use this when the user asks to show, highlight, point out, or locate specific objects.",
  parameters: {
    type: "object",
    properties: {
      object_name: {
        type: "string",
        description: "The name of the object to highlight in the camera view (e.g., 'cup', 'laptop', 'person', 'phone')"
      }
    },
    required: ["object_name"]
  }
};
