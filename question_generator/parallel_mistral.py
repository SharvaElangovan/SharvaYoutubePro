#!/usr/bin/env python3
"""
Parallel Mistral Generator - Runs multiple generators concurrently
With fact-checking validation to prevent wrong answers.
"""

import json
import sqlite3
import time
import urllib.request
import random
import threading
import sys
import re

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
OLLAMA_URL = "http://localhost:11434/api/generate"

# =============================================================================
# FACT VALIDATION DATABASE - Prevents common AI mistakes
# =============================================================================
KNOWN_FACTS = {
    # Capitals
    'capital.*france': 'paris', 'capital.*japan': 'tokyo', 'capital.*australia': 'canberra',
    'capital.*germany': 'berlin', 'capital.*italy': 'rome', 'capital.*spain': 'madrid',
    'capital.*brazil': 'brasilia', 'capital.*canada': 'ottawa', 'capital.*india': 'delhi',
    'capital.*china': 'beijing', 'capital.*russia': 'moscow', 'capital.*turkey': 'ankara',
    'capital.*uk|capital.*britain': 'london', 'capital.*egypt': 'cairo',
    # Planets
    'largest planet(?!.*second)': 'jupiter', 'smallest planet': 'mercury',
    'closest.*sun(?!.*second)': 'mercury', 'hottest planet': 'venus', 'red planet': 'mars',
    # Geography
    'largest ocean(?!.*second)': 'pacific', 'largest continent(?!.*second)': 'asia',
    'smallest continent': 'australia', 'longest river.*africa': 'nile',
    'highest mountain.*world(?!.*second)': 'everest', 'highest mountain.*africa': 'kilimanjaro',
    'largest country(?!.*second)': 'russia', 'largest desert(?!.*second)': 'sahara|antarctic',
    # Science
    'chemical symbol.*gold': 'au', 'chemical symbol.*silver': 'ag', 'chemical symbol.*iron': 'fe',
    'atomic number.*oxygen': '8(?![0-9])', 'atomic number.*carbon': '6(?![0-9])',
    # Body
    'largest organ': 'skin', 'largest bone': 'femur', 'bones.*human.*adult': '206',
    # Animals
    'largest animal(?!.*land)': 'whale', 'fastest land animal': 'cheetah',
    'tallest animal': 'giraffe', 'largest bird': 'ostrich',
    # Math
    'square root.*144': '12', 'square root.*100': '10', 'square root.*81': '9',
    'square root.*64': '8', 'square root.*49': '7', 'square root.*36': '6',
}

BAD_PATTERNS = ['Unknown', 'Not applicable', 'None of', 'All of the above', 'N/A']
RIDDLE_PATTERNS = [r'what am i\??$', r'i have .* what am i', r'i am .* what am i']


def validate_question(question, options, answer_idx):
    """Validate factual accuracy. Returns (is_valid, reason)."""
    q_lower = question.lower()
    answer = str(options[answer_idx]).lower() if 0 <= answer_idx < len(options) else ""

    # Reject riddles
    for pattern in RIDDLE_PATTERNS:
        if re.search(pattern, q_lower):
            return False, "Riddle rejected"

    # Check bad patterns in options
    opts_str = str(options)
    if any(bad in opts_str for bad in BAD_PATTERNS):
        return False, "Bad pattern in options"

    # Check facts
    for pattern, correct in KNOWN_FACTS.items():
        if re.search(pattern, q_lower):
            if not re.search(correct, answer, re.IGNORECASE):
                return False, f"Wrong fact: {answer}"

    # Duplicate options check
    if len(set(str(o).lower().strip() for o in options)) < 4:
        return False, "Duplicate options"

    return True, "OK"


