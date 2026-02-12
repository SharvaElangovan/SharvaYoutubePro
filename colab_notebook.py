#!/usr/bin/env python3
"""
Colab Notebook Code - Copy this into a Google Colab notebook.
Generates flat vector/clipart images for Spot the Difference videos.

Instructions:
1. Open Google Colab (colab.research.google.com)
2. Create a new notebook
3. Paste each section below into separate cells
4. Save the notebook to Google Drive
5. Use colab_runner.py to automate running it nightly

Cell 1: Install dependencies
Cell 2: Mount Google Drive
Cell 3: Generate images
Cell 4: Completion marker
"""

# =====================================================================
# CELL 1: Install dependencies (paste this in first Colab cell)
# =====================================================================
CELL_1_INSTALL = """
!pip install -q diffusers transformers accelerate safetensors
!pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu121
"""

# =====================================================================
# CELL 2: Mount Drive + Setup (paste this in second Colab cell)
# =====================================================================
CELL_2_SETUP = """
from google.colab import drive
drive.mount('/content/drive')

import os
OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clear old images (keep Drive clean)
for f in os.listdir(OUTPUT_DIR):
    if f.endswith('.png'):
        os.remove(os.path.join(OUTPUT_DIR, f))
print(f"Output directory ready: {OUTPUT_DIR}")
"""

# =====================================================================
# CELL 3: Generate images (paste this in third Colab cell)
# =====================================================================
CELL_3_GENERATE = """
import torch
from diffusers import StableDiffusionXLPipeline
from datetime import datetime
import random
import gc

# Load SDXL on T4 (float16 fits in 16GB)
print("Loading SDXL model...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()  # Save memory

# Flat vector/clipart scene prompts
SCENE_PROMPTS = [
    "living room interior with couch bookshelf lamp and table, flat vector illustration, simple clipart style, solid colors, no shading, 2D graphic design, clean lines, bright colors",
    "garden scene with flowers butterflies watering can and fence, flat vector art, clipart style, bold colors, no gradients, simple geometric shapes, 2D illustration",
    "kitchen interior with pots pans fruits vegetables and stove, flat 2D illustration, vector clipart, solid flat colors, minimal detail, clean design",
    "bedroom scene with bed nightstand lamp toys and window, simple vector illustration, flat clipart style, bold solid colors, 2D graphic, no shadows",
    "beach scene with umbrella sandcastle bucket and seagull, flat vector art, simple clipart, solid colors, no shading, bright cheerful, 2D design",
    "park scene with trees bench pond ducks and playground, flat 2D vector, clipart illustration, bold simple colors, clean lines, no gradients",
    "bakery shop interior with cakes bread display and counter, flat vector illustration, simple clipart style, solid pastel colors, 2D art",
    "zoo scene with elephant giraffe monkey and cages, flat 2D clipart, vector art style, bold primary colors, simple shapes, clean lines",
    "classroom interior with desks chalkboard globe and books, flat vector illustration, clipart style, solid colors, educational art, 2D design",
    "playground scene with swings slide sandbox and children playing, simple flat vector, 2D clipart art, bold colors, no shading, clean",
    "underwater ocean scene with fish coral treasure chest, flat vector illustration, simple shapes, bold colors, 2D clipart, no gradients",
    "farm scene with barn tractor animals and crops, flat 2D vector art, clipart style, bright solid colors, simple geometric shapes",
    "city street with buildings cars trees and people, flat vector illustration, simple clipart, solid colors, clean 2D design, no shadows",
    "library interior with bookshelves reading desk and globe, flat 2D illustration, vector clipart, solid colors, clean lines, simple shapes",
    "pet shop with dogs cats fish tanks and bird cages, flat vector art, clipart style, bold cheerful colors, 2D graphic design",
    "space scene with rocket planets stars and astronaut, flat vector illustration, simple 2D clipart, bold colors, no gradients, clean design",
    "toy shop interior with teddy bears blocks trains and dolls, flat 2D vector, clipart style, bright solid colors, simple shapes",
    "camping scene with tent campfire trees and mountains, flat vector illustration, simple clipart, solid colors, 2D outdoor art",
    "ice cream shop with counter sundaes cones and toppings, flat 2D clipart, vector art, bold pastel colors, simple clean design",
    "music room with piano guitar drums and notes, flat vector illustration, clipart style, solid bright colors, 2D graphic, no shading",
]

NEGATIVE_PROMPT = (
    "realistic, photograph, 3d render, photorealistic, gradient, shading, "
    "shadows, detailed texture, complex, blurry, disney, pixar, anime, "
    "watermark, text, logo, signature, dark, gloomy, scary"
)

# Generate 10 images (enough for 2 videos of 5 puzzles each)
NUM_IMAGES = 10
timestamp = datetime.now().strftime("%Y%m%d")

print(f"Generating {NUM_IMAGES} flat vector images...")
prompts = random.sample(SCENE_PROMPTS, min(NUM_IMAGES, len(SCENE_PROMPTS)))

for i, prompt in enumerate(prompts):
    seed = random.randint(0, 2**32 - 1)
    generator = torch.Generator("cuda").manual_seed(seed)

    print(f"\\n[{i+1}/{NUM_IMAGES}] {prompt[:60]}...")

    image = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=30,
        guidance_scale=7.5,
        generator=generator,
        width=1024,
        height=1024,
    ).images[0]

    filename = f"scene_{timestamp}_{i+1:02d}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    image.save(filepath)
    print(f"  Saved: {filename}")

    # Free memory between generations
    del image
    gc.collect()
    torch.cuda.empty_cache()

# Cleanup
del pipe
gc.collect()
torch.cuda.empty_cache()

print(f"\\n{'='*60}")
print(f"Generated {NUM_IMAGES} images in {OUTPUT_DIR}")
print(f"{'='*60}")
"""

# =====================================================================
# CELL 4: Completion marker (paste this in fourth Colab cell)
# =====================================================================
CELL_4_DONE = """
import os
OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'
images = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.png')]
print(f"\\nTotal images saved: {len(images)}")
for img in sorted(images):
    size = os.path.getsize(os.path.join(OUTPUT_DIR, img))
    print(f"  {img} ({size // 1024} KB)")
print("\\nALL_IMAGES_GENERATED")
"""


def print_notebook_cells():
    """Print all cells for easy copy-paste into Colab."""
    cells = [
        ("Cell 1 - Install Dependencies", CELL_1_INSTALL),
        ("Cell 2 - Mount Drive + Setup", CELL_2_SETUP),
        ("Cell 3 - Generate Images", CELL_3_GENERATE),
        ("Cell 4 - Completion Marker", CELL_4_DONE),
    ]

    print("=" * 70)
    print("COLAB NOTEBOOK - Copy each cell into Google Colab")
    print("=" * 70)

    for title, code in cells:
        print(f"\n{'─' * 70}")
        print(f"# {title}")
        print(f"{'─' * 70}")
        print(code.strip())
        print()


if __name__ == "__main__":
    print_notebook_cells()
