#!/bin/bash
# Setup script for R-Hat Backend

set -e  # Exit on error

echo "🚀 Starting R-Hat Backend Setup..."

# Check Python version
echo "📍 Checking Python version..."
python3 --version

# Create virtual environment
echo "📦 Creating virtual environment..."
python3.10 -m venv venv || python3 -m venv venv

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install PyTorch (CPU version - change if you have CUDA)
echo "🔥 Installing PyTorch..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install requirements
echo "📋 Installing requirements..."
pip install -r requirements.txt

# Clone Grounded-SAM-2 if not exists
if [ ! -d "Grounded-SAM-2" ]; then
    echo "📥 Cloning Grounded-SAM-2..."
    git clone https://github.com/IDEA-Research/Grounded-SAM-2.git
fi

# Install SAM 2
echo "🎯 Installing SAM 2..."
cd Grounded-SAM-2
pip install -e .

# Install Grounding DINO
echo "🎯 Installing Grounding DINO..."
pip install --no-build-isolation -e grounding_dino

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Download model checkpoints (see backend/models/README.md)"
echo ""
echo "3. Run the server:"
echo "   python sam2_service.py"
