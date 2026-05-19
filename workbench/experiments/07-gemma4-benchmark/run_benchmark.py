#!/usr/bin/env python
"""Benchmark Gemma 4 vs Gemini Flash on Tier 2 processing (perceive + classify).

Runs the full perception -> classification pipeline on Exp 06 media items
for each specified model, recording per-item metrics.

Usage:
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/run_benchmark.py
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/run_benchmark.py --limit 10
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/run_benchmark.py --models gemma-4-31b-it
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/run_benchmark.py --types instagram_video,tiktok_video
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/run_benchmark.py --skip-perceive  # classify only, reuse existing perception
"""

import argparse
import base64
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
EXP06_DIR = REPO_ROOT / "workbench" / "experiments" / "06-media-type-benchmark"
EXP06_DATA = EXP06_DIR / "data"
EXP06_MEDIA = EXP06_DIR / "media"

# Add backend to path for imports
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

load_dotenv(REPO_ROOT / ".env.master")
load_dotenv(REPO_ROOT / "workbench" / ".env")

from app.services.gemini import (  # noqa: E402
    GEMINI_API_BASE,
    PERCEPTION_MAX_TOKENS,
    REQUEST_TIMEOUT,
    delete_file_sync,
    upload_file_sync,
    wait_for_file_sync,
)
from app.services.ontology import FACET_NAMES, validate_classification  # noqa: E402
from app.services.prompt_loader import load_prompt  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CLASSIFY_MAX_TOKENS = 2048
CONCURRENCY = 5  # conservative for benchmarking — want stable latency numbers

# Pricing per 1M tokens (input, output)
# Gemma models on AI Studio are free-tier for now; using $0 for accurate cost comparison.
# Update if Google announces paid pricing.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3-flash-preview": (0.10, 0.40),
    "gemma-4-31b-it": (0.0, 0.0),  # free on AI Studio as of 2026-04
    "gemma-4-26b-a4b-it": (0.0, 0.0),  # free on AI Studio as of 2026-04
}
DEFAULT_PRICING = (0.10, 0.40)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


# ---------------------------------------------------------------------------
# Load Exp 06 items
# ---------------------------------------------------------------------------


def load_items(types: list[str] | None = None) -> list[dict]:
    """Load items from Exp 06 data directory."""
    items = []
    for path in sorted(EXP06_DATA.glob("*.json")):
        if path.name == "all_items_with_raw.json":
            continue
        type_key = path.stem  # e.g. "instagram_video"
        if types and type_key not in types:
            continue
        data = json.loads(path.read_text())
        for item in data:
            item["_type_key"] = type_key
        items.extend(data)
    return items


# ---------------------------------------------------------------------------
# Perceive
# ---------------------------------------------------------------------------


def _build_perception_context(item: dict) -> str:
    """Build metadata context string for perception prompt."""
    apify = item.get("apify", {})
    parts: list[str] = []
    if apify.get("caption"):
        parts.append(f"Caption: {apify['caption']}")
    if apify.get("hashtags"):
        parts.append(f"Hashtags: #{', #'.join(str(h) for h in apify['hashtags'][:20])}")
    if apify.get("music_metadata"):
        parts.append(f"Music: {apify['music_metadata']}")
    if apify.get("duration_seconds") is not None:
        parts.append(f"Duration: {apify['duration_seconds']}s")
    if apify.get("subtitle_text"):
        parts.append(f"Subtitles: {apify['subtitle_text'][:500]}")
    return "\n".join(parts) if parts else "(No metadata available)"


def _find_local_thumbnail(item_id: str) -> Path | None:
    """Find a local thumbnail file for an item."""
    for path in [
        EXP06_MEDIA / f"thumb_{item_id}.jpg",
        EXP06_MEDIA / f"thumb_{item_id}.png",
    ]:
        if path.exists():
            return path
    return None


def _find_local_slides(item_id: str) -> list[Path]:
    """Find local slideshow images for an item."""
    slides = sorted(EXP06_MEDIA.glob(f"slide_{item_id}_*.jpg"))
    return slides[:10]


def _inline_image_part(path: Path) -> dict:
    """Create an inlineData part from a local image file."""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return {"inlineData": {"mimeType": mime, "data": data}}


MAX_RETRIES = 3
RETRY_BASE_DELAY = 15  # seconds


def _call_gemini(
    api_key: str, model: str, parts: list[dict], max_tokens: int
) -> httpx.Response:
    """Make a generateContent request to the Gemini API with retry on 429."""
    # Use generous timeout — Gemma 4 thinking adds significant latency
    timeout = max(REQUEST_TIMEOUT * 3, 180.0)

    for attempt in range(MAX_RETRIES + 1):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{GEMINI_API_BASE}/models/{model}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                },
            )
        if resp.status_code != 429 or attempt == MAX_RETRIES:
            return resp
        delay = RETRY_BASE_DELAY * (2**attempt)
        print(
            f"    429 rate limit, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})"
        )
        time.sleep(delay)
    return resp  # unreachable but satisfies type checker


