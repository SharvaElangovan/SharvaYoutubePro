#!/bin/bash
# Run the AI-Powered JSON Generator

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "============================================"
    echo "  Ollama not found!"
    echo "============================================"
    echo ""
    echo "Please install Ollama first:"
    echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
    echo "Then pull a model:"
    echo "  ollama pull llama3.2"
    echo ""
    echo "And start Ollama:"
    echo "  ollama serve"
    echo ""
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama in background..."
    ollama serve &
    sleep 3
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

python3 ai_json_generator.py
