#!/usr/bin/env python3
"""
TTS Pre-warming Script - Pre-generates TTS audio for questions in advance.
Run this in the background to speed up video generation.
"""

import sqlite3
import sys
import os
import time

# Add video generator to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "video_generator"))

DB_PATH = "/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db"

def get_questions_for_prewarm(count=1000):
    """Get questions that need TTS pre-generation."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('''
        SELECT question, option_a, option_b, option_c, option_d, correct_answer
        FROM question_bank
        WHERE times_used = 0
        AND length(question) BETWEEN 20 AND 200
        AND question NOT LIKE '%[%]%'
        AND question NOT LIKE '%http%'
        AND question LIKE '%?%'
        ORDER BY RANDOM()
        LIMIT ?
    ''', (count,))

    rows = cur.fetchall()
    conn.close()
    return rows


def prewarm_questions(count=1000, batch_size=100):
    """Pre-warm TTS cache with questions and answers."""
    from sound_effects import TTSCache

    cache = TTSCache()
    stats = cache.get_cache_stats()
    print(f"Current cache: {stats['files']} files, {stats['size_mb']} MB")

    questions = get_questions_for_prewarm(count)
    print(f"Got {len(questions)} questions to pre-warm")

    # Collect all texts to generate
    all_texts = []
    for q in questions:
        question_text = q[0]
        options = [q[1], q[2], q[3], q[4]]
        answer_idx = q[5]
        answer_letter = ['A', 'B', 'C', 'D'][min(answer_idx, 3)]
        answer_text = options[min(answer_idx, 3)]

        # Question TTS
        all_texts.append(question_text)
        # Answer TTS
        all_texts.append(f"{answer_letter}! {answer_text}")

    # Remove already cached
    uncached = [t for t in all_texts if not cache.get_cached(t)]
    print(f"Need to generate TTS for {len(uncached)} texts ({len(all_texts) - len(uncached)} already cached)")

    if not uncached:
        print("All done - cache is fully warmed!")
        return

    # Generate in batches
    for i in range(0, len(uncached), batch_size):
        batch = uncached[i:i + batch_size]
        print(f"\nBatch {i//batch_size + 1}/{(len(uncached) + batch_size - 1)//batch_size}: {len(batch)} texts...")
        cache.prewarm_cache(batch)

        # Show progress
        stats = cache.get_cache_stats()
        print(f"Cache now: {stats['files']} files, {stats['size_mb']} MB")

    print("\nPre-warming complete!")
    stats = cache.get_cache_stats()
    print(f"Final cache: {stats['files']} files, {stats['size_mb']} MB")


def continuous_prewarm(interval_minutes=30, batch_per_run=500):
    """Continuously pre-warm cache in background."""
    print(f"Starting continuous TTS pre-warm (every {interval_minutes} minutes)")

    while True:
        try:
            prewarm_questions(batch_per_run, batch_size=50)
        except Exception as e:
            print(f"Error during prewarm: {e}")

        print(f"\nSleeping {interval_minutes} minutes until next run...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pre-warm TTS cache")
    parser.add_argument("--count", type=int, default=500, help="Number of questions to pre-warm")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=30, help="Minutes between runs (for continuous mode)")

    args = parser.parse_args()

    if args.continuous:
        continuous_prewarm(args.interval, args.count)
    else:
        prewarm_questions(args.count)
