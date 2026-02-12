#!/usr/bin/env python3
"""
Colab Notebook Code - Copy this into a Google Colab notebook.

Two-step pipeline:
  1. SDXL generates flat vector base scenes (fast, great style)
  2. FLUX Kontext creates modified versions with real differences (smart edits)

This produces image pairs for Spot the Difference videos.

Instructions:
1. Open Google Colab (colab.research.google.com) - select T4 GPU runtime
2. Create a new notebook
3. Paste each section below into separate cells
4. Save the notebook to Google Drive
5. Use colab_runner.py to automate running it nightly
"""

# =====================================================================
# CELL 1: Install dependencies
# =====================================================================
CELL_1_INSTALL = """
!pip install -q diffusers[torch] transformers accelerate safetensors sentencepiece protobuf
"""

# =====================================================================
# CELL 2: Mount Drive + Setup
# =====================================================================
CELL_2_SETUP = """
from google.colab import drive
drive.mount('/content/drive')

import os
OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clear old images (keep Drive clean, spot_difference_upload.py also deletes after use)
for f in os.listdir(OUTPUT_DIR):
    if f.endswith('.png'):
        os.remove(os.path.join(OUTPUT_DIR, f))
print(f"Output directory ready: {OUTPUT_DIR}")
"""

# =====================================================================
# CELL 3: Generate base scenes with SDXL
# =====================================================================
CELL_3_SDXL = """
import torch
from diffusers import StableDiffusionXLPipeline
from datetime import datetime
import random
import gc

print("Loading SDXL (fp16 on T4)...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()

# 50 flat vector scene prompts - each has lots of objects for good spot-the-difference
SCENE_PROMPTS = [
    "living room interior with couch bookshelf floor lamp coffee table and rug, flat vector illustration, simple clipart style, solid colors, no shading, 2D graphic design, clean lines, bright colors",
    "garden scene with red flowers butterflies watering can white fence and trees, flat vector art, clipart style, bold colors, no gradients, simple geometric shapes, 2D illustration",
    "kitchen interior with pots pans fruits vegetables stove and fridge, flat 2D illustration, vector clipart, solid flat colors, minimal detail, clean design",
    "bedroom scene with bed nightstand lamp teddy bear toys and window with curtains, simple vector illustration, flat clipart style, bold solid colors, 2D graphic, no shadows",
    "beach scene with striped umbrella sandcastle bucket shovel and seagull flying, flat vector art, simple clipart, solid colors, no shading, bright cheerful, 2D design",
    "park scene with green trees park bench pond with ducks and playground slide, flat 2D vector, clipart illustration, bold simple colors, clean lines, no gradients",
    "bakery shop interior with cakes bread rolls display case and counter, flat vector illustration, simple clipart style, solid pastel colors, 2D art",
    "zoo scene with elephant giraffe monkey in cages and trees, flat 2D clipart, vector art style, bold primary colors, simple shapes, clean lines",
    "classroom interior with desks chalkboard with writing globe and stacked books, flat vector illustration, clipart style, solid colors, educational art, 2D design",
    "playground scene with red swings blue slide sandbox bucket and children playing, simple flat vector, 2D clipart art, bold colors, no shading, clean",
    "underwater ocean scene with colorful fish coral reef treasure chest and seaweed, flat vector illustration, simple shapes, bold colors, 2D clipart, no gradients",
    "farm scene with red barn tractor cow chicken and crop field, flat 2D vector art, clipart style, bright solid colors, simple geometric shapes",
    "city street with tall buildings cars traffic light trees and people walking, flat vector illustration, simple clipart, solid colors, clean 2D design, no shadows",
    "library interior with tall bookshelves reading desk lamp and globe, flat 2D illustration, vector clipart, solid colors, clean lines, simple shapes",
    "pet shop interior with puppies kittens fish tank and bird cage, flat vector art, clipart style, bold cheerful colors, 2D graphic design",
    "space scene with red rocket saturn planet stars moon and astronaut floating, flat vector illustration, simple 2D clipart, bold colors, no gradients, clean design",
    "toy shop interior with teddy bears building blocks toy train and dolls on shelves, flat 2D vector, clipart style, bright solid colors, simple shapes",
    "camping scene with orange tent campfire marshmallows tall trees and mountains, flat vector illustration, simple clipart, solid colors, 2D outdoor art",
    "ice cream shop with counter display sundaes waffle cones and colorful toppings, flat 2D clipart, vector art, bold pastel colors, simple clean design",
    "music room with grand piano red guitar drum set and floating music notes, flat vector illustration, clipart style, solid bright colors, 2D graphic, no shading",
    "aquarium scene with tropical fish jellyfish starfish and coral formations, flat vector illustration, simple shapes, bright colors, 2D clipart style",
    "train station platform with train benches clock tower and passengers, flat 2D vector, clipart illustration, bold colors, simple geometric shapes, clean lines",
    "butterfly garden with colorful butterflies flowers fountain and stone path, flat vector art, simple clipart, solid colors, no shading, 2D illustration",
    "pirate ship on ocean with skull flag treasure chest parrot and waves, flat 2D clipart, vector art style, bold primary colors, simple shapes",
    "candy shop interior with jars of candy lollipops gumball machine and cupcakes, flat vector illustration, clipart style, bright pastel colors, 2D design",
    "dinosaur scene with t-rex palm trees volcano and pterodactyl flying, flat 2D vector, simple clipart art, bold colors, no gradients, clean design",
    "airport scene with airplane terminal building control tower and luggage carts, flat vector illustration, simple clipart style, solid colors, 2D graphic",
    "castle scene with towers flags moat drawbridge and knight on horse, flat 2D clipart, vector art, bold medieval colors, simple shapes, clean lines",
    "fruit market stall with apples bananas oranges grapes and vendor with umbrella, flat vector art, clipart style, bright solid colors, 2D illustration",
    "snow scene with snowman igloo pine trees sled and falling snowflakes, flat 2D vector, simple clipart, bold colors on white, no shading, clean design",
    "jungle scene with toucan monkey vines waterfall and large tropical leaves, flat vector illustration, clipart style, bold green colors, 2D art",
    "race track with colorful race cars checkered flag grandstand and pit stop, flat 2D clipart, vector art style, bright primary colors, simple shapes",
    "haunted house with bats ghost pumpkins black cat and full moon, flat vector illustration, simple clipart, bold orange purple colors, 2D design",
    "circus tent with clown elephant on ball balloons and popcorn stand, flat 2D vector, clipart illustration, bright cheerful colors, simple shapes",
    "construction site with crane dump truck hard hats and building frame, flat vector art, simple clipart style, bold yellow orange colors, 2D graphic",
    "flower shop with bouquets potted plants watering can and window display, flat vector illustration, clipart style, soft pastel colors, 2D clean design",
    "hospital room with bed doctor stethoscope medicine cabinet and wheelchair, flat 2D clipart, vector art, bold colors, simple shapes, clean lines",
    "pizza shop with brick oven pizza on counter chef hat and menu board, flat vector illustration, simple clipart style, warm solid colors, 2D art",
    "laundry room with washing machine basket of clothes iron and hanging shirts, flat 2D vector, clipart illustration, bold colors, simple shapes, clean design",
    "treehouse scene with wooden treehouse ladder swing tire and birds nest, flat vector art, clipart style, brown green colors, simple 2D illustration",
    "bowling alley with lanes pins bowling balls scoreboard and seats, flat 2D clipart, vector art style, bold neon colors, simple shapes, clean lines",
    "art studio with easel paint palette brushes and colorful canvases, flat vector illustration, simple clipart, bright colors, 2D graphic design",
    "dentist office with chair tools mirror toothbrush poster and light, flat 2D vector, clipart illustration, clean white blue colors, simple shapes",
    "fire station with fire truck dalmatian dog helmets and fire pole, flat vector art, clipart style, bold red colors, simple 2D illustration",
    "superhero scene with hero cape mask building skyline and clouds, flat 2D clipart, vector art, bold primary colors, simple shapes, clean design",
    "hot air balloon festival with colorful balloons clouds birds and landscape, flat vector illustration, clipart style, bright rainbow colors, 2D art",
    "robot workshop with robots gears tools computer screen and workbench, flat 2D vector, simple clipart, bold metallic colors, clean design",
    "safari scene with jeep binoculars lion zebra and acacia tree, flat vector art, clipart style, warm golden colors, simple 2D illustration",
    "witch scene with cauldron spell book black cat broomstick and potion bottles, flat 2D clipart, vector art, bold purple green colors, simple shapes",
    "birthday party with cake balloons presents party hats and confetti, flat vector illustration, clipart style, bright festive colors, 2D clean design",
]

NEGATIVE_PROMPT = (
    "realistic, photograph, 3d render, photorealistic, gradient, shading, "
    "shadows, detailed texture, complex, blurry, disney, pixar, anime, "
    "watermark, text, logo, signature, dark, gloomy, scary"
)

NUM_IMAGES = 50
timestamp = datetime.now().strftime("%Y%m%d")

print(f"\\nGenerating {NUM_IMAGES} base scenes with SDXL...")
prompts = random.sample(SCENE_PROMPTS, min(NUM_IMAGES, len(SCENE_PROMPTS)))

for i, prompt in enumerate(prompts):
    seed = random.randint(0, 2**32 - 1)
    generator = torch.Generator("cuda").manual_seed(seed)

    print(f"[{i+1}/{NUM_IMAGES}] {prompt[:60]}...")

    image = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=30,
        guidance_scale=7.5,
        generator=generator,
        width=1024,
        height=1024,
    ).images[0]

    filename = f"pair_{i+1:03d}_original.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    image.save(filepath)
    print(f"  Saved: {filename}")

    del image
    gc.collect()
    torch.cuda.empty_cache()

# Unload SDXL completely to free VRAM for FLUX
del pipe
gc.collect()
torch.cuda.empty_cache()
print(f"\\nSDXL done! {NUM_IMAGES} base scenes saved. VRAM freed for FLUX.")
"""

