#!/usr/bin/env python
"""Profile Apify enrichment quality against a real TikTok data export.

Usage:
    # From combined JSON export (favorites only)
    .venv/bin/python workbench/experiments/01-apify-profiling/apify_profiler.py workbench/data/my-export/full_anonymized.json --limit 100

    # Quick smoke test (5 URLs)
    .venv/bin/python workbench/experiments/01-apify-profiling/apify_profiler.py workbench/data/my-export/full_anonymized.json --limit 5

    # Full run (all favorites)
    .venv/bin/python workbench/experiments/01-apify-profiling/apify_profiler.py workbench/data/my-export/full_anonymized.json

    # Scale test (progressive batches with timing)
    .venv/bin/python workbench/experiments/01-apify-profiling/apify_profiler.py workbench/data/my-export/full_anonymized.json --scale-test

Requires: APIFY_API_TOKEN in workbench/.env
Outputs:
    workbench/data/apify_profile_report.json   — structured quality metrics
    workbench/data/apify_raw_samples/          — raw Apify responses (first 20)
    workbench/data/profiler_plots/             — histogram PNGs
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────

APIFY_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_BATCH_SIZE = 50
APIFY_POLL_INTERVAL_S = 5
APIFY_MAX_WAIT_S = 600

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
RAW_SAMPLES_DIR = RESULTS_DIR / "apify_raw_samples"
PLOTS_DIR = RESULTS_DIR / "profiler_plots"
REPORT_PATH = RESULTS_DIR / "apify_profile_report.json"

load_dotenv(REPO_ROOT / "workbench" / ".env")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

# ── URL helpers (from pipeline.py patterns) ─────────────────────────────────

_TIKTOK_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


def _normalize_url(url: str) -> str:
    """tiktokv.com → tiktok.com for Apify compatibility."""
    return url.replace("://www.tiktokv.com/", "://www.tiktok.com/")


def _extract_platform_id(url: str) -> str | None:
    match = _TIKTOK_VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


# ── Emoji detection ─────────────────────────────────────────────────────────

def _is_emoji_only(text: str) -> bool:
    """Check if text contains only emoji, whitespace, and variation selectors."""
    if not text or not text.strip():
        return True
    for char in text:
        if char.isspace():
            continue
        cat = unicodedata.category(char)
        # So = Symbol Other (emoji), Sk = modifier, Mn/Mc = combining marks, Cf = format (ZWJ, VS16)
        if cat not in ("So", "Sk", "Mn", "Mc", "Cf"):
            return False
    return True


# ── Export parser (standalone — doesn't import backend) ─────────────────────

def parse_favorites_from_export(path: Path) -> list[dict]:
    """Extract favorite video URLs + dates from a combined TikTok export JSON."""
    with open(path) as f:
        data = json.load(f)

    # Navigate to favorites
    likes_section = data.get("Likes and Favorites", {})
    fav_data = likes_section.get("Favorite Videos", {})
    fav_list = fav_data.get("FavoriteVideoList", [])

    items = []
    for item in fav_list:
        url = item.get("Link") or item.get("link")
        date = item.get("Date") or item.get("date")
        if url:
            items.append({
                "url": url,
                "date": date,
                "interaction_type": "favorited",
                "platform_id": _extract_platform_id(url),
            })
    return items


# ── Apify client ────────────────────────────────────────────────────────────

def run_apify_batch(urls: list[str]) -> tuple[list[dict], dict]:
    """Run Apify TikTok scraper on a batch of URLs.

    Returns (items, run_metadata) where run_metadata has timing/status info.
    """
    if not APIFY_API_TOKEN:
        print("ERROR: APIFY_API_TOKEN not set in workbench/.env")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }

    client = httpx.Client(timeout=60)

    # Start run — enable all media downloads and transcription
    start_time = time.time()
    resp = client.post(
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs",
        headers=headers,
        json={
            "postURLs": urls,
            "resultsPerPage": len(urls),
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": True,
            "shouldDownloadSlideshowImages": True,
            "shouldDownloadSubtitles": True,
            "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES",
            "commentsPerPost": 10,
        },
    )
    resp.raise_for_status()
    run_data = resp.json()["data"]
    run_id = run_data["id"]

    # Poll for completion
    elapsed = 0
    status = "RUNNING"
    status_data: dict = {}
    while elapsed < APIFY_MAX_WAIT_S:
        time.sleep(APIFY_POLL_INTERVAL_S)
        elapsed += APIFY_POLL_INTERVAL_S

        resp = client.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            headers=headers,
        )
        resp.raise_for_status()
        status_data = resp.json()["data"]
        status = status_data["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    wall_clock_s = time.time() - start_time

    run_meta = {
        "run_id": run_id,
        "status": status,
        "wall_clock_s": round(wall_clock_s, 1),
        "urls_submitted": len(urls),
        "usage_usd": status_data.get("usageTotalUsd"),
        "started_at": status_data.get("startedAt"),
        "finished_at": status_data.get("finishedAt"),
    }

    if status != "SUCCEEDED":
        print(f"  WARNING: Apify run {run_id} ended with status: {status}")
        return [], run_meta

    # Fetch dataset items
    dataset_id = status_data["defaultDatasetId"]
    resp = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers,
    )
    resp.raise_for_status()
    items = resp.json()
    if not isinstance(items, list):
        items = []

    run_meta["items_returned"] = len(items)

    client.close()
    return items, run_meta


# ── Profile computation ─────────────────────────────────────────────────────

# Fields we care about profiling (Apify response → readable name)
# NOTE: Apify clockworks~tiktok-scraper response structure (as of 2026-03):
#   - Thumbnails at videoMeta.coverUrl (NOT covers.default)
#   - No videoUrl field (direct download URLs not included)
#   - Slideshows: isSlideshow (bool) + slideshowImageLinks (array)
#   - Subtitles: videoMeta.transcriptionLink
PROFILE_FIELDS = {
    "text": "caption_text",
    "hashtags": "hashtags",
    "authorMeta": "creator",
    "videoMeta": "video_meta",
    "musicMeta": "music",
    "playCount": "play_count",
    "diggCount": "like_count",
    "commentCount": "comment_count",
    "shareCount": "share_count",
    "collectCount": "collect_count",
    "webVideoUrl": "web_url",
    "createTime": "create_time",
    "mentions": "mentions",
    "isAd": "is_ad",
    "locationCreated": "location",
    "effectStickers": "effects",
    "textLanguage": "text_language",
}


def _has_value(item: dict, field: str) -> bool:
    """Check if an Apify response field is meaningfully populated."""
    val = item.get(field)
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    if isinstance(val, list) and len(val) == 0:
        return False
    if isinstance(val, dict) and len(val) == 0:
        return False
    # Special: authorMeta must have name
    if field == "authorMeta":
        return bool((val or {}).get("name"))
    return True


def compute_profile(
    export_items: list[dict],
    apify_items: list[dict],
    run_metas: list[dict],
) -> dict:
    """Compute comprehensive data quality profile."""
    # Index Apify results by platform_id (same logic as pipeline.py)
    results_by_pid: dict[str, dict] = {}
    for item in apify_items:
        apify_id = str(item.get("id", ""))
        if apify_id:
            results_by_pid[apify_id] = item
        web_url = item.get("webVideoUrl", "")
        pid = _extract_platform_id(web_url)
        if pid:
            results_by_pid[pid] = item

    # Match export items to Apify results
    matched = []
    unmatched_urls = []  # URLs Apify returned nothing for (deleted/unavailable)
    for export_item in export_items:
        pid = export_item.get("platform_id")
        if pid and pid in results_by_pid:
            matched.append({
                "export": export_item,
                "apify": results_by_pid[pid],
            })
        else:
            unmatched_urls.append(export_item)

    total_submitted = len(export_items)
    total_returned = len(apify_items)
    total_matched = len(matched)

    # ── Fill rates ──
    fill_rates = {}
    for apify_field, readable_name in PROFILE_FIELDS.items():
        filled = sum(1 for m in matched if _has_value(m["apify"], apify_field))
        fill_rates[readable_name] = {
            "filled": filled,
            "total": total_matched,
            "rate": round(filled / total_matched, 4) if total_matched else 0,
        }

    # ── Caption analysis ──
    captions = [m["apify"].get("text", "") or "" for m in matched]
    caption_lengths = [len(c) for c in captions]
    empty_captions = sum(1 for c in captions if not c.strip())
    emoji_only_captions = sum(1 for c in captions if c.strip() and _is_emoji_only(c))

    caption_analysis = {
        "total": total_matched,
        "empty": empty_captions,
        "empty_pct": round(empty_captions / total_matched, 4) if total_matched else 0,
        "emoji_only": emoji_only_captions,
        "emoji_only_pct": round(emoji_only_captions / total_matched, 4) if total_matched else 0,
        "length_mean": round(np.mean(caption_lengths), 1) if caption_lengths else 0,
        "length_median": round(float(np.median(caption_lengths)), 1) if caption_lengths else 0,
        "length_p25": round(float(np.percentile(caption_lengths, 25)), 1) if caption_lengths else 0,
        "length_p75": round(float(np.percentile(caption_lengths, 75)), 1) if caption_lengths else 0,
        "length_p95": round(float(np.percentile(caption_lengths, 95)), 1) if caption_lengths else 0,
        "length_max": max(caption_lengths) if caption_lengths else 0,
    }

    # ── Hashtag analysis ──
    hashtag_counts = []
    for m in matched:
        tags = m["apify"].get("hashtags") or []
        hashtag_counts.append(len(tags))

    hashtag_analysis = {
        "items_with_hashtags": sum(1 for c in hashtag_counts if c > 0),
        "items_with_hashtags_pct": round(sum(1 for c in hashtag_counts if c > 0) / total_matched, 4) if total_matched else 0,
        "count_mean": round(np.mean(hashtag_counts), 1) if hashtag_counts else 0,
        "count_median": round(float(np.median(hashtag_counts)), 1) if hashtag_counts else 0,
        "count_max": max(hashtag_counts) if hashtag_counts else 0,
    }

    # ── Media type breakdown ──
    # Current Apify response uses isSlideshow (bool) + slideshowImageLinks (array)
    media_types = {"video": 0, "image": 0, "slideshow": 0}
    for m in matched:
        apify = m["apify"]
        is_slideshow = bool(apify.get("isSlideshow"))
        slideshow_images = apify.get("slideshowImageLinks") or []
        # Also check legacy fields
        legacy_images = apify.get("images") or []
        if is_slideshow or len(slideshow_images) > 1 or bool(apify.get("imagePost")):
            media_types["slideshow"] += 1
        elif len(slideshow_images) == 1 or len(legacy_images) == 1:
            media_types["image"] += 1
        else:
            media_types["video"] += 1

    # ── Thumbnail URL availability ──
    # Current Apify: videoMeta.coverUrl (NOT covers.default)
    thumbnail_count = 0
    for m in matched:
        apify = m["apify"]
        cover_url = (apify.get("videoMeta") or {}).get("coverUrl")
        legacy_cover = (apify.get("covers") or {}).get("default")
        if cover_url or legacy_cover:
            thumbnail_count += 1

    thumbnail_analysis = {
        "available": thumbnail_count,
        "total": total_matched,
        "rate": round(thumbnail_count / total_matched, 4) if total_matched else 0,
        "field_path": "videoMeta.coverUrl",
    }

    # ── Video download URL availability (critical for Day 2) ──
    # With shouldDownloadVideos=true: videoMeta.downloadAddr and mediaUrls[] point to KV store
    video_url_count = 0
    for m in matched:
        apify = m["apify"]
        has_video_url = bool(
            (apify.get("videoMeta") or {}).get("downloadAddr")
            or (apify.get("mediaUrls") and len(apify["mediaUrls"]) > 0)
        )
        if has_video_url:
            video_url_count += 1

    video_url_analysis = {
        "available": video_url_count,
        "total": total_matched,
        "rate": round(video_url_count / total_matched, 4) if total_matched else 0,
        "field_path": "videoMeta.downloadAddr / mediaUrls[]",
    }

    # ── Slideshow image URLs ──
    slideshow_items = [m for m in matched if bool(m["apify"].get("isSlideshow"))]
    slideshow_with_images = sum(
        1 for m in slideshow_items if len(m["apify"].get("slideshowImageLinks") or []) > 0
    )
    slideshow_analysis = {
        "total_slideshows": len(slideshow_items),
        "with_image_links": slideshow_with_images,
        "image_count_examples": [
            len(m["apify"].get("slideshowImageLinks") or []) for m in slideshow_items[:10]
        ],
    }

    # ── Subtitle / transcription availability ──
    # With shouldDownloadSubtitles + DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES:
    # videoMeta.subtitleLinks[] has downloadLink pointing to KV store VTT files
    subtitle_count = 0
    subtitle_sources: dict[str, int] = {}  # ASR vs authored vs transcribed
    for m in matched:
        apify = m["apify"]
        sub_links = (apify.get("videoMeta") or {}).get("subtitleLinks") or []
        if sub_links:
            subtitle_count += 1
            for sl in sub_links:
                source = sl.get("source", "unknown")
                subtitle_sources[source] = subtitle_sources.get(source, 0) + 1

    subtitle_analysis = {
        "available": subtitle_count,
        "total": total_matched,
        "rate": round(subtitle_count / total_matched, 4) if total_matched else 0,
        "sources": subtitle_sources,
        "field_path": "videoMeta.subtitleLinks[].downloadLink",
    }

    # ── Engagement stats ──
    play_counts = [m["apify"].get("playCount", 0) or 0 for m in matched]
    like_counts = [m["apify"].get("diggCount", 0) or 0 for m in matched]

    engagement_analysis = {
        "play_count_mean": round(np.mean(play_counts)) if play_counts else 0,
        "play_count_median": round(float(np.median(play_counts))) if play_counts else 0,
        "play_count_max": max(play_counts) if play_counts else 0,
        "like_count_mean": round(np.mean(like_counts)) if like_counts else 0,
        "like_count_median": round(float(np.median(like_counts))) if like_counts else 0,
    }

    # ── Video duration ──
    durations = []
    for m in matched:
        d = (m["apify"].get("videoMeta") or {}).get("duration")
        if d and d > 0:
            durations.append(d)

    duration_analysis = {
        "items_with_duration": len(durations),
        "mean_s": round(np.mean(durations), 1) if durations else 0,
        "median_s": round(float(np.median(durations)), 1) if durations else 0,
        "p95_s": round(float(np.percentile(durations, 95)), 1) if durations else 0,
        "max_s": max(durations) if durations else 0,
    }

    # ── Unmatched analysis (deleted/unavailable TikToks) ──
    unmatched_analysis = {
        "count": len(unmatched_urls),
        "total_submitted": total_submitted,
        "rate": round(len(unmatched_urls) / total_submitted, 4) if total_submitted else 0,
        "sample_urls": [u["url"] for u in unmatched_urls[:10]],
        "date_range": {
            "oldest": min((u["date"] for u in unmatched_urls), default=None),
            "newest": max((u["date"] for u in unmatched_urls), default=None),
        },
    }

    # ── Apify extra items (returned but not in our export — shouldn't happen) ──
    export_pids = {i["platform_id"] for i in export_items if i.get("platform_id")}
    extra_apify = []
    for item in apify_items:
        apify_id = str(item.get("id", ""))
        web_url = item.get("webVideoUrl", "")
        pid = _extract_platform_id(web_url) or apify_id
        if pid not in export_pids:
            extra_apify.append(pid)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "urls_submitted": total_submitted,
            "apify_items_returned": total_returned,
            "matched_to_export": total_matched,
            "unmatched_deleted_or_unavailable": len(unmatched_urls),
            "match_rate": round(total_matched / total_submitted, 4) if total_submitted else 0,
            "extra_apify_items": len(extra_apify),
        },
        "fill_rates": fill_rates,
        "caption_analysis": caption_analysis,
        "hashtag_analysis": hashtag_analysis,
        "media_types": media_types,
        "thumbnail_availability": thumbnail_analysis,
        "video_url_availability": video_url_analysis,
        "slideshow_details": slideshow_analysis,
        "subtitle_availability": subtitle_analysis,
        "engagement_stats": engagement_analysis,
        "video_duration": duration_analysis,
        "unmatched": unmatched_analysis,
        "apify_runs": run_metas,
    }


# ── Plotting ────────────────────────────────────────────────────────────────

def save_plots(matched_items: list[dict], plots_dir: Path) -> None:
    """Generate and save histogram PNGs."""
    plots_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    captions = [m["apify"].get("text", "") or "" for m in matched_items]
    caption_lengths = [len(c) for c in captions]
    hashtag_counts = [len(m["apify"].get("hashtags") or []) for m in matched_items]
    durations = []
    for m in matched_items:
        d = (m["apify"].get("videoMeta") or {}).get("duration")
        if d and d > 0:
            durations.append(d)

    # Caption length histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(caption_lengths, bins=50, color="#A06840", edgecolor="white", alpha=0.8)
    ax.set_title("Caption Length Distribution", fontsize=14)
    ax.set_xlabel("Characters")
    ax.set_ylabel("Count")
    ax.axvline(np.median(caption_lengths), color="red", linestyle="--", label=f"Median: {np.median(caption_lengths):.0f}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "caption_length_histogram.png", dpi=150)
    plt.close(fig)

    # Hashtag count histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    max_tags = min(max(hashtag_counts) if hashtag_counts else 20, 30)
    ax.hist(hashtag_counts, bins=range(0, max_tags + 2), color="#2C2926", edgecolor="white", alpha=0.8)
    ax.set_title("Hashtag Count Distribution", fontsize=14)
    ax.set_xlabel("Number of Hashtags")
    ax.set_ylabel("Count")
    ax.axvline(np.median(hashtag_counts), color="red", linestyle="--", label=f"Median: {np.median(hashtag_counts):.0f}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "hashtag_count_histogram.png", dpi=150)
    plt.close(fig)

    # Video duration histogram
    if durations:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(durations, bins=50, color="#9C9890", edgecolor="white", alpha=0.8)
        ax.set_title("Video Duration Distribution", fontsize=14)
        ax.set_xlabel("Seconds")
        ax.set_ylabel("Count")
        ax.axvline(np.median(durations), color="red", linestyle="--", label=f"Median: {np.median(durations):.0f}s")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plots_dir / "duration_histogram.png", dpi=150)
        plt.close(fig)

    print(f"  Plots saved to {plots_dir}/")


# ── Raw sample saving ──────────────────────────────────────────────────────

def save_raw_samples(apify_items: list[dict], max_samples: int = 20) -> None:
    """Save first N raw Apify responses for manual inspection."""
    RAW_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(apify_items[:max_samples]):
        pid = str(item.get("id", f"unknown_{i}"))
        path = RAW_SAMPLES_DIR / f"{pid}.json"
        with open(path, "w") as f:
            json.dump(item, f, indent=2, default=str)
    print(f"  Saved {min(len(apify_items), max_samples)} raw samples to {RAW_SAMPLES_DIR}/")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Profile Apify enrichment quality")
    parser.add_argument("export_path", help="Path to TikTok export JSON file")
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to process (0=all)")
    parser.add_argument("--concurrency", type=int, default=7, help="Max concurrent Apify actor runs (default: 7)")
    parser.add_argument("--scale-test", action="store_true", help="Run progressive scale test (50, 200, 500)")
    args = parser.parse_args()

    export_path = Path(args.export_path)
    if not export_path.exists():
        print(f"ERROR: File not found: {export_path}")
        sys.exit(1)

    if not APIFY_API_TOKEN:
        print("ERROR: APIFY_API_TOKEN not set. Check workbench/.env")
        sys.exit(1)

    # Parse export
    print(f"Parsing favorites from {export_path}...")
    export_items = parse_favorites_from_export(export_path)
    print(f"  Found {len(export_items)} favorite videos")

    # Deduplicate by platform_id
    seen_pids: set[str] = set()
    deduped: list[dict] = []
    for item in export_items:
        pid = item.get("platform_id")
        if pid and pid not in seen_pids:
            seen_pids.add(pid)
            deduped.append(item)
        elif not pid:
            deduped.append(item)  # keep items without extractable platform_id
    export_items = deduped
    print(f"  {len(export_items)} unique after deduplication")

    # Apply limit
    if args.limit > 0:
        export_items = export_items[:args.limit]
        print(f"  Limited to {len(export_items)} items")

    if args.scale_test:
        run_scale_test(export_items, concurrency=args.concurrency)
        return

    # Process in batches (concurrent Apify runs)
    all_apify_items: list[dict] = []
    all_run_metas: list[dict] = []
    urls = [_normalize_url(item["url"]) for item in export_items]

    # Split into batches of APIFY_BATCH_SIZE
    batches: list[list[str]] = []
    for i in range(0, len(urls), APIFY_BATCH_SIZE):
        batches.append(urls[i:i + APIFY_BATCH_SIZE])

    concurrency = args.concurrency
    print(f"\nProcessing {len(urls)} URLs in {len(batches)} batches of {APIFY_BATCH_SIZE} ({concurrency} concurrent)...")

    def _run_batch(batch_num: int, batch_urls: list[str]) -> tuple[int, list[dict], dict]:
        """Run a single Apify batch. Returns (batch_num, items, run_meta)."""
        items, run_meta = run_apify_batch(batch_urls)
        return batch_num, items, run_meta

    completed = 0
    overall_start = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(_run_batch, i + 1, batch): i + 1
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            batch_num, items, run_meta = future.result()
            all_apify_items.extend(items)
            all_run_metas.append(run_meta)
            completed += 1

            status_icon = "OK" if run_meta["status"] == "SUCCEEDED" else "FAIL"
            elapsed_total = time.time() - overall_start
            cost_str = f", ${run_meta['usage_usd']:.4f}" if run_meta.get("usage_usd") else ""
            print(
                f"  [{completed}/{len(batches)}] Batch {batch_num}: "
                f"{status_icon} — {run_meta.get('items_returned', 0)} items, "
                f"{run_meta['wall_clock_s']}s{cost_str}"
                f"  (elapsed: {elapsed_total:.0f}s)"
            )

    # Save raw samples
    print(f"\nSaving raw samples...")
    save_raw_samples(all_apify_items)

    # Compute profile
    print("Computing profile...")

    # Build matched list for plotting
    results_by_pid: dict[str, dict] = {}
    for item in all_apify_items:
        apify_id = str(item.get("id", ""))
        if apify_id:
            results_by_pid[apify_id] = item
        web_url = item.get("webVideoUrl", "")
        pid = _extract_platform_id(web_url)
        if pid:
            results_by_pid[pid] = item

    matched_for_plots = []
    for export_item in export_items:
        pid = export_item.get("platform_id")
        if pid and pid in results_by_pid:
            matched_for_plots.append({"export": export_item, "apify": results_by_pid[pid]})

    profile = compute_profile(export_items, all_apify_items, all_run_metas)

    # Save report
    with open(REPORT_PATH, "w") as f:
        json.dump(profile, f, indent=2, default=str)
    print(f"  Report saved to {REPORT_PATH}")

    # Generate plots
    if matched_for_plots:
        save_plots(matched_for_plots, PLOTS_DIR)

    # Print summary
    print("\n" + "=" * 70)
    print("APIFY ENRICHMENT PROFILE REPORT")
    print("=" * 70)

    s = profile["summary"]
    print(f"\n  URLs submitted:                {s['urls_submitted']}")
    print(f"  Apify items returned:          {s['apify_items_returned']}")
    print(f"  Matched to export:             {s['matched_to_export']}")
    print(f"  Unmatched (deleted/unavail):   {s['unmatched_deleted_or_unavailable']}")
    print(f"  Match rate:                    {s['match_rate']:.1%}")

    print(f"\n  FIELD FILL RATES:")
    for field, data in profile["fill_rates"].items():
        bar = "█" * int(data["rate"] * 30) + "░" * (30 - int(data["rate"] * 30))
        print(f"    {field:<25s} {bar} {data['rate']:.1%} ({data['filled']}/{data['total']})")

    c = profile["caption_analysis"]
    print(f"\n  CAPTION ANALYSIS:")
    print(f"    Empty:         {c['empty']} ({c['empty_pct']:.1%})")
    print(f"    Emoji-only:    {c['emoji_only']} ({c['emoji_only_pct']:.1%})")
    print(f"    Length median:  {c['length_median']} chars")
    print(f"    Length p95:     {c['length_p95']} chars")

    h = profile["hashtag_analysis"]
    print(f"\n  HASHTAG ANALYSIS:")
    print(f"    Items with hashtags: {h['items_with_hashtags']} ({h['items_with_hashtags_pct']:.1%})")
    print(f"    Count median:        {h['count_median']}")

    m = profile["media_types"]
    total_media = sum(m.values())
    print(f"\n  MEDIA TYPES:")
    for mtype, count in m.items():
        pct = count / total_media if total_media else 0
        print(f"    {mtype:<12s} {count:>5d} ({pct:.1%})")

    thumb = profile["thumbnail_availability"]
    print(f"\n  THUMBNAIL AVAILABILITY: {thumb['available']}/{thumb['total']} ({thumb['rate']:.1%}) [{thumb['field_path']}]")

    v = profile["video_url_availability"]
    print(f"  VIDEO URL AVAILABILITY: {v['available']}/{v['total']} ({v['rate']:.1%}) [{v.get('field_path', '')}]")

    sl = profile["slideshow_details"]
    print(f"  SLIDESHOWS:             {sl['total_slideshows']} items, {sl['with_image_links']} with image links")

    sub = profile["subtitle_availability"]
    print(f"  SUBTITLE AVAILABILITY:  {sub['available']}/{sub['total']} ({sub['rate']:.1%}) [{sub['field_path']}]")
    if sub.get("sources"):
        for source, count in sub["sources"].items():
            print(f"    {source}: {count}")

    d = profile["video_duration"]
    print(f"\n  VIDEO DURATION:")
    print(f"    Median:  {d['median_s']}s")
    print(f"    p95:     {d['p95_s']}s")
    print(f"    Max:     {d['max_s']}s")

    u = profile["unmatched"]
    print(f"\n  UNMATCHED (deleted/unavailable): {u['count']} ({u['rate']:.1%})")
    if u["count"] > 0:
        print(f"    Date range: {u['date_range']['oldest']} to {u['date_range']['newest']}")
        print(f"    Sample URLs:")
        for url in u["sample_urls"][:5]:
            print(f"      {url}")

    # Apify cost/timing summary
    total_cost = sum(r.get("usage_usd") or 0 for r in all_run_metas)
    total_time = sum(r.get("wall_clock_s") or 0 for r in all_run_metas)
    print(f"\n  APIFY RUNS:")
    print(f"    Total batches:  {len(all_run_metas)}")
    print(f"    Total time:     {total_time:.0f}s ({total_time/60:.1f}m)")
    print(f"    Total cost:     ${total_cost:.4f}")
    if s["matched_to_export"] > 0:
        print(f"    Cost per item:  ${total_cost / s['matched_to_export']:.5f}")

    print("\n" + "=" * 70)


def run_scale_test(export_items: list[dict], concurrency: int = 4) -> None:
    """Run progressive scale test: 50, 200, 500 URLs."""
    batch_sizes = [50, 200, 500]
    scale_results = []

    for target in batch_sizes:
        if target > len(export_items):
            print(f"\n  Skipping {target}-URL test (only {len(export_items)} available)")
            continue

        subset = export_items[:target]
        urls = [_normalize_url(item["url"]) for item in subset]

        print(f"\n{'='*50}")
        print(f"SCALE TEST: {target} URLs ({concurrency} concurrent)")
        print(f"{'='*50}")

        batches: list[list[str]] = []
        for i in range(0, len(urls), APIFY_BATCH_SIZE):
            batches.append(urls[i:i + APIFY_BATCH_SIZE])

        all_items: list[dict] = []
        all_metas: list[dict] = []
        start = time.time()

        def _run(batch_num: int, batch_urls: list[str]) -> tuple[int, list[dict], dict]:
            items, meta = run_apify_batch(batch_urls)
            return batch_num, items, meta

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_run, i + 1, batch): i + 1
                for i, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_num, items, meta = future.result()
                all_items.extend(items)
                all_metas.append(meta)
                print(f"  Batch {batch_num}/{len(batches)}: {meta['status']} — {meta.get('items_returned', 0)} items, {meta['wall_clock_s']}s")

        total_time = time.time() - start
        total_cost = sum(m.get("usage_usd") or 0 for m in all_metas)
        failures = sum(1 for m in all_metas if m["status"] != "SUCCEEDED")

        result = {
            "target_urls": target,
            "actual_urls": len(urls),
            "items_returned": len(all_items),
            "wall_clock_s": round(total_time, 1),
            "time_per_item_s": round(total_time / target, 2),
            "total_cost_usd": round(total_cost, 5),
            "cost_per_item_usd": round(total_cost / target, 6) if total_cost else None,
            "failed_batches": failures,
            "batches": len(all_metas),
            "concurrency": concurrency,
        }
        scale_results.append(result)

        print(f"  Returned: {len(all_items)} items in {total_time:.0f}s")
        print(f"  Per item: {total_time/target:.2f}s, ${total_cost/target:.5f}" if total_cost else f"  Per item: {total_time/target:.2f}s")

    # Save scale test results
    scale_path = RESULTS_DIR / "apify_scale_test.json"
    with open(scale_path, "w") as f:
        json.dump({"tests": scale_results, "generated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
    print(f"\n  Scale test results saved to {scale_path}")


if __name__ == "__main__":
    main()
