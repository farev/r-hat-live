"""
Test SAM-2 Automatic Mask Generation - Visualize all object masks
Usage: python test_sam2.py <path_to_image>

SAM-2 will automatically generate masks for all objects in the image.
This uses the "automatic mask generation" mode which doesn't require prompts.
"""

import sys
import cv2
import numpy as np
import torch
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

# Fix for PyTorch 2.6 weights_only issue
import os
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'


def draw_masks(image, masks):
    """
    Draw all masks on the image with different colors

    Args:
        image: Input image as numpy array (RGB format)
        masks: List of mask dictionaries from SAM2AutomaticMaskGenerator
               Each mask contains: 'segmentation', 'area', 'bbox', 'predicted_iou', 'stability_score'

    Returns:
        Image with colored masks overlay
    """
    img_copy = image.copy()
    h, w = image.shape[:2]

    print(f"\n{'='*80}")
    print(f"Image size: {w}x{h}")
    print(f"Total masks generated: {len(masks)}")
    print(f"{'='*80}\n")

    # Create a blank overlay
    overlay = np.zeros_like(image, dtype=np.uint8)

    # Sort masks by area (largest first) so small objects are drawn on top
    sorted_masks = sorted(masks, key=lambda x: x['area'], reverse=True)

    for i, mask_data in enumerate(sorted_masks):
        # Get the binary mask
        mask = mask_data['segmentation']

        # Generate a random color for this mask
        color = np.random.randint(0, 255, size=3, dtype=np.uint8)

        # Apply color to the overlay where mask is True
        overlay[mask] = color

        # Get bounding box (in XYWH format)
        bbox = mask_data['bbox']
        x, y, width, height = [int(v) for v in bbox]

        # Draw bounding box
        cv2.rectangle(img_copy, (x, y), (x + width, y + height), color.tolist(), 2)

        # Add label
        label = f"#{i+1}"
        cv2.putText(img_copy, label, (x, y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color.tolist(), 2)

        # Print mask info
        print(f"Mask #{i+1}:")
        print(f"  Area: {mask_data['area']} pixels")
        print(f"  BBox: x={x}, y={y}, w={width}, h={height}")
        print(f"  Predicted IoU: {mask_data.get('predicted_iou', 'N/A'):.4f}")
        print(f"  Stability Score: {mask_data.get('stability_score', 'N/A'):.4f}")
        print()

    # Blend the overlay with the original image
    alpha = 0.5
    result = cv2.addWeighted(img_copy, 1 - alpha, overlay, alpha, 0)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_sam2.py <path_to_image>")
        print("\nThis script uses SAM-2's automatic mask generation mode.")
        print("It will automatically detect and segment all objects in the image.")
        print("\nExamples:")
        print("  python test_sam2.py test_image.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    print(f"Loading image: {image_path}")
    # Load image in RGB format
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)

    # Convert BGR to RGB for SAM-2
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load SAM-2 model
    print("Loading SAM-2.1 Hiera Large model...")
    sam2_checkpoint = "./models/sam2.1_hiera_large.pt"
    model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"

    try:
        sam2_model = build_sam2(model_cfg, sam2_checkpoint, device=device)
        print("SAM-2 model loaded successfully!")
    except Exception as e:
        print(f"Error loading SAM-2 model: {e}")
        print("\nMake sure you have:")
        print("1. SAM-2 model weights in ./models/sam2.1_hiera_large.pt")
        print("2. SAM-2 config in ./configs/sam2.1/sam2.1_hiera_l.yaml")
        print("3. SAM-2 installed: pip install git+https://github.com/facebookresearch/segment-anything-2.git")
        sys.exit(1)

    # Create automatic mask generator
    print("Initializing SAM-2 Automatic Mask Generator...")
    mask_generator = SAM2AutomaticMaskGenerator(
        model=sam2_model,
        points_per_side=32,  # Higher = more masks, slower
        pred_iou_thresh=0.7,  # IoU threshold for keeping masks
        stability_score_thresh=0.85,  # Stability threshold
        crop_n_layers=1,
        crop_n_points_downscale_factor=2,
        min_mask_region_area=100,  # Minimum mask area in pixels
    )

    # Generate masks
    print("Generating masks... (this may take a moment)")
    masks = mask_generator.generate(image_rgb)

    # Draw masks
    result_image = draw_masks(image_rgb, masks)

    # Convert back to BGR for saving
    result_bgr = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)

    # Save result
    output_path = image_path.rsplit('.', 1)[0] + '_sam2_masks.jpg'
    cv2.imwrite(output_path, result_bgr)
    print(f"{'='*80}")
    print(f"Result saved to: {output_path}")
    print(f"{'='*80}\n")

    # Display if possible
    try:
        cv2.imshow('SAM-2 Masks (Press any key to close)', result_bgr)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except:
        print("(Display not available, but image was saved)")


if __name__ == "__main__":
    main()