# =====================================================================
# CELL 4: Create differences with FLUX Kontext
# =====================================================================
CELL_4_FLUX = """
import torch
import os
import gc
import random
from PIL import Image
from diffusers import FluxKontextPipeline
from diffusers.utils import load_image

OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'

print("Loading FLUX Kontext (with CPU offloading for T4)...")
pipe = FluxKontextPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-Kontext-dev",
    torch_dtype=torch.bfloat16,
)
pipe.enable_model_cpu_offload()  # Fits in 16GB T4 with offloading

# Edit instructions - FLUX makes smart, meaningful changes
EDIT_INSTRUCTIONS = [
    "Make exactly 3 visible changes to this flat vector clipart image: change one object's color to a completely different color, remove one small object entirely, and add a small new colored object somewhere. Keep the flat vector clipart style exactly the same.",
    "Make exactly 4 visible changes to this flat clipart illustration: swap two objects' colors, remove one object, make one object much bigger, and add a new small shape. Keep the flat 2D clipart style.",
    "Make exactly 3 obvious differences in this flat vector image: remove one object completely, change one object from its current color to bright red, and flip one object horizontally. Keep the flat vector style.",
    "Make exactly 3 clear changes to this clipart scene: change the background color of one area, remove one small detail, and add a bright star shape somewhere new. Maintain the flat clipart look.",
    "Make exactly 4 visible edits to this flat vector illustration: change one large object's color, remove a small object, add a new small animal or item, and move one object to a different position. Keep the flat vector style.",
    "Make exactly 3 noticeable changes to this 2D clipart image: turn one object upside down, change one color from warm to cool tone, and remove one item entirely. Keep the flat 2D clipart style.",
    "Make exactly 3 differences in this flat vector scene: add a new brightly colored object, remove an existing small object, and change the color of one large area. Maintain flat vector illustration style.",
    "Make exactly 4 changes to this clipart image: replace one object with a different object of similar size, change two objects' colors to new colors, and remove one small detail. Keep the flat clipart style.",
]

original_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith('_original.png')])
total = len(original_files)

print(f"\\nCreating modified versions for {total} images with FLUX Kontext...")

for i, orig_file in enumerate(original_files):
    pair_num = int(orig_file.split('_')[1])
    modified_file = f"pair_{pair_num:03d}_modified.png"
    modified_path = os.path.join(OUTPUT_DIR, modified_file)

    # Skip if already generated (resume support)
    if os.path.exists(modified_path):
        print(f"[{i+1}/{total}] {modified_file} already exists, skipping")
        continue

    orig_path = os.path.join(OUTPUT_DIR, orig_file)
    orig_image = load_image(orig_path).resize((1024, 1024))

    edit_instruction = random.choice(EDIT_INSTRUCTIONS)
    print(f"[{i+1}/{total}] Creating {modified_file}...")

    try:
        result = pipe(
            image=orig_image,
            prompt=edit_instruction,
            guidance_scale=2.5,
            num_inference_steps=28,
            height=1024,
            width=1024,
        ).images[0]

        result.save(modified_path)
        print(f"  Saved: {modified_file}")

    except Exception as e:
        print(f"  ERROR: {e} - skipping this pair")

    del orig_image
    gc.collect()
    torch.cuda.empty_cache()

# Cleanup
del pipe
gc.collect()
torch.cuda.empty_cache()

print(f"\\n{'='*60}")
print("FLUX Kontext modifications complete!")
print(f"{'='*60}")
"""

