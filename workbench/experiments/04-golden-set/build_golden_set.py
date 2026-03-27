#!/usr/bin/env python
"""Build golden set annotation templates from TikTok collections.

Samples items from each collection per a predefined plan, generates annotation
templates sorted by difficulty, and writes Apify input files.

Usage:
    python workbench/experiments/04-golden-set/build_golden_set.py
"""
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "workbench" / "data"
INPUT_PATH = DATA_DIR / "tiktok_favorites.json"

# Output paths
RESULTS_DIR = SCRIPT_DIR / "results"
TEMPLATE_PATH = RESULTS_DIR / "golden_set_template.json"
APIFY_INPUT_PATH = RESULTS_DIR / "apify_golden_set_input.json"
APIFY_URLS_PATH = RESULTS_DIR / "apify_golden_set_urls.txt"

# Difficulty tier ordering for sort
DIFFICULTY_ORDER = {"hard": 0, "medium": 1, "easy": 2}

# ── Collection config ────────────────────────────────────────────────────────
# Each entry: sample_size, difficulty, topic (None=VARIES), affect (None=VARIES),
#             genre (None=not auto-filled), failure_modes
COLLECTION_CONFIG: dict[str, dict] = {
    "cooking": {
        "sample_size": 8,
        "difficulty": "easy",
        "topic": "food",
        "affect": "informative",
        "genre": "recipe",
        "failure_modes": ["entity_extraction"],
    },
    "Food": {
        "sample_size": 6,
        "difficulty": "easy",
        "topic": "food",
        "affect": None,
        "genre": None,
        "failure_modes": ["entity_extraction"],
    },
    "Workout": {
        "sample_size": 6,
        "difficulty": "easy",
        "topic": "fitness",
        "affect": "informative",
        "genre": "workout",
        "failure_modes": ["entity_extraction"],
    },
    "startup building": {
        "sample_size": 6,
        "difficulty": "easy",
        "topic": "career",
        "affect": "informative",
        "genre": None,
        "failure_modes": ["opinion_as_content"],
    },
    "Career": {
        "sample_size": 5,
        "difficulty": "easy",
        "topic": "career",
        "affect": "informative",
        "genre": None,
        "failure_modes": ["opinion_as_content"],
    },
    "Edits": {
        "sample_size": 10,
        "difficulty": "hard",
        "topic": None,
        "affect": None,
        "genre": "edit",
        "failure_modes": ["audio_dependent", "low_text", "cultural_context"],
    },
    "music": {
        "sample_size": 6,
        "difficulty": "medium",
        "topic": "music",
        "affect": None,
        "genre": None,
        "failure_modes": ["audio_dependent"],
    },
    "Art": {
        "sample_size": 5,
        "difficulty": "medium",
        "topic": "art",
        "affect": None,
        "genre": None,
        "failure_modes": ["visual_only"],
    },
    "fight": {
        "sample_size": 6,
        "difficulty": "medium",
        "topic": None,
        "affect": None,
        "genre": None,
        "failure_modes": ["visual_only"],
    },
    "Clothes": {
        "sample_size": 5,
        "difficulty": "medium",
        "topic": "fashion",
        "affect": None,
        "genre": None,
        "failure_modes": ["visual_plus_entity"],
    },
    "Deep": {
        "sample_size": 8,
        "difficulty": "hard",
        "topic": None,
        "affect": None,
        "genre": None,
        "failure_modes": ["cultural_context", "opinion_as_content"],
    },
    "Cool": {
        "sample_size": 8,
        "difficulty": "hard",
        "topic": None,
        "affect": None,
        "genre": None,
        "failure_modes": ["multi_topic", "cultural_context"],
    },
    "Europe": {
        "sample_size": 6,
        "difficulty": "medium",
        "topic": "travel",
        "affect": None,
        "genre": None,
        "failure_modes": ["entity_heavy"],
    },
    "Golf": {
        "sample_size": 4,
        "difficulty": "medium",
        "topic": "sports",
        "affect": None,
        "genre": None,
        "failure_modes": ["sports_technique"],
    },
    "Tech": {
        "sample_size": 5,
        "difficulty": "medium",
        "topic": "technology",
        "affect": "informative",
        "genre": None,
        "failure_modes": ["entity_heavy"],
    },
    "Movies TV n stuff": {
        "sample_size": 4,
        "difficulty": "medium",
        "topic": "movies_tv",
        "affect": None,
        "genre": None,
        "failure_modes": ["cultural_refs"],
    },
    "Hoops": {
        "sample_size": 4,
        "difficulty": "medium",
        "topic": "sports",
        "affect": None,
        "genre": None,
        "failure_modes": ["sports"],
    },
    "attic": {
        "sample_size": 4,
        "difficulty": "hard",
        "topic": None,
        "affect": None,
        "genre": None,
        "failure_modes": ["meta_product_research"],
    },
}


