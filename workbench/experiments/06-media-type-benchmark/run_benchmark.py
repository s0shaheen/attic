#!/usr/bin/env python
"""Phase 2: Run Gemini perceive + classify on collected items by media type.

Reads items from Phase 1 (collect_data.py), runs them through the same
Gemini pipeline as Exp 03, and saves per-item results with usageMetadata.

Usage:
    # Run all collected data
    python workbench/experiments/06-media-type-benchmark/run_benchmark.py

    # Run specific media types only
    python workbench/experiments/06-media-type-benchmark/run_benchmark.py --types tiktok_video,instagram_slideshow

    # Limit items per type (for testing)
    python workbench/experiments/06-media-type-benchmark/run_benchmark.py --limit 3

    # Pass 1 only (perception)
    python workbench/experiments/06-media-type-benchmark/run_benchmark.py --pass1-only

Requires: GEMINI_API_KEY in workbench/.env or .env.master
          Media files downloaded by collect_data.py in ./media/
"""

import base64
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
RESULTS_DIR = SCRIPT_DIR / "results"
MEDIA_DIR = SCRIPT_DIR / "media"

load_dotenv(REPO_ROOT / "workbench" / ".env")
load_dotenv(REPO_ROOT / ".env.master")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-3-flash-preview"

# Pricing per million tokens (Gemini 3 Flash)
INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 0.60

PASS1_MAX_TOKENS = 16384
PASS2_MAX_TOKENS = 8192

CONCURRENCY = 4  # Conservative for mixed workload

# ── Import prompts from Exp 03 ───────────────────────────────────────────

sys.path.insert(0, str(REPO_ROOT / "workbench" / "experiments" / "03-pipeline-v3"))
from run_pipeline_v3 import (  # noqa: E402
    PASS1_SLIDESHOW_PROMPT,
    PASS1_VIDEO_PROMPT,
    PASS2_CLASSIFICATION_PROMPT,
    safe_json_parse,
)


# ── Gemini Client ─────────────────────────────────────────────────────────


def gemini_generate(
    parts: list[dict], max_tokens: int = PASS1_MAX_TOKENS, temperature: float = 0.2
) -> dict:
    resp = httpx.post(
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def gemini_upload_file(file_path: str, mime_type: str) -> str:
    file_size = os.path.getsize(file_path)
    client = httpx.Client(timeout=300)
    resp = client.post(
        "https://generativelanguage.googleapis.com/upload/v1beta/files",
        params={"key": GEMINI_API_KEY},
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
        },
        json={"file": {"displayName": Path(file_path).name}},
    )
    resp.raise_for_status()
    upload_url = resp.headers["X-Goog-Upload-URL"]
    with open(file_path, "rb") as f:
        resp = client.put(
            upload_url,
            headers={
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
                "Content-Length": str(file_size),
            },
            content=f.read(),
        )
    resp.raise_for_status()
    client.close()
    return resp.json()["file"]["name"]


