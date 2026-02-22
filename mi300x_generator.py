#!/usr/bin/env python3
"""
MI300X Max-VRAM Image Generator (ROCm)

Maximizes 192GB HBM3 on AMD MI300X for mass parallel SDXL + FLUX generation.
Built for ROCm/HIP — uses bfloat16 (native on MI300X), configures HIP memory
allocator, enables flash attention via SDPA, and uses torch.compile() with
Triton backend for ROCm kernel fusion.

Loads each model ONCE, creates N lightweight pipeline clones sharing GPU weights,
runs them in parallel threads across the MI300X's 8 XCDs (compute dies).
Auto-detects optimal worker count to fill ~90% of free VRAM.

Usage:
    pip install diffusers[torch] transformers accelerate safetensors sentencepiece protobuf
    python mi300x_generator.py                # auto-fill VRAM (default)
    python mi300x_generator.py --workers 12   # force 12 workers
    python mi300x_generator.py --target 1000  # generate 1000 pairs
"""

# ── ROCm environment (must be set BEFORE importing torch) ───────────────
import os

# HIP memory allocator: expandable segments reduces fragmentation on MI300X
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")
# MI300X = gfx942 architecture
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "9.4.2")
# Enable Triton flash attention for ROCm SDPA
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

import torch
import gc
import sys
import copy
import time
import random
import argparse
import threading
from datetime import datetime
from queue import Queue, Empty
from PIL import Image

# ── Config ──────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.expanduser("~/spot_difference_images")
IMAGE_SIZE = 1024
SDXL_STEPS = 30
FLUX_STEPS = 24
SDXL_GUIDANCE = 7.5
FLUX_GUIDANCE = 2.5
# MI300X has native bfloat16 support — faster and more numerically stable than fp16
DTYPE = torch.bfloat16

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
stats = {"sdxl_done": 0, "flux_done": 0, "errors": 0, "start_time": 0}


def get_vram_gb():
    """Get total and free VRAM in GB via HIP (torch.cuda maps to HIP on ROCm)."""
    if torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        used = torch.cuda.memory_allocated(0) / (1024**3)
        return total, total - used
    return 0, 0


def log(msg):
    with print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def setup_rocm():
    """Configure ROCm/HIP runtime for MI300X."""
    if not torch.cuda.is_available():
        log("ERROR: No GPU detected. Is ROCm installed?")
        log("  Check: rocm-smi")
        log("  Check: python -c \"import torch; print(torch.cuda.is_available())\"")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    log(f"GPU: {gpu_name}")

    # Verify we're on ROCm, not CUDA
    is_rocm = hasattr(torch.version, 'hip') and torch.version.hip is not None
    if is_rocm:
        log(f"ROCm/HIP: {torch.version.hip}")
    else:
        log("WARNING: Running on CUDA, not ROCm. This script is optimized for MI300X/ROCm.")
        log("  It will still work, but bfloat16 and HIP settings may differ.")

    # Enable flash attention via scaled dot product attention (SDPA)
    # On ROCm this uses the Triton flash attention backend
    torch.backends.cuda.enable_flash_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    log("  Flash attention (SDPA): enabled")

    total, free = get_vram_gb()
    log(f"  VRAM: {total:.1f}GB total, {free:.1f}GB free")
    log(f"  Dtype: bfloat16 (native MI300X)")
    log(f"  HIP memory allocator: expandable_segments={os.environ.get('PYTORCH_HIP_ALLOC_CONF', 'default')}")

    return is_rocm


def clone_sdxl(base_pipe):
    """Create a lightweight SDXL pipeline clone sharing GPU model weights."""
    from diffusers import StableDiffusionXLPipeline
    return StableDiffusionXLPipeline(
        unet=base_pipe.unet,
        vae=base_pipe.vae,
        text_encoder=base_pipe.text_encoder,
        text_encoder_2=base_pipe.text_encoder_2,
        tokenizer=base_pipe.tokenizer,
        tokenizer_2=base_pipe.tokenizer_2,
        scheduler=copy.deepcopy(base_pipe.scheduler),
    )


