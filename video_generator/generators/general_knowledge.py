"""General Knowledge Quiz Video Generator."""

from .base import BaseVideoGenerator
from PIL import ImageDraw, Image
import random
import math
import numpy as np


class GeneralKnowledgeGenerator(BaseVideoGenerator):
    """Generate General Knowledge quiz videos."""

    def __init__(self, question_time=5, answer_time=3, **kwargs):
        super().__init__(**kwargs)
        self.question_time = question_time  # seconds to show question
        self.answer_time = answer_time      # seconds to show answer
        self.countdown_time = 1  # seconds per countdown number

        # Scale factor for 4K support (base is 1080p)
        self.scale = self.width / 1920

        # Re-init fonts with scaled sizes for 4K
        if self.scale > 1:
            self.font_large = self._get_font(int(80 * self.scale))
            self.font_medium = self._get_font(int(50 * self.scale))
            self.font_small = self._get_font(int(35 * self.scale))

        # Professional color scheme
        self.header_color = (41, 98, 168)  # Blue header
        self.content_bg = (198, 217, 237)  # Light blue background
        self.question_color = (30, 60, 100)  # Dark blue text
        self.answer_box_color = (255, 255, 255)  # White answer boxes
        self.letter_badge_color = (41, 98, 168)  # Blue badges
        self.border_color = (100, 140, 180)  # Dotted border color

        # Pre-generate spiral background
        self._spiral_bg = None

    def _create_spiral_background(self):
        """Create a spiral pattern background (optimized with numpy)."""
        if self._spiral_bg is not None:
            return self._spiral_bg

        # Create coordinate grids
        y_coords, x_coords = np.mgrid[0:self.height, 0:self.width]
        cx, cy = self.width // 2, self.height // 2

        # Calculate distance and angle from center
        dx = x_coords - cx
        dy = y_coords - cy
        dist = np.sqrt(dx**2 + dy**2)
        angle = np.arctan2(dy, dx)

        # Spiral pattern
        spiral = (angle + dist * 0.02) % (math.pi / 4)

        # Create color arrays
        pixels = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Mask for alternating colors
        light_mask = spiral < (math.pi / 8)

        # Base colors
        pixels[light_mask] = [180, 210, 240]  # Lighter blue
        pixels[~light_mask] = [160, 195, 230]  # Darker blue

        # Add radial gradient (darker at edges)
        max_dist = max(self.width, self.height) * 0.6
        fade = np.clip(dist / max_dist, 0, 1) * 0.2
        fade_3d = np.stack([fade, fade, fade], axis=2)

        pixels = (pixels * (1 - fade_3d)).astype(np.uint8)

        img = Image.fromarray(pixels, 'RGB')
        self._spiral_bg = img
        return img

    def create_question_frame(self, question_num, total_questions, question, options,
                              timer_seconds=None, highlight_answer=None,
                              slide_progress=1.0, question_alpha=1.0):
        """
        Create a professional quiz frame with animations.

        Args:
            slide_progress: 0.0 to 1.0 - how far options have slid in (for animation)
            question_alpha: 0.0 to 1.0 - question text fade in
        """
        # Spiral background
        frame = self._create_spiral_background().copy()
        draw = ImageDraw.Draw(frame)
        s = self.scale  # Shorthand for scaling

        # === HEADER BAR ===
        header_height = int(90 * s)
        draw.rectangle([0, 0, self.width, header_height], fill=self.header_color)

        # Question number on left (with proper margins)
        text_y = int(50 * s)  # Lower than center to avoid top crop
        self.add_text(frame, f"Question {question_num}/{total_questions}",
                     (int(50 * s), text_y),
                     font=self.font_medium, color=(255, 255, 255), anchor='lm')

        # Timer circle in header (right side)
        if timer_seconds is not None:
            timer_x = self.width - int(150 * s)
            timer_y = text_y
            # Timer background circle
            timer_radius = int(30 * s)
            draw.ellipse([timer_x - timer_radius, timer_y - timer_radius,
                         timer_x + timer_radius, timer_y + timer_radius],
                        fill=(30, 70, 130))
            # Draw arc for timer progress
            if self.question_time > 0:
                progress = timer_seconds / self.question_time
                start_angle = -90
                end_angle = start_angle + (360 * progress)
                draw.arc([timer_x - timer_radius - int(5 * s), timer_y - timer_radius - int(5 * s),
                         timer_x + timer_radius + int(5 * s), timer_y + timer_radius + int(5 * s)],
                        start_angle, end_angle, fill=(255, 255, 255), width=int(4 * s))
            self.add_text(frame, str(timer_seconds), (timer_x, timer_y),
                         font=self.font_medium, color=(255, 255, 255))

        # === CONTENT AREA WITH DOTTED BORDER ===
        content_margin = int(40 * s)
        content_top = header_height + int(20 * s)
        content_bottom = self.height - int(70 * s)  # Leave room for progress bar

        # Draw dotted border
        self._draw_dotted_rectangle(draw,
                                    content_margin, content_top,
                                    self.width - content_margin, content_bottom,
                                    self.border_color, dot_spacing=int(8 * s))

        # === QUESTION TEXT ===
        question_y = content_top + int(80 * s)
        max_question_width = self.width - int(200 * s)

        # Use smaller font for long questions to prevent overlap
        question_font = self.font_large
        if len(question) > 100:
            question_font = self.font_medium
        if len(question) > 180:
            question_font = self.font_small

        # Calculate question text height to position options below it
        question_bbox = self.add_text_wrapped(frame, question, (self.width // 2, question_y),
                             max_width=max_question_width, font=question_font,
                             color=self.question_color)

        # Get the bottom of the question text (add_text_wrapped returns bbox)
        question_bottom = question_y + int(120 * s)  # Default estimate
        if question_bbox:
            # question_bbox is (x1, y1, x2, y2)
            question_bottom = question_bbox[3] + int(40 * s)  # Add padding below question

        # === VERTICAL 1x4 ANSWER LIST ===
        # Position options below question text, with minimum position
        min_options_y = content_top + int(280 * s)
        options_start_y = max(min_options_y, question_bottom)
        box_margin = int(150 * s)  # Left/right margin
        box_width = self.width - box_margin * 2
        box_height = int(85 * s)
        box_gap = int(20 * s)

        option_labels = ['A', 'B', 'C', 'D']

        for i, option in enumerate(options[:4]):
            # Animation: each option slides in with delay
            option_delay = i * 0.15  # Stagger the animations
            option_progress = max(0, min(1, (slide_progress - option_delay) / 0.3))

            # Slide from right
            slide_offset = int((1 - option_progress) * 400 * s)

            x = box_margin + slide_offset
            y = options_start_y + i * (box_height + box_gap)

            # Determine colors based on highlight
            if highlight_answer is not None:
                if i == highlight_answer:
                    box_color = (180, 255, 180)  # Light green for correct
                    badge_color = (50, 180, 50)  # Green badge
                    border = (50, 180, 50)
                    border_width = int(4 * s)
                else:
                    box_color = (255, 200, 200)  # Light red for wrong
                    badge_color = (200, 80, 80)  # Red badge
                    border = (200, 80, 80)
                    border_width = int(2 * s)
            else:
                box_color = self.answer_box_color
                badge_color = self.letter_badge_color
                border = (180, 180, 180)
                border_width = int(2 * s)

            # Only draw if visible (slid in enough)
            if option_progress > 0:
                # Answer box with rounded corners
                self._draw_rounded_rect(draw, x, y, x + box_width - slide_offset, y + box_height,
                                       radius=int(15 * s), fill=box_color, outline=border, width=border_width)

                # Letter badge (square with rounded corners)
                badge_size = int(55 * s)
                badge_x = x + int(15 * s)
                badge_y = y + (box_height - badge_size) // 2
                self._draw_rounded_rect(draw, badge_x, badge_y,
                                       badge_x + badge_size, badge_y + badge_size,
                                       radius=int(10 * s), fill=badge_color)

                # Letter in badge
                self.add_text(frame, option_labels[i],
                         (badge_x + badge_size // 2, badge_y + badge_size // 2),
                         font=self.font_medium, color=(255, 255, 255))

                # Option text
                text_x = badge_x + badge_size + int(20 * s)
                self.add_text(frame, option,
                             (text_x, y + box_height // 2),
                             font=self.font_small, color=self.question_color, anchor='lm')

        # === BOTTOM PROGRESS BAR ===
        if timer_seconds is not None and self.question_time > 0:
            bar_height = int(15 * s)
            bar_margin = int(60 * s)
            bar_y = self.height - int(55 * s)
            total_bar_width = self.width - bar_margin * 2

            # Background bar (dark gray track)
            draw.rectangle([bar_margin, bar_y, self.width - bar_margin, bar_y + bar_height],
                          fill=(60, 60, 80), outline=(100, 100, 120))

            # Progress bar fills from left to right as time passes
            time_passed = self.question_time - timer_seconds
            progress = time_passed / self.question_time
            filled_width = int(total_bar_width * progress)

            if filled_width > 0:
                # Entire bar changes color based on progress
                if progress < 0.5:
                    bar_color = (80, 200, 80)  # Green
                elif progress < 0.8:
                    bar_color = (240, 200, 60)  # Yellow
                else:
                    bar_color = (240, 80, 80)  # Red

                draw.rectangle([bar_margin, bar_y, bar_margin + filled_width, bar_y + bar_height],
                              fill=bar_color)

        return frame

    def _draw_dotted_rectangle(self, draw, x1, y1, x2, y2, color, dot_spacing=10):
        """Draw a dotted rectangle border."""
        dot_size = int(3 * self.scale)
        # Top edge
        for x in range(int(x1), int(x2), dot_spacing):
            draw.rectangle([x, y1, x + dot_size, y1 + dot_size], fill=color)
        # Bottom edge
        for x in range(int(x1), int(x2), dot_spacing):
            draw.rectangle([x, y2 - dot_size, x + dot_size, y2], fill=color)
        # Left edge
        for y in range(int(y1), int(y2), dot_spacing):
            draw.rectangle([x1, y, x1 + dot_size, y + dot_size], fill=color)
        # Right edge
        for y in range(int(y1), int(y2), dot_spacing):
            draw.rectangle([x2 - dot_size, y, x2, y + dot_size], fill=color)

    def _draw_rounded_rect(self, draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=1):
        """Draw a rounded rectangle."""
        # Draw the main rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

        # Draw the corners
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

        # Draw outline if specified
        if outline:
            draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=width)
            draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=width)
            draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
            draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
            draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
            draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)

    def generate(self, questions, output_filename="general_knowledge.mp4", enable_tts=True):
        """
        Generate a general knowledge quiz video.

        Args:
            questions: List of dicts with 'question', 'options', 'answer' (index)
            output_filename: Output file name
            enable_tts: Enable text-to-speech narration
        """
        import os
        import subprocess

        frames = []
        total_questions = len(questions)

        print("Generating frames...")

        # Intro
        intro_frame = self.create_title_frame("General Knowledge Quiz",
                                              f"{total_questions} Questions - Test Your Knowledge!")
        frames.append((intro_frame, 3))

        # Countdown (3, 2, 1)
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        # Questions
        for q_num, q_data in enumerate(questions, 1):
            print(f"  Question {q_num}/{total_questions}")
            question = q_data.get('question', f'Question {q_num}')
            options = q_data.get('options', ['A', 'B', 'C', 'D'])
            answer_idx = q_data.get('answer', 0)
            # Validate answer index
            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx >= len(options):
                answer_idx = 0

            # === SLIDE-IN ANIMATION ===
            animation_fps = 8
            frames_per_step = 1.0 / 16  # Quick animation

            for anim_frame in range(animation_fps):
                slide_progress = (anim_frame + 1) / animation_fps
                anim_question_frame = self.create_question_frame(
                    q_num, total_questions, question, options,
                    timer_seconds=self.question_time,
                    slide_progress=slide_progress
                )
                frames.append((anim_question_frame, frames_per_step))

            # Question frames with timer countdown
            for sec in range(self.question_time, 0, -1):
                question_frame = self.create_question_frame(
                    q_num, total_questions, question, options,
                    timer_seconds=sec,
                    slide_progress=1.0
                )
                frames.append((question_frame, 1))

            # === ANSWER REVEAL ===
            answer_frame = self.create_question_frame(
                q_num, total_questions, question, options,
                timer_seconds=None, highlight_answer=answer_idx
            )
            frames.append((answer_frame, self.answer_time))

        # Outro
        outro_frame = self.create_title_frame("Thanks for Playing!",
                                              "Subscribe for more quizzes!")
        frames.append((outro_frame, 3))

        print("Encoding video...")
        # Save video
        output_path = self.save_video_fast(frames, output_filename)

        # Add TTS if enabled
        if enable_tts:
            print("Adding TTS narration...")
            output_path = self._add_tts_audio(questions, output_path)

        print(f"Video saved to: {output_path}")
        return output_path

    def _get_audio_duration(self, audio_file, ffmpeg_path):
        """Get duration of audio file in seconds."""
        return self._get_media_duration(audio_file, ffmpeg_path, default=2.0)

    def _get_video_duration(self, video_file, ffmpeg_path):
        """Get duration of video file in seconds."""
        return self._get_media_duration(video_file, ffmpeg_path, default=300.0)

    def _get_media_duration(self, file_path, ffmpeg_path, default=2.0):
        """Get duration of media file in seconds."""
        import subprocess
        cmd = [
            ffmpeg_path, '-i', file_path, '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        for line in result.stderr.split('\n'):
            if 'Duration:' in line:
                import re
                match = re.search(r'Duration: (\d+):(\d+):(\d+\.?\d*)', line)
                if match:
                    h, m, s = match.groups()
                    return int(h) * 3600 + int(m) * 60 + float(s)
        return default

    def _add_tts_audio(self, questions, video_path):
        """Add TTS narration using parallel generation and fast mixing."""
        import os
        import subprocess
        from sound_effects import SoundEffects

        sfx = SoundEffects()
        ffmpeg_path = self._get_ffmpeg_path()
        temp_dir = '/tmp'

        print("  Preparing TTS generation...")

        # Build list of all TTS items to generate in parallel
        tts_items = []  # (text, output_path)
        tts_events = []  # (timestamp, output_path)

        # Countdown TTS at timestamps 3, 4, 5 seconds (after 3s intro)
        for i, num in enumerate([3, 2, 1]):
            tts_file = os.path.join(temp_dir, f'_countdown_{num}.mp3')
            tts_items.append((str(num), tts_file))
            timestamp = 3 + i  # 3s intro, then 3, 2, 1
            tts_events.append((timestamp, tts_file))

        # Questions and answers
        anim_duration = 0.5  # Quick slide-in animation
        current_time = 6 + anim_duration  # After intro (3s) + countdown (3s) + animation

        for q_num, q_data in enumerate(questions, 1):
            question = q_data.get('question', f'Question {q_num}')
            options = q_data.get('options', ['A', 'B', 'C', 'D'])
            answer_idx = q_data.get('answer', 0)
            # Validate answer index to prevent crashes
            if not isinstance(answer_idx, int) or answer_idx < 0 or answer_idx >= len(options):
                answer_idx = 0
            answer_text = options[answer_idx] if options else 'Unknown'
            answer_letter = ['A', 'B', 'C', 'D'][min(answer_idx, 3)]

            # TTS for question
            tts_q = os.path.join(temp_dir, f'_tts_q{q_num}.mp3')
            tts_items.append((question, tts_q))
            tts_events.append((current_time, tts_q))

            # Move to answer reveal time
            current_time += self.question_time + anim_duration

            # TTS for answer
            tts_a = os.path.join(temp_dir, f'_tts_a{q_num}.mp3')
            tts_items.append((f"The answer is {answer_letter}, {answer_text}", tts_a))
            tts_events.append((current_time, tts_a))

            current_time += self.answer_time

        # Generate all TTS files in parallel
        sfx.text_to_speech_batch(tts_items)

        if not tts_events:
            return video_path

        print("  Building audio track...")

        # Use FFmpeg's adelay filter - single command for all TTS positioning
        # This is faster than concat with silence files
        inputs = ['-i', video_path]
        filter_parts = []

        # Add all TTS files as inputs
        valid_events = [(i, t, f) for i, (t, f) in enumerate(tts_events) if os.path.exists(f)]

        for idx, (i, timestamp, audio_file) in enumerate(valid_events):
            inputs.extend(['-i', audio_file])
            delay_ms = int(timestamp * 1000)
            # Input index is idx+1 (0 is video)
            filter_parts.append(f'[{idx+1}]adelay={delay_ms}|{delay_ms},aformat=sample_rates=44100:channel_layouts=stereo[a{idx}]')

        if not filter_parts:
            return video_path

        # Mix all delayed audio streams
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

        print(f"  Mixing {len(valid_events)} audio tracks...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        # Cleanup TTS temp files
        for _, f in tts_events:
            try: os.remove(f)
            except: pass

        if result.returncode == 0 and os.path.exists(output_with_audio):
            os.replace(output_with_audio, video_path)
            return video_path
        else:
            print(f"  TTS audio failed: {result.stderr[:200] if result.stderr else 'unknown error'}")
            return video_path


# Sample questions for testing
SAMPLE_QUESTIONS = [
    {
        "question": "What is the capital of France?",
        "options": ["London", "Berlin", "Paris", "Madrid"],
        "answer": 2
    },
    {
        "question": "Which planet is known as the 'Red Planet'?",
        "options": ["Uranus", "Saturn", "Mars", "Jupiter"],
        "answer": 2
    },
    {
        "question": "What is the largest ocean on Earth?",
        "options": ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Pacific Ocean"],
        "answer": 3
    },
    {
        "question": "Who painted the Mona Lisa?",
        "options": ["Vincent van Gogh", "Pablo Picasso", "Leonardo da Vinci", "Michelangelo"],
        "answer": 2
    },
    {
        "question": "What is the chemical symbol for silver?",
        "options": ["Ag", "Si", "Au", "H"],
        "answer": 0
    }
]
