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
  tracking_duration_seconds?: number;
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
  description: "Highlights and identifies objects in the camera view by drawing bounding boxes around them. Use this when the user asks to show, highlight, point out, or locate specific objects.",
  parameters: {
    type: "object",
    properties: {
      object_name: {
        type: "string",
        description: "The name of the object to highlight in the camera view (e.g., 'cup', 'laptop', 'person', 'phone')"
      },
      tracking_duration_seconds: {
        type: "number",
        description: "Optional duration in seconds to keep the tracker active. Use shorter durations (2-5s) for quick callouts and longer ones (10-30s) when the user needs more time with the object."
      },
    },
    required: ["object_name"]
  }
};

// Image display tool specific types
export interface DisplayImageArgs {
  query: string;
}

export interface DisplayedImage {
  id: string;
  image_base64: string;
  description: string;
  attribution: string;
}

// YouTube tool specific types
export interface PlayYouTubeArgs {
  query: string;
  timestamp?: number; // seconds
}

export interface YouTubeVideo {
  video_id: string;
  title: string;
  url: string;
  start_time: number;
  channel_title?: string;
  description?: string;
  thumbnail_url?: string;
}

export interface YouTubeToolResult {
  video: YouTubeVideo;
  rawResponse?: any;
}

// Checklist tool specific types
export interface ChecklistItemInput {
  id?: string;
  label: string;
  completed?: boolean;
}

export interface ChecklistItem {
  id: string;
  label: string;
  completed: boolean;
}

export interface ChecklistUpdateArgs {
  title?: string;
  items?: ChecklistItemInput[];
  clear?: boolean;
  completedItems?: string[];
  incompleteItems?: string[];
  toggleItems?: string[];
}

// Timer tool specific types
export interface StartTimerArgs {
  /**
   * Duration to set the timer for, in seconds. Example: 300 for 5 minutes.
   */
  time: number;
}
