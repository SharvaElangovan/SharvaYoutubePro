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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_GEN_PATH = os.path.join(SCRIPT_DIR, "video_generator")
DB_PATH = "/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db"
OUTPUT_DIR = os.path.join(VIDEO_GEN_PATH, "output")
LOG_FILE = os.path.join(SCRIPT_DIR, "daily_upload.log")

sys.path.insert(0, VIDEO_GEN_PATH)

DISCORD_WEBHOOK = None  # Set your webhook URL here or in settings table
MAX_RETRIES = 3  # Number of times to retry failed uploads
RETRY_DELAY = 30  # Seconds between retries

def get_setting(key):
    """Get a setting from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

def get_discord_webhook():
    """Get Discord webhook URL from settings."""
    global DISCORD_WEBHOOK
    if DISCORD_WEBHOOK:
        return DISCORD_WEBHOOK
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'discord_webhook'")
        row = cur.fetchone()
        conn.close()
        if row:
            DISCORD_WEBHOOK = row[0]
            return DISCORD_WEBHOOK
    except:
        pass
    return None

def send_discord_notification(message, color=0x00ff00):
    """Send notification to Discord webhook."""
    webhook_url = get_discord_webhook()
    if not webhook_url:
        return

    import urllib.request
    data = json.dumps({
        "embeds": [{
            "title": "YouTube Upload Bot",
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }]
    }).encode()

    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def send_email_alert(subject, message):
    """Send email alert using SMTP settings from database."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = get_setting('smtp_host')
    smtp_port = get_setting('smtp_port') or '587'
    smtp_user = get_setting('smtp_user')
    smtp_pass = get_setting('smtp_password')
    email_to = get_setting('alert_email')

    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email_to
        msg['Subject'] = f"[YouTube Bot] {subject}"

        body = f"""
{message}

---
Sent by SharvaYoutubePro Upload Bot
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, email_to, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        log(f"Email alert failed: {e}")
        return False

def upload_with_retry(video_path, title, description, is_short=False):
    """Upload video with automatic retry on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        video_id, error = upload_video(video_path, title, description, is_short)

        if video_id:
            return video_id, None

        if error == "LIMIT_REACHED":
            return None, "LIMIT_REACHED"

        if attempt < MAX_RETRIES:
            log(f"  Upload failed (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY * attempt)  # Exponential backoff
        else:
            log(f"  Upload failed after {MAX_RETRIES} attempts")
            send_discord_notification(
                f"Upload failed after {MAX_RETRIES} attempts!\n"
                f"Title: {title}\n"
                f"Error: {error}",
                0xff0000
            )

    return None, "MAX_RETRIES_EXCEEDED"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def fetch_questions_from_opentdb(count):
    """Fetch questions from Open Trivia Database API as backup."""
    import urllib.request
    import html

    try:
        url = f"https://opentdb.com/api.php?amount={count}&type=multiple"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        if data.get('response_code') != 0:
            return []

        questions = []
        for item in data.get('results', []):
            # Decode HTML entities
            question = html.unescape(item['question'])
            correct = html.unescape(item['correct_answer'])
            incorrect = [html.unescape(a) for a in item['incorrect_answers']]

            # Shuffle options
            options = incorrect + [correct]
            import random
            random.shuffle(options)
            answer_idx = options.index(correct)

            questions.append({
                'question': question,
                'options': options,
                'answer': answer_idx,
                'from_api': True  # Mark as API-sourced (no ID to mark as used)
            })

        log(f"  Fetched {len(questions)} backup questions from OpenTDB API")
        return questions

    except Exception as e:
        log(f"  OpenTDB API error: {e}")
        return []


def get_questions(count, for_shorts=False, use_backup=True):
    """Fetch unused questions from database, with API fallback."""
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

    # If not enough questions, try backup API
    if len(questions) < count and use_backup:
        needed = count - len(questions)
        log(f"  Only {len(questions)} local questions, fetching {needed} from backup API...")
        backup = fetch_questions_from_opentdb(needed)
        questions.extend(backup)

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


def upload_thumbnail(video_id, thumbnail_path):
    """Upload a custom thumbnail for a video."""
    import urllib.request
    import urllib.error

    if not os.path.exists(thumbnail_path):
        log(f"  Thumbnail not found: {thumbnail_path}")
        return False

    token = get_oauth_token()
    if not token:
        token = refresh_token()
    if not token:
        return False

    try:
        with open(thumbnail_path, 'rb') as f:
            thumbnail_data = f.read()

        # Determine content type
        content_type = 'image/jpeg' if thumbnail_path.endswith('.jpg') else 'image/png'

        req = urllib.request.Request(
            f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}',
            data=thumbnail_data,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': content_type
            },
            method='POST'
        )

        with urllib.request.urlopen(req) as resp:
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        log(f"  Thumbnail upload failed: {e.code} - {error_body[:100]}")
        return False
    except Exception as e:
        log(f"  Thumbnail upload error: {e}")
        return False


