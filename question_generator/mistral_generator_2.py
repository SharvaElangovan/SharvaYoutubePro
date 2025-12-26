#!/usr/bin/env python3
"""
Mistral Question Generator - Instance 2
Different topics to avoid overlap with instance 1.
"""

import json
import sqlite3
import time
import urllib.request
import urllib.error
import random

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
OLLAMA_URL = "http://localhost:11434/api/generate"

# Different topics from instance 1 - general knowledge only
TOPICS = [
    "Cars", "Planes", "Ships", "Trains", "Aviation",
    "Dinosaurs", "Insects", "Birds", "Marine Life", "Mammals",
    "Weather", "Earthquakes", "Volcanoes", "Climate", "Natural Disasters",
    "Olympics", "Soccer", "Basketball", "Baseball", "Tennis",
    "Classic Movies", "Hollywood", "Academy Awards", "Famous Directors", "Box Office",
    "Cooking", "Desserts", "World Cuisines", "Beverages", "Ingredients",
    "Flags", "Currencies", "World Languages", "World Religions", "National Holidays",
    "Celebrities", "Rock Music", "Classical Music", "Famous Athletes", "Nobel Prize Winners",
    "Board Games", "Card Games", "World Wonders", "Famous Landmarks", "National Parks",
    "Military History", "Ancient Civilizations", "Medieval Times", "Exploration", "Inventions"
]

PROMPT_TEMPLATE = """Generate 10 trivia questions about {topic}.

Rules:
- Each question MUST have EXACTLY 4 options
- Options must be 1-5 words each
- No "True/False" questions
- No "None of the above" options

Output ONLY this JSON format:
[{{"question":"What is X?","options":["A","B","C","D"],"answer":0}}]

Generate 10 {topic} questions now:"""


def generate_questions(topic):
    """Generate questions using Mistral via Ollama."""
    prompt = PROMPT_TEMPLATE.format(topic=topic)

    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "num_predict": 4096,
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


def parse_questions(response_text):
    """Parse JSON questions from response."""
    if not response_text:
        return []

    try:
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            questions = json.loads(json_str)
            return questions
    except json.JSONDecodeError:
        pass

    return []


def save_to_database(questions, topic):
    """Save questions to SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    saved = 0
    for q in questions:
        try:
            question_text = q.get('question', '').strip()
            options = q.get('options', [])
            answer_idx = q.get('answer', 0)

            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx > 3:
                answer_idx = 0

            if not question_text or len(options) != 4:
                print(f"    Skip: bad format")
                continue
            if not question_text.endswith('?'):
                print(f"    Skip: no ?")
                continue
            if len(question_text) > 200:
                print(f"    Skip: too long")
                continue
            if any(len(str(opt)) > 80 for opt in options):
                print(f"    Skip: option too long")
                continue

            bad_patterns = ['Unknown', 'Not applicable', 'None of', 'All of the above']
            if any(bad in str(options) for bad in bad_patterns):
                print(f"    Skip: bad pattern")
                continue

            cur.execute("SELECT id FROM question_bank WHERE question = ?", (question_text,))
            if cur.fetchone():
                print(f"    Skip: duplicate")
                continue

            cur.execute('''
                INSERT INTO question_bank
                (question, option_a, option_b, option_c, option_d, correct_answer, topic_id, difficulty, source, times_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                question_text,
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
            print(f"    + {question_text[:50]}...")

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
    print("MISTRAL QUESTION GENERATOR - INSTANCE 2")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Starting count: {get_question_count()} mistral questions")
    print("Press Ctrl+C to stop\n")

    batch = 0

    while True:
        batch += 1
        topic = random.choice(TOPICS)

        print(f"[Instance 2 - Batch {batch}] Generating: {topic}...")

        response = generate_questions(topic)
        if response:
            questions = parse_questions(response)
            if questions:
                saved = save_to_database(questions, topic)
                current_count = get_question_count()
                print(f"  ✓ Saved {saved}/{len(questions)} (Total: {current_count})")
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
        print(f"Final count: {get_question_count()} mistral questions")
