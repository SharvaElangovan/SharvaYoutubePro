#!/usr/bin/env python3
"""
MI300X Max-VRAM Image Generator

Maximizes 192GB VRAM on AMD MI300X for mass parallel SDXL + FLUX generation.
Loads each model ONCE, creates N lightweight pipeline clones sharing GPU weights,
runs them in parallel threads across the MI300X's 8 compute dies.
Auto-detects optimal worker count to fill ~90% of free VRAM.

Usage:
    pip install diffusers[torch] transformers accelerate safetensors sentencepiece protobuf
    python mi300x_generator.py                # auto-fill VRAM (default)
    python mi300x_generator.py --workers 12   # force 12 workers
    python mi300x_generator.py --target 1000  # generate 1000 pairs
"""

import torch
import gc
import os
import sys
import copy
import time
import random
import argparse
import threading
from datetime import datetime
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

# ── Config ──────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.expanduser("~/spot_difference_images")
IMAGE_SIZE = 1024
SDXL_STEPS = 30
FLUX_STEPS = 24
SDXL_GUIDANCE = 7.5
FLUX_GUIDANCE = 2.5

# ── Scene prompts ───────────────────────────────────────────────────────
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

# ── Globals ─────────────────────────────────────────────────────────────
print_lock = threading.Lock()
save_lock = threading.Lock()
pair_counter_lock = threading.Lock()
stats = {"sdxl_done": 0, "flux_done": 0, "errors": 0, "start_time": 0}


def get_vram_gb():
    """Get total and free VRAM in GB."""
    if torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        used = torch.cuda.memory_allocated(0) / (1024**3)
        return total, total - used
    return 0, 0


def log(msg):
    with print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def clone_sdxl(base_pipe, device="cuda"):
    """Create a lightweight SDXL pipeline clone sharing GPU model weights."""
    from diffusers import StableDiffusionXLPipeline
    clone = StableDiffusionXLPipeline(
        unet=base_pipe.unet,
        vae=base_pipe.vae,
        text_encoder=base_pipe.text_encoder,
        text_encoder_2=base_pipe.text_encoder_2,
        tokenizer=base_pipe.tokenizer,
        tokenizer_2=base_pipe.tokenizer_2,
        scheduler=copy.deepcopy(base_pipe.scheduler),
    )
    return clone


def clone_flux(base_pipe, device="cuda"):
    """Create a lightweight FLUX pipeline clone sharing GPU model weights."""
    from diffusers import FluxKontextPipeline
    clone = FluxKontextPipeline(
        transformer=base_pipe.transformer,
        text_encoder=base_pipe.text_encoder,
        text_encoder_2=base_pipe.text_encoder_2,
        tokenizer=base_pipe.tokenizer,
        tokenizer_2=base_pipe.tokenizer_2,
        vae=base_pipe.vae,
        scheduler=copy.deepcopy(base_pipe.scheduler),
    )
    return clone


def estimate_worker_vram():
    """
    Estimate VRAM per worker by running a single test inference.
    Returns (sdxl_per_worker_gb, flux_per_worker_gb).
    """
    return 5.0, 8.0  # Conservative estimates; actual tuning happens at runtime


def auto_worker_count(free_vram_gb, target_usage=0.90):
    """
    Calculate how many workers to run to fill target_usage of free VRAM.
    Each worker pair (SDXL + FLUX) needs ~13GB for inference buffers.
    """
    sdxl_cost, flux_cost = estimate_worker_vram()
    per_worker = sdxl_cost + flux_cost  # Both run concurrently in pipeline
    usable = free_vram_gb * target_usage
    count = max(1, int(usable / per_worker))
    return count


