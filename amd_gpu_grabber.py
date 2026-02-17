#!/usr/bin/env python3
"""
AMD Developer Cloud GPU Auto-Grabber

Polls the AMD/DigitalOcean API every 60 seconds and instantly creates
an MI300X droplet the moment GPU capacity becomes available.

Usage:
    export AMD_TOKEN="your-api-token-here"
    python amd_gpu_grabber.py

    # Or pass token directly:
    python amd_gpu_grabber.py --token dop_v1_xxxxx

    # Custom poll interval:
    python amd_gpu_grabber.py --interval 30
"""

import os
import sys
import time
import json
import argparse
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

API_BASE = "https://api-amd.digitalocean.com/v2"

# MI300X droplet config (from the AMD Cloud console)
DROPLET_CONFIG = {
    "size": "gpu-mi300x8-1536gb-devcloud",
    "image": "ubuntu-25-10-x64",
    "ssh_keys": [54161895],
    "backups": False,
    "ipv6": False,
    "monitoring": False,
    "tags": ["auto-grabbed"],
    "user_data": "",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def api_request(method, endpoint, token, data=None):
    """Make an API request using curl (no extra dependencies needed)."""
    cmd = [
        "curl", "-s", "-X", method,
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {token}",
        "-w", "\n%{http_code}",
    ]
    if data:
        cmd += ["-d", json.dumps(data)]
    cmd.append(f"{API_BASE}{endpoint}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout.strip()

    # Split response body and status code
    lines = output.rsplit("\n", 1)
    if len(lines) == 2:
        body, status = lines
        try:
            return json.loads(body), int(status)
        except (json.JSONDecodeError, ValueError):
            return {"raw": body}, int(status) if status.isdigit() else 0
    return {"raw": output}, 0


def get_regions(token):
    """Get available datacenter regions."""
    data, status = api_request("GET", "/regions", token)
    if status == 200 and "regions" in data:
        return [r["slug"] for r in data["regions"] if r.get("available", False)]
    return []


def get_gpu_sizes(token):
    """Get available GPU droplet sizes and their regions."""
    data, status = api_request("GET", "/sizes", token)
    if status != 200 or "sizes" not in data:
        return []

    gpu_sizes = []
    for size in data["sizes"]:
        if "gpu" in size.get("slug", "").lower() or "mi300" in size.get("slug", "").lower():
            gpu_sizes.append({
                "slug": size["slug"],
                "regions": size.get("regions", []),
                "available": size.get("available", False),
                "price_hourly": size.get("price_hourly", 0),
                "memory": size.get("memory", 0),
                "vcpus": size.get("vcpus", 0),
                "disk": size.get("disk", 0),
                "description": size.get("description", ""),
            })
    return gpu_sizes


def try_create_droplet(token, region):
    """Attempt to create a GPU droplet in the given region."""
    config = {**DROPLET_CONFIG, "region": region, "name": f"mi300x-{region}-auto"}

    # Try to get VPC for the region
    vpcs_data, vpcs_status = api_request("GET", f"/vpcs?region={region}", token)
    if vpcs_status == 200 and "vpcs" in vpcs_data and vpcs_data["vpcs"]:
        config["vpc_uuid"] = vpcs_data["vpcs"][0]["id"]

    log(f"  Attempting to create droplet in {region}...")
    data, status = api_request("POST", "/droplets", token, config)

    if status in (200, 201, 202):
        return True, data
    else:
        error_msg = ""
        if isinstance(data, dict):
            error_msg = data.get("message", data.get("id", str(data)))
        return False, error_msg


def ssh_cmd(ip, cmd, timeout=600):
    """Run a command on the remote droplet via SSH."""
    ssh = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
        f"root@{ip}", cmd
    ]
    log(f"  [SSH] {cmd[:80]}...")
    result = subprocess.run(ssh, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and result.stderr:
        log(f"  [SSH] stderr: {result.stderr[:200]}")
    return result


def wait_for_ssh(ip, max_wait=300):
    """Wait for SSH to become available on the droplet."""
    log(f"  Waiting for SSH on {ip}...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 f"root@{ip}", "echo ready"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and "ready" in result.stdout:
                log(f"  SSH ready! ({time.time() - start:.0f}s)")
                return True
        except (subprocess.TimeoutExpired, Exception):
            pass
        time.sleep(10)
    return False


def deploy_and_run(ip, droplet_id, token):
    """Full auto-deploy: SSH in, install deps, run generator, copy images back, destroy droplet."""
    local_output = os.path.expanduser("~/spot_difference_images")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    generator_path = os.path.join(script_dir, "mi300x_generator.py")

    log(f"\n{'═'*55}")
    log(f"  AUTO-DEPLOY STARTING")
    log(f"{'═'*55}\n")

    # Step 1: Wait for SSH
    if not wait_for_ssh(ip):
        log("ERROR: SSH never became available. Check the droplet manually.")
        log(f"  ssh root@{ip}")
        return

    # Step 2: Upload the generator script
    log("Uploading mi300x_generator.py...")
    scp = subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", generator_path, f"root@{ip}:/root/"],
        capture_output=True, text=True, timeout=60
    )
    if scp.returncode != 0:
        log(f"  SCP failed: {scp.stderr}")
        return

    # Step 3: Install dependencies
    log("Installing Python dependencies (this takes a few minutes)...")
    ssh_cmd(ip,
        "pip install diffusers[torch] transformers accelerate safetensors sentencepiece protobuf",
        timeout=600
    )

    # Step 4: Run the generator
    log("\n  Starting MI300X generator...")
    log("  This will run until budget limit ($98) is reached.\n")

    # Run in foreground so we can stream output
    ssh_proc = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{ip}",
         "python /root/mi300x_generator.py --target 2000"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    # Stream output in real-time
    try:
        for line in ssh_proc.stdout:
            print(f"  [MI300X] {line}", end="", flush=True)
        ssh_proc.wait()
    except KeyboardInterrupt:
        log("\nInterrupted! Copying whatever images were generated...")

    # Step 5: Copy images back to local machine
    log(f"\nCopying images from droplet to {local_output}...")
    os.makedirs(local_output, exist_ok=True)

    rsync = subprocess.run(
        ["rsync", "-avz", "--progress",
         f"root@{ip}:/root/spot_difference_images/", f"{local_output}/"],
        capture_output=False, timeout=1800  # 30 min max for transfer
    )

    if rsync.returncode != 0:
        log("  rsync failed, trying scp...")
        subprocess.run(
            ["scp", "-o", "StrictHostKeyChecking=no", "-r",
             f"root@{ip}:/root/spot_difference_images/*", f"{local_output}/"],
            capture_output=False, timeout=1800
        )

    # Count what we got
    pairs = 0
    if os.path.isdir(local_output):
        originals = [f for f in os.listdir(local_output) if "_original.png" in f]
        modifieds = [f for f in os.listdir(local_output) if "_modified.png" in f]
        pairs = min(len(originals), len(modifieds))

    log(f"\n{'═'*55}")
    log(f"  IMAGES COPIED: {pairs} complete pairs")
    log(f"  Location: {local_output}")
    log(f"  Videos possible: {pairs // 5}")
    log(f"{'═'*55}")

    # Step 6: Destroy the droplet to stop billing
    log(f"\nDestroying droplet {droplet_id} to stop billing...")
    data, status = api_request("DELETE", f"/droplets/{droplet_id}", token)
    if status == 204:
        log("  Droplet destroyed! No more charges.")
    else:
        log(f"  WARNING: Could not destroy droplet (status {status})")
        log(f"  DESTROY IT MANUALLY: AMD Cloud Console → Droplets → Destroy")
        log(f"  Or: curl -X DELETE -H 'Authorization: Bearer $TOKEN' {API_BASE}/droplets/{droplet_id}")


def main():
    parser = argparse.ArgumentParser(description="AMD Cloud GPU Auto-Grabber")
    parser.add_argument("--token", type=str, default=None,
                        help="API token (or set AMD_TOKEN env var)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between checks (default: 60)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check availability without creating")
    parser.add_argument("--manual", action="store_true",
                        help="Don't auto-deploy, just print SSH info")
    parser.add_argument("--local-output", type=str,
                        default=os.path.expanduser("~/spot_difference_images"),
                        help="Local directory to copy images back to")
    args = parser.parse_args()

    token = args.token or os.environ.get("AMD_TOKEN")
    if not token:
        log("ERROR: No API token. Set AMD_TOKEN env var or use --token")
        log("  Get your token from: AMD Developer Cloud → API → Generate Token")
        sys.exit(1)

    log("═══════════════════════════════════════════════════════")
    log("  AMD Developer Cloud GPU Auto-Grabber")
    log(f"  Polling every {args.interval}s for MI300X availability")
    log(f"  Dry run: {args.dry_run}")
    log("═══════════════════════════════════════════════════════\n")

    # First, check what regions and sizes exist
    log("Fetching available regions and GPU sizes...")
    regions = get_regions(token)
    gpu_sizes = get_gpu_sizes(token)

    if regions:
        log(f"  Regions: {', '.join(regions)}")
    else:
        log("  No regions found via API, will try common ones")
        regions = ["tor1", "nyc1", "nyc3", "sfo3", "ams3", "sgp1", "lon1", "fra1", "blr1", "syd1"]

    if gpu_sizes:
        for gs in gpu_sizes:
            log(f"  GPU: {gs['slug']} | ${gs['price_hourly']}/hr | regions: {gs['regions']} | available: {gs['available']}")
            if gs["regions"]:
                regions = list(set(regions + gs["regions"]))
    else:
        log("  No GPU sizes found via API, using default config")

    log(f"\n  Will try regions: {', '.join(regions)}")
    log(f"  Polling starts now...\n")

    attempt = 0
    while True:
        attempt += 1
        log(f"── Attempt #{attempt} ──")

        for region in regions:
            if args.dry_run:
                log(f"  [DRY RUN] Would try region: {region}")
                continue

            success, result = try_create_droplet(token, region)

            if success:
                log(f"\n{'═'*55}")
                log(f"  GPU GRABBED! Droplet created in {region}!")
                log(f"{'═'*55}")

                droplet = result.get("droplet", {})
                droplet_id = droplet.get("id", "unknown")
                log(f"  Droplet ID: {droplet_id}")
                log(f"  Name: {droplet.get('name', 'unknown')}")
                log(f"  Region: {region}")
                log(f"  Size: {DROPLET_CONFIG['size']}")
                log(f"\n  Waiting for IP address...")

                # Poll for IP
                ip = None
                for _ in range(30):
                    time.sleep(10)
                    d_data, d_status = api_request("GET", f"/droplets/{droplet_id}", token)
                    if d_status == 200 and "droplet" in d_data:
                        networks = d_data["droplet"].get("networks", {})
                        v4 = networks.get("v4", [])
                        for net in v4:
                            if net.get("type") == "public":
                                ip = net["ip_address"]
                                log(f"\n  PUBLIC IP: {ip}")
                                break
                    if ip:
                        break

                if not ip:
                    log("  Could not get IP. Check the AMD Cloud console.")
                    return

                # ── Auto-deploy and run ─────────────────────────────
                if not args.manual:
                    deploy_and_run(ip, droplet_id, token)
                else:
                    log(f"  SSH: ssh root@{ip}")
                    log(f"  scp mi300x_generator.py root@{ip}:")
                    log(f"  ssh root@{ip} 'pip install diffusers[torch] transformers accelerate safetensors sentencepiece protobuf && python mi300x_generator.py'")
                    log(f"\n{'═'*55}")
                return

            else:
                log(f"  {region}: {result}")

        log(f"  No GPUs available. Retrying in {args.interval}s...\n")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
