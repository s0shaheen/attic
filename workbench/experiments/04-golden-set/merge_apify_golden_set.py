#!/usr/bin/env python
"""Merge Apify enrichment output into golden set annotation templates.

Takes Apify output JSON (array of enriched items), matches by video_id,
and populates the `apify` fields in golden_set_template.json.

Usage:
    python workbench/experiments/04-golden-set/merge_apify_golden_set.py workbench/data/apify_output.json
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "results" / "golden_set_template.json"


def extract_apify_fields(apify_item: dict) -> dict:
    """Extract and normalize relevant fields from an Apify result."""
    video_meta = apify_item.get("videoMeta") or {}
    music_meta = apify_item.get("musicMeta") or {}

    # Hashtags: Apify returns array of objects with "name" key
    raw_hashtags = apify_item.get("hashtags") or []
    hashtags = [h["name"] if isinstance(h, dict) else str(h) for h in raw_hashtags]

    # Comments: inline array if commentsPerPost was set, otherwise empty
    raw_comments = apify_item.get("comments") or []
    comments_top10 = [c.get("text", "") for c in raw_comments[:10]] if raw_comments else None

    # Slideshow detection
    is_slideshow = apify_item.get("isSlideshow", False)
    image_count = apify_item.get("imageCount")

    # Subtitle links exist but text isn't inline — note availability
    subtitle_links = video_meta.get("subtitleLinks") or []
    has_subtitle_links = len(subtitle_links) > 0

    return {
        "caption": apify_item.get("text"),
        "hashtags": hashtags if hashtags else None,
        "music_metadata": music_meta.get("musicName"),
        "duration_seconds": video_meta.get("duration"),
        "is_slideshow": is_slideshow,
        "image_count": image_count,
        "subtitle_text": None,  # requires separate download from subtitleLinks
        "comments_top10": comments_top10,
        "thumbnail_url": video_meta.get("coverUrl"),
        "_has_subtitle_links": has_subtitle_links,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python merge_apify_golden_set.py <apify_output.json>")
        sys.exit(1)

    apify_path = Path(sys.argv[1])
    if not apify_path.exists():
        print(f"ERROR: Apify output file not found: {apify_path}")
        sys.exit(1)

    apify_items = json.loads(apify_path.read_text())
    template = json.loads(TEMPLATE_PATH.read_text())

    # Build lookup by video ID (Apify `id` field is the video ID as string)
    apify_by_id: dict[str, dict] = {}
    for item in apify_items:
        vid_id = str(item.get("id", ""))
        if vid_id:
            apify_by_id[vid_id] = item

    # Match and merge
    matched = 0
    unmatched_ids: list[str] = []
    subtitle_link_count = 0
    slideshow_count = 0
    has_caption_count = 0

    for entry in template:
        vid_id = entry["id"]
        apify_item = apify_by_id.get(vid_id)

        if not apify_item:
            unmatched_ids.append(vid_id)
            continue

        fields = extract_apify_fields(apify_item)

        # Track stats before removing internal field
        if fields.pop("_has_subtitle_links"):
            subtitle_link_count += 1
        if fields.get("is_slideshow"):
            slideshow_count += 1
        if fields.get("caption"):
            has_caption_count += 1

        entry["apify"] = fields
        matched += 1

    # Write merged result
    TEMPLATE_PATH.write_text(json.dumps(template, indent=2))

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(template)
    print("=" * 60)
    print("APIFY MERGE SUMMARY")
    print("=" * 60)

    print(f"\nMatch rate: {matched}/{total} ({matched/total:.0%})")
    if unmatched_ids:
        print(f"Unmatched (deleted/private): {len(unmatched_ids)}")
        for vid_id in unmatched_ids:
            # Find collection for this ID
            coll = next((e["collection"] for e in template if e["id"] == vid_id), "?")
            print(f"  {vid_id}  ({coll})")

    print(f"\nContent stats:")
    print(f"  With captions:       {has_caption_count}/{matched}")
    print(f"  Slideshows:          {slideshow_count}/{matched}")
    print(f"  With subtitle links: {subtitle_link_count}/{matched} (text not yet downloaded)")

    # Per-collection breakdown
    print(f"\nPer collection:")
    coll_stats: dict[str, dict] = {}
    for entry in template:
        c = entry["collection"]
        if c not in coll_stats:
            coll_stats[c] = {"total": 0, "matched": 0}
        coll_stats[c]["total"] += 1
        if entry["apify"].get("caption") is not None:
            coll_stats[c]["matched"] += 1

    for coll_name in sorted(coll_stats.keys()):
        s = coll_stats[coll_name]
        print(f"  {coll_name:25s}  {s['matched']:2d}/{s['total']:2d} enriched")

    print(f"\nMerged result written to {TEMPLATE_PATH.relative_to(REPO_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
