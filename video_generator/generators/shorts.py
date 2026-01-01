"""YouTube Shorts Quiz Video Generator - Vertical format, 60 seconds max."""

from .base import BaseVideoGenerator
from PIL import ImageDraw, Image, ImageFilter
import random
import math
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor


# Global frame cache for reusable elements
_frame_cache = {}

# Available color themes
THEMES = {
    # Standard themes
    'purple': {
        'gradient_top': (75, 0, 130),      # Indigo
        'gradient_bottom': (238, 130, 238), # Violet
        'accent': (255, 215, 0),            # Gold
        'correct': (0, 255, 127),           # Spring green
    },
    'ocean': {
        'gradient_top': (0, 50, 100),       # Deep blue
        'gradient_bottom': (0, 150, 200),   # Cyan
        'accent': (255, 200, 50),           # Yellow
        'correct': (50, 255, 150),          # Mint
    },
    'sunset': {
        'gradient_top': (150, 50, 50),      # Dark red
        'gradient_bottom': (255, 150, 50),  # Orange
        'accent': (255, 255, 100),          # Light yellow
        'correct': (100, 255, 100),         # Green
    },
    'forest': {
        'gradient_top': (20, 60, 40),       # Dark green
        'gradient_bottom': (50, 150, 80),   # Forest green
        'accent': (255, 220, 100),          # Gold
        'correct': (150, 255, 150),         # Light green
    },
    'neon': {
        'gradient_top': (20, 0, 40),        # Dark purple
        'gradient_bottom': (60, 0, 80),     # Purple
        'accent': (0, 255, 255),            # Cyan
        'correct': (0, 255, 100),           # Neon green
    },
    'fire': {
        'gradient_top': (80, 20, 0),        # Dark red
        'gradient_bottom': (200, 80, 0),    # Orange
        'accent': (255, 255, 0),            # Yellow
        'correct': (100, 255, 50),          # Lime
    },
    # Seasonal themes
    'christmas': {
        'gradient_top': (139, 0, 0),        # Dark red
        'gradient_bottom': (0, 100, 0),     # Dark green
        'accent': (255, 215, 0),            # Gold
        'correct': (255, 255, 255),         # White (snow)
        'emoji': '🎄',
        'seasonal': True,
    },
    'halloween': {
        'gradient_top': (20, 0, 30),        # Very dark purple
        'gradient_bottom': (80, 40, 0),     # Dark orange
        'accent': (255, 140, 0),            # Orange
        'correct': (0, 255, 0),             # Spooky green
        'emoji': '🎃',
        'seasonal': True,
    },
    'valentine': {
        'gradient_top': (180, 20, 60),      # Deep pink
        'gradient_bottom': (255, 105, 180), # Hot pink
        'accent': (255, 255, 255),          # White
        'correct': (255, 182, 193),         # Light pink
        'emoji': '💕',
        'seasonal': True,
    },
    'summer': {
        'gradient_top': (0, 150, 255),      # Sky blue
        'gradient_bottom': (255, 220, 100), # Sandy yellow
        'accent': (255, 100, 50),           # Orange
        'correct': (50, 255, 200),          # Aqua
        'emoji': '☀️',
        'seasonal': True,
    },
    'winter': {
        'gradient_top': (30, 60, 100),      # Dark blue
        'gradient_bottom': (150, 200, 255), # Ice blue
        'accent': (255, 255, 255),          # White
        'correct': (200, 240, 255),         # Light ice
        'emoji': '❄️',
        'seasonal': True,
    },
    'spring': {
        'gradient_top': (100, 200, 100),    # Light green
        'gradient_bottom': (255, 200, 220), # Pink
        'accent': (255, 255, 100),          # Yellow
        'correct': (150, 255, 150),         # Light green
        'emoji': '🌸',
        'seasonal': True,
    },
    'autumn': {
        'gradient_top': (139, 69, 19),      # Saddle brown
        'gradient_bottom': (210, 105, 30),  # Chocolate
        'accent': (255, 200, 50),           # Gold
        'correct': (255, 165, 0),           # Orange
        'emoji': '🍂',
        'seasonal': True,
    },
    'newyear': {
        'gradient_top': (0, 0, 50),         # Midnight blue
        'gradient_bottom': (50, 0, 100),    # Dark purple
        'accent': (255, 215, 0),            # Gold
        'correct': (255, 255, 255),         # White sparkle
        'emoji': '🎆',
        'seasonal': True,
    },
    'stpatricks': {
        'gradient_top': (0, 80, 0),         # Dark green
        'gradient_bottom': (0, 150, 50),    # Shamrock green
        'accent': (255, 215, 0),            # Gold (pot of gold)
        'correct': (150, 255, 150),         # Light green
        'emoji': '🍀',
        'seasonal': True,
    },
    'easter': {
        'gradient_top': (200, 230, 255),    # Light blue
        'gradient_bottom': (255, 220, 255), # Light pink
        'accent': (255, 255, 100),          # Yellow
        'correct': (200, 255, 200),         # Light green
        'emoji': '🐰',
        'seasonal': True,
    },
    'independence': {
        'gradient_top': (0, 40, 104),       # USA blue
        'gradient_bottom': (191, 10, 48),   # USA red
        'accent': (255, 255, 255),          # White
        'correct': (255, 215, 0),           # Gold
        'emoji': '🇺🇸',
        'seasonal': True,
    },
    'thanksgiving': {
        'gradient_top': (139, 69, 19),      # Brown
        'gradient_bottom': (205, 133, 63),  # Peru
        'accent': (255, 140, 0),            # Dark orange
        'correct': (255, 200, 100),         # Light orange
        'emoji': '🦃',
        'seasonal': True,
    },
}

