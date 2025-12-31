#!/usr/bin/env python3
"""
Automated Video Generation Pipeline

Generates quiz videos using AI continuously.
"""

import os
import sys
import json
import time
import pickle
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generators import GeneralKnowledgeGenerator, EmojiWordGenerator


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # AI Generation settings
    'ollama_host': 'http://localhost:11434',
    'ollama_model': 'mistral',  # Will auto-detect available models
    'questions_per_video': 10,
    'difficulty': 'medium',

    # Quiz types to rotate through
    'quiz_types': ['gk'],  # 'gk' = General Knowledge, 'emoji' = Emoji Word

    # Topics to rotate through (empty = random)
    'topics': [
        'Science', 'History', 'Geography', 'Movies', 'Music',
        'Sports', 'Literature', 'Technology', 'Nature', 'Food'
    ],

    # File management
    'output_dir': 'generated_videos',

    # Paths
    'state_file': 'automation_state.pkl',
    'log_file': 'automation.log',
}


# ============================================================================
# LOGGING
# ============================================================================

def log(message, level='INFO'):
    """Log message to console and file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)

    try:
        with open(CONFIG['log_file'], 'a') as f:
            f.write(log_line + '\n')
    except:
        pass


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class PipelineState:
    """Persistent state for crash recovery."""

    def __init__(self):
        self.total_generated = 0
        self.current_topic_index = 0

    def save(self):
        """Save state to file."""
        try:
            with open(CONFIG['state_file'], 'wb') as f:
                pickle.dump(self, f)
        except Exception as e:
            log(f"Failed to save state: {e}", 'ERROR')

    @staticmethod
    def load():
        """Load state from file."""
        try:
            if os.path.exists(CONFIG['state_file']):
                with open(CONFIG['state_file'], 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            log(f"Failed to load state: {e}", 'WARNING')
        return PipelineState()


# ============================================================================
# OLLAMA CLIENT
# ============================================================================

class OllamaClient:
    """Client for local Ollama API."""

    def __init__(self, host=None):
        self.host = host or CONFIG['ollama_host']
        self.api_url = f"{self.host}/api/generate"
        self.models_url = f"{self.host}/api/tags"

    def is_running(self):
        """Check if Ollama is running."""
        try:
            req = urllib.request.Request(self.models_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except:
            return False

    def get_models(self):
        """Get available models."""
        try:
            req = urllib.request.Request(self.models_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return [m['name'] for m in data.get('models', [])]
        except:
            return []

    def generate(self, model, prompt):
        """Generate text."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 32768,
                "num_ctx": 8192
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            self.api_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read().decode())
            return result.get('response', '')


# ============================================================================
# AI QUIZ GENERATOR
# ============================================================================

class QuizGenerator:
    """Generate quiz questions using AI."""

    def __init__(self):
        self.ollama = OllamaClient()
        self.model = None

    def initialize(self):
        """Initialize and find available model."""
        if not self.ollama.is_running():
            raise RuntimeError("Ollama is not running! Start with: ollama serve")

        models = self.ollama.get_models()
        if not models:
            raise RuntimeError("No Ollama models found! Install with: ollama pull mistral")

        # Prefer configured model, fall back to first available
        if CONFIG['ollama_model'] in models:
            self.model = CONFIG['ollama_model']
        else:
            self.model = models[0]

        log(f"Using Ollama model: {self.model}")
        return True

    def _get_gk_prompt(self, count, topic, difficulty):
        """Prompt for general knowledge questions."""
        topic_str = f" about {topic}" if topic else ""
        return f"""Generate exactly {count} unique multiple-choice general knowledge questions{topic_str}.
Difficulty level: {difficulty}

IMPORTANT: Return ONLY a valid JSON array, no other text. Each question must have exactly this format:
[
  {{
    "question": "What is the capital of France?",
    "options": ["London", "Berlin", "Paris", "Madrid"],
    "answer": 2
  }}
]

Rules:
- "answer" is the INDEX (0-3) of the correct option
- Make questions varied and interesting
- Ensure only ONE answer is correct
- All 4 options should be plausible
- No duplicate questions

Generate {count} questions now as a JSON array:"""

    def _get_emoji_prompt(self, count, topic, difficulty):
        """Prompt for emoji puzzles."""
        topic_str = f" related to {topic}" if topic else ""
        return f"""Generate exactly {count} REBUS emoji puzzles{topic_str}.
Difficulty level: {difficulty}

EXAMPLES:
- RAINBOW = 🌧️ + 🎀
- BUTTERFLY = 🧈 + 🪰
- STARFISH = ⭐ + 🐟

Return ONLY a valid JSON array:
[
  {{
    "emojis": "🌧️ + 🎀",
    "answer": "Rainbow",
    "hint": "Colorful arc in the sky",
    "category": "Nature"
  }}
]

Generate {count} puzzles:"""

    def _parse_json(self, response):
        """Extract JSON from response."""
        import re
        response = response.strip()

        # Try direct parse
        try:
            return json.loads(response)
        except:
            pass

        # Find JSON array
        patterns = [r'\[[\s\S]*\]', r'```json\s*([\s\S]*?)```', r'```\s*([\s\S]*?)```']
        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except:
                    continue

        raise ValueError("Could not parse JSON")

    def generate_quiz(self, quiz_type='gk', topic=None, count=None, difficulty=None):
        """Generate a quiz."""
        if not self.model:
            self.initialize()

        count = count or CONFIG['questions_per_video']
        difficulty = difficulty or CONFIG['difficulty']

        log(f"Generating {quiz_type.upper()} quiz: {count} questions, topic={topic or 'random'}")

        # Batch generation for reliability
        BATCH_SIZE = 15
        all_questions = []
        remaining = count
        batch_num = 0

        while remaining > 0:
            batch_count = min(BATCH_SIZE, remaining)
            batch_num += 1

            if quiz_type == 'gk':
                prompt = self._get_gk_prompt(batch_count, topic, difficulty)
            else:
                prompt = self._get_emoji_prompt(batch_count, topic, difficulty)

            # Retry logic
            for attempt in range(3):
                try:
                    response = self.ollama.generate(self.model, prompt)
                    questions = self._parse_json(response)

                    if isinstance(questions, list) and len(questions) > 0:
                        all_questions.extend(questions)
                        log(f"  Batch {batch_num}: got {len(questions)} items")
                        break
                except Exception as e:
                    if attempt < 2:
                        log(f"  Batch {batch_num} retry {attempt+1}: {str(e)[:50]}", 'WARNING')
                        time.sleep(2)
                    else:
                        log(f"  Batch {batch_num} failed: {str(e)[:50]}", 'ERROR')

            remaining -= batch_count

        # Validate answers
        for q in all_questions:
            if 'answer' in q and 'options' in q:
                if not isinstance(q['answer'], int) or q['answer'] < 0 or q['answer'] >= len(q['options']):
                    q['answer'] = 0

        log(f"Generated {len(all_questions)} questions total")
        return all_questions


