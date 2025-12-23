#!/bin/bash

# Start SharvaYoutubePro app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
PID_FILE="$SCRIPT_DIR/.tauri.pid"
LOG_FILE="$SCRIPT_DIR/.tauri.log"

# Source cargo environment
source "$HOME/.cargo/env" 2>/dev/null

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  restart    Stop the app first, then start"
    echo "  --help     Show this help message"
    echo ""
}

stop_app() {
    "$SCRIPT_DIR/stop.sh"
}

start_app() {
    cd "$APP_DIR"

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "SharvaYoutubePro is already running (PID: $PID)"
            echo "Use '$0 restart' to restart the app"
            exit 1
        fi
        rm -f "$PID_FILE"
    fi

    echo "Starting SharvaYoutubePro..."

    # Start tauri dev in background
    nohup npm run tauri dev > "$LOG_FILE" 2>&1 &
    APP_PID=$!

    echo "$APP_PID" > "$PID_FILE"
    echo "SharvaYoutubePro started (PID: $APP_PID)"
    echo "Logs: $LOG_FILE"
    echo ""
    echo "Use './stop.sh' to stop the app"
}

# Parse arguments
case "$1" in
    restart)
        echo "Restarting SharvaYoutubePro..."
        stop_app
        sleep 2
        start_app
        ;;
    --help|-h)
        show_help
        ;;
    "")
        start_app
        ;;
    *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
