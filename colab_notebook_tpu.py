#!/usr/bin/env python3
"""
Colab Notebook Code - TPU VARIANT (the gamble)

WARNING: This is experimental. TPU v2-8 has only 8GB per core.
- SDXL (6.5GB bf16) → might barely fit on 1 TPU core
- FLUX (24GB bf16) → won't fit, uses CPU offloading through TPU host RAM (~25GB)

If this crashes, use colab_notebook.py with T4 GPU instead.

Instructions:
1. Open Google Colab
2. Runtime > Change runtime type > TPU v2
3. Paste each cell below
4. Cross your fingers
"""

# =====================================================================
# CELL 1: Install dependencies for TPU
# =====================================================================
CELL_1_INSTALL = """
# Install PyTorch XLA for TPU support
!pip install -q torch_xla[tpu] -f https://storage.googleapis.com/libtpu-releases/index.html
!pip install -q diffusers[torch] transformers accelerate safetensors sentencepiece protobuf

import torch
import torch_xla.core.xla_model as xm

# Check TPU availability
device = xm.xla_device()
print(f"TPU device: {device}")
print(f"TPU type: {torch_xla._XLAC._xla_get_default_device()}")
print(f"System RAM: {torch.cuda.get_device_properties(0).total_memory // 1e9:.1f} GB" if torch.cuda.is_available() else "No CUDA (expected on TPU)")
print()

import psutil
print(f"Host RAM: {psutil.virtual_memory().total / 1e9:.1f} GB")
print(f"Host RAM available: {psutil.virtual_memory().available / 1e9:.1f} GB")
print()
print("If host RAM is 25+ GB, FLUX CPU offloading should work!")
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

for f in os.listdir(OUTPUT_DIR):
    if f.endswith('.png'):
        os.remove(os.path.join(OUTPUT_DIR, f))
print(f"Output directory ready: {OUTPUT_DIR}")
"""

# =====================================================================
# CELL 3: Generate base scenes with SDXL on TPU
# =====================================================================
CELL_3_SDXL_TPU = """
import torch
import torch_xla.core.xla_model as xm
from diffusers import StableDiffusionXLPipeline
from datetime import datetime
import random
import gc
import time

device = xm.xla_device()

# THE GAMBLE: Load SDXL in bfloat16 onto a single TPU core (8GB)
# bfloat16 is native TPU dtype (faster than float16 on TPU)
print("Loading SDXL onto TPU (bfloat16)... this is the gamble part")
try:
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.bfloat16,
        variant="fp16",  # Load fp16 weights, cast to bf16
        use_safetensors=True,
    )
    pipe = pipe.to(device)
    pipe.enable_attention_slicing(1)  # Minimum memory attention
    USE_TPU = True
    print("SDXL loaded on TPU! The gamble paid off!")
except Exception as e:
    print(f"TPU failed: {e}")
    print("Falling back to CPU with float32... (slow but safe)")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float32,
        use_safetensors=True,
    )
    pipe.enable_attention_slicing(1)
    pipe.enable_sequential_cpu_offload()
    USE_TPU = False
    device = torch.device("cpu")
    print("Running on CPU (this will be slow)")

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

print(f"\\nGenerating {NUM_IMAGES} base scenes...")
print(f"Running on: {'TPU' if USE_TPU else 'CPU (fallback)'}")
if USE_TPU:
    print("NOTE: First image is slow (XLA graph compilation). After that it's fast!")

prompts = random.sample(SCENE_PROMPTS, min(NUM_IMAGES, len(SCENE_PROMPTS)))

for i, prompt in enumerate(prompts):
    seed = random.randint(0, 2**32 - 1)

    # TPU uses torch.Generator without device arg, GPU/CPU uses device arg
    if USE_TPU:
        generator = torch.Generator().manual_seed(seed)
    else:
        generator = torch.Generator().manual_seed(seed)

    print(f"[{i+1}/{NUM_IMAGES}] {prompt[:60]}...")
    start = time.time()

    try:
        image = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=25,  # Slightly fewer steps to reduce TPU memory
            guidance_scale=7.5,
            generator=generator,
            width=1024,
            height=1024,
        ).images[0]

        if USE_TPU:
            xm.mark_step()  # Sync TPU execution

        filename = f"pair_{i+1:03d}_original.png"
        filepath = os.path.join(OUTPUT_DIR, filename)
        image.save(filepath)
        elapsed = time.time() - start
        print(f"  Saved: {filename} ({elapsed:.1f}s)")

        del image
    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "resource" in str(e).lower():
            print(f"  OOM! TPU core ran out of memory at image {i+1}")
            print(f"  Generated {i} images before crashing - continuing with what we have")
            break
        raise

    gc.collect()

del pipe
gc.collect()
print(f"\\nSDXL done! Base scenes saved to Drive.")
"""

