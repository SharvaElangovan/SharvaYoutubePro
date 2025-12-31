#!/usr/bin/env python3
"""
Video Generator App
Generate quiz videos: General Knowledge, Spot the Difference, Odd One Out, Emoji Word

Works completely offline!
"""

import os
import sys
import json
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


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    """Print app header."""
    print("\n" + "=" * 60)
    print("        VIDEO GENERATOR - Quiz & Puzzle Videos")
    print("=" * 60)


def print_menu():
    """Print main menu."""
    print("\n  Choose a video type to generate:\n")
    print("  1. General Knowledge Quiz")
    print("  2. Spot the Difference")
    print("  3. Odd One Out")
    print("  4. Guess the Word by Emoji")
    print("  5. Exit")
    print()


def get_int_input(prompt, min_val=1, max_val=100, default=None):
    """Get integer input with validation."""
    while True:
        try:
            default_str = f" [{default}]" if default else ""
            user_input = input(f"{prompt}{default_str}: ").strip()

            if not user_input and default:
                return default

            value = int(user_input)
            if min_val <= value <= max_val:
                return value
            print(f"  Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print("  Please enter a valid number")


def get_file_path(prompt, must_exist=True):
    """Get file path input."""
    while True:
        path = input(f"{prompt}: ").strip()

        if not path:
            print("  Please enter a path")
            continue

        # Expand user home directory
        path = os.path.expanduser(path)

        if must_exist and not os.path.exists(path):
            print(f"  File not found: {path}")
            continue

        return path


def generate_general_knowledge():
    """Generate General Knowledge quiz video."""
    clear_screen()
    print_header()
    print("\n  GENERAL KNOWLEDGE QUIZ\n")

    print("  Options:")
    print("  1. Use sample questions")
    print("  2. Load questions from JSON file")
    print("  3. Enter questions manually")

    choice = get_int_input("\n  Select option", 1, 3, 1)

    if choice == 1:
        questions = SAMPLE_QUESTIONS
        print(f"\n  Using {len(questions)} sample questions")

    elif choice == 2:
        path = get_file_path("  Enter JSON file path")
        try:
            with open(path, 'r') as f:
                questions = json.load(f)
            print(f"\n  Loaded {len(questions)} questions")
        except Exception as e:
            print(f"  Error loading file: {e}")
            input("\n  Press Enter to continue...")
            return

    else:
        questions = []
        print("\n  Enter questions (type 'done' when finished):\n")

        while True:
            q_num = len(questions) + 1
            question = input(f"  Question {q_num}: ").strip()

            if question.lower() == 'done':
                break

            options = []
            print("  Enter 4 options:")
            for i in range(4):
                opt = input(f"    Option {chr(65+i)}: ").strip()
                options.append(opt)

            answer = get_int_input("  Correct answer (1-4)", 1, 4) - 1

            questions.append({
                'question': question,
                'options': options,
                'answer': answer
            })
            print()

        if not questions:
            print("  No questions entered!")
            input("\n  Press Enter to continue...")
            return

    # Settings
    question_time = get_int_input("\n  Time per question (seconds)", 3, 30, 5)
    answer_time = get_int_input("  Answer display time (seconds)", 1, 10, 3)
    filename = input("  Output filename [general_knowledge.mp4]: ").strip()
    if not filename:
        filename = "general_knowledge.mp4"
    if not filename.endswith('.mp4'):
        filename += '.mp4'

    print("\n  Generating video...")

    generator = GeneralKnowledgeGenerator()
    generator.question_time = question_time
    generator.answer_time = answer_time

    output_path = generator.generate(questions, filename)

    print(f"\n  Video saved to: {output_path}")
    input("\n  Press Enter to continue...")


def generate_spot_difference():
    """Generate Spot the Difference video."""
    clear_screen()
    print_header()
    print("\n  SPOT THE DIFFERENCE\n")

    print("  Options:")
    print("  1. Auto-generate (fetches images from internet)")
    print("  2. Single image (provide your own)")
    print("  3. Multiple images (batch)")

    choice = get_int_input("\n  Select option", 1, 3, 1)

    if choice == 1:
        # Auto-generate mode
        num_puzzles = get_int_input("  Number of puzzles", 1, 20, 5)

        print("\n  Difficulty levels:")
        print("  1. Easy   (3 differences, 15 seconds)")
        print("  2. Medium (5 differences, 10 seconds)")
        print("  3. Hard   (7 differences, 7 seconds)")
        difficulty = get_int_input("  Select difficulty", 1, 3, 2)

        if difficulty == 1:
            num_diff, puzzle_time = 3, 15
        elif difficulty == 3:
            num_diff, puzzle_time = 7, 7
        else:
            num_diff, puzzle_time = 5, 10

        reveal_time = get_int_input("  Answer display time (seconds)", 2, 15, 5)
        filename = input("  Output filename [spot_difference_auto.mp4]: ").strip()
        if not filename:
            filename = "spot_difference_auto.mp4"
        if not filename.endswith('.mp4'):
            filename += '.mp4'

        print("\n  Fetching images and generating video...")
        print("  (This may take a moment as images are downloaded)\n")

        generator = SpotDifferenceGenerator()
        output_path = generator.generate_auto(
            num_puzzles=num_puzzles,
            num_differences=num_diff,
            puzzle_time=puzzle_time,
            reveal_time=reveal_time,
            output_filename=filename
        )

    elif choice == 2:
        image_path = get_file_path("  Enter image path")

        num_diff = get_int_input("  Number of differences to create", 1, 9, 3)
        puzzle_time = get_int_input("  Time to find differences (seconds)", 5, 60, 10)
        reveal_time = get_int_input("  Answer display time (seconds)", 2, 15, 5)
        filename = input("  Output filename [spot_difference.mp4]: ").strip()
        if not filename:
            filename = "spot_difference.mp4"
        if not filename.endswith('.mp4'):
            filename += '.mp4'

        print("\n  Generating video...")

        generator = SpotDifferenceGenerator()
        output_path = generator.generate(
            image_path,
            num_differences=num_diff,
            puzzle_time=puzzle_time,
            reveal_time=reveal_time,
            output_filename=filename
        )

    else:  # choice == 3
        print("\n  Enter image paths (one per line, type 'done' when finished):")
        image_paths = []

        while True:
            path = input(f"  Image {len(image_paths)+1}: ").strip()

            if path.lower() == 'done':
                break

            path = os.path.expanduser(path)
            if os.path.exists(path):
                image_paths.append(path)
            else:
                print(f"    File not found: {path}")

        if not image_paths:
            print("  No images provided!")
            input("\n  Press Enter to continue...")
            return

        num_diff = get_int_input("  Number of differences per image", 1, 9, 3)
        puzzle_time = get_int_input("  Time per puzzle (seconds)", 5, 60, 10)
        reveal_time = get_int_input("  Answer display time (seconds)", 2, 15, 5)
        filename = input("  Output filename [spot_difference_batch.mp4]: ").strip()
        if not filename:
            filename = "spot_difference_batch.mp4"
        if not filename.endswith('.mp4'):
            filename += '.mp4'

        print("\n  Generating video...")

        generator = SpotDifferenceGenerator()
        output_path = generator.generate_batch(
            image_paths,
            num_differences=num_diff,
            puzzle_time=puzzle_time,
            reveal_time=reveal_time,
            output_filename=filename
        )

    print(f"\n  Video saved to: {output_path}")
    input("\n  Press Enter to continue...")


def generate_odd_one_out():
    """Generate Odd One Out video."""
    clear_screen()
    print_header()
    print("\n  ODD ONE OUT\n")

    print("  Puzzle types:")
    print("  1. Auto-generate shape puzzles")
    print("  2. Custom text/word puzzles")

    choice = get_int_input("\n  Select option", 1, 2, 1)

    if choice == 1:
        num_puzzles = get_int_input("  Number of puzzles", 1, 20, 5)

        puzzles = []
        diff_types = ['color', 'shape', 'size']
        grids = [(3, 3), (4, 4), (4, 5), (5, 4)]

        for i in range(num_puzzles):
            puzzles.append({
                'type': 'shape',
                'difference': diff_types[i % len(diff_types)],
                'grid': grids[i % len(grids)]
            })

    else:
        puzzles = []
        print("\n  Enter word puzzles (type 'done' when finished):\n")

        while True:
            print(f"\n  Puzzle {len(puzzles)+1}:")
            word = input("    Normal word (or 'done'): ").strip()

            if word.lower() == 'done':
                break

            odd = input("    Odd word (misspelled/different): ").strip()
            count = get_int_input("    Number of normal words", 8, 30, 15)
            rows = get_int_input("    Grid rows", 2, 6, 4)
            cols = get_int_input("    Grid columns", 2, 6, 4)

            words = [word] * count + [odd]
            puzzles.append({
                'type': 'text',
                'words': words,
                'grid': (rows, cols)
            })

        if not puzzles:
            print("  No puzzles created!")
            input("\n  Press Enter to continue...")
            return

    puzzle_time = get_int_input("\n  Time per puzzle (seconds)", 3, 30, 8)
    answer_time = get_int_input("  Answer display time (seconds)", 1, 10, 3)
    filename = input("  Output filename [odd_one_out.mp4]: ").strip()
    if not filename:
        filename = "odd_one_out.mp4"
    if not filename.endswith('.mp4'):
        filename += '.mp4'

    print("\n  Generating video...")

    generator = OddOneOutGenerator()
    output_path = generator.generate(
        puzzles,
        puzzle_time=puzzle_time,
        answer_time=answer_time,
        output_filename=filename
    )

    print(f"\n  Video saved to: {output_path}")
    input("\n  Press Enter to continue...")


def generate_emoji_word():
    """Generate Guess the Word by Emoji video."""
    clear_screen()
    print_header()
    print("\n  GUESS THE WORD BY EMOJI\n")

    print("  Options:")
    print("  1. Use sample puzzles")
    print("  2. Load from JSON file")
    print("  3. Enter puzzles manually")

    choice = get_int_input("\n  Select option", 1, 3, 1)

    if choice == 1:
        puzzles = SAMPLE_EMOJI_PUZZLES
        print(f"\n  Using {len(puzzles)} sample puzzles")

    elif choice == 2:
        path = get_file_path("  Enter JSON file path")
        try:
            with open(path, 'r') as f:
                puzzles = json.load(f)
            print(f"\n  Loaded {len(puzzles)} puzzles")
        except Exception as e:
            print(f"  Error loading file: {e}")
            input("\n  Press Enter to continue...")
            return

    else:
        puzzles = []
        print("\n  Enter emoji puzzles (type 'done' when finished):\n")
        print("  Tip: Copy-paste emojis from an emoji picker\n")

        while True:
            print(f"\n  Puzzle {len(puzzles)+1}:")
            emojis = input("    Emojis (or 'done'): ").strip()

            if emojis.lower() == 'done':
                break

            answer = input("    Answer: ").strip()
            hint = input("    Hint (optional): ").strip()
            category = input("    Category (optional): ").strip()

            puzzle = {
                'emojis': emojis,
                'answer': answer
            }
            if hint:
                puzzle['hint'] = hint
            if category:
                puzzle['category'] = category

            puzzles.append(puzzle)

        if not puzzles:
            print("  No puzzles created!")
            input("\n  Press Enter to continue...")
            return

    guess_time = get_int_input("\n  Time per puzzle (seconds)", 3, 30, 8)
    answer_time = get_int_input("  Answer display time (seconds)", 1, 10, 3)
    filename = input("  Output filename [emoji_word.mp4]: ").strip()
    if not filename:
        filename = "emoji_word.mp4"
    if not filename.endswith('.mp4'):
        filename += '.mp4'

    print("\n  Generating video...")

    generator = EmojiWordGenerator()
    output_path = generator.generate(
        puzzles,
        guess_time=guess_time,
        answer_time=answer_time,
        output_filename=filename
    )

    print(f"\n  Video saved to: {output_path}")
    input("\n  Press Enter to continue...")


def main():
    """Main app loop."""
    while True:
        clear_screen()
        print_header()
        print_menu()

        choice = get_int_input("  Enter choice", 1, 5)

        if choice == 1:
            generate_general_knowledge()
        elif choice == 2:
            generate_spot_difference()
        elif choice == 3:
            generate_odd_one_out()
        elif choice == 4:
            generate_emoji_word()
        elif choice == 5:
            print("\n  Goodbye!\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
