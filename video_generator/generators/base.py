"""Base video generator class with common functionality."""

import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Cache for system info
_system_info = None


def get_system_info():
    """Detect system capabilities (cached)."""
    global _system_info
    if _system_info is not None:
        return _system_info

    import multiprocessing

    info = {
        'cpu_cores': multiprocessing.cpu_count(),
        'gpu_capable': False,
        'gpu_name': None,
        'gpu_vram_mb': 0,
        'nvenc_capable': False,
    }

    # Detect NVIDIA GPU
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            # Find the best GPU (most VRAM, skip old cards like K2200)
            best_gpu = None
            best_vram = 0
            for line in lines:
                parts = line.split(', ')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    vram = int(parts[1].strip())
                    # Use any GPU with 2GB+ VRAM for NVENC
                    if vram >= 2000 and vram > best_vram:
                        best_gpu = name
                        best_vram = vram

            if best_gpu:
                info['gpu_capable'] = True
                info['gpu_name'] = best_gpu
                info['gpu_vram_mb'] = best_vram
                # NVENC capable if GPU has 2GB+ VRAM
                info['nvenc_capable'] = best_vram >= 2000
    except:
        pass

    _system_info = info
    return info


class BaseVideoGenerator:
    """Base class for all video generators."""

    def __init__(self, width=1920, height=1080, fps=24):
        """
        Initialize the video generator.

        Args:
            width: Video width in pixels (default 1920 for landscape)
            height: Video height in pixels (default 1080 for landscape)
            fps: Frames per second
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')

        # Colors
        self.bg_color = (25, 25, 35)
        self.text_color = (255, 255, 255)
        self.accent_color = (100, 200, 255)
        self.correct_color = (100, 255, 100)
        self.wrong_color = (255, 100, 100)

        # Try to load a font, fallback to default
        self.font_large = self._get_font(80)
        self.font_medium = self._get_font(50)
        self.font_small = self._get_font(35)
        self.font_emoji = self._get_font(120)

        # FFmpeg path (use bundled one from imageio_ffmpeg)
        self._ffmpeg_path = None

        # System info
        self._system_info = None

    def _get_system_info(self):
        """Get cached system info."""
        if self._system_info is None:
            self._system_info = get_system_info()
        return self._system_info

    def _get_ffmpeg_path(self):
        """Get ffmpeg binary path. Prefers system ffmpeg for NVENC support."""
        if self._ffmpeg_path is None:
            import subprocess
            import shutil
            # Prefer system ffmpeg (has NVENC support)
            system_ffmpeg = shutil.which('ffmpeg')
            if system_ffmpeg:
                try:
                    result = subprocess.run([system_ffmpeg, '-encoders'], capture_output=True, text=True, timeout=5)
                    if 'h264_nvenc' in result.stdout:
                        self._ffmpeg_path = system_ffmpeg
                        return self._ffmpeg_path
                except:
                    pass
            # Fall back to bundled ffmpeg
            try:
                import imageio_ffmpeg
                self._ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                self._ffmpeg_path = system_ffmpeg or 'ffmpeg'
        return self._ffmpeg_path

    def _get_font(self, size):
        """Get a font at the specified size."""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        ]

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue

        # Fallback to default font
        return ImageFont.load_default()

    def _get_emoji_font(self, size):
        """Get emoji font specifically."""
        emoji_paths = [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        for path in emoji_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
        return self._get_font(size)

    def create_frame(self, bg_color=None):
        """Create a blank frame with background color."""
        if bg_color is None:
            bg_color = self.bg_color
        return Image.new('RGB', (self.width, self.height), bg_color)

    def add_text(self, img, text, position, font=None, color=None, anchor='mm'):
        """Add text to an image."""
        if font is None:
            font = self.font_medium
        if color is None:
            color = self.text_color

        draw = ImageDraw.Draw(img)
        draw.text(position, text, font=font, fill=color, anchor=anchor)
        return img

    def add_text_wrapped(self, img, text, position, max_width, font=None, color=None, line_spacing=10):
        """Add wrapped text to an image."""
        if font is None:
            font = self.font_medium
        if color is None:
            color = self.text_color

        draw = ImageDraw.Draw(img)

        # Word wrap
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        # Draw lines
        x, y = position
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            draw.text((x - line_width // 2, y), line, font=font, fill=color)
            y += line_height + line_spacing

        return img

    def add_rounded_rectangle(self, img, bbox, radius, fill_color, outline_color=None, outline_width=3):
        """Add a rounded rectangle to an image."""
        draw = ImageDraw.Draw(img)
        x1, y1, x2, y2 = bbox

        draw.rounded_rectangle(bbox, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
        return img

    def add_circle(self, img, center, radius, fill_color, outline_color=None, outline_width=3):
        """Add a circle to an image."""
        draw = ImageDraw.Draw(img)
        x, y = center
        bbox = (x - radius, y - radius, x + radius, y + radius)
        draw.ellipse(bbox, fill=fill_color, outline=outline_color, width=outline_width)
        return img

    def create_countdown_frame(self, number, text=""):
        """Create a countdown frame."""
        frame = self.create_frame()

        # Add number
        self.add_text(frame, str(number), (self.width // 2, self.height // 2 - 50),
                     font=self._get_font(200), color=self.accent_color)

        if text:
            self.add_text(frame, text, (self.width // 2, self.height // 2 + 150),
                         font=self.font_medium, color=self.text_color)

        return frame

    def create_title_frame(self, title, subtitle=""):
        """Create a title frame."""
        frame = self.create_frame()

        self.add_text(frame, title, (self.width // 2, self.height // 2 - 50),
                     font=self.font_large, color=self.accent_color)

        if subtitle:
            self.add_text(frame, subtitle, (self.width // 2, self.height // 2 + 100),
                         font=self.font_medium, color=self.text_color)

        return frame

    def _has_nvenc(self, ffmpeg_path):
        """Check if NVENC hardware encoding is available and we have a capable GPU."""
        sys_info = self._get_system_info()

        # Only use NVENC if we have a capable GPU (not old Quadro K/M)
        if not sys_info['nvenc_capable']:
            return False

        try:
            result = subprocess.run(
                [ffmpeg_path, '-encoders'],
                capture_output=True, text=True, timeout=10
            )
            return 'h264_nvenc' in result.stdout
        except:
            return False

    def save_video_fast(self, frames_with_duration, filename, use_temp_images=False):
        """
        Save video using direct FFmpeg piping - MUCH faster than MoviePy.
        Auto-detects and uses NVENC hardware encoding when a capable GPU is available.
        Uses all CPU cores for maximum performance.

        Args:
            frames_with_duration: List of tuples (PIL_Image, duration_in_seconds)
            filename: Output filename
            use_temp_images: If True, save unique frames as temp images (faster for many duplicate frames)
        """
        output_path = os.path.join(self.output_dir, filename)
        os.makedirs(self.output_dir, exist_ok=True)

        ffmpeg_path = self._get_ffmpeg_path()
        sys_info = self._get_system_info()
        cpu_threads = sys_info['cpu_cores']

        # Check for NVENC hardware encoding
        use_nvenc = self._has_nvenc(ffmpeg_path)
        if use_nvenc:
            print(f"  Using NVENC hardware encoding ({sys_info['gpu_name']})")
            # RTX 4000 optimized: p1 = fastest, high bitrate for quality
            encoder_args = ['-c:v', 'h264_nvenc', '-preset', 'p1', '-rc', 'vbr', '-cq', '20', '-b:v', '10M', '-maxrate', '15M']
        else:
            print(f"  Using CPU encoding ({cpu_threads} threads)")
            encoder_args = ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23']

        # Optimization: Use image-based concat for videos with many static frames
        if use_temp_images or self._should_use_temp_images(frames_with_duration):
            return self._save_video_concat(frames_with_duration, output_path, ffmpeg_path, encoder_args, cpu_threads)

        # FFmpeg command for piped input - use all CPU cores
        cmd = [
            ffmpeg_path,
            '-y',  # Overwrite output
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{self.width}x{self.height}',
            '-pix_fmt', 'rgb24',
            '-r', str(self.fps),
            '-i', '-',  # Read from stdin
            *encoder_args,
            '-pix_fmt', 'yuv420p',
            '-threads', str(cpu_threads),
            output_path
        ]

        # Start FFmpeg process
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Write frames directly to FFmpeg - optimized with memoryview
        for img, duration in frames_with_duration:
            # Convert PIL image to bytes
            frame_bytes = img.tobytes()
            # Calculate number of frames for this duration
            num_frames = max(1, int(duration * self.fps))
            # Write the same frame multiple times for the duration
            # Use multiplication for efficiency instead of loop
            if num_frames <= 10:
                for _ in range(num_frames):
                    process.stdin.write(frame_bytes)
            else:
                # For longer durations, write in chunks
                chunk = frame_bytes * min(num_frames, 24)  # 1 second worth
                remaining = num_frames
                while remaining > 0:
                    write_count = min(remaining, 24)
                    if write_count == 24:
                        process.stdin.write(chunk)
                    else:
                        process.stdin.write(frame_bytes * write_count)
                    remaining -= write_count

        # Close stdin and wait for FFmpeg to finish
        process.stdin.close()
        process.wait()

        print(f"Video saved to: {output_path}")
        return output_path

    def _should_use_temp_images(self, frames_with_duration):
        """Determine if temp image method would be faster."""
        # DISABLED - the hash-based deduplication was broken (all frames had same hash)
        # because gradient backgrounds have identical first 1000 bytes
        # TODO: Fix hashing to use full image or sample from multiple regions
        return False

    def _save_video_concat(self, frames_with_duration, output_path, ffmpeg_path, encoder_args, cpu_threads):
        """
        Alternative video saving using image concat - faster for static frames.
        Saves unique frames as temp images and uses FFmpeg concat demuxer.
        """
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp(prefix='video_gen_')
        concat_file = os.path.join(temp_dir, 'concat.txt')

        try:
            # Save unique frames and build concat file
            frame_cache = {}  # hash -> filename
            with open(concat_file, 'w') as f:
                for idx, (img, duration) in enumerate(frames_with_duration):
                    # Create a simple hash from image data
                    img_hash = hash(img.tobytes()[:1000])  # First 1000 bytes for speed

                    if img_hash not in frame_cache:
                        frame_path = os.path.join(temp_dir, f'frame_{idx:04d}.png')
                        img.save(frame_path, 'PNG', optimize=False)
                        frame_cache[img_hash] = frame_path

                    f.write(f"file '{frame_cache[img_hash]}'\n")
                    f.write(f"duration {duration}\n")

            print(f"  Saved {len(frame_cache)} unique frames (concat method)")

            # FFmpeg concat
            cmd = [
                ffmpeg_path,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                *encoder_args,
                '-pix_fmt', 'yuv420p',
                '-threads', str(cpu_threads),
                '-vsync', 'cfr',
                '-r', str(self.fps),
                output_path
            ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
            print(f"Video saved to: {output_path}")
            return output_path

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Legacy MoviePy methods for backward compatibility
    def image_to_clip(self, img, duration):
        """Convert PIL Image to MoviePy clip (legacy method)."""
        from moviepy import ImageClip
        return ImageClip(np.array(img)).with_duration(duration)

    def save_video(self, clips, filename):
        """Save clips as video file using MoviePy (legacy method)."""
        from moviepy import concatenate_videoclips
        output_path = os.path.join(self.output_dir, filename)
        sys_info = self._get_system_info()

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Concatenate and write - use all CPU cores
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, fps=self.fps, codec='libx264',
                             audio=False, logger=None, preset='ultrafast',
                             threads=sys_info['cpu_cores'])

        print(f"Video saved to: {output_path}")
        return output_path

    def generate(self, content, output_filename):
        """Generate video - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement generate()")

    def generate_thumbnail(self, title, subtitle="", output_path=None):
        """Generate an eye-catching thumbnail for the video."""
        if output_path is None:
            output_path = os.path.join(self.output_dir, "thumbnail.jpg")

        # Create vibrant gradient background
        img = Image.new('RGB', (1280, 720))
        pixels = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Purple to blue gradient
        for y in range(720):
            ratio = y / 720
            r = int(100 * (1 - ratio) + 30 * ratio)
            g = int(50 * (1 - ratio) + 100 * ratio)
            b = int(200 * (1 - ratio) + 220 * ratio)
            pixels[y, :] = [r, g, b]

        img = Image.fromarray(pixels, 'RGB')
        draw = ImageDraw.Draw(img)

        # Big emoji/icon
        self.add_text(img, "🧠", (640, 200),
                     font=self._get_font(180), color=(255, 255, 255))

        # Title with shadow
        title_font = self._get_font(80)
        # Shadow
        self.add_text(img, title[:30], (644, 404),
                     font=title_font, color=(0, 0, 0))
        # Main text
        self.add_text(img, title[:30], (640, 400),
                     font=title_font, color=(255, 215, 0))

        # Subtitle
        if subtitle:
            self.add_text(img, subtitle[:40], (640, 520),
                         font=self._get_font(50), color=(255, 255, 255))

        # CTA badge
        draw.rounded_rectangle([400, 580, 880, 680], radius=20, fill=(255, 0, 0))
        self.add_text(img, "CAN YOU ANSWER?", (640, 630),
                     font=self._get_font(40), color=(255, 255, 255))

        img.save(output_path, quality=95)
        return output_path
