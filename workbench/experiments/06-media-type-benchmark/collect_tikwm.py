#!/usr/bin/env python
"""Collect TikTok items via TikWM and categorize by media type.

Faster and cheaper than Apify (~$0.001/item vs $0.014/item).
Grabs a small sample to get per-media-type unit data.

Usage:
    .venv/bin/python workbench/experiments/06-media-type-benchmark/collect_tikwm.py
    .venv/bin/python workbench/experiments/06-media-type-benchmark/collect_tikwm.py --sample 30
    .venv/bin/python workbench/experiments/06-media-type-benchmark/collect_tikwm.py --dry-run
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
MEDIA_DIR = SCRIPT_DIR / "media"

load_dotenv(REPO_ROOT / ".env.master")
load_dotenv(REPO_ROOT / "workbench" / ".env")
TIKWM_API_KEY = os.environ.get("TIKWM_API_KEY", "")
TIKWM_BASE = "https://api.tikwmapi.com"
DELAY_S = 0.3  # Stay under 5 RPS


def load_tiktok_urls() -> list[str]:
    export_path = (
        REPO_ROOT / "workbench" / "data" / "my-export" / "full_anonymized.json"
    )
    data = json.loads(export_path.read_text())
    favs = data["Likes and Favorites"]["Favorite Videos"]["FavoriteVideoList"]
    return [f["Link"] for f in favs if f.get("Link")]


def tikwm_get(url: str) -> dict | None:
    try:
        resp = httpx.get(
            TIKWM_BASE,
            params={"url": url},
            headers={"x-tikwmapi-key": TIKWM_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 0 and body.get("data"):
            return body["data"]
        return None
    except Exception as e:
        print(f"    ERR: {e}")
        return None


def determine_media_type(data: dict) -> str:
    images = data.get("images") or []
    if images:
        return "slideshow" if len(images) > 1 else "image"
    return "video"


def map_tikwm_item(data: dict, url: str) -> dict:
    title = data.get("title", "")
    author = data.get("author", {})
    music = data.get("music_info", {})
    media_type = determine_media_type(data)
    images = data.get("images") or []

    import re

    hashtags = re.findall(r"#(\w+)", title)
    caption = re.sub(r"\s*#\w+", "", title).strip()

    music_str = None
    if music.get("title"):
        music_str = f"{music.get('title', '')} — {music.get('author', '')}"

    video_url = data.get("play") or data.get("hdplay")
    image_urls = images if images else None

    return {
        "id": str(data.get("id", "")),
        "url": url,
        "platform": "tiktok",
        "media_type": media_type,
        "creator": author.get("unique_id", ""),
        "apify": {
            "caption": caption,
            "hashtags": hashtags,
            "is_slideshow": media_type == "slideshow",
            "thumbnail_url": data.get("cover") or data.get("origin_cover"),
            "duration_seconds": data.get("duration"),
            "music_metadata": music_str,
            "subtitle_text": None,
            "comments_top10": [],
            "video_url": video_url,
            "image_urls": image_urls,
            "image_count": len(images) if images else None,
        },
    }


def download_media(items: list[dict]) -> int:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    for item in items:
        pid = item["id"]
        apify = item.get("apify", {})
        media_type = item.get("media_type", "")

        if media_type == "video":
            video_url = apify.get("video_url")
            if video_url:
                dest = MEDIA_DIR / f"video_{pid}.mp4"
                if not dest.exists():
                    try:
                        r = httpx.get(video_url, timeout=120, follow_redirects=True)
                        r.raise_for_status()
                        dest.write_bytes(r.content)
                        downloaded += 1
                    except Exception as e:
                        print(f"    WARN video {pid}: {e}")

        if media_type == "slideshow":
            for j, url in enumerate((apify.get("image_urls") or [])[:10]):
                dest = MEDIA_DIR / f"slide_{pid}_{j:03d}.jpg"
                if not dest.exists():
                    try:
                        r = httpx.get(url, timeout=60, follow_redirects=True)
                        r.raise_for_status()
                        dest.write_bytes(r.content)
                        downloaded += 1
                    except Exception as e:
                        print(f"    WARN slide {pid}_{j}: {e}")

        thumb_url = apify.get("thumbnail_url")
        if thumb_url:
            dest = MEDIA_DIR / f"thumb_{pid}.jpg"
            if not dest.exists():
                try:
                    r = httpx.get(thumb_url, timeout=30, follow_redirects=True)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    downloaded += 1
                except Exception:
                    pass

    return downloaded


def main() -> None:
    if not TIKWM_API_KEY:
        print("ERROR: TIKWM_API_KEY not set in .env.master")
        sys.exit(1)

    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    sample_size = 50
    for i, a in enumerate(args):
        if a == "--sample" and i + 1 < len(args):
            sample_size = int(args[i + 1])

    print("=" * 60)
    print(f"TikTok via TikWM — sampling {sample_size} URLs")
    print("=" * 60)

    all_urls = load_tiktok_urls()
    print(f"  Total TikTok favorites: {len(all_urls)}")

    random.seed(42)
    sample = random.sample(all_urls, min(sample_size, len(all_urls)))
    print(f"  Estimated cost: ~${len(sample) * 0.001:.2f}")

    if dry_run:
        print("  [DRY RUN] Stopping.")
        return

    items: list[dict] = []
    success = 0
    fail = 0

    for i, url in enumerate(sample):
        data = tikwm_get(url)
        if data:
            item = map_tikwm_item(data, url)
            items.append(item)
            mt = item["media_type"]
            success += 1
            print(f"  [{i + 1}/{len(sample)}] {item['id']}: {mt}")
        else:
            fail += 1
            print(f"  [{i + 1}/{len(sample)}] FAIL: {url[:60]}")
        time.sleep(DELAY_S)

    print(f"\n  Success: {success}, Failed: {fail}")

    # Stats
    by_type: dict[str, int] = {}
    for item in items:
        mt = item["media_type"]
        by_type[mt] = by_type.get(mt, 0) + 1
    print("\n  Media type distribution:")
    for mt, count in sorted(by_type.items()):
        print(f"    {mt}: {count}")

    # Save by type
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[dict]] = {}
    for item in items:
        key = f"tiktok_{item['media_type']}"
        groups.setdefault(key, []).append(item)

    for key, group_items in sorted(groups.items()):
        path = DATA_DIR / f"{key}.json"
        path.write_text(json.dumps(group_items, indent=2, default=str))
        print(f"  Saved {key}: {len(group_items)} items → {path.name}")

    # Download media
    print(f"\n{'=' * 60}")
    print("DOWNLOADING MEDIA")
    print("=" * 60)
    count = download_media(items)
    print(f"  Downloaded {count} files")

    # Summary
    print(f"\n{'=' * 60}")
    print("DONE")
    print("=" * 60)
    print(
        f"  Total: {len(items)} items ({', '.join(f'{v} {k}' for k, v in sorted(by_type.items()))})"
    )
    print(
        "\nNext: .venv/bin/python workbench/experiments/06-media-type-benchmark/run_benchmark.py --types tiktok_video,tiktok_slideshow,tiktok_image"
    )


if __name__ == "__main__":
    main()