def gemini_wait_for_file(file_name: str, timeout: int = 120) -> str:
    client = httpx.Client(timeout=30)
    elapsed = 0
    while elapsed < timeout:
        resp = client.get(
            f"{GEMINI_API_BASE}/{file_name}", params={"key": GEMINI_API_KEY}
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("state") == "ACTIVE":
            client.close()
            return data.get("uri", f"{GEMINI_API_BASE}/{file_name}")
        if data.get("state") == "FAILED":
            client.close()
            raise RuntimeError(f"File processing failed: {file_name}")
        time.sleep(2)
        elapsed += 2
    client.close()
    raise TimeoutError(f"File not ACTIVE within {timeout}s")


def gemini_delete_file(file_name: str) -> None:
    try:
        httpx.delete(
            f"{GEMINI_API_BASE}/{file_name}", params={"key": GEMINI_API_KEY}, timeout=10
        )
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────


def estimate_cost(in_tok: int, out_tok: int) -> float:
    return (in_tok * INPUT_COST_PER_M + out_tok * OUTPUT_COST_PER_M) / 1_000_000


def image_to_inline(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return {"inlineData": {"mimeType": mime, "data": b64}}


def get_video_path(pid: str) -> Path | None:
    path = MEDIA_DIR / f"video_{pid}.mp4"
    return path if path.exists() else None


def get_slideshow_images(pid: str) -> list[Path]:
    return sorted(MEDIA_DIR.glob(f"slide_{pid}_*.jpg"))


def get_thumbnail_path(pid: str) -> Path | None:
    path = MEDIA_DIR / f"thumb_{pid}.jpg"
    return path if path.exists() else None


def extract_keyframes(video_path: Path, interval_seconds: int = 10) -> list[Path]:
    output_pattern = MEDIA_DIR / f"keyframe_{video_path.stem}_%03d.jpg"
    for old in MEDIA_DIR.glob(f"keyframe_{video_path.stem}_*.jpg"):
        old.unlink()
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(video_path),
                "-vf",
                f"fps=1/{interval_seconds}",
                "-q:v",
                "2",
                str(output_pattern),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return sorted(MEDIA_DIR.glob(f"keyframe_{video_path.stem}_*.jpg"))


def build_context(item: dict) -> str:
    apify = item.get("apify", {})
    parts = []
    caption = apify.get("caption") or ""
    if caption:
        parts.append(f"Caption: {caption[:500]}")
    hashtags = apify.get("hashtags") or []
    if hashtags:
        parts.append(f"Hashtags: #{', #'.join(hashtags[:15])}")
    parts.append(f"Creator: @{item.get('creator', '?')}")
    music = apify.get("music_metadata")
    if music:
        parts.append(f"Music metadata: {music}")
    duration = apify.get("duration_seconds")
    if duration:
        parts.append(f"Duration: {duration}s")
    subtitle = apify.get("subtitle_text")
    if subtitle:
        parts.append(f"Subtitle transcript: {subtitle[:1000]}")
    comments = apify.get("comments_top10") or []
    if comments:
        clines = [f'  {j+1}. "{c[:120]}"' for j, c in enumerate(comments[:10]) if c]
        if clines:
            parts.append("Top comments:\n" + "\n".join(clines))
    return "\n".join(parts) if parts else "(No metadata available)"


def save_result(
    item_id: str,
    stage: str,
    api_resp: dict,
    parsed: dict,
    latency_ms: int,
    upload_ms: int = 0,
    ctx: dict | None = None,
) -> dict:
    usage = api_resp.get("usageMetadata", {})
    in_tok = usage.get("promptTokenCount", 0)
    out_tok = usage.get("candidatesTokenCount", 0)

    record = {
        "item_id": item_id,
        "stage": stage,
        "model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parsed_output": parsed,
        "metrics": {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "cost_usd": round(estimate_cost(in_tok, out_tok), 6),
            "latency_ms": latency_ms,
            "upload_ms": upload_ms,
        },
        "context_used": ctx or {},
    }
    stage_dir = RESULTS_DIR / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"{item_id}.json").write_text(
        json.dumps(record, indent=2, default=str)
    )
    return record


# ── Pipeline Passes ───────────────────────────────────────────────────────


def run_pass1(item: dict) -> dict | None:
    """Pass 1: Perception + Entity Extraction."""
    pid = item["id"]
    context = build_context(item)
    media_type = item.get("media_type", "")
    is_slideshow = media_type == "slideshow"
    platform = item.get("platform", "tiktok")

    start = time.time()
    upload_ms = 0
    file_name = None

    try:
        if is_slideshow:
            imgs = get_slideshow_images(pid)
            if not imgs:
                thumb = get_thumbnail_path(pid)
                imgs = [thumb] if thumb else []
            if not imgs:
                return None
            prompt = PASS1_SLIDESHOW_PROMPT.format(
                context=context, image_count=len(imgs)
            )
            parts = [{"text": prompt}] + [image_to_inline(p) for p in imgs[:10]]

        elif media_type == "video":
            video_path = get_video_path(pid)
            if video_path:
                t0 = time.time()
                file_name = gemini_upload_file(str(video_path), "video/mp4")
                uri = gemini_wait_for_file(file_name)
                upload_ms = int((time.time() - t0) * 1000)
                prompt = PASS1_VIDEO_PROMPT.format(context=context)
                parts = [
                    {"text": prompt},
                    {"fileData": {"mimeType": "video/mp4", "fileUri": uri}},
                ]
            else:
                thumb = get_thumbnail_path(pid)
                if not thumb:
                    return None
                prompt = PASS1_VIDEO_PROMPT.format(context=context)
                parts = [{"text": prompt}, image_to_inline(thumb)]

        else:  # single image
            thumb = get_thumbnail_path(pid)
            if not thumb:
                return None
            prompt = PASS1_VIDEO_PROMPT.format(context=context)
            parts = [{"text": prompt}, image_to_inline(thumb)]

        api_resp = gemini_generate(parts, max_tokens=PASS1_MAX_TOKENS)

        if file_name:
            gemini_delete_file(file_name)

        latency = int((time.time() - start) * 1000)
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)

        ctx = {
            "platform": platform,
            "media_type": media_type,
            "is_slideshow": is_slideshow,
            "has_video": get_video_path(pid) is not None,
            "has_thumbnail": get_thumbnail_path(pid) is not None,
            "slideshow_image_count": len(get_slideshow_images(pid)),
        }
        return save_result(
            pid, "pass1_perception", api_resp, parsed, latency, upload_ms, ctx
        )

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        if file_name:
            gemini_delete_file(file_name)
        save_result(pid, "pass1_perception", {}, {"_error": str(e)}, latency)
        return {"_error": str(e), "item_id": pid}


