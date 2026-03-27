#!/usr/bin/env python
"""End-to-end Tier 1 runtime test.

Simulates the full upload-time experience from raw TikTok URLs:
  Stage 1: Apify enrichment (metadata + video download + subtitles + comments)
  Stage 2: Keyframe extraction (local ffmpeg)
  Stage 3: Gemini processing (3 keyframes + metadata → single pass)
  Stage 4: Embedding generation (OpenAI)

Times each stage independently to identify bottlenecks.

Usage:
    python workbench/experiments/03-pipeline-v3/tier1_e2e_test.py workbench/data/tier1_test_sample.json
"""
import base64
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
MEDIA_DIR = RESULTS_DIR / "tier1_e2e_media"

load_dotenv(REPO_ROOT / "workbench" / ".env")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-3-flash-preview"
EMBEDDING_MODEL = "text-embedding-3-small"
APIFY_ACTOR_ID = "clockworks~tiktok-scraper"

GEMINI_CONCURRENCY = 8

# Import the Tier 1 prompt from run_tier1.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_tier1 import TIER1_PROMPT, safe_json_parse, estimate_cost


def stage_apify(items: list[dict]) -> tuple[dict, float, float]:
    """Stage 1: Apify enrichment with video download."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    urls = [i["url"] for i in items]

    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}",
               "Content-Type": "application/json"}
    client = httpx.Client(timeout=60)

    print(f"  Submitting {len(urls)} URLs to Apify (with video download)...")
    t0 = time.time()

    resp = client.post(
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs",
        headers=headers,
        json={
            "postURLs": urls,
            "resultsPerPage": len(urls),
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": True,
            "shouldDownloadSubtitles": True,
            "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES",
            "commentsPerPost": 10,
        },
    )
    resp.raise_for_status()
    run_id = resp.json()["data"]["id"]
    print(f"  Run: {run_id}")

    # Poll
    status = "RUNNING"
    while time.time() - t0 < 900:
        time.sleep(10)
        elapsed = int(time.time() - t0)
        resp = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                          headers=headers)
        resp.raise_for_status()
        sd = resp.json()["data"]
        status = sd["status"]
        print(f"    [{elapsed}s] {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    apify_time = time.time() - t0
    apify_cost = sd.get("usageTotalUsd", 0)

    if status != "SUCCEEDED":
        print(f"  ERROR: Apify ended with {status}")
        client.close()
        return {}, apify_time, apify_cost

    # Fetch results
    dataset_id = sd["defaultDatasetId"]
    resp = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers, timeout=120)
    resp.raise_for_status()
    apify_items = resp.json()

    # Download media files
    t_dl = time.time()
    downloaded = 0
    for ai in apify_items:
        vid_id = str(ai.get("id", ""))
        if not vid_id:
            continue

        # Video
        media_urls = ai.get("mediaUrls") or []
        dl_addr = (ai.get("videoMeta") or {}).get("downloadAddr", "")
        video_url = media_urls[0] if media_urls else dl_addr
        if video_url:
            dest = MEDIA_DIR / f"video_{vid_id}.mp4"
            if not dest.exists():
                try:
                    r = httpx.get(video_url, timeout=120, follow_redirects=True)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    downloaded += 1
                except Exception:
                    pass

        # Thumbnail
        cover = (ai.get("videoMeta") or {}).get("coverUrl")
        if cover:
            dest = MEDIA_DIR / f"thumb_{vid_id}.jpg"
            if not dest.exists():
                try:
                    r = httpx.get(cover, timeout=30, follow_redirects=True)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                except Exception:
                    pass

    dl_time = time.time() - t_dl
    total_time = time.time() - t0

    print(f"  Apify: {len(apify_items)} items returned, {downloaded} videos downloaded")
    print(f"  Apify run: {apify_time:.0f}s, media download: {dl_time:.0f}s")

    # Build enriched item data
    apify_by_id = {}
    for ai in apify_items:
        vid_id = str(ai.get("id", ""))
        vm = ai.get("videoMeta") or {}
        mm = ai.get("musicMeta") or {}
        raw_ht = ai.get("hashtags") or []
        hashtags = [h["name"] if isinstance(h, dict) else str(h) for h in raw_ht]
        raw_comments = ai.get("comments") or []
        comments = [c.get("text", "") for c in raw_comments[:10]] if raw_comments else None

        # Parse subtitles if available
        subtitle_text = None
        sub_links = vm.get("subtitleLinks") or []
        if sub_links:
            best = sub_links[0]
            for sl in sub_links:
                if "eng" in (sl.get("language") or "").lower():
                    best = sl
                    break
            dl_url = best.get("downloadLink")
            if dl_url:
                try:
                    r = httpx.get(dl_url, timeout=10, follow_redirects=True)
                    if r.status_code == 200:
                        import re
                        lines = []
                        for line in r.text.strip().split("\n"):
                            line = line.strip()
                            if line == "WEBVTT" or "-->" in line or not line:
                                continue
                            line = re.sub(r"<[^>]+>", "", line)
                            if line and (not lines or line != lines[-1]):
                                lines.append(line)
                        subtitle_text = " ".join(lines) if lines else None
                except Exception:
                    pass

        apify_by_id[vid_id] = {
            "caption": ai.get("text"),
            "hashtags": hashtags if hashtags else None,
            "music_metadata": mm.get("musicName"),
            "duration_seconds": vm.get("duration"),
            "is_slideshow": ai.get("isSlideshow", False),
            "thumbnail_url": vm.get("coverUrl"),
            "comments_top10": comments,
            "subtitle_text": subtitle_text,
        }

    client.close()
    return apify_by_id, total_time, apify_cost


def stage_keyframes(items: list[dict]) -> tuple[dict, float]:
    """Stage 2: Extract 3 keyframes per video."""
    t0 = time.time()
    results = {}

    for item in items:
        pid = item["id"]
        video_path = MEDIA_DIR / f"video_{pid}.mp4"
        thumb_path = MEDIA_DIR / f"thumb_{pid}.jpg"

        if video_path.exists():
            # Get duration
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                    capture_output=True, text=True, timeout=10)
                duration = float(result.stdout.strip())
            except Exception:
                duration = 30

            timestamps = [0, duration / 2, max(duration - 1, 0)]
            frames = []
            for i, ts in enumerate(timestamps):
                output = MEDIA_DIR / f"kf_{pid}_{i}.jpg"
                try:
                    subprocess.run([
                        "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                        "-frames:v", "1", "-q:v", "2", str(output),
                    ], capture_output=True, timeout=10, check=True)
                    if output.exists() and output.stat().st_size > 0:
                        frames.append(output)
                except Exception:
                    pass
            results[pid] = frames
        elif thumb_path.exists():
            results[pid] = [thumb_path]

    elapsed = time.time() - t0
    frame_counts = [len(v) for v in results.values()]
    print(f"  Keyframes: {len(results)} items, avg {sum(frame_counts)/len(frame_counts):.1f} frames, {elapsed:.1f}s")
    return results, elapsed


def stage_gemini(items: list[dict], apify_data: dict, keyframes: dict) -> tuple[list[dict], float, float]:
    """Stage 3: Gemini single-pass processing."""
    t0 = time.time()
    total_cost = 0.0

    def process_one(item: dict) -> dict | None:
        pid = item["id"]
        apify = apify_data.get(pid, {})
        frames = keyframes.get(pid, [])
        if not frames:
            return None

        # Build context
        parts_text = []
        caption = apify.get("caption") or ""
        if caption.strip():
            parts_text.append(f"Caption: {caption.strip()[:500]}")
        hashtags = apify.get("hashtags") or []
        if hashtags:
            parts_text.append(f"Hashtags: #{', #'.join(hashtags[:15])}")
        parts_text.append(f"Creator: @{item.get('creator', '?')}")
        music = apify.get("music_metadata")
        if music:
            parts_text.append(f"Music metadata: {music}")
        duration = apify.get("duration_seconds")
        if duration:
            parts_text.append(f"Duration: {duration}s")
        sub = apify.get("subtitle_text")
        if sub:
            parts_text.append(f"Subtitles: {sub[:500]}")
        comments = apify.get("comments_top10") or []
        if comments:
            clines = [f'  {j+1}. "{c[:120]}"' for j, c in enumerate(comments[:10]) if c]
            if clines:
                parts_text.append("Top comments:\n" + "\n".join(clines))

        context = "\n".join(parts_text)
        prompt = TIER1_PROMPT.format(context=context)

        # Build parts
        gemini_parts = [{"text": prompt}]
        for f in frames:
            b64 = base64.b64encode(f.read_bytes()).decode()
            gemini_parts.append({"inlineData": {"mimeType": "image/jpeg", "data": b64}})

        start = time.time()
        try:
            resp = httpx.post(
                f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [{"parts": gemini_parts}],
                    "generationConfig": {
                        "maxOutputTokens": 4096,
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            latency = int((time.time() - start) * 1000)

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = safe_json_parse(text)

            usage = data.get("usageMetadata", {})
            in_tok = usage.get("promptTokenCount", 0)
            out_tok = usage.get("candidatesTokenCount", 0)
            cost = estimate_cost(in_tok, out_tok)

            return {
                "item_id": pid,
                "parsed_output": parsed,
                "cost": cost,
                "latency_ms": latency,
            }
        except Exception as e:
            return {"item_id": pid, "_error": str(e)}

    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=GEMINI_CONCURRENCY) as ex:
        futs = {ex.submit(process_one, item): item for item in items}
        for fut in as_completed(futs):
            done += 1
            r = fut.result()
            if r and "_error" not in r:
                results.append(r)
                total_cost += r["cost"]
                po = r.get("parsed_output") or {}
                topic = (po.get("topic") or {}).get("primary", "?")
                elapsed = time.time() - t0
                print(f"    [{done}/{len(items)}] {r['item_id']}: topic={topic:12s} ${r['cost']:.4f} {elapsed:.0f}s")
            elif r:
                print(f"    [{done}/{len(items)}] {r['item_id']}: ERR {r.get('_error', '')[:50]}")

    elapsed = time.time() - t0
    print(f"  Gemini: {len(results)} OK, ${total_cost:.4f}, {elapsed:.0f}s")
    return results, elapsed, total_cost


def stage_embeddings(results: list[dict]) -> tuple[float]:
    """Stage 4: Generate embeddings from model-constructed text."""
    t0 = time.time()
    texts = []
    for r in results:
        po = r.get("parsed_output") or {}
        if isinstance(po, dict):
            texts.append(po.get("embedding_text") or po.get("summary") or "(no content)")
        else:
            texts.append("(no content)")

    # Batch embed
    client = httpx.Client(timeout=60)
    all_embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"input": batch, "model": EMBEDDING_MODEL},
        )
        resp.raise_for_status()
        data = resp.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        all_embeddings.extend([d["embedding"] for d in sorted_data])
    client.close()

    elapsed = time.time() - t0
    print(f"  Embeddings: {len(all_embeddings)} items, {elapsed:.1f}s")
    return elapsed,


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tier1_e2e_test.py <sample.json>")
        sys.exit(1)

    items = json.loads(Path(sys.argv[1]).read_text())
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"{'='*60}")
    print(f"TIER 1 END-TO-END RUNTIME TEST — {len(items)} items")
    print(f"{'='*60}")

    overall_start = time.time()

    # Stage 1: Apify
    print(f"\n[STAGE 1] Apify enrichment + media download")
    apify_data, apify_time, apify_cost = stage_apify(items)
    matched = len(apify_data)
    print(f"  → {matched}/{len(items)} matched, {apify_time:.0f}s, ${apify_cost:.2f}")

    # Filter to matched items
    matched_items = [i for i in items if i["id"] in apify_data]

    # Stage 2: Keyframes
    print(f"\n[STAGE 2] Keyframe extraction (ffmpeg)")
    keyframes, kf_time = stage_keyframes(matched_items)
    has_frames = sum(1 for v in keyframes.values() if v)
    print(f"  → {has_frames}/{len(matched_items)} with keyframes, {kf_time:.1f}s")

    # Stage 3: Gemini
    print(f"\n[STAGE 3] Gemini Tier 1 processing ({GEMINI_CONCURRENCY} concurrent)")
    gemini_items = [i for i in matched_items if i["id"] in keyframes and keyframes[i["id"]]]
    gemini_results, gemini_time, gemini_cost = stage_gemini(gemini_items, apify_data, keyframes)
    print(f"  → {len(gemini_results)} OK, {gemini_time:.0f}s, ${gemini_cost:.4f}")

    # Stage 4: Embeddings
    print(f"\n[STAGE 4] OpenAI embedding generation")
    (embed_time,) = stage_embeddings(gemini_results)
    print(f"  → {embed_time:.1f}s")

    # Summary
    total_time = time.time() - overall_start
    total_cost = apify_cost + gemini_cost  # embedding cost negligible

    print(f"\n{'='*60}")
    print(f"TIER 1 E2E SUMMARY")
    print(f"{'='*60}")
    print(f"  Items: {len(items)} input → {matched} Apify → {has_frames} keyframes → {len(gemini_results)} processed")
    print()
    print(f"  Stage timing:")
    print(f"    Apify (run + download): {apify_time:6.0f}s  ({apify_time/60:.1f} min)")
    print(f"    Keyframe extraction:    {kf_time:6.1f}s")
    print(f"    Gemini processing:      {gemini_time:6.0f}s  ({gemini_time/60:.1f} min)")
    print(f"    Embedding generation:   {embed_time:6.1f}s")
    print(f"    TOTAL:                  {total_time:6.0f}s  ({total_time/60:.1f} min)")
    print()
    print(f"  Cost:")
    print(f"    Apify:  ${apify_cost:.2f}")
    print(f"    Gemini: ${gemini_cost:.4f}")
    print(f"    TOTAL:  ${total_cost:.2f}")
    print()
    n = len(gemini_results) or 1
    print(f"  Per-item averages:")
    print(f"    Time:  {total_time/n:.1f}s")
    print(f"    Cost:  ${total_cost/n:.4f}")
    print()
    print(f"  Projected for 1000 items:")
    print(f"    Time:  ~{total_time/n*1000/60:.0f} min (with {GEMINI_CONCURRENCY}x Gemini concurrency)")
    print(f"    Cost:  ~${total_cost/n*1000:.2f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
