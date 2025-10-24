/**
 * YouTube Service
 * Communicates with the backend API to retrieve YouTube videos.
 */

import { YouTubeVideo } from '../types/tools';

const BACKEND_URL = 'http://localhost:8000';

interface YouTubeSearchResponse {
  video_id: string;
  title: string;
  url: string;
  start_time: number;
  channel_title?: string;
  description?: string;
  thumbnail_url?: string;
}

export async function searchYouTubeVideo(
  query: string,
  timestamp?: number
): Promise<YouTubeVideo> {
  const response = await fetch(`${BACKEND_URL}/youtube/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      timestamp,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const message =
      errorBody?.detail ||
      `YouTube search failed with status ${response.status}`;
    throw new Error(message);
  }

  const data: YouTubeSearchResponse = await response.json();

  return {
    video_id: data.video_id,
    title: data.title,
    url: data.url,
    start_time: data.start_time,
    channel_title: data.channel_title,
    description: data.description,
    thumbnail_url: data.thumbnail_url,
  };
}