def generate_and_upload_shorts(use_themes=True):
    """Generate and upload short-form videos until YouTube limit."""
    from generators import ShortsGenerator
    from sound_effects import TitleGenerator, TopicCategories

    log("=== Generating Shorts until YouTube limit ===")

    topic_cats = TopicCategories(DB_PATH)
    categories = ['Science', 'History', 'Entertainment', 'Sports', 'Nature', 'Geography', None]  # None = general
    cat_idx = 0

    i = 0
    while True:
        i += 1

        # Rotate through categories for variety
        category = categories[cat_idx % len(categories)] if use_themes else None
        cat_idx += 1

        if category:
            questions, ids = topic_cats.get_questions_by_category(category, 5, for_shorts=True)
            if len(questions) < 5:
                log(f"Not enough {category} questions, using general...")
                questions, ids = get_questions(5, for_shorts=True)
                category = None
        else:
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
                title = TitleGenerator.generate_shorts_title(5, category=category)
                desc = TitleGenerator.generate_description(5, is_shorts=True, category=category)

                video_id, error = upload_video(output_path, title, desc, is_short=True)

                if video_id:
                    mark_used(ids)
                    cat_text = f" ({category})" if category else ""
                    log(f"✓ Short #{i}{cat_text} uploaded: https://youtube.com/watch?v={video_id}")
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

def generate_and_upload_longform(use_themes=True):
    """Generate and upload long-form videos until YouTube limit."""
    from generators import GeneralKnowledgeGenerator
    from sound_effects import TitleGenerator, TopicCategories

    log("=== Generating Long-form Videos until YouTube limit ===")

    topic_cats = TopicCategories(DB_PATH)
    categories = ['Science', 'History', 'Entertainment', 'Nature', None]  # Fewer categories for longform
    cat_idx = 0

    i = 0
    while True:
        i += 1

        # Rotate through categories
        category = categories[cat_idx % len(categories)] if use_themes else None
        cat_idx += 1

        if category:
            questions, ids = topic_cats.get_questions_by_category(category, 50, for_shorts=False)
            if len(questions) < 50:
                log(f"Not enough {category} questions for longform, using general...")
                questions, ids = get_questions(50, for_shorts=False)
                category = None
        else:
            questions, ids = get_questions(50, for_shorts=False)

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
                title = TitleGenerator.generate_longform_title(50, category=category)
                desc = TitleGenerator.generate_description(50, is_shorts=False, category=category)

                video_id, error = upload_video(output_path, title, desc, is_short=False)

                if video_id:
                    mark_used(ids)
                    cat_text = f" ({category})" if category else ""
                    log(f"✓ Long-form #{i}{cat_text} uploaded: https://youtube.com/watch?v={video_id}")
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