# =====================================================================
# CELL 4: FLUX Kontext for differences (CPU offload through TPU host)
# =====================================================================
CELL_4_FLUX_TPU = """
import torch
import os
import gc
import random
import time
from PIL import Image
from diffusers import FluxKontextPipeline
from diffusers.utils import load_image

OUTPUT_DIR = '/content/drive/MyDrive/spot_difference_images'

# FLUX is too big for a single TPU core (24GB > 8GB)
# But TPU host has ~25GB RAM - use CPU offloading
print("Loading FLUX Kontext with CPU offloading (TPU host RAM)...")
print("This is the BIG GAMBLE - FLUX needs ~24GB, TPU host has ~25GB RAM")
print()

try:
    pipe = FluxKontextPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-Kontext-dev",
        torch_dtype=torch.bfloat16,
    )
    # CPU offloading - model stays on CPU, moves to device only during forward pass
    # On TPU runtime, this uses the host CPU RAM (~25GB)
    pipe.enable_sequential_cpu_offload()
    print("FLUX loaded with CPU offloading! This will be SLOW but should work.")
    print("Expected: ~2-5 min per image on CPU")
except Exception as e:
    print(f"FLUX loading failed: {e}")
    print()
    print("FLUX can't run on this TPU instance.")
    print("Options:")
    print("  1. Switch to T4 GPU runtime and use colab_notebook.py")
    print("  2. Use the SDXL base images with PIL modifications (local SD fallback)")
    raise SystemExit("FLUX loading failed - switch to GPU runtime")

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

print(f"\\nCreating modified versions for {total} images...")
print(f"WARNING: CPU inference is SLOW (~2-5 min per image, total ~{total * 3} min)")
print()

for i, orig_file in enumerate(original_files):
    pair_num = int(orig_file.split('_')[1])
    modified_file = f"pair_{pair_num:03d}_modified.png"
    modified_path = os.path.join(OUTPUT_DIR, modified_file)

    if os.path.exists(modified_path):
        print(f"[{i+1}/{total}] {modified_file} already exists, skipping")
        continue

    orig_path = os.path.join(OUTPUT_DIR, orig_file)
    orig_image = load_image(orig_path).resize((1024, 1024))

    edit_instruction = random.choice(EDIT_INSTRUCTIONS)
    print(f"[{i+1}/{total}] Creating {modified_file}...")
    start = time.time()

    try:
        result = pipe(
            image=orig_image,
            prompt=edit_instruction,
            guidance_scale=2.5,
            num_inference_steps=24,  # Fewer steps since CPU is slow
            height=1024,
            width=1024,
        ).images[0]

        result.save(modified_path)
        elapsed = time.time() - start
        remaining = (total - i - 1) * elapsed
        print(f"  Saved: {modified_file} ({elapsed:.0f}s, ~{remaining/60:.0f}min remaining)")

    except Exception as e:
        print(f"  ERROR: {e}")
        if "out of memory" in str(e).lower():
            print("  Host RAM OOM - can't continue. Switch to GPU runtime.")
            break

    del orig_image
    gc.collect()

del pipe
gc.collect()
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
        ("Cell 1 - Install Dependencies (TPU)", CELL_1_INSTALL),
        ("Cell 2 - Mount Drive + Setup", CELL_2_SETUP),
        ("Cell 3 - SDXL on TPU (the first gamble)", CELL_3_SDXL_TPU),
        ("Cell 4 - FLUX Kontext via CPU offload (the big gamble)", CELL_4_FLUX_TPU),
        ("Cell 5 - Verify + Completion Marker", CELL_5_DONE),
    ]

    print("=" * 70)
    print("COLAB NOTEBOOK - TPU VARIANT (GAMBLING EDITION)")
    print("Runtime > Change runtime type > TPU v2")
    print("=" * 70)
    print()
    print("RISKS:")
    print("  - SDXL might OOM on single TPU core (8GB)")
    print("  - FLUX runs on CPU (slow: ~2-5 min per image)")
    print("  - PyTorch XLA may have random compilation errors")
    print("  - First SDXL image takes ~5 min (XLA graph compile)")
    print()
    print("If it crashes, use colab_notebook.py with T4 GPU instead.")
    print()

    for title, code in cells:
        print(f"\n{'='*70}")
        print(f"# {title}")
        print(f"{'='*70}")
        print(code.strip())
        print()


if __name__ == "__main__":
    print_notebook_cells()
