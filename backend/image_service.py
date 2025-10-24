"""
Image Fetching Service for R-Hat
Fetches images using Google Custom Search API
"""

import requests
import base64
from io import BytesIO
from PIL import Image
import logging
import os
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageService:
    """Service for fetching and processing images"""

    def __init__(self, google_api_key: Optional[str] = None, google_cse_id: Optional[str] = None):
        """Initialize the image service"""
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = google_cse_id or os.getenv("GOOGLE_CSE_ID")
        self.google_search_url = "https://www.googleapis.com/customsearch/v1"

    def search_google_images(self, query: str) -> Optional[Dict]:
        """
        Search for images using Google Custom Search API

        Args:
            query: Search query

        Returns:
            Image data dict with url, description, and source info
        """
        if not self.google_api_key or not self.google_cse_id:
            logger.warning("Google API key or CSE ID not provided")
            return None

        try:
            params = {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "searchType": "image",
                "num": 1,  # Get first result
                "safe": "active",  # Safe search
                "imgSize": "large"  # Prefer larger images
            }

            response = requests.get(self.google_search_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check if we have results
            items = data.get("items", [])
            if not items:
                logger.warning(f"No images found for query: {query}")
                return None

            # Get first image result
            image = items[0]

            return {
                "url": image["link"],  # Direct image URL
                "description": image.get("title", query),
                "source_page": image.get("image", {}).get("contextLink", ""),
                "thumbnail": image.get("image", {}).get("thumbnailLink", "")
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Google API quota exceeded. Free tier: 100 queries/day")
            else:
                logger.error(f"Google Image Search HTTP error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Google Image Search error: {str(e)}")
            return None

    def fetch_image_from_url(self, url: str, max_width: int = 800) -> str:
        """
        Fetch an image from a URL and return as base64

        Args:
            url: Image URL
            max_width: Maximum width to resize to

        Returns:
            Base64 encoded image string
        """
        try:
            logger.info(f"Fetching image from: {url}")

            # Download image with proper headers (some sites block requests without User-Agent)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Open image with PIL
            img = Image.open(BytesIO(response.content))

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if needed
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {max_width}x{new_height}")

            # Convert to base64
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            img_str = base64.b64encode(buffered.getvalue()).decode()

            logger.info(f"Image processed successfully, size: {len(img_str)} bytes")
            return img_str

        except Exception as e:
            logger.error(f"Image fetch error: {str(e)}")
            raise Exception(f"Failed to fetch image: {str(e)}")

    def get_image(self, query: str) -> Dict:
        """
        Get an image based on a search query

        Args:
            query: Search query for the image

        Returns:
            Dict with image_base64, description, and attribution
        """
        # Check if API credentials are configured
        if not self.google_api_key or not self.google_cse_id:
            raise Exception(
                "Image search requires Google API credentials. "
                "Please set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables. "
                "Get your API key from Google Cloud Console and create a Custom Search Engine at "
                "https://programmable-search.google.com/"
            )

        # Search for image using Google Custom Search
        google_result = self.search_google_images(query)

        if not google_result:
            raise Exception(
                f"No images found for '{query}'. This could be due to: "
                "1) No matching images, 2) API quota exceeded (100/day free), or 3) Network error."
            )

        # Fetch and encode the image
        image_base64 = self.fetch_image_from_url(google_result["url"])

        return {
            "image_base64": image_base64,
            "description": google_result["description"],
            "attribution": f"Image from Google Search",
            "attribution_url": google_result["source_page"]
        }


# Global service instance
_image_service = None


def get_image_service(google_api_key: Optional[str] = None, google_cse_id: Optional[str] = None) -> ImageService:
    """Get or create the global image service instance"""
    global _image_service
    if _image_service is None:
        _image_service = ImageService(google_api_key=google_api_key, google_cse_id=google_cse_id)
    return _image_service
