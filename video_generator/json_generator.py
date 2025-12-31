#!/usr/bin/env python3
"""
JSON Generator App
Automatically generates JSON files for General Knowledge and Emoji Word quizzes.
No human intervention needed - just set the count and generate!
"""

import os
import sys
import json
import random
import string
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data import (
    QUESTIONS, get_random_questions, get_questions_count,
    EMOJI_PUZZLES, get_random_puzzles, get_all_categories, get_puzzles_count
)


class JSONGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON Generator - Auto Quiz Creator")
        self.root.geometry("700x600")
        self.root.minsize(600, 500)

        # Colors
        self.colors = {
            'bg': '#1e1e2e',
            'secondary': '#2a2a3e',
            'accent': '#7c3aed',
            'highlight': '#a855f7',
            'success': '#22c55e',
            'text': '#ffffff',
            'text_dim': '#a0a0b0'
        }

        self.setup_styles()
        self.root.configure(bg=self.colors['bg'])

        # Output directory
        self.output_dir = os.path.join(os.path.dirname(__file__), 'generated_json')
        os.makedirs(self.output_dir, exist_ok=True)

        self.create_widgets()

    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('.', background=self.colors['bg'],
                       foreground=self.colors['text'])
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'],
                       foreground=self.colors['text'], font=('Helvetica', 10))
        style.configure('TButton', background=self.colors['accent'],
                       foreground=self.colors['text'], font=('Helvetica', 11, 'bold'),
                       padding=12)
        style.map('TButton',
                 background=[('active', self.colors['highlight'])])

        style.configure('Header.TLabel', font=('Helvetica', 28, 'bold'),
                       foreground=self.colors['highlight'])
        style.configure('SubHeader.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Info.TLabel', foreground=self.colors['text_dim'],
                       font=('Helvetica', 9))

        style.configure('TLabelframe', background=self.colors['bg'])
        style.configure('TLabelframe.Label', background=self.colors['bg'],
                       foreground=self.colors['accent'], font=('Helvetica', 12, 'bold'))

        style.configure('TSpinbox', fieldbackground=self.colors['secondary'],
                       foreground=self.colors['text'])

        style.configure('Success.TLabel', foreground=self.colors['success'],
                       font=('Helvetica', 10, 'bold'))

    def create_widgets(self):
        """Create all widgets."""
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill='x', padx=30, pady=20)

        ttk.Label(header, text="JSON Generator",
                 style='Header.TLabel').pack(side='left')

        # Stats
        stats_frame = ttk.Frame(header)
        stats_frame.pack(side='right')
        ttk.Label(stats_frame, text=f"Questions: {get_questions_count()}",
                 style='Info.TLabel').pack()
        ttk.Label(stats_frame, text=f"Emoji Puzzles: {get_puzzles_count()}",
                 style='Info.TLabel').pack()

        # Main content
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=30, pady=10)

        # General Knowledge Section
        gk_frame = ttk.LabelFrame(main, text="  General Knowledge Quiz  ")
        gk_frame.pack(fill='x', pady=10, ipady=10)

        gk_content = ttk.Frame(gk_frame)
        gk_content.pack(fill='x', padx=20, pady=10)

        # Row 1: Number of files
        row1 = ttk.Frame(gk_content)
        row1.pack(fill='x', pady=5)

        ttk.Label(row1, text="Number of JSON files:").pack(side='left')
        self.gk_files = tk.IntVar(value=1)
        ttk.Spinbox(row1, from_=1, to=100, textvariable=self.gk_files,
                   width=10).pack(side='left', padx=10)

        # Row 2: Questions per file
        row2 = ttk.Frame(gk_content)
        row2.pack(fill='x', pady=5)

        ttk.Label(row2, text="Questions per file:").pack(side='left')
        self.gk_questions = tk.IntVar(value=10)
        ttk.Spinbox(row2, from_=5, to=50, textvariable=self.gk_questions,
                   width=10).pack(side='left', padx=10)

        max_q = get_questions_count()
        ttk.Label(row2, text=f"(max {max_q} unique)",
                 style='Info.TLabel').pack(side='left')

        # Generate button
        btn_frame = ttk.Frame(gk_content)
        btn_frame.pack(fill='x', pady=15)

        ttk.Button(btn_frame, text="Generate GK Files",
                  command=self.generate_gk).pack(side='left')

        self.gk_status = ttk.Label(btn_frame, text="", style='Success.TLabel')
        self.gk_status.pack(side='left', padx=20)

        # Emoji Word Section
        emoji_frame = ttk.LabelFrame(main, text="  Guess the Word by Emoji  ")
        emoji_frame.pack(fill='x', pady=10, ipady=10)

        emoji_content = ttk.Frame(emoji_frame)
        emoji_content.pack(fill='x', padx=20, pady=10)

        # Row 1: Number of files
        row1e = ttk.Frame(emoji_content)
        row1e.pack(fill='x', pady=5)

        ttk.Label(row1e, text="Number of JSON files:").pack(side='left')
        self.emoji_files = tk.IntVar(value=1)
        ttk.Spinbox(row1e, from_=1, to=100, textvariable=self.emoji_files,
                   width=10).pack(side='left', padx=10)

        # Row 2: Puzzles per file
        row2e = ttk.Frame(emoji_content)
        row2e.pack(fill='x', pady=5)

        ttk.Label(row2e, text="Puzzles per file:").pack(side='left')
        self.emoji_puzzles = tk.IntVar(value=10)
        ttk.Spinbox(row2e, from_=5, to=50, textvariable=self.emoji_puzzles,
                   width=10).pack(side='left', padx=10)

        max_e = get_puzzles_count()
        ttk.Label(row2e, text=f"(max {max_e} unique)",
                 style='Info.TLabel').pack(side='left')

        # Generate button
        btn_frame_e = ttk.Frame(emoji_content)
        btn_frame_e.pack(fill='x', pady=15)

        ttk.Button(btn_frame_e, text="Generate Emoji Files",
                  command=self.generate_emoji).pack(side='left')

        self.emoji_status = ttk.Label(btn_frame_e, text="", style='Success.TLabel')
        self.emoji_status.pack(side='left', padx=20)

        # Quick Generate Both Section
        quick_frame = ttk.LabelFrame(main, text="  Quick Generate Both  ")
        quick_frame.pack(fill='x', pady=10, ipady=10)

        quick_content = ttk.Frame(quick_frame)
        quick_content.pack(fill='x', padx=20, pady=10)

        ttk.Label(quick_content,
                 text="Generate both GK and Emoji files with current settings:",
                 style='Info.TLabel').pack(anchor='w')

        ttk.Button(quick_content, text="Generate All",
                  command=self.generate_all).pack(pady=15)

        # Output directory
        output_frame = ttk.Frame(main)
        output_frame.pack(fill='x', pady=20)

        ttk.Label(output_frame, text="Output Directory:",
                 style='Info.TLabel').pack(anchor='w')

        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill='x', pady=5)

        self.output_var = tk.StringVar(value=self.output_dir)
        output_entry = ttk.Entry(dir_frame, textvariable=self.output_var, width=50)
        output_entry.pack(side='left', fill='x', expand=True)

        ttk.Button(dir_frame, text="Browse",
                  command=self.browse_output).pack(side='left', padx=5)
        ttk.Button(dir_frame, text="Open Folder",
                  command=self.open_folder).pack(side='left')

    def browse_output(self):
        """Browse for output directory."""
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.output_var.set(path)

    def open_folder(self):
        """Open output folder in file manager."""
        os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == 'darwin':
            os.system(f'open "{self.output_dir}"')
        elif sys.platform == 'win32':
            os.startfile(self.output_dir)
        else:
            os.system(f'xdg-open "{self.output_dir}"')

    def generate_unique_filename(self, prefix, extension=".json"):
        """Generate a unique filename that never overwrites existing files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        filename = f"{prefix}_{timestamp}_{unique_id}{extension}"
        filepath = os.path.join(self.output_dir, filename)

        # Extra safety: if file somehow exists, regenerate
        while os.path.exists(filepath):
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{prefix}_{timestamp}_{unique_id}{extension}"
            filepath = os.path.join(self.output_dir, filename)

        return filename, filepath

    def generate_gk(self):
        """Generate General Knowledge JSON files."""
        num_files = self.gk_files.get()
        questions_per_file = self.gk_questions.get()

        self.output_dir = self.output_var.get()
        os.makedirs(self.output_dir, exist_ok=True)

        # Get all questions and shuffle
        all_questions = QUESTIONS.copy()
        random.shuffle(all_questions)

        generated = 0

        for i in range(num_files):
            # Get questions for this file
            start_idx = (i * questions_per_file) % len(all_questions)
            file_questions = []

            for j in range(questions_per_file):
                idx = (start_idx + j) % len(all_questions)
                file_questions.append(all_questions[idx])

            # Shuffle within file
            random.shuffle(file_questions)

            # Save file - ALWAYS create new unique file
            filename, filepath = self.generate_unique_filename("gk_quiz")

            with open(filepath, 'x', encoding='utf-8') as f:  # 'x' = create new only
                json.dump(file_questions, f, indent=2, ensure_ascii=False)

            generated += 1

        self.gk_status.config(text=f"Generated {generated} files!")
        messagebox.showinfo("Success",
                           f"Generated {generated} General Knowledge JSON files!\n\n"
                           f"Location: {self.output_dir}")

    def generate_emoji(self):
        """Generate Emoji Word JSON files."""
        num_files = self.emoji_files.get()
        puzzles_per_file = self.emoji_puzzles.get()

        self.output_dir = self.output_var.get()
        os.makedirs(self.output_dir, exist_ok=True)

        # Get all puzzles and shuffle
        all_puzzles = EMOJI_PUZZLES.copy()
        random.shuffle(all_puzzles)

        generated = 0

        for i in range(num_files):
            # Get puzzles for this file
            start_idx = (i * puzzles_per_file) % len(all_puzzles)
            file_puzzles = []

            for j in range(puzzles_per_file):
                idx = (start_idx + j) % len(all_puzzles)
                file_puzzles.append(all_puzzles[idx])

            # Shuffle within file
            random.shuffle(file_puzzles)

            # Save file - ALWAYS create new unique file
            filename, filepath = self.generate_unique_filename("emoji_quiz")

            with open(filepath, 'x', encoding='utf-8') as f:  # 'x' = create new only
                json.dump(file_puzzles, f, indent=2, ensure_ascii=False)

            generated += 1

        self.emoji_status.config(text=f"Generated {generated} files!")
        messagebox.showinfo("Success",
                           f"Generated {generated} Emoji Word JSON files!\n\n"
                           f"Location: {self.output_dir}")

    def generate_all(self):
        """Generate both GK and Emoji files."""
        self.generate_gk()
        self.generate_emoji()


def main():
    root = tk.Tk()
    app = JSONGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
