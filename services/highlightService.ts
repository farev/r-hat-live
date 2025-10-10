/**
 * Highlight Service
 * Communicates with the backend SAM2 service to highlight objects
 */

import { HighlightResult } from '../types/tools';

const BACKEND_URL = 'http://localhost:8000';

/**
 * Call the backend /highlight endpoint to detect and segment objects
 */
export async function highlightObject(
  imageBase64: string,
  objectName: string
): Promise<HighlightResult> {
  try {
    console.log(`🎯 Highlighting: ${objectName}`);

    const response = await fetch(`${BACKEND_URL}/highlight`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageBase64,
        object_name: objectName,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend request failed: ${response.status}`);
    }

    const result: HighlightResult = await response.json();

    console.log(`✅ Highlight result:`, {
      success: result.success,
      object_name: result.object_name,
      masks_count: result.masks?.length || 0,
      has_image: !!result.annotated_image
    });

    return result;
  } catch (error) {
    console.error('❌ Highlight service error:', error);
    return {
      success: false,
      object_name: objectName,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Check if the backend service is healthy
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_URL}/health`);
    if (!response.ok) return false;

    const data = await response.json();
    return data.status === 'healthy' && data.model_loaded === true;
  } catch (error) {
    console.error('Backend health check failed:', error);
    return false;
  }
}
