#!/usr/bin/env python
"""Assemble the golden set from annotated items + v2 experiment items.

Merges user annotations (exported from the annotator UI) with the 47 v2
experiment items. Deduplicates by video ID — for overlaps, prefers the
favorites Apify data but keeps v2 reference results.

Usage:
    python workbench/experiments/04-golden-set/assemble_golden_set.py workbench/data/golden_set_annotated.json
    python workbench/experiments/04-golden-set/assemble_golden_set.py workbench/data/golden_set_annotated.json --annotated-only
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "workbench" / "data"
V2_PATH = REPO_ROOT / "workbench" / "experiments" / "02-vision-analysis" / "results" / "v2_items_converted.json"
OUTPUT_PATH = DATA_DIR / "golden_set.json"


def is_annotated(item: dict) -> bool:
    """Check if an item has meaningful human annotations."""
    h = item.get("human", {})
    return bool(h.get("description") or h.get("search_queries") or h.get("save_reason"))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python assemble_golden_set.py <annotated_export.json> [--annotated-only]")
        sys.exit(1)

    annotated_path = Path(sys.argv[1])
    annotated_only_flag = "--annotated-only" in sys.argv

    if not annotated_path.exists():
        print(f"ERROR: Annotated file not found: {annotated_path}")
        sys.exit(1)

    # Load annotated items (from UI export — includes all 394 but only some annotated)
    all_exported = json.loads(annotated_path.read_text())

    # Filter to only annotated items
    annotated = [i for i in all_exported if is_annotated(i)]
    print(f"Annotated items from export: {len(annotated)}")

    # Load v2 items
    v2_items = json.loads(V2_PATH.read_text())
    print(f"V2 experiment items: {len(v2_items)}")

    # Build by ID — annotated items take priority
    by_id: dict[str, dict] = {}

    # Add v2 items first (lower priority)
    if not annotated_only_flag:
        for item in v2_items:
            by_id[item["id"]] = item

    # Add annotated items (override v2 if overlap, but keep v2 reference data)
    for item in annotated:
        vid_id = item["id"]
        if vid_id in by_id:
            # Overlap: keep annotated item but merge v2 reference data
            v2_item = by_id[vid_id]
            item["v2_perception"] = v2_item.get("v2_perception")
            item["v2_classification_vision"] = v2_item.get("v2_classification_vision")
            item["v2_classification_text"] = v2_item.get("v2_classification_text")
        by_id[vid_id] = item

    golden_set = list(by_id.values())

    # Sort: annotated first, then v2-only
    golden_set.sort(key=lambda x: (0 if is_annotated(x) else 1, x.get("collection", ""), x["id"]))

    OUTPUT_PATH.write_text(json.dumps(golden_set, indent=2))

    # Summary
    n_annotated = sum(1 for i in golden_set if is_annotated(i))
    n_v2_only = len(golden_set) - n_annotated
    collections = {}
    for i in golden_set:
        c = i.get("collection", "unknown")
        collections[c] = collections.get(c, 0) + 1

    print(f"\nGolden set assembled: {len(golden_set)} items")
    print(f"  Annotated:  {n_annotated}")
    print(f"  V2-only:    {n_v2_only}")
    print(f"\nBy collection:")
    for coll in sorted(collections.keys()):
        print(f"  {coll:25s}  {collections[coll]}")
    print(f"\nOutput: {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
