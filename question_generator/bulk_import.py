#!/usr/bin/env python3
"""
Bulk Question Importer - FREE sources
Downloads questions from free APIs and datasets
"""

import json
import sqlite3
import os
import requests
import html
import time

DB_PATH = os.path.expanduser("~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db")

# OpenTriviaDB category mapping to our topics
OPENTDB_CATEGORIES = {
    9: (3, "General Knowledge"),      # -> Science
    10: (6, "Entertainment: Books"),   # -> Literature
    11: (101, "Entertainment: Film"),  # -> Movies
    12: (103, "Entertainment: Music"), # -> Music
    14: (102, "Entertainment: Television"),
    15: (104, "Entertainment: Video Games"),
    17: (3, "Science & Nature"),       # -> Science
    18: (201, "Science: Computers"),   # -> Computers
    19: (2, "Science: Mathematics"),   # -> Mathematics
    20: (4, "Mythology"),              # -> History
    21: (301, "Sports"),               # -> Sports
    22: (5, "Geography"),
    23: (4, "History"),
    25: (15, "Art"),                   # -> Art History
    26: (105, "Celebrities"),
    27: (401, "Animals"),
    28: (501, "Vehicles"),             # -> Cars
    30: (206, "Science: Gadgets"),     # -> Gadgets
    31: (106, "Entertainment: Anime"),
    32: (106, "Entertainment: Cartoons"),
}

def get_db():
    return sqlite3.connect(DB_PATH)

def import_opentdb():
    """Import all questions from OpenTriviaDB (free API, ~4000+ questions)"""
    print("\n" + "="*60)
    print("IMPORTING FROM OPENTDB (Free Trivia API)")
    print("="*60)

    # Get NEW session token each time
    token_resp = requests.get("https://opentdb.com/api_token.php?command=request")
    token = token_resp.json().get("token", "")
    print(f"Got session token: {token[:20]}...")

    conn = get_db()
    cur = conn.cursor()
    total = 0

    import random

    for cat_id, (topic_id, cat_name) in OPENTDB_CATEGORIES.items():
        print(f"[{cat_name}]", end=" ", flush=True)

        try:
            url = f"https://opentdb.com/api.php?amount=50&category={cat_id}&type=multiple"
            resp = requests.get(url, timeout=15)
            data = resp.json()

            if data.get("response_code") != 0:
                print("skip", end=" ")
                continue

            questions = data.get("results", [])
            added = 0

            for q in questions:
                question = html.unescape(q["question"])
                correct = html.unescape(q["correct_answer"])
                incorrect = [html.unescape(a) for a in q["incorrect_answers"]]

                options = incorrect + [correct]
                random.shuffle(options)
                answer_idx = options.index(correct)

                difficulty_map = {"easy": 1, "medium": 3, "hard": 5}
                diff = difficulty_map.get(q.get("difficulty", "medium"), 3)

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question,))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (topic_id, question, options[0], options[1], options[2], options[3],
                      answer_idx, diff, "opentdb"))
                added += 1

            conn.commit()
            total += added
            print(f"+{added}", end=" ")
            time.sleep(0.5)

        except Exception as e:
            print(f"err", end=" ")

    print()

    conn.close()
    print(f"\n\nTotal imported from OpenTriviaDB: {total}")
    return total

