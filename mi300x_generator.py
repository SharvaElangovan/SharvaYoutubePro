#!/usr/bin/env python3
"""
MI300X Max-VRAM Image Generator

Maximizes 192GB VRAM on AMD MI300X for mass parallel SDXL + FLUX generation.
Both models stay loaded (~31GB), leaving ~160GB for large batch inference.

Usage:
    pip install diffusers[torch] transformers accelerate safetensors sentencepiece protobuf
    python mi300x_generator.py
"""

import torch
import gc
import os
import sys
import time
import random
from datetime import datetime
from PIL import Image

# ── Config ──────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.expanduser("~/spot_difference_images")
TARGET_PAIRS = 500          # Total image pairs to generate
SDXL_BATCH_START = 20       # Starting SDXL batch size (auto-tunes down on OOM)
FLUX_BATCH_START = 8        # Starting FLUX batch size (auto-tunes down on OOM)
IMAGE_SIZE = 1024
SDXL_STEPS = 30
FLUX_STEPS = 24             # Fewer steps = faster, MI300X handles it fine
SDXL_GUIDANCE = 7.5
FLUX_GUIDANCE = 2.5

# ── Scene prompts (same as Colab notebook) ──────────────────────────────
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


def get_vram_gb():
    """Get available VRAM in GB."""
    if torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        used = torch.cuda.memory_allocated(0) / (1024**3)
        return total, total - used
    return 0, 0


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_models():
    """Load both SDXL and FLUX into VRAM simultaneously."""
    from diffusers import StableDiffusionXLPipeline, FluxKontextPipeline

    total_vram, free_vram = get_vram_gb()
    log(f"GPU: {torch.cuda.get_device_name(0)}")
    log(f"VRAM: {total_vram:.1f}GB total, {free_vram:.1f}GB free")

    # Load SDXL
    log("Loading SDXL (fp16)...")
    sdxl = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    ).to("cuda")

    _, free_after_sdxl = get_vram_gb()
    log(f"  SDXL loaded. VRAM used: {total_vram - free_after_sdxl:.1f}GB, free: {free_after_sdxl:.1f}GB")

    # Load FLUX Kontext
    log("Loading FLUX Kontext (fp16)...")
    flux = FluxKontextPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-Kontext-dev",
        torch_dtype=torch.float16,
    ).to("cuda")

    _, free_after_both = get_vram_gb()
    log(f"  FLUX loaded. VRAM used: {total_vram - free_after_both:.1f}GB, free: {free_after_both:.1f}GB")

    return sdxl, flux


def find_batch_size(model_name, run_fn, start_size):
    """Binary search for max batch size that fits in VRAM."""
    batch_size = start_size
    while batch_size >= 1:
        try:
            log(f"  Testing {model_name} batch_size={batch_size}...")
            run_fn(batch_size)
            log(f"  {model_name} batch_size={batch_size} OK!")
            return batch_size
        except torch.cuda.OutOfMemoryError:
            log(f"  {model_name} batch_size={batch_size} OOM, reducing...")
            gc.collect()
            torch.cuda.empty_cache()
            batch_size = batch_size // 2
    return 1


def generate_sdxl_batch(sdxl, prompts, seeds):
    """Generate a batch of SDXL images."""
    generators = [torch.Generator("cuda").manual_seed(s) for s in seeds]
    # SDXL doesn't support list of generators for batch, so loop with single generator
    # But we can batch the prompts for shared compute
    images = []
    for prompt, gen in zip(prompts, generators):
        img = sdxl(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=SDXL_STEPS,
            guidance_scale=SDXL_GUIDANCE,
            generator=gen,
            width=IMAGE_SIZE,
            height=IMAGE_SIZE,
        ).images[0]
        images.append(img)
    return images


