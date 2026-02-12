#!/bin/bash
# Run Colab notebook automation + sync images from Google Drive
# Usage:
#   ./run_colab.sh              # Run Colab notebook + sync images
#   ./run_colab.sh --sync-only  # Just sync images from Drive

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/colab_runner_venv"

# Check venv exists
if [ ! -f "$VENV/bin/python" ]; then
    echo "Creating venv..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install selenium
fi

# Check rclone
if ! command -v rclone &>/dev/null; then
    echo "ERROR: rclone not installed. Run: sudo apt install rclone"
    echo "Then configure: rclone config  (choose Google Drive, name it 'gdrive')"
    exit 1
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/colab_runner.py" "$@"