def import_jeopardy():
    """Import Jeopardy dataset (538,000+ questions from jwolle1)"""
    print("\n" + "="*60)
    print("IMPORTING JEOPARDY DATASET (538,000+ questions)")
    print("="*60)

    # jwolle1's comprehensive TSV dataset
    url = "https://raw.githubusercontent.com/jwolle1/jeopardy_clue_dataset/main/combined_season1-41.tsv"

    print("Downloading TSV dataset (this may take a minute)...", flush=True)

    try:
        resp = requests.get(url, timeout=300, stream=True)
        resp.raise_for_status()
        lines = resp.text.strip().split('\n')
        print(f"Downloaded {len(lines):,} lines")
    except Exception as e:
        print(f"Error downloading: {e}")
        return 0

    conn = get_db()
    cur = conn.cursor()

    # Map Jeopardy categories to our topics
    category_map = {
        "science": 3, "history": 4, "geography": 5, "literature": 6,
        "art": 15, "music": 103, "film": 101, "television": 102, "tv": 102,
        "sports": 301, "food": 600, "animals": 401, "nature": 400,
        "world": 700, "america": 4, "u.s.": 4, "space": 901, "math": 2,
        "movie": 101, "book": 6, "author": 6, "poet": 6, "opera": 103,
        "biology": 10, "chemistry": 9, "physics": 8, "computer": 201,
        "religion": 703, "bible": 703, "mytholog": 4, "war": 4,
        "president": 4, "king": 4, "queen": 4, "country": 5, "capital": 5,
        "ocean": 403, "river": 5, "mountain": 5, "island": 5,
        "animal": 401, "bird": 401, "fish": 401, "mammal": 401,
        "plant": 402, "tree": 402, "flower": 402,
        "car": 501, "plane": 502, "ship": 504, "train": 503,
        "game": 104, "sport": 301, "olymp": 306, "baseball": 304,
        "football": 303, "basketball": 302, "soccer": 301, "tennis": 305,
    }

    total = 0
    skipped = 0
    import random

    # Skip header
    for i, line in enumerate(lines[1:], 1):
        if i % 10000 == 0:
            print(f"Processing {i:,}/{len(lines):,} (added: {total:,})...", end="\r", flush=True)

        try:
            # TSV format: round, clue_value, daily_double_value, category, comments, answer, question, air_date, notes
            parts = line.split('\t')
            if len(parts) < 7:
                continue

            category = parts[3].lower() if len(parts) > 3 else ""
            answer = parts[5].strip() if len(parts) > 5 else ""
            question_text = parts[6].strip() if len(parts) > 6 else ""

            # Clean up the question (remove quotes, HTML)
            question_text = question_text.strip("'\"")
            answer = answer.strip("'\"")

            if not question_text or not answer or len(answer) > 150 or len(question_text) < 10:
                skipped += 1
                continue

            # Determine topic from category
            topic_id = 4  # Default to History
            for key, tid in category_map.items():
                if key in category:
                    topic_id = tid
                    break

            # Check for duplicate
            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
            if cur.fetchone():
                skipped += 1
                continue

            # Generate plausible wrong answers based on answer type
            wrong_answers = generate_wrong_answers(answer)
            options = [answer] + wrong_answers
            random.shuffle(options)
            correct_idx = options.index(answer)

            cur.execute("""
                INSERT INTO question_bank
                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (topic_id, question_text, options[0], options[1], options[2], options[3],
                  correct_idx, 3, "jeopardy"))
            total += 1

            if total % 10000 == 0:
                conn.commit()

        except Exception as e:
            skipped += 1
            continue

    conn.commit()
    conn.close()
    print(f"\nTotal imported from Jeopardy: {total:,} (skipped: {skipped:,})")
    return total

def generate_wrong_answers(correct_answer):
    """Generate plausible wrong answers based on the correct answer."""
    import random

    # Common wrong answer patterns
    generic = ["None of these", "Not applicable", "Unknown"]

    # If it's a number, generate nearby numbers
    try:
        num = int(correct_answer)
        return [str(num + random.randint(1, 10)),
                str(num - random.randint(1, 5)),
                str(num * 2)]
    except:
        pass

    # If it's a year
    if len(correct_answer) == 4 and correct_answer.isdigit():
        year = int(correct_answer)
        return [str(year + random.randint(1, 20)),
                str(year - random.randint(1, 20)),
                str(year + random.randint(50, 100))]

    # If it's a name or word, use generic alternatives
    words = correct_answer.split()
    if len(words) == 1:
        return [f"The {correct_answer}", f"A {correct_answer}", random.choice(generic)]
    elif len(words) == 2:
        return [words[1] + " " + words[0],  # Swap
                words[0] + " Smith",
                random.choice(generic)]
    else:
        return generic

def import_mmlu():
    """Import MMLU dataset (14,000+ academic multiple-choice questions)"""
    print("\n" + "="*60)
    print("IMPORTING MMLU DATASET (Academic Questions)")
    print("="*60)

    # MMLU subjects mapped to our topics
    subject_map = {
        "abstract_algebra": 2, "anatomy": 10, "astronomy": 901, "business_ethics": 700,
        "clinical_knowledge": 800, "college_biology": 10, "college_chemistry": 9,
        "college_computer_science": 201, "college_mathematics": 2, "college_medicine": 800,
        "college_physics": 8, "computer_security": 201, "conceptual_physics": 8,
        "econometrics": 700, "electrical_engineering": 205, "elementary_mathematics": 2,
        "formal_logic": 2, "global_facts": 700, "high_school_biology": 10,
        "high_school_chemistry": 9, "high_school_computer_science": 201,
        "high_school_european_history": 4, "high_school_geography": 5,
        "high_school_government_and_politics": 700, "high_school_macroeconomics": 700,
        "high_school_mathematics": 2, "high_school_microeconomics": 700,
        "high_school_physics": 8, "high_school_psychology": 700,
        "high_school_statistics": 2, "high_school_us_history": 4,
        "high_school_world_history": 4, "human_aging": 800, "human_sexuality": 800,
        "international_law": 700, "jurisprudence": 700, "logical_fallacies": 6,
        "machine_learning": 201, "management": 700, "marketing": 700,
        "medical_genetics": 10, "miscellaneous": 3, "moral_disputes": 700,
        "moral_scenarios": 700, "nutrition": 600, "philosophy": 700,
        "prehistory": 4, "professional_accounting": 700, "professional_law": 700,
        "professional_medicine": 800, "professional_psychology": 700,
        "public_relations": 700, "security_studies": 700, "sociology": 700,
        "us_foreign_policy": 700, "virology": 10, "world_religions": 703,
    }

    # HuggingFace datasets API for MMLU
    base_url = "https://huggingface.co/datasets/cais/mmlu/resolve/main"

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for subject, topic_id in subject_map.items():
        print(f"[{subject}]", end=" ", flush=True)
        try:
            # Try test split first (most questions)
            url = f"{base_url}/{subject}/test-00000-of-00001.parquet"
            resp = requests.get(url, timeout=30)

            if resp.status_code != 200:
                # Try CSV format
                url = f"{base_url}/data/{subject}_test.csv"
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    print("skip", end=" ")
                    continue

                # Parse CSV
                lines = resp.text.strip().split('\n')
                added = 0
                for line in lines[1:]:  # Skip header
                    parts = line.split(',')
                    if len(parts) < 6:
                        continue
                    question_text = parts[0].strip('"')
                    options = [parts[i].strip('"') for i in range(1, 5)]
                    answer_letter = parts[5].strip('"')
                    answer_idx = ord(answer_letter) - ord('A')

                    cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                    if cur.fetchone():
                        continue

                    cur.execute("""
                        INSERT INTO question_bank
                        (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (topic_id, question_text, options[0], options[1], options[2], options[3],
                          answer_idx, 3, "mmlu"))
                    added += 1

                conn.commit()
                total += added
                print(f"+{added}", end=" ")
            else:
                # Parquet format - need pandas
                print("parquet", end=" ")

        except Exception as e:
            print(f"err", end=" ")

    print()
    conn.close()
    print(f"\nTotal imported from MMLU: {total}")
    return total


def import_arc():
    """Import ARC dataset (7,787 science multiple-choice questions)"""
    print("\n" + "="*60)
    print("IMPORTING ARC DATASET (Science Questions)")
    print("="*60)

    # ARC from original source (AllenAI direct download)
    url = "https://ai2-public-datasets.s3.amazonaws.com/arc/ARC-V1-Feb2018.zip"

    print("Downloading ARC dataset...", flush=True)
    import zipfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed to download: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.endswith('.jsonl') and '._' not in name:
                    difficulty = "challenge" if "Challenge" in name else "easy"
                    print(f"  Processing {name.split('/')[-1]}...", end=" ", flush=True)

                    with z.open(name) as f:
                        added = 0
                        for line in f:
                            try:
                                q = json.loads(line.decode('utf-8'))
                                question_text = q.get("question", {}).get("stem", "")
                                choices = q.get("question", {}).get("choices", [])
                                answer_key = q.get("answerKey", "")

                                if not question_text or len(choices) < 4:
                                    continue

                                # Extract options
                                options = []
                                answer_idx = 0
                                for i, choice in enumerate(choices[:4]):
                                    options.append(choice.get("text", ""))
                                    if choice.get("label", "") == answer_key:
                                        answer_idx = i

                                while len(options) < 4:
                                    options.append("N/A")

                                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                                if cur.fetchone():
                                    continue

                                diff = 4 if difficulty == "challenge" else 2

                                cur.execute("""
                                    INSERT INTO question_bank
                                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (3, question_text, options[0], options[1], options[2], options[3],
                                      answer_idx, diff, "arc"))
                                added += 1

                            except (json.JSONDecodeError, KeyError):
                                continue

                        conn.commit()
                        total += added
                        print(f"+{added}")

        conn.close()
        print(f"\nTotal imported from ARC: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_triviaqa():
    """Import TriviaQA dataset (95,000 trivia questions)"""
    print("\n" + "="*60)
    print("IMPORTING TRIVIAQA DATASET (95,000 questions)")
    print("="*60)

    # TriviaQA unfiltered version - smaller download
    url = "https://nlp.cs.washington.edu/triviaqa/data/triviaqa-unfiltered.tar.gz"

    print("Note: TriviaQA requires downloading a 604MB file.")
    print("For faster results, use --arc or --mmlu instead.")
    print("Skipping TriviaQA (use --triviaqa-force to download)")
    return 0


def import_sciq():
    """Import SciQ dataset (13,000+ science questions)"""
    print("\n" + "="*60)
    print("IMPORTING SCIQ DATASET (Science Questions)")
    print("="*60)

    # SciQ from AllenAI S3 (original source)
    url = "https://ai2-public-datasets.s3.amazonaws.com/sciq/SciQ.zip"

    print("Downloading SciQ dataset...", flush=True)
    import zipfile
    import io

    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.endswith('.json') and 'train' in name.lower() and '__MACOSX' not in name:
                    print(f"  Processing {name}...", flush=True)

                    with z.open(name) as f:
                        data = json.load(f)

                        for q in data:
                            question_text = q.get("question", "")
                            correct = q.get("correct_answer", "")

                            if not question_text or not correct:
                                continue

                            options = [
                                correct,
                                q.get("distractor1", "Option B"),
                                q.get("distractor2", "Option C"),
                                q.get("distractor3", "Option D"),
                            ]

                            random.shuffle(options)
                            answer_idx = options.index(correct)

                            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                            if cur.fetchone():
                                continue

                            cur.execute("""
                                INSERT INTO question_bank
                                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (3, question_text, options[0], options[1], options[2], options[3],
                                  answer_idx, 3, "sciq"))
                            total += 1

        conn.commit()
        conn.close()
        print(f"Total imported from SciQ: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0

def import_millionaire():
    """Import Who Wants to Be a Millionaire questions"""
    print("\n" + "="*60)
    print("IMPORTING WHO WANTS TO BE A MILLIONAIRE")
    print("="*60)

    url = "https://raw.githubusercontent.com/aaronnech/Who-Wants-to-Be-a-Millionaire/master/questions.json"

    print("Downloading...", flush=True)
    try:
        resp = requests.get(url, timeout=30)
        data = resp.json()

        conn = get_db()
        cur = conn.cursor()
        total = 0

        # Structure is {"games": [{"questions": [...]}]}
        games = data.get("games", [])
        for game in games:
            questions = game.get("questions", [])
            for q in questions:
                question_text = q.get("question", "")
                content = q.get("content", [])  # List of strings
                correct_idx = q.get("correct", 0)  # Index of correct answer

                if not question_text or len(content) < 4:
                    continue

                options = content[:4]

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (3, question_text, options[0], options[1], options[2], options[3],
                      correct_idx, 3, "millionaire"))
                total += 1

        conn.commit()
        conn.close()
        print(f"Total imported from Millionaire: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_qanta():
    """Import QANTA Quiz Bowl dataset (20,407 questions)"""
    print("\n" + "="*60)
    print("IMPORTING QANTA QUIZ BOWL DATASET")
    print("="*60)

    url = "https://people.cs.umass.edu/~miyyer/data/question_data.tar.gz"

    print("Downloading (31MB)...", flush=True)
    import tarfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0

        with tarfile.open(fileobj=io.BytesIO(resp.content), mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.json'):
                    print(f"  Processing {member.name}...", flush=True)
                    f = tar.extractfile(member)
                    if f:
                        try:
                            data = json.load(f)
                            questions = data if isinstance(data, list) else data.get("questions", [])

                            for q in questions:
                                question_text = q.get("question", "") or q.get("text", "")
                                answer = q.get("answer", "") or q.get("page", "")

                                if not question_text or not answer or len(question_text) < 20:
                                    continue

                                # Generate wrong answers for quiz bowl
                                wrong = generate_wrong_answers(answer)
                                import random
                                options = [answer] + wrong
                                random.shuffle(options)
                                correct_idx = options.index(answer)

                                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text[:200],))
                                if cur.fetchone():
                                    continue

                                # Determine topic from category if available
                                cat = q.get("category", "").lower()
                                topic_id = 4  # Default history
                                if "science" in cat:
                                    topic_id = 3
                                elif "literature" in cat:
                                    topic_id = 6
                                elif "geography" in cat:
                                    topic_id = 5
                                elif "art" in cat:
                                    topic_id = 15

                                cur.execute("""
                                    INSERT INTO question_bank
                                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (topic_id, question_text[:500], options[0], options[1], options[2], options[3],
                                      correct_idx, 4, "qanta"))
                                total += 1

                        except json.JSONDecodeError:
                            continue

        conn.commit()
        conn.close()
        print(f"Total imported from QANTA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_opentriviaqa():
    """Import OpenTriviaQA dataset from GitHub"""
    print("\n" + "="*60)
    print("IMPORTING OPENTRIVIAQA DATASET")
    print("="*60)

    # Download the repo as zip
    url = "https://github.com/uberspot/OpenTriviaQA/archive/refs/heads/master.zip"

    print("Downloading...", flush=True)
    import zipfile
    import io
    import re

    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        # Category to topic mapping
        cat_map = {
            "science": 3, "geography": 5, "history": 4, "literature": 6,
            "music": 103, "art": 15, "sport": 301, "nature": 400,
            "food": 600, "general": 3, "entertainment": 101,
        }

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                # Files don't have extension, just category names
                if '/categories/' in name and not name.endswith('/'):
                    cat_name = name.split('/')[-1].replace('.txt', '').lower()
                    topic_id = 3  # Default
                    for key, tid in cat_map.items():
                        if key in cat_name:
                            topic_id = tid
                            break

                    print(f"  [{cat_name}]", end=" ", flush=True)

                    with z.open(name) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        # Parse the custom format
                        questions = re.split(r'\n#Q ', content)
                        added = 0

                        for q_block in questions:
                            if not q_block.strip():
                                continue

                            lines = q_block.strip().split('\n')
                            if len(lines) < 3:
                                continue

                            question_text = lines[0].replace('#Q ', '').strip()
                            correct = ""
                            options = []

                            for line in lines[1:]:
                                line = line.strip()
                                if line.startswith('^'):
                                    correct = line[1:].strip()
                                elif len(line) > 1 and line[0].isalpha() and line[1] in ' .':
                                    options.append(line[2:].strip())

                            if not question_text or not correct or len(options) < 3:
                                continue

                            # Ensure we have 4 options
                            if correct not in options:
                                options = [correct] + options[:3]
                            while len(options) < 4:
                                options.append("None of these")
                            options = options[:4]

                            random.shuffle(options)
                            try:
                                correct_idx = options.index(correct)
                            except ValueError:
                                continue

                            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                            if cur.fetchone():
                                continue

                            cur.execute("""
                                INSERT INTO question_bank
                                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (topic_id, question_text, options[0], options[1], options[2], options[3],
                                  correct_idx, 3, "opentriviaqa"))
                            added += 1
                            total += 1

                        print(f"+{added}", end=" ")
                        conn.commit()

        print()
        conn.close()
        print(f"Total imported from OpenTriviaQA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_nfl6():
    """Import Yahoo nfL6 dataset (87,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING YAHOO NFL6 DATASET (87,000 questions)")
    print("="*60)

    url = "https://ciir.cs.umass.edu/downloads/nfL6/nfL6.json.gz"

    print("Downloading (48MB)...", flush=True)
    import gzip

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        # Decompress gzip
        content = gzip.decompress(resp.content).decode('utf-8')
        data = json.loads(content)

        print(f"  Processing {len(data)} questions...", flush=True)

        for q in data:
            question_text = q.get("question", "")
            answer = q.get("answer", "") or q.get("nbestanswer", "")

            if not question_text or not answer or len(question_text) < 15:
                continue

            # Truncate long answers
            if len(answer) > 200:
                answer = answer[:200]

            # Generate wrong answers
            wrong = generate_wrong_answers(answer)
            options = [answer] + wrong
            random.shuffle(options)
            correct_idx = options.index(answer)

            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text[:200],))
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO question_bank
                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (3, question_text[:500], options[0][:200], options[1][:200], options[2][:200], options[3][:200],
                  correct_idx, 3, "yahoo"))
            total += 1

            if total % 10000 == 0:
                print(f"    Added {total:,}...", flush=True)
                conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from Yahoo nfL6: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_squad():
    """Import SQuAD dataset (100,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING SQUAD DATASET (100,000 questions)")
    print("="*60)

    urls = [
        "https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v2.0.json",
        "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        print(f"Downloading {url.split('/')[-1]}...", flush=True)
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code != 200:
                print(f"Failed: {resp.status_code}")
                continue

            data = resp.json()
            articles = data.get("data", [])

            for article in articles:
                for para in article.get("paragraphs", []):
                    for qa in para.get("qas", []):
                        question_text = qa.get("question", "")
                        answers = qa.get("answers", [])

                        if not question_text or not answers:
                            # Check for plausible_answers (SQuAD 2.0)
                            answers = qa.get("plausible_answers", [])
                            if not answers:
                                continue

                        answer = answers[0].get("text", "") if answers else ""
                        if not answer or len(answer) > 150:
                            continue

                        # Generate wrong answers
                        wrong = generate_wrong_answers(answer)
                        options = [answer] + wrong
                        random.shuffle(options)
                        correct_idx = options.index(answer)

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question_text, options[0], options[1], options[2], options[3],
                              correct_idx, 3, "squad"))
                        total += 1

            conn.commit()
            print(f"  Added from this file, total so far: {total}")

        except Exception as e:
            print(f"Error: {e}")

    conn.close()
    print(f"Total imported from SQuAD: {total}")
    return total


def import_openbookqa():
    """Import OpenBookQA dataset (5,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING OPENBOOKQA DATASET")
    print("="*60)

    url = "https://ai2-public-datasets.s3.amazonaws.com/open-book-qa/OpenBookQA-V1-Sep2018.zip"

    print("Downloading...", flush=True)
    import zipfile
    import io

    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.endswith('.jsonl') and 'Additional' not in name:
                    print(f"  Processing {name.split('/')[-1]}...", end=" ", flush=True)
                    added = 0

                    with z.open(name) as f:
                        for line in f:
                            try:
                                q = json.loads(line.decode('utf-8'))
                                stem = q.get("question", {}).get("stem", "")
                                choices = q.get("question", {}).get("choices", [])
                                answer_key = q.get("answerKey", "")

                                if not stem or len(choices) < 4:
                                    continue

                                options = [c.get("text", "") for c in choices[:4]]
                                labels = [c.get("label", "") for c in choices[:4]]

                                try:
                                    correct_idx = labels.index(answer_key)
                                except ValueError:
                                    continue

                                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (stem,))
                                if cur.fetchone():
                                    continue

                                cur.execute("""
                                    INSERT INTO question_bank
                                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (3, stem, options[0], options[1], options[2], options[3],
                                      correct_idx, 3, "openbookqa"))
                                added += 1
                                total += 1

                            except json.JSONDecodeError:
                                continue

                    conn.commit()
                    print(f"+{added}")

        conn.close()
        print(f"Total imported from OpenBookQA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_hotpotqa():
    """Import HotpotQA dataset (113,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING HOTPOTQA DATASET (113,000 questions)")
    print("="*60)

    urls = [
        "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json",
        "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        print(f"Downloading {url.split('/')[-1]}...", flush=True)
        try:
            resp = requests.get(url, timeout=300)
            if resp.status_code != 200:
                print(f"Failed: {resp.status_code}")
                continue

            data = resp.json()
            print(f"  Processing {len(data)} questions...", flush=True)

            for i, q in enumerate(data):
                question_text = q.get("question", "")
                answer = q.get("answer", "")

                if not question_text or not answer or len(answer) > 150:
                    continue

                # Generate wrong answers
                wrong = generate_wrong_answers(answer)
                options = [answer] + wrong
                random.shuffle(options)
                correct_idx = options.index(answer)

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                if cur.fetchone():
                    continue

                # Determine difficulty from level
                level = q.get("level", "medium")
                diff_map = {"easy": 2, "medium": 3, "hard": 4}
                diff = diff_map.get(level, 3)

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (3, question_text, options[0], options[1], options[2], options[3],
                      correct_idx, diff, "hotpotqa"))
                total += 1

                if total % 10000 == 0:
                    print(f"    Added {total:,}...", flush=True)
                    conn.commit()

            conn.commit()

        except Exception as e:
            print(f"Error: {e}")

    conn.close()
    print(f"Total imported from HotpotQA: {total}")
    return total


def import_commonsenseqa():
    """Import CommonsenseQA dataset (12,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING COMMONSENSEQA DATASET")
    print("="*60)

    # Direct download from HuggingFace raw
    urls = [
        "https://huggingface.co/datasets/tau/commonsense_qa/resolve/main/data/train.json",
        "https://huggingface.co/datasets/tau/commonsense_qa/resolve/main/data/validation.json",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        print(f"Downloading {url.split('/')[-1]}...", flush=True)
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                # Try JSONL format
                for line in resp.text.strip().split('\n'):
                    try:
                        process_csqa_line(line, cur, total)
                    except:
                        pass
                continue

            # Try JSON array format
            try:
                data = resp.json()
                if isinstance(data, list):
                    for q in data:
                        question_text = q.get("question", {}).get("stem", "")
                        choices = q.get("question", {}).get("choices", [])
                        answer_key = q.get("answerKey", "")

                        if not question_text or len(choices) < 4:
                            continue

                        options = [c.get("text", "") for c in choices[:4]]
                        labels = [c.get("label", "") for c in choices[:4]]

                        try:
                            correct_idx = labels.index(answer_key)
                        except ValueError:
                            continue

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question_text, options[0], options[1], options[2], options[3],
                              correct_idx, 3, "commonsenseqa"))
                        total += 1

            except json.JSONDecodeError:
                # Try JSONL
                for line in resp.text.strip().split('\n'):
                    try:
                        q = json.loads(line)
                        question_text = q.get("question", {}).get("stem", "")
                        choices = q.get("question", {}).get("choices", [])
                        answer_key = q.get("answerKey", "")

                        if not question_text or len(choices) < 4:
                            continue

                        options = [c.get("text", "") for c in choices[:4]]
                        labels = [c.get("label", "") for c in choices[:4]]

                        try:
                            correct_idx = labels.index(answer_key)
                        except ValueError:
                            continue

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question_text, options[0], options[1], options[2], options[3],
                              correct_idx, 3, "commonsenseqa"))
                        total += 1
                    except:
                        continue

            conn.commit()

        except Exception as e:
            print(f"Error: {e}")

    conn.close()
    print(f"Total imported from CommonsenseQA: {total}")
    return total


