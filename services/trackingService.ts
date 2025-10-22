/**
 * Tracking Service
 * Handles communication with the backend tracking API
 */

const BACKEND_URL = 'http://localhost:8000';

export interface TrackedObject {
  tracker_id: string;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  label: string;
  confidence: number;
  status: 'tracking' | 'lost';
}

export interface HighlightResponse {
  tracker_id: string;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  label: string;
  confidence: number;
  yolo_class: string;
}

/**
 * Highlight an object in the video frame
 */
export async function highlightObject(
  imageBase64: string,
  textQuery: string
): Promise<HighlightResponse> {
  const response = await fetch(`${BACKEND_URL}/highlight`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      image: imageBase64,
      text_query: textQuery,
      confidence_threshold: 0.25,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to highlight object');
  }

  return response.json();
}

/**
 * Update all active trackers with new frame
 */
export async function updateTrackers(
  imageBase64: string,
  trackerIds?: string[]
): Promise<Record<string, TrackedObject>> {
  const response = await fetch(`${BACKEND_URL}/track/update`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      image: imageBase64,
      tracker_ids: trackerIds,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update trackers');
  }

  const data = await response.json();
  return data.tracks;
}

/**
 * Remove a specific tracker
 */
export async function removeTracker(trackerId: string): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/track/remove`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tracker_id: trackerId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to remove tracker');
  }
}

/**
 * Clear all trackers
 */
export async function clearAllTrackers(): Promise<void> {
  const response = await fetch(`${BACKEND_URL}/track/clear`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to clear trackers');
  }
}

/**
 * Get backend status
 */
export async function getBackendStatus() {
  const response = await fetch(`${BACKEND_URL}/status`);

  if (!response.ok) {
    throw new Error('Failed to get backend status');
  }

  return response.json();
}

/**
 * Convert canvas to base64 image
 */
export function canvasToBase64(canvas: HTMLCanvasElement): string {
  return canvas.toDataURL('image/jpeg', 0.8);
}
