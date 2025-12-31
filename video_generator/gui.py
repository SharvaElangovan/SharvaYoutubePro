#!/usr/bin/env python3
"""
Video Generator GUI
A graphical interface for generating quiz videos.
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generators import (
    GeneralKnowledgeGenerator,
    SpotDifferenceGenerator,
    OddOneOutGenerator,
    EmojiWordGenerator
)
from generators.general_knowledge import SAMPLE_QUESTIONS
from generators.emoji_word import SAMPLE_EMOJI_PUZZLES


class VideoGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Generator - Quiz & Puzzle Videos")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Set theme colors
        self.colors = {
            'bg': '#1a1a2e',
            'secondary': '#16213e',
            'accent': '#0f3460',
            'highlight': '#e94560',
            'text': '#ffffff',
            'text_dim': '#a0a0a0'
        }

        # Configure style
        self.setup_styles()

        # Configure root
        self.root.configure(bg=self.colors['bg'])

        # Create main container
        self.create_widgets()

        # Status variable
        self.is_generating = False


    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure('.',
                       background=self.colors['bg'],
                       foreground=self.colors['text'],
                       fieldbackground=self.colors['secondary'])

        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'],
                       foreground=self.colors['text'], font=('Helvetica', 10))
        style.configure('TButton', background=self.colors['accent'],
                       foreground=self.colors['text'], font=('Helvetica', 10, 'bold'),
                       padding=10)
        style.map('TButton',
                 background=[('active', self.colors['highlight']),
                            ('pressed', self.colors['highlight'])])

        style.configure('Header.TLabel', font=('Helvetica', 24, 'bold'),
                       foreground=self.colors['highlight'])
        style.configure('SubHeader.TLabel', font=('Helvetica', 14, 'bold'),
                       foreground=self.colors['text'])

        style.configure('TNotebook', background=self.colors['bg'])
        style.configure('TNotebook.Tab', background=self.colors['secondary'],
                       foreground=self.colors['text'], padding=[20, 10],
                       font=('Helvetica', 10, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', self.colors['text'])])

        style.configure('TEntry', fieldbackground=self.colors['secondary'],
                       foreground=self.colors['text'], insertcolor=self.colors['text'])

        style.configure('TSpinbox', fieldbackground=self.colors['secondary'],
                       foreground=self.colors['text'])

        style.configure('Horizontal.TProgressbar',
                       background=self.colors['highlight'],
                       troughcolor=self.colors['secondary'])

    def create_widgets(self):
        """Create all GUI widgets."""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=20, pady=15)

        ttk.Label(header_frame, text="Video Generator",
                 style='Header.TLabel').pack(side='left')

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=10)

        # Create tabs
        self.create_gk_tab()
        self.create_spot_diff_tab()
        self.create_odd_one_out_tab()
        self.create_emoji_tab()
        self.create_automation_tab()

        # Status bar
        self.create_status_bar()

    def create_gk_tab(self):
        """Create General Knowledge tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  General Knowledge  ")

        # Main container with scrollbar
        canvas = tk.Canvas(tab, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Content
        content = ttk.Frame(scrollable_frame)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content, text="General Knowledge Quiz",
                 style='SubHeader.TLabel').pack(anchor='w')
        ttk.Label(content, text="Create multiple-choice quiz videos",
                 foreground=self.colors['text_dim']).pack(anchor='w', pady=(0, 20))

        # Source selection
        source_frame = ttk.Frame(content)
        source_frame.pack(fill='x', pady=10)

        ttk.Label(source_frame, text="Question Source:").pack(anchor='w')

        self.gk_source = tk.StringVar(value='sample')
        ttk.Radiobutton(source_frame, text="Use Sample Questions",
                       variable=self.gk_source, value='sample').pack(anchor='w')
        ttk.Radiobutton(source_frame, text="Load from JSON File",
                       variable=self.gk_source, value='file').pack(anchor='w')

        # File selection
        file_frame = ttk.Frame(content)
        file_frame.pack(fill='x', pady=10)

        self.gk_file_path = tk.StringVar()
        ttk.Label(file_frame, text="JSON File:").pack(anchor='w')
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill='x')

        self.gk_file_entry = ttk.Entry(file_entry_frame, textvariable=self.gk_file_path)
        self.gk_file_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(file_entry_frame, text="Browse",
                  command=lambda: self.browse_file(self.gk_file_path, [('JSON', '*.json')])).pack(side='left', padx=(5, 0))

        # Settings
        settings_frame = ttk.Frame(content)
        settings_frame.pack(fill='x', pady=20)

        ttk.Label(settings_frame, text="Settings", style='SubHeader.TLabel').pack(anchor='w')

        # Time settings
        time_frame = ttk.Frame(settings_frame)
        time_frame.pack(fill='x', pady=10)

        ttk.Label(time_frame, text="Question Time (seconds):").grid(row=0, column=0, sticky='w', pady=5)
        self.gk_question_time = tk.IntVar(value=5)
        ttk.Spinbox(time_frame, from_=3, to=30, textvariable=self.gk_question_time, width=10).grid(row=0, column=1, padx=10)

        ttk.Label(time_frame, text="Answer Display Time (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.gk_answer_time = tk.IntVar(value=3)
        ttk.Spinbox(time_frame, from_=1, to=10, textvariable=self.gk_answer_time, width=10).grid(row=1, column=1, padx=10)

        # Output filename
        output_frame = ttk.Frame(content)
        output_frame.pack(fill='x', pady=10)

        ttk.Label(output_frame, text="Output Filename:").pack(anchor='w')
        self.gk_output = tk.StringVar(value='general_knowledge.mp4')
        ttk.Entry(output_frame, textvariable=self.gk_output).pack(fill='x')

        # Generate button
        ttk.Button(content, text="Generate Video",
                  command=self.generate_gk).pack(pady=20)

    def create_spot_diff_tab(self):
        """Create Spot the Difference tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Spot the Difference  ")

        content = ttk.Frame(tab)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content, text="Spot the Difference",
                 style='SubHeader.TLabel').pack(anchor='w')
        ttk.Label(content, text="Use AI to generate illustrated cartoon images or fetch photos",
                 foreground=self.colors['text_dim']).pack(anchor='w', pady=(0, 20))

        # Image selection
        img_frame = ttk.Frame(content)
        img_frame.pack(fill='x', pady=10)

        ttk.Label(img_frame, text="Image Source:").pack(anchor='w')

        # AI, Auto, Single or batch
        self.spot_mode = tk.StringVar(value='ai')
        mode_frame = ttk.Frame(img_frame)
        mode_frame.pack(fill='x', pady=5)
        ttk.Radiobutton(mode_frame, text="AI Generated (Pollinations.ai)",
                       variable=self.spot_mode, value='ai').pack(side='left')
        ttk.Radiobutton(mode_frame, text="Auto (fetch photos)",
                       variable=self.spot_mode, value='auto').pack(side='left', padx=15)

        mode_frame2 = ttk.Frame(img_frame)
        mode_frame2.pack(fill='x', pady=2)
        ttk.Radiobutton(mode_frame2, text="Single Image",
                       variable=self.spot_mode, value='single').pack(side='left')
        ttk.Radiobutton(mode_frame2, text="Batch",
                       variable=self.spot_mode, value='batch').pack(side='left', padx=15)

        # Number of puzzles for auto/ai mode
        auto_frame = ttk.Frame(img_frame)
        auto_frame.pack(fill='x', pady=5)
        ttk.Label(auto_frame, text="Number of Puzzles:").pack(side='left')
        self.spot_num_puzzles = tk.IntVar(value=5)
        ttk.Spinbox(auto_frame, from_=1, to=20, textvariable=self.spot_num_puzzles, width=10).pack(side='left', padx=10)

        # Difficulty level
        diff_frame = ttk.Frame(img_frame)
        diff_frame.pack(fill='x', pady=5)
        ttk.Label(diff_frame, text="Difficulty:").pack(side='left')
        self.spot_difficulty = tk.StringVar(value='medium')
        ttk.Radiobutton(diff_frame, text="Easy", variable=self.spot_difficulty, value='easy').pack(side='left', padx=(10, 5))
        ttk.Radiobutton(diff_frame, text="Medium", variable=self.spot_difficulty, value='medium').pack(side='left', padx=5)
        ttk.Radiobutton(diff_frame, text="Hard", variable=self.spot_difficulty, value='hard').pack(side='left', padx=5)

        # AI status indicator
        self.ai_status_frame = ttk.Frame(img_frame)
        self.ai_status_frame.pack(fill='x', pady=5)
        self.ai_status_label = ttk.Label(self.ai_status_frame,
                                         text="AI Mode: Pollinations.ai (free, no setup needed)",
                                         foreground='#00ff00')
        self.ai_status_label.pack(side='left')

        # File selection
        file_frame = ttk.Frame(img_frame)
        file_frame.pack(fill='x', pady=5)

        self.spot_file_path = tk.StringVar()
        self.spot_file_entry = ttk.Entry(file_frame, textvariable=self.spot_file_path)
        self.spot_file_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(file_frame, text="Browse",
                  command=self.browse_spot_image).pack(side='left', padx=(5, 0))

        # Image list for batch mode
        ttk.Label(content, text="Selected Images:").pack(anchor='w', pady=(10, 0))
        self.spot_image_list = tk.Listbox(content, height=4, bg=self.colors['secondary'],
                                          fg=self.colors['text'], selectbackground=self.colors['accent'])
        self.spot_image_list.pack(fill='x', pady=5)

        list_btn_frame = ttk.Frame(content)
        list_btn_frame.pack(fill='x')
        ttk.Button(list_btn_frame, text="Add Image",
                  command=self.add_spot_image).pack(side='left')
        ttk.Button(list_btn_frame, text="Remove Selected",
                  command=self.remove_spot_image).pack(side='left', padx=5)
        ttk.Button(list_btn_frame, text="Clear All",
                  command=lambda: self.spot_image_list.delete(0, tk.END)).pack(side='left')

        # Settings
        settings_frame = ttk.Frame(content)
        settings_frame.pack(fill='x', pady=20)

        ttk.Label(settings_frame, text="Settings", style='SubHeader.TLabel').pack(anchor='w')

        time_frame = ttk.Frame(settings_frame)
        time_frame.pack(fill='x', pady=10)

        ttk.Label(time_frame, text="Number of Differences:").grid(row=0, column=0, sticky='w', pady=5)
        self.spot_num_diff = tk.IntVar(value=3)
        ttk.Spinbox(time_frame, from_=1, to=9, textvariable=self.spot_num_diff, width=10).grid(row=0, column=1, padx=10)

        ttk.Label(time_frame, text="Puzzle Time (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.spot_puzzle_time = tk.IntVar(value=10)
        ttk.Spinbox(time_frame, from_=5, to=60, textvariable=self.spot_puzzle_time, width=10).grid(row=1, column=1, padx=10)

        ttk.Label(time_frame, text="Answer Display Time (seconds):").grid(row=2, column=0, sticky='w', pady=5)
        self.spot_answer_time = tk.IntVar(value=5)
        ttk.Spinbox(time_frame, from_=2, to=15, textvariable=self.spot_answer_time, width=10).grid(row=2, column=1, padx=10)

        # Output filename
        output_frame = ttk.Frame(content)
        output_frame.pack(fill='x', pady=10)

        ttk.Label(output_frame, text="Output Filename:").pack(anchor='w')
        self.spot_output = tk.StringVar(value='spot_difference.mp4')
        ttk.Entry(output_frame, textvariable=self.spot_output).pack(fill='x')

        # Generate button
        ttk.Button(content, text="Generate Video",
                  command=self.generate_spot_diff).pack(pady=20)

    def create_odd_one_out_tab(self):
        """Create Odd One Out tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Odd One Out  ")

        content = ttk.Frame(tab)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content, text="Odd One Out",
                 style='SubHeader.TLabel').pack(anchor='w')
        ttk.Label(content, text="Create puzzles where one item is different from the rest",
                 foreground=self.colors['text_dim']).pack(anchor='w', pady=(0, 20))

        # Puzzle type
        type_frame = ttk.Frame(content)
        type_frame.pack(fill='x', pady=10)

        ttk.Label(type_frame, text="Puzzle Type:").pack(anchor='w')

        self.odd_type = tk.StringVar(value='shape')
        ttk.Radiobutton(type_frame, text="Shape Puzzles (auto-generated)",
                       variable=self.odd_type, value='shape').pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Text/Word Puzzles",
                       variable=self.odd_type, value='text').pack(anchor='w')

        # Settings
        settings_frame = ttk.Frame(content)
        settings_frame.pack(fill='x', pady=20)

        ttk.Label(settings_frame, text="Settings", style='SubHeader.TLabel').pack(anchor='w')

        time_frame = ttk.Frame(settings_frame)
        time_frame.pack(fill='x', pady=10)

        ttk.Label(time_frame, text="Number of Puzzles:").grid(row=0, column=0, sticky='w', pady=5)
        self.odd_num_puzzles = tk.IntVar(value=5)
        ttk.Spinbox(time_frame, from_=1, to=20, textvariable=self.odd_num_puzzles, width=10).grid(row=0, column=1, padx=10)

        ttk.Label(time_frame, text="Puzzle Time (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.odd_puzzle_time = tk.IntVar(value=8)
        ttk.Spinbox(time_frame, from_=3, to=30, textvariable=self.odd_puzzle_time, width=10).grid(row=1, column=1, padx=10)

        ttk.Label(time_frame, text="Answer Display Time (seconds):").grid(row=2, column=0, sticky='w', pady=5)
        self.odd_answer_time = tk.IntVar(value=3)
        ttk.Spinbox(time_frame, from_=1, to=10, textvariable=self.odd_answer_time, width=10).grid(row=2, column=1, padx=10)

        # Output filename
        output_frame = ttk.Frame(content)
        output_frame.pack(fill='x', pady=10)

        ttk.Label(output_frame, text="Output Filename:").pack(anchor='w')
        self.odd_output = tk.StringVar(value='odd_one_out.mp4')
        ttk.Entry(output_frame, textvariable=self.odd_output).pack(fill='x')

        # Generate button
        ttk.Button(content, text="Generate Video",
                  command=self.generate_odd_one_out).pack(pady=20)

    def create_emoji_tab(self):
        """Create Emoji Word tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Emoji Word  ")

        content = ttk.Frame(tab)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content, text="Guess the Word by Emoji",
                 style='SubHeader.TLabel').pack(anchor='w')
        ttk.Label(content, text="Show emojis and let viewers guess the word",
                 foreground=self.colors['text_dim']).pack(anchor='w', pady=(0, 20))

        # Source selection
        source_frame = ttk.Frame(content)
        source_frame.pack(fill='x', pady=10)

        ttk.Label(source_frame, text="Puzzle Source:").pack(anchor='w')

        self.emoji_source = tk.StringVar(value='sample')
        ttk.Radiobutton(source_frame, text="Use Sample Puzzles",
                       variable=self.emoji_source, value='sample').pack(anchor='w')
        ttk.Radiobutton(source_frame, text="Load from JSON File",
                       variable=self.emoji_source, value='file').pack(anchor='w')
        ttk.Radiobutton(source_frame, text="Enter Custom Puzzles",
                       variable=self.emoji_source, value='custom').pack(anchor='w')

        # File selection
        file_frame = ttk.Frame(content)
        file_frame.pack(fill='x', pady=10)

        self.emoji_file_path = tk.StringVar()
        ttk.Label(file_frame, text="JSON File:").pack(anchor='w')
        file_entry_frame = ttk.Frame(file_frame)
        file_entry_frame.pack(fill='x')

        self.emoji_file_entry = ttk.Entry(file_entry_frame, textvariable=self.emoji_file_path)
        self.emoji_file_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(file_entry_frame, text="Browse",
                  command=lambda: self.browse_file(self.emoji_file_path, [('JSON', '*.json')])).pack(side='left', padx=(5, 0))

        # Custom puzzle editor
        custom_frame = ttk.LabelFrame(content, text="Custom Puzzles")
        custom_frame.pack(fill='x', pady=10)

        # Puzzle list
        self.emoji_puzzles = []

        puzzle_list_frame = ttk.Frame(custom_frame)
        puzzle_list_frame.pack(fill='x', padx=10, pady=5)

        self.emoji_puzzle_list = tk.Listbox(puzzle_list_frame, height=3, bg=self.colors['secondary'],
                                            fg=self.colors['text'], selectbackground=self.colors['accent'])
        self.emoji_puzzle_list.pack(fill='x')

        # Add puzzle inputs
        add_frame = ttk.Frame(custom_frame)
        add_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(add_frame, text="Emojis:").grid(row=0, column=0, sticky='w')
        self.emoji_input = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.emoji_input, width=30).grid(row=0, column=1, padx=5)

        ttk.Label(add_frame, text="Answer:").grid(row=1, column=0, sticky='w')
        self.emoji_answer_input = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.emoji_answer_input, width=30).grid(row=1, column=1, padx=5)

        ttk.Label(add_frame, text="Hint:").grid(row=2, column=0, sticky='w')
        self.emoji_hint_input = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.emoji_hint_input, width=30).grid(row=2, column=1, padx=5)

        btn_frame = ttk.Frame(custom_frame)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Puzzle", command=self.add_emoji_puzzle).pack(side='left')
        ttk.Button(btn_frame, text="Remove Selected", command=self.remove_emoji_puzzle).pack(side='left', padx=5)

        # Settings
        settings_frame = ttk.Frame(content)
        settings_frame.pack(fill='x', pady=20)

        ttk.Label(settings_frame, text="Settings", style='SubHeader.TLabel').pack(anchor='w')

        time_frame = ttk.Frame(settings_frame)
        time_frame.pack(fill='x', pady=10)

        ttk.Label(time_frame, text="Guess Time (seconds):").grid(row=0, column=0, sticky='w', pady=5)
        self.emoji_guess_time = tk.IntVar(value=8)
        ttk.Spinbox(time_frame, from_=3, to=30, textvariable=self.emoji_guess_time, width=10).grid(row=0, column=1, padx=10)

        ttk.Label(time_frame, text="Answer Display Time (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.emoji_answer_time = tk.IntVar(value=3)
        ttk.Spinbox(time_frame, from_=1, to=10, textvariable=self.emoji_answer_time, width=10).grid(row=1, column=1, padx=10)

        # Output filename
        output_frame = ttk.Frame(content)
        output_frame.pack(fill='x', pady=10)

        ttk.Label(output_frame, text="Output Filename:").pack(anchor='w')
        self.emoji_output = tk.StringVar(value='emoji_word.mp4')
        ttk.Entry(output_frame, textvariable=self.emoji_output).pack(fill='x')

        # Generate button
        ttk.Button(content, text="Generate Video",
                  command=self.generate_emoji).pack(pady=20)

    def create_status_bar(self):
        """Create status bar at bottom."""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', padx=20, pady=10)

        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=(0, 5))

        self.status_label = ttk.Label(status_frame, text="Ready",
                                      foreground=self.colors['text_dim'])
        self.status_label.pack(anchor='w')

    def browse_file(self, var, filetypes):
        """Open file browser dialog."""
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def browse_spot_image(self):
        """Browse for spot the difference image."""
        filetypes = [('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        if self.spot_mode.get() == 'single':
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                self.spot_file_path.set(path)
        else:
            paths = filedialog.askopenfilenames(filetypes=filetypes)
            for path in paths:
                self.spot_image_list.insert(tk.END, path)

    def add_spot_image(self):
        """Add image to spot difference list."""
        filetypes = [('Images', '*.png *.jpg *.jpeg *.bmp *.gif')]
        paths = filedialog.askopenfilenames(filetypes=filetypes)
        for path in paths:
            self.spot_image_list.insert(tk.END, path)

    def remove_spot_image(self):
        """Remove selected image from list."""
        selection = self.spot_image_list.curselection()
        if selection:
            self.spot_image_list.delete(selection[0])

    def add_emoji_puzzle(self):
        """Add custom emoji puzzle."""
        emojis = self.emoji_input.get().strip()
        answer = self.emoji_answer_input.get().strip()
        hint = self.emoji_hint_input.get().strip()

        if not emojis or not answer:
            messagebox.showwarning("Missing Info", "Please enter emojis and answer")
            return

        puzzle = {'emojis': emojis, 'answer': answer}
        if hint:
            puzzle['hint'] = hint

        self.emoji_puzzles.append(puzzle)
        self.emoji_puzzle_list.insert(tk.END, f"{emojis} = {answer}")

        # Clear inputs
        self.emoji_input.set('')
        self.emoji_answer_input.set('')
        self.emoji_hint_input.set('')

    def remove_emoji_puzzle(self):
        """Remove selected emoji puzzle."""
        selection = self.emoji_puzzle_list.curselection()
        if selection:
            idx = selection[0]
            self.emoji_puzzle_list.delete(idx)
            del self.emoji_puzzles[idx]

    def set_status(self, message):
        """Update status label."""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def start_progress(self):
        """Start progress bar."""
        self.progress.start(10)
        self.is_generating = True

    def stop_progress(self):
        """Stop progress bar."""
        self.progress.stop()
        self.is_generating = False

    def generate_in_thread(self, func, *args):
        """Run generation in separate thread."""
        def wrapper():
            try:
                self.start_progress()
                result = func(*args)
                self.root.after(0, lambda r=result: self.generation_complete(r))
            except Exception as e:
                error_msg = str(e)
                import traceback
                traceback.print_exc()  # Print full error to console
                self.root.after(0, lambda err=error_msg: self.generation_error(err))

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()

    def generation_complete(self, output_path):
        """Handle successful generation."""
        self.stop_progress()
        self.set_status(f"Video saved: {output_path}")
        messagebox.showinfo("Success", f"Video generated successfully!\n\nSaved to:\n{output_path}")

    def generation_error(self, error):
        """Handle generation error."""
        self.stop_progress()
        self.set_status(f"Error: {error}")
        messagebox.showerror("Error", f"Failed to generate video:\n{error}")

    def generate_gk(self):
        """Generate General Knowledge video."""
        if self.is_generating:
            return

        self.set_status("Generating General Knowledge video...")

        # Get questions
        if self.gk_source.get() == 'sample':
            questions = SAMPLE_QUESTIONS
        else:
            path = self.gk_file_path.get()
            if not path or not os.path.exists(path):
                messagebox.showerror("Error", "Please select a valid JSON file")
                return
            try:
                with open(path, 'r') as f:
                    questions = json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load JSON: {e}")
                return

        def do_generate():
            generator = GeneralKnowledgeGenerator()
            generator.question_time = self.gk_question_time.get()
            generator.answer_time = self.gk_answer_time.get()

            filename = self.gk_output.get()
            if not filename.endswith('.mp4'):
                filename += '.mp4'

            return generator.generate(questions, filename)

        self.generate_in_thread(do_generate)

    def generate_spot_diff(self):
        """Generate Spot the Difference video."""
        if self.is_generating:
            return

        self.set_status("Generating Spot the Difference video...")

        mode = self.spot_mode.get()

        # Apply difficulty presets
        difficulty = self.spot_difficulty.get()
        if difficulty == 'easy':
            num_diff = 3
            puzzle_time = 15
        elif difficulty == 'hard':
            num_diff = 7
            puzzle_time = 7
        else:  # medium
            num_diff = 5
            puzzle_time = 10

        # AI mode - use Pollinations.ai
        if mode == 'ai':
            def do_generate():
                from ai_image_generator import SCENE_PROMPTS
                import random

                generator = SpotDifferenceGenerator()
                filename = self.spot_output.get()
                if not filename.endswith('.mp4'):
                    filename += '.mp4'

                # Select random scene prompts
                selected_prompts = random.sample(
                    SCENE_PROMPTS,
                    min(self.spot_num_puzzles.get(), len(SCENE_PROMPTS))
                )

                return generator.generate_with_ai(
                    num_puzzles=self.spot_num_puzzles.get(),
                    scene_prompts=selected_prompts,
                    num_differences=num_diff,
                    puzzle_time=puzzle_time,
                    reveal_time=self.spot_answer_time.get(),
                    difficulty=difficulty,
                    output_filename=filename
                )

            self.generate_in_thread(do_generate)
            return

        # Auto mode - fetch images from internet
        if mode == 'auto':
            def do_generate():
                generator = SpotDifferenceGenerator()

                filename = self.spot_output.get()
                if not filename.endswith('.mp4'):
                    filename += '.mp4'

                return generator.generate_auto(
                    num_puzzles=self.spot_num_puzzles.get(),
                    num_differences=num_diff,
                    puzzle_time=puzzle_time,
                    reveal_time=self.spot_answer_time.get(),
                    output_filename=filename
                )

            self.generate_in_thread(do_generate)
            return

        # Get images for single/batch mode
        if mode == 'single':
            image_path = self.spot_file_path.get()
            if not image_path or not os.path.exists(image_path):
                messagebox.showerror("Error", "Please select an image file")
                return
            image_paths = [image_path]
            is_batch = False
        else:
            image_paths = list(self.spot_image_list.get(0, tk.END))
            if not image_paths:
                messagebox.showerror("Error", "Please add at least one image")
                return
            is_batch = len(image_paths) > 1

        def do_generate():
            generator = SpotDifferenceGenerator()

            filename = self.spot_output.get()
            if not filename.endswith('.mp4'):
                filename += '.mp4'

            if is_batch:
                return generator.generate_batch(
                    image_paths,
                    num_differences=self.spot_num_diff.get(),
                    puzzle_time=self.spot_puzzle_time.get(),
                    reveal_time=self.spot_answer_time.get(),
                    output_filename=filename
                )
            else:
                return generator.generate(
                    image_paths[0],
                    num_differences=self.spot_num_diff.get(),
                    puzzle_time=self.spot_puzzle_time.get(),
                    reveal_time=self.spot_answer_time.get(),
                    output_filename=filename
                )

        self.generate_in_thread(do_generate)

    def generate_odd_one_out(self):
        """Generate Odd One Out video."""
        if self.is_generating:
            return

        self.set_status("Generating Odd One Out video...")

        num_puzzles = self.odd_num_puzzles.get()
        puzzle_type = self.odd_type.get()

        def do_generate():
            generator = OddOneOutGenerator()

            # Generate puzzles
            puzzles = []
            diff_types = ['color', 'shape', 'size']
            grids = [(3, 3), (4, 4), (4, 5), (5, 4)]

            for i in range(num_puzzles):
                if puzzle_type == 'shape':
                    puzzles.append({
                        'type': 'shape',
                        'difference': diff_types[i % len(diff_types)],
                        'grid': grids[i % len(grids)]
                    })
                else:
                    # Default text puzzles
                    words = ['Cat'] * 15 + ['Cot']
                    puzzles.append({
                        'type': 'text',
                        'words': words,
                        'grid': (4, 4)
                    })

            filename = self.odd_output.get()
            if not filename.endswith('.mp4'):
                filename += '.mp4'

            return generator.generate(
                puzzles,
                puzzle_time=self.odd_puzzle_time.get(),
                answer_time=self.odd_answer_time.get(),
                output_filename=filename
            )

        self.generate_in_thread(do_generate)

    def generate_emoji(self):
        """Generate Emoji Word video."""
        if self.is_generating:
            return

        self.set_status("Generating Emoji Word video...")

        # Get puzzles
        source = self.emoji_source.get()

        if source == 'sample':
            puzzles = SAMPLE_EMOJI_PUZZLES
        elif source == 'file':
            path = self.emoji_file_path.get()
            if not path or not os.path.exists(path):
                messagebox.showerror("Error", "Please select a valid JSON file")
                return
            try:
                with open(path, 'r') as f:
                    puzzles = json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load JSON: {e}")
                return
        else:
            if not self.emoji_puzzles:
                messagebox.showerror("Error", "Please add at least one puzzle")
                return
            puzzles = self.emoji_puzzles

        def do_generate():
            generator = EmojiWordGenerator()

            filename = self.emoji_output.get()
            if not filename.endswith('.mp4'):
                filename += '.mp4'

            return generator.generate(
                puzzles,
                guess_time=self.emoji_guess_time.get(),
                answer_time=self.emoji_answer_time.get(),
                output_filename=filename
            )

        self.generate_in_thread(do_generate)

    def create_automation_tab(self):
        """Create Automation tab for continuous video generation."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Automation  ")

        # Main container with scrollbar
        canvas = tk.Canvas(tab, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        content = ttk.Frame(scrollable_frame)
        content.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(content, text="Automation Pipeline",
                 style='SubHeader.TLabel').pack(anchor='w')
        ttk.Label(content, text="AI generates quiz → Video created → Repeat forever",
                 foreground=self.colors['text_dim']).pack(anchor='w', pady=(0, 20))

        # Status frame
        status_frame = ttk.LabelFrame(content, text="Status")
        status_frame.pack(fill='x', pady=10)

        self.auto_status_text = tk.StringVar(value="Stopped")
        self.auto_generated = tk.StringVar(value="0")

        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill='x', padx=10, pady=10)

        ttk.Label(status_grid, text="Status:").grid(row=0, column=0, sticky='w', pady=2)
        self.auto_status_label = ttk.Label(status_grid, textvariable=self.auto_status_text, foreground='#ff6666')
        self.auto_status_label.grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Videos Generated:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Label(status_grid, textvariable=self.auto_generated).grid(row=1, column=1, sticky='w', padx=10)

        # Settings frame
        settings_frame = ttk.LabelFrame(content, text="Settings")
        settings_frame.pack(fill='x', pady=10)

        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill='x', padx=10, pady=10)

        # Ollama model
        ttk.Label(settings_grid, text="AI Model:").grid(row=0, column=0, sticky='w', pady=5)
        self.auto_model = tk.StringVar(value="mistral")
        model_combo = ttk.Combobox(settings_grid, textvariable=self.auto_model, width=20)
        model_combo.grid(row=0, column=1, padx=10, sticky='w')
        model_combo['values'] = ['mistral', 'llama3.2', 'gemma2']
        ttk.Button(settings_grid, text="Refresh", command=self.refresh_models).grid(row=0, column=2)

        # Questions per video
        ttk.Label(settings_grid, text="Questions per Video:").grid(row=1, column=0, sticky='w', pady=5)
        self.auto_questions = tk.IntVar(value=10)
        ttk.Spinbox(settings_grid, from_=5, to=30, textvariable=self.auto_questions, width=10).grid(row=1, column=1, padx=10, sticky='w')

        # Topics
        ttk.Label(settings_grid, text="Topics (comma-separated):").grid(row=2, column=0, sticky='w', pady=5)
        self.auto_topics = tk.StringVar(value="Science, History, Geography, Movies, Music, Sports")
        ttk.Entry(settings_grid, textvariable=self.auto_topics, width=50).grid(row=2, column=1, columnspan=2, padx=10, sticky='w')

        # Control buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=20)

        self.auto_start_btn = ttk.Button(btn_frame, text="Start Generation", command=self.start_automation)
        self.auto_start_btn.pack(side='left', padx=5)

        self.auto_stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_automation, state='disabled')
        self.auto_stop_btn.pack(side='left', padx=5)

        # Log frame
        log_frame = ttk.LabelFrame(content, text="Log")
        log_frame.pack(fill='both', expand=True, pady=10)

        self.auto_log = scrolledtext.ScrolledText(log_frame, height=10, bg=self.colors['secondary'],
                                                   fg=self.colors['text'], insertbackground=self.colors['text'])
        self.auto_log.pack(fill='both', expand=True, padx=5, pady=5)

        # Automation state
        self.automation_running = False
        self.automation_thread = None
        self.pipeline = None

        # Auto-refresh models on tab creation
        self.root.after(1000, self.refresh_models)

    def refresh_models(self):
        """Refresh available Ollama models."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request('http://localhost:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                models = [m['name'] for m in data.get('models', [])]
                if models:
                    self.auto_model.set(models[0])
                    self.log_auto(f"Found models: {', '.join(models)}")
        except Exception as e:
            self.log_auto(f"Error getting models: {e}")

    def log_auto(self, message):
        """Add message to automation log."""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.auto_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.auto_log.see(tk.END)

    def update_auto_status(self):
        """Update automation status display."""
        if self.pipeline:
            state = self.pipeline.state
            self.auto_generated.set(str(state.total_generated))

    def start_automation(self):
        """Start the automation pipeline."""
        if self.automation_running:
            return

        # Import here to avoid circular imports
        from automation import AutomationPipeline, CONFIG

        # Update config from GUI
        CONFIG['ollama_model'] = self.auto_model.get()
        CONFIG['questions_per_video'] = self.auto_questions.get()
        CONFIG['topics'] = [t.strip() for t in self.auto_topics.get().split(',') if t.strip()]

        self.pipeline = AutomationPipeline()

        def run_pipeline():
            self.automation_running = True
            self.root.after(0, lambda: self.auto_status_text.set("Running"))
            self.root.after(0, lambda: self.auto_status_label.config(foreground='#66ff66'))
            self.root.after(0, lambda: self.auto_start_btn.config(state='disabled'))
            self.root.after(0, lambda: self.auto_stop_btn.config(state='normal'))

            try:
                self.pipeline.quiz_gen.initialize()
                self.root.after(0, lambda: self.log_auto("Pipeline initialized"))

                while self.automation_running:
                    try:
                        # Update status
                        self.root.after(0, self.update_auto_status)

                        # Generate video
                        self.root.after(0, lambda: self.log_auto("Generating new video..."))
                        result = self.pipeline.generate_one()
                        if result:
                            self.root.after(0, lambda r=result: self.log_auto(f"Generated: {os.path.basename(r)}"))

                        import time
                        time.sleep(5)

                    except Exception as e:
                        self.root.after(0, lambda err=str(e): self.log_auto(f"Error: {err}"))
                        import time
                        time.sleep(30)

            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_auto(f"Pipeline error: {err}"))

            self.automation_running = False
            self.root.after(0, lambda: self.auto_status_text.set("Stopped"))
            self.root.after(0, lambda: self.auto_status_label.config(foreground='#ff6666'))
            self.root.after(0, lambda: self.auto_start_btn.config(state='normal'))
            self.root.after(0, lambda: self.auto_stop_btn.config(state='disabled'))

        self.automation_thread = threading.Thread(target=run_pipeline, daemon=True)
        self.automation_thread.start()
        self.log_auto("Starting automation pipeline...")

    def stop_automation(self):
        """Stop the automation pipeline."""
        self.automation_running = False
        self.log_auto("Stopping pipeline...")



def main():
    root = tk.Tk()
    app = VideoGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
