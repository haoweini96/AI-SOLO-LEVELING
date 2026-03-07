#!/bin/bash
echo ""
echo "  ⚔️  Setting up AI Solo Leveling..."
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy environment variables template
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  📝 Created .env — please add your API keys"
fi

# Create required directories
mkdir -p logs data/study_analyses data/study_frames data/thumbnails

echo ""
echo "  ✅ Setup complete!"
echo ""
echo "  To start:"
echo "    source venv/bin/activate"
echo "    python3 api_server.py"
echo ""
echo "  Then open http://localhost:8081 in your browser"
echo ""
echo "  ⚔️ Arise, Shadow Monarch!"
echo ""
