#!/usr/bin/env python3
"""
Mock Failure Event Simulator
=============================
Replays the cascading RDBMS → MCP outage scenario defined in seed_data.json.

Usage:
    python scripts/mock_failure_event.py [--host http://localhost:8000] [--burst] [--fast]

Options:
    --host   Backend base URL (default: http://localhost:8000)
    --burst  Also send 100 duplicate signals to CACHE_CLUSTER_01 to demonstrate debouncing
    --fast   Skip wave delays — send all signals immediately
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx first:  pip install httpx")
    sys.exit(1)


SEED_FILE = Path(__file__).parent / "seed_data.json"


async def send_signal(client: httpx.AsyncClient, base_url: str, payload: dict, label: str = "") -> bool:
    try:
        resp = await client.post(f"{base_url}/api/signals", json=payload, timeout=10)
        status = "✅" if resp.status_code == 202 else "⚠️"
        print(f"  {status} {payload['component_id']} [{payload['severity']}] {label}")
        return resp.status_code == 202
    except Exception as exc:
        print(f"  ❌ {payload['component_id']}: {exc}")
        return False


async def run_scenario(base_url: str, fast: bool, burst: bool) -> None:
    seed = json.loads(SEED_FILE.read_text())
    print(f"\n{'='*60}")
    print(f"  Scenario: {seed['description']}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient() as client:
        # Verify backend is up
        try:
            r = await client.get(f"{base_url}/health", timeout=5)
            health = r.json()
            print(f"Backend health: {health['status']}")
            if health['status'] != 'healthy':
                print(f"Warning: some backends degraded: {health['checks']}")
        except Exception as exc:
            print(f"❌ Cannot reach backend at {base_url}: {exc}")
            print("   Make sure the backend is running: docker-compose up backend")
            return

        for wave in seed["waves"]:
            print(f"\n[WAVE] {wave['name']}")

            if not fast and wave["delay_seconds"] > 0:
                print(f"  ⏳ Waiting {wave['delay_seconds']}s...")
                await asyncio.sleep(wave["delay_seconds"])

            tasks = [
                send_signal(client, base_url, signal)
                for signal in wave["signals"]
            ]
            results = await asyncio.gather(*tasks)
            sent = sum(results)
            print(f"  → {sent}/{len(results)} signals accepted")

        if burst:
            print("\n[BURST] Sending 100 signals to CACHE_CLUSTER_01 (debounce demo)")
            print("        Only 1 work item should be created for all 100 signals...")
            t0 = time.monotonic()
            tasks = [
                send_signal(
                    client, base_url,
                    {
                        "component_id": "CACHE_CLUSTER_01",
                        "component_type": "CACHE",
                        "error_type": "BURST_TEST",
                        "severity": "MEDIUM",
                        "message": f"Burst test signal #{i}",
                        "metadata": {"burst_index": i},
                    },
                    label=f"#{i}",
                )
                for i in range(100)
            ]
            results = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - t0
            accepted = sum(results)
            print(f"\n  → {accepted}/100 signals accepted in {elapsed:.2f}s")
            print(f"  → Check the dashboard — CACHE_CLUSTER_01 should show 1 work item with 100+ signals")

        print(f"\n{'='*60}")
        print("  Simulation complete! Open http://localhost:3000 to view the dashboard.")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="IMS Mock Failure Event Simulator")
    parser.add_argument("--host", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--burst", action="store_true", help="Send 100 signals to one component (debounce demo)")
    parser.add_argument("--fast", action="store_true", help="Skip wave delays")
    args = parser.parse_args()

    asyncio.run(run_scenario(args.host, fast=args.fast, burst=args.burst))


if __name__ == "__main__":
    main()