def clone_flux(base_pipe):
    """Create a lightweight FLUX pipeline clone sharing GPU model weights."""
    from diffusers import FluxKontextPipeline
    return FluxKontextPipeline(
        transformer=base_pipe.transformer,
        text_encoder=base_pipe.text_encoder,
        text_encoder_2=base_pipe.text_encoder_2,
        tokenizer=base_pipe.tokenizer,
        tokenizer_2=base_pipe.tokenizer_2,
        vae=base_pipe.vae,
        scheduler=copy.deepcopy(base_pipe.scheduler),
    )


def auto_worker_count(free_vram_gb, target_usage=0.90):
    """
    Calculate how many workers to run to fill target_usage of free VRAM.
    Each worker pair needs inference buffers: ~4GB SDXL + ~7GB FLUX in bf16.
    """
    per_worker = 4.0 + 7.0  # bf16 uses slightly less than fp16 for activations
    usable = free_vram_gb * target_usage
    count = max(1, int(usable / per_worker))
    return count


def load_models(num_workers, compile_models=True):
    """Load base models in bf16, optionally torch.compile, then create N clones."""
    from diffusers import StableDiffusionXLPipeline, FluxKontextPipeline

    total_vram, free_vram = get_vram_gb()

    # Load base SDXL in bfloat16
    log("Loading SDXL base model (bfloat16)...")
    sdxl_base = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=DTYPE,
        use_safetensors=True,
    ).to("cuda")

    _, free = get_vram_gb()
    log(f"  SDXL loaded. {free:.1f}GB VRAM free")

    # Load base FLUX Kontext in bfloat16
    log("Loading FLUX Kontext base model (bfloat16)...")
    flux_base = FluxKontextPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-Kontext-dev",
        torch_dtype=DTYPE,
    ).to("cuda")

    _, free = get_vram_gb()
    log(f"  FLUX loaded. {free:.1f}GB VRAM free")

    # torch.compile() with Triton backend — fuses ROCm kernels for ~20-40% speedup
    if compile_models:
        log("Compiling models with torch.compile (Triton/ROCm)...")
        log("  (First inference will be slow due to compilation, then much faster)")
        try:
            sdxl_base.unet = torch.compile(sdxl_base.unet, mode="reduce-overhead")
            flux_base.transformer = torch.compile(flux_base.transformer, mode="reduce-overhead")
            log("  Compilation registered (will JIT on first run)")
        except Exception as e:
            log(f"  torch.compile failed (non-fatal, running without): {e}")

    # Auto-detect worker count
    if num_workers == 0:
        num_workers = auto_worker_count(free)
        log(f"  Auto-detected: {num_workers} workers to fill {free:.1f}GB free VRAM")

    # Create worker clones (share compiled weights, own schedulers)
    log(f"Creating {num_workers} SDXL + {num_workers} FLUX worker clones...")
    sdxl_workers = [clone_sdxl(sdxl_base) for _ in range(num_workers)]
    flux_workers = [clone_flux(flux_base) for _ in range(num_workers)]

    _, free = get_vram_gb()
    log(f"  {num_workers} workers ready. {free:.1f}GB VRAM free for inference")

    return sdxl_workers, flux_workers, num_workers


def sdxl_worker(worker_id, sdxl_pipe, task_queue, result_queue, output_dir):
    """Worker thread: pulls pair numbers from queue, generates SDXL originals."""
    # Each worker gets its own HIP stream for concurrent kernel dispatch
    stream = torch.cuda.Stream()
    while True:
        try:
            pair_num = task_queue.get(timeout=2)
        except Empty:
            return

        prompt = random.choice(SCENE_PROMPTS)
        seed = random.randint(0, 2**32 - 1)
        filepath = os.path.join(output_dir, f"pair_{pair_num:04d}_original.png")

        try:
            with torch.cuda.stream(stream), torch.no_grad():
                gen = torch.Generator(device="cuda").manual_seed(seed)
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
            log(f"  [S{worker_id}] SDXL #{pair_num} done ({stats['sdxl_done']} total)")

        except torch.cuda.OutOfMemoryError:
            log(f"  [S{worker_id}] SDXL #{pair_num} OOM — skipping, will retry if rerun")
            gc.collect()
            torch.cuda.empty_cache()
            stats["errors"] += 1
        except Exception as e:
            log(f"  [S{worker_id}] SDXL #{pair_num} ERROR: {e}")
            stats["errors"] += 1

        task_queue.task_done()


