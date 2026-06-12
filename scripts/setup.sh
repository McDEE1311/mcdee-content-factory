#!/bin/bash
# McDEE Content Factory Setup Script
# Run once on taorig1: bash scripts/setup.sh

set -e

echo "=== McDEE Content Factory Setup ==="
echo ""

# Check Python version
python3 --version

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[setup] Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "[setup] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p data logs outputs/upload_packages credentials config

# Copy env example if .env not present
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[setup] Created .env from .env.example — EDIT IT with your API keys."
fi

# Copy channels config if not present
if [ ! -f "config/channels.yaml" ]; then
    cp config/channels.example.yaml config/channels.yaml
    echo "[setup] Created config/channels.yaml — EDIT IT with your channel info."
fi

# Initialize DB
python3 scripts/init_db.py

# Check Ollama
echo ""
echo "[setup] Checking Ollama..."
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "[setup] Ollama: OK"
    echo "[setup] Available models:"
    curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; data=json.load(sys.stdin); [print('  -', m['name']) for m in data.get('models',[])]"
else
    echo "[setup] Ollama: NOT RUNNING — start with 'ollama serve'"
fi

# Check ffmpeg
echo ""
if command -v ffmpeg &> /dev/null; then
    echo "[setup] ffmpeg: OK"
else
    echo "[setup] ffmpeg: NOT FOUND — install with: sudo apt install ffmpeg"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Edit config/channels.yaml"
echo "  3. Run: python3 -m app.main   (health check at http://127.0.0.1:8899/health)"
echo "  4. Run: python3 -m app.workers.daily_run --dry-run"
echo "  5. Run: bash scripts/pm2_start.sh"