def generate_one_short(topic_cats, categories, cat_idx):
    """Generate and upload a single short. Returns (success, new_cat_idx, error)."""
    from generators import ShortsGenerator
    from sound_effects import TitleGenerator

    category = categories[cat_idx % len(categories)]
    cat_idx += 1

    if category:
        questions, ids = topic_cats.get_questions_by_category(category, 5, for_shorts=True)
        if len(questions) < 5:
            questions, ids = get_questions(5, for_shorts=True)
            category = None
    else:
        questions, ids = get_questions(5, for_shorts=True)

    if len(questions) < 5:
        return False, cat_idx, "NO_QUESTIONS"

    filename = f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, filename)
    thumbnail_path = output_path.replace('.mp4', '_thumb.jpg')

    try:
        generator = ShortsGenerator()
        generator.generate(questions, filename, enable_tts=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            title = TitleGenerator.generate_shorts_title(5, category=category)
            desc = TitleGenerator.generate_description(5, is_shorts=True, category=category)

            # Generate thumbnail
            first_question = questions[0].get('question', 'Quiz Time!')[:50]
            generator.generate_thumbnail(first_question, thumbnail_path, category=category)

            video_id, error = upload_with_retry(output_path, title, desc, is_short=True)
            os.remove(output_path)

            if video_id:
                # Upload thumbnail
                if os.path.exists(thumbnail_path):
                    upload_thumbnail(video_id, thumbnail_path)
                    os.remove(thumbnail_path)

                mark_used(ids)
                cat_text = f" ({category})" if category else ""
                log(f"✓ Short{cat_text}: https://youtube.com/watch?v={video_id}")
                return True, cat_idx, None
            else:
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
                return False, cat_idx, error
        else:
            return False, cat_idx, "GEN_FAILED"
    except Exception as e:
        log(f"✗ Short error: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        return False, cat_idx, "ERROR"


def generate_one_longform(topic_cats, categories, cat_idx):
    """Generate and upload a single longform video. Returns (success, new_cat_idx, error)."""
    from generators import GeneralKnowledgeGenerator
    from sound_effects import TitleGenerator

    category = categories[cat_idx % len(categories)]
    cat_idx += 1

    if category:
        questions, ids = topic_cats.get_questions_by_category(category, 50, for_shorts=False)
        if len(questions) < 50:
            questions, ids = get_questions(50, for_shorts=False)
            category = None
    else:
        questions, ids = get_questions(50, for_shorts=False)

    if len(questions) < 50:
        return False, cat_idx, "NO_QUESTIONS"

    filename = f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(OUTPUT_DIR, filename)
    thumbnail_path = output_path.replace('.mp4', '_thumb.jpg')

    try:
        generator = GeneralKnowledgeGenerator(
            width=1920, height=1080,
            question_time=10, answer_time=5
        )
        generator.generate(questions, filename, enable_tts=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            title = TitleGenerator.generate_longform_title(50, category=category)
            desc = TitleGenerator.generate_description(50, is_shorts=False, category=category)

            # Generate thumbnail
            cat_text_thumb = f" {category}" if category else ""
            generator.generate_thumbnail(f"50{cat_text_thumb} Quiz Questions", "Test Your Knowledge!", thumbnail_path, category=category)

            video_id, error = upload_with_retry(output_path, title, desc, is_short=False)
            os.remove(output_path)

            if video_id:
                # Upload thumbnail
                if os.path.exists(thumbnail_path):
                    upload_thumbnail(video_id, thumbnail_path)
                    os.remove(thumbnail_path)

                mark_used(ids)
                cat_text = f" ({category})" if category else ""
                log(f"✓ Longform{cat_text}: https://youtube.com/watch?v={video_id}")
                return True, cat_idx, None
            else:
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
                return False, cat_idx, error
        else:
            return False, cat_idx, "GEN_FAILED"
    except Exception as e:
        log(f"✗ Longform error: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        return False, cat_idx, "ERROR"


class VideoQueue:
    """Priority queue for video generation and uploads."""

    PRIORITY_HIGH = 1
    PRIORITY_NORMAL = 2
    PRIORITY_LOW = 3

    def __init__(self):
        self.queue = []  # List of (priority, timestamp, task)
        self.completed = []
        self.failed = []

    def add_task(self, task_type, config, priority=PRIORITY_NORMAL):
        """Add a task to the queue."""
        import heapq
        task = {
            'type': task_type,  # 'short', 'longform', 'truefalse'
            'config': config,
            'status': 'pending',
            'created': datetime.now().isoformat()
        }
        heapq.heappush(self.queue, (priority, datetime.now().timestamp(), task))
        return task

    def add_shorts(self, count, priority=PRIORITY_NORMAL, **config):
        """Add short video generation tasks."""
        for i in range(count):
            self.add_task('short', {'index': i, **config}, priority)

    def add_longform(self, count, priority=PRIORITY_NORMAL, **config):
        """Add longform video generation tasks."""
        for i in range(count):
            self.add_task('longform', {'index': i, **config}, priority)

    def get_next(self):
        """Get next task from queue."""
        import heapq
        if self.queue:
            priority, timestamp, task = heapq.heappop(self.queue)
            task['status'] = 'processing'
            return task
        return None

    def mark_complete(self, task, video_id=None):
        """Mark task as completed."""
        task['status'] = 'completed'
        task['video_id'] = video_id
        task['completed'] = datetime.now().isoformat()
        self.completed.append(task)

    def mark_failed(self, task, error=None):
        """Mark task as failed."""
        task['status'] = 'failed'
        task['error'] = error
        self.failed.append(task)

    def get_stats(self):
        """Get queue statistics."""
        return {
            'pending': len(self.queue),
            'completed': len(self.completed),
            'failed': len(self.failed),
            'total': len(self.queue) + len(self.completed) + len(self.failed)
        }

    def process_all(self):
        """Process all tasks in queue."""
        from sound_effects import TopicCategories, TitleGenerator

        topic_cats = TopicCategories(DB_PATH)
        short_categories = ['Science', 'History', 'Entertainment', 'Sports', 'Nature', None]
        long_categories = ['Science', 'History', 'Entertainment', 'Nature', None]
        cat_idx = 0

        while self.queue:
            task = self.get_next()
            if not task:
                break

            task_type = task['type']
            log(f"Processing {task_type} task (priority queue)...")

            try:
                if task_type in ['short', 'truefalse']:
                    category = short_categories[cat_idx % len(short_categories)]
                    cat_idx += 1

                    if category:
                        questions, ids = topic_cats.get_questions_by_category(category, 5, for_shorts=True)
                        if len(questions) < 5:
                            questions, ids = get_questions(5, for_shorts=True)
                            category = None
                    else:
                        questions, ids = get_questions(5, for_shorts=True)

                    if len(questions) < 5:
                        self.mark_failed(task, "NO_QUESTIONS")
                        continue

                    from generators import ShortsGenerator
                    mode = 'truefalse' if task_type == 'truefalse' else 'standard'
                    generator = ShortsGenerator(mode=mode)

                    filename = f"{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                    generator.generate(questions, filename, enable_tts=True)

                    output_path = os.path.join(OUTPUT_DIR, filename)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        title = TitleGenerator.generate_shorts_title(5, category=category)
                        desc = TitleGenerator.generate_description(5, is_shorts=True, category=category)

                        video_id, error = upload_with_retry(output_path, title, desc, is_short=True)
                        os.remove(output_path)

                        if video_id:
                            mark_used(ids)
                            self.mark_complete(task, video_id)
                            log(f"✓ {task_type}: https://youtube.com/watch?v={video_id}")
                        elif error == "LIMIT_REACHED":
                            log("YouTube limit reached!")
                            return
                        else:
                            self.mark_failed(task, error)
                    else:
                        self.mark_failed(task, "GEN_FAILED")

                elif task_type == 'longform':
                    category = long_categories[cat_idx % len(long_categories)]
                    cat_idx += 1

                    if category:
                        questions, ids = topic_cats.get_questions_by_category(category, 50, for_shorts=False)
                        if len(questions) < 50:
                            questions, ids = get_questions(50, for_shorts=False)
                            category = None
                    else:
                        questions, ids = get_questions(50, for_shorts=False)

                    if len(questions) < 50:
                        self.mark_failed(task, "NO_QUESTIONS")
                        continue

                    from generators import GeneralKnowledgeGenerator
                    generator = GeneralKnowledgeGenerator(width=1920, height=1080, question_time=10, answer_time=5)

                    filename = f"longform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                    generator.generate(questions, filename, enable_tts=True)

                    output_path = os.path.join(OUTPUT_DIR, filename)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        title = TitleGenerator.generate_longform_title(50, category=category)
                        desc = TitleGenerator.generate_description(50, is_shorts=False, category=category)

                        video_id, error = upload_with_retry(output_path, title, desc, is_short=False)
                        os.remove(output_path)

                        if video_id:
                            mark_used(ids)
                            self.mark_complete(task, video_id)
                            log(f"✓ longform: https://youtube.com/watch?v={video_id}")
                        elif error == "LIMIT_REACHED":
                            log("YouTube limit reached!")
                            return
                        else:
                            self.mark_failed(task, error)
                    else:
                        self.mark_failed(task, "GEN_FAILED")

                time.sleep(3)

            except Exception as e:
                self.mark_failed(task, str(e))
                log(f"✗ Task error: {e}")

        stats = self.get_stats()
        log(f"Queue complete: {stats['completed']} completed, {stats['failed']} failed")
        return stats


def generate_batch_videos(video_type='short', count=5, parallel=2):
    """
    Generate multiple videos in parallel for faster throughput.

    Args:
        video_type: 'short' or 'longform'
        count: Number of videos to generate
        parallel: Number of parallel workers

    Returns:
        List of generated video paths
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from sound_effects import TopicCategories

    os.chdir(VIDEO_GEN_PATH)
    topic_cats = TopicCategories(DB_PATH)

    if video_type == 'short':
        categories = ['Science', 'History', 'Entertainment', 'Sports', 'Nature', 'Geography', None]
        q_count = 5
    else:
        categories = ['Science', 'History', 'Entertainment', 'Nature', None]
        q_count = 50

    log(f"Generating {count} {video_type} videos with {parallel} workers...")

    tasks = []
    for i in range(count):
        category = categories[i % len(categories)]
        if category:
            questions, ids = topic_cats.get_questions_by_category(
                category, q_count, for_shorts=(video_type == 'short')
            )
            if len(questions) < q_count:
                questions, ids = get_questions(q_count, for_shorts=(video_type == 'short'))
                category = None
        else:
            questions, ids = get_questions(q_count, for_shorts=(video_type == 'short'))

        if len(questions) < q_count:
            log(f"  Not enough questions for video {i+1}")
            continue

        filename = f"{video_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.mp4"
        tasks.append({
            'questions': questions,
            'ids': ids,
            'filename': filename,
            'category': category,
            'video_type': video_type
        })

    generated = []

    def generate_single(task):
        """Generate a single video (runs in subprocess)."""
        try:
            if task['video_type'] == 'short':
                from generators import ShortsGenerator
                generator = ShortsGenerator()
            else:
                from generators import GeneralKnowledgeGenerator
                generator = GeneralKnowledgeGenerator(
                    width=1920, height=1080,
                    question_time=10, answer_time=5
                )

            generator.generate(task['questions'], task['filename'], enable_tts=True)
            output_path = os.path.join(OUTPUT_DIR, task['filename'])

            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                return {
                    'success': True,
                    'path': output_path,
                    'ids': task['ids'],
                    'category': task['category']
                }
            return {'success': False, 'path': None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Use thread pool instead of process pool for simpler handling
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(generate_single, task): task for task in tasks}

        for future in as_completed(futures):
            result = future.result()
            if result.get('success'):
                generated.append(result)
                log(f"  Generated: {os.path.basename(result['path'])}")
            else:
                log(f"  Generation failed: {result.get('error', 'unknown')}")

    log(f"Batch complete: {len(generated)}/{len(tasks)} videos generated")
    return generated


def main():
    log("=" * 60)
    log("DAILY UPLOAD SCRIPT STARTED (Alternating Short/Longform)")
    log("=" * 60)

    send_discord_notification("🚀 **Daily upload started!**\nGenerating and uploading videos...", 0x00ff00)

    os.chdir(VIDEO_GEN_PATH)

    from sound_effects import TopicCategories
    topic_cats = TopicCategories(DB_PATH)

    short_categories = ['Science', 'History', 'Entertainment', 'Sports', 'Nature', 'Geography', None]
    long_categories = ['Science', 'History', 'Entertainment', 'Nature', None]

    short_cat_idx = 0
    long_cat_idx = 0

    shorts_uploaded = 0
    longform_uploaded = 0
    is_short_turn = True  # Start with a short

    while True:
        if is_short_turn:
            success, short_cat_idx, error = generate_one_short(topic_cats, short_categories, short_cat_idx)
            if success:
                shorts_uploaded += 1
            elif error == "LIMIT_REACHED":
                log(f"YouTube limit reached! Shorts: {shorts_uploaded}, Longform: {longform_uploaded}")
                break
            elif error == "NO_QUESTIONS":
                log("No more questions for shorts!")
                is_short_turn = False
                continue
        else:
            success, long_cat_idx, error = generate_one_longform(topic_cats, long_categories, long_cat_idx)
            if success:
                longform_uploaded += 1
            elif error == "LIMIT_REACHED":
                log(f"YouTube limit reached! Shorts: {shorts_uploaded}, Longform: {longform_uploaded}")
                break
            elif error == "NO_QUESTIONS":
                log("No more questions for longform!")
                is_short_turn = True
                continue

        # Alternate
        is_short_turn = not is_short_turn
        time.sleep(3)

    log("=" * 60)
    log(f"DAILY UPLOAD COMPLETE - {shorts_uploaded} shorts, {longform_uploaded} longform")
    log("=" * 60)

    # Send completion notification
    total = shorts_uploaded + longform_uploaded
    send_discord_notification(
        f"✅ **Daily upload complete!**\n\n"
        f"📹 **{total}** videos uploaded\n"
        f"• Shorts: {shorts_uploaded}\n"
        f"• Long-form: {longform_uploaded}\n\n"
        f"YouTube limit reached!",
        0x00ff00
    )

    # Send email summary
    send_email_alert(
        f"Daily Upload Complete - {total} videos",
        f"Daily upload has completed successfully!\n\n"
        f"Videos uploaded: {total}\n"
        f"  - Shorts: {shorts_uploaded}\n"
        f"  - Long-form: {longform_uploaded}\n\n"
        f"The YouTube upload limit has been reached for today."
    )

if __name__ == "__main__":
    main()
