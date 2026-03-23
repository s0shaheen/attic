#!/usr/bin/env python
"""Run classification evals against a golden set.

Usage:
    python workbench/scripts/run_evals.py
    python workbench/scripts/run_evals.py --verbose --save
    python workbench/scripts/run_evals.py --facet affect --verbose
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os

# Import classify_one from sibling script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_batch import classify_one

from app.services.ontology import FACET_NAMES


async def main():
    golden_path = Path(__file__).resolve().parents[1] / "data" / "golden-set.json"
    golden = json.loads(golden_path.read_text())

    if not golden:
        print("golden-set.json is empty. Add hand-labeled items first.")
        print("Format: [{\"id\": \"...\", \"caption\": \"...\", \"expected\": {\"affect\": \"funny\", ...}}]")
        sys.exit(0)

    # Parse args
    verbose = "--verbose" in sys.argv
    save = "--save" in sys.argv
    facet_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--facet" and i + 1 < len(sys.argv):
            facet_filter = sys.argv[i + 1]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in workbench/.env")
        sys.exit(1)

    print(f"Evaluating {len(golden)} items...")
    if facet_filter:
        print(f"  Filtering to facet: {facet_filter}")

    # Classify each item
    results = []
    comparisons = []
    for i, item in enumerate(golden):
        result = await classify_one(item, api_key)
        results.append(result)

        expected = item.get("expected", {})
        facets_to_check = [facet_filter] if facet_filter else list(expected.keys())

        for facet in facets_to_check:
            if facet not in expected:
                continue
            predicted = result.get("tier1", {}).get(facet, "—") if result["success"] else "ERROR"
            correct = expected[facet] == predicted
            comparisons.append({
                "id": item["id"],
                "facet": facet,
                "expected": expected[facet],
                "predicted": predicted,
                "correct": correct,
            })
            if verbose:
                status = "PASS" if correct else "FAIL"
                print(f"  [{status}] {item['id'][:20]:20s} {facet:25s} expected={expected[facet]:20s} got={predicted}")

    # Summary
    print("\n" + "=" * 70)
    print("Per-Facet Accuracy:")
    print("-" * 70)

    facet_stats = {}
    for facet in FACET_NAMES:
        facet_comps = [c for c in comparisons if c["facet"] == facet]
        if facet_comps:
            correct = sum(1 for c in facet_comps if c["correct"])
            total = len(facet_comps)
            accuracy = correct / total
            facet_stats[facet] = {"correct": correct, "total": total, "accuracy": accuracy}
            bar = "█" * int(accuracy * 20) + "░" * (20 - int(accuracy * 20))
            print(f"  {facet:25s} {bar} {accuracy:6.1%}  ({correct}/{total})")

    total_correct = sum(1 for c in comparisons if c["correct"])
    total_count = len(comparisons)
    overall = total_correct / total_count if total_count else 0

    print("-" * 70)
    print(f"  {'OVERALL':25s} {'':20s} {overall:6.1%}  ({total_correct}/{total_count})")
    print("=" * 70)

    # Save results
    if save:
        results_dir = Path(__file__).resolve().parents[1] / "evals" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = {
            "timestamp": timestamp,
            "golden_set_size": len(golden),
            "facet_stats": facet_stats,
            "overall_accuracy": overall,
            "comparisons": comparisons,
        }
        output_path = results_dir / f"eval-{timestamp}.json"
        output_path.write_text(json.dumps(output, indent=2, default=str))
        print(f"\nResults saved to {output_path}")

    # Exit code: 0 if >= 60% accuracy, 1 otherwise
    if overall < 0.6:
        print(f"\nFAIL: Overall accuracy {overall:.0%} < 60% threshold")
        sys.exit(1)
    else:
        print(f"\nPASS: Overall accuracy {overall:.0%} >= 60% threshold")


if __name__ == "__main__":
    asyncio.run(main())
