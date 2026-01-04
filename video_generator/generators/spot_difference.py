"""Spot the Difference Video Generator - Captain Brain Style."""

from .base import BaseVideoGenerator
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont
import numpy as np
import random
import os
import sys
import math

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SpotDifferenceGenerator(BaseVideoGenerator):
    """Generate Spot the Difference puzzle videos with branded styling."""

    def __init__(self, channel_name="BRAIN BLITZ", **kwargs):
        super().__init__(**kwargs)
        self.channel_name = channel_name
        self.default_puzzle_time = 15

        # Color scheme
        self.brand_blue = (25, 55, 95)
        self.brand_gold = (220, 180, 50)
        self.brand_light_blue = (70, 130, 180)
        self.header_height = 70
        self.footer_height = 60
        self.border_width = 25

    def detect_differences(self, img1, img2, min_area=500, max_regions=10):
        """Detect differences between two images and return circle locations."""
        arr1 = np.array(img1).astype(np.float32)
        arr2 = np.array(img2).astype(np.float32)
        diff = np.abs(arr1 - arr2)
        diff_gray = np.mean(diff, axis=2)
        threshold = 30
        binary = (diff_gray > threshold).astype(np.uint8)

        height, width = binary.shape
        cell_size = 80
        regions = []

        for y in range(0, height - cell_size, cell_size // 2):
            for x in range(0, width - cell_size, cell_size // 2):
                cell = binary[y:y+cell_size, x:x+cell_size]
                diff_count = np.sum(cell)
                if diff_count > min_area // 10:
                    cx = x + cell_size // 2
                    cy = y + cell_size // 2
                    regions.append((cx, cy, cell_size // 2 + 15, diff_count))

        merged = []
        used = set()
        for i, (cx1, cy1, r1, count1) in enumerate(regions):
            if i in used:
                continue
            total_x, total_y, total_count, num = cx1, cy1, count1, 1
            for j, (cx2, cy2, r2, count2) in enumerate(regions):
                if j != i and j not in used:
                    dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                    if dist < cell_size * 1.5:
                        total_x += cx2
                        total_y += cy2
                        total_count += count2
                        num += 1
                        used.add(j)
            used.add(i)
            merged.append((total_x // num, total_y // num, 50, total_count))

        merged.sort(key=lambda x: x[3], reverse=True)
        merged = merged[:max_regions]
        return [(cx, cy, max(r, 40)) for cx, cy, r, _ in merged]

    def load_and_resize_image(self, image_path, max_width=900, max_height=700):
        """Load an image and resize it to fit the frame."""
        img = Image.open(image_path).convert('RGB')
        ratio = min(max_width / img.width, max_height / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        return img.resize(new_size, Image.Resampling.LANCZOS)

    def draw_dotted_circle(self, draw, cx, cy, radius, color1=(255, 0, 255), color2=(0, 255, 0),
                          dot_count=40, dot_radius=4):
        """Draw an animated-style dotted circle with alternating colors."""
        for i in range(dot_count):
            angle = (2 * math.pi * i) / dot_count
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            color = color1 if i % 2 == 0 else color2
            draw.ellipse(
                [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                fill=color
            )

    def create_branded_frame(self, img1, img2, puzzle_label="FIRST",
                            show_circles=False, circle_locations=None):
        """Create a branded frame with two images side by side."""
        # Create base frame with brand blue background
        frame = Image.new('RGB', (self.width, self.height), self.brand_blue)
        draw = ImageDraw.Draw(frame)

        # Calculate image area dimensions
        content_top = self.header_height
        content_bottom = self.height - self.footer_height
        content_height = content_bottom - content_top

        # Image dimensions (side by side with gap)
        gap = 20
        img_area_width = (self.width - self.border_width * 2 - gap) // 2
        img_area_height = content_height - self.border_width * 2

        # Resize images to fit
        img1_resized = img1.copy()
        img2_resized = img2.copy()

        # Scale images to fit area while maintaining aspect ratio
        for img in [img1_resized, img2_resized]:
            if img.width != img_area_width or img.height != img_area_height:
                ratio = min(img_area_width / img.width, img_area_height / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

        img1_resized = img1.resize(
            (int(img1.width * min(img_area_width / img1.width, img_area_height / img1.height)),
             int(img1.height * min(img_area_width / img1.width, img_area_height / img1.height))),
            Image.Resampling.LANCZOS
        )
        img2_resized = img2.resize(
            (int(img2.width * min(img_area_width / img2.width, img_area_height / img2.height)),
             int(img2.height * min(img_area_width / img2.width, img_area_height / img2.height))),
            Image.Resampling.LANCZOS
        )

        # Calculate positions to center images in their areas
        x1 = self.border_width + (img_area_width - img1_resized.width) // 2
        x2 = self.width // 2 + gap // 2 + (img_area_width - img2_resized.width) // 2
        y_center = content_top + self.border_width + (img_area_height - img1_resized.height) // 2

        # Draw decorative border pattern (blue gradient effect)
        for i in range(self.border_width):
            alpha = i / self.border_width
            border_color = (
                int(25 + alpha * 45),
                int(55 + alpha * 75),
                int(95 + alpha * 85)
            )
            draw.rectangle(
                [i, content_top + i, self.width - i, content_bottom - i],
                outline=border_color
            )

        # Paste images
        frame.paste(img1_resized, (x1, y_center))
        frame.paste(img2_resized, (x2, y_center))

        # Draw thin border around each image
        draw.rectangle(
            [x1 - 2, y_center - 2, x1 + img1_resized.width + 2, y_center + img1_resized.height + 2],
            outline=(100, 150, 200), width=2
        )
        draw.rectangle(
            [x2 - 2, y_center - 2, x2 + img2_resized.width + 2, y_center + img2_resized.height + 2],
            outline=(100, 150, 200), width=2
        )

        # Draw circles on RIGHT image only if showing answers
        if show_circles and circle_locations:
            # Scale circle positions to resized image
            scale_x = img2_resized.width / img2.width
            scale_y = img2_resized.height / img2.height

            for cx, cy, radius in circle_locations:
                scaled_cx = x2 + int(cx * scale_x)
                scaled_cy = y_center + int(cy * scale_y)
                scaled_radius = int(radius * min(scale_x, scale_y))
                self.draw_dotted_circle(draw, scaled_cx, scaled_cy, scaled_radius)

        # Header bar
        draw.rectangle([0, 0, self.width, self.header_height], fill=self.brand_blue)

        # Channel name (left side with gold color and italic style)
        header_font = self._get_font(50)
        self.add_text(frame, self.channel_name, (200, self.header_height // 2),
                     font=header_font, color=self.brand_gold)

        # Puzzle label badge (right side)
        badge_font = self._get_font(35)
        badge_text = puzzle_label
        badge_width = 150
        badge_x = self.width - badge_width - 30
        badge_y = self.header_height // 2

        # Badge background
        draw.rounded_rectangle(
            [badge_x - badge_width // 2, badge_y - 25, badge_x + badge_width // 2, badge_y + 25],
            radius=5, fill=self.brand_gold
        )
        self.add_text(frame, badge_text, (badge_x, badge_y),
                     font=badge_font, color=self.brand_blue)

        # Watermark on both images
        watermark_font = self._get_font(20)
        watermark = f"@{self.channel_name.replace(' ', '-')}"
        self.add_text(frame, watermark, (x1 + 80, y_center + 25),
                     font=watermark_font, color=(255, 255, 255, 180))
        self.add_text(frame, watermark, (x2 + 80, y_center + 25),
                     font=watermark_font, color=(255, 255, 255, 180))

        # Footer
        draw.rectangle([0, self.height - self.footer_height, self.width, self.height],
                      fill=self.brand_blue)
        footer_font = self._get_font(45)
        self.add_text(frame, "SPOT THE DIFFERENCE", (self.width // 2, self.height - self.footer_height // 2),
                     font=footer_font, color=(255, 255, 255))

        # Divider line under header
        draw.line([(0, self.header_height), (self.width, self.header_height)],
                 fill=self.brand_light_blue, width=3)
        # Divider line above footer
        draw.line([(0, self.height - self.footer_height), (self.width, self.height - self.footer_height)],
                 fill=self.brand_light_blue, width=3)

        return frame

    def create_intro_frame(self, num_puzzles, num_differences):
        """Create animated intro frame."""
        frame = Image.new('RGB', (self.width, self.height), self.brand_blue)
        draw = ImageDraw.Draw(frame)

        # Add subtle gradient/pattern
        for y in range(self.height):
            alpha = y / self.height
            color = (
                int(25 + alpha * 20),
                int(55 + alpha * 30),
                int(95 + alpha * 40)
            )
            draw.line([(0, y), (self.width, y)], fill=color)

        # Channel name
        title_font = self._get_font(90)
        self.add_text(frame, self.channel_name, (self.width // 2, 200),
                     font=title_font, color=self.brand_gold)

        # Main title
        main_font = self._get_font(80)
        self.add_text(frame, f"SPOT THE {num_differences} DIFFERENCES",
                     (self.width // 2, 350),
                     font=main_font, color=(100, 200, 255))

        # Subtitle
        sub_font = self._get_font(60)
        self.add_text(frame, f"{num_puzzles} PUZZLES AWAIT!",
                     (self.width // 2, 480),
                     font=sub_font, color=self.brand_gold)

        return frame

    def create_challenge_transition(self, challenge_num, total_challenges):
        """Create transition screen between challenges."""
        frame = Image.new('RGB', (self.width, self.height), (30, 30, 40))
        draw = ImageDraw.Draw(frame)

        # Draw perspective corridor effect
        center_x, center_y = self.width // 2, self.height // 2
        for i in range(20, 0, -1):
            scale = i / 20
            rect_w = int(self.width * scale * 0.8)
            rect_h = int(self.height * scale * 0.8)
            gray = int(40 + (20 - i) * 8)
            draw.rectangle(
                [center_x - rect_w // 2, center_y - rect_h // 2,
                 center_x + rect_w // 2, center_y + rect_h // 2],
                outline=(gray, gray, gray + 20), width=2
            )

        # Channel name in corner
        corner_font = self._get_font(35)
        self.add_text(frame, self.channel_name, (150, 40),
                     font=corner_font, color=self.brand_gold)

        # Challenge text
        ordinals = ["First", "Second", "Third", "Fourth", "Fifth",
                   "Sixth", "Seventh", "Eighth", "Ninth", "Tenth"]
        ordinal = ordinals[challenge_num - 1] if challenge_num <= 10 else f"#{challenge_num}"

        challenge_font = self._get_font(80)
        self.add_text(frame, f"The {ordinal} Challenge",
                     (self.width // 2, self.height // 2),
                     font=challenge_font, color=(200, 200, 220))

        return frame

    def create_modified_image(self, original_img, num_changes=3, hard_mode=False):
        """Create a modified version of the image with OBVIOUS, visible differences.

        Like Captain Brain style - whole objects removed or colors completely changed.
        """
        modified = original_img.copy()
        img_width, img_height = modified.size

        # Use 3x3 grid for big, obvious regions
        grid_cols = 3
        grid_rows = 3
        cell_width = img_width // grid_cols
        cell_height = img_height // grid_rows

        all_cells = [(r, c) for r in range(grid_rows) for c in range(grid_cols)]
        change_cells = random.sample(all_cells, min(num_changes, len(all_cells)))

        change_locations = []

        # OBVIOUS modifications only - things you can see immediately
        modification_types = [
            'remove_object',      # Fill region with background color (object disappears)
            'color_swap',         # Completely change color (red→blue, not subtle)
            'add_object',         # Add a visible colored shape
            'invert_colors',      # Invert the colors in region
            'remove_object',      # Higher chance of removal (most obvious)
        ]

        for i, (row, col) in enumerate(change_cells):
            # BIG regions - 60-100 pixels so changes are visible
            region_size = random.randint(60, 100)
            x1 = col * cell_width + random.randint(10, max(11, cell_width - region_size - 10))
            y1 = row * cell_height + random.randint(10, max(11, cell_height - region_size - 10))
            x2 = x1 + region_size
            y2 = y1 + region_size

            # Keep within bounds
            x1 = max(5, min(x1, img_width - region_size - 5))
            y1 = max(5, min(y1, img_height - region_size - 5))
            x2 = min(x2, img_width - 5)
            y2 = min(y2, img_height - 5)

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            radius = max(x2 - x1, y2 - y1) // 2 + 15

            change_locations.append((center_x, center_y, radius))

            mod_type = random.choice(modification_types)
            modified = self._apply_modification(modified, (x1, y1, x2, y2), mod_type)

        return modified, change_locations

    def _apply_modification(self, img, region, mod_type):
        """Apply an OBVIOUS modification to a region of the image."""
        x1, y1, x2, y2 = region
        region_img = img.crop((x1, y1, x2, y2))
        w, h = region_img.size

        if mod_type == 'remove_object':
            # Sample colors from edges to fill (makes object "disappear")
            edge_colors = []
            for x in range(w):
                edge_colors.append(region_img.getpixel((x, 0)))
                edge_colors.append(region_img.getpixel((x, h-1)))
            for y in range(h):
                edge_colors.append(region_img.getpixel((0, y)))
                edge_colors.append(region_img.getpixel((w-1, y)))
            # Average edge color
            avg_r = sum(c[0] for c in edge_colors) // len(edge_colors)
            avg_g = sum(c[1] for c in edge_colors) // len(edge_colors)
            avg_b = sum(c[2] for c in edge_colors) // len(edge_colors)
            region_img = Image.new('RGB', (w, h), (avg_r, avg_g, avg_b))

        elif mod_type == 'color_swap':
            # Completely swap color channels for dramatic change
            r, g, b = region_img.split()
            swap = random.choice(['rgb_to_bgr', 'rgb_to_grb', 'invert_one'])
            if swap == 'rgb_to_bgr':
                region_img = Image.merge('RGB', (b, g, r))
            elif swap == 'rgb_to_grb':
                region_img = Image.merge('RGB', (g, r, b))
            else:
                # Invert just one channel for obvious but natural-ish change
                from PIL import ImageOps
                r = ImageOps.invert(r)
                region_img = Image.merge('RGB', (r, g, b))

        elif mod_type == 'add_object':
            # Add a bright, obvious colored shape
            draw = ImageDraw.Draw(region_img)
            bright_colors = [
                (255, 50, 50),    # Bright red
                (50, 255, 50),    # Bright green
                (50, 50, 255),    # Bright blue
                (255, 255, 50),   # Yellow
                (255, 50, 255),   # Magenta
                (50, 255, 255),   # Cyan
                (255, 150, 50),   # Orange
            ]
            color = random.choice(bright_colors)
            shape = random.choice(['circle', 'star', 'square'])
            cx, cy = w // 2, h // 2
            size = min(w, h) // 3

            if shape == 'circle':
                draw.ellipse([cx-size, cy-size, cx+size, cy+size], fill=color)
            elif shape == 'square':
                draw.rectangle([cx-size, cy-size, cx+size, cy+size], fill=color)
            else:  # star - draw as overlapping triangles
                draw.polygon([(cx, cy-size), (cx+size, cy+size), (cx-size, cy+size)], fill=color)
                draw.polygon([(cx, cy+size), (cx+size, cy-size), (cx-size, cy-size)], fill=color)

        elif mod_type == 'invert_colors':
            # Full color inversion - very obvious
            from PIL import ImageOps
            region_img = ImageOps.invert(region_img)

        result = img.copy()
        result.paste(region_img, (x1, y1))
        return result

    def generate_with_sd(self, num_puzzles=5, scene_prompts=None,
                         num_differences=3, puzzle_time=15, reveal_time=5,
                         output_filename="spot_difference_sd.mp4"):
        """Generate Spot the Difference video using local Stable Diffusion."""
        import torch
        from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline

        default_prompts = [
            "cozy living room with bookshelf armchair and table, bold black outlines, flat colors, cartoon illustration, children's book art style",
            "colorful garden with flowers watering can and butterflies, bold outlines, flat cartoon colors, illustration",
            "kitchen scene with fruits pots and window, bold black outlines, flat colors, cartoon style illustration",
            "child bedroom with bed toys and lamp, bold outlines, colorful flat cartoon illustration",
            "beach scene with umbrella sandcastle and seagulls, bold black outlines, flat cartoon colors",
            "park with trees bench and pond with ducks, bold outlines, flat colors, cartoon illustration",
            "bakery shop with cakes bread and counter, bold black outlines, flat cartoon colors, illustration",
            "zoo scene with animals and visitors, bold outlines, colorful flat cartoon style",
            "classroom with desks chalkboard and globe, bold black outlines, flat cartoon illustration",
            "playground with swings slide and children, bold outlines, flat colors, cartoon style",
        ]

        if not scene_prompts:
            scene_prompts = random.sample(default_prompts, min(num_puzzles, len(default_prompts)))

        print("Loading Stable Diffusion...")
        model_path = os.path.expanduser("~/stable-diffusion-webui/models/Stable-diffusion/sd_v1.5.safetensors")

        pipe = StableDiffusionPipeline.from_single_file(
            model_path,
            torch_dtype=torch.float16
        ).to("cuda")

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
        puzzle_labels = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH",
                        "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH"]

        # Intro frames
        intro_frame = self.create_intro_frame(num_puzzles, num_differences)
        frames.append((intro_frame, 4))

        puzzles_generated = 0
        for idx in range(num_puzzles):
            prompt = scene_prompts[idx % len(scene_prompts)]
            print(f"Generating SD puzzle {idx + 1}/{num_puzzles}: {prompt[:50]}...")

            try:
                seed = random.randint(0, 2**32 - 1)
                generator = torch.Generator("cuda").manual_seed(seed)

                base_result = pipe(
                    prompt,
                    negative_prompt="blurry, low quality, distorted, ugly, realistic, photograph, 3d render, photorealistic, gradient shading, soft edges",
                    num_inference_steps=25,
                    generator=generator,
                    width=512,
                    height=512,
                )
                base_img = base_result.images[0]

                # Create modified version with guaranteed visible differences
                modified_img, diff_locations = self.create_modified_image(base_img, num_differences)

                puzzles_generated += 1
                label = puzzle_labels[puzzles_generated - 1] if puzzles_generated <= 10 else f"#{puzzles_generated}"

            except Exception as e:
                print(f"  SD generation failed: {e}, skipping puzzle")
                continue

            # Transition screen
            transition = self.create_challenge_transition(puzzles_generated, num_puzzles)
            frames.append((transition, 2))

            # Puzzle frames (no circles)
            for sec in range(puzzle_time):
                puzzle_frame = self.create_branded_frame(
                    base_img, modified_img,
                    puzzle_label=label,
                    show_circles=False
                )
                frames.append((puzzle_frame, 1))

            # Reveal frames (with circles appearing)
            reveal_frame = self.create_branded_frame(
                base_img, modified_img,
                puzzle_label=label,
                show_circles=True,
                circle_locations=diff_locations
            )
            frames.append((reveal_frame, reveal_time))

        if puzzles_generated == 0:
            raise RuntimeError("Failed to generate any puzzles")

        del pipe
        del img2img
        torch.cuda.empty_cache()

        # Outro
        outro_frame = self.create_intro_frame(puzzles_generated, num_differences)
        draw = ImageDraw.Draw(outro_frame)
        draw.rectangle([0, 0, self.width, self.height], fill=self.brand_blue)
        outro_font = self._get_font(70)
        self.add_text(outro_frame, "Great Job!", (self.width // 2, self.height // 2 - 50),
                     font=outro_font, color=self.brand_gold)
        self.add_text(outro_frame, "Thanks for playing!", (self.width // 2, self.height // 2 + 50),
                     font=self._get_font(50), color=(255, 255, 255))
        frames.append((outro_frame, 3))

        return self.save_video_fast(frames, output_filename)

    def generate(self, image_path, num_differences=3, puzzle_time=10,
                 reveal_time=5, output_filename="spot_difference.mp4"):
        """Generate a Spot the Difference video from a user-provided image."""
        frames = []

        print(f"Loading image: {image_path}")
        original_img = self.load_and_resize_image(image_path)

        print(f"Creating {num_differences} differences...")
        modified_img, change_locations = self.create_modified_image(original_img, num_differences)

        # Intro
        intro_frame = self.create_intro_frame(1, num_differences)
        frames.append((intro_frame, 3))

        # Transition
        transition = self.create_challenge_transition(1, 1)
        frames.append((transition, 2))

        # Puzzle frames
        for sec in range(puzzle_time):
            puzzle_frame = self.create_branded_frame(
                original_img, modified_img,
                puzzle_label="CHALLENGE",
                show_circles=False
            )
            frames.append((puzzle_frame, 1))

        # Reveal
        reveal_frame = self.create_branded_frame(
            original_img, modified_img,
            puzzle_label="ANSWER",
            show_circles=True,
            circle_locations=change_locations
        )
        frames.append((reveal_frame, reveal_time))

        # Outro
        outro = Image.new('RGB', (self.width, self.height), self.brand_blue)
        self.add_text(outro, "Did you find them all?", (self.width // 2, self.height // 2),
                     font=self._get_font(60), color=self.brand_gold)
        frames.append((outro, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_batch(self, image_paths, num_differences=3, puzzle_time=10,
                       reveal_time=5, output_filename="spot_difference_batch.mp4"):
        """Generate a video with multiple Spot the Difference puzzles."""
        frames = []
        puzzle_labels = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH",
                        "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH"]

        intro_frame = self.create_intro_frame(len(image_paths), num_differences)
        frames.append((intro_frame, 3))

        for idx, image_path in enumerate(image_paths, 1):
            print(f"Processing image {idx}/{len(image_paths)}: {image_path}")
            label = puzzle_labels[idx - 1] if idx <= 10 else f"#{idx}"

            original_img = self.load_and_resize_image(image_path)
            modified_img, change_locations = self.create_modified_image(original_img, num_differences)

            transition = self.create_challenge_transition(idx, len(image_paths))
            frames.append((transition, 2))

            for sec in range(puzzle_time):
                puzzle_frame = self.create_branded_frame(
                    original_img, modified_img,
                    puzzle_label=label,
                    show_circles=False
                )
                frames.append((puzzle_frame, 1))

            reveal_frame = self.create_branded_frame(
                original_img, modified_img,
                puzzle_label=label,
                show_circles=True,
                circle_locations=change_locations
            )
            frames.append((reveal_frame, reveal_time))

        outro = Image.new('RGB', (self.width, self.height), self.brand_blue)
        self.add_text(outro, "Great Job!", (self.width // 2, self.height // 2 - 30),
                     font=self._get_font(70), color=self.brand_gold)
        self.add_text(outro, "Thanks for playing!", (self.width // 2, self.height // 2 + 50),
                     font=self._get_font(50), color=(255, 255, 255))
        frames.append((outro, 3))

        return self.save_video_fast(frames, output_filename)

    def generate_auto(self, num_puzzles=5, num_differences=3, puzzle_time=10,
                      reveal_time=5, output_filename="spot_difference_auto.mp4"):
        """Generate Spot the Difference video using local Stable Diffusion.

        Uses RTX 4000 GPU via SD venv subprocess.
        """
        import subprocess

        sd_python = os.path.expanduser("~/stable-diffusion-webui/venv/bin/python")
        video_gen_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(video_gen_path, "output", output_filename)

        gen_script = f'''
import sys
sys.path.insert(0, "{video_gen_path}")
from generators import SpotDifferenceGenerator

gen = SpotDifferenceGenerator()
gen.generate_with_sd(
    num_puzzles={num_puzzles},
    num_differences={num_differences},
    puzzle_time={puzzle_time},
    reveal_time={reveal_time},
    output_filename="{output_filename}"
)
print("VIDEO_GENERATED")
'''

        print(f"Running Stable Diffusion via subprocess...")
        result = subprocess.run(
            [sd_python, "-c", gen_script],
            capture_output=True,
            text=True,
            cwd=video_gen_path
        )

        if "VIDEO_GENERATED" in result.stdout:
            print("Video generated successfully!")
            return output_path
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"SD generation failed: {error_msg}")
