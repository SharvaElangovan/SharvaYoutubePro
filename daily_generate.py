#!/usr/bin/env python3
"""
Daily Video Generation Script - Runs during the day
Generates videos + thumbnails, saves to queue for later upload
"""

import subprocess
import sqlite3
import os
import sys
import json
import random
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_GEN_PATH = os.path.join(SCRIPT_DIR, "video_generator")
DB_PATH = "/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db"
QUEUE_DIR = os.path.join(SCRIPT_DIR, "upload_queue")
LOG_FILE = os.path.join(SCRIPT_DIR, "daily_generate.log")

sys.path.insert(0, VIDEO_GEN_PATH)

# How many videos to generate (15 shorts + 5 longform = 20/day)
LONGFORM_COUNT = 5
SHORTS_COUNT = 15

def log(msg):
    """Log message to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_unused_questions(category, count):
    """Fetch unused questions from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, question, option_a, option_b, option_c, option_d, correct_answer, category
            FROM question_bank
            WHERE times_used = 0 AND category LIKE ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (f"%{category}%", count))
        rows = cur.fetchall()
        conn.close()

        questions = []
        for row in rows:
            options = [row[2], row[3], row[4], row[5]]
            correct = row[6].upper()
            answer_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(correct, 0)
            questions.append({
                'id': row[0],
                'question': row[1],
                'options': options,
                'answer': answer_idx,
                'category': row[7]
            })
        return questions
    except Exception as e:
        log(f"DB error: {e}")
        return []

def mark_questions_used(question_ids):
    """Mark questions as used in database."""
    if not question_ids:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.executemany(
            "UPDATE question_bank SET times_used = times_used + 1 WHERE id = ?",
            [(qid,) for qid in question_ids]
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"Failed to mark questions used: {e}")

def generate_longform_video(questions, video_num):
    """Generate a longform quiz video."""
    from generators import GeneralKnowledgeGenerator

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gk_longform_{video_num}_{timestamp}.mp4"

    gen = GeneralKnowledgeGenerator()
    output_path = gen.generate(questions, output_filename=filename, enable_tts=True)

    # Generate thumbnail
    category = questions[0].get('category', 'General') if questions else 'General'
    thumb_path = output_path.replace('.mp4', '_thumb.jpg')
    gen.generate_thumbnail(
        title="General Knowledge",
        subtitle=f"{len(questions)} Questions",
        output_path=thumb_path,
        category=category
    )

    return output_path, thumb_path

def generate_shorts_video(questions, video_num):
    """Generate a shorts quiz video."""
    from generators import ShortsGenerator

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gk_shorts_{video_num}_{timestamp}.mp4"

    gen = ShortsGenerator()
    output_path = gen.generate(questions, output_filename=filename, enable_tts=True)

    # Thumbnail for shorts
    thumb_path = output_path.replace('.mp4', '_thumb.jpg')
    gen.generate_thumbnail(
        title="Quick Quiz",
        output_path=thumb_path
    )

    return output_path, thumb_path

def save_to_queue(video_path, thumb_path, video_type, questions):
    """Save video info to queue for later upload."""
    os.makedirs(QUEUE_DIR, exist_ok=True)

    # Create metadata file
    meta = {
        'video_path': video_path,
        'thumb_path': thumb_path,
        'video_type': video_type,  # 'longform' or 'shorts'
        'question_ids': [q['id'] for q in questions],
        'question_count': len(questions),
        'category': questions[0].get('category', 'General') if questions else 'General',
        'created_at': datetime.now().isoformat()
    }

    meta_filename = os.path.basename(video_path).replace('.mp4', '.json')
    meta_path = os.path.join(QUEUE_DIR, meta_filename)

    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    log(f"  Queued: {meta_filename}")
    return meta_path

def main():
    log("=" * 60)
    log("DAILY VIDEO GENERATION STARTED")
    log("=" * 60)

    total_generated = 0

    # Generate longform videos
    log(f"\n--- Generating {LONGFORM_COUNT} Longform Videos ---")
    for i in range(LONGFORM_COUNT):
        questions = get_unused_questions("", 50)  # 50 questions per video
        if len(questions) < 20:
            log(f"  Not enough questions for longform {i+1}, skipping")
            continue

        log(f"  Generating longform {i+1}/{LONGFORM_COUNT}...")
        try:
            video_path, thumb_path = generate_longform_video(questions, i+1)
            save_to_queue(video_path, thumb_path, 'longform', questions)
            mark_questions_used([q['id'] for q in questions])
            total_generated += 1
        except Exception as e:
            log(f"  ERROR generating longform {i+1}: {e}")

    # Generate shorts videos
    log(f"\n--- Generating {SHORTS_COUNT} Shorts Videos ---")
    for i in range(SHORTS_COUNT):
        questions = get_unused_questions("", 5)  # 5 questions per short
        if len(questions) < 3:
            log(f"  Not enough questions for shorts {i+1}, skipping")
            continue

        log(f"  Generating shorts {i+1}/{SHORTS_COUNT}...")
        try:
            video_path, thumb_path = generate_shorts_video(questions, i+1)
            save_to_queue(video_path, thumb_path, 'shorts', questions)
            mark_questions_used([q['id'] for q in questions])
            total_generated += 1
        except Exception as e:
            log(f"  ERROR generating shorts {i+1}: {e}")

    log(f"\n{'=' * 60}")
    log(f"GENERATION COMPLETE: {total_generated} videos queued for upload")
    log(f"Queue directory: {QUEUE_DIR}")
    log("=" * 60)

if __name__ == "__main__":
    main()