def run_pass2(item: dict, pass1_result: dict) -> dict | None:
    """Pass 2: Classification using Pass 1 output + visual keyframes."""
    pid = item["id"]
    apify = item.get("apify", {})
    media_type = item.get("media_type", "")
    platform = item.get("platform", "tiktok")
    is_slideshow = media_type == "slideshow"

    p1 = pass1_result.get("parsed_output", {})
    pass1_summary = json.dumps(p1, indent=2, default=str)[:4000]

    caption = apify.get("caption") or "(no caption)"
    hashtags = ", ".join(f"#{h}" for h in (apify.get("hashtags") or [])[:15])
    creator = item.get("creator", "?")
    music = apify.get("music_metadata") or "(unknown)"
    duration = apify.get("duration_seconds") or "?"
    subtitle = apify.get("subtitle_text") or ""
    subtitles_section = f"Subtitles: {subtitle[:500]}" if subtitle else ""
    comments = apify.get("comments_top10") or []
    if comments:
        clines = [f'  {j+1}. "{c[:120]}"' for j, c in enumerate(comments[:10]) if c]
        comments_section = "Top comments:\n" + "\n".join(clines)
    else:
        comments_section = ""

    prompt = PASS2_CLASSIFICATION_PROMPT.format(
        pass1_summary=pass1_summary,
        caption=caption,
        hashtags=hashtags or "(none)",
        creator=creator,
        music=music,
        duration=duration,
        subtitles_section=subtitles_section,
        comments_section=comments_section,
    )

    start = time.time()

    try:
        visual_parts: list[dict] = []
        if is_slideshow:
            imgs = get_slideshow_images(pid)
            if not imgs:
                thumb = get_thumbnail_path(pid)
                if thumb:
                    imgs = [thumb]
            visual_parts = [image_to_inline(p) for p in imgs[:10]]
        else:
            video_path = get_video_path(pid)
            if video_path:
                keyframes = extract_keyframes(video_path, interval_seconds=10)
                visual_parts = [image_to_inline(kf) for kf in keyframes]
            else:
                thumb = get_thumbnail_path(pid)
                if thumb:
                    visual_parts = [image_to_inline(thumb)]

        parts = [{"text": prompt}] + visual_parts
        api_resp = gemini_generate(parts, max_tokens=PASS2_MAX_TOKENS)

        latency = int((time.time() - start) * 1000)
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)

        ctx = {
            "platform": platform,
            "media_type": media_type,
            "is_slideshow": is_slideshow,
            "visual_input": "slideshow_images"
            if is_slideshow
            else ("keyframes_10s" if get_video_path(pid) else "thumbnail"),
            "visual_count": len(visual_parts),
        }
        return save_result(
            pid, "pass2_classification", api_resp, parsed, latency, ctx=ctx
        )

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        save_result(pid, "pass2_classification", {}, {"_error": str(e)}, latency)
        return {"_error": str(e), "item_id": pid}


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    args = sys.argv[1:]
    pass1_only = "--pass1-only" in args
    limit = None
    type_filter = None

    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if a == "--types" and i + 1 < len(args):
            type_filter = args[i + 1].split(",")

    # Load all collected data files
    all_items: list[dict] = []
    for json_file in sorted(DATA_DIR.glob("*.json")):
        if json_file.name.startswith("all_items"):
            continue
        group_name = json_file.stem
        if type_filter and group_name not in type_filter:
            continue
        items = json.loads(json_file.read_text())
        if limit:
            items = items[:limit]
        all_items.extend(items)
        print(f"  Loaded {len(items)} items from {json_file.name}")

    if not all_items:
        print("No items found. Run collect_data.py first.")
        sys.exit(1)

    print(f"\nTotal items: {len(all_items)}")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Results: {RESULTS_DIR}")

    # Check media availability
    has_video = sum(1 for i in all_items if get_video_path(i["id"]))
    has_slides = sum(1 for i in all_items if get_slideshow_images(i["id"]))
    has_thumb = sum(1 for i in all_items if get_thumbnail_path(i["id"]))
    print(f"Media: {has_video} videos, {has_slides} slideshows, {has_thumb} thumbnails")

    # ── Pass 1: Perception ────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("PASS 1: Perception + Entity Extraction")
    print(f"{'=' * 60}\n")

    pass1_results: dict[str, dict] = {}
    total_cost = 0.0
    t0 = time.time()

    # Check for cached results
    p1_dir = RESULTS_DIR / "pass1_perception"
    items_to_run = []
    for item in all_items:
        existing = p1_dir / f"{item['id']}.json"
        if existing.exists():
            try:
                r = json.loads(existing.read_text())
                po = r.get("parsed_output") or {}
                if (
                    isinstance(po, dict)
                    and not po.get("_error")
                    and not po.get("_parse_error")
                ):
                    pass1_results[item["id"]] = r
                    continue
            except Exception:
                pass
        items_to_run.append(item)

    if pass1_results:
        print(
            f"Loaded {len(pass1_results)} cached results, running {len(items_to_run)} remaining"
        )

    def do_pass1(item: dict) -> tuple[str, dict | None]:
        return item["id"], run_pass1(item)

    done = 0
    total_to_run = len(items_to_run)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(do_pass1, item): item for item in items_to_run}
        for fut in as_completed(futs):
            item = futs[fut]
            done += 1
            item_id, result = fut.result()
            elapsed = time.time() - t0

            if result and "_error" not in result:
                pass1_results[item_id] = result
                c = result["metrics"]["cost_usd"]
                total_cost += c
                mt = result.get("context_used", {}).get("media_type", "?")
                print(
                    f"  [{done}/{total_to_run}] {item_id} ({mt}): "
                    f"OK | {result['metrics']['input_tokens']}+"
                    f"{result['metrics']['output_tokens']} tok | "
                    f"${c:.4f} | {elapsed:.0f}s"
                )
            else:
                err = result.get("_error", "no media") if result else "skip"
                print(f"  [{done}/{total_to_run}] {item_id}: {err[:60]}")

    wall1 = time.time() - t0
    print(
        f"\nPass 1 done: {len(pass1_results)}/{len(all_items)} items | "
        f"${total_cost:.4f} | {wall1:.0f}s"
    )

    if pass1_only:
        print("\n--pass1-only flag set. Stopping.")
        return

    # ── Pass 2: Classification ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("PASS 2: Classification")
    print(f"{'=' * 60}\n")

    pass2_cost = 0.0
    t0 = time.time()

    def do_pass2(item: dict) -> tuple[str, dict | None]:
        p1 = pass1_results.get(item["id"])
        if not p1:
            return item["id"], None
        return item["id"], run_pass2(item, p1)

    done = 0
    items_for_p2 = [i for i in all_items if i["id"] in pass1_results]

    # Check for cached pass2 results
    p2_dir = RESULTS_DIR / "pass2_classification"
    items_to_run_p2 = []
    for item in items_for_p2:
        existing = p2_dir / f"{item['id']}.json"
        if existing.exists():
            try:
                r = json.loads(existing.read_text())
                po = r.get("parsed_output") or {}
                if (
                    isinstance(po, dict)
                    and not po.get("_error")
                    and not po.get("_parse_error")
                ):
                    c = r["metrics"]["cost_usd"]
                    pass2_cost += c
                    continue
            except Exception:
                pass
        items_to_run_p2.append(item)

    cached_p2 = len(items_for_p2) - len(items_to_run_p2)
    if cached_p2:
        print(
            f"Loaded {cached_p2} cached results, running {len(items_to_run_p2)} remaining"
        )

    total_to_run = len(items_to_run_p2)
    with ThreadPoolExecutor(max_workers=CONCURRENCY + 2) as ex:
        futs = {ex.submit(do_pass2, item): item for item in items_to_run_p2}
        for fut in as_completed(futs):
            item = futs[fut]
            done += 1
            item_id, result = fut.result()
            elapsed = time.time() - t0

            if result and "_error" not in result:
                c = result["metrics"]["cost_usd"]
                pass2_cost += c
                mt = result.get("context_used", {}).get("media_type", "?")
                print(
                    f"  [{done}/{total_to_run}] {item_id} ({mt}): "
                    f"OK | {result['metrics']['input_tokens']}+"
                    f"{result['metrics']['output_tokens']} tok | "
                    f"${c:.4f} | {elapsed:.0f}s"
                )
            else:
                print(f"  [{done}/{total_to_run}] {item_id}: skip")

    wall2 = time.time() - t0
    print(f"\nPass 2 done: ${pass2_cost:.4f} | {wall2:.0f}s")
    print(f"\nTotal Gemini cost: ${total_cost + pass2_cost:.4f}")
    print("\nNext: python workbench/experiments/06-media-type-benchmark/analyze.py")


if __name__ == "__main__":
    main()
