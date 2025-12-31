"""Stable Diffusion integration for generating spot-the-difference images."""

import os
import time
import subprocess
import requests
from PIL import Image
from io import BytesIO
import json

class StableDiffusionGenerator:
    """Generate illustrated images using local Stable Diffusion."""

    def __init__(self, api_url="http://localhost:7860"):
        self.api_url = api_url
        self.sd_path = os.path.expanduser("~/stable-diffusion-webui")
        self.process = None

    def is_running(self):
        """Check if SD WebUI is running."""
        try:
            response = requests.get(f"{self.api_url}/sdapi/v1/sd-models", timeout=2)
            return response.status_code == 200
        except:
            return False

    def start_server(self):
        """Start the SD WebUI server in background."""
        if self.is_running():
            print("Stable Diffusion already running")
            return True

        print("Starting Stable Diffusion WebUI...")
        print("(First run will take 5-10 minutes to install dependencies)")

        # Start in background
        self.process = subprocess.Popen(
            ["./webui.sh", "--nowebui"],  # API only, no browser
            cwd=self.sd_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )

        # Wait for server to be ready (up to 10 minutes for first run)
        for i in range(120):  # 10 minutes max
            if self.is_running():
                print("Stable Diffusion ready!")
                return True
            time.sleep(5)
            if i % 6 == 0:
                print(f"  Waiting for SD to start... ({i*5}s)")

        print("Failed to start Stable Diffusion")
        return False

    def generate_image(self, prompt, negative_prompt="", width=512, height=512,
                       steps=20, cfg_scale=7, seed=-1):
        """Generate an image using the SD API."""
        if not self.is_running():
            raise RuntimeError("Stable Diffusion not running. Call start_server() first.")

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt or "realistic, photo, blurry, text, watermark, low quality",
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": seed,
            "sampler_name": "DPM++ 2M Karras",
        }

        response = requests.post(
            f"{self.api_url}/sdapi/v1/txt2img",
            json=payload,
            timeout=300  # 5 min timeout for generation
        )

        if response.status_code != 200:
            raise RuntimeError(f"SD API error: {response.status_code}")

        result = response.json()

        # Decode base64 image
        import base64
        img_data = base64.b64decode(result['images'][0])
        img = Image.open(BytesIO(img_data))

        # Get the seed used (for reproducibility)
        info = json.loads(result.get('info', '{}'))
        used_seed = info.get('seed', seed)

        return img, used_seed

    def generate_variation(self, prompt, seed, variation_strength=0.1, **kwargs):
        """Generate a slight variation of an image using subseed."""
        if not self.is_running():
            raise RuntimeError("Stable Diffusion not running")

        payload = {
            "prompt": prompt,
            "negative_prompt": kwargs.get('negative_prompt', "realistic, photo, blurry, text, watermark"),
            "width": kwargs.get('width', 512),
            "height": kwargs.get('height', 512),
            "steps": kwargs.get('steps', 20),
            "cfg_scale": kwargs.get('cfg_scale', 7),
            "seed": seed,
            "subseed": seed + 1,
            "subseed_strength": variation_strength,
            "sampler_name": "DPM++ 2M Karras",
        }

        response = requests.post(
            f"{self.api_url}/sdapi/v1/txt2img",
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f"SD API error: {response.status_code}")

        result = response.json()
        import base64
        img_data = base64.b64decode(result['images'][0])
        return Image.open(BytesIO(img_data))

    def generate_spot_difference_pair(self, scene_prompt, num_differences=5):
        """
        Generate a pair of images for spot-the-difference.

        Strategy: Generate base image, then use img2img with slight modifications
        to create natural differences.
        """
        # Base prompt for cartoon style
        full_prompt = f"cartoon illustration, children's book style, {scene_prompt}, colorful, clean lines, detailed scene with many objects"
        negative = "realistic, photo, blurry, text, watermark, signature, low quality, deformed"

        print(f"Generating base image...")
        base_img, seed = self.generate_image(full_prompt, negative)

        print(f"Generating modified version (seed: {seed})...")

        # Use img2img to create variations
        modified_img = self._img2img_variation(base_img, full_prompt, negative, num_differences)

        return base_img, modified_img, seed

    def _img2img_variation(self, source_img, prompt, negative_prompt, num_differences):
        """Use img2img to create a variation with differences."""
        import base64

        # Convert image to base64
        buffer = BytesIO()
        source_img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Lower denoising = more similar, higher = more different
        # Aim for subtle but noticeable differences
        denoising = 0.3 + (num_differences * 0.05)  # 0.35-0.75 based on difficulty
        denoising = min(0.6, denoising)

        payload = {
            "init_images": [img_base64],
            "prompt": prompt + ", slight variations",
            "negative_prompt": negative_prompt,
            "denoising_strength": denoising,
            "steps": 20,
            "cfg_scale": 7,
            "width": source_img.width,
            "height": source_img.height,
            "sampler_name": "DPM++ 2M Karras",
        }

        response = requests.post(
            f"{self.api_url}/sdapi/v1/img2img",
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f"img2img error: {response.status_code}")

        result = response.json()
        img_data = base64.b64decode(result['images'][0])
        return Image.open(BytesIO(img_data))

    def get_models(self):
        """Get list of available models."""
        if not self.is_running():
            return []

        try:
            response = requests.get(f"{self.api_url}/sdapi/v1/sd-models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                return [m['model_name'] for m in models]
        except:
            pass
        return []

    def set_model(self, model_name):
        """Switch to a specific model."""
        payload = {"sd_model_checkpoint": model_name}
        response = requests.post(
            f"{self.api_url}/sdapi/v1/options",
            json=payload,
            timeout=120
        )
        return response.status_code == 200


# Scene prompts for spot-the-difference puzzles
SCENE_PROMPTS = [
    "beach scene with seagulls, umbrella, sandcastle, beach ball, and picnic food",
    "kitchen scene with pots, pans, fruits, vegetables, and cooking utensils",
    "park scene with playground, trees, ducks, bench, and children playing",
    "living room with couch, TV, bookshelf, plants, and cat",
    "restaurant table with plates, glasses, cutlery, and food",
    "garden scene with flowers, butterflies, watering can, and birds",
    "toy store shelves with dolls, cars, balls, and stuffed animals",
    "bedroom with bed, lamp, clock, pictures, and toys",
    "zoo scene with animals, fences, visitors, and balloons",
    "bakery display with cakes, cookies, bread, and pastries",
    "aquarium scene with fish, coral, treasure chest, and diver",
    "classroom with desks, blackboard, books, and school supplies",
    "farm scene with barn, tractor, animals, and hay bales",
    "candy shop with jars, lollipops, chocolates, and gummies",
    "space scene with planets, rockets, astronauts, and stars",
]


if __name__ == "__main__":
    # Test the integration
    sd = StableDiffusionGenerator()

    print("Checking if SD is running...")
    if sd.is_running():
        print("SD is running!")
        models = sd.get_models()
        print(f"Available models: {models}")

        # Test generation
        print("\nGenerating test image...")
        img, seed = sd.generate_image(
            "cartoon illustration, beach scene with seagull, colorful",
            width=512, height=512
        )
        img.save("test_sd_image.png")
        print(f"Saved test_sd_image.png (seed: {seed})")
    else:
        print("SD not running. Start it with: cd ~/stable-diffusion-webui && ./webui.sh")
