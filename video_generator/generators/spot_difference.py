"""Spot the Difference Video Generator."""

from .base import BaseVideoGenerator
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import numpy as np
import random
import os
import sys

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SpotDifferenceGenerator(BaseVideoGenerator):
    """Generate Spot the Difference puzzle videos from user images or auto-fetched images."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default_puzzle_time = 10  # default seconds to find differences
        self._image_fetcher = None
        self._difference_maker = None

    def _get_image_fetcher(self):
        """Lazy load image fetcher."""
        if self._image_fetcher is None:
            from image_fetcher import ImageFetcher
            self._image_fetcher = ImageFetcher()
        return self._image_fetcher

    def _get_difference_maker(self):
        """Lazy load difference maker."""
        if self._difference_maker is None:
            from difference_maker import DifferenceMaker
            self._difference_maker = DifferenceMaker()
        return self._difference_maker

    def detect_differences(self, img1, img2, min_area=500, max_regions=10):
        """
        Detect differences between two images and return circle locations.

        Returns list of (cx, cy, radius) tuples for circling differences.
        """
        # Convert to numpy arrays
        arr1 = np.array(img1).astype(np.float32)
        arr2 = np.array(img2).astype(np.float32)

        # Calculate absolute difference
        diff = np.abs(arr1 - arr2)

        # Convert to grayscale difference
        diff_gray = np.mean(diff, axis=2)

        # Threshold to find significant differences
        threshold = 30
        binary = (diff_gray > threshold).astype(np.uint8)

        # Simple grid-based region detection (no scipy needed)
        # Divide image into grid cells and find cells with differences
        height, width = binary.shape
        cell_size = 80  # Size of each grid cell
        regions = []

        for y in range(0, height - cell_size, cell_size // 2):
            for x in range(0, width - cell_size, cell_size // 2):
                cell = binary[y:y+cell_size, x:x+cell_size]
                diff_count = np.sum(cell)

                if diff_count > min_area // 10:  # Significant difference in this cell
                    cx = x + cell_size // 2
                    cy = y + cell_size // 2
                    regions.append((cx, cy, cell_size // 2 + 15, diff_count))

        # Merge nearby regions
        merged = []
        used = set()
        for i, (cx1, cy1, r1, count1) in enumerate(regions):
            if i in used:
                continue
            # Find all nearby regions
            total_x, total_y, total_count, num = cx1, cy1, count1, 1
            for j, (cx2, cy2, r2, count2) in enumerate(regions):
                if j != i and j not in used:
                    dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                    if dist < cell_size * 1.5:  # Close enough to merge
                        total_x += cx2
                        total_y += cy2
                        total_count += count2
                        num += 1
                        used.add(j)
            used.add(i)
            merged.append((total_x // num, total_y // num, 50, total_count))

        # Sort by difference amount and take top N
        merged.sort(key=lambda x: x[3], reverse=True)
        merged = merged[:max_regions]

        # Return circles with good radius
        return [(cx, cy, max(r, 40)) for cx, cy, r, _ in merged]

    def load_and_resize_image(self, image_path, max_width=900, max_height=700):
        """Load an image and resize it to fit the frame."""
        img = Image.open(image_path).convert('RGB')

        # Calculate scaling to fit within max dimensions
        ratio = min(max_width / img.width, max_height / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))

        return img.resize(new_size, Image.Resampling.LANCZOS)

    def create_modified_image(self, original_img, num_changes=3):
        """
        Create a modified version of the image with specified number of changes.
        Returns the modified image and list of change locations for highlighting.
        """
        modified = original_img.copy()
        img_width, img_height = modified.size

        # Divide image into grid sections to place changes
        grid_cols = 3
        grid_rows = 3
        cell_width = img_width // grid_cols
        cell_height = img_height // grid_rows

        # Get random cells for changes (avoid edges)
        all_cells = [(r, c) for r in range(grid_rows) for c in range(grid_cols)]
        change_cells = random.sample(all_cells, min(num_changes, len(all_cells)))

        change_locations = []  # Store (x, y, radius) for highlighting

        modification_types = [
            'color_shift',
            'blur_region',
            'brightness_change',
            'remove_region',
            'add_shape',
            'flip_region',
            'tint_region'
        ]

        for i, (row, col) in enumerate(change_cells):
            # Calculate region bounds
            x1 = col * cell_width + cell_width // 4
            y1 = row * cell_height + cell_height // 4
            x2 = x1 + cell_width // 2
            y2 = y1 + cell_height // 2

            # Ensure bounds are within image
            x1 = max(10, min(x1, img_width - 60))
            y1 = max(10, min(y1, img_height - 60))
            x2 = max(x1 + 40, min(x2, img_width - 10))
            y2 = max(y1 + 40, min(y2, img_height - 10))

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            radius = max(x2 - x1, y2 - y1) // 2 + 10

            change_locations.append((center_x, center_y, radius))

            # Apply a random modification
            mod_type = random.choice(modification_types)
            modified = self._apply_modification(modified, (x1, y1, x2, y2), mod_type)

        return modified, change_locations

    def _apply_modification(self, img, region, mod_type):
        """Apply a specific modification to a region of the image."""
        x1, y1, x2, y2 = region

        # Crop the region
        region_img = img.crop((x1, y1, x2, y2))

        if mod_type == 'color_shift':
            # Shift colors in the region
            r, g, b = region_img.split()
            # Rotate color channels
            region_img = Image.merge('RGB', (g, b, r))

        elif mod_type == 'blur_region':
            # Blur the region heavily
            region_img = region_img.filter(ImageFilter.GaussianBlur(radius=8))

        elif mod_type == 'brightness_change':
            # Make region brighter or darker
            enhancer = ImageEnhance.Brightness(region_img)
            region_img = enhancer.enhance(random.choice([0.4, 1.8]))

        elif mod_type == 'remove_region':
            # Fill region with a solid color (sampled from edge)
            edge_color = img.getpixel((x1, y1))
            region_img = Image.new('RGB', region_img.size, edge_color)

        elif mod_type == 'add_shape':
            # Add a colored shape to the region
            draw = ImageDraw.Draw(region_img)
            shape_color = random.choice([
                (255, 100, 100), (100, 255, 100), (100, 100, 255),
                (255, 255, 100), (255, 100, 255), (100, 255, 255)
            ])
            w, h = region_img.size
            shape = random.choice(['ellipse', 'rectangle'])
            if shape == 'ellipse':
                draw.ellipse((w//4, h//4, 3*w//4, 3*h//4), fill=shape_color)
            else:
                draw.rectangle((w//4, h//4, 3*w//4, 3*h//4), fill=shape_color)

        elif mod_type == 'flip_region':
            # Flip the region horizontally
            region_img = region_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        elif mod_type == 'tint_region':
            # Apply a color tint
            tint_color = random.choice([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
            tint_layer = Image.new('RGB', region_img.size, tint_color)
            region_img = Image.blend(region_img, tint_layer, 0.5)

        # Paste modified region back
        result = img.copy()
        result.paste(region_img, (x1, y1))

        return result

    def create_comparison_frame(self, img1, img2, title="Find the Differences!",
                                highlight_locations=None, num_differences=None, show_timer=None):
        """Create a frame showing original and modified images side-by-side (landscape)."""
        frame = self.create_frame()

        # Title at top
        self.add_text(frame, title, (self.width // 2, 50),
                     font=self.font_large, color=self.accent_color)

        if num_differences and not highlight_locations:
            self.add_text(frame, f"Find {num_differences} differences!",
                         (self.width // 2, 110),
                         font=self.font_small, color=self.text_color)

        # Create copies to draw on
        display_img1 = img1.copy()
        display_img2 = img2.copy()

        # Add highlights if revealing answers
        if highlight_locations:
            draw1 = ImageDraw.Draw(display_img1)
            draw2 = ImageDraw.Draw(display_img2)

            for loc in highlight_locations:
                # Handle both tuple formats: (cx, cy, radius) or dict with 'region'
                if isinstance(loc, dict):
                    region = loc['region']
                    cx = (region[0] + region[2]) // 2
                    cy = (region[1] + region[3]) // 2
                    radius = max(region[2] - region[0], region[3] - region[1]) // 2 + 15
                else:
                    cx, cy, radius = loc

                # Draw circle highlight on both images
                draw1.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                             outline=(255, 50, 50), width=5)
                draw2.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                             outline=(255, 50, 50), width=5)

        # Add borders to images
        self._add_image_border(display_img1)
        self._add_image_border(display_img2)

        # LANDSCAPE: Side-by-side layout
        gap = 40
        total_width = img1.width + img2.width + gap
        x1 = (self.width - total_width) // 2
        x2 = x1 + img1.width + gap
        y_pos = 150

        frame.paste(display_img1, (x1, y_pos))
        frame.paste(display_img2, (x2, y_pos))

        # Labels below each image
        label_y = y_pos + img1.height + 20
        self.add_text(frame, "Original", (x1 + img1.width // 2, label_y),
                     font=self.font_small, color=(150, 150, 150))
        self.add_text(frame, "Modified", (x2 + img2.width // 2, label_y),
                     font=self.font_small, color=(150, 150, 150))

        # Timer in top-left corner
        if show_timer is not None:
            timer_x = 80
            timer_y = 60
            self.add_circle(frame, (timer_x, timer_y), 45,
                           fill_color=(60, 60, 80), outline_color=self.accent_color)
            self.add_text(frame, str(show_timer), (timer_x, timer_y),
                         font=self.font_medium, color=self.accent_color)

        return frame

    def _add_image_border(self, img):
        """Add a border to an image."""
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, img.width - 1, img.height - 1),
                      outline=(100, 100, 120), width=3)

    def generate(self, image_path, num_differences=3, puzzle_time=10,
                 reveal_time=5, output_filename="spot_difference.mp4"):
        """
        Generate a Spot the Difference video from a user-provided image using fast FFmpeg.

        Args:
            image_path: Path to the original image
            num_differences: Number of differences to create (default 3)
            puzzle_time: Seconds to show puzzle (time for viewer to find differences)
            reveal_time: Seconds to show the answer
            output_filename: Output file name
        """
        frames = []  # List of (PIL_Image, duration) tuples

        # Load and resize the original image
        print(f"Loading image: {image_path}")
        original_img = self.load_and_resize_image(image_path)

        # Create modified version
        print(f"Creating {num_differences} differences...")
        modified_img, change_locations = self.create_modified_image(original_img, num_differences)

        # Intro
        intro_frame = self.create_title_frame("Spot the Difference", f"Find {num_differences} differences!")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        # Puzzle with timer countdown
        for sec in range(puzzle_time, 0, -1):
            puzzle_frame = self.create_comparison_frame(
                original_img, modified_img,
                title="Spot the Difference",
                num_differences=num_differences,
                show_timer=sec
            )
            frames.append((puzzle_frame, 1))

        # Reveal differences
        reveal_frame = self.create_comparison_frame(
            original_img, modified_img,
            title=f"Answer: {num_differences} Differences!",
            highlight_locations=change_locations
        )
        frames.append((reveal_frame, reveal_time))

        # Outro
        outro_frame = self.create_title_frame("Did you find them all?", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_batch(self, image_paths, num_differences=3, puzzle_time=10,
                       reveal_time=5, output_filename="spot_difference_batch.mp4"):
        """
        Generate a video with multiple Spot the Difference puzzles using fast FFmpeg.

        Args:
            image_paths: List of paths to images
            num_differences: Number of differences per puzzle
            puzzle_time: Seconds per puzzle
            reveal_time: Seconds to show each answer
            output_filename: Output file name
        """
        frames = []  # List of (PIL_Image, duration) tuples

        # Intro
        intro_frame = self.create_title_frame("Spot the Difference",
                                              f"{len(image_paths)} Puzzles - {num_differences} differences each!")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        for idx, image_path in enumerate(image_paths, 1):
            print(f"Processing image {idx}/{len(image_paths)}: {image_path}")

            # Load image
            original_img = self.load_and_resize_image(image_path)
            modified_img, change_locations = self.create_modified_image(original_img, num_differences)

            # Puzzle number
            title_frame = self.create_title_frame(f"Puzzle {idx}", f"Find {num_differences} differences!")
            frames.append((title_frame, 2))

            # Puzzle with timer
            for sec in range(puzzle_time, 0, -1):
                puzzle_frame = self.create_comparison_frame(
                    original_img, modified_img,
                    title=f"Puzzle {idx}",
                    num_differences=num_differences,
                    show_timer=sec
                )
                frames.append((puzzle_frame, 1))

            # Reveal
            reveal_frame = self.create_comparison_frame(
                original_img, modified_img,
                title="Differences Found!",
                highlight_locations=change_locations
            )
            frames.append((reveal_frame, reveal_time))

        # Outro
        outro_frame = self.create_title_frame("Great Job!", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_auto(self, num_puzzles=5, num_differences=4, puzzle_time=10,
                      reveal_time=5, output_filename="spot_difference_auto.mp4"):
        """
        Auto-generate Spot the Difference video by fetching images from the internet.

        Args:
            num_puzzles: Number of puzzles to generate
            num_differences: Number of differences per puzzle
            puzzle_time: Seconds to show each puzzle
            reveal_time: Seconds to show answer
            output_filename: Output file name
        """
        frames = []

        # Get components
        fetcher = self._get_image_fetcher()
        maker = self._get_difference_maker()

        # Calculate image size for side-by-side display
        # Leave room for gap and margins
        img_width = (self.width - 120) // 2  # 40px gap + 40px margins each side
        img_height = self.height - 200  # Room for title and labels

        # Intro
        intro_frame = self.create_title_frame("Spot the Difference",
                                              f"{num_puzzles} Puzzles - {num_differences} differences each!")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        for idx in range(1, num_puzzles + 1):
            print(f"Generating puzzle {idx}/{num_puzzles}...")

            # Fetch image from internet
            print(f"  Fetching image...")
            original_img = fetcher.fetch_image(width=img_width, height=img_height)

            if original_img is None:
                print(f"  Failed to fetch image, skipping puzzle {idx}")
                continue

            # Create differences
            print(f"  Creating {num_differences} differences...")
            modified_img, differences = maker.create_differences(original_img, num_differences)

            # Puzzle number
            title_frame = self.create_title_frame(f"Puzzle {idx}", f"Find {num_differences} differences!")
            frames.append((title_frame, 2))

            # Puzzle with timer
            for sec in range(puzzle_time, 0, -1):
                puzzle_frame = self.create_comparison_frame(
                    original_img, modified_img,
                    title=f"Puzzle {idx}",
                    num_differences=num_differences,
                    show_timer=sec
                )
                frames.append((puzzle_frame, 1))

            # Reveal
            reveal_frame = self.create_comparison_frame(
                original_img, modified_img,
                title="Differences Found!",
                highlight_locations=differences
            )
            frames.append((reveal_frame, reveal_time))

        # Outro
        outro_frame = self.create_title_frame("Great Job!", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_with_ai(self, num_puzzles=5, scene_prompts=None,
                         num_differences=5, puzzle_time=10, reveal_time=5,
                         difficulty='medium',
                         output_filename="spot_difference_ai.mp4"):
        """
        Generate Spot the Difference video using AI-generated images from Pollinations.ai.

        Args:
            num_puzzles: Number of puzzles to generate
            scene_prompts: List of scene descriptions for image generation
            num_differences: Target number of differences (display only)
            puzzle_time: Seconds to show each puzzle
            reveal_time: Seconds to show answer
            difficulty: 'easy', 'medium', or 'hard' - controls how subtle the differences are
            output_filename: Output file name
        """
        from ai_image_generator import AIImageGenerator, SCENE_PROMPTS

        ai_gen = AIImageGenerator()
        frames = []

        # Default prompts if none provided
        if not scene_prompts:
            import random
            scene_prompts = random.sample(SCENE_PROMPTS, min(num_puzzles, len(SCENE_PROMPTS)))

        # Calculate image size for side-by-side display
        img_width = (self.width - 120) // 2
        img_height = self.height - 200

        # Intro (no AI mention for monetization)
        intro_frame = self.create_title_frame("Spot the Difference",
                                              f"{num_puzzles} Puzzles - Can You Find Them All?")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        puzzles_generated = 0
        for idx in range(num_puzzles):
            prompt = scene_prompts[idx % len(scene_prompts)]
            print(f"Generating AI puzzle {idx + 1}/{num_puzzles}: {prompt[:50]}...")

            try:
                # Generate base and modified images using Pollinations.ai
                base_img, modified_img, seed = ai_gen.generate_spot_difference_pair(
                    prompt, difficulty=difficulty
                )

                # Resize to fit our video layout
                base_img = base_img.resize((img_width, img_height), Image.Resampling.LANCZOS)
                modified_img = modified_img.resize((img_width, img_height), Image.Resampling.LANCZOS)

                puzzles_generated += 1

            except Exception as e:
                print(f"  AI generation failed: {e}, skipping puzzle")
                continue

            # Puzzle title
            title_frame = self.create_title_frame(f"Puzzle {puzzles_generated}",
                                                  f"Find the differences!")
            frames.append((title_frame, 2))

            # Detect differences for reveal
            if difficulty == 'easy':
                diff_locations = self.detect_differences(base_img, modified_img, min_area=300, max_regions=8)
            else:  # medium and hard both have ~3 differences (hard ones are just more subtle)
                diff_locations = self.detect_differences(base_img, modified_img, min_area=400, max_regions=5)
            num_found = len(diff_locations)

            # Puzzle with timer
            for sec in range(puzzle_time, 0, -1):
                puzzle_frame = self.create_comparison_frame(
                    base_img, modified_img,
                    title=f"Puzzle {puzzles_generated}",
                    num_differences=num_found if num_found > 0 else num_differences,
                    show_timer=sec
                )
                frames.append((puzzle_frame, 1))

            # Reveal with circles around differences
            reveal_frame = self.create_comparison_frame(
                base_img, modified_img,
                title=f"Answer - {num_found} Differences Found!",
                highlight_locations=diff_locations if diff_locations else None
            )
            frames.append((reveal_frame, reveal_time))

        if puzzles_generated == 0:
            raise RuntimeError("Failed to generate any puzzles")

        # Final outro
        outro_frame = self.create_title_frame("Great Job!", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_with_sd(self, num_puzzles=5, scene_prompts=None,
                         num_differences=5, puzzle_time=15, reveal_time=5,
                         output_filename="spot_difference_sd.mp4"):
        """
        Generate Spot the Difference video using local Stable Diffusion.

        Args:
            num_puzzles: Number of puzzles to generate
            scene_prompts: List of scene descriptions for image generation
            num_differences: Target number of differences
            puzzle_time: Seconds to show each puzzle
            reveal_time: Seconds to show answer
            output_filename: Output file name
        """
        import torch
        from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline

        # Default prompts for variety
        default_prompts = [
            "a cozy living room with fireplace and bookshelves, warm lighting, detailed interior design",
            "a beautiful garden with colorful flowers and stone path, sunny day, professional photography",
            "a modern kitchen with fruits and vegetables on counter, clean and organized",
            "a child's bedroom with toys and stuffed animals, colorful and playful",
            "a beach scene with palm trees and beach chairs, tropical paradise",
            "a mountain landscape with lake reflection, peaceful nature scene",
            "a busy city street with shops and cafes, urban photography",
            "a forest clearing with mushrooms and flowers, fairy tale setting",
            "a vintage classroom with chalkboard and wooden desks, nostalgic",
            "a bakery display with cakes and pastries, appetizing food photography",
        ]

        if not scene_prompts:
            import random
            scene_prompts = random.sample(default_prompts, min(num_puzzles, len(default_prompts)))

        # Load SD pipeline
        print("Loading Stable Diffusion...")
        model_path = os.path.expanduser("~/stable-diffusion-webui/models/Stable-diffusion/sd_v1.5.safetensors")

        pipe = StableDiffusionPipeline.from_single_file(
            model_path,
            torch_dtype=torch.float16
        ).to("cuda")

        # Also load img2img for creating variations
        img2img = StableDiffusionImg2ImgPipeline(
            vae=pipe.vae,
            text_encoder=pipe.text_encoder,
            tokenizer=pipe.tokenizer,
            unet=pipe.unet,
            scheduler=pipe.scheduler,
            safety_checker=None,
            feature_extractor=None,
            requires_safety_checker=False,
        ).to("cuda")

        frames = []

        # Calculate image size for side-by-side display
        img_width = (self.width - 120) // 2
        img_height = self.height - 200

        # Intro
        intro_frame = self.create_title_frame("Spot the Difference",
                                              f"{num_puzzles} Puzzles - Can You Find Them All?")
        frames.append((intro_frame, 3))

        # Countdown
        for i in range(3, 0, -1):
            countdown_frame = self.create_countdown_frame(i, "Get Ready!")
            frames.append((countdown_frame, 1))

        puzzles_generated = 0
        for idx in range(num_puzzles):
            prompt = scene_prompts[idx % len(scene_prompts)]
            print(f"Generating SD puzzle {idx + 1}/{num_puzzles}: {prompt[:50]}...")

            try:
                # Generate base image
                seed = random.randint(0, 2**32 - 1)
                generator = torch.Generator("cuda").manual_seed(seed)

                base_result = pipe(
                    prompt,
                    negative_prompt="blurry, low quality, distorted, ugly",
                    num_inference_steps=25,
                    generator=generator,
                    width=512,
                    height=512,
                )
                base_img = base_result.images[0]

                # Create modified version using img2img with slight variation
                mod_generator = torch.Generator("cuda").manual_seed(seed + 1)

                modified_result = img2img(
                    prompt=prompt + ", slightly different details",
                    image=base_img,
                    strength=0.3,  # Lower = more similar to original
                    negative_prompt="blurry, low quality, distorted",
                    num_inference_steps=20,
                    generator=mod_generator,
                )
                modified_img = modified_result.images[0]

                # Resize to fit our video layout
                base_img = base_img.resize((img_width, img_height), Image.Resampling.LANCZOS)
                modified_img = modified_img.resize((img_width, img_height), Image.Resampling.LANCZOS)

                puzzles_generated += 1

            except Exception as e:
                print(f"  SD generation failed: {e}, skipping puzzle")
                continue

            # Puzzle title
            title_frame = self.create_title_frame(f"Puzzle {puzzles_generated}",
                                                  f"Find the differences!")
            frames.append((title_frame, 2))

            # Detect differences for reveal
            diff_locations = self.detect_differences(base_img, modified_img, min_area=300, max_regions=8)
            num_found = len(diff_locations)

            # Puzzle with timer
            for sec in range(puzzle_time, 0, -1):
                puzzle_frame = self.create_comparison_frame(
                    base_img, modified_img,
                    title=f"Puzzle {puzzles_generated}",
                    num_differences=num_found if num_found > 0 else num_differences,
                    show_timer=sec
                )
                frames.append((puzzle_frame, 1))

            # Reveal with circles around differences
            reveal_frame = self.create_comparison_frame(
                base_img, modified_img,
                title=f"Answer - {num_found} Differences Found!",
                highlight_locations=diff_locations if diff_locations else None
            )
            frames.append((reveal_frame, reveal_time))

        if puzzles_generated == 0:
            raise RuntimeError("Failed to generate any puzzles")

        # Clean up GPU memory
        del pipe
        del img2img
        torch.cuda.empty_cache()

        # Final outro
        outro_frame = self.create_title_frame("Great Job!", "Thanks for playing!")
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)
