#!/usr/bin/env python3
"""
Daily Spot the Difference Upload Script
Uses pre-generated images from Colab (Google Drive sync) or falls back to local SD.
"""

import os
import sys
import json
import glob
import sqlite3
import random
import urllib.request
import urllib.parse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_GEN_PATH = os.path.join(SCRIPT_DIR, "video_generator")
sys.path.insert(0, VIDEO_GEN_PATH)

# Pre-generated images from Colab (synced via rclone from Google Drive)
COLAB_IMAGES_DIR = os.path.join(SCRIPT_DIR, "spot_difference_images")

# Fallback: local SD venv
SD_VENV = os.path.expanduser("~/stable-diffusion-webui/venv")
SD_PYTHON = os.path.join(SD_VENV, "bin", "python")

DB_PATH = os.path.expanduser("~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db")
LOG_FILE = os.path.join(SCRIPT_DIR, "spot_difference_upload.log")

def log(msg):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_setting(key):
    """Get setting from database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def refresh_token():
    """Refresh OAuth token."""
    client_id = get_setting('youtube_client_id')
    client_secret = get_setting('youtube_client_secret')
    refresh_tok = get_setting('youtube_refresh_token')

    if not all([client_id, client_secret, refresh_tok]):
        return None

    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_tok,
        'grant_type': 'refresh_token'
    }).encode()

    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            new_token = result.get('access_token')
            if new_token:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("UPDATE settings SET value = ? WHERE key = 'youtube_access_token'", (new_token,))
                conn.commit()
                conn.close()
            return new_token
    except Exception as e:
        log(f"Token refresh failed: {e}")
        return None

def get_token():
    """Get valid OAuth token."""
    token = get_setting('youtube_access_token')
    if not token:
        token = refresh_token()
    return token

def upload_video(video_path, title, description, is_short=False):
    """Upload video to YouTube."""
    token = get_token()
    if not token:
        return None, "NO_TOKEN"

    # Video metadata
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["spot the difference", "puzzle", "find differences", "brain game", "visual puzzle"],
            "categoryId": "20"  # Gaming
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    if is_short:
        metadata["snippet"]["tags"].append("shorts")

    # Resumable upload
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(os.path.getsize(video_path))
    }

    req = urllib.request.Request(init_url, data=json.dumps(metadata).encode(), headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            upload_url = resp.headers.get("Location")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if "quotaExceeded" in error_body or "uploadLimitExceeded" in error_body:
            return None, "QUOTA_EXCEEDED"
        log(f"Upload init error: {e.code} - {error_body[:200]}")
        return None, f"INIT_ERROR_{e.code}"
    except Exception as e:
        return None, str(e)

    # Upload video file
    with open(video_path, 'rb') as f:
        video_data = f.read()

    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "video/mp4",
        "Content-Length": str(len(video_data))
    }

    upload_req = urllib.request.Request(upload_url, data=video_data, headers=upload_headers)

    try:
        with urllib.request.urlopen(upload_req, timeout=600) as resp:
            result = json.loads(resp.read().decode())
            return result.get("id"), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if "quotaExceeded" in error_body or "uploadLimitExceeded" in error_body:
            return None, "QUOTA_EXCEEDED"
        return None, f"UPLOAD_ERROR_{e.code}"
    except Exception as e:
        return None, str(e)

def generate_title(num_puzzles):
    """Generate a catchy title."""
    import random
    templates = [
        f"IMPOSSIBLE Spot The Difference - {num_puzzles} HARD Puzzles!",
        f"Find ALL 5 Differences - Only Geniuses Can! {num_puzzles} Levels",
        f"99% FAIL This Spot The Difference Challenge!",
        f"EXTREME Spot The Difference - Can You Beat It?",
        f"Genius IQ Test: Find The Hidden Differences - {num_puzzles} Puzzles",
        f"The HARDEST Spot The Difference You'll Ever See!",
    ]
    return random.choice(templates)

def generate_description(num_puzzles):
    """Generate video description."""
    return f"""🔍 EXTREME Spot The Difference Challenge!

Can you find ALL 5 hidden differences in these {num_puzzles} HARD puzzles?

🧠 This is NOT your average spot the difference game - these are TINY, SUBTLE changes!

⏱️ You have 100 SECONDS per puzzle - you'll need every second!

👁️ Look VERY carefully at every pixel - the differences are almost invisible!

🏆 Only TRUE geniuses can find them all!

Comment below how many you found! 👇