# ============================================================================
# VIDEO GENERATOR
# ============================================================================

class VideoMaker:
    """Generate videos from quiz data."""

    def __init__(self):
        self.output_dir = CONFIG['output_dir']
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_video(self, questions, quiz_type='gk', topic=None):
        """Generate a video from questions."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        topic_slug = (topic or 'general').lower().replace(' ', '_')[:20]

        filename = f"{quiz_type}_{topic_slug}_{timestamp}.mp4"

        log(f"Generating video: {filename}")

        try:
            if quiz_type == 'gk':
                generator = GeneralKnowledgeGenerator()
                generator.question_time = 5
                generator.answer_time = 3
                output_path = generator.generate(questions, filename)
            else:
                generator = EmojiWordGenerator()
                output_path = generator.generate(questions, filename)

            # Move to output directory
            final_path = os.path.join(self.output_dir, filename)
            if output_path != final_path:
                os.rename(output_path, final_path)

            log(f"Video saved: {final_path}")
            return final_path

        except Exception as e:
            log(f"Video generation failed: {e}", 'ERROR')
            import traceback
            traceback.print_exc()
            return None


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class AutomationPipeline:
    """Main automation pipeline."""

    def __init__(self):
        self.state = PipelineState.load()
        self.quiz_gen = QuizGenerator()
        self.video_maker = VideoMaker()
        self.running = False

    def get_next_topic(self):
        """Get next topic from rotation."""
        topics = CONFIG['topics']
        if not topics:
            return None

        topic = topics[self.state.current_topic_index % len(topics)]
        self.state.current_topic_index += 1
        self.state.save()
        return topic

    def get_next_quiz_type(self):
        """Get next quiz type from rotation."""
        types = CONFIG['quiz_types']
        return types[self.state.total_generated % len(types)]

    def generate_one(self):
        """Generate one video."""
        topic = self.get_next_topic()
        quiz_type = self.get_next_quiz_type()

        # Generate questions
        questions = self.quiz_gen.generate_quiz(
            quiz_type=quiz_type,
            topic=topic,
            count=CONFIG['questions_per_video'],
            difficulty=CONFIG['difficulty']
        )

        if not questions:
            log("Failed to generate questions", 'ERROR')
            return None

        # Generate video
        video_path = self.video_maker.generate_video(questions, quiz_type, topic)

        if video_path:
            self.state.total_generated += 1
            self.state.save()

        return video_path

    def run_forever(self):
        """Run the pipeline continuously."""
        log("=" * 60)
        log("AUTOMATION PIPELINE STARTED")
        log(f"Topics: {', '.join(CONFIG['topics'])}")
        log(f"State: {self.state.total_generated} videos generated")
        log("=" * 60)

        self.running = True

        # Initialize
        try:
            self.quiz_gen.initialize()
        except Exception as e:
            log(f"Failed to initialize: {e}", 'ERROR')
            return

        while self.running:
            try:
                log(f"\n--- Generating video #{self.state.total_generated + 1} ---")
                self.generate_one()

                # Small delay between cycles
                time.sleep(5)

            except KeyboardInterrupt:
                log("\nStopping pipeline (Ctrl+C)...")
                self.running = False
            except Exception as e:
                log(f"Pipeline error: {e}", 'ERROR')
                time.sleep(30)

        self.state.save()
        log("Pipeline stopped. State saved.")

    def run_generate(self, count=10):
        """Generate a specific number of videos."""
        log(f"Generating {count} videos...")

        self.quiz_gen.initialize()

        for i in range(count):
            log(f"\n--- Generating video {i+1}/{count} ---")
            self.generate_one()

        log(f"\nDone! Generated {count} videos.")

    def status(self):
        """Print current status."""
        print("\n" + "=" * 50)
        print("AUTOMATION PIPELINE STATUS")
        print("=" * 50)
        print(f"Total videos generated: {self.state.total_generated}")
        print(f"Output directory: {CONFIG['output_dir']}")
        print("=" * 50)


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Automated Quiz Video Pipeline')
    parser.add_argument('command', choices=['run', 'generate', 'status'],
                       help='Command to run')
    parser.add_argument('-n', '--count', type=int, default=10,
                       help='Number of videos to generate (for generate command)')

    args = parser.parse_args()

    pipeline = AutomationPipeline()

    if args.command == 'run':
        pipeline.run_forever()
    elif args.command == 'generate':
        pipeline.run_generate(args.count)
    elif args.command == 'status':
        pipeline.status()


if __name__ == '__main__':
    main()