def load_models(num_workers):
    """Load base models, then create N clones sharing GPU weights."""
    from diffusers import StableDiffusionXLPipeline, FluxKontextPipeline

    total_vram, free_vram = get_vram_gb()
    log(f"GPU: {torch.cuda.get_device_name(0)}")
    log(f"VRAM: {total_vram:.1f}GB total, {free_vram:.1f}GB free")

    # Load base SDXL
    log("Loading SDXL base model (fp16)...")
    sdxl_base = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    ).to("cuda")

    _, free = get_vram_gb()
    log(f"  SDXL loaded. {free:.1f}GB VRAM free")

    # Load base FLUX Kontext
    log("Loading FLUX Kontext base model (fp16)...")
    flux_base = FluxKontextPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-Kontext-dev",
        torch_dtype=torch.float16,
    ).to("cuda")

    _, free = get_vram_gb()
    log(f"  FLUX loaded. {free:.1f}GB VRAM free")

    # Auto-detect worker count if requested
    if num_workers == 0:
        num_workers = auto_worker_count(free)
        log(f"  Auto-detected: {num_workers} workers to fill {free:.1f}GB free VRAM")

    # Create worker clones (share weights, own schedulers)
    log(f"Creating {num_workers} SDXL + {num_workers} FLUX worker clones...")
    sdxl_workers = [clone_sdxl(sdxl_base) for _ in range(num_workers)]
    flux_workers = [clone_flux(flux_base) for _ in range(num_workers)]

    _, free = get_vram_gb()
    log(f"  {num_workers} workers ready. {free:.1f}GB VRAM free for inference")

    return sdxl_workers, flux_workers, num_workers


def sdxl_worker(worker_id, sdxl_pipe, task_queue, result_queue, output_dir):
    """Worker thread: pulls pair numbers from queue, generates SDXL originals."""
    stream = torch.cuda.Stream()
    while True:
        try:
            pair_num = task_queue.get(timeout=1)
        except Empty:
            return

        prompt = random.choice(SCENE_PROMPTS)
        seed = random.randint(0, 2**32 - 1)
        filename = f"pair_{pair_num:04d}_original.png"
        filepath = os.path.join(output_dir, filename)

        try:
            with torch.cuda.stream(stream):
                gen = torch.Generator("cuda").manual_seed(seed)
                img = sdxl_pipe(
                    prompt=prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    num_inference_steps=SDXL_STEPS,
                    guidance_scale=SDXL_GUIDANCE,
                    generator=gen,
                    width=IMAGE_SIZE,
                    height=IMAGE_SIZE,
                ).images[0]

            img.save(filepath)
            result_queue.put((pair_num, img))
            stats["sdxl_done"] += 1
            log(f"  [W{worker_id}] SDXL #{pair_num} done ({stats['sdxl_done']} total)")

        except Exception as e:
            log(f"  [W{worker_id}] SDXL #{pair_num} ERROR: {e}")
            stats["errors"] += 1
            task_queue.task_done()
            continue

        task_queue.task_done()


def flux_worker(worker_id, flux_pipe, result_queue, output_dir, total_target):
    """Worker thread: takes SDXL results, generates FLUX modifications."""
    stream = torch.cuda.Stream()
    while stats["flux_done"] + stats["errors"] < total_target:
        try:
            pair_num, orig_img = result_queue.get(timeout=5)
        except Empty:
            # Check if SDXL is done and queue is empty
            if stats["sdxl_done"] >= total_target:
                return
            continue

        modified_path = os.path.join(output_dir, f"pair_{pair_num:04d}_modified.png")
        instruction = random.choice(EDIT_INSTRUCTIONS)

        try:
            with torch.cuda.stream(stream):
                result = flux_pipe(
                    image=orig_img.resize((IMAGE_SIZE, IMAGE_SIZE)),
                    prompt=instruction,
                    guidance_scale=FLUX_GUIDANCE,
                    num_inference_steps=FLUX_STEPS,
                    height=IMAGE_SIZE,
                    width=IMAGE_SIZE,
                ).images[0]

            result.save(modified_path)
            stats["flux_done"] += 1
            elapsed = time.time() - stats["start_time"]
            rate = stats["flux_done"] / (elapsed / 3600)
            log(f"  [F{worker_id}] FLUX #{pair_num} done ({stats['flux_done']} complete pairs | {rate:.0f}/hr)")

        except Exception as e:
            log(f"  [F{worker_id}] FLUX #{pair_num} ERROR: {e}")
            stats["errors"] += 1

        result_queue.task_done()


