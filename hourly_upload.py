#!/usr/bin/env python3
"""
Hourly YouTube Upload Script - Spreads uploads throughout the day
Run this every hour via cron: 0 * * * * /path/to/python hourly_upload.py
Uploads ~4 videos per hour (2 shorts + 2 longform) = ~96 videos/day
"""

import subprocess
import sqlite3
import os
import sys
import json
import time
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_GEN_PATH = os.path.join(SCRIPT_DIR, "video_generator")
DB_PATH = "/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db"
OUTPUT_DIR = os.path.join(VIDEO_GEN_PATH, "output")
LOG_FILE = os.path.join(SCRIPT_DIR, "hourly_upload.log")

# Config
SHORTS_PER_HOUR = 2
LONGFORM_PER_HOUR = 2
DELAY_BETWEEN_UPLOADS = 60  # seconds

sys.path.insert(0, VIDEO_GEN_PATH)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_questions(count, for_shorts=False, difficulty=None):
    """Fetch unused questions from database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    length_filter = "BETWEEN 20 AND 120" if for_shorts else "BETWEEN 20 AND 200"
    diff_filter = ""
    if difficulty == 'easy':
        diff_filter = "AND difficulty IN (1, 2)"
    elif difficulty == 'hard':
        diff_filter = "AND difficulty IN (4, 5)"

    cur.execute(f'''
        SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
        FROM question_bank
        WHERE times_used = 0
        AND length(question) {length_filter}
        AND length(option_a) BETWEEN 1 AND 50
        AND length(option_b) BETWEEN 1 AND 50
        AND length(option_c) BETWEEN 1 AND 50
        AND length(option_d) BETWEEN 1 AND 50
        AND question NOT LIKE '%[%]%'
        AND question NOT LIKE '%http%'
        AND question LIKE '%?%'
        {diff_filter}
        ORDER BY RANDOM()
        LIMIT ?
    ''', (count,))

    rows = cur.fetchall()
    conn.close()

    questions = []
    ids = []
    for row in rows:
        ids.append(row[0])
        questions.append({
            'question': row[1],
            'options': [row[2], row[3], row[4], row[5]],
            'answer': row[6]
        })
    return questions, ids

def mark_used(question_ids):
    if not question_ids:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    placeholders = ','.join('?' * len(question_ids))
    cur.execute(f'UPDATE question_bank SET times_used = times_used + 1 WHERE id IN ({placeholders})', question_ids)
    conn.commit()
    conn.close()

def get_oauth_token():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'youtube_access_token'")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def upload_video(video_path, title, description, is_short=False):
    """Upload video to YouTube."""
    import urllib.request
    import urllib.error

    token = get_oauth_token()
    if not token:
        return None, "NO_TOKEN"

    with open(video_path, 'rb') as f:
        video_data = f.read()

    metadata = {
        "snippet": {
            "title": title + (" #shorts" if is_short else ""),
            "description": description,
            "tags": ["quiz", "trivia", "brain teaser"],
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-Upload-Content-Type': 'video/mp4',
        'X-Upload-Content-Length': str(len(video_data))
    }

    req = urllib.request.Request(
        'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
        data=json.dumps(metadata).encode(),
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as resp:
            upload_url = resp.headers.get('Location')

        req2 = urllib.request.Request(
            upload_url,
            data=video_data,
            headers={'Content-Type': 'video/mp4'},
            method='PUT'
        )

        with urllib.request.urlopen(req2) as resp:
            result = json.loads(resp.read().decode())
            return result.get('id'), None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if 'quotaExceeded' in error_body or 'uploadLimitExceeded' in error_body:
            return None, "LIMIT_REACHED"
        log(f"Upload error: {e.code} - {error_body[:200]}")
        return None, "ERROR"
    except Exception as e:
        log(f"Upload error: {e}")
        return None, "ERROR"

def generate_and_upload_short(difficulty=None):
    """Generate and upload one short."""
    from generators import ShortsGenerator
    from sound_effects import TitleGenerator
    import random

    questions, ids = get_questions(5, for_shorts=True, difficulty=difficulty)
    if len(questions) < 5:
        return False, "NO_QUESTIONS"

    filename = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, filename)

    try:
        generator = ShortsGenerator()
        generator.generate(questions, filename, enable_tts=True, difficulty=difficulty)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            title = TitleGenerator.generate_shorts_title(5, difficulty=difficulty)
            desc = TitleGenerator.generate_description(5, is_shorts=True)

            video_id, error = upload_video(output_path, title, desc, is_short=True)
            os.remove(output_path)

            if video_id:
                mark_used(ids)
                log(f"✓ Short uploaded: https://youtube.com/watch?v={video_id}")
                return True, None
            return False, error
        return False, "GEN_FAILED"
    except Exception as e:
        log(f"✗ Short error: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False, "ERROR"

def generate_and_upload_longform():
    """Generate and upload one longform video."""
    from generators import GeneralKnowledgeGenerator
    from sound_effects import TitleGenerator

    questions, ids = get_questions(50, for_shorts=False)
    if len(questions) < 50:
        return False, "NO_QUESTIONS"

    filename = f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, filename)

    try:
        generator = GeneralKnowledgeGenerator(width=1920, height=1080, question_time=10, answer_time=5)
        generator.generate(questions, filename, enable_tts=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            title = TitleGenerator.generate_longform_title(50)
            desc = TitleGenerator.generate_description(50, is_shorts=False)

            video_id, error = upload_video(output_path, title, desc, is_short=False)
            os.remove(output_path)

            if video_id:
                mark_used(ids)
                log(f"✓ Longform uploaded: https://youtube.com/watch?v={video_id}")
                return True, None
            return False, error
        return False, "GEN_FAILED"
    except Exception as e:
        log(f"✗ Longform error: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False, "ERROR"

def main():
    hour = datetime.now().hour
    log(f"=== Hourly upload (hour {hour}) ===")

    os.chdir(VIDEO_GEN_PATH)

    # Vary difficulty by time of day
    if hour < 8:
        difficulty = 'easy'  # Morning - easy
    elif hour < 16:
        difficulty = None    # Afternoon - mixed
    else:
        difficulty = 'hard'  # Evening - hard

    uploaded = 0

    # Upload shorts
    for i in range(SHORTS_PER_HOUR):
        success, error = generate_and_upload_short(difficulty)
        if success:
            uploaded += 1
        elif error == "LIMIT_REACHED":
            log("Limit reached, stopping")
            return
        time.sleep(DELAY_BETWEEN_UPLOADS)

    # Upload longform
    for i in range(LONGFORM_PER_HOUR):
        success, error = generate_and_upload_longform()
        if success:
            uploaded += 1
        elif error == "LIMIT_REACHED":
            log("Limit reached, stopping")
            return
        time.sleep(DELAY_BETWEEN_UPLOADS)

    log(f"=== Hourly complete: {uploaded} videos ===")

if __name__ == "__main__":
    main()
