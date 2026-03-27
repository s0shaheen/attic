#!/usr/bin/env python
"""Test whether Apify video download URLs expire over time.

Usage:
    # First run (immediately after profiling)
    .venv/bin/python workbench/experiments/01-apify-profiling/url_stability_test.py

    # Re-run after 1 hour and 6 hours to compare
    .venv/bin/python workbench/experiments/01-apify-profiling/url_stability_test.py

Reads video URLs from workbench/data/apify_raw_samples/*.json
Saves results to workbench/data/url_stability_results.json (appends each run)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RAW_SAMPLES_DIR = SCRIPT_DIR / "results" / "apify_raw_samples"
RESULTS_PATH = SCRIPT_DIR / "results" / "url_stability_results.json"
MAX_URLS = 10


def main():
    if not RAW_SAMPLES_DIR.exists():
        print("ERROR: No raw samples found. Run apify_profiler.py first.")
        sys.exit(1)

    # Collect video/media URLs from raw samples
    # Tests video download URL, thumbnail, and subtitle links
    test_urls: list[dict] = []
    for path in sorted(RAW_SAMPLES_DIR.glob("*.json")):
        with open(path) as f:
            item = json.load(f)
        vm = item.get("videoMeta") or {}
        video_url = vm.get("downloadAddr") or item.get("videoUrl")
        cover_url = vm.get("coverUrl")
        subtitle_url = None
        for sl in (vm.get("subtitleLinks") or []):
            if sl.get("downloadLink"):
                subtitle_url = sl["downloadLink"]
                break
        # First slideshow image (TikTok CDN, may expire)
        slideshow_image_url = None
        for sl in (item.get("slideshowImageLinks") or []):
            if isinstance(sl, dict) and sl.get("downloadLink"):
                slideshow_image_url = sl["downloadLink"]
                break
        if video_url or slideshow_image_url:
            test_urls.append({
                "platform_id": str(item.get("id", path.stem)),
                "video_url": video_url,
                "cover_url": cover_url,
                "subtitle_url": subtitle_url,
                "slideshow_image_url": slideshow_image_url,
                "web_url": item.get("webVideoUrl", ""),
            })
        if len(test_urls) >= MAX_URLS:
            break

    if not test_urls:
        print("ERROR: No video URLs found in raw samples.")
        sys.exit(1)

    print(f"Testing {len(test_urls)} items (video + cover + subtitle URLs)...")

    # HEAD request each URL type
    client = httpx.Client(timeout=15, follow_redirects=True)
    results = []
    for item in test_urls:
        pid = item["platform_id"]
        item_result = {"platform_id": pid, "urls": {}}

        for url_type in ("video_url", "cover_url", "subtitle_url", "slideshow_image_url"):
            url = item.get(url_type)
            if not url:
                continue
            try:
                start = time.time()
                resp = client.head(url)
                latency_ms = int((time.time() - start) * 1000)
                item_result["urls"][url_type] = {
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("content-type", ""),
                    "content_length": resp.headers.get("content-length", ""),
                    "latency_ms": latency_ms,
                    "accessible": resp.status_code == 200,
                }
            except httpx.HTTPError as e:
                item_result["urls"][url_type] = {
                    "status_code": None,
                    "error": str(e),
                    "accessible": False,
                }

        results.append(item_result)

        # Print summary line
        statuses = []
        for url_type in ("video_url", "cover_url", "subtitle_url", "slideshow_image_url"):
            if url_type in item_result["urls"]:
                r = item_result["urls"][url_type]
                label = url_type.replace("_url", "")
                icon = "OK" if r["accessible"] else f"FAIL({r.get('status_code', '?')})"
                statuses.append(f"{label}:{icon}")
        print(f"  {pid}: {' | '.join(statuses)}")

    client.close()

    # Build run record
    total_urls = sum(len(r["urls"]) for r in results)
    total_ok = sum(1 for r in results for u in r["urls"].values() if u["accessible"])
    run_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "items_tested": len(results),
        "total_urls_tested": total_urls,
        "total_accessible": total_ok,
        "total_failed": total_urls - total_ok,
        "results": results,
    }

    # Load existing results and append
    existing = {"runs": []}
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            existing = json.load(f)

    existing["runs"].append(run_record)

    with open(RESULTS_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    # Summary
    print(f"\n  URLs tested: {run_record['total_urls_tested']}")
    print(f"  Accessible:  {run_record['total_accessible']}/{run_record['total_urls_tested']}")
    print(f"  Results saved to {RESULTS_PATH}")

    if len(existing["runs"]) > 1:
        print(f"\n  Run history ({len(existing['runs'])} runs):")
        for i, run in enumerate(existing["runs"]):
            print(f"    Run {i+1}: {run['timestamp']} — {run['total_accessible']}/{run['total_urls_tested']} accessible")

        # Compare first and latest per URL type
        first = existing["runs"][0]
        latest = existing["runs"][-1]
        for url_type in ("video_url", "cover_url", "subtitle_url", "slideshow_image_url"):
            first_ok = {r["platform_id"] for r in first["results"] if r["urls"].get(url_type, {}).get("accessible")}
            latest_ok = {r["platform_id"] for r in latest["results"] if r["urls"].get(url_type, {}).get("accessible")}
            expired = first_ok - latest_ok
            if expired:
                print(f"\n  EXPIRED {url_type} since first run: {len(expired)}")
                for pid in expired:
                    print(f"    {pid}")
        if not any(
            {r["platform_id"] for r in first["results"] if r["urls"].get(t, {}).get("accessible")}
            - {r["platform_id"] for r in latest["results"] if r["urls"].get(t, {}).get("accessible")}
            for t in ("video_url", "cover_url", "subtitle_url")
        ):
            print(f"\n  No URLs expired between runs.")
    else:
        print(f"\n  Re-run this script in 1 hour and 6 hours to check URL expiration.")


if __name__ == "__main__":
    main()
