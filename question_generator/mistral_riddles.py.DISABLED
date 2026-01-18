#!/usr/bin/env python3
"""
Mistral Riddle Generator
Generates riddles with multiple choice answers.
"""

import json
import sqlite3
import time
import urllib.request
import random

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
OLLAMA_URL = "http://localhost:11434/api/generate"

RIDDLE_TYPES = [
    "everyday objects", "animals", "food", "nature", "body parts",
    "household items", "weather", "time", "tools", "vehicles",
    "fruits", "vegetables", "clothing", "sports equipment", "musical instruments",
    "school supplies", "kitchen items", "bathroom items", "furniture", "electronics"
]

PROMPT_TEMPLATE = """Generate 10 clever riddles about {topic}.

Rules:
- Each riddle must be a "What am I?" style riddle
- Give 4 possible answers, only 1 correct
- Riddles should be fun and not too hard
- Keep riddles under 100 characters

Output ONLY this JSON format:
[{{"question":"I have hands but cannot clap. What am I?","options":["Clock","Gloves","Tree","Robot"],"answer":0}}]

Generate 10 {topic} riddles now:"""


def generate_riddles(topic):
    """Generate riddles using Mistral."""
    prompt = PROMPT_TEMPLATE.format(topic=topic)

    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.9,
            "num_predict": 4096,
            "num_thread": 10,
        }
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())
            return result.get('response', '')
    except Exception as e:
        print(f"  Error: {e}")
        return None


def parse_riddles(response_text):
    """Parse JSON riddles from response."""
    if not response_text:
        return []

    try:
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            riddles = json.loads(json_str)
            return riddles
    except json.JSONDecodeError:
        pass

    return []


def save_to_database(riddles, topic):
    """Save riddles to SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    saved = 0
    for r in riddles:
        try:
            riddle_text = r.get('question', '').strip()
            options = r.get('options', [])
            answer_idx = r.get('answer', 0)

            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx > 3:
                answer_idx = 0

            if not riddle_text or len(options) != 4:
                print(f"    Skip: bad format")
                continue
            if len(riddle_text) > 200:
                print(f"    Skip: too long")
                continue
            if any(len(str(opt)) > 80 for opt in options):
                print(f"    Skip: option too long")
                continue

            # Check duplicate
            cur.execute("SELECT id FROM question_bank WHERE question = ?", (riddle_text,))
            if cur.fetchone():
                print(f"    Skip: duplicate")
                continue

            cur.execute('''
                INSERT INTO question_bank
                (question, option_a, option_b, option_c, option_d, correct_answer, topic_id, difficulty, source, times_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                riddle_text,
                str(options[0]),
                str(options[1]),
                str(options[2]),
                str(options[3]),
                answer_idx,
                1,
                1,
                'mistral',
                0
            ))
            saved += 1
            print(f"    + {riddle_text[:50]}...")

        except Exception as e:
            print(f"    Error: {e}")
            continue

    conn.commit()
    conn.close()
    return saved


def get_question_count():
    """Get current mistral question count."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM question_bank WHERE source = 'mistral'")
    count = cur.fetchone()[0]
    conn.close()
    return count


def main():
    print("=" * 60)
    print("MISTRAL RIDDLE GENERATOR")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Starting count: {get_question_count()} questions")
    print("Press Ctrl+C to stop\n")

    batch = 0

    while True:
        batch += 1
        topic = random.choice(RIDDLE_TYPES)

        print(f"[Riddles - Batch {batch}] Generating: {topic}...")

        response = generate_riddles(topic)
        if response:
            riddles = parse_riddles(response)
            if riddles:
                saved = save_to_database(riddles, topic)
                current_count = get_question_count()
                print(f"  ✓ Saved {saved}/{len(riddles)} (Total: {current_count})")
            else:
                print(f"  ✗ Failed to parse")
        else:
            print(f"  ✗ Generation failed")

        time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        print(f"Final count: {get_question_count()} questions")
