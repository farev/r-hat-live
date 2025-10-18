"""
Test CLIP directly - Compare an image to text prompts
Usage: python test_clip.py <path_to_image> <text_query1> [text_query2] [text_query3] ...
"""

import sys
import cv2
import numpy as np
import clip
import torch
from PIL import Image

def test_clip(image_path, text_queries):
    """Test CLIP with an image and multiple text queries"""

    # Load CLIP model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP ViT-L/14 on {device}...")
    model, preprocess = clip.load("ViT-L/14", device=device)
    print("CLIP loaded!\n")

    # Load image
    print(f"Loading image: {image_path}")
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)

    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image_pil = Image.fromarray(image_rgb)

    print(f"Image size: {image_bgr.shape[1]}x{image_bgr.shape[0]}")
    print(f"Text queries: {text_queries}\n")

    # Preprocess image
    image_input = preprocess(image_pil).unsqueeze(0).to(device)
    text_inputs = clip.tokenize(text_queries).to(device)

    # Calculate features
    with torch.no_grad():
        image_features = model.encode_image(image_input)
        text_features = model.encode_text(text_inputs)

        # Normalize features
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        # Calculate cosine similarity
        similarities = (image_features @ text_features.T).squeeze()

        # Handle single query case
        if len(text_queries) == 1:
            similarities = similarities.unsqueeze(0)

    # Print results
    print("=" * 80)
    print("CLIP Similarity Scores:")
    print("=" * 80)

    for query, score in zip(text_queries, similarities):
        score_val = float(score)
        # Create a visual bar
        bar_length = int(score_val * 50)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"{query:30s} | {score_val:.4f} | {bar}")

    print("=" * 80)

    # Show which query matched best
    best_idx = similarities.argmax()
    best_score = float(similarities[best_idx])
    print(f"\nBest match: '{text_queries[best_idx]}' with score {best_score:.4f}")

    # Interpretation guide
    print("\nScore interpretation:")
    print("  > 0.30: Strong match")
    print("  0.20-0.30: Good match")
    print("  0.15-0.20: Weak match")
    print("  < 0.15: Poor match")


def main():
    if len(sys.argv) < 3:
        print("Usage: python test_clip.py <image_path> <text_query1> [text_query2] [text_query3] ...")
        print("\nExamples:")
        print("  python test_clip.py test.jpg 'phone'")
        print("  python test_clip.py test.jpg 'phone' 'person' 'laptop' 'cup'")
        print("  python test_clip.py test.jpg 'a red flashlight' 'a person holding something' 'electronic device'")
        sys.exit(1)

    image_path = sys.argv[1]
    text_queries = sys.argv[2:]

    test_clip(image_path, text_queries)


if __name__ == "__main__":
    main()
