#!/usr/bin/env python3
"""
Continuous Mistral Question Generator
Generates quiz questions using Mistral via Ollama and saves to database.
Runs forever until stopped.
"""

import json
import sqlite3
import time
import urllib.request
import urllib.error
import random

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
OLLAMA_URL = "http://localhost:11434/api/generate"

TOPICS = [
    "Science", "History", "Geography", "Mathematics", "Literature",
    "Music", "Movies", "Sports", "Technology", "Nature",
    "Space", "Animals", "Food", "Art", "Politics",
    "Medicine", "Psychology", "Economics", "Physics", "Chemistry",
    "Biology", "Astronomy", "Mythology", "Philosophy", "Architecture",
    "Fashion", "Inventions", "World Records", "Famous People", "Languages",
    "Computers", "Internet", "Video Games", "Television", "Books",
    "Oceans", "Mountains", "Rivers", "Countries", "Capitals",
    "Presidents", "Wars", "Ancient History", "Modern History", "Pop Culture"
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


def parse_questions(response_text):
    """Parse JSON questions from response."""
    if not response_text:
        return []

    # Find JSON array in response
    try:
        # Try to find JSON array
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

            # Clamp answer_idx to valid range 0-3
            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx > 3:
                answer_idx = 0

            # Validate
            if not question_text or len(options) != 4:
                print(f"    Skip: bad format - q={question_text[:30]}...")
                continue
            if not question_text.endswith('?'):
                print(f"    Skip: no ? - {question_text[:30]}...")
                continue
            if len(question_text) > 200:
                print(f"    Skip: too long ({len(question_text)} chars)")
                continue
            if any(len(str(opt)) > 80 for opt in options):
                print(f"    Skip: option too long")
                continue

            # Check for bad patterns
            bad_patterns = ['Unknown', 'Not applicable', 'None of', 'All of the above']
            if any(bad in str(options) for bad in bad_patterns):
                print(f"    Skip: bad pattern in options")
                continue

            # Check duplicate
            cur.execute("SELECT id FROM question_bank WHERE question = ?", (question_text,))
            if cur.fetchone():
                print(f"    Skip: duplicate")
                continue

            # Insert
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
                1,  # Default topic_id
                1,  # difficulty (integer)
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
    print("MISTRAL QUESTION GENERATOR - CONTINUOUS MODE")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Starting count: {get_question_count()} mistral questions")
    print("Press Ctrl+C to stop\n")

    batch = 0
    total_generated = 0

    while True:
        batch += 1
        topic = random.choice(TOPICS)

        print(f"[Batch {batch}] Generating questions about: {topic}...")

        response = generate_questions(topic)
        if response:
            questions = parse_questions(response)
            if questions:
                saved = save_to_database(questions, topic)
                total_generated += saved
                current_count = get_question_count()
                print(f"  ✓ Saved {saved}/{len(questions)} questions (Total mistral: {current_count})")
            else:
                print(f"  ✗ Failed to parse questions")
        else:
            print(f"  ✗ Generation failed")

        # Delay between batches to reduce CPU load
        time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        print(f"Final count: {get_question_count()} mistral questions")
