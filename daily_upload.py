#!/usr/bin/env python3
"""
Daily YouTube Upload Script - Runs at quota reset
Generates and uploads 25 long-form + 25 short-form videos
"""

import subprocess
import sqlite3
import os
import sys
import json
import time
from datetime import datetime

# Paths
VIDEO_GEN_PATH = "/home/sharva/projects/video generator"
DB_PATH = "/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db"
OUTPUT_DIR = "/home/sharva/projects/video generator/output"
LOG_FILE = "/home/sharva/projects/SharvaYoutubePro/daily_upload.log"

sys.path.insert(0, VIDEO_GEN_PATH)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_questions(count, for_shorts=False):
    """Fetch unused questions from database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    length_filter = "BETWEEN 20 AND 120" if for_shorts else "BETWEEN 20 AND 200"
    
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
        AND source IN ('opentriviaqa', 'triviaapi', 'opentdb', 'millionaire', 'built-in', 'sciq', 'arc', 'openbookqa', 'mistral')
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
    """Mark questions as used."""
    if not question_ids:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    placeholders = ','.join('?' * len(question_ids))
    cur.execute(f'UPDATE question_bank SET times_used = times_used + 1 WHERE id IN ({placeholders})', question_ids)
    conn.commit()
    conn.close()

def get_oauth_token():
    """Get OAuth token from database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'youtube_access_token'")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def refresh_token():
    """Refresh OAuth token if needed."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT value FROM settings WHERE key = 'youtube_client_id'")
    client_id = cur.fetchone()
    cur.execute("SELECT value FROM settings WHERE key = 'youtube_client_secret'")
    client_secret = cur.fetchone()
    cur.execute("SELECT value FROM settings WHERE key = 'youtube_refresh_token'")
    refresh_token = cur.fetchone()
    
    if not all([client_id, client_secret, refresh_token]):
        conn.close()
        return None
    
    import urllib.request
    import urllib.parse
    
    data = urllib.parse.urlencode({
        'client_id': client_id[0],
        'client_secret': client_secret[0],
        'refresh_token': refresh_token[0],
        'grant_type': 'refresh_token'
    }).encode()
    
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            new_token = result.get('access_token')
            if new_token:
                cur.execute("UPDATE settings SET value = ? WHERE key = 'youtube_access_token'", (new_token,))
                conn.commit()
                conn.close()
                return new_token
    except Exception as e:
        log(f"Token refresh failed: {e}")
    
    conn.close()
    return None

def upload_video(video_path, title, description, is_short=False):
    """Upload video to YouTube."""
    import urllib.request
    import urllib.error
    
    token = get_oauth_token()
    if not token:
        token = refresh_token()
    if not token:
        return None
    
    # Read video file
    with open(video_path, 'rb') as f:
        video_data = f.read()
    
    metadata = {
        "snippet": {
            "title": title,
            "description": description + "\n\n#quiz #trivia #brainteaser",
            "tags": ["quiz", "trivia", "brain teaser", "general knowledge"],
            "categoryId": "27"  # Education
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    if is_short:
        metadata["snippet"]["title"] = title + " #shorts"
    
    # Start resumable upload
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
        
        # Upload video data
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
        if '401' in str(e.code) or 'UNAUTHENTICATED' in error_body:
            log("Token expired, refreshing...")
            refresh_token()
            return upload_video(video_path, title, description, is_short)  # Retry once
        if 'quotaExceeded' in error_body:
            log("YouTube API quota exceeded!")
            return None, "LIMIT_REACHED"
        log(f"Upload error: {e.code} - {error_body}")
        return None, "ERROR"
    except Exception as e:
        log(f"Upload error: {e}")
        return None, "ERROR"

def generate_and_upload_shorts():
    """Generate and upload short-form videos until YouTube limit."""
    from generators import ShortsGenerator

    log("=== Generating Shorts until YouTube limit ===")

    i = 0
    while True:
        i += 1
        questions, ids = get_questions(5, for_shorts=True)
        if len(questions) < 5:
            log("Not enough questions for Shorts!")
            break

        filename = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.mp4"
        output_path = os.path.join(OUTPUT_DIR, filename)

        try:
            generator = ShortsGenerator()
            generator.generate(questions, filename, enable_tts=True)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                title = f"Quiz Time! Can You Answer? #{i}"
                desc = "Test your knowledge with this quick quiz!"

                video_id, error = upload_video(output_path, title, desc, is_short=True)

                if video_id:
                    mark_used(ids)
                    log(f"✓ Short #{i} uploaded: https://youtube.com/watch?v={video_id}")
                    os.remove(output_path)  # Clean up
                elif error == "LIMIT_REACHED":
                    log(f"YouTube upload limit reached after {i-1} Shorts!")
                    os.remove(output_path)
                    return "LIMIT_REACHED"
                else:
                    log(f"✗ Short #{i} upload failed")
                    os.remove(output_path)
            else:
                log(f"✗ Short #{i} generation failed")

        except Exception as e:
            log(f"✗ Short #{i} error: {e}")

        time.sleep(5)  # Small delay between uploads

    return "DONE"

def generate_and_upload_longform():
    """Generate and upload long-form videos until YouTube limit."""
    from generators import GeneralKnowledgeGenerator

    log("=== Generating Long-form Videos until YouTube limit ===")

    i = 0
    while True:
        i += 1
        questions, ids = get_questions(50, for_shorts=False)  # 50 questions per video
        if len(questions) < 50:
            log("Not enough questions for long-form!")
            break

        filename = f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.mp4"
        output_path = os.path.join(OUTPUT_DIR, filename)

        try:
            generator = GeneralKnowledgeGenerator(
                width=1920, height=1080,
                question_time=10, answer_time=5
            )
            generator.generate(questions, filename, enable_tts=True)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                title = f"50 Trivia Questions - General Knowledge Quiz #{i}"
                desc = "Challenge yourself with 50 trivia questions! How many can you get right?"

                video_id, error = upload_video(output_path, title, desc, is_short=False)

                if video_id:
                    mark_used(ids)
                    log(f"✓ Long-form #{i} uploaded: https://youtube.com/watch?v={video_id}")
                    os.remove(output_path)  # Clean up
                elif error == "LIMIT_REACHED":
                    log(f"YouTube upload limit reached after {i-1} Long-form videos!")
                    os.remove(output_path)
                    return "LIMIT_REACHED"
                else:
                    log(f"✗ Long-form #{i} upload failed")
                    os.remove(output_path)
            else:
                log(f"✗ Long-form #{i} generation failed")

        except Exception as e:
            log(f"✗ Long-form #{i} error: {e}")

        time.sleep(5)  # Small delay between uploads

    return "DONE"

def main():
    log("=" * 60)
    log("DAILY UPLOAD SCRIPT STARTED")
    log("=" * 60)

    os.chdir(VIDEO_GEN_PATH)

    # Generate and upload shorts first (faster)
    result = generate_and_upload_shorts()

    # If shorts didn't hit limit, do long-form
    if result != "LIMIT_REACHED":
        generate_and_upload_longform()

    log("=" * 60)
    log("DAILY UPLOAD COMPLETE - YouTube maxed out!")
    log("=" * 60)

if __name__ == "__main__":
    main()
