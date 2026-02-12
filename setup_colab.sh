#!/bin/bash
# One-time setup for Colab image generation pipeline
# Run this once to set everything up, then use run_colab.sh or cron

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  Colab Pipeline Setup"
echo "========================================"

# Step 1: Install rclone if needed
if ! command -v rclone &>/dev/null; then
    echo ""
    echo "[1/4] Installing rclone..."
    sudo apt install -y rclone
else
    echo "[1/4] rclone already installed: $(rclone version | head -1)"
fi

# Step 2: Configure rclone for Google Drive
if ! rclone listremotes 2>/dev/null | grep -q "^gdrive:"; then
    echo ""
    echo "[2/4] Configuring rclone for Google Drive..."
    echo "  When prompted:"
    echo "    - Name: gdrive"
    echo "    - Storage type: google cloud storage → actually choose 'drive' (Google Drive)"
    echo "    - Leave client_id and secret blank"
    echo "    - Scope: 1 (Full access)"
    echo "    - Leave root_folder_id blank"
    echo "    - Leave service_account_file blank"
    echo "    - Auto config: Y"
    echo ""
    rclone config
else
    echo "[2/4] rclone 'gdrive' remote already configured"
fi

# Step 3: Create venv + install selenium
VENV="$SCRIPT_DIR/colab_runner_venv"
if [ ! -f "$VENV/bin/python" ]; then
    echo ""
    echo "[3/4] Creating Python venv + installing selenium..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q selenium
else
    echo "[3/4] Venv already exists with selenium"
fi

# Step 4: Upload notebook to Google Drive
echo ""
echo "[4/4] Uploading notebook to Google Drive..."
NOTEBOOK="$SCRIPT_DIR/spot_difference_colab.ipynb"
if [ -f "$NOTEBOOK" ]; then
    rclone copy "$NOTEBOOK" gdrive: --progress
    echo "  Notebook uploaded to Google Drive root"
    echo ""
    echo "  NEXT STEPS:"
    echo "  1. Go to https://drive.google.com"
    echo "  2. Find 'spot_difference_colab.ipynb' and double-click to open in Colab"
    echo "  3. In Colab: Runtime → Change runtime type → T4 GPU"
    echo "  4. Copy the notebook URL from the browser"
    echo "  5. Set it in colab_runner.py or as env var:"
    echo "     export COLAB_NOTEBOOK_URL='https://colab.research.google.com/drive/YOUR_ID'"
else
    echo "  ERROR: $NOTEBOOK not found!"
    exit 1
fi

# Step 5: Set up cron
echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To set up nightly automation, add this cron job:"
echo "  crontab -e"
echo ""
echo "  # Run Colab at 2 AM, images ready for 8 AM upload"
echo "  0 2 * * * $VENV/bin/python $SCRIPT_DIR/colab_runner.py >> $SCRIPT_DIR/colab_runner.log 2>&1"
echo ""
echo "Or run manually:"
echo "  ./run_colab.sh              # Full run (Selenium + sync)"
echo "  ./run_colab.sh --sync-only  # Just sync from Drive"