def import_coqa():
    """Import CoQA dataset (127,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING COQA DATASET (127,000 questions)")
    print("="*60)

    url = "https://nlp.stanford.edu/data/coqa/coqa-train-v1.0.json"

    print("Downloading (47MB)...", flush=True)
    try:
        resp = requests.get(url, timeout=300)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        data = resp.json()
        conversations = data.get("data", [])

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        print(f"  Processing {len(conversations)} conversations...", flush=True)

        for conv in conversations:
            questions = conv.get("questions", [])
            answers = conv.get("answers", [])

            for i, q in enumerate(questions):
                if i >= len(answers):
                    break

                question_text = q.get("input_text", "")
                answer = answers[i].get("input_text", "")

                if not question_text or not answer or len(answer) > 150 or len(question_text) < 10:
                    continue

                # Generate wrong answers
                wrong = generate_wrong_answers(answer)
                options = [answer] + wrong
                random.shuffle(options)
                correct_idx = options.index(answer)

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (3, question_text, options[0], options[1], options[2], options[3],
                      correct_idx, 3, "coqa"))
                total += 1

                if total % 10000 == 0:
                    print(f"    Added {total:,}...", flush=True)
                    conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from CoQA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_quac():
    """Import QuAC dataset (98,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING QUAC DATASET (98,000 questions)")
    print("="*60)

    url = "https://s3.amazonaws.com/my89public/quac/train_v0.2.json"

    print("Downloading...", flush=True)
    try:
        resp = requests.get(url, timeout=300)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        data = resp.json()
        dialogs = data.get("data", [])

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        print(f"  Processing {len(dialogs)} articles...", flush=True)

        for article in dialogs:
            for para in article.get("paragraphs", []):
                for qa in para.get("qas", []):
                    question_text = qa.get("question", "")
                    answers = qa.get("answers", [])

                    if not question_text or not answers:
                        continue

                    answer = answers[0].get("text", "") if answers else ""
                    if not answer or len(answer) > 150:
                        continue

                    # Generate wrong answers
                    wrong = generate_wrong_answers(answer)
                    options = [answer] + wrong
                    random.shuffle(options)
                    correct_idx = options.index(answer)

                    cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                    if cur.fetchone():
                        continue

                    cur.execute("""
                        INSERT INTO question_bank
                        (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (3, question_text, options[0], options[1], options[2], options[3],
                          correct_idx, 3, "quac"))
                    total += 1

                    if total % 10000 == 0:
                        print(f"    Added {total:,}...", flush=True)
                        conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from QuAC: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_triviaapi():
    """Import from The Trivia API (10,000+ questions)"""
    print("\n" + "="*60)
    print("IMPORTING FROM THE TRIVIA API")
    print("="*60)

    # Categories from The Trivia API
    categories = [
        "music", "sport_and_leisure", "film_and_tv", "arts_and_literature",
        "history", "society_and_culture", "science", "geography", "food_and_drink", "general_knowledge"
    ]

    # Map to our topics
    cat_map = {
        "music": 103, "sport_and_leisure": 301, "film_and_tv": 101,
        "arts_and_literature": 6, "history": 4, "society_and_culture": 700,
        "science": 3, "geography": 5, "food_and_drink": 600, "general_knowledge": 3
    }

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for cat in categories:
        print(f"[{cat}]", end=" ", flush=True)
        added = 0

        # Get 50 questions per request, multiple requests per category
        for _ in range(20):  # 20 requests x 50 = 1000 per category max
            try:
                url = f"https://the-trivia-api.com/v2/questions?limit=50&categories={cat}"
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    break

                questions = resp.json()
                if not questions:
                    break

                for q in questions:
                    question_text = q.get("question", {}).get("text", "")
                    correct = q.get("correctAnswer", "")
                    incorrect = q.get("incorrectAnswers", [])

                    if not question_text or not correct or len(incorrect) < 3:
                        continue

                    options = [correct] + incorrect[:3]
                    random.shuffle(options)
                    correct_idx = options.index(correct)

                    cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                    if cur.fetchone():
                        continue

                    topic_id = cat_map.get(cat, 3)
                    diff_map = {"easy": 2, "medium": 3, "hard": 4}
                    diff = diff_map.get(q.get("difficulty", "medium"), 3)

                    cur.execute("""
                        INSERT INTO question_bank
                        (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (topic_id, question_text, options[0], options[1], options[2], options[3],
                          correct_idx, diff, "triviaapi"))
                    added += 1
                    total += 1

                conn.commit()
                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                break

        print(f"+{added}", end=" ")

    print()
    conn.close()
    print(f"Total imported from The Trivia API: {total}")
    return total


def import_triviaqa():
    """Import TriviaQA dataset (110,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING TRIVIAQA DATASET (110,000 questions)")
    print("="*60)

    url = "http://nlp.cs.washington.edu/triviaqa/data/triviaqa-unfiltered.tar.gz"

    print("Downloading (604MB)...", flush=True)
    import tarfile
    import io

    try:
        resp = requests.get(url, timeout=600, stream=True)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        # Extract from tar.gz
        with tarfile.open(fileobj=io.BytesIO(resp.content), mode='r:gz') as tar:
            for member in tar.getmembers():
                if 'unfiltered-web-train.json' in member.name:
                    print(f"  Processing {member.name}...", flush=True)
                    f = tar.extractfile(member)
                    data = json.load(f)

                    questions = data.get("Data", [])
                    print(f"  Found {len(questions)} questions", flush=True)

                    for q in questions:
                        question_text = q.get("Question", "")
                        answer_data = q.get("Answer", {})
                        answer = answer_data.get("Value", "") if isinstance(answer_data, dict) else str(answer_data)

                        if not question_text or not answer or len(answer) > 150:
                            continue

                        # Generate wrong answers
                        wrong = generate_wrong_answers(answer)
                        options = [answer] + wrong
                        random.shuffle(options)
                        correct_idx = options.index(answer)

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text[:200],))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question_text[:500], options[0][:200], options[1][:200], options[2][:200], options[3][:200],
                              correct_idx, 3, "triviaqa"))
                        total += 1

                        if total % 10000 == 0:
                            print(f"    Added {total:,}...", flush=True)
                            conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from TriviaQA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_cmu_qa():
    """Import CMU Question Answer dataset"""
    print("\n" + "="*60)
    print("IMPORTING CMU QA DATASET")
    print("="*60)

    url = "http://www.cs.cmu.edu/~ark/QA-data/data/Question_Answer_Dataset_v1.2.tar.gz"

    print("Downloading...", flush=True)
    import tarfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with tarfile.open(fileobj=io.BytesIO(resp.content), mode='r:gz') as tar:
            for member in tar.getmembers():
                if 'question_answer_pairs.txt' in member.name and '._' not in member.name:
                    print(f"  Processing {member.name}...", flush=True)
                    f = tar.extractfile(member)
                    content = f.read().decode('utf-8', errors='ignore')

                    for line in content.strip().split('\n'):
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            # Format: ArticleTitle Question Answer DifficultyFromQuestioner DifficultyFromAnswerer ArticleFile
                            question_text = parts[1].strip()
                            answer = parts[2].strip()

                            if not question_text or not answer or len(answer) > 150:
                                continue

                            wrong = generate_wrong_answers(answer)
                            options = [answer] + wrong
                            random.shuffle(options)
                            correct_idx = options.index(answer)

                            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                            if cur.fetchone():
                                continue

                            cur.execute("""
                                INSERT INTO question_bank
                                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (3, question_text, options[0], options[1], options[2], options[3],
                                  correct_idx, 3, "cmuqa"))
                            total += 1

        conn.commit()
        conn.close()
        print(f"Total imported from CMU QA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_elcms_trivia():
    """Import el-cms Open Trivia Database"""
    print("\n" + "="*60)
    print("IMPORTING EL-CMS OPEN TRIVIA DATABASE")
    print("="*60)

    # Fetch the file list from GitHub API
    base_url = "https://api.github.com/repos/el-cms/Open-trivia-database/contents/en"

    try:
        resp = requests.get(base_url, timeout=30)
        if resp.status_code != 200:
            print(f"Failed to list files: {resp.status_code}")
            return 0

        files = resp.json()
        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        for f in files:
            if f['name'].endswith('.json') and not f['name'].startswith('.'):
                print(f"  [{f['name']}]", end=" ", flush=True)
                file_resp = requests.get(f['download_url'], timeout=30)
                if file_resp.status_code != 200:
                    continue

                questions = file_resp.json()
                added = 0

                for q in questions:
                    question_text = q.get("question", "")
                    answer = q.get("answer", "")
                    wrong_answers = q.get("answers", [])

                    if not question_text or not answer:
                        continue

                    if len(wrong_answers) >= 3:
                        options = [answer] + wrong_answers[:3]
                    else:
                        wrong = generate_wrong_answers(answer)
                        options = [answer] + wrong

                    random.shuffle(options)
                    correct_idx = options.index(answer)

                    cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                    if cur.fetchone():
                        continue

                    cur.execute("""
                        INSERT INTO question_bank
                        (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (3, question_text, options[0], options[1], options[2], options[3],
                          correct_idx, 3, "elcms"))
                    added += 1
                    total += 1

                print(f"+{added}", end=" ")
                conn.commit()

        print()
        conn.close()
        print(f"Total imported from el-cms: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_narrativeqa():
    """Import NarrativeQA dataset (46,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING NARRATIVEQA DATASET (46,000 questions)")
    print("="*60)

    url = "https://raw.githubusercontent.com/google-deepmind/narrativeqa/master/qaps.csv"

    print("Downloading...", flush=True)
    import csv

    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        reader = csv.DictReader(resp.text.strip().split('\n'))

        for row in reader:
            question_text = row.get('question', '')
            answer1 = row.get('answer1', '')
            answer2 = row.get('answer2', '')

            if not question_text or not answer1:
                continue

            # Use answer1 as the correct answer
            answer = answer1.strip()
            if len(answer) > 150:
                continue

            wrong = generate_wrong_answers(answer)
            options = [answer] + wrong
            random.shuffle(options)
            correct_idx = options.index(answer)

            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO question_bank
                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (3, question_text, options[0], options[1], options[2], options[3],
                  correct_idx, 3, "narrativeqa"))
            total += 1

            if total % 10000 == 0:
                print(f"  Added {total:,}...", flush=True)
                conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from NarrativeQA: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_duorc():
    """Import DuoRC dataset (186,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING DUORC DATASET (186,000 questions)")
    print("="*60)

    urls = [
        "https://raw.githubusercontent.com/duorc/duorc/master/dataset/SelfRC_train.json",
        "https://raw.githubusercontent.com/duorc/duorc/master/dataset/SelfRC_dev.json",
        "https://raw.githubusercontent.com/duorc/duorc/master/dataset/ParaphraseRC_train.json",
        "https://raw.githubusercontent.com/duorc/duorc/master/dataset/ParaphraseRC_dev.json",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        filename = url.split('/')[-1]
        print(f"  Downloading {filename}...", flush=True)

        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code != 200:
                print(f"    Failed: {resp.status_code}")
                continue

            data = resp.json()

            for story in data:
                for qa in story.get('qa', []):
                    question_text = qa.get('question', '')
                    answers = qa.get('answers', [])

                    if not question_text or not answers:
                        continue

                    answer = answers[0].strip() if answers else ''
                    if not answer or len(answer) > 150:
                        continue

                    wrong = generate_wrong_answers(answer)
                    options = [answer] + wrong
                    random.shuffle(options)
                    correct_idx = options.index(answer)

                    cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                    if cur.fetchone():
                        continue

                    cur.execute("""
                        INSERT INTO question_bank
                        (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (3, question_text, options[0], options[1], options[2], options[3],
                          correct_idx, 3, "duorc"))
                    total += 1

                    if total % 10000 == 0:
                        print(f"    Added {total:,}...", flush=True)
                        conn.commit()

            conn.commit()
            print(f"    +{total} so far")

        except Exception as e:
            print(f"    Error: {e}")

    conn.close()
    print(f"Total imported from DuoRC: {total}")
    return total


def import_hellaswag():
    """Import HellaSwag dataset (50,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING HELLASWAG DATASET (50,000 questions)")
    print("="*60)

    urls = [
        "https://raw.githubusercontent.com/rowanz/hellaswag/master/data/hellaswag_train.jsonl",
        "https://raw.githubusercontent.com/rowanz/hellaswag/master/data/hellaswag_val.jsonl",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        filename = url.split('/')[-1]
        print(f"  Downloading {filename}...", flush=True)

        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code != 200:
                print(f"    Failed: {resp.status_code}")
                continue

            for line in resp.text.strip().split('\n'):
                try:
                    data = json.loads(line)
                except:
                    continue

                ctx = data.get('ctx', '')
                endings = data.get('endings', [])
                label = data.get('label', -1)

                if not ctx or len(endings) < 4 or label < 0 or label >= len(endings):
                    continue

                # Question is the context, options are the endings
                question_text = f"Complete: {ctx}"
                options = endings[:4]
                correct_idx = label

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text[:200],))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (3, question_text[:500], options[0][:200], options[1][:200], options[2][:200], options[3][:200],
                      correct_idx, 3, "hellaswag"))
                total += 1

                if total % 10000 == 0:
                    print(f"    Added {total:,}...", flush=True)
                    conn.commit()

            conn.commit()

        except Exception as e:
            print(f"    Error: {e}")

    conn.close()
    print(f"Total imported from HellaSwag: {total}")
    return total


def import_drop():
    """Import DROP dataset (96,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING DROP DATASET (96,000 questions)")
    print("="*60)

    url = "https://s3-us-west-2.amazonaws.com/allennlp/datasets/drop/drop_dataset.zip"

    print("Downloading (8MB)...", flush=True)
    import zipfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if 'train' in name and name.endswith('.json'):
                    print(f"  Processing {name}...", flush=True)
                    with zf.open(name) as f:
                        data = json.load(f)

                    for passage_id, passage_data in data.items():
                        for qa in passage_data.get('qa_pairs', []):
                            question_text = qa.get('question', '')
                            answer_data = qa.get('answer', {})

                            # Get the answer (can be number, span, or date)
                            answer = None
                            if answer_data.get('number'):
                                answer = str(answer_data['number'])
                            elif answer_data.get('spans'):
                                answer = answer_data['spans'][0]
                            elif answer_data.get('date'):
                                date = answer_data['date']
                                answer = f"{date.get('month', '')}/{date.get('day', '')}/{date.get('year', '')}".strip('/')

                            if not question_text or not answer or len(answer) > 150:
                                continue

                            wrong = generate_wrong_answers(answer)
                            options = [answer] + wrong
                            random.shuffle(options)
                            correct_idx = options.index(answer)

                            cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                            if cur.fetchone():
                                continue

                            cur.execute("""
                                INSERT INTO question_bank
                                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (3, question_text, options[0], options[1], options[2], options[3],
                                  correct_idx, 4, "drop"))
                            total += 1

                            if total % 10000 == 0:
                                print(f"    Added {total:,}...", flush=True)
                                conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from DROP: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_winogrande():
    """Import WinoGrande dataset (44,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING WINOGRANDE DATASET (44,000 questions)")
    print("="*60)

    url = "https://storage.googleapis.com/ai2-mosaic/public/winogrande/winogrande_1.1.zip"

    print("Downloading (3MB)...", flush=True)
    import zipfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if 'train' in name and name.endswith('.jsonl'):
                    print(f"  Processing {name}...", flush=True)
                    with zf.open(name) as f:
                        content = f.read().decode('utf-8')

                    for line in content.strip().split('\n'):
                        try:
                            data = json.loads(line)
                        except:
                            continue

                        sentence = data.get('sentence', '')
                        option1 = data.get('option1', '')
                        option2 = data.get('option2', '')
                        answer_key = data.get('answer', '')

                        if not sentence or not option1 or not option2:
                            continue

                        # Create question from sentence with blank
                        question_text = sentence

                        if answer_key == '1':
                            correct = option1
                            wrong_opt = option2
                        elif answer_key == '2':
                            correct = option2
                            wrong_opt = option1
                        else:
                            continue

                        # Generate more wrong answers
                        wrong = [wrong_opt] + generate_wrong_answers(correct)[:2]
                        options = [correct] + wrong
                        random.shuffle(options)
                        correct_idx = options.index(correct)

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question_text, options[0], options[1], options[2], options[3],
                              correct_idx, 3, "winogrande"))
                        total += 1

                        if total % 10000 == 0:
                            print(f"    Added {total:,}...", flush=True)
                            conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from WinoGrande: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def import_boolq():
    """Import BoolQ dataset (16,000 yes/no questions)"""
    print("\n" + "="*60)
    print("IMPORTING BOOLQ DATASET (16,000 questions)")
    print("="*60)

    urls = [
        "https://raw.githubusercontent.com/google-research-datasets/boolean-questions/master/train.jsonl",
        "https://raw.githubusercontent.com/google-research-datasets/boolean-questions/master/dev.jsonl",
    ]

    conn = get_db()
    cur = conn.cursor()
    total = 0
    import random

    for url in urls:
        filename = url.split('/')[-1]
        print(f"  Downloading {filename}...", flush=True)

        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                print(f"    Failed: {resp.status_code}")
                continue

            for line in resp.text.strip().split('\n'):
                try:
                    data = json.loads(line)
                except:
                    continue

                question_text = data.get('question', '')
                answer = data.get('answer', False)

                if not question_text:
                    continue

                # Convert yes/no to options
                if answer:
                    correct = "Yes"
                    wrong = ["No", "Maybe", "Not enough information"]
                else:
                    correct = "No"
                    wrong = ["Yes", "Maybe", "Not enough information"]

                options = [correct] + wrong
                random.shuffle(options)
                correct_idx = options.index(correct)

                cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question_text,))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (3, question_text, options[0], options[1], options[2], options[3],
                      correct_idx, 3, "boolq"))
                total += 1

            conn.commit()

        except Exception as e:
            print(f"    Error: {e}")

    conn.close()
    print(f"Total imported from BoolQ: {total}")
    return total


def import_race():
    """Import RACE dataset (100,000 questions)"""
    print("\n" + "="*60)
    print("IMPORTING RACE DATASET (100,000 questions)")
    print("="*60)

    url = "http://www.cs.cmu.edu/~glai1/data/race/RACE.tar.gz"

    print("Downloading (24MB)...", flush=True)
    import tarfile
    import io

    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code != 200:
            print(f"Failed: {resp.status_code}")
            return 0

        conn = get_db()
        cur = conn.cursor()
        total = 0
        import random

        with tarfile.open(fileobj=io.BytesIO(resp.content), mode='r:gz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.txt') and '._' not in member.name:
                    f = tar.extractfile(member)
                    if not f:
                        continue
                    content = f.read().decode('utf-8', errors='ignore')
                    try:
                        data = json.loads(content)
                    except:
                        continue

                    article = data.get('article', '')
                    questions = data.get('questions', [])
                    options_list = data.get('options', [])
                    answers = data.get('answers', [])

                    for i, question in enumerate(questions):
                        if i >= len(options_list) or i >= len(answers):
                            continue

                        options = options_list[i]
                        answer_key = answers[i]

                        if len(options) < 4:
                            continue

                        # Convert A/B/C/D to index
                        answer_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                        if answer_key not in answer_map:
                            continue

                        correct_idx = answer_map[answer_key]

                        cur.execute("SELECT 1 FROM question_bank WHERE question = ?", (question,))
                        if cur.fetchone():
                            continue

                        cur.execute("""
                            INSERT INTO question_bank
                            (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (3, question, options[0][:200], options[1][:200], options[2][:200], options[3][:200],
                              correct_idx, 3, "race"))
                        total += 1

                        if total % 10000 == 0:
                            print(f"  Added {total:,}...", flush=True)
                            conn.commit()

        conn.commit()
        conn.close()
        print(f"Total imported from RACE: {total}")
        return total

    except Exception as e:
        print(f"Error: {e}")
        return 0


def show_stats():
    """Show current database stats"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM question_bank")
    total = cur.fetchone()[0]

    cur.execute("SELECT source, COUNT(*) FROM question_bank GROUP BY source")
    by_source = cur.fetchall()

    print("\n" + "="*60)
    print("CURRENT DATABASE STATS")
    print("="*60)
    print(f"Total questions: {total:,}")
    print("\nBy source:")
    for source, count in by_source:
        print(f"  {source or 'built-in'}: {count:,}")

    conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bulk import free question datasets")
    parser.add_argument("--opentdb", action="store_true", help="Import from OpenTriviaDB (~4000 questions)")
    parser.add_argument("--jeopardy", action="store_true", help="Import Jeopardy dataset (~100,000 questions)")
    parser.add_argument("--sciq", action="store_true", help="Import SciQ science questions (~13,000)")
    parser.add_argument("--mmlu", action="store_true", help="Import MMLU academic questions (~14,000)")
    parser.add_argument("--arc", action="store_true", help="Import ARC science questions (~7,800)")
    parser.add_argument("--millionaire", action="store_true", help="Import Who Wants to Be a Millionaire")
    parser.add_argument("--qanta", action="store_true", help="Import QANTA Quiz Bowl (~20,000)")
    parser.add_argument("--opentriviaqa", action="store_true", help="Import OpenTriviaQA")
    parser.add_argument("--yahoo", action="store_true", help="Import Yahoo nfL6 (~87,000)")
    parser.add_argument("--squad", action="store_true", help="Import SQuAD (~100,000)")
    parser.add_argument("--openbookqa", action="store_true", help="Import OpenBookQA (~5,000)")
    parser.add_argument("--hotpotqa", action="store_true", help="Import HotpotQA (~113,000)")
    parser.add_argument("--commonsenseqa", action="store_true", help="Import CommonsenseQA (~12,000)")
    parser.add_argument("--triviaapi", action="store_true", help="Import The Trivia API (~10,000)")
    parser.add_argument("--coqa", action="store_true", help="Import CoQA (~127,000)")
    parser.add_argument("--quac", action="store_true", help="Import QuAC (~98,000)")
    parser.add_argument("--triviaqa", action="store_true", help="Import TriviaQA (~110,000)")
    parser.add_argument("--cmuqa", action="store_true", help="Import CMU QA dataset")
    parser.add_argument("--elcms", action="store_true", help="Import el-cms Open Trivia")
    parser.add_argument("--narrativeqa", action="store_true", help="Import NarrativeQA (~46,000)")
    parser.add_argument("--duorc", action="store_true", help="Import DuoRC (~186,000)")
    parser.add_argument("--race", action="store_true", help="Import RACE (~100,000)")
    parser.add_argument("--boolq", action="store_true", help="Import BoolQ (~16,000)")
    parser.add_argument("--drop", action="store_true", help="Import DROP (~96,000)")
    parser.add_argument("--winogrande", action="store_true", help="Import WinoGrande (~44,000)")
    parser.add_argument("--hellaswag", action="store_true", help="Import HellaSwag (~50,000)")
    parser.add_argument("--all", action="store_true", help="Import from all sources")
    parser.add_argument("--stats", action="store_true", help="Show database stats")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    total = 0

    if args.all or args.opentdb:
        total += import_opentdb()

    if args.all or args.jeopardy:
        total += import_jeopardy()

    if args.all or args.sciq:
        total += import_sciq()

    if args.all or args.mmlu:
        total += import_mmlu()

    if args.all or args.arc:
        total += import_arc()

    if args.all or args.millionaire:
        total += import_millionaire()

    if args.all or args.qanta:
        total += import_qanta()

    if args.all or args.opentriviaqa:
        total += import_opentriviaqa()

    if args.all or args.yahoo:
        total += import_nfl6()

    if args.all or args.squad:
        total += import_squad()

    if args.all or args.openbookqa:
        total += import_openbookqa()

    if args.all or args.hotpotqa:
        total += import_hotpotqa()

    if args.all or args.commonsenseqa:
        total += import_commonsenseqa()

    if args.all or args.triviaapi:
        total += import_triviaapi()

    if args.all or args.coqa:
        total += import_coqa()

    if args.all or args.quac:
        total += import_quac()

    if args.all or args.triviaqa:
        total += import_triviaqa()

    if args.all or args.cmuqa:
        total += import_cmu_qa()

    if args.all or args.elcms:
        total += import_elcms_trivia()

    if args.all or args.narrativeqa:
        total += import_narrativeqa()

    if args.all or args.duorc:
        total += import_duorc()

    if args.all or args.race:
        total += import_race()

    if args.all or args.boolq:
        total += import_boolq()

    if args.all or args.drop:
        total += import_drop()

    if args.all or args.winogrande:
        total += import_winogrande()

    if args.all or args.hellaswag:
        total += import_hellaswag()

    if total > 0:
        print("\n" + "="*60)
        print(f"IMPORT COMPLETE: {total:,} questions added")
        print("="*60)
        show_stats()
    elif not args.stats:
        print("Usage:")
        print("  --opentdb    Import OpenTriviaDB (~4,000 verified questions)")
        print("  --jeopardy   Import Jeopardy (~100,000 questions)")
        print("  --sciq       Import SciQ (~13,000 science questions)")
        print("  --mmlu       Import MMLU (~14,000 academic questions)")
        print("  --arc        Import ARC (~7,800 science questions)")
        print("  --all        Import from all sources")
        print("  --stats      Show current database stats")

if __name__ == "__main__":
    main()
