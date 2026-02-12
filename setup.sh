#!/bin/bash
set -e

echo "=== WarGame Setup ==="
echo

# Check Python
echo "[1/4] Checking Python..."
python3 --version || { echo "ERROR: Python 3 not found"; exit 1; }

# Install dependencies
echo "[2/4] Installing Python dependencies..."
pip3 install -r requirements.txt

# Check Ollama
echo "[3/4] Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "Ollama found!"
else
    echo "Ollama not found. Install from: https://ollama.com/download"
    echo "After installing, run: ollama serve"
    exit 1
fi

# Pull model
echo "[4/4] Pulling DeepSeek R1 32B model (~20GB download)..."
echo "This may take a while on first run..."
ollama pull deepseek-r1:32b

echo
echo "=== Setup Complete! ==="
echo "Start the game with: python3 run.py"
echo "Or with fewer countries: python3 run.py --countries PL RU US DE"
