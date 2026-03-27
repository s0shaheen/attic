#!/usr/bin/env python
"""Convert 47 v2 experiment items to golden set format.

Reads manifest.json and per-item result files from vision_v2/, maps to the
golden set template schema, and attaches v2 perception/classification results
as reference data.

Usage:
    python workbench/experiments/04-golden-set/convert_v2_to_golden.py
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
V2_DIR = REPO_ROOT / "workbench" / "experiments" / "02-vision-analysis" / "results" / "vision_v2"
MANIFEST_PATH = V2_DIR / "manifest.json"
RESULTS_DIR = V2_DIR / "results"
OUTPUT_PATH = SCRIPT_DIR / "results" / "v2_items_converted.json"


def load_result(stage: str, item_id: str) -> dict | None:
    """Load a per-item result file, return parsed_output or None."""
    path = RESULTS_DIR / stage / f"{item_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("parsed_output")


def convert_item(item: dict) -> dict:
    """Convert a single v2 manifest item to golden set format."""
    pid = item["platform_id"]
    ad = item.get("apify_data") or {}
    author = ad.get("authorMeta") or {}
    video_meta = ad.get("videoMeta") or {}
    music_meta = ad.get("musicMeta") or {}
    raw_hashtags = ad.get("hashtags") or []
    hashtags = [h["name"] if isinstance(h, dict) else str(h) for h in raw_hashtags]
    raw_comments = item.get("comments") or []
    comments_top10 = [c.get("text", "") for c in raw_comments[:10]] if raw_comments else None

    # Load v2 results as reference data
    perception = load_result("perception", pid)
    classify_vision = load_result("classify_5facet_vision", pid)
    classify_text = load_result("classify_5facet_text", pid)

    return {
        "id": pid,
        "url": item.get("web_url", ""),
        "creator": author.get("name", ""),
        "collection": "v2_experiment",
        "apify": {
            "caption": item.get("caption") or ad.get("text"),
            "hashtags": hashtags if hashtags else None,
            "music_metadata": music_meta.get("musicName"),
            "duration_seconds": video_meta.get("duration") or item.get("duration"),
            "is_slideshow": ad.get("isSlideshow", False),
            "image_count": len(ad.get("slideshowImageLinks") or []) or None,
            "subtitle_text": item.get("subtitle_text") or None,
            "comments_top10": comments_top10,
            "thumbnail_url": video_meta.get("coverUrl"),
        },
        "human": {
            "description": "",
            "search_queries": [],
            "topic": "",
            "affect": "",
            "key_entities": [],
            "save_reason": "",
            "difficulty": "medium",
            "failure_modes": [],
            "collection_source": "v2_experiment",
            "auto_topic": None,
            "auto_genre": None,
        },
        "human_deep": None,
        # V2 reference data — NOT ground truth, just prior pipeline output
        "v2_perception": {
            "summary": (perception or {}).get("overall_summary"),
            "entities": (perception or {}).get("entities_detected"),
            "style": (perception or {}).get("presentation_style"),
            "mood": (perception or {}).get("visual_mood"),
            "topic_hints": (perception or {}).get("topic_hints"),
            "affect_hints": (perception or {}).get("affect_hints"),
            "genre_hints": (perception or {}).get("genre_hints"),
        } if perception else None,
        "v2_classification_vision": classify_vision,
        "v2_classification_text": classify_text,
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    items = manifest["items"]
    matched = [i for i in items if i.get("matched")]

    converted = [convert_item(i) for i in matched]

    OUTPUT_PATH.write_text(json.dumps(converted, indent=2))

    # Summary
    has_perception = sum(1 for c in converted if c["v2_perception"])
    has_vision_class = sum(1 for c in converted if c["v2_classification_vision"])
    has_text_class = sum(1 for c in converted if c["v2_classification_text"])
    has_subtitles = sum(1 for c in converted if c["apify"].get("subtitle_text"))
    slideshows = sum(1 for c in converted if c["apify"].get("is_slideshow"))

    print(f"Converted {len(converted)} v2 items to golden set format")
    print(f"  With perception:       {has_perception}/{len(converted)}")
    print(f"  With vision classify:  {has_vision_class}/{len(converted)}")
    print(f"  With text classify:    {has_text_class}/{len(converted)}")
    print(f"  With subtitles:        {has_subtitles}/{len(converted)}")
    print(f"  Slideshows:            {slideshows}/{len(converted)}")
    print(f"\nOutput: {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