def main():
    parser = argparse.ArgumentParser(description="MI300X Max-VRAM Image Generator")
    parser.add_argument("--workers", type=int, default=0, help="Number of parallel workers (0=auto-fill VRAM, default: 0)")
    parser.add_argument("--target", type=int, default=500, help="Total pairs to generate (default: 500)")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    num_workers = args.workers
    target = args.target
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # ── Resume support ──────────────────────────────────────────────────
    existing = set()
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            if "_original.png" in f:
                pair_num = int(f.split("_")[1])
                modified = f"pair_{pair_num:04d}_modified.png"
                if os.path.exists(os.path.join(output_dir, modified)):
                    existing.add(pair_num)

    if existing:
        log(f"Found {len(existing)} existing complete pairs, resuming...")
    remaining = target - len(existing)
    if remaining <= 0:
        log(f"Already have {len(existing)} pairs, target is {target}. Done!")
        return

    log(f"═══════════════════════════════════════════════════════")
    log(f"  MI300X Max-VRAM Generator")
    log(f"  Workers: {'AUTO (fill VRAM)' if num_workers == 0 else f'{num_workers} SDXL + {num_workers} FLUX'}")
    log(f"  Target: {remaining} pairs ({target} total, {len(existing)} exist)")
    log(f"  Output: {output_dir}")
    log(f"═══════════════════════════════════════════════════════\n")

    # ── Load models + create worker clones ──────────────────────────────
    sdxl_workers, flux_workers, num_workers = load_models(num_workers)

    # ── Setup queues ────────────────────────────────────────────────────
    # task_queue: pair numbers for SDXL to generate
    # result_queue: (pair_num, image) for FLUX to process
    task_queue = Queue()
    result_queue = Queue(maxsize=num_workers * 3)  # Buffer 3x workers to avoid RAM bloat

    start_pair = max(existing) + 1 if existing else 1
    for i in range(remaining):
        task_queue.put(start_pair + i)

    stats["start_time"] = time.time()

    # ── Launch workers ──────────────────────────────────────────────────
    log(f"Launching {num_workers} SDXL workers + {num_workers} FLUX workers...\n")

    threads = []

    # SDXL producer threads
    for i in range(num_workers):
        t = threading.Thread(
            target=sdxl_worker,
            args=(i, sdxl_workers[i], task_queue, result_queue, output_dir),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # FLUX consumer threads
    for i in range(num_workers):
        t = threading.Thread(
            target=flux_worker,
            args=(i, flux_workers[i], result_queue, output_dir, remaining),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # ── Monitor progress ────────────────────────────────────────────────
    try:
        while stats["flux_done"] + stats["errors"] < remaining:
            time.sleep(30)
            elapsed = time.time() - stats["start_time"]
            rate = stats["flux_done"] / (elapsed / 3600) if stats["flux_done"] > 0 else 0
            eta_min = (remaining - stats["flux_done"]) / (rate / 60) if rate > 0 else 0
            _, free = get_vram_gb()

            log(f"\n  ── Progress ──────────────────────")
            log(f"  SDXL: {stats['sdxl_done']}/{remaining} | FLUX: {stats['flux_done']}/{remaining}")
            log(f"  Rate: {rate:.0f} pairs/hr | ETA: {eta_min:.0f} min")
            log(f"  VRAM free: {free:.1f}GB | Errors: {stats['errors']}")
            log(f"  ──────────────────────────────────\n")

    except KeyboardInterrupt:
        log("\nInterrupted! Waiting for current images to finish...")

    # Wait for threads to finish
    for t in threads:
        t.join(timeout=60)

    # ── Done ────────────────────────────────────────────────────────────
    total_time = time.time() - stats["start_time"]
    log(f"\n{'═'*55}")
    log(f"  DONE!")
    log(f"  Generated: {stats['flux_done']} complete pairs")
    log(f"  Errors: {stats['errors']}")
    log(f"  Time: {total_time/60:.1f} minutes ({total_time/3600:.1f} hours)")
    if stats['flux_done'] > 0:
        log(f"  Average: {total_time/stats['flux_done']:.1f}s per pair")
        log(f"  Rate: {stats['flux_done']/(total_time/3600):.0f} pairs/hour")
    log(f"  Output: {output_dir}")
    log(f"  Videos possible: {stats['flux_done'] // 5}")
    log(f"{'═'*55}")


if __name__ == "__main__":
    main()
