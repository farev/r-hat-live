# R-Hat Backend - Grounded-SAM 2 Highlight Service

This backend service provides object detection and segmentation using Grounded-SAM 2.

## Setup

### 1. Create Python Virtual Environment

```bash
cd backend
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install PyTorch (adjust for your CUDA version if needed)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install other requirements
pip install -r requirements.txt
```

### 3. Install Grounded-SAM 2

```bash
# Clone the repository
git clone https://github.com/IDEA-Research/Grounded-SAM-2.git
cd Grounded-SAM-2

# Install SAM 2
pip install -e .

# Install Grounding DINO
pip install --no-build-isolation -e grounding_dino

cd ..
```

### 4. Download Model Checkpoints

Download the following checkpoints and place them in `backend/models/`:

**SAM 2 Checkpoint:**
```bash
mkdir -p models
cd models

# Download SAM 2 large checkpoint
wget https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt

# Or use curl
curl -L -o sam2_hiera_large.pt https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt
```

**Grounding DINO Checkpoint:**
```bash
# Download Grounding DINO checkpoint
wget https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

# Or use curl
curl -L -o groundingdino_swint_ogc.pth https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

cd ..
```

### 5. Run the Server

```bash
# Make sure you're in the backend directory with venv activated
python sam2_service.py
```

The server will start at `http://localhost:8000`

## API Endpoints

### POST /highlight

Highlights objects in an image using text prompts.

**Request:**
```json
{
  "image": "base64_encoded_image_string",
  "object_name": "cup"
}
```

**Response:**
```json
{
  "success": true,
  "object_name": "cup",
  "masks": [
    {
      "box": [x1, y1, x2, y2],
      "confidence": 0.95
    }
  ],
  "annotated_image": "base64_encoded_annotated_image"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

## Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test highlight endpoint (requires base64 image)
# See test_backend.py for example
```

## Troubleshooting

**Issue: CUDA out of memory**
- Solution: Use SAM 2 small model instead: `sam2_hiera_small.pt`
- Or reduce image resolution before processing

**Issue: Import errors**
- Solution: Make sure Grounded-SAM-2 is properly installed
- Check that you're using Python 3.10

**Issue: Model download fails**
- Solution: Manually download from URLs above
- Place in `backend/models/` directory
