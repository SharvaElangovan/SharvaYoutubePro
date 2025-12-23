#!/bin/bash

# Stop SharvaYoutubePro app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
PID_FILE="$SCRIPT_DIR/.tauri.pid"

stop_app() {
    # Kill by PID file if exists
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping SharvaYoutubePro (PID: $PID)..."
            kill "$PID" 2>/dev/null
            sleep 1
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # Also kill any remaining processes
    pkill -f "sharva-youtube-pro" 2>/dev/null
    pkill -f "npm run tauri" 2>/dev/null

    # Kill vite dev server on port 5173
    lsof -ti:5173 | xargs -r kill 2>/dev/null

    echo "SharvaYoutubePro stopped."
}

stop_app