def _parse_response(
    resp: httpx.Response, model: str
) -> tuple[dict | None, dict, str | None]:
    """Parse a Gemini API response. Returns (parsed_json, metrics, error)."""
    if resp.status_code != 200:
        return None, {}, f"API {resp.status_code}: {resp.text[:200]}"

    data = resp.json()
    usage = data.get("usageMetadata", {})
    input_tok = usage.get("promptTokenCount", 0)
    output_tok = usage.get("candidatesTokenCount", 0)
    thoughts_tok = usage.get("thoughtsTokenCount", 0)

    # Handle blocked/empty responses
    candidates = data.get("candidates", [])
    if not candidates:
        return None, {}, f"No candidates in response: {json.dumps(data)[:200]}"

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        finish_reason = candidates[0].get("finishReason", "unknown")
        return None, {}, f"No parts in response (finishReason={finish_reason})"

    # Extract the actual text (skip thought parts)
    text_parts = [p.get("text", "") for p in parts if not p.get("thought")]
    text = "".join(text_parts).strip()

    if not text:
        return (
            None,
            {},
            "Empty text output (model may have only produced thinking tokens)",
        )

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return None, {}, f"JSON parse error: {e} — raw: {text[:200]}"

    metrics = {
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "thoughts_tokens": thoughts_tok,
        "cost_usd": estimate_cost(model, input_tok, output_tok),
    }
    return parsed, metrics, None


