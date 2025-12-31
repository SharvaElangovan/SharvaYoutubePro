#!/usr/bin/env python3
"""
AI-Powered JSON Generator
Uses a local AI model (Ollama) to generate unique quiz questions and emoji puzzles.

Requirements:
- Install Ollama: https://ollama.ai
- Pull a model: ollama pull llama3.2 (or mistral, gemma2, etc.)
"""

import os
import sys
import json
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
import urllib.request
import urllib.error
import uuid
import random
import string


class OllamaClient:
    """Client for interacting with local Ollama API."""

    def __init__(self, host="http://localhost:11434"):
        self.host = host
        self.api_url = f"{host}/api/generate"
        self.models_url = f"{host}/api/tags"

    def is_running(self):
        """Check if Ollama is running."""
        try:
            req = urllib.request.Request(self.models_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except:
            return False

    def get_models(self):
        """Get list of available models."""
        try:
            req = urllib.request.Request(self.models_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return [model['name'] for model in data.get('models', [])]
        except:
            return []

    def generate(self, model, prompt, callback=None):
        """Generate text using the model."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 32768,  # Increased token limit
                "num_ctx": 8192  # Context window
            }
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.api_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=600) as response:  # 10 min for up to 100 questions
                result = json.loads(response.read().decode())
                return result.get('response', '')
        except urllib.error.URLError as e:
            raise Exception(f"Connection error: {e}")
        except Exception as e:
            raise Exception(f"Generation error: {e}")


class AIJSONGenerator:
    """Main application class."""

    def __init__(self, root):
        self.root = root
        self.root.title("AI Quiz Generator - Powered by Local LLM")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)

        # Colors
        self.colors = {
            'bg': '#0f0f1a',
            'secondary': '#1a1a2e',
            'accent': '#00d4ff',
            'success': '#00ff88',
            'warning': '#ffaa00',
            'error': '#ff4466',
            'text': '#ffffff',
            'text_dim': '#888899'
        }

        self.setup_styles()
        self.root.configure(bg=self.colors['bg'])

        # Ollama client
        self.ollama = OllamaClient()

        # Output directory
        self.output_dir = os.path.join(os.path.dirname(__file__), 'ai_generated')
        os.makedirs(self.output_dir, exist_ok=True)

        # State
        self.is_generating = False
        self.available_models = []

        self.create_widgets()
        self.check_ollama_status()

    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('.', background=self.colors['bg'],
                       foreground=self.colors['text'])
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'],
                       foreground=self.colors['text'], font=('Helvetica', 10))
        style.configure('TButton', background=self.colors['secondary'],
                       foreground=self.colors['text'], font=('Helvetica', 11, 'bold'),
                       padding=12)
        style.map('TButton',
                 background=[('active', self.colors['accent']),
                            ('disabled', '#333344')])

        style.configure('Header.TLabel', font=('Helvetica', 26, 'bold'),
                       foreground=self.colors['accent'])
        style.configure('SubHeader.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('Info.TLabel', foreground=self.colors['text_dim'],
                       font=('Helvetica', 9))
        style.configure('Status.TLabel', font=('Helvetica', 10, 'bold'))

        style.configure('TLabelframe', background=self.colors['bg'])
        style.configure('TLabelframe.Label', background=self.colors['bg'],
                       foreground=self.colors['accent'], font=('Helvetica', 12, 'bold'))

        style.configure('TCombobox', fieldbackground=self.colors['secondary'],
                       foreground=self.colors['text'])
        style.configure('TSpinbox', fieldbackground=self.colors['secondary'],
                       foreground=self.colors['text'])

        style.configure('Horizontal.TProgressbar',
                       background=self.colors['accent'],
                       troughcolor=self.colors['secondary'])

    def create_widgets(self):
        """Create all widgets."""
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=30, pady=15)

        ttk.Label(header, text="AI Quiz Generator",
                 style='Header.TLabel').pack(side='left')

        # Status indicator
        self.status_frame = ttk.Frame(header)
        self.status_frame.pack(side='right')

        self.status_dot = tk.Canvas(self.status_frame, width=12, height=12,
                                    bg=self.colors['bg'], highlightthickness=0)
        self.status_dot.pack(side='left', padx=5)

        self.status_label = ttk.Label(self.status_frame, text="Checking Ollama...",
                                      style='Status.TLabel')
        self.status_label.pack(side='left')

        # Main content
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=30, pady=10)

        # Model Selection
        model_frame = ttk.LabelFrame(main, text="  AI Model  ")
        model_frame.pack(fill='x', pady=10, ipady=5)

        model_content = ttk.Frame(model_frame)
        model_content.pack(fill='x', padx=20, pady=10)

        ttk.Label(model_content, text="Select Model:").pack(side='left')

        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(model_content, textvariable=self.model_var,
                                        state='readonly', width=30)
        self.model_combo.pack(side='left', padx=10)

        ttk.Button(model_content, text="Refresh",
                  command=self.refresh_models).pack(side='left')

        ttk.Label(model_content,
                 text="(Install: ollama pull llama3.2)",
                 style='Info.TLabel').pack(side='left', padx=20)

        # Generation Type
        type_frame = ttk.LabelFrame(main, text="  Quiz Type  ")
        type_frame.pack(fill='x', pady=10, ipady=5)

        type_content = ttk.Frame(type_frame)
        type_content.pack(fill='x', padx=20, pady=10)

        self.quiz_type = tk.StringVar(value='gk')

        ttk.Radiobutton(type_content, text="General Knowledge Quiz",
                       variable=self.quiz_type, value='gk').pack(side='left', padx=10)
        ttk.Radiobutton(type_content, text="Emoji Word Puzzle",
                       variable=self.quiz_type, value='emoji').pack(side='left', padx=10)
        ttk.Radiobutton(type_content, text="Both",
                       variable=self.quiz_type, value='both').pack(side='left', padx=10)

        # Settings
        settings_frame = ttk.LabelFrame(main, text="  Generation Settings  ")
        settings_frame.pack(fill='x', pady=10, ipady=5)

        settings_content = ttk.Frame(settings_frame)
        settings_content.pack(fill='x', padx=20, pady=10)

        # Row 1
        row1 = ttk.Frame(settings_content)
        row1.pack(fill='x', pady=5)

        ttk.Label(row1, text="Number of files:").pack(side='left')
        self.num_files = tk.IntVar(value=1)
        ttk.Spinbox(row1, from_=1, to=20, textvariable=self.num_files,
                   width=8).pack(side='left', padx=10)

        ttk.Label(row1, text="Items per file:").pack(side='left', padx=(30, 0))
        self.items_per_file = tk.IntVar(value=10)
        ttk.Spinbox(row1, from_=3, to=100, textvariable=self.items_per_file,
                   width=8).pack(side='left', padx=10)

        # Row 2 - Category/Topic
        row2 = ttk.Frame(settings_content)
        row2.pack(fill='x', pady=5)

        ttk.Label(row2, text="Topic/Category (optional):").pack(side='left')
        self.topic_var = tk.StringVar()
        topic_entry = ttk.Entry(row2, textvariable=self.topic_var, width=40)
        topic_entry.pack(side='left', padx=10)

        ttk.Label(row2, text="e.g., Science, Movies, Sports",
                 style='Info.TLabel').pack(side='left')

        # Difficulty
        row3 = ttk.Frame(settings_content)
        row3.pack(fill='x', pady=5)

        ttk.Label(row3, text="Difficulty:").pack(side='left')
        self.difficulty = tk.StringVar(value='medium')
        ttk.Radiobutton(row3, text="Easy", variable=self.difficulty,
                       value='easy').pack(side='left', padx=10)
        ttk.Radiobutton(row3, text="Medium", variable=self.difficulty,
                       value='medium').pack(side='left', padx=10)
        ttk.Radiobutton(row3, text="Hard", variable=self.difficulty,
                       value='hard').pack(side='left', padx=10)

        # Generate Button
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=15)

        self.generate_btn = ttk.Button(btn_frame, text="Generate with AI",
                                       command=self.start_generation)
        self.generate_btn.pack(side='left')

        self.progress = ttk.Progressbar(btn_frame, mode='indeterminate', length=200)
        self.progress.pack(side='left', padx=20)

        # Log output
        log_frame = ttk.LabelFrame(main, text="  Generation Log  ")
        log_frame.pack(fill='both', expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, bg=self.colors['secondary'],
            fg=self.colors['text'], font=('Consolas', 9),
            insertbackground=self.colors['text']
        )
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Output directory
        output_frame = ttk.Frame(main)
        output_frame.pack(fill='x', pady=10)

        ttk.Label(output_frame, text="Output:", style='Info.TLabel').pack(side='left')

        self.output_var = tk.StringVar(value=self.output_dir)
        ttk.Entry(output_frame, textvariable=self.output_var, width=45).pack(side='left', padx=5)

        ttk.Button(output_frame, text="Browse",
                  command=self.browse_output).pack(side='left')
        ttk.Button(output_frame, text="Open",
                  command=self.open_folder).pack(side='left', padx=5)

    def log(self, message, level='info'):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {'info': 'ℹ', 'success': '✓', 'error': '✗', 'warning': '⚠'}
        self.log_text.insert(tk.END, f"[{timestamp}] {prefix.get(level, '•')} {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def check_ollama_status(self):
        """Check if Ollama is running and update status."""
        def check():
            if self.ollama.is_running():
                self.root.after(0, lambda: self.update_status(True))
                models = self.ollama.get_models()
                self.root.after(0, lambda: self.update_models(models))
            else:
                self.root.after(0, lambda: self.update_status(False))

        threading.Thread(target=check, daemon=True).start()

    def update_status(self, is_running):
        """Update status indicator."""
        self.status_dot.delete('all')
        if is_running:
            self.status_dot.create_oval(2, 2, 10, 10, fill=self.colors['success'], outline='')
            self.status_label.config(text="Ollama Running")
        else:
            self.status_dot.create_oval(2, 2, 10, 10, fill=self.colors['error'], outline='')
            self.status_label.config(text="Ollama Not Found")
            self.log("Ollama not running! Start it with: ollama serve", 'error')

    def update_models(self, models):
        """Update model dropdown."""
        self.available_models = models
        self.model_combo['values'] = models
        if models:
            self.model_combo.current(0)
            self.log(f"Found {len(models)} models: {', '.join(models)}", 'success')
        else:
            self.log("No models found. Install one with: ollama pull llama3.2", 'warning')

    def refresh_models(self):
        """Refresh available models."""
        self.log("Refreshing models...")
        self.check_ollama_status()

    def browse_output(self):
        """Browse for output directory."""
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.output_var.set(path)

    def open_folder(self):
        """Open output folder."""
        os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == 'darwin':
            os.system(f'open "{self.output_dir}"')
        elif sys.platform == 'win32':
            os.startfile(self.output_dir)
        else:
            os.system(f'xdg-open "{self.output_dir}"')

    def get_gk_prompt(self, count, topic, difficulty):
        """Get prompt for generating GK questions."""
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

    def get_emoji_prompt(self, count, topic, difficulty):
        """Get prompt for generating emoji puzzles (rebus style)."""
        topic_str = f" related to {topic}" if topic else ""
        return f"""Generate exactly {count} REBUS emoji puzzles{topic_str}.
Difficulty level: {difficulty}

HOW IT WORKS:
1. Pick a simple compound word (like rainbow, snowman, butterfly)
2. Split it into two simple words
3. Find emojis that represent each word

EXAMPLES:
- RAINBOW = 🌧️ (rain) + 🎀 (bow)
- BUTTERFLY = 🧈 (butter) + 🪰 (fly)
- SNOWMAN = ❄️ (snow) + 👨 (man)
- STARFISH = ⭐ (star) + 🐟 (fish)
- FOOTBALL = 🦶 (foot) + ⚽ (ball)
- HOTDOG = 🔥 (hot) + 🐕 (dog)
- SUNFLOWER = ☀️ (sun) + 🌻 (flower)
- PINEAPPLE = 🌲 (pine) + 🍎 (apple)
- WATERMELON = 💧 (water) + 🍈 (melon)
- HONEYBEE = 🍯 (honey) + 🐝 (bee)

DO NOT use complex words - only use simple compound words that can be split into two emoji-friendly parts!

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

    def parse_json_response(self, response):
        """Extract JSON from AI response."""
        # Try to find JSON array in response
        response = response.strip()

        # Try direct parse first
        try:
            return json.loads(response)
        except:
            pass

        # Try to find JSON array pattern
        patterns = [
            r'\[[\s\S]*\]',  # Match array
            r'```json\s*([\s\S]*?)```',  # Match code block
            r'```\s*([\s\S]*?)```',  # Match any code block
        ]

        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except:
                    continue

        raise ValueError("Could not parse JSON from response")

    def generate_file(self, quiz_type, file_num, total_files):
        """Generate a single file with auto-batching for large requests."""
        model = self.model_var.get()
        count = self.items_per_file.get()
        topic = self.topic_var.get().strip()
        difficulty = self.difficulty.get()

        type_name = "GK" if quiz_type == 'gk' else "Emoji"
        self.log(f"Generating {type_name} file {file_num}/{total_files}...")

        # Auto-batch for large requests (smaller batches = more reliable)
        BATCH_SIZE = 15  # Smaller batches are more reliable
        all_data = []

        if count <= BATCH_SIZE:
            batches = [(count, 1, 1)]
        else:
            num_batches = (count + BATCH_SIZE - 1) // BATCH_SIZE
            batches = []
            remaining = count
            for b in range(num_batches):
                batch_count = min(BATCH_SIZE, remaining)
                batches.append((batch_count, b + 1, num_batches))
                remaining -= batch_count

        # Generate with AI (in batches if needed)
        try:
            for batch_count, batch_num, num_batches in batches:
                if num_batches > 1:
                    self.log(f"  Batch {batch_num}/{num_batches} (requesting {batch_count} items)...")

                # Get appropriate prompt
                if quiz_type == 'gk':
                    prompt = self.get_gk_prompt(batch_count, topic, difficulty)
                else:
                    prompt = self.get_emoji_prompt(batch_count, topic, difficulty)

                # Retry logic for failed batches
                max_retries = 2
                batch_data = []

                for attempt in range(max_retries + 1):
                    try:
                        response = self.ollama.generate(model, prompt)
                        parsed = self.parse_json_response(response)

                        if isinstance(parsed, list) and len(parsed) > 0:
                            batch_data = parsed
                            break
                        else:
                            if attempt < max_retries:
                                self.log(f"    Retry {attempt + 1}: Empty response, retrying...", 'warning')
                    except Exception as e:
                        if attempt < max_retries:
                            self.log(f"    Retry {attempt + 1}: {str(e)[:50]}", 'warning')
                        else:
                            self.log(f"    Batch failed after retries: {str(e)[:50]}", 'error')

                if batch_data:
                    all_data.extend(batch_data)
                    self.log(f"    Got {len(batch_data)} items (total: {len(all_data)})")
                else:
                    self.log(f"    Batch {batch_num} failed - no valid data", 'error')

            data = all_data

            if not isinstance(data, list) or len(data) == 0:
                raise ValueError("Invalid response format")

            # Validate and fix answer indices
            for item in data:
                if 'answer' in item and 'options' in item:
                    options = item.get('options', [])
                    answer = item.get('answer', 0)
                    if not isinstance(answer, int) or answer < 0 or answer >= len(options):
                        item['answer'] = 0  # Default to first option if invalid

            # Save file - ALWAYS create new unique file, never overwrite
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds
            unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            filename = f"ai_{quiz_type}_{timestamp}_{unique_id}.json"
            filepath = os.path.join(self.output_dir, filename)

            # Extra safety: if file somehow exists, add UUID
            while os.path.exists(filepath):
                unique_id = uuid.uuid4().hex[:8]
                filename = f"ai_{quiz_type}_{timestamp}_{unique_id}.json"
                filepath = os.path.join(self.output_dir, filename)

            # Write to NEW file (never edit existing)
            with open(filepath, 'x', encoding='utf-8') as f:  # 'x' mode = create new only
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.log(f"Saved: {filename} ({len(data)} items)", 'success')
            return True

        except FileExistsError:
            # If somehow file exists, try again with new name
            self.log("File conflict, retrying with new name...", 'warning')
            return self.generate_file(quiz_type, file_num, total_files)

        except Exception as e:
            self.log(f"Error: {str(e)}", 'error')
            return False

    def start_generation(self):
        """Start the generation process."""
        if self.is_generating:
            return

        model = self.model_var.get()
        if not model:
            messagebox.showerror("Error", "Please select a model first!")
            return

        if not self.ollama.is_running():
            messagebox.showerror("Error", "Ollama is not running!\nStart it with: ollama serve")
            return

        self.is_generating = True
        self.generate_btn.config(state='disabled')
        self.progress.start(10)

        self.output_dir = self.output_var.get()
        os.makedirs(self.output_dir, exist_ok=True)

        def generate():
            num_files = self.num_files.get()
            quiz_type = self.quiz_type.get()
            success_count = 0

            self.log(f"Starting generation: {num_files} files, type: {quiz_type}")

            types_to_generate = []
            if quiz_type == 'gk':
                types_to_generate = ['gk']
            elif quiz_type == 'emoji':
                types_to_generate = ['emoji']
            else:
                types_to_generate = ['gk', 'emoji']

            for qtype in types_to_generate:
                for i in range(num_files):
                    if self.generate_file(qtype, i + 1, num_files):
                        success_count += 1

            self.root.after(0, lambda: self.generation_complete(success_count))

        threading.Thread(target=generate, daemon=True).start()

    def generation_complete(self, count):
        """Handle generation completion."""
        self.is_generating = False
        self.generate_btn.config(state='normal')
        self.progress.stop()

        self.log(f"Generation complete! {count} files created.", 'success')
        messagebox.showinfo("Complete",
                           f"Generated {count} JSON files!\n\nLocation: {self.output_dir}")


def main():
    root = tk.Tk()
    app = AIJSONGenerator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
