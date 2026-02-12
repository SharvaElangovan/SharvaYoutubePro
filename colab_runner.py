#!/usr/bin/env python3
"""
Colab Runner - Selenium automation to run Colab notebook at night.
Generates spot-the-difference images on Colab's free T4 GPU,
saves to Google Drive, then syncs to local PC.

Usage:
    python colab_runner.py              # Run Colab notebook + sync images
    python colab_runner.py --headless   # Run headless (for cron at night)
    python colab_runner.py --sync-only  # Just sync images from Drive

Cron (run at 2 AM, images ready for 8 AM upload):
    0 2 * * * /path/to/venv/bin/python /path/to/colab_runner.py --headless >> /path/to/colab_runner.log 2>&1
"""

import os
import sys
import time
import glob
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "colab_runner.log")

# Colab notebook URL
COLAB_NOTEBOOK_URL = os.environ.get(
    "COLAB_NOTEBOOK_URL",
    "https://colab.research.google.com/drive/1f0T_JhQaVtCwncEg0qx46YE7kBhNNYLm"
)

# Local folder to sync images into
LOCAL_IMAGES_DIR = os.path.join(SCRIPT_DIR, "spot_difference_images")

# Google Drive remote folder (rclone remote name : path)
GDRIVE_REMOTE = "gdrive:spot_difference_images"

# Firefox profile (snap Firefox - already logged into Google)
FIREFOX_PROFILE = os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/6nzsg7ue.default")

# How long to wait for Colab to finish (seconds)
# SDXL: ~15min for 50 images, FLUX Kontext: ~90min for 50 images with CPU offloading
MAX_WAIT_TIME = 150 * 60  # 2.5 hours


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_colab_notebook():
    """Use Selenium + Firefox to open Colab notebook and click Run All."""
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
    except ImportError:
        log("ERROR: selenium not installed. Run: pip install selenium")
        return False

    log("Starting Firefox with Selenium...")

    headless = "--headless" in sys.argv

    options = Options()
    # Snap Firefox: selenium needs the real binary, not the /usr/bin wrapper
    options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
    # Use existing Firefox profile (already logged into Google)
    options.profile = FIREFOX_PROFILE
    if headless:
        options.add_argument("--headless")

    driver = None
    try:
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(60)
        driver.set_window_size(1920, 1080)

        # Open the Colab notebook
        log(f"Opening notebook: {COLAB_NOTEBOOK_URL}")
        driver.get(COLAB_NOTEBOOK_URL)
        time.sleep(15)  # Wait for Colab to fully load

        # Check if we need to sign in
        if "accounts.google.com" in driver.current_url or "signin" in driver.current_url.lower():
            log("ERROR: Not logged into Google in Firefox.")
            log("  Open Firefox manually, log into Google, then try again.")
            return False

        log("Colab loaded. Sending Ctrl+F9 (Run All)...")
        ActionChains(driver).key_down(Keys.CONTROL).send_keys(Keys.F9).key_up(Keys.CONTROL).perform()
        time.sleep(5)

        # Handle "Run anyway" dialog (for notebooks not authored by you)
        try:
            run_anyway = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//*[contains(text(), 'Run anyway') or contains(text(), 'RUN ANYWAY')]"
                ))
            )
            run_anyway.click()
            log("Clicked 'Run anyway' confirmation")
        except TimeoutException:
            log("No 'Run anyway' dialog (or already dismissed)")

        time.sleep(5)

        # Wait for execution to complete
        log(f"Waiting for notebook execution (max {MAX_WAIT_TIME // 60} min)...")
        start_time = time.time()

        while time.time() - start_time < MAX_WAIT_TIME:
            time.sleep(30)
            elapsed = int(time.time() - start_time)
            log(f"  Waiting... ({elapsed}s elapsed)")

            try:
                # Check for completion marker in page output
                page_source = driver.page_source
                if "ALL_IMAGES_GENERATED" in page_source:
                    log("Found completion marker - notebook finished!")
                    break

                # Check for errors
                if "ResourceExhausted" in page_source or "out of memory" in page_source.lower():
                    log("GPU OOM detected - notebook may have failed")
                    break
            except Exception:
                pass

        elapsed_total = int(time.time() - start_time)
        log(f"Colab execution finished (or timed out) after {elapsed_total}s")
        return True

    except Exception as e:
        log(f"Selenium error: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def sync_from_drive():
    """Sync images from Google Drive to local folder using rclone."""
    os.makedirs(LOCAL_IMAGES_DIR, exist_ok=True)

    # Check rclone is installed
    try:
        subprocess.run(["rclone", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        log("ERROR: rclone not installed. Run: sudo apt install rclone")
        return False

    log(f"Syncing images from {GDRIVE_REMOTE} to {LOCAL_IMAGES_DIR}...")

    result = subprocess.run(
        ["rclone", "sync", GDRIVE_REMOTE, LOCAL_IMAGES_DIR, "--progress", "-v"],
        capture_output=True,
        text=True,
        timeout=300
    )

    if result.returncode == 0:
        # Count synced pairs
        originals = glob.glob(os.path.join(LOCAL_IMAGES_DIR, "pair_*_original.png"))
        modifieds = glob.glob(os.path.join(LOCAL_IMAGES_DIR, "pair_*_modified.png"))
        log(f"Sync complete! {len(originals)} originals, {len(modifieds)} modified images")
        return True
    else:
        log(f"Sync failed: {result.stderr[:500]}")
        return False


def get_available_pairs():
    """Get list of complete image pairs ready for video generation."""
    if not os.path.exists(LOCAL_IMAGES_DIR):
        return []
    originals = sorted(glob.glob(os.path.join(LOCAL_IMAGES_DIR, "pair_*_original.png")))
    pairs = []
    for orig_path in originals:
        mod_path = orig_path.replace("_original.png", "_modified.png")
        if os.path.exists(mod_path):
            pairs.append((orig_path, mod_path))
    return pairs


def main():
    log("=" * 60)
    log("COLAB RUNNER - SDXL + FLUX Kontext Image Pair Generator")
    log("=" * 60)

    sync_only = "--sync-only" in sys.argv

    if not sync_only:
        if "YOUR_NOTEBOOK_ID_HERE" in COLAB_NOTEBOOK_URL:
            log("ERROR: Set COLAB_NOTEBOOK_URL env var or update the URL in this script")
            log("  export COLAB_NOTEBOOK_URL='https://colab.research.google.com/drive/YOUR_ID'")
            return

        # Run the Colab notebook
        success = run_colab_notebook()
        if not success:
            log("Colab execution failed - will try to sync anyway")

        # Wait a bit for Drive to sync
        log("Waiting 60s for Google Drive to sync...")
        time.sleep(60)

    # Sync images from Drive to local
    sync_success = sync_from_drive()

    if sync_success:
        pairs = get_available_pairs()
        log(f"Ready: {len(pairs)} complete pairs ({len(pairs) // 5} videos worth)")
    else:
        log("Sync failed - check rclone config")

    log("=" * 60)
    log("COLAB RUNNER COMPLETE")
    log("=" * 60)


if __name__ == "__main__":
    main()
