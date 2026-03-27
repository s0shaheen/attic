#!/usr/bin/env python
"""Classify a batch of videos and output structured results.

Usage:
    python workbench/tools/classify_batch.py workbench/data/sample-videos.json
    python workbench/tools/classify_batch.py workbench/data/sample-videos.json --output results.json
    python workbench/tools/classify_batch.py workbench/data/sample-videos.json --limit 10
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os
from app.services.gemini import classify as gemini_classify
from app.services.ontology import validate_classification


async def classify_one(item: dict, api_key: str) -> dict:
    """Classify a single item and return structured result."""
    start = time.time()
    try:
        result = await gemini_classify(
            api_key=api_key,
            caption=item.get("caption"),
            subtitle=item.get("subtitle"),
            hashtags=item.get("hashtags"),
            creator_username=item.get("creator"),
            music_name=item.get("music"),
        )
        elapsed = time.time() - start

        if not result.success:
            return {"id": item.get("id", "unknown"), "success": False, "error": result.error, "elapsed": elapsed}

        validated = validate_classification(result.raw_classification or {})
        return {
            "id": item.get("id", "unknown"),
            "success": True,
            "raw": result.raw_classification,
            "tier1": validated.tier1,
            "tier2": validated.tier2,
            "confidence": validated.confidence,
            "elapsed": elapsed,
        }
    except Exception as e:
        return {"id": item.get("id", "unknown"), "success": False, "error": str(e), "elapsed": time.time() - start}


async def main():
    if len(sys.argv) < 2:
        print("Usage: python classify_batch.py <input.json> [--output results.json] [--limit N]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    items = json.loads(input_path.read_text())

    output_path = None
    limit = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = Path(sys.argv[i + 1])
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if limit:
        items = items[:limit]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in workbench/.env")
        sys.exit(1)

    print(f"Classifying {len(items)} items...")
    results = []
    for i, item in enumerate(items):
        result = await classify_one(item, api_key)
        status = "OK" if result["success"] else f"FAIL: {result.get('error', 'unknown')}"
        print(f"  [{i+1}/{len(items)}] {item.get('id', 'unknown')[:20]:20s} {status} ({result['elapsed']:.1f}s)")
        results.append(result)

    successes = sum(1 for r in results if r["success"])
    print(f"\nDone: {successes}/{len(results)} succeeded")

    if output_path:
        output_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"Results saved to {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
