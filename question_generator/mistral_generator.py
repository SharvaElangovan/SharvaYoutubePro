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
import re

DB_PATH = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'

# =============================================================================
# FACT VALIDATION DATABASE
# Format: (keyword_pattern, correct_answer_must_contain)
# If question matches pattern and answer doesn't contain correct text, reject it
# =============================================================================
KNOWN_FACTS = {
    # Capitals - common mistakes
    'capital.*france': 'paris',
    'capital.*japan': 'tokyo',
    'capital.*australia': 'canberra',
    'capital.*germany': 'berlin',
    'capital.*italy': 'rome',
    'capital.*spain': 'madrid',
    'capital.*brazil': 'brasilia',
    'capital.*canada': 'ottawa',
    'capital.*india': 'delhi',
    'capital.*china': 'beijing',
    'capital.*russia': 'moscow',
    'capital.*uk|capital.*united kingdom|capital.*britain': 'london',
    'capital.*turkey': 'ankara',
    'capital.*egypt': 'cairo',
    'capital.*mexico': 'mexico city',
    'capital.*switzerland': 'bern',
    'capital.*poland': 'warsaw',
    'capital.*south korea': 'seoul',
    'capital.*vietnam': 'hanoi',
    'capital.*thailand': 'bangkok',

    # Planets (not "second largest" etc)
    'largest planet(?!.*second)': 'jupiter',
    'smallest planet': 'mercury',
    'closest.*sun(?!.*second)': 'mercury',
    'hottest planet': 'venus',
    'red planet': 'mars',

    # Geography
    'largest ocean(?!.*second)': 'pacific',
    'largest continent(?!.*second)': 'asia',
    'smallest continent': 'australia',
    'longest river.*africa': 'nile',
    'highest mountain.*world(?!.*second)': 'everest',
    'highest mountain.*africa': 'kilimanjaro',
    'highest mountain.*north america': 'denali',
    'highest mountain.*europe': 'elbrus|mont blanc',
    'largest country(?!.*second)': 'russia',
    'largest desert(?!.*second)': 'sahara|antarctic',

    # Science
    'chemical symbol.*gold': 'au',
    'chemical symbol.*silver': 'ag',
    'chemical symbol.*iron': 'fe',
    'chemical symbol.*sodium': 'na',
    'chemical symbol.*potassium': 'k(?![a-z])',
    'chemical symbol.*oxygen': 'o(?![a-z])',
    'chemical symbol.*hydrogen': 'h(?![a-z])',
    'chemical symbol.*water': 'h2o',
    'atomic number.*hydrogen': '1(?![0-9])',
    'atomic number.*helium': '2(?![0-9])',
    'atomic number.*carbon': '6(?![0-9])',
    'atomic number.*oxygen': '8(?![0-9])',

    # Human body
    'largest organ.*body|largest organ.*human': 'skin',
    'largest bone': 'femur',
    'smallest bone': 'stapes|stirrup',
    'bones.*human.*adult|how many bones': '206',

    # Animals
    'largest animal(?!.*land)': 'whale',
    'largest land animal': 'elephant',
    'fastest land animal': 'cheetah',
    'tallest animal': 'giraffe',
    'largest bird': 'ostrich',

    # Basic facts
    'boiling point.*water.*celsius': '100',
    'freezing point.*water.*celsius': '0',
    'speed of light': '299|300',  # ~299,792 km/s or ~300,000 km/s

    # Math
    'square root.*144': '12',
    'square root.*100': '10',
    'square root.*81': '9',
    'square root.*64': '8',
    'square root.*49': '7',
    'square root.*36': '6',
    'square root.*25': '5',
    'square root.*16': '4',
    'square root.*9(?![0-9])': '3',
    'square root.*4(?![0-9])': '2',
}

# Patterns that indicate "What am I" riddles - reject these
RIDDLE_PATTERNS = [
    r'what am i\??$',
    r'i have .* what am i',
    r'i am .* what am i',
    r"i'm .* what am i",
]


def validate_factual_accuracy(question, options, answer_idx):
    """
    Validate that the answer is factually correct for known facts.
    Returns (is_valid, reason)
    """
    q_lower = question.lower()
    answer = str(options[answer_idx]).lower() if 0 <= answer_idx < len(options) else ""

    # Check against known facts
    for pattern, correct_must_contain in KNOWN_FACTS.items():
        if re.search(pattern, q_lower):
            # This question matches a known fact pattern
            if not re.search(correct_must_contain, answer, re.IGNORECASE):
                # Answer doesn't contain the correct value
                # Check if correct answer exists in any option
                correct_option_idx = None
                for i, opt in enumerate(options):
                    if re.search(correct_must_contain, str(opt).lower()):
                        correct_option_idx = i
                        break

                if correct_option_idx is not None:
                    return False, f"Wrong answer: {answer}. Should contain: {correct_must_contain}"
                else:
                    return False, f"Correct answer ({correct_must_contain}) not in options"

    # Check for riddle patterns - reject these
    for riddle_pattern in RIDDLE_PATTERNS:
        if re.search(riddle_pattern, q_lower):
            return False, "Riddle question (What am I) - rejected"

    # Check for duplicate/similar options (sign of low quality)
    opts_lower = [str(o).lower().strip() for o in options]
    if len(set(opts_lower)) < 4:
        return False, "Duplicate options detected"

    # Check if answer option is too similar to question (often wrong)
    if answer in q_lower and len(answer) > 3:
        return False, "Answer appears in question"

    return True, "OK"


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
            bad_patterns = ['Unknown', 'Not applicable', 'None of', 'All of the above', 'N/A']
            if any(bad in str(options) for bad in bad_patterns):
                print(f"    Skip: bad pattern in options")
                continue

            # FACT VALIDATION - Check if answer is factually correct
            is_valid, reason = validate_factual_accuracy(question_text, options, answer_idx)
            if not is_valid:
                print(f"    Skip: {reason}")
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
