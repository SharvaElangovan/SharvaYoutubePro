"""AI Image Generator using Pollinations.ai (free, no API key needed)."""

import requests
from PIL import Image
from io import BytesIO
import urllib.parse
import time
import random

class AIImageGenerator:
    """Generate illustrated images using Pollinations.ai API."""

    def __init__(self):
        self.base_url = "https://image.pollinations.ai/prompt"

    def generate_image(self, prompt, width=512, height=512, seed=None):
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image
            width: Image width (default 512)
            height: Image height (default 512)
            seed: Random seed for reproducibility

        Returns:
            PIL Image object
        """
        if seed is None:
            seed = random.randint(1, 999999)

        # Add style keywords for cartoon look
        full_prompt = f"cartoon illustration, children's book style, colorful, clean lines, {prompt}"

        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(full_prompt)

        # Build URL with parameters
        url = f"{self.base_url}/{encoded_prompt}?width={width}&height={height}&seed={seed}&model=flux"

        print(f"  Generating: {prompt[:50]}...")

        # Fetch the image
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=120)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    return img.convert('RGB'), seed
                else:
                    print(f"  Attempt {attempt + 1} failed: {response.status_code}")
                    time.sleep(2)
            except Exception as e:
                print(f"  Attempt {attempt + 1} error: {e}")
                time.sleep(2)

        raise RuntimeError(f"Failed to generate image after 3 attempts")

    def generate_spot_difference_pair(self, scene_prompt, difficulty='medium'):
        """
        Generate a pair of similar images for spot-the-difference.

        Args:
            scene_prompt: Base scene description
            difficulty: 'easy', 'medium', or 'hard'
                - easy: 5 obvious differences
                - medium: 3-4 moderate differences
                - hard: 2-3 very subtle differences

        Generates a single side-by-side image and splits it into two halves.
        """
        seed = random.randint(1, 999999)

        # Difficulty controls how subtle the differences are
        if difficulty == 'easy':
            diff_desc = "5 obvious differences like missing objects, big color changes, or items in different positions"
        elif difficulty == 'hard':
            diff_desc = "exactly 3 very subtle tricky differences that are hard to spot - like a small pattern change, a tiny missing detail, a slight color shade difference, or a small shape variation - differences should require careful looking"
        else:  # medium
            diff_desc = "3 small but noticeable differences"

        # Generate side-by-side spot-the-difference image
        sidebyside_prompt = (
            f"two identical cartoon panels side by side, spot the difference puzzle, "
            f"left and right showing same {scene_prompt}, "
            f"with {diff_desc} between panels, "
            f"children book illustration, colorful, clean lines, "
            f"absolutely no text, no words, no letters, no labels, no watermarks"
        )

        print(f"  Generating spot-the-difference pair ({difficulty})...")
        # Request high resolution (API may return smaller, we'll upscale)
        combined_img, _ = self.generate_image(sidebyside_prompt, width=2048, height=1024, seed=seed)

        # Crop out watermark (bottom 40 pixels where "pollinations.ai" appears)
        width = combined_img.width
        height = combined_img.height
        watermark_crop = 40
        combined_img = combined_img.crop((0, 0, width, height - watermark_crop))
        height = combined_img.height

        # Split into left and right halves
        mid = width // 2

        left_img = combined_img.crop((0, 0, mid, height))
        right_img = combined_img.crop((mid, 0, width, height))

        # Upscale to good quality for 1080p video (each side ~900x900 for side-by-side display)
        target_size = (900, 900)
        left_img = left_img.resize(target_size, Image.Resampling.LANCZOS)
        right_img = right_img.resize(target_size, Image.Resampling.LANCZOS)

        return left_img, right_img, seed


# Scene prompts for spot-the-difference puzzles
SCENE_PROMPTS = [
    "beach scene with seagulls, umbrella, sandcastle, and picnic basket",
    "kitchen scene with pots, fruits, vegetables on counter",
    "park scene with playground, trees, ducks in pond",
    "living room with couch, TV, bookshelf, houseplants",
    "restaurant table with plates, glasses, cutlery, food",
    "garden with colorful flowers, butterflies, watering can",
    "toy store shelves with dolls, toy cars, stuffed animals",
    "bedroom with bed, lamp, alarm clock, posters on wall",
    "zoo scene with elephant, giraffe, monkey, balloons",
    "bakery display with cakes, cookies, bread loaves",
    "aquarium with tropical fish, coral, treasure chest",
    "classroom with desks, blackboard, books, globe",
    "farm scene with red barn, tractor, chickens, hay",
    "candy shop with jars of lollipops and chocolates",
    "space scene with planets, rocket ship, astronaut",
]


if __name__ == "__main__":
    # Test the generator
    gen = AIImageGenerator()

    print("Testing image generation...")
    img, seed = gen.generate_image("cute cat sitting on a couch", width=512, height=512)
    img.save("test_ai_image.png")
    print(f"Saved test_ai_image.png (seed: {seed})")

    print("\nTesting spot-difference pair...")
    base, modified, seed = gen.generate_spot_difference_pair("beach with seagulls and umbrella")
    base.save("test_base.png")
    modified.save("test_modified.png")
    print(f"Saved test_base.png and test_modified.png")