def make_template(video: dict, collection_name: str, config: dict) -> dict:
    """Build a single annotation template entry."""
    topic_auto = config["topic"]
    affect_auto = config["affect"]
    genre_auto = config["genre"]

    item = {
        "id": video["video_id"],
        "url": video["url"],
        "creator": video["username"],
        "collection": collection_name,
        "apify": {
            "caption": None,
            "hashtags": None,
            "music_metadata": None,
            "duration_seconds": None,
            "is_slideshow": None,
            "image_count": None,
            "subtitle_text": None,
            "comments_top10": None,
            "thumbnail_url": None,
        },
        "human": {
            "description": "",
            "search_queries": [],
            "topic": topic_auto if topic_auto else "",
            "affect": affect_auto if affect_auto else "",
            "key_entities": [],
            "save_reason": "",
            "difficulty": config["difficulty"],
            "failure_modes": config["failure_modes"],
            "collection_source": collection_name,
            "auto_topic": topic_auto,
            "auto_genre": genre_auto,
        },
        "human_deep": None,
    }

    # Hard items get deep annotation template
    if config["difficulty"] == "hard":
        item["human_deep"] = {
            "entities": [],
            "per_slide": None,
            "actual_audio": None,
            "cultural_context": None,
            "structured_type": None,
            "structured_items": None,
        }

    return item


def main() -> None:
    data = json.loads(INPUT_PATH.read_text())
    collections = data["collections"]

    random.seed(42)

    all_items: list[dict] = []
    for coll_name, config in COLLECTION_CONFIG.items():
        coll = collections.get(coll_name)
        if not coll:
            print(f"WARNING: Collection '{coll_name}' not found in data, skipping")
            continue

        videos = coll["videos"]
        sample_size = config["sample_size"]

        if sample_size >= len(videos):
            sampled = videos
        else:
            sampled = random.sample(videos, sample_size)

        for video in sampled:
            all_items.append(make_template(video, coll_name, config))

    # Sort: hard first, then medium, then easy. Within tier, alphabetical by collection.
    all_items.sort(key=lambda x: (
        DIFFICULTY_ORDER[x["human"]["difficulty"]],
        x["collection"],
    ))

    # Write template
    TEMPLATE_PATH.write_text(json.dumps(all_items, indent=2))
    print(f"Wrote {len(all_items)} items to {TEMPLATE_PATH.relative_to(REPO_ROOT)}")

    # Write Apify input
    urls = [item["url"] for item in all_items]
    apify_input = {
        "postURLs": urls,
        "resultsPerPage": len(urls),
        "commentsPerPost": 10,
    }
    APIFY_INPUT_PATH.write_text(json.dumps(apify_input, indent=2))
    print(f"Wrote Apify input to {APIFY_INPUT_PATH.relative_to(REPO_ROOT)}")

    # Write URL list
    APIFY_URLS_PATH.write_text("\n".join(urls) + "\n")
    print(f"Wrote {len(urls)} URLs to {APIFY_URLS_PATH.relative_to(REPO_ROOT)}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("GOLDEN SET SUMMARY")
    print("=" * 60)

    # Items per difficulty tier
    tier_counts: dict[str, int] = {}
    for item in all_items:
        d = item["human"]["difficulty"]
        tier_counts[d] = tier_counts.get(d, 0) + 1

    print("\nBy difficulty:")
    for tier in ["hard", "medium", "easy"]:
        count = tier_counts.get(tier, 0)
        print(f"  {tier:8s}  {count:3d} items")
    print(f"  {'TOTAL':8s}  {len(all_items):3d} items")

    # Items per collection
    print("\nBy collection:")
    coll_counts: dict[str, int] = {}
    for item in all_items:
        c = item["collection"]
        coll_counts[c] = coll_counts.get(c, 0) + 1
    for coll_name in sorted(coll_counts.keys()):
        config = COLLECTION_CONFIG[coll_name]
        avail = collections[coll_name]["video_count"]
        print(f"  {coll_name:25s}  {coll_counts[coll_name]:2d}/{avail:2d}  ({config['difficulty']})")

    # Auto-filled vs needs manual
    auto_topic = sum(1 for i in all_items if i["human"]["auto_topic"])
    manual_topic = len(all_items) - auto_topic
    auto_affect = sum(1 for i in all_items if i["human"].get("affect"))
    manual_affect = len(all_items) - auto_affect
    auto_genre = sum(1 for i in all_items if i["human"]["auto_genre"])
    manual_genre = len(all_items) - auto_genre

    print("\nAuto-fill status:")
    print(f"  topic:   {auto_topic:3d} auto-filled, {manual_topic:3d} needs manual")
    print(f"  affect:  {auto_affect:3d} auto-filled, {manual_affect:3d} needs manual")
    print(f"  genre:   {auto_genre:3d} auto-filled, {manual_genre:3d} needs manual")

    # Deep annotation
    deep_count = sum(1 for i in all_items if i["human_deep"] is not None)
    print(f"\nDeep annotation needed: {deep_count} items")

    # Time estimates
    fast_pass_items = len(all_items)
    deep_pass_items = deep_count
    fast_time_min = fast_pass_items * 45 / 60
    deep_time_min = deep_pass_items * 180 / 60
    total_min = fast_time_min + deep_time_min

    print(f"\nEstimated annotation time:")
    print(f"  Fast pass ({fast_pass_items} items x 45s):  {fast_time_min:.0f} min")
    print(f"  Deep pass ({deep_pass_items} items x 3min): {deep_time_min:.0f} min")
    print(f"  Total:                         {total_min:.0f} min (~{total_min/60:.1f} hrs)")
    print("=" * 60)


if __name__ == "__main__":
    main()