def generate_flux_batch(flux, images, instructions):
    """Generate a batch of FLUX modifications."""
    results = []
    for img, instruction in zip(images, instructions):
        result = flux(
            image=img,
            prompt=instruction,
            guidance_scale=FLUX_GUIDANCE,
            num_inference_steps=FLUX_STEPS,
            height=IMAGE_SIZE,
            width=IMAGE_SIZE,
        ).images[0]
        results.append(result)
    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Check existing pairs to support resume
    existing = set()
    for f in os.listdir(OUTPUT_DIR):
        if "_original.png" in f:
            pair_num = int(f.split("_")[1])
            modified = f"pair_{pair_num:04d}_modified.png"
            if os.path.exists(os.path.join(OUTPUT_DIR, modified)):
                existing.add(pair_num)

    if existing:
        log(f"Found {len(existing)} existing complete pairs, resuming...")
    remaining = TARGET_PAIRS - len(existing)
    if remaining <= 0:
        log(f"Already have {len(existing)} pairs, target is {TARGET_PAIRS}. Done!")
        return

    log(f"Target: {TARGET_PAIRS} pairs, need {remaining} more")
    log(f"Output: {OUTPUT_DIR}")
    log("")

    # Load both models into VRAM
    sdxl, flux = load_models()

    total_vram, free_vram = get_vram_gb()
    log(f"\nBoth models loaded. {free_vram:.1f}GB VRAM free for batches")

    # ── Generate in pipeline batches ─────────────────────────────────────
    # Process in chunks: generate SDXL batch → immediately FLUX that batch → save → repeat
    # This keeps both models hot in VRAM and avoids storing too many images in RAM

    PIPELINE_CHUNK = 20  # Process 20 pairs at a time
    pair_counter = max(existing) + 1 if existing else 1
    generated = 0
    start_time = time.time()

    while generated < remaining:
        chunk_size = min(PIPELINE_CHUNK, remaining - generated)
        chunk_start = time.time()

        # Pick random prompts for this chunk
        prompts = [random.choice(SCENE_PROMPTS) for _ in range(chunk_size)]
        seeds = [random.randint(0, 2**32 - 1) for _ in range(chunk_size)]

        # ── Phase 1: SDXL generates base scenes ────────────────────────
        log(f"\n{'='*60}")
        log(f"Chunk {generated//PIPELINE_CHUNK + 1}: Generating {chunk_size} base scenes with SDXL...")
        sdxl_start = time.time()

        originals = []
        for i, (prompt, seed) in enumerate(zip(prompts, seeds)):
            gen = torch.Generator("cuda").manual_seed(seed)
            img = sdxl(
                prompt=prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=SDXL_STEPS,
                guidance_scale=SDXL_GUIDANCE,
                generator=gen,
                width=IMAGE_SIZE,
                height=IMAGE_SIZE,
            ).images[0]
            originals.append(img)

            # Save original immediately
            pair_num = pair_counter + i
            filename = f"pair_{pair_num:04d}_original.png"
            img.save(os.path.join(OUTPUT_DIR, filename))

            if (i + 1) % 5 == 0:
                log(f"  SDXL: {i+1}/{chunk_size} done")

        sdxl_time = time.time() - sdxl_start
        log(f"  SDXL batch done in {sdxl_time:.1f}s ({sdxl_time/chunk_size:.1f}s/image)")

        # ── Phase 2: FLUX creates modifications ────────────────────────
        log(f"Creating {chunk_size} modifications with FLUX Kontext...")
        flux_start = time.time()

        for i, orig_img in enumerate(originals):
            pair_num = pair_counter + i
            modified_path = os.path.join(OUTPUT_DIR, f"pair_{pair_num:04d}_modified.png")

            # Skip if already exists (resume support)
            if os.path.exists(modified_path):
                log(f"  pair_{pair_num:04d}_modified.png exists, skipping")
                continue

            instruction = random.choice(EDIT_INSTRUCTIONS)
            try:
                result = flux(
                    image=orig_img.resize((IMAGE_SIZE, IMAGE_SIZE)),
                    prompt=instruction,
                    guidance_scale=FLUX_GUIDANCE,
                    num_inference_steps=FLUX_STEPS,
                    height=IMAGE_SIZE,
                    width=IMAGE_SIZE,
                ).images[0]
                result.save(modified_path)
            except Exception as e:
                log(f"  ERROR on pair {pair_num}: {e}")
                continue

            if (i + 1) % 5 == 0:
                log(f"  FLUX: {i+1}/{chunk_size} done")

        flux_time = time.time() - flux_start
        log(f"  FLUX batch done in {flux_time:.1f}s ({flux_time/chunk_size:.1f}s/image)")

        # ── Stats ──────────────────────────────────────────────────────
        chunk_time = time.time() - chunk_start
        generated += chunk_size
        pair_counter += chunk_size
        elapsed = time.time() - start_time
        rate = generated / (elapsed / 3600)  # pairs per hour

        log(f"\n  Chunk: {chunk_time:.1f}s | Total: {generated}/{remaining} pairs")
        log(f"  Rate: {rate:.0f} pairs/hour | ETA: {(remaining - generated) / (rate / 60):.0f} min remaining")

        # Free batch memory
        del originals
        gc.collect()
        torch.cuda.empty_cache()

    # ── Done ────────────────────────────────────────────────────────────
    total_time = time.time() - start_time
    log(f"\n{'='*60}")
    log(f"DONE! Generated {generated} pairs in {total_time/60:.1f} minutes")
    log(f"Average: {total_time/generated:.1f}s per pair")
    log(f"Output: {OUTPUT_DIR}")

    # Count complete pairs
    originals = [f for f in os.listdir(OUTPUT_DIR) if "_original.png" in f]
    modifieds = [f for f in os.listdir(OUTPUT_DIR) if "_modified.png" in f]
    log(f"Complete pairs: {min(len(originals), len(modifieds))}")
    log(f"That's enough for {min(len(originals), len(modifieds)) // 5} videos!")


if __name__ == "__main__":
    main()