# Topics (NO riddle topics - they produce bad questions)
TOPICS = [
    "Science", "History", "Geography", "Mathematics", "Literature",
    "Music", "Movies", "Sports", "Technology", "Nature",
    "Space", "Animals", "Food", "Art", "Politics",
    "Medicine", "Psychology", "Economics", "Physics", "Chemistry",
    "Biology", "Astronomy", "Mythology", "Philosophy", "Architecture",
    "Fashion", "Inventions", "World Records", "Famous People", "Languages",
    "Computers", "Internet", "Video Games", "Television", "Books",
    "Oceans", "Mountains", "Rivers", "Countries", "Capitals",
]

PROMPT_TRIVIA = """Generate 10 trivia questions about {topic}.
Rules:
- Each question MUST have EXACTLY 4 options
- Options must be 1-5 words each
- No "True/False" or "None of the above"
- Make sure the answer is FACTUALLY CORRECT
Output ONLY JSON: [{{"question":"What is X?","options":["A","B","C","D"],"answer":0}}]"""

db_lock = threading.Lock()
stats = {"generated": 0, "saved": 0, "errors": 0}
stats_lock = threading.Lock()

def generate(topic):
    """Generate trivia questions using Mistral."""
    prompt = PROMPT_TRIVIA.format(topic=topic)
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 4096}
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(OLLAMA_URL, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())
            return result.get('response', '')
    except Exception as e:
        return None

def parse(response_text):
    if not response_text:
        return []
    try:
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
    except:
        pass
    return []

def save(questions):
    """Save questions to database with validation."""
    saved = 0
    rejected = 0
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for q in questions:
            try:
                text = q.get('question', '').strip()
                opts = q.get('options', [])
                ans = q.get('answer', 0)

                # Basic validation
                if not isinstance(ans, int) or ans < 0 or ans > 3:
                    ans = 0
                if not text or len(opts) != 4 or len(text) > 200:
                    continue
                if not text.endswith('?'):
                    continue
                if any(len(str(o)) > 80 for o in opts):
                    continue

                # FACT VALIDATION - reject incorrect answers
                is_valid, reason = validate_question(text, opts, ans)
                if not is_valid:
                    rejected += 1
                    continue

                # Check duplicate
                cur.execute("SELECT id FROM question_bank WHERE question = ?", (text,))
                if cur.fetchone():
                    continue

                cur.execute('''INSERT INTO question_bank
                    (question, option_a, option_b, option_c, option_d, correct_answer, topic_id, difficulty, source, times_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (text, str(opts[0]), str(opts[1]), str(opts[2]), str(opts[3]), ans, 1, 1, 'mistral', 0))
                saved += 1
            except:
                continue
        conn.commit()
        conn.close()
    return saved

def worker(worker_id, stop_event):
    """Worker thread that generates and saves questions."""
    while not stop_event.is_set():
        topic = random.choice(TOPICS)

        response = generate(topic)
        with stats_lock:
            stats["generated"] += 1

        if response:
            questions = parse(response)
            if questions:
                saved = save(questions)
                with stats_lock:
                    stats["saved"] += saved
        else:
            with stats_lock:
                stats["errors"] += 1

        time.sleep(1)  # Small delay between requests

def get_count():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM question_bank WHERE source = 'mistral'")
    count = cur.fetchone()[0]
    conn.close()
    return count

def main():
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    
    print("=" * 60)
    print(f"PARALLEL MISTRAL GENERATOR - {num_workers} WORKERS")
    print("=" * 60)
    print(f"Starting count: {get_count()} mistral questions")
    print("Press Ctrl+C to stop\n")
    
    stop_event = threading.Event()
    threads = []
    
    for i in range(num_workers):
        t = threading.Thread(target=worker, args=(i, stop_event), daemon=True)
        t.start()
        threads.append(t)
        print(f"  Started worker {i+1}")
    
    try:
        while True:
            time.sleep(10)
            count = get_count()
            with stats_lock:
                print(f"[Stats] Batches: {stats['generated']} | Saved: {stats['saved']} | Errors: {stats['errors']} | Total: {count}")
    except KeyboardInterrupt:
        print("\n\nStopping workers...")
        stop_event.set()
        print(f"Final count: {get_count()} mistral questions")

if __name__ == "__main__":
    main()
