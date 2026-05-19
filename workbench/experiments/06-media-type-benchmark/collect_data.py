#!/usr/bin/env python
"""Phase 1: Collect and enrich items by media type for benchmarking.

Enriches a sample of TikTok and Instagram URLs via Apify, categorizes by
media type, downloads media files, and outputs benchmark-ready JSON files.

Usage:
    # Dry run — show what would be enriched, don't call Apify
    python workbench/experiments/06-media-type-benchmark/collect_data.py --dry-run

    # Full run — enrich via Apify, download media
    python workbench/experiments/06-media-type-benchmark/collect_data.py

    # TikTok only (skip Instagram)
    python workbench/experiments/06-media-type-benchmark/collect_data.py --tiktok-only

    # Instagram only (skip TikTok)
    python workbench/experiments/06-media-type-benchmark/collect_data.py --instagram-only

    # Custom sample sizes
    python workbench/experiments/06-media-type-benchmark/collect_data.py --tt-sample 100 --ig-sample 50

Estimated cost: ~$4-5 on Apify Starter plan
Requires: APIFY_API_TOKEN in workbench/.env or .env.master
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

load_dotenv(REPO_ROOT / "workbench" / ".env")
load_dotenv(REPO_ROOT / ".env.master")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

APIFY_TT_ACTOR = "clockworks~tiktok-scraper"
APIFY_IG_ACTOR = "apify~instagram-scraper"
APIFY_POLL_S = 10
APIFY_MAX_WAIT_S = 900

# Target: enough items of each type to get 15+ per media_type
TT_SAMPLE_SIZE = 200  # Expect ~48 slideshows at 24% rate
IG_SAMPLE_SIZE = 100  # 50 reels + 50 posts


def load_tiktok_urls() -> list[str]:
    """Load TikTok favorite URLs from the data export."""
    export_path = (
        REPO_ROOT / "workbench" / "data" / "my-export" / "full_anonymized.json"
    )
    data = json.loads(export_path.read_text())
    favs = data["Likes and Favorites"]["Favorite Videos"]["FavoriteVideoList"]
    return [f["Link"] for f in favs if f.get("Link")]


def load_instagram_urls() -> tuple[list[str], list[str]]:
    """Load Instagram saved post URLs, split into reels and posts."""
    ig_path = REPO_ROOT / "workbench" / "data" / "instagram_saved_posts.json"
    data = json.loads(ig_path.read_text())
    items = data.get("saved_saved_media", [])

    reels, posts = [], []
    for item in items:
        href = item.get("string_map_data", {}).get("Saved on", {}).get("href", "")
        if not href:
            continue
        if "/reel/" in href:
            reels.append(href)
        elif "/p/" in href:
            posts.append(href)
    return reels, posts


def run_apify_batch(actor_id: str, urls: list[str], platform: str) -> list[dict]:
    """Run an Apify actor on a batch of URLs, poll for completion, return items."""
    if not APIFY_API_TOKEN:
        print("ERROR: APIFY_API_TOKEN not set")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }
    client = httpx.Client(timeout=60)

    if platform == "tiktok":
        body = {
            "postURLs": urls,
            "resultsPerPage": len(urls),
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": True,
            "shouldDownloadSlideshowImages": True,
            "shouldDownloadSubtitles": True,
            "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES",
            "commentsPerPost": 10,
        }
    else:
        body = {
            "directUrls": urls,
            "resultsLimit": len(urls),
        }

    print(f"  Starting Apify {actor_id} on {len(urls)} URLs...")
    resp = client.post(
        f"https://api.apify.com/v2/acts/{actor_id}/runs",
        headers=headers,
        json=body,
    )
    resp.raise_for_status()
    run_id = resp.json()["data"]["id"]
    print(f"  Run ID: {run_id}")

    elapsed = 0
    status = "RUNNING"
    status_data: dict = {}
    while elapsed < APIFY_MAX_WAIT_S:
        time.sleep(APIFY_POLL_S)
        elapsed += APIFY_POLL_S
        resp = client.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            headers=headers,
        )
        resp.raise_for_status()
        status_data = resp.json()["data"]
        status = status_data["status"]
        print(f"    [{elapsed}s] {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"  ERROR: Run ended with {status}")
        client.close()
        return []

    cost = status_data.get("usageTotalUsd", "?")
    print(f"  Run succeeded. Cost: ${cost}")

    dataset_id = status_data["defaultDatasetId"]
    resp = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    client.close()
    return resp.json()


def map_tiktok_item(apify_data: dict) -> dict:
    """Map TikTok Apify response to benchmark item format."""
    author = apify_data.get("authorMeta") or {}
    music = apify_data.get("musicMeta") or {}
    video_meta = apify_data.get("videoMeta") or {}
    covers = apify_data.get("covers") or {}

    is_slideshow = bool(apify_data.get("imagePost"))
    images = apify_data.get("images") or []
    if is_slideshow or len(images) > 0:
        media_type = "slideshow" if len(images) > 1 else "image"
    else:
        media_type = "video"

    hashtags = [
        h.get("name", "")
        for h in (apify_data.get("hashtags") or [])
        if isinstance(h, dict)
    ]

    # Build subtitle text from subtitle links
    subtitle_text = None
    subtitle_links = video_meta.get("subtitleLinks") or []
    if subtitle_links:
        subtitle_text = "(subtitle available)"

    # Extract top comments
    comments_top10 = []
    # Comments are in a separate dataset — skip for now, not critical for benchmark

    # Build music metadata string
    music_str = None
    if music.get("musicName"):
        music_str = f"{music.get('musicName', '')} — {music.get('musicAuthor', '')}"

    # Get download URLs for media
    media_urls = apify_data.get("mediaUrls") or []
    video_url = (
        media_urls[0] if media_urls else (video_meta.get("downloadAddr") or None)
    )

    slideshow_links = apify_data.get("slideshowImageLinks") or []
    image_urls = []
    for sl in slideshow_links:
        dl = sl.get("downloadLink") or sl.get("tiktokLink")
        if dl:
            image_urls.append(dl)
    if not image_urls and images:
        image_urls = images

    return {
        "id": str(apify_data.get("id", "")),
        "url": apify_data.get("webVideoUrl") or apify_data.get("input", ""),
        "platform": "tiktok",
        "media_type": media_type,
        "creator": author.get("name", ""),
        "apify": {
            "caption": apify_data.get("text") or "",
            "hashtags": hashtags,
            "is_slideshow": is_slideshow,
            "thumbnail_url": covers.get("default") or (video_meta.get("coverUrl")),
            "duration_seconds": video_meta.get("duration"),
            "music_metadata": music_str,
            "subtitle_text": subtitle_text,
            "comments_top10": comments_top10,
            "video_url": video_url,
            "image_urls": image_urls,
            "image_count": len(images) if images else None,
        },
        "apify_raw": apify_data,
    }


def map_instagram_item(apify_data: dict) -> dict:
    """Map Instagram Apify response to benchmark item format."""
    post_type = apify_data.get("type", "")
    images = apify_data.get("images") or []
    video_url = apify_data.get("videoUrl")

    if post_type == "Video" or video_url:
        media_type = "video"
    elif len(images) > 1 or post_type == "Sidecar":
        media_type = "slideshow"
    else:
        media_type = "image"

    raw_hashtags = apify_data.get("hashtags") or []
    hashtags = [h if isinstance(h, str) else str(h) for h in raw_hashtags]

    return {
        "id": apify_data.get("shortCode") or apify_data.get("id", ""),
        "url": apify_data.get("url", ""),
        "platform": "instagram",
        "media_type": media_type,
        "creator": apify_data.get("ownerUsername") or "",
        "apify": {
            "caption": apify_data.get("caption") or "",
            "hashtags": hashtags,
            "is_slideshow": media_type == "slideshow",
            "thumbnail_url": apify_data.get("displayUrl"),
            "duration_seconds": apify_data.get("videoDuration"),
            "music_metadata": None,
            "subtitle_text": None,
            "comments_top10": [],
            "video_url": video_url,
            "image_urls": images if images else None,
            "image_count": len(images) if images else None,
        },
        "apify_raw": apify_data,
    }


def download_media(items: list[dict]) -> int:
    """Download video/slideshow/thumbnail files for all items."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    for item in items:
        pid = item["id"]
        apify = item.get("apify", {})
        media_type = item.get("media_type", "")

        # Download video
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
                        print(f"    WARN: Failed to download video {pid}: {e}")

        # Download slideshow images
        if media_type == "slideshow":
            image_urls = apify.get("image_urls") or []
            for j, url in enumerate(image_urls[:10]):
                dest = MEDIA_DIR / f"slide_{pid}_{j:03d}.jpg"
                if not dest.exists():
                    try:
                        r = httpx.get(url, timeout=60, follow_redirects=True)
                        r.raise_for_status()
                        dest.write_bytes(r.content)
                        downloaded += 1
                    except Exception as e:
                        print(f"    WARN: Failed to download slide {pid}_{j}: {e}")

        # Always download thumbnail
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
                    pass  # Thumbnails are optional

    return downloaded


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    tt_only = "--tiktok-only" in args
    ig_only = "--instagram-only" in args

    tt_sample = TT_SAMPLE_SIZE
    ig_sample = IG_SAMPLE_SIZE
    for i, a in enumerate(args):
        if a == "--tt-sample" and i + 1 < len(args):
            tt_sample = int(args[i + 1])
        if a == "--ig-sample" and i + 1 < len(args):
            ig_sample = int(args[i + 1])

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_items: list[dict] = []

    # ── TikTok ────────────────────────────────────────────────────────────
    if not ig_only:
        print("=" * 60)
        print("TIKTOK: Loading URLs from export")
        print("=" * 60)
        tt_urls = load_tiktok_urls()
        print(f"  Total TikTok favorites: {len(tt_urls)}")

        # Random sample
        random.seed(42)
        sample = random.sample(tt_urls, min(tt_sample, len(tt_urls)))
        print(f"  Sampling {len(sample)} URLs for enrichment")
        print(f"  Estimated Apify cost: ~${len(sample) * 0.014:.2f}")

        if dry_run:
            print("  [DRY RUN] Skipping Apify call")
        else:
            apify_results = run_apify_batch(APIFY_TT_ACTOR, sample, "tiktok")
            print(f"  Got {len(apify_results)} results from Apify")

            tt_items = [map_tiktok_item(r) for r in apify_results]
            all_items.extend(tt_items)

            # Stats
            by_type = {}
            for item in tt_items:
                mt = item["media_type"]
                by_type[mt] = by_type.get(mt, 0) + 1
            print("\n  TikTok media type distribution:")
            for mt, count in sorted(by_type.items()):
                print(f"    {mt}: {count}")

    # ── Instagram ─────────────────────────────────────────────────────────
    if not tt_only:
        print(f"\n{'=' * 60}")
        print("INSTAGRAM: Loading URLs from export")
        print("=" * 60)
        ig_reels, ig_posts = load_instagram_urls()
        print(f"  Total IG reels: {len(ig_reels)}, posts: {len(ig_posts)}")

        # Sample: half reels, half posts to get media type diversity
        random.seed(42)
        reel_sample = random.sample(ig_reels, min(ig_sample // 2, len(ig_reels)))
        post_sample = random.sample(ig_posts, min(ig_sample // 2, len(ig_posts)))
        ig_urls = reel_sample + post_sample
        print(
            f"  Sampling {len(reel_sample)} reels + {len(post_sample)} posts = {len(ig_urls)} URLs"
        )
        print(f"  Estimated Apify cost: ~${len(ig_urls) * 0.014:.2f}")

        if dry_run:
            print("  [DRY RUN] Skipping Apify call")
        else:
            apify_results = run_apify_batch(APIFY_IG_ACTOR, ig_urls, "instagram")
            print(f"  Got {len(apify_results)} results from Apify")

            ig_items = [map_instagram_item(r) for r in apify_results]
            all_items.extend(ig_items)

            by_type = {}
            for item in ig_items:
                mt = item["media_type"]
                by_type[mt] = by_type.get(mt, 0) + 1
            print("\n  Instagram media type distribution:")
            for mt, count in sorted(by_type.items()):
                print(f"    {mt}: {count}")

    if dry_run:
        print("\n[DRY RUN] No data collected. Remove --dry-run to proceed.")
        return

    if not all_items:
        print("\nNo items collected. Check Apify token and URLs.")
        return

    # ── Save by platform × media_type ─────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("SAVING DATA")
    print("=" * 60)

    groups: dict[str, list[dict]] = {}
    for item in all_items:
        key = f"{item['platform']}_{item['media_type']}"
        groups.setdefault(key, []).append(item)

    for key, items in sorted(groups.items()):
        path = DATA_DIR / f"{key}.json"
        # Strip apify_raw to keep files manageable
        clean = [{k: v for k, v in item.items() if k != "apify_raw"} for item in items]
        path.write_text(json.dumps(clean, indent=2, default=str))
        print(f"  {key}: {len(items)} items → {path.name}")

    # Also save the full dataset with raw data for debugging
    full_path = DATA_DIR / "all_items_with_raw.json"
    full_path.write_text(json.dumps(all_items, indent=2, default=str))
    print(f"  Full dataset (with raw): {len(all_items)} items → {full_path.name}")

    # ── Download media ────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("DOWNLOADING MEDIA")
    print("=" * 60)

    count = download_media(all_items)
    print(f"  Downloaded {count} new media files to {MEDIA_DIR.relative_to(REPO_ROOT)}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total items: {len(all_items)}")
    for key, items in sorted(groups.items()):
        has_video = sum(
            1 for i in items if (MEDIA_DIR / f"video_{i['id']}.mp4").exists()
        )
        has_slides = sum(
            1 for i in items if list(MEDIA_DIR.glob(f"slide_{i['id']}_*.jpg"))
        )
        has_thumb = sum(
            1 for i in items if (MEDIA_DIR / f"thumb_{i['id']}.jpg").exists()
        )
        print(
            f"  {key}: {len(items)} items | "
            f"{has_video} videos, {has_slides} slideshows, {has_thumb} thumbs"
        )
    print("\nNext: run_benchmark.py to measure Gemini cost/time per media type")


if __name__ == "__main__":
    main()
