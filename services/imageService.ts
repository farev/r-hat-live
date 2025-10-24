import { DisplayedImage } from '../types/tools';

const BACKEND_URL = 'http://localhost:8000';

/**
 * Fetch an image from the backend based on a search query
 *
 * @param query - The search query for the image
 * @returns Promise with image data including base64, description, and attribution
 */
export async function fetchImage(query: string): Promise<Omit<DisplayedImage, 'id'>> {
  try {
    const response = await fetch(`${BACKEND_URL}/fetch-image`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Image fetch request failed');
    }

    const data = await response.json();

    return {
      image_base64: data.image_base64,
      description: data.description,
      attribution: data.attribution,
    };

  } catch (error) {
    console.error('Image service error:', error);
    throw error;
  }
}
