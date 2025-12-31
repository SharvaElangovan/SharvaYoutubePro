"""Guess the Word by Emoji Video Generator."""

from .base import BaseVideoGenerator
from PIL import ImageFont, ImageDraw
from pilmoji import Pilmoji
import os


class EmojiWordGenerator(BaseVideoGenerator):
    """Generate Guess the Word by Emoji puzzle videos."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.guess_time = 8
        self.answer_time = 3

        # Font for emoji text (pilmoji will handle emoji rendering)
        self.emoji_font = self._get_font(80)
        self.emoji_font_large = self._get_font(100)

    def add_emoji_text(self, img, text, position, font=None, color=None):
        """Add text with emoji support using pilmoji."""
        if font is None:
            font = self.emoji_font_large
        if color is None:
            color = self.text_color

        # Calculate text position for center alignment
        with Pilmoji(img) as pilmoji:
            # Get text size for centering
            text_bbox = pilmoji.getsize(text, font)
            x = position[0] - text_bbox[0] // 2
            y = position[1] - text_bbox[1] // 2
            pilmoji.text((x, y), text, font=font, fill=color)

        return img

    def create_puzzle_frame(self, emojis, hint=None, title="Guess the Word!",
                            show_timer=None, show_answer=None):
        """
        Create a frame showing emojis for the user to guess (landscape layout).

        Args:
            emojis: String of emojis representing the word
            hint: Optional hint text
            title: Frame title
            show_timer: Timer value (or None)
            show_answer: The answer to reveal (or None)
        """
        frame = self.create_frame()

        # Title at top
        self.add_text(frame, title, (self.width // 2, 80),
                     font=self.font_large, color=self.accent_color)

        # Emoji display area - centered vertically for landscape
        emoji_y = self.height // 2 - 50

        # Create a background box for emojis (wider for landscape)
        emoji_box_padding = 300
        self.add_rounded_rectangle(frame,
                                   (emoji_box_padding, emoji_y - 100,
                                    self.width - emoji_box_padding, emoji_y + 100),
                                   radius=20, fill_color=(50, 50, 70),
                                   outline_color=(100, 100, 120))

        # Draw emojis using pilmoji for proper emoji rendering
        self.add_emoji_text(frame, emojis, (self.width // 2, emoji_y),
                           font=self.emoji_font_large, color=self.text_color)

        # Hint section - below emojis
        if hint:
            hint_y = emoji_y + 150
            self.add_text(frame, "Hint:", (self.width // 2, hint_y),
                         font=self.font_small, color=(150, 150, 150))
            self.add_text(frame, hint, (self.width // 2, hint_y + 45),
                         font=self.font_medium, color=self.accent_color)

        # Answer blanks or revealed answer
        answer_y = self.height - 150 if hint else self.height - 180

        if show_answer:
            # Show the answer
            self.add_rounded_rectangle(frame,
                                       (self.width // 2 - 300, answer_y - 50,
                                        self.width // 2 + 300, answer_y + 50),
                                       radius=15, fill_color=(30, 100, 30),
                                       outline_color=self.correct_color)

            self.add_text(frame, show_answer.upper(), (self.width // 2, answer_y),
                         font=self.font_large, color=self.correct_color)
        else:
            # Show question marks as blanks
            self.add_text(frame, "? ? ? ? ?", (self.width // 2, answer_y),
                         font=self.font_large, color=(100, 100, 120))

        # Timer - top left corner for landscape
        if show_timer is not None:
            timer_x = 80
            timer_y = 80
            self.add_circle(frame, (timer_x, timer_y), 50,
                           fill_color=(60, 60, 80), outline_color=self.accent_color)
            self.add_text(frame, str(show_timer), (timer_x, timer_y),
                         font=self.font_medium, color=self.accent_color)

        return frame

    def create_category_frame(self, category):
        """Create a frame showing the puzzle category."""
        frame = self.create_frame()

        self.add_text(frame, "Category:", (self.width // 2, self.height // 2 - 80),
                     font=self.font_medium, color=(150, 150, 150))
        self.add_text(frame, category, (self.width // 2, self.height // 2 + 20),
                     font=self.font_large, color=self.accent_color)

        return frame

    def generate(self, puzzles=None, guess_time=8, answer_time=3,
                 output_filename="emoji_word.mp4"):
        """
        Generate a Guess the Word by Emoji video using fast FFmpeg piping.

        Args:
            puzzles: List of dicts with 'emojis', 'answer', optional 'hint', 'category'
            guess_time: Seconds to guess each puzzle
            answer_time: Seconds to show answer
            output_filename: Output file name
        """
        frames = []  # List of (PIL_Image, duration) tuples

        # Use sample puzzles if none provided
        if puzzles is None:
            puzzles = SAMPLE_EMOJI_PUZZLES

        # Intro
        intro_frame = self.create_title_frame("Guess the Word!", "From the Emojis")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        for puzzle_num, puzzle in enumerate(puzzles, 1):
            emojis = puzzle['emojis']
            answer = puzzle['answer']
            hint = puzzle.get('hint', None)
            category = puzzle.get('category', None)

            # Show category if provided
            if category:
                cat_frame = self.create_category_frame(category)
                frames.append((cat_frame, 2))

            # Puzzle number intro
            title_frame = self.create_title_frame(f"Puzzle {puzzle_num}",
                                                  "Guess the Word!")
            frames.append((title_frame, 1.5))

            # Puzzle with timer
            for sec in range(guess_time, 0, -1):
                puzzle_frame = self.create_puzzle_frame(
                    emojis, hint=hint,
                    title=f"Puzzle {puzzle_num}",
                    show_timer=sec
                )
                frames.append((puzzle_frame, 1))

            # Reveal answer
            answer_frame = self.create_puzzle_frame(
                emojis, hint=hint,
                title="Answer!",
                show_answer=answer
            )
            frames.append((answer_frame, answer_time))

        # Outro
        outro_frame = self.create_title_frame("Great Job!", "How many did you get?")
        frames.append((outro_frame, 3))

        # Use fast FFmpeg piping instead of MoviePy
        return self.save_video_fast(frames, output_filename)


# Sample emoji puzzles (REBUS style - emojis represent sounds/syllables)
SAMPLE_EMOJI_PUZZLES = [
    {
        'emojis': '🌧️ + 🎀',
        'answer': 'Rainbow',
        'hint': 'Colorful arc in the sky',
        'category': 'Nature'
    },
    {
        'emojis': '🧈 + 🪰',
        'answer': 'Butterfly',
        'hint': 'A colorful insect',
        'category': 'Animals'
    },
    {
        'emojis': '☀️ + 🌸',
        'answer': 'Sunflower',
        'hint': 'A tall yellow flower',
        'category': 'Plants'
    },
    {
        'emojis': '🔥 + 🐕',
        'answer': 'Hotdog',
        'hint': 'A popular fast food',
        'category': 'Food'
    },
    {
        'emojis': '🔑 + 🪵',
        'answer': 'Keyboard',
        'hint': 'Used for typing',
        'category': 'Technology'
    },
    {
        'emojis': '❄️ + ⚽',
        'answer': 'Snowball',
        'hint': 'Winter projectile',
        'category': 'Winter'
    },
    {
        'emojis': '🌲 + 🍎',
        'answer': 'Pineapple',
        'hint': 'A tropical fruit',
        'category': 'Food'
    },
    {
        'emojis': '👁️ + 🏝️',
        'answer': 'Island',
        'hint': 'Land surrounded by water',
        'category': 'Geography'
    },
    {
        'emojis': '⭐ + 🐟',
        'answer': 'Starfish',
        'hint': 'A sea creature',
        'category': 'Animals'
    },
    {
        'emojis': '💧 + 🍈',
        'answer': 'Watermelon',
        'hint': 'A large summer fruit',
        'category': 'Food'
    }
]