def flux_worker(worker_id, flux_pipe, result_queue, output_dir, total_target):
    """Worker thread: takes SDXL results, generates FLUX modifications."""
    stream = torch.cuda.Stream()
    while stats["flux_done"] + stats["errors"] < total_target:
        try:
            pair_num, orig_img = result_queue.get(timeout=5)
        except Empty:
            if stats["sdxl_done"] + stats["errors"] >= total_target:
                return
            continue

        modified_path = os.path.join(output_dir, f"pair_{pair_num:04d}_modified.png")
        instruction = random.choice(EDIT_INSTRUCTIONS)

        try:
            with torch.cuda.stream(stream), torch.no_grad():
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
            log(f"  [F{worker_id}] FLUX #{pair_num} done ({stats['flux_done']} complete | {rate:.0f}/hr)")

        except torch.cuda.OutOfMemoryError:
            log(f"  [F{worker_id}] FLUX #{pair_num} OOM — skipping")
            gc.collect()
            torch.cuda.empty_cache()
            stats["errors"] += 1
        except Exception as e:
            log(f"  [F{worker_id}] FLUX #{pair_num} ERROR: {e}")
            stats["errors"] += 1

        result_queue.task_done()


def main():
    parser = argparse.ArgumentParser(description="MI300X Max-VRAM Image Generator (ROCm)")
    parser.add_argument("--workers", type=int, default=0,
                        help="Number of parallel workers (0=auto-fill VRAM, default: 0)")
    parser.add_argument("--target", type=int, default=500,
                        help="Total pairs to generate (default: 500)")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR,
                        help="Output directory")
    parser.add_argument("--no-compile", action="store_true",
                        help="Disable torch.compile (faster startup, slower inference)")
    parser.add_argument("--budget", type=float, default=298.0,
                        help="Max dollars to spend before auto-shutdown (default: 298, keeps $2 buffer)")
    parser.add_argument("--cost-per-hour", type=float, default=15.92,
                        help="Hourly cost of the droplet (default: 15.92 for 8xMI300X)")
    args = parser.parse_args()

    num_workers = args.workers
    target = args.target
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # ── ROCm setup ──────────────────────────────────────────────────────
    log("═══════════════════════════════════════════════════════")
    log("  MI300X Max-VRAM Generator (ROCm/HIP)")
    log("═══════════════════════════════════════════════════════\n")

    is_rocm = setup_rocm()

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

    max_hours = args.budget / args.cost_per_hour
    log(f"\n  Workers: {'AUTO (fill VRAM)' if num_workers == 0 else f'{num_workers} SDXL + {num_workers} FLUX'}")
    log(f"  Target: {remaining} pairs ({target} total, {len(existing)} exist)")
    log(f"  Output: {output_dir}")
    log(f"  Compile: {'no' if args.no_compile else 'yes (Triton/ROCm)'}")
    log(f"  Budget: ${args.budget:.2f} (${args.cost_per_hour:.2f}/hr = {max_hours:.1f} hours max)\n")

    # ── Load models + create worker clones ──────────────────────────────
    sdxl_workers, flux_workers, num_workers = load_models(
        num_workers, compile_models=not args.no_compile
    )

    # ── Setup queues ────────────────────────────────────────────────────
    task_queue = Queue()
    result_queue = Queue(maxsize=num_workers * 3)

    start_pair = max(existing) + 1 if existing else 1
    for i in range(remaining):
        task_queue.put(start_pair + i)

    stats["start_time"] = time.time()

    # ── Launch workers ──────────────────────────────────────────────────
    log(f"Launching {num_workers} SDXL + {num_workers} FLUX workers across MI300X XCDs...\n")

    threads = []

    for i in range(num_workers):
        t = threading.Thread(
            target=sdxl_worker,
            args=(i, sdxl_workers[i], task_queue, result_queue, output_dir),
            daemon=True,
        )
        t.start()
        threads.append(t)

    for i in range(num_workers):
        t = threading.Thread(
            target=flux_worker,
            args=(i, flux_workers[i], result_queue, output_dir, remaining),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # ── Monitor progress + budget tracking ──────────────────────────────
    budget_exceeded = False
    try:
        while stats["flux_done"] + stats["errors"] < remaining:
            time.sleep(30)
            elapsed = time.time() - stats["start_time"]
            elapsed_hours = elapsed / 3600
            spent = elapsed_hours * args.cost_per_hour
            remaining_budget = args.budget - spent
            rate = stats["flux_done"] / elapsed_hours if stats["flux_done"] > 0 else 0
            eta_min = (remaining - stats["flux_done"]) / (rate / 60) if rate > 0 else 0
            _, free = get_vram_gb()

            log(f"\n  ── Progress ──────────────────────")
            log(f"  SDXL: {stats['sdxl_done']}/{remaining} | FLUX: {stats['flux_done']}/{remaining}")
            log(f"  Rate: {rate:.0f} pairs/hr | ETA: {eta_min:.0f} min")
            log(f"  VRAM free: {free:.1f}GB | Errors: {stats['errors']}")
            log(f"  BUDGET: ${spent:.2f} spent / ${args.budget:.2f} | ${remaining_budget:.2f} left ({remaining_budget/args.cost_per_hour*60:.0f} min)")
            log(f"  ──────────────────────────────────\n")

            # Auto-stop 10 minutes before budget runs out (buffer for FLUX to finish)
            if remaining_budget < args.cost_per_hour * (10/60):
                log(f"  BUDGET WARNING: Only ${remaining_budget:.2f} left!")
                log(f"  Stopping SDXL workers — letting FLUX finish current batch...")
                budget_exceeded = True
                # Drain the task queue so SDXL workers stop picking up new work
                while not task_queue.empty():
                    try:
                        task_queue.get_nowait()
                        task_queue.task_done()
                    except Empty:
                        break
                break

    except KeyboardInterrupt:
        log("\nInterrupted! Waiting for current images to finish...")

    for t in threads:
        t.join(timeout=60)

    # Wait for in-flight FLUX work to finish (up to 5 min)
    if budget_exceeded:
        log("Waiting up to 5 min for in-flight FLUX images to finish...")
        deadline = time.time() + 300
        while not result_queue.empty() and time.time() < deadline:
            time.sleep(10)

    # ── Done ────────────────────────────────────────────────────────────
    total_time = time.time() - stats["start_time"]
    total_spent = (total_time / 3600) * args.cost_per_hour
    log(f"\n{'═'*55}")
    log(f"  DONE!{'  (budget limit reached)' if budget_exceeded else ''}")
    log(f"  Generated: {stats['flux_done']} complete pairs")
    log(f"  Errors: {stats['errors']}")
    log(f"  Time: {total_time/60:.1f} minutes ({total_time/3600:.1f} hours)")
    log(f"  Cost: ${total_spent:.2f} / ${args.budget:.2f} budget")
    if stats["flux_done"] > 0:
        log(f"  Average: {total_time/stats['flux_done']:.1f}s per pair (${total_spent/stats['flux_done']:.3f}/pair)")
        log(f"  Rate: {stats['flux_done']/(total_time/3600):.0f} pairs/hour")
    log(f"  Output: {output_dir}")
    log(f"  Videos possible: {stats['flux_done'] // 5}")
    log(f"{'═'*55}")
    if budget_exceeded:
        log("\n  IMPORTANT: Destroy the droplet NOW to stop billing!")
        log("  AMD Cloud Console → Droplets → Destroy")


if __name__ == "__main__":
    main()