def get_seasonal_theme():
    """Get appropriate theme based on current date."""
    from datetime import datetime
    today = datetime.now()
    month, day = today.month, today.day

    # Check for specific holidays/seasons
    if month == 12 and day >= 15:
        return 'christmas'
    elif month == 1 and day <= 5:
        return 'newyear'
    elif month == 10 and day >= 20:
        return 'halloween'
    elif month == 2 and day >= 10 and day <= 14:
        return 'valentine'
    elif month == 3 and day >= 14 and day <= 17:
        return 'stpatricks'
    elif month == 4 and day >= 1 and day <= 20:
        return 'easter'
    elif month == 7 and day >= 1 and day <= 7:
        return 'independence'
    elif month == 11 and day >= 20 and day <= 28:
        return 'thanksgiving'
    # Seasons
    elif month in [6, 7, 8]:
        return 'summer'
    elif month in [3, 4, 5]:
        return 'spring'
    elif month in [9, 10, 11]:
        return 'autumn'
    elif month in [12, 1, 2]:
        return 'winter'
    return None


class ShortsGenerator(BaseVideoGenerator):
    """Generate YouTube Shorts quiz videos (vertical 9:16 format)."""

    def __init__(self, theme=None, use_seasonal=True, mode='standard', **kwargs):
        """
        Initialize Shorts generator.

        Args:
            theme: Color theme name (or None for random/seasonal)
            use_seasonal: Auto-select seasonal theme based on date
            mode: 'standard' or 'truefalse'
        """
        # Force vertical dimensions for Shorts
        kwargs['width'] = 1080
        kwargs['height'] = 1920
        super().__init__(**kwargs)

        self.mode = mode

        # Mode-specific settings
        if mode == 'truefalse':
            self.question_time = 8   # Slightly faster for binary choice
            self.answer_time = 4
            self.max_questions = 6
        else:  # standard
            self.question_time = 10  # Time to read question
            self.answer_time = 5     # Time to see answer
            self.max_questions = 5   # Keep it under 60 seconds

        # Theme selection priority:
        # 1. Explicit theme parameter
        # 2. Seasonal theme (if use_seasonal=True and it's a holiday)
        # 3. Random from all themes
        if theme is None:
            if use_seasonal:
                seasonal = get_seasonal_theme()
                if seasonal:
                    theme = seasonal
            if theme is None:
                # Prefer non-seasonal themes for random selection
                standard_themes = [k for k, v in THEMES.items() if not v.get('seasonal')]
                theme = random.choice(standard_themes if standard_themes else list(THEMES.keys()))

        self.theme_name = theme
        theme_colors = THEMES.get(theme, THEMES['purple'])
        self.theme_emoji = theme_colors.get('emoji', '🧠')
        self.is_seasonal = theme_colors.get('seasonal', False)

        self.bg_gradient_top = theme_colors['gradient_top']
        self.bg_gradient_bottom = theme_colors['gradient_bottom']
        self.text_color = (255, 255, 255)
        self.accent_color = theme_colors['accent']
        self.correct_color = theme_colors['correct']
        self.wrong_color = (255, 69, 0)  # Red-orange
        self.enable_transitions = True
        self.transition_frames = 6  # ~0.25 sec at 24fps

        # Animated background particles
        self.enable_animated_bg = True
        self.bg_particles = self._init_bg_particles(20)  # 20 floating particles

    def _init_bg_particles(self, count=20):
        """Initialize floating background particles."""
        particles = []
        for _ in range(count):
            particles.append({
                'x': random.randint(0, self.width),
                'y': random.randint(0, self.height),
                'size': random.randint(5, 20),
                'speed_x': random.uniform(-0.5, 0.5),
                'speed_y': random.uniform(-1, -0.2),  # Float upward
                'alpha': random.randint(30, 80),
                'color': random.choice([
                    self.accent_color,
                    self.correct_color,
                    (255, 255, 255),
                ])
            })
        return particles

    def _update_particles(self):
        """Update particle positions for animation."""
        for p in self.bg_particles:
            p['x'] += p['speed_x']
            p['y'] += p['speed_y']
            # Wrap around screen
            if p['y'] < -20:
                p['y'] = self.height + 20
                p['x'] = random.randint(0, self.width)
            if p['x'] < -20:
                p['x'] = self.width + 20
            elif p['x'] > self.width + 20:
                p['x'] = -20

    def _draw_bg_particles(self, frame):
        """Draw floating particles on frame."""
        if not self.enable_animated_bg:
            return frame

        draw = ImageDraw.Draw(frame, 'RGBA')
        for p in self.bg_particles:
            x, y = int(p['x']), int(p['y'])
            size = p['size']
            color = (*p['color'], p['alpha'])
            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)
        return frame

    def create_transition_frames(self, from_frame, to_frame, num_frames=6):
        """Create smooth transition frames between two images."""
        frames = []
        for i in range(num_frames):
            alpha = i / num_frames
            # Blend the two frames
            blended = Image.blend(from_frame, to_frame, alpha)
            frames.append((blended, 1.0 / self.fps))
        return frames

    def create_slide_transition(self, from_frame, to_frame, num_frames=6, direction='left'):
        """Create slide transition between frames."""
        frames = []
        for i in range(num_frames):
            progress = i / num_frames
            # Ease-out curve for smooth deceleration
            progress = 1 - (1 - progress) ** 2

            combined = Image.new('RGB', (self.width, self.height))

            if direction == 'left':
                offset = int(self.width * (1 - progress))
                combined.paste(from_frame, (-int(self.width * progress), 0))
                combined.paste(to_frame, (offset, 0))
            else:  # right
                offset = int(self.width * progress)
                combined.paste(from_frame, (offset, 0))
                combined.paste(to_frame, (offset - self.width, 0))

            frames.append((combined, 1.0 / self.fps))
        return frames

    def create_zoom_transition(self, from_frame, to_frame, num_frames=8):
        """Create zoom-out transition - old frame shrinks while new appears."""
        frames = []
        for i in range(num_frames):
            progress = i / num_frames
            # Ease-in-out curve
            progress = progress * progress * (3 - 2 * progress)

            combined = to_frame.copy()

            # Shrink the old frame
            scale = 1 - (progress * 0.5)
            new_size = (int(self.width * scale), int(self.height * scale))
            if new_size[0] > 0 and new_size[1] > 0:
                shrunk = from_frame.resize(new_size, Image.Resampling.LANCZOS)
                # Center it
                x = (self.width - new_size[0]) // 2
                y = (self.height - new_size[1]) // 2
                # Blend with transparency based on progress
                if progress < 0.8:
                    combined.paste(shrunk, (x, y))

            frames.append((combined, 1.0 / self.fps))
        return frames

    def create_wipe_transition(self, from_frame, to_frame, num_frames=8, direction='down'):
        """Create wipe transition - new frame wipes over old."""
        frames = []
        for i in range(num_frames):
            progress = i / num_frames
            # Ease-out curve
            progress = 1 - (1 - progress) ** 2

            combined = from_frame.copy()

            if direction == 'down':
                # Wipe from top to bottom
                cut_y = int(self.height * progress)
                if cut_y > 0:
                    region = to_frame.crop((0, 0, self.width, cut_y))
                    combined.paste(region, (0, 0))
            elif direction == 'up':
                # Wipe from bottom to top
                cut_y = int(self.height * (1 - progress))
                if cut_y < self.height:
                    region = to_frame.crop((0, cut_y, self.width, self.height))
                    combined.paste(region, (0, cut_y))
            elif direction == 'right':
                # Wipe from left to right
                cut_x = int(self.width * progress)
                if cut_x > 0:
                    region = to_frame.crop((0, 0, cut_x, self.height))
                    combined.paste(region, (0, 0))
            else:  # left
                # Wipe from right to left
                cut_x = int(self.width * (1 - progress))
                if cut_x < self.width:
                    region = to_frame.crop((cut_x, 0, self.width, self.height))
                    combined.paste(region, (cut_x, 0))

            frames.append((combined, 1.0 / self.fps))
        return frames

    def create_fade_transition(self, from_frame, to_frame, num_frames=6):
        """Create fade through black transition."""
        frames = []
        black = Image.new('RGB', (self.width, self.height), (0, 0, 0))

        # First half: fade to black
        for i in range(num_frames // 2):
            progress = i / (num_frames // 2)
            blended = Image.blend(from_frame, black, progress)
            frames.append((blended, 1.0 / self.fps))

        # Second half: fade from black to new frame
        for i in range(num_frames // 2):
            progress = i / (num_frames // 2)
            blended = Image.blend(black, to_frame, progress)
            frames.append((blended, 1.0 / self.fps))

        return frames

    def create_spin_transition(self, from_frame, to_frame, num_frames=10):
        """Create spinning zoom transition."""
        frames = []
        for i in range(num_frames):
            progress = i / num_frames
            # Ease-in-out
            progress = progress * progress * (3 - 2 * progress)

            if progress < 0.5:
                # First half: spin and shrink old frame
                scale = 1 - progress
                angle = progress * 180
                current = from_frame.copy()
            else:
                # Second half: unspin and grow new frame
                scale = progress
                angle = (1 - progress) * 180
                current = to_frame.copy()

            # Rotate and scale
            rotated = current.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
            new_size = (max(1, int(self.width * scale)), max(1, int(self.height * scale)))
            scaled = rotated.resize(new_size, Image.Resampling.LANCZOS)

            # Create combined frame with black background
            combined = Image.new('RGB', (self.width, self.height), (0, 0, 0))
            x = (self.width - new_size[0]) // 2
            y = (self.height - new_size[1]) // 2
            combined.paste(scaled, (x, y))

            frames.append((combined, 1.0 / self.fps))
        return frames

    def get_random_transition(self, from_frame, to_frame):
        """Get a random transition effect."""
        transitions = [
            lambda: self.create_slide_transition(from_frame, to_frame, 6, 'left'),
            lambda: self.create_zoom_transition(from_frame, to_frame, 8),
            lambda: self.create_wipe_transition(from_frame, to_frame, 8, 'down'),
            lambda: self.create_wipe_transition(from_frame, to_frame, 8, 'right'),
            lambda: self.create_fade_transition(from_frame, to_frame, 6),
            lambda: self.create_transition_frames(from_frame, to_frame, 6),  # Simple blend
        ]
        return random.choice(transitions)()

    def draw_circular_timer(self, draw, center_x, center_y, radius, progress, color):
        """Draw an animated circular timer."""
        import math
        # Background circle
        draw.ellipse(
            [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
            outline=(100, 100, 100), width=8
        )
        # Progress arc
        start_angle = -90  # Start from top
        end_angle = start_angle + (360 * progress)

        # Draw arc as segments
        segments = max(1, int(36 * progress))
        for i in range(segments):
            angle1 = math.radians(start_angle + (360 * progress * i / segments))
            angle2 = math.radians(start_angle + (360 * progress * (i + 1) / segments))
            x1 = center_x + radius * math.cos(angle1)
            y1 = center_y + radius * math.sin(angle1)
            x2 = center_x + radius * math.cos(angle2)
            y2 = center_y + radius * math.sin(angle2)
            draw.line([(x1, y1), (x2, y2)], fill=color, width=8)

    def create_particle_effect(self, frame, center_x, center_y, num_particles=20):
        """Add particle burst effect for correct answer."""
        import math
        draw = ImageDraw.Draw(frame)

        for i in range(num_particles):
            angle = (2 * math.pi * i) / num_particles
            distance = random.randint(50, 150)
            x = center_x + int(distance * math.cos(angle))
            y = center_y + int(distance * math.sin(angle))
            size = random.randint(5, 15)

            # Random bright colors
            colors = [self.accent_color, self.correct_color, (255, 255, 255), (255, 200, 0)]
            color = random.choice(colors)

            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)

        return frame

    def _create_gradient_background(self):
        """Create a vibrant gradient background (cached for performance)."""
        global _frame_cache

        # Cache key based on dimensions and colors
        cache_key = (self.width, self.height, self.bg_gradient_top, self.bg_gradient_bottom)

        if cache_key in _frame_cache:
            # Return a copy to avoid modifying cached image
            return _frame_cache[cache_key].copy()

        img = Image.new('RGB', (self.width, self.height))
        pixels = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        for y in range(self.height):
            ratio = y / self.height
            r = int(self.bg_gradient_top[0] * (1 - ratio) + self.bg_gradient_bottom[0] * ratio)
            g = int(self.bg_gradient_top[1] * (1 - ratio) + self.bg_gradient_bottom[1] * ratio)
            b = int(self.bg_gradient_top[2] * (1 - ratio) + self.bg_gradient_bottom[2] * ratio)
            pixels[y, :] = [r, g, b]

        bg = Image.fromarray(pixels, 'RGB')
        _frame_cache[cache_key] = bg
        return bg.copy()

    def create_question_frame(self, question_num, total_questions, question, options,
                              timer_seconds=None, highlight_answer=None, score=None, streak=None):
        """Create a Shorts-optimized quiz frame."""
        frame = self._create_gradient_background()

        # Add animated background particles
        if self.enable_animated_bg:
            self._update_particles()
            frame = self._draw_bg_particles(frame)

        draw = ImageDraw.Draw(frame)

        # Score counter in top-right corner
        if score is not None:
            score_x = self.width - 120
            score_y = 80
            # Score background
            draw.rounded_rectangle([score_x - 60, score_y - 35, score_x + 60, score_y + 35],
                                  radius=20, fill=(0, 0, 0, 150))
            self.add_text(frame, f"⭐ {score}", (score_x, score_y),
                         font=self._get_font(40), color=self.accent_color)

        # Streak counter (shows when streak >= 2)
        if streak is not None and streak >= 2:
            streak_x = self.width - 120
            streak_y = 160
            streak_color = (255, 100, 50) if streak >= 3 else (255, 200, 50)
            draw.rounded_rectangle([streak_x - 70, streak_y - 25, streak_x + 70, streak_y + 25],
                                  radius=15, fill=streak_color)
            self.add_text(frame, f"🔥 {streak} STREAK!", (streak_x, streak_y),
                         font=self._get_font(28), color=(0, 0, 0))

        # Question number badge at top
        badge_y = 100
        draw.ellipse([self.width//2 - 50, badge_y - 50,
                      self.width//2 + 50, badge_y + 50],
                     fill=self.accent_color)
        self.add_text(frame, f"{question_num}", (self.width // 2, badge_y),
                     font=self._get_font(60), color=(0, 0, 0))

        # Circular timer at top-left
        if timer_seconds is not None:
            progress = timer_seconds / self.question_time
            timer_color = self.correct_color if progress > 0.3 else self.wrong_color

            # Draw circular timer
            timer_x, timer_y = 100, 180
            timer_radius = 45
            self.draw_circular_timer(draw, timer_x, timer_y, timer_radius, progress, timer_color)

            # Timer number in center
            self.add_text(frame, str(timer_seconds), (timer_x, timer_y),
                         font=self._get_font(36), color=self.text_color)

        # Question text (larger, centered)
        question_y = 350
        self.add_text_wrapped(frame, question, (self.width // 2, question_y),
                             max_width=self.width - 100,
                             font=self._get_font(48),
                             color=self.text_color, line_spacing=15)

        # Answer options (stacked vertically, full width)
        options_start_y = 750
        box_height = 120
        box_gap = 25
        box_margin = 50

        option_labels = ['A', 'B', 'C', 'D']

        for i, option in enumerate(options[:4]):
            y = options_start_y + i * (box_height + box_gap)

            # Determine colors
            if highlight_answer is not None:
                if i == highlight_answer:
                    box_color = self.correct_color
                    text_col = (0, 0, 0)
                else:
                    box_color = (100, 100, 100)
                    text_col = (200, 200, 200)
            else:
                box_color = (255, 255, 255)
                text_col = (0, 0, 0)

            # Draw rounded option box
            draw.rounded_rectangle(
                [box_margin, y, self.width - box_margin, y + box_height],
                radius=20, fill=box_color
            )

            # Letter badge
            badge_size = 50
            badge_x = box_margin + 20
            badge_y = y + (box_height - badge_size) // 2
            draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
                        fill=self.accent_color if highlight_answer is None else box_color)
            self.add_text(frame, option_labels[i],
                         (badge_x + badge_size//2, badge_y + badge_size//2),
                         font=self._get_font(30),
                         color=(0, 0, 0) if highlight_answer is None else text_col)

            # Option text
            text_x = badge_x + badge_size + 20
            self.add_text(frame, option[:40],  # Truncate long options
                         (text_x, y + box_height // 2),
                         font=self._get_font(32), color=text_col, anchor='lm')

        # Subscribe reminder at bottom
        self.add_text(frame, "Follow for more!", (self.width // 2, self.height - 100),
                     font=self._get_font(36), color=self.accent_color)

        return frame

    def create_truefalse_frame(self, question_num, total_questions, question,
                                correct_answer, timer_seconds=None, show_answer=False, score=None):
        """Create a True/False question frame with large buttons."""
        frame = self._create_gradient_background()

        # Add animated background particles
        if self.enable_animated_bg:
            self._update_particles()
            frame = self._draw_bg_particles(frame)

        draw = ImageDraw.Draw(frame)

        # Score counter
        if score is not None:
            score_x = self.width - 120
            score_y = 80
            draw.rounded_rectangle([score_x - 60, score_y - 35, score_x + 60, score_y + 35],
                                  radius=20, fill=(0, 0, 0, 150))
            self.add_text(frame, f"⭐ {score}", (score_x, score_y),
                         font=self._get_font(40), color=self.accent_color)

        # Question number badge
        badge_y = 100
        draw.ellipse([self.width//2 - 50, badge_y - 50,
                      self.width//2 + 50, badge_y + 50],
                     fill=self.accent_color)
        self.add_text(frame, f"{question_num}", (self.width // 2, badge_y),
                     font=self._get_font(60), color=(0, 0, 0))

        # Timer
        if timer_seconds is not None:
            progress = timer_seconds / self.question_time
            timer_color = self.correct_color if progress > 0.3 else self.wrong_color
            timer_x, timer_y = 100, 180
            timer_radius = 45
            self.draw_circular_timer(draw, timer_x, timer_y, timer_radius, progress, timer_color)
            self.add_text(frame, str(timer_seconds), (timer_x, timer_y),
                         font=self._get_font(36), color=self.text_color)

        # Question text
        question_y = 400
        self.add_text_wrapped(frame, question, (self.width // 2, question_y),
                             max_width=self.width - 100,
                             font=self._get_font(52),
                             color=self.text_color, line_spacing=15)

        # Large TRUE/FALSE buttons
        btn_y_true = 900
        btn_y_false = 1150
        btn_margin = 80
        btn_height = 180
        btn_radius = 30

        # Determine colors based on answer reveal
        if show_answer:
            true_color = self.correct_color if correct_answer else (100, 100, 100)
            false_color = self.correct_color if not correct_answer else (100, 100, 100)
            true_text = (0, 0, 0) if correct_answer else (150, 150, 150)
            false_text = (0, 0, 0) if not correct_answer else (150, 150, 150)
        else:
            true_color = (50, 200, 50)  # Green
            false_color = (200, 50, 50)  # Red
            true_text = (255, 255, 255)
            false_text = (255, 255, 255)

        # TRUE button
        draw.rounded_rectangle(
            [btn_margin, btn_y_true, self.width - btn_margin, btn_y_true + btn_height],
            radius=btn_radius, fill=true_color
        )
        self.add_text(frame, "✓ TRUE", (self.width // 2, btn_y_true + btn_height // 2),
                     font=self._get_font(70), color=true_text)

        # FALSE button
        draw.rounded_rectangle(
            [btn_margin, btn_y_false, self.width - btn_margin, btn_y_false + btn_height],
            radius=btn_radius, fill=false_color
        )
        self.add_text(frame, "✗ FALSE", (self.width // 2, btn_y_false + btn_height // 2),
                     font=self._get_font(70), color=false_text)

        # Follow reminder
        self.add_text(frame, "Follow for more!", (self.width // 2, self.height - 100),
                     font=self._get_font(36), color=self.accent_color)

        return frame

    def create_intro_frame(self, num_questions, difficulty=None):
        """Create an eye-catching intro frame for Shorts."""
        frame = self._create_gradient_background()

        # Add animated background particles
        if self.enable_animated_bg:
            self._update_particles()
            frame = self._draw_bg_particles(frame)

        draw = ImageDraw.Draw(frame)

        # Mode badge at very top (for True/False mode)
        if self.mode == 'truefalse':
            draw.rounded_rectangle([self.width//2 - 180, 180, self.width//2 + 180, 250],
                                  radius=20, fill=(0, 150, 255))
            self.add_text(frame, '✓✗ TRUE/FALSE', (self.width // 2, 215),
                         font=self._get_font(38), color=(0, 0, 0))

        # Difficulty badge
        badge_y_offset = 80 if self.mode != 'standard' else 0
        if difficulty:
            diff_colors = {'easy': (50, 200, 50), 'medium': (255, 200, 0), 'hard': (255, 50, 50)}
            diff_labels = {'easy': 'EASY MODE', 'medium': 'MEDIUM', 'hard': 'HARD MODE'}
            diff_color = diff_colors.get(difficulty, (255, 200, 0))
            diff_label = diff_labels.get(difficulty, 'QUIZ')

            draw.rounded_rectangle([self.width//2 - 150, 250 + badge_y_offset, self.width//2 + 150, 320 + badge_y_offset],
                                  radius=20, fill=diff_color)
            self.add_text(frame, diff_label, (self.width // 2, 285 + badge_y_offset),
                         font=self._get_font(40), color=(0, 0, 0))

        # Big emoji (use theme emoji for seasonal themes)
        emoji_y = 450 + badge_y_offset if difficulty else 400 + badge_y_offset
        display_emoji = self.theme_emoji if self.is_seasonal else "🧠"
        self.add_text(frame, display_emoji, (self.width // 2, emoji_y),
                     font=self._get_font(200), color=self.text_color)

        # Title
        title = "TRUE or FALSE?" if self.mode == 'truefalse' else "QUIZ TIME!"
        self.add_text(frame, title, (self.width // 2, emoji_y + 300),
                     font=self._get_font(90), color=self.accent_color)

        # Subtitle
        self.add_text(frame, f"{num_questions} Questions", (self.width // 2, emoji_y + 450),
                     font=self._get_font(60), color=self.text_color)

        # CTA
        self.add_text(frame, "Can you get them all?", (self.width // 2, emoji_y + 600),
                     font=self._get_font(48), color=self.text_color)

        # Follow prompt
        self.add_text(frame, "👆 Follow for daily quizzes!", (self.width // 2, 1500),
                     font=self._get_font(40), color=self.accent_color)

        return frame

    def create_outro_frame(self, score_text="", animated=False, frame_num=0):
        """Create outro frame with CTA."""
        frame = self._create_gradient_background()

        # Add animated background particles
        if self.enable_animated_bg:
            self._update_particles()
            frame = self._draw_bg_particles(frame)

        draw = ImageDraw.Draw(frame)

        # Animated pulsing effect for the checkmark
        if animated:
            pulse = 1 + 0.1 * math.sin(frame_num * 0.3)
            font_size = int(200 * pulse)
        else:
            font_size = 200

        self.add_text(frame, "✅", (self.width // 2, 400),
                     font=self._get_font(font_size), color=self.text_color)

        self.add_text(frame, "Great Job!", (self.width // 2, 700),
                     font=self._get_font(80), color=self.accent_color)

        if score_text:
            self.add_text(frame, score_text, (self.width // 2, 850),
                         font=self._get_font(50), color=self.text_color)

        # Animated subscribe button
        if animated:
            # Pulsing red subscribe button
            btn_pulse = 1 + 0.05 * math.sin(frame_num * 0.5)
            btn_w = int(300 * btn_pulse)
            btn_h = int(80 * btn_pulse)
            btn_x = self.width // 2
            btn_y = 1050
            draw.rounded_rectangle(
                [btn_x - btn_w//2, btn_y - btn_h//2, btn_x + btn_w//2, btn_y + btn_h//2],
                radius=15, fill=(255, 0, 0)
            )
            self.add_text(frame, "SUBSCRIBE", (btn_x, btn_y),
                         font=self._get_font(40), color=(255, 255, 255))
        else:
            self.add_text(frame, "👆 FOLLOW", (self.width // 2, 1100),
                         font=self._get_font(70), color=self.accent_color)

        self.add_text(frame, "for more quizzes!", (self.width // 2, 1200),
                     font=self._get_font(50), color=self.text_color)

        self.add_text(frame, "💬 Comment your score!", (self.width // 2, 1400),
                     font=self._get_font(40), color=self.text_color)

        return frame

    def create_animated_outro(self, score_text="", duration=2.0):
        """Create animated outro with subscribe button animation."""
        frames = []
        num_frames = int(duration * self.fps)

        for i in range(num_frames):
            frame = self.create_outro_frame(score_text, animated=True, frame_num=i)
            frames.append((frame, 1.0 / self.fps))

        return frames

    def generate(self, questions, output_filename="quiz_short.mp4", enable_tts=True, difficulty=None):
        """Generate a YouTube Shorts quiz video (max 60 seconds)."""
        # Limit to max_questions for Shorts
        questions = questions[:self.max_questions]
        frames = []
        total_questions = len(questions)
        current_score = 0
        current_streak = 0  # Track consecutive correct answers (simulated)
        self.difficulty = difficulty

        diff_text = f", difficulty: {difficulty}" if difficulty else ""
        print(f"Generating Shorts video with {total_questions} questions (theme: {self.theme_name}{diff_text})...")

        # Quick intro (2 seconds)
        intro_frame = self.create_intro_frame(total_questions, difficulty)
        frames.append((intro_frame, 2))

        last_frame = intro_frame

        # Questions
        for q_num, q_data in enumerate(questions, 1):
            question = q_data.get('question', f'Question {q_num}')
            options = q_data.get('options', ['A', 'B', 'C', 'D'])
            answer_idx = q_data.get('answer', 0)

            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx >= len(options):
                answer_idx = 0

            # First frame of this question (for transition)
            first_question_frame = self.create_question_frame(
                q_num, total_questions, question, options,
                timer_seconds=self.question_time, score=current_score
            )

            # Add random transition from previous frame
            if self.enable_transitions and q_num > 1:
                transition_frames = self.get_random_transition(last_frame, first_question_frame)
                frames.extend(transition_frames)

            # Question with timer (show current score and streak)
            for sec in range(self.question_time, 0, -1):
                question_frame = self.create_question_frame(
                    q_num, total_questions, question, options,
                    timer_seconds=sec, score=current_score, streak=current_streak
                )
                frames.append((question_frame, 1))

            # Increment score and streak after each question (viewer assumed correct)
            current_score += 1
            current_streak += 1

            # Answer reveal with particle effect (show updated streak)
            answer_frame = self.create_question_frame(
                q_num, total_questions, question, options,
                highlight_answer=answer_idx, score=current_score, streak=current_streak
            )

            # Add particle burst on correct answer (animated over several frames)
            # Option box is at y = 850 + answer_idx * 145 approximately
            option_y = 890 + answer_idx * 145
            for particle_frame in range(3):
                frame_with_particles = answer_frame.copy()
                self.create_particle_effect(frame_with_particles, self.width // 2, option_y,
                                          num_particles=15 + particle_frame * 5)
                frames.append((frame_with_particles, 0.2))

            # Rest of answer time
            remaining_time = self.answer_time - 0.6
            frames.append((answer_frame, remaining_time))

            last_frame = answer_frame

        # Transition to animated outro
        outro_frame = self.create_outro_frame(f"Score: {current_score}/{total_questions}")
        if self.enable_transitions:
            transition_frames = self.create_transition_frames(last_frame, outro_frame, 6)
            frames.extend(transition_frames)

        # Use animated outro with pulsing subscribe button
        animated_outro = self.create_animated_outro(f"Score: {current_score}/{total_questions}", duration=2.0)
        frames.extend(animated_outro)

        print("Encoding Shorts video...")
        output_path = self.save_video_fast(frames, output_filename)

        # Add TTS if enabled
        if enable_tts:
            print("Adding TTS narration...")
            output_path = self._add_tts_audio(questions, output_path)

        print(f"Shorts video saved to: {output_path}")
        return output_path

    def _add_tts_audio(self, questions, video_path, enable_music=True, enable_sfx=True):
        """Add TTS narration, background music, and sound effects for Shorts."""
        import subprocess
        from sound_effects import SoundEffects, AudioEnhancements

        sfx = SoundEffects()
        audio_enhance = AudioEnhancements()
        ffmpeg_path = self._get_ffmpeg_path()
        temp_dir = '/tmp'

        tts_items = []
        tts_events = []
        sfx_events = []  # For sound effects

        current_time = 2  # After intro

        for q_num, q_data in enumerate(questions, 1):
            question = q_data.get('question', f'Question {q_num}')
            options = q_data.get('options', ['A', 'B', 'C', 'D'])
            answer_idx = q_data.get('answer', 0)
            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx >= len(options):
                answer_idx = 0
            answer_text = options[answer_idx]
            answer_letter = ['A', 'B', 'C', 'D'][min(answer_idx, 3)]

            # Question TTS
            tts_q = os.path.join(temp_dir, f'_shorts_q{q_num}.mp3')
            tts_items.append((question, tts_q))
            tts_events.append((current_time, tts_q))

            # Add timer tick sounds (every second, louder for last 3)
            if enable_sfx:
                for sec in range(self.question_time):
                    tick_time = current_time + sec
                    remaining = self.question_time - sec
                    if remaining <= 3:
                        sfx_events.append((tick_time, 'warning'))  # Urgent beep for last 3 sec
                    elif remaining <= 5:
                        sfx_events.append((tick_time, 'tick'))  # Normal tick

            current_time += self.question_time

            # Add correct sound effect at answer reveal
            if enable_sfx:
                sfx_events.append((current_time, 'correct'))
                # Add streak sound if this is question 2 or later (streak >= 2)
                if q_num >= 2:
                    sfx_events.append((current_time + 0.2, 'streak'))

            # Answer TTS
            tts_a = os.path.join(temp_dir, f'_shorts_a{q_num}.mp3')
            tts_items.append((f"{answer_letter}! {answer_text}", tts_a))
            tts_events.append((current_time + 0.3, tts_a))  # Slight delay after sfx

            current_time += self.answer_time

        # Generate TTS
        sfx.text_to_speech_batch(tts_items)

        if not tts_events:
            return video_path

        # Use enhanced audio mixing if music or sfx enabled
        if enable_music or enable_sfx:
            output_with_audio = video_path.replace('.mp4', '_with_audio.mp4')
            result = audio_enhance.mix_audio_with_music(
                video_path,
                tts_events,
                sfx_events=sfx_events if enable_sfx else None,
                music_volume=0.12,
                output_path=output_with_audio
            )

            # Cleanup TTS files
            for _, f in tts_events:
                try: os.remove(f)
                except: pass

            if result and os.path.exists(output_with_audio):
                os.replace(output_with_audio, video_path)
            return video_path

        # Fallback: original TTS-only mixing
        inputs = ['-i', video_path]
        filter_parts = []

        valid_events = [(i, t, f) for i, (t, f) in enumerate(tts_events) if os.path.exists(f)]

        for idx, (i, timestamp, audio_file) in enumerate(valid_events):
            inputs.extend(['-i', audio_file])
            delay_ms = int(timestamp * 1000)
            filter_parts.append(f'[{idx+1}]adelay={delay_ms}|{delay_ms},aformat=sample_rates=44100:channel_layouts=stereo[a{idx}]')

        if not filter_parts:
            return video_path

        mix_inputs = ''.join(f'[a{i}]' for i in range(len(valid_events)))
        filter_parts.append(f'{mix_inputs}amix=inputs={len(valid_events)}:normalize=0[aout]')

        filter_complex = ';'.join(filter_parts)
        output_with_audio = video_path.replace('.mp4', '_with_audio.mp4')

        cmd = [
            ffmpeg_path, '-y',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest',
            output_with_audio
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Cleanup
        for _, f in tts_events:
            try: os.remove(f)
            except: pass

        if result.returncode == 0 and os.path.exists(output_with_audio):
            os.replace(output_with_audio, video_path)

        return video_path

    def generate_thumbnail(self, question_text, output_path, category=None):
        """Generate an eye-catching, high-CTR thumbnail for Shorts."""
        import random

        # Vibrant color schemes - different from longform for variety
        color_schemes = [
            {"top": (255, 0, 80), "bottom": (150, 0, 50), "accent": (255, 255, 0), "glow": (255, 100, 150)},    # Hot Pink
            {"top": (0, 200, 255), "bottom": (0, 80, 150), "accent": (255, 255, 0), "glow": (100, 220, 255)},   # Cyan
            {"top": (255, 100, 0), "bottom": (180, 50, 0), "accent": (255, 255, 100), "glow": (255, 150, 50)},  # Orange
            {"top": (120, 0, 255), "bottom": (60, 0, 150), "accent": (0, 255, 255), "glow": (180, 100, 255)},   # Electric Purple
            {"top": (0, 255, 100), "bottom": (0, 150, 60), "accent": (255, 255, 0), "glow": (100, 255, 150)},   # Neon Green
            {"top": (255, 50, 50), "bottom": (150, 20, 20), "accent": (255, 215, 0), "glow": (255, 100, 100)},  # Red/Gold
        ]
        scheme = random.choice(color_schemes)

        # Category-specific emojis
        emoji_map = {
            "geography": ["🌍", "🗺️", "🌎", "🧭"],
            "science": ["🔬", "🧪", "⚗️", "🔭"],
            "history": ["📜", "⏳", "🏛️", "👑"],
            "sports": ["⚽", "🏆", "🎯", "🏀"],
            "movies": ["🎬", "🎥", "🍿", "🌟"],
            "music": ["🎵", "🎸", "🎤", "🎹"],
            "food": ["🍕", "🍔", "🍳", "🍰"],
            "animals": ["🦁", "🐘", "🦊", "🐬"],
            "riddles": ["🤔", "💭", "🔮", "✨"],
        }
        default_emojis = ["🧠", "❓", "💡", "🤯", "⚡", "🔥"]

        if category and category.lower() in emoji_map:
            emoji = random.choice(emoji_map[category.lower()])
        else:
            emoji = random.choice(default_emojis)

        # Clickbait variations for Shorts
        hooks = [
            ("Only 1% Get", "ALL 5 RIGHT! 😱"),
            ("IMPOSSIBLE", "Quiz Challenge! 🔥"),
            ("Are You A", "GENIUS? 🧠"),
            ("99% FAIL", "This Quiz! 💀"),
            ("Can You", "BEAT THIS? ⚡"),
            ("Test Your", "IQ NOW! 🎯"),
        ]
        hook_top, hook_bottom = random.choice(hooks)

        # Create gradient background
        pixels = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        for y in range(self.height):
            ratio = y / self.height
            r = int(scheme["top"][0] * (1 - ratio) + scheme["bottom"][0] * ratio)
            g = int(scheme["top"][1] * (1 - ratio) + scheme["bottom"][1] * ratio)
            b = int(scheme["top"][2] * (1 - ratio) + scheme["bottom"][2] * ratio)
            pixels[y, :] = [r, g, b]

        frame = Image.fromarray(pixels, 'RGB')
        draw = ImageDraw.Draw(frame)

        # Dynamic background elements - zigzag pattern
        for i in range(0, self.height, 200):
            points = []
            for x in range(0, self.width + 100, 100):
                y_offset = 50 if (x // 100) % 2 == 0 else -50
                points.append((x, i + y_offset))
            if len(points) >= 2:
                draw.line(points, fill=scheme["glow"], width=3)

        # Glowing border with multiple layers
        for i, width in enumerate([12, 8, 4]):
            alpha_color = tuple(min(255, c + i * 30) for c in scheme["accent"])
            draw.rectangle([15 - i*3, 15 - i*3, self.width - 15 + i*3, self.height - 15 + i*3],
                          outline=alpha_color, width=width)

        # Starburst behind emoji
        center_x, center_y = self.width // 2, 380
        for angle in range(0, 360, 30):
            import math
            end_x = center_x + int(250 * math.cos(math.radians(angle)))
            end_y = center_y + int(250 * math.sin(math.radians(angle)))
            draw.line([(center_x, center_y), (end_x, end_y)], fill=scheme["glow"], width=8)

        # Big emoji with glow
        for offset in range(20, 0, -5):
            self.add_text(frame, emoji, (self.width // 2, 380),
                         font=self._get_font(300 + offset), color=scheme["glow"])
        self.add_text(frame, emoji, (self.width // 2, 380),
                     font=self._get_font(300), color=(255, 255, 255))

        # "QUIZ" text with heavy outline
        quiz_y = 750
        for dx in range(-6, 7, 2):
            for dy in range(-6, 7, 2):
                self.add_text(frame, "QUIZ", (self.width // 2 + dx, quiz_y + dy),
                             font=self._get_font(160), color=(0, 0, 0))
        self.add_text(frame, "QUIZ", (self.width // 2, quiz_y),
                     font=self._get_font(160), color=scheme["accent"])

        # Hook text - top line
        hook_font_top = self._get_font(75)
        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
            self.add_text(frame, hook_top, (self.width // 2 + dx, 960 + dy),
                         font=hook_font_top, color=(0, 0, 0))
        self.add_text(frame, hook_top, (self.width // 2, 960),
                     font=hook_font_top, color=(255, 255, 255))

        # Hook text - bottom line (bigger, more impactful)
        hook_font_bottom = self._get_font(85)
        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
            self.add_text(frame, hook_bottom, (self.width // 2 + dx, 1060 + dy),
                         font=hook_font_bottom, color=(0, 0, 0))
        self.add_text(frame, hook_bottom, (self.width // 2, 1060),
                     font=hook_font_bottom, color=scheme["accent"])

        # Question preview box with glow
        preview = question_text[:35] + "...?" if len(question_text) > 35 else question_text
        box_y = 1220
        # Glow effect for box
        for expand in range(10, 0, -2):
            draw.rounded_rectangle([60 - expand, box_y - 60 - expand,
                                   self.width - 60 + expand, box_y + 70 + expand],
                                  radius=30, outline=scheme["glow"])
        draw.rounded_rectangle([60, box_y - 60, self.width - 60, box_y + 70],
                              radius=30, fill=(0, 0, 0))
        self.add_text_wrapped(frame, preview, (self.width // 2, box_y + 5),
                             max_width=self.width - 160,
                             font=self._get_font(42), color=(255, 255, 255))

        # CTA button at bottom
        cta_y = 1420
        ctas = ["▶ SWIPE UP!", "⚡ PLAY NOW!", "🎯 TAP TO START!"]
        cta = random.choice(ctas)
        draw.rounded_rectangle([150, cta_y - 40, self.width - 150, cta_y + 50],
                              radius=45, fill=scheme["accent"])
        self.add_text(frame, cta, (self.width // 2, cta_y + 5),
                     font=self._get_font(50), color=(0, 0, 0))

        # Corner badges
        draw.polygon([(0, 0), (200, 0), (0, 200)], fill=scheme["accent"])
        self.add_text(frame, "NEW", (60, 60),
                     font=self._get_font(40), color=(0, 0, 0))

        frame.save(output_path, quality=95)
        return output_path
