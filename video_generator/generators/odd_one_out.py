"""Odd One Out Video Generator."""

from .base import BaseVideoGenerator
from PIL import Image, ImageDraw
from collections import Counter
import random
import os


class OddOneOutGenerator(BaseVideoGenerator):
    """Generate Odd One Out puzzle videos."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.puzzle_time = 8
        self.answer_time = 3

    def create_grid_frame(self, items, odd_index, rows, cols, title="Find the Odd One Out!",
                          highlight_answer=False, show_timer=None):
        """
        Create a frame with a grid of items where one is different.

        Args:
            items: List of dicts with 'type', 'color', 'size' etc.
            odd_index: Index of the odd item
            rows, cols: Grid dimensions
            title: Frame title
            highlight_answer: Whether to highlight the odd one
            show_timer: Timer value to display (or None)
        """
        frame = self.create_frame()

        # Title at top
        title_y = 60
        self.add_text(frame, title, (self.width // 2, title_y),
                     font=self.font_large, color=self.accent_color)

        # Calculate grid layout - dynamic based on screen size
        padding = 80
        start_y = 130
        grid_width = self.width - (padding * 2)
        grid_height = self.height - start_y - 100  # Leave room for timer at bottom
        cell_width = grid_width // cols
        cell_height = grid_height // rows
        start_x = padding

        draw = ImageDraw.Draw(frame)

        for idx, item in enumerate(items):
            row = idx // cols
            col = idx % cols

            center_x = start_x + col * cell_width + cell_width // 2
            center_y = start_y + row * cell_height + cell_height // 2

            # Draw the shape
            self._draw_item(draw, item, center_x, center_y)

            # Highlight if showing answer
            if highlight_answer and idx == odd_index:
                radius = item.get('size', 50) + 20
                draw.ellipse((center_x - radius, center_y - radius,
                             center_x + radius, center_y + radius),
                            outline=(255, 50, 50), width=5)

                # Add "ODD" label
                self.add_text(frame, "ODD!", (center_x, center_y + radius + 30),
                             font=self.font_small, color=(255, 50, 50))

        # Timer
        if show_timer is not None:
            timer_y = self.height - 100
            self.add_circle(frame, (self.width // 2, timer_y), 50,
                           fill_color=(60, 60, 80), outline_color=self.accent_color)
            self.add_text(frame, str(show_timer), (self.width // 2, timer_y),
                         font=self.font_medium, color=self.accent_color)

        return frame

    def _draw_item(self, draw, item, x, y):
        """Draw an item (shape) at the specified position."""
        shape_type = item.get('type', 'circle')
        color = item.get('color', (100, 200, 255))
        size = item.get('size', 50)

        if shape_type == 'circle':
            draw.ellipse((x - size, y - size, x + size, y + size), fill=color)
        elif shape_type == 'square':
            draw.rectangle((x - size, y - size, x + size, y + size), fill=color)
        elif shape_type == 'triangle':
            points = [(x, y - size), (x - size, y + size), (x + size, y + size)]
            draw.polygon(points, fill=color)
        elif shape_type == 'diamond':
            points = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
            draw.polygon(points, fill=color)
        elif shape_type == 'star':
            points = [
                (x, y - size),
                (x + size//3, y - size//3),
                (x + size, y),
                (x + size//3, y + size//3),
                (x, y + size),
                (x - size//3, y + size//3),
                (x - size, y),
                (x - size//3, y - size//3)
            ]
            draw.polygon(points, fill=color)
        elif shape_type == 'hexagon':
            import math
            points = []
            for i in range(6):
                angle = math.pi / 3 * i - math.pi / 6
                px = x + size * math.cos(angle)
                py = y + size * math.sin(angle)
                points.append((px, py))
            draw.polygon(points, fill=color)

    def generate_puzzle(self, grid_size=(4, 4), difference_type='color'):
        """
        Generate a puzzle with items where one is different.

        Args:
            grid_size: (rows, cols) tuple
            difference_type: 'color', 'shape', 'size', or 'rotation'

        Returns:
            items: List of item dicts
            odd_index: Index of the odd item
        """
        rows, cols = grid_size
        total_items = rows * cols

        # Base item properties
        shapes = ['circle', 'square', 'triangle', 'diamond', 'star', 'hexagon']
        colors = [
            (255, 99, 71),   # Tomato
            (50, 205, 50),   # Lime
            (65, 105, 225),  # Royal blue
            (255, 215, 0),   # Gold
            (238, 130, 238), # Violet
            (0, 206, 209),   # Turquoise
        ]

        base_shape = random.choice(shapes)
        base_color = random.choice(colors)
        base_size = 55

        # Create all items as the same
        items = []
        for _ in range(total_items):
            items.append({
                'type': base_shape,
                'color': base_color,
                'size': base_size
            })

        # Pick one to be different
        odd_index = random.randint(0, total_items - 1)

        if difference_type == 'color':
            odd_color = random.choice([c for c in colors if c != base_color])
            items[odd_index]['color'] = odd_color
        elif difference_type == 'shape':
            odd_shape = random.choice([s for s in shapes if s != base_shape])
            items[odd_index]['type'] = odd_shape
        elif difference_type == 'size':
            items[odd_index]['size'] = base_size + random.choice([-20, 25])

        return items, odd_index, (rows, cols)

    def create_text_grid_frame(self, words, odd_index, rows, cols, title="Find the Odd One Out!",
                               highlight_answer=False, show_timer=None):
        """Create a frame with a grid of text/words."""
        frame = self.create_frame()

        # Title at top
        title_y = 60
        self.add_text(frame, title, (self.width // 2, title_y),
                     font=self.font_large, color=self.accent_color)

        # Calculate grid layout - dynamic based on screen size
        padding = 60
        start_y = 130
        grid_width = self.width - (padding * 2)
        grid_height = self.height - start_y - 100  # Leave room for timer
        cell_width = grid_width // cols
        cell_height = grid_height // rows
        start_x = padding

        for idx, word in enumerate(words):
            row = idx // cols
            col = idx % cols

            center_x = start_x + col * cell_width + cell_width // 2
            center_y = start_y + row * cell_height + cell_height // 2

            # Background box
            box_padding = 10
            bg_color = (50, 50, 70)
            border_color = (100, 100, 120)

            if highlight_answer and idx == odd_index:
                bg_color = (100, 50, 50)
                border_color = (255, 50, 50)

            bbox = (center_x - cell_width//2 + box_padding,
                   center_y - 40,
                   center_x + cell_width//2 - box_padding,
                   center_y + 40)

            self.add_rounded_rectangle(frame, bbox, radius=10,
                                       fill_color=bg_color, outline_color=border_color)

            # Word text
            self.add_text(frame, word, (center_x, center_y),
                         font=self.font_small, color=self.text_color)

        # Timer
        if show_timer is not None:
            timer_y = self.height - 100
            self.add_circle(frame, (self.width // 2, timer_y), 50,
                           fill_color=(60, 60, 80), outline_color=self.accent_color)
            self.add_text(frame, str(show_timer), (self.width // 2, timer_y),
                         font=self.font_medium, color=self.accent_color)

        return frame

    def generate(self, puzzles=None, puzzle_time=8, answer_time=3,
                 output_filename="odd_one_out.mp4"):
        """
        Generate an Odd One Out video using fast FFmpeg piping.

        Args:
            puzzles: List of puzzle configs, or None for auto-generated
            puzzle_time: Seconds to show each puzzle
            answer_time: Seconds to show answer
            output_filename: Output file name
        """
        frames = []  # List of (PIL_Image, duration) tuples

        # Auto-generate puzzles if none provided
        if puzzles is None:
            puzzles = [
                {'type': 'shape', 'difference': 'color', 'grid': (4, 4)},
                {'type': 'shape', 'difference': 'shape', 'grid': (3, 3)},
                {'type': 'shape', 'difference': 'size', 'grid': (4, 4)},
                {'type': 'shape', 'difference': 'color', 'grid': (5, 4)},
                {'type': 'text', 'words': ['Apple'] * 15 + ['Aple'], 'grid': (4, 4)},
            ]

        # Intro
        intro_frame = self.create_title_frame("Odd One Out", "Find the different one!")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        for puzzle_num, puzzle in enumerate(puzzles, 1):
            # Puzzle title
            title_frame = self.create_title_frame(f"Puzzle {puzzle_num}",
                                                  "Find the Odd One Out!")
            frames.append((title_frame, 2))

            if puzzle.get('type') == 'text':
                # Text/word puzzle
                words = puzzle['words']
                rows, cols = puzzle.get('grid', (4, 4))

                # Find the odd word BEFORE shuffle (the one that appears only once)
                word_counts = Counter(words)
                odd_word = None
                for word, count in word_counts.items():
                    if count == 1:
                        odd_word = word
                        break

                # Fallback if no unique word found
                if odd_word is None:
                    odd_word = words[-1]

                random.shuffle(words)
                # Find odd word's position after shuffle
                odd_index = words.index(odd_word)

                # Puzzle with timer
                for sec in range(puzzle_time, 0, -1):
                    puzzle_frame = self.create_text_grid_frame(
                        words[:rows*cols], odd_index, rows, cols,
                        title=f"Puzzle {puzzle_num}",
                        show_timer=sec
                    )
                    frames.append((puzzle_frame, 1))

                # Answer
                answer_frame = self.create_text_grid_frame(
                    words[:rows*cols], odd_index, rows, cols,
                    title="Answer!",
                    highlight_answer=True
                )
                frames.append((answer_frame, answer_time))

            else:
                # Shape puzzle
                items, odd_index, (rows, cols) = self.generate_puzzle(
                    grid_size=puzzle.get('grid', (4, 4)),
                    difference_type=puzzle.get('difference', 'color')
                )

                # Puzzle with timer
                for sec in range(puzzle_time, 0, -1):
                    puzzle_frame = self.create_grid_frame(
                        items, odd_index, rows, cols,
                        title=f"Puzzle {puzzle_num}",
                        show_timer=sec
                    )
                    frames.append((puzzle_frame, 1))

                # Answer
                answer_frame = self.create_grid_frame(
                    items, odd_index, rows, cols,
                    title="Answer!",
                    highlight_answer=True
                )
                frames.append((answer_frame, answer_time))

        # Outro
        outro_frame = self.create_title_frame("Great Job!", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)


# Sample word puzzles
SAMPLE_TEXT_PUZZLES = [
    {'words': ['Cat'] * 15 + ['Cot'], 'grid': (4, 4)},
    {'words': ['Python'] * 11 + ['Pyhton'], 'grid': (3, 4)},
    {'words': ['Hello'] * 19 + ['Hallo'], 'grid': (5, 4)},
]