def perceive_one(api_key: str, model: str, item: dict) -> dict:
    """Run visual perception on a single item using local media files."""
    apify = item.get("apify", {})
    media_type = item.get("media_type", "video")
    is_slideshow = apify.get("is_slideshow", False)
    platform = item.get("platform", "tiktok")
    interaction = "saved"
    context = _build_perception_context(item)
    item_id = item.get("id", "")

    result: dict = {
        "parsed_output": None,
        "metrics": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "video_uploaded": False,
        },
        "error": None,
    }

    t0 = time.monotonic()

    # Gemma models don't support video/audio input — skip File API upload entirely
    model_supports_video = "gemini" in model.lower()

    try:
        # ---- VIDEO: upload local file via File API (Gemini only) ----
        if media_type == "video" and model_supports_video:
            local_video = EXP06_MEDIA / f"video_{item_id}.mp4"

            if local_video.exists():
                prompt_text = load_prompt("perception", "observe_video")
                prompt = (
                    prompt_text.replace("{platform}", platform)
                    .replace("{interaction_type}", interaction)
                    .replace("{context}", context)
                )

                video_file_name = upload_file_sync(
                    api_key, str(local_video), "video/mp4"
                )
                if video_file_name:
                    file_uri = wait_for_file_sync(api_key, video_file_name)
                    if file_uri:
                        parts: list[dict] = [
                            {"text": prompt},
                            {
                                "fileData": {
                                    "mimeType": "video/mp4",
                                    "fileUri": file_uri,
                                }
                            },
                        ]
                        resp = _call_gemini(
                            api_key, model, parts, PERCEPTION_MAX_TOKENS
                        )
                        delete_file_sync(api_key, video_file_name)

                        parsed, metrics, error = _parse_response(resp, model)
                        if parsed is not None:
                            result["parsed_output"] = parsed
                            result["metrics"].update(metrics)
                            result["metrics"]["video_uploaded"] = True
                            result["metrics"]["latency_ms"] = int(
                                (time.monotonic() - t0) * 1000
                            )
                            return result
                        else:
                            result["error"] = f"Video: {error}"
                    else:
                        delete_file_sync(api_key, video_file_name)
                        result["error"] = "File API: file never became ACTIVE"

            # Fall through to thumbnail

        # ---- SLIDESHOW: send local images inline ----
        if is_slideshow:
            slides = _find_local_slides(item_id)
            if slides:
                prompt_text = load_prompt("perception", "observe_slideshow")
                prompt = (
                    prompt_text.replace("{platform}", platform)
                    .replace("{interaction_type}", interaction)
                    .replace("{image_count}", str(len(slides)))
                    .replace("{context}", context)
                )
                parts = [{"text": prompt}]
                for slide_path in slides:
                    parts.append(_inline_image_part(slide_path))

                resp = _call_gemini(api_key, model, parts, PERCEPTION_MAX_TOKENS)
                parsed, metrics, error = _parse_response(resp, model)
                if parsed is not None:
                    result["parsed_output"] = parsed
                    result["metrics"].update(metrics)
                else:
                    result["error"] = f"Slideshow: {error}"
                result["metrics"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
                return result

        # ---- SINGLE IMAGE / THUMBNAIL FALLBACK ----
        thumb = _find_local_thumbnail(item_id)
        if not thumb:
            if not result["error"]:
                result["error"] = (
                    f"No local media for {item_id} (checked video, slides, thumb)"
                )
            result["metrics"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
            return result

        prompt_text = load_prompt("perception", "observe_image")
        prompt = (
            prompt_text.replace("{platform}", platform)
            .replace("{interaction_type}", interaction)
            .replace("{context}", context)
        )
        parts = [{"text": prompt}, _inline_image_part(thumb)]

        resp = _call_gemini(api_key, model, parts, PERCEPTION_MAX_TOKENS)
        parsed, metrics, error = _parse_response(resp, model)
        if parsed is not None:
            result["parsed_output"] = parsed
            result["metrics"].update(metrics)
            result["error"] = None  # Clear any prior video error — thumbnail succeeded
        else:
            result["error"] = f"Image fallback: {error}"

    except Exception as e:
        result["error"] = str(e)

    result["metrics"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Classify
# ---------------------------------------------------------------------------


def classify_one(api_key: str, model: str, item: dict, perception: dict | None) -> dict:
    """Run 8-facet classification. Adapted from pipeline.py:_classify_one_sync."""
    apify = item.get("apify", {})
    platform = item.get("platform", "tiktok")
    interaction = "saved"

    result: dict = {
        "parsed_output": None,
        "metrics": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
        },
        "valid": False,
        "tier1": None,
        "validation_errors": [],
        "error": None,
    }

    # Build supplementary metadata context
    context_parts: list[str] = []
    if apify.get("caption"):
        context_parts.append(f"Caption: {apify['caption']}")
    if apify.get("subtitle_text"):
        context_parts.append(f"Subtitles: {apify['subtitle_text'][:500]}")
    if apify.get("hashtags"):
        context_parts.append(
            f"Hashtags: #{', #'.join(str(h) for h in apify['hashtags'][:20])}"
        )
    if item.get("creator"):
        context_parts.append(f"Creator: @{item['creator']}")
    if apify.get("music_metadata"):
        context_parts.append(f"Music: {apify['music_metadata']}")
    if apify.get("duration_seconds") is not None:
        context_parts.append(f"Duration: {apify['duration_seconds']}s")
    if apify.get("comments_top10"):
        clines = [
            f'  {j + 1}. "{c[:120]}"'
            for j, c in enumerate(apify["comments_top10"][:10])
            if c
        ]
        if clines:
            context_parts.append("Top comments:\n" + "\n".join(clines))
    context = "\n".join(context_parts) if context_parts else "(No metadata available.)"

    # Perception summary
    if perception:
        perception_summary = json.dumps(perception, indent=2, default=str)[:6000]
    else:
        perception_summary = (
            "(No perception data available -- classify from metadata only.)"
        )

    prompt = (
        load_prompt("classify", "tier2")
        .replace("{platform}", platform)
        .replace("{interaction_type}", interaction)
        .replace("{perception_summary}", perception_summary)
        .replace("{context}", context)
    )

    # Only attach image if no perception (avoid double-processing)
    item_id = item.get("id", "")
    parts: list[dict] = [{"text": prompt}]
    if not perception:
        thumb = _find_local_thumbnail(item_id)
        if thumb:
            parts.append(_inline_image_part(thumb))

    t0 = time.monotonic()
    try:
        resp = _call_gemini(api_key, model, parts, CLASSIFY_MAX_TOKENS)
        parsed, metrics, error = _parse_response(resp, model)
        if error:
            result["error"] = f"Classify: {error}"
            result["metrics"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
            return result

        result["parsed_output"] = parsed
        result["metrics"].update(metrics)

        # Validate against ontology
        try:
            cr = validate_classification(parsed)
            result["tier1"] = cr.tier1
            result["valid"] = len(cr.tier1) >= 6  # at least 6 of 8 facets filled
            missing = [f for f in FACET_NAMES if f not in cr.tier1]
            if missing:
                result["validation_errors"].append(f"missing_facets: {missing}")
        except Exception as ve:
            result["validation_errors"].append(str(ve))

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
    except Exception as e:
        result["error"] = str(e)

    result["metrics"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Run single item
# ---------------------------------------------------------------------------


def run_item(
    api_key: str,
    model: str,
    item: dict,
    skip_perceive: bool = False,
    reuse_perception_from: str | None = None,
) -> dict:
    """Run full perceive -> classify pipeline for one item."""
    item_id = item.get("id", "unknown")

    # Optionally reuse perception from another model's results
    perception_output = None
    if skip_perceive and reuse_perception_from:
        reuse_path = RESULTS_DIR / reuse_perception_from / f"{item_id}.json"
        if reuse_path.exists():
            prev = json.loads(reuse_path.read_text())
            perception_output = prev.get("pass1_perception", {}).get("parsed_output")

    if not skip_perceive:
        p1 = perceive_one(api_key, model, item)
        perception_output = p1.get("parsed_output")
    else:
        p1 = {
            "parsed_output": perception_output,
            "metrics": {},
            "error": None,
            "skipped": True,
        }

    p2 = classify_one(api_key, model, item, perception_output)

    return {
        "item_id": item_id,
        "model": model,
        "type_key": item.get("_type_key", ""),
        "media_type": item.get("media_type", ""),
        "platform": item.get("platform", ""),
        "pass1_perception": p1,
        "pass2_classification": p2,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemma 4 vs Gemini Flash benchmark")
    parser.add_argument(
        "--models",
        default="gemini-3-flash-preview,gemma-4-31b-it",
        help="Comma-separated model names",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Max items per model (0 = all)"
    )
    parser.add_argument(
        "--types",
        default="tiktok_video,tiktok_slideshow,tiktok_image",
        help="Comma-separated type keys. Default: TikTok only (Instagram CDN URLs expired).",
    )
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument(
        "--skip-perceive",
        action="store_true",
        help="Skip perception, reuse from first model's results",
    )
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env.master")
        sys.exit(1)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    types = [t.strip() for t in args.types.split(",") if t.strip()] or None

    items = load_items(types)
    if args.limit:
        items = items[: args.limit]

    print("=" * 60)
    print("Gemma 4 Benchmark — Tier 2 Processing")
    print("=" * 60)
    print(f"  Models: {', '.join(models)}")
    print(f"  Items: {len(items)}")
    if types:
        print(f"  Types: {', '.join(types)}")
    print()

    for model in models:
        model_dir = RESULTS_DIR / model
        model_dir.mkdir(parents=True, exist_ok=True)

        # Check which items already have results (resume support)
        pending = []
        for item in items:
            result_path = model_dir / f"{item['id']}.json"
            if result_path.exists():
                continue
            pending.append(item)

        done_count = len(items) - len(pending)
        if done_count:
            print(
                f"  [{model}] Resuming: {done_count} already done, {len(pending)} pending"
            )
        else:
            print(
                f"  [{model}] Running {len(pending)} items (concurrency={args.concurrency})"
            )

        if not pending:
            print(f"  [{model}] All items already processed. Delete results/ to rerun.")
            continue

        reuse_from = models[0] if args.skip_perceive and model != models[0] else None

        successes = 0
        failures = 0
        total_cost = 0.0
        t_start = time.monotonic()

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(
                    run_item,
                    GEMINI_API_KEY,
                    model,
                    item,
                    args.skip_perceive,
                    reuse_from,
                ): item
                for item in pending
            }

            for i, future in enumerate(as_completed(futures), start=1):
                item = futures[future]
                try:
                    result = future.result()
                    result_path = model_dir / f"{item['id']}.json"
                    result_path.write_text(json.dumps(result, indent=2, default=str))

                    p1_ok = result["pass1_perception"].get("error") is None
                    p2_ok = result["pass2_classification"].get("error") is None
                    p2_valid = result["pass2_classification"].get("valid", False)

                    p1_cost = (
                        result["pass1_perception"].get("metrics", {}).get("cost_usd", 0)
                    )
                    p2_cost = (
                        result["pass2_classification"]
                        .get("metrics", {})
                        .get("cost_usd", 0)
                    )
                    item_cost = p1_cost + p2_cost
                    total_cost += item_cost

                    status = "OK" if (p1_ok and p2_ok and p2_valid) else "WARN"
                    if not p1_ok or not p2_ok:
                        status = "FAIL"
                        failures += 1
                    else:
                        successes += 1

                    p1_ms = (
                        result["pass1_perception"]
                        .get("metrics", {})
                        .get("latency_ms", 0)
                    )
                    p2_ms = (
                        result["pass2_classification"]
                        .get("metrics", {})
                        .get("latency_ms", 0)
                    )

                    print(
                        f"  [{model}] {i + done_count}/{len(items)} "
                        f"{item['id'][:16]:16s} {status:4s} "
                        f"P1={p1_ms:5d}ms P2={p2_ms:5d}ms "
                        f"${item_cost:.4f}"
                    )

                except Exception as e:
                    failures += 1
                    print(
                        f"  [{model}] {i + done_count}/{len(items)} {item['id'][:16]} ERROR: {e}"
                    )

        elapsed = time.monotonic() - t_start
        print(
            f"\n  [{model}] Done: {successes} ok, {failures} fail, "
            f"${total_cost:.4f} total, {elapsed:.0f}s elapsed\n"
        )

    print("=" * 60)
    print("Results saved to:", RESULTS_DIR)
    print("Next: .venv/bin/python workbench/experiments/07-gemma4-benchmark/compare.py")


if __name__ == "__main__":
    main()