# =====================================================================
# CELL 5: Verify and completion marker
# =====================================================================
CELL_5_DONE = """
import os

OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'

originals = sorted([f for f in os.listdir(OUTPUT_DIR) if '_original.png' in f])
modifieds = sorted([f for f in os.listdir(OUTPUT_DIR) if '_modified.png' in f])

# Find complete pairs
complete_pairs = 0
for orig in originals:
    pair_num = orig.split('_')[1]
    modified = f"pair_{pair_num}_modified.png"
    if modified in modifieds:
        complete_pairs += 1

print(f"\\nResults:")
print(f"  Original images: {len(originals)}")
print(f"  Modified images: {len(modifieds)}")
print(f"  Complete pairs:  {complete_pairs}")

if complete_pairs > 0:
    print(f"  That's enough for {complete_pairs // 5} videos ({complete_pairs} puzzles)")

print("\\nALL_IMAGES_GENERATED")
"""


def print_notebook_cells():
    """Print all cells for easy copy-paste into Colab."""
    cells = [
        ("Cell 1 - Install Dependencies", CELL_1_INSTALL),
        ("Cell 2 - Mount Drive + Setup", CELL_2_SETUP),
        ("Cell 3 - Generate Base Scenes with SDXL", CELL_3_SDXL),
        ("Cell 4 - Create Differences with FLUX Kontext", CELL_4_FLUX),
        ("Cell 5 - Verify + Completion Marker", CELL_5_DONE),
    ]

    print("=" * 70)
    print("COLAB NOTEBOOK - SDXL + FLUX Kontext Pipeline")
    print("Copy each cell into Google Colab (T4 GPU runtime)")
    print("=" * 70)

    for title, code in cells:
        print(f"\n{'='*70}")
        print(f"# {title}")
        print(f"{'='*70}")
        print(code.strip())
        print()


if __name__ == "__main__":
    print_notebook_cells()