#SpotTheDifference #Puzzle #BrainGame #FindTheDifference #IQTest #HardPuzzle #Genius
"""

def get_colab_pairs(count=5):
    """Get pre-generated image pairs from Colab sync folder.

    Looks for pairs: pair_001_original.png + pair_001_modified.png
    Returns list of (original_path, modified_path) tuples.
    """
    if not os.path.exists(COLAB_IMAGES_DIR):
        return []

    originals = sorted(glob.glob(os.path.join(COLAB_IMAGES_DIR, "pair_*_original.png")))
    pairs = []
    for orig_path in originals:
        mod_path = orig_path.replace("_original.png", "_modified.png")
        if os.path.exists(mod_path):
            pairs.append((orig_path, mod_path))

    if len(pairs) >= count:
        return random.sample(pairs, count)
    return pairs


def generate_with_colab_pairs(image_pairs, output_filename, puzzle_time, reveal_time):
    """Generate video using FLUX Kontext pre-made pairs (original + modified)."""
    from generators import SpotDifferenceGenerator

    gen = SpotDifferenceGenerator()
    output_path = gen.generate_from_pairs(
        image_pairs=image_pairs,
        num_differences=5,
        puzzle_time=puzzle_time,
        reveal_time=reveal_time,
        output_filename=output_filename,
    )
    return output_path


def generate_with_local_sd(output_filename, num_puzzles, puzzle_time, reveal_time):
    """Fallback: Generate video using local Stable Diffusion."""
    import subprocess

    gen_script = f'''
import sys
sys.path.insert(0, "{VIDEO_GEN_PATH}")
from generators import SpotDifferenceGenerator

gen = SpotDifferenceGenerator()
gen.generate_with_sd(
    num_puzzles={num_puzzles},
    puzzle_time={puzzle_time},
    reveal_time={reveal_time},
    num_differences=5,
    output_filename="{output_filename}"
)
print("VIDEO_GENERATED")
'''

    result = subprocess.run(
        [SD_PYTHON, "-c", gen_script],
        capture_output=True,
        text=True,
        timeout=600
    )

    output_path = os.path.join(VIDEO_GEN_PATH, "output", output_filename)
    if "VIDEO_GENERATED" in result.stdout or os.path.exists(output_path):
        return output_path
    return None


def main():
    log("=" * 60)
    log("SPOT THE DIFFERENCE DAILY UPLOAD")
    log("=" * 60)

    # Check for token
    if not get_token():
        log("ERROR: No YouTube token. Please authenticate via the app first.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"spot_diff_{timestamp}.mp4"
    output_path = os.path.join(VIDEO_GEN_PATH, "output", output_filename)

    num_puzzles = 5
    puzzle_time = 100  # 100 seconds per puzzle
    reveal_time = 8

    # Try Colab pre-generated pairs first (SDXL base + FLUX Kontext differences)
    colab_pairs = get_colab_pairs(num_puzzles)
    if len(colab_pairs) >= num_puzzles:
        log(f"Using {len(colab_pairs)} Colab pairs (SDXL + FLUX Kontext)")
        try:
            result_path = generate_with_colab_pairs(
                colab_pairs, output_filename, puzzle_time, reveal_time
            )
            if result_path and os.path.exists(result_path):
                output_path = result_path
                # Remove used pairs so they aren't reused
                for orig, mod in colab_pairs:
                    for f in (orig, mod):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                log(f"Video generated from Colab pairs: {output_path}")
            else:
                log("Colab pair video generation failed, falling back to local SD")
                colab_pairs = []
        except Exception as e:
            log(f"Colab pair generation error: {e}, falling back to local SD")
            colab_pairs = []

    # Fallback: local Stable Diffusion
    if not os.path.exists(output_path):
        log(f"Generating {num_puzzles} puzzles with local Stable Diffusion...")
        result_path = generate_with_local_sd(output_filename, num_puzzles, puzzle_time, reveal_time)
        if result_path:
            output_path = result_path
        else:
            log("Video generation failed (both Colab and local SD)")
            return

    if not os.path.exists(output_path):
        log("Video file not found after generation")
        return

    log(f"Video generated: {output_path}")

    # Upload
    title = generate_title(num_puzzles)
    description = generate_description(num_puzzles)

    log(f"Uploading: {title}")
    video_id, error = upload_video(output_path, title, description)

    # Clean up video
    try:
        os.remove(output_path)
    except Exception:
        pass

    if video_id:
        log(f"✓ Uploaded: https://youtube.com/watch?v={video_id}")
    else:
        log(f"✗ Upload failed: {error}")

    log("=" * 60)
    log("DAILY UPLOAD COMPLETE")
    log("=" * 60)

if __name__ == "__main__":
    main()
