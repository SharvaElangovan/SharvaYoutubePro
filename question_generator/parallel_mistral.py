#!/usr/bin/env python3
"""
Parallel Mistral Generator - Runs multiple generators concurrently
"""

import json
import sqlite3
import time
import urllib.request
import random
import threading
import sys

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
OLLAMA_URL = "http://localhost:11434/api/generate"

# All topics combined
TOPICS = [
    # General Knowledge
    "Science", "History", "Geography", "Mathematics", "Literature",
    "Music", "Movies", "Sports", "Technology", "Nature",
    "Space", "Animals", "Food", "Art", "Politics",
    "Medicine", "Psychology", "Economics", "Physics", "Chemistry",
    "Biology", "Astronomy", "Mythology", "Philosophy", "Architecture",
    "Fashion", "Inventions", "World Records", "Famous People", "Languages",
    "Computers", "Internet", "Video Games", "Television", "Books",
    "Oceans", "Mountains", "Rivers", "Countries", "Capitals",
    # Riddles topics
    "everyday objects", "household items", "weather", "time", "tools",
    "vehicles", "fruits", "vegetables", "clothing", "sports equipment",
    "musical instruments", "school supplies", "kitchen items", "furniture", "electronics"
]

PROMPT_TRIVIA = """Generate 10 trivia questions about {topic}.
Rules:
- Each question MUST have EXACTLY 4 options
- Options must be 1-5 words each
- No "True/False" or "None of the above"
Output ONLY JSON: [{{"question":"What is X?","options":["A","B","C","D"],"answer":0}}]"""

PROMPT_RIDDLE = """Generate 10 clever riddles about {topic}.
Rules:
- Each riddle must be a "What am I?" style riddle
- Give 4 possible answers, only 1 correct
- Keep riddles under 100 characters
Output ONLY JSON: [{{"question":"I have hands but cannot clap. What am I?","options":["Clock","Gloves","Tree","Robot"],"answer":0}}]"""

db_lock = threading.Lock()
stats = {"generated": 0, "saved": 0, "errors": 0}
stats_lock = threading.Lock()

def generate(topic, is_riddle=False):
    prompt = (PROMPT_RIDDLE if is_riddle else PROMPT_TRIVIA).format(topic=topic)
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.9, "num_predict": 4096}
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
    saved = 0
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for q in questions:
            try:
                text = q.get('question', '').strip()
                opts = q.get('options', [])
                ans = q.get('answer', 0)
                if not isinstance(ans, int) or ans < 0 or ans > 3:
                    ans = 0
                if not text or len(opts) != 4 or len(text) > 200:
                    continue
                if any(len(str(o)) > 80 for o in opts):
                    continue
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
    while not stop_event.is_set():
        topic = random.choice(TOPICS)
        is_riddle = random.random() < 0.3  # 30% riddles
        
        response = generate(topic, is_riddle)
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
