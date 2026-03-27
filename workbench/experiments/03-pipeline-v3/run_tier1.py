#!/usr/bin/env python
"""Tier 1: Fast ingest-time processing with keyframes.

Single Gemini call per item using 3 keyframes (first, middle, last) + metadata.
Produces: summary, entities, classification, and model-constructed embedding text.
Generates OpenAI embeddings and outputs a search index.

Usage:
    python workbench/experiments/03-pipeline-v3/run_tier1.py workbench/data/golden_set_template.json
    python workbench/experiments/03-pipeline-v3/run_tier1.py workbench/data/golden_set_template.json --limit 5
    python workbench/experiments/03-pipeline-v3/run_tier1.py workbench/data/golden_set_template.json --compare
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
RESULTS_DIR = SCRIPT_DIR / "results"
MEDIA_DIR = RESULTS_DIR / "pipeline_v3_media"

load_dotenv(REPO_ROOT / "workbench" / ".env")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-3-flash-preview"
EMBEDDING_MODEL = "text-embedding-3-small"

INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 0.60
MAX_OUTPUT_TOKENS = 4096
CONCURRENCY = 8  # keyframe-only calls are light — no video uploads

TIER1_DIR = RESULTS_DIR / "tier1"
TIER1_RESULTS_DIR = TIER1_DIR / "results"
INDEX_PATH = TIER1_DIR / "search_index.json"

# ── Tier 1 Prompt ──────────────────────────────────────────────────────────

TIER1_PROMPT = """You are processing a TikTok video for a personal media library. Your output
powers search, browse filters, and aggregate stats. Users will search for
specific items ("that grilled cheese recipe"), browse by category ("show me
fitness videos"), and ask questions about their collection ("what topics do I
save most?").

You are seeing 3 keyframes (beginning, middle, end) from the video — not the
full video. Extract what you can from these frames plus the metadata below.

METADATA:
{context}

Return JSON with this exact structure:

{{
  "summary": "2-3 sentences: what is this TikTok about? Why would someone save it? Be specific — name people, products, places, not generic descriptions.",
  "entities": [
    {{
      "name": "specific name (e.g., 'Adidas Samba', not 'sneakers')",
      "type": "person|place|product|brand|song|artist|book|movie_or_show|app_or_tool|restaurant|exercise|recipe|ingredient|clothing|technique|trend_or_meme|cultural_reference|event|podcast|game",
      "relevance": "primary|supporting"
    }}
  ],
  "topic": {{
    "primary": "label",
    "secondary": "label or null"
  }},
  "genre": "label",
  "affect": {{
    "dominant": "label",
    "secondary": "label or null"
  }},
  "viewer_orientation": "why the user saved this: active_learning|passive_consumption|inspiration_saving|shopping_research|social_sharing|emotional_regulation",
  "embedding_text": "A 100-150 word paragraph optimized for semantic search. Write this as if you're describing the video to someone who wants to find it later. Include: the main subject, key entities by name, what happens, what kind of content it is. Prioritize specificity — 'Adidas Samba sneaker recommendation for European travel' over 'shoe video'. Include any on-screen text, named people, places, or products."
}}

TOPIC LABELS (pick one primary, optional secondary):
food, fashion, beauty, fitness, travel, music, dance, comedy, education,
technology, gaming, sports, pets, art, books, movies_tv, news, politics,
science, nature, diy, finance, relationships, parenting, health, career,
real_estate, automotive, other

Key definitions:
- fitness: Exercise must be VISIBLE or explicitly discussed. NOT content that merely has fitness hashtags.
- comedy: Primary purpose is humor. For funny-but-informative content, use the informative topic and let affect capture the humor.
- education: Structured teaching. Career advice = career, not education.
- health: Wellbeing/medical. Distinct from fitness (exercise).

GENRE LABELS:
tutorial, review, vlog, skit, storytime, haul, asmr, challenge, reaction,
compilation, before_after, day_in_life, get_ready_with_me, unboxing, recipe,
workout, news_commentary, interview, timelapse, meme, duet, room_tour,
outfit_showcase, ranking, edit, pov, other

AFFECT LABELS:
funny, wholesome, sad, angry, nostalgic, inspiring, informative, cringe,
satisfying, scary, relaxing, shocking, neutral

Key definitions:
- inspiring: Genuine emotional uplift — NOT merely useful/informative content.
- informative: Saved to LEARN or REFERENCE. Tutorials, tips, advice, recommendations.
- neutral: Only when no other label applies.

INSTRUCTIONS:
- Extract up to 5 entities. Focus on what someone would search for.
- Use comments to identify entities, cultural references, and context.
- On-screen text in keyframes is high-value — transcribe names, products, places.
- Be specific in entity names: "Nike Pegasus 39" not "running shoes".
- The embedding_text field is critical — it determines whether users can find this item via search. Write it like a rich description, not a label list."""


# ── Helpers ────────────────────────────────────────────────────────────────

def estimate_cost(in_tok: int, out_tok: int) -> float:
    return (in_tok * INPUT_COST_PER_M + out_tok * OUTPUT_COST_PER_M) / 1_000_000


def safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return parsed[0]
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    return item
            return {"_parse_error": True}
        return parsed
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw_text": text[:2000]}


def image_to_inline(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return {"inlineData": {"mimeType": mime, "data": b64}}


def extract_3_keyframes(video_path: Path) -> list[Path]:
    """Extract 3 keyframes: first frame, middle, and last."""
    # Get video duration first
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(result.stdout.strip())
    except Exception:
        duration = 30  # fallback

    # Extract at 3 timestamps: 0s, middle, near-end
    timestamps = [0, duration / 2, max(duration - 1, 0)]
    frames = []

    for i, ts in enumerate(timestamps):
        output = MEDIA_DIR / f"t1_keyframe_{video_path.stem}_{i}.jpg"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
                "-frames:v", "1", "-q:v", "2", str(output),
            ], capture_output=True, timeout=10, check=True)
            if output.exists() and output.stat().st_size > 0:
                frames.append(output)
        except Exception:
            pass

    return frames


def build_context(item: dict) -> str:
    apify = item.get("apify", {})
    parts = []

    caption = apify.get("caption") or ""
    if caption.strip():
        parts.append(f"Caption: {caption.strip()[:500]}")

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

    comments = apify.get("comments_top10") or []
    if comments:
        clines = [f'  {j+1}. "{c[:120]}"' for j, c in enumerate(comments[:10]) if c]
        if clines:
            parts.append("Top comments:\n" + "\n".join(clines))

    return "\n".join(parts)


def gemini_generate(parts: list[dict]) -> dict:
    gen_config = {
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.2,
        "responseMimeType": "application/json",
    }
    resp = httpx.post(
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": parts}], "generationConfig": gen_config},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def embed_batch(texts: list[str]) -> list[list[float]]:
    texts = [t if t.strip() else "(no content)" for t in texts]
    all_embeddings = []
    client = httpx.Client(timeout=60)
    batch_size = 50

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
        usage = data.get("usage", {})
        print(f"  Embedding batch {i // batch_size + 1}: {len(batch)} items, "
              f"{usage.get('total_tokens', '?')} tokens")

    client.close()
    return all_embeddings


# ── Pipeline ───────────────────────────────────────────────────────────────

def process_item(item: dict) -> dict | None:
    pid = item["id"]
    context = build_context(item)
    prompt = TIER1_PROMPT.format(context=context)

    start = time.time()

    # Get keyframes
    video_path = MEDIA_DIR / f"video_{pid}.mp4"
    thumb_path = MEDIA_DIR / f"thumb_{pid}.jpg"

    if video_path.exists():
        frames = extract_3_keyframes(video_path)
    elif thumb_path.exists():
        frames = [thumb_path]
    else:
        return None

    # Build parts: text prompt + keyframe images
    parts = [{"text": prompt}] + [image_to_inline(f) for f in frames]

    try:
        api_resp = gemini_generate(parts)
        latency = int((time.time() - start) * 1000)

        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)

        usage = api_resp.get("usageMetadata", {})
        in_tok = usage.get("promptTokenCount", 0)
        out_tok = usage.get("candidatesTokenCount", 0)

        result = {
            "item_id": pid,
            "parsed_output": parsed,
            "metrics": {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
                "cost_usd": round(estimate_cost(in_tok, out_tok), 6),
                "latency_ms": latency,
                "keyframe_count": len(frames),
            },
        }

        # Save per-item result
        TIER1_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (TIER1_RESULTS_DIR / f"{pid}.json").write_text(json.dumps(result, indent=2, default=str))
        return result

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {"item_id": pid, "_error": str(e), "metrics": {"latency_ms": latency}}


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_tier1.py <golden_set.json> [--limit N] [--compare]")
        sys.exit(1)

    items = json.loads(Path(sys.argv[1]).read_text())
    compare = "--compare" in sys.argv

    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    if limit:
        items = items[:limit]

    TIER1_DIR.mkdir(parents=True, exist_ok=True)
    TIER1_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Tier 1 Pipeline — {len(items)} items")
    print(f"  Model: {GEMINI_MODEL}")
    print(f"  Concurrency: {CONCURRENCY}")
    print(f"  Keyframes: 3 per video (first, middle, last)")

    # ── Process ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("TIER 1: Single-pass keyframe processing")
    print(f"{'='*60}\n")

    results: list[dict] = []
    total_cost = 0.0
    t0 = time.time()
    done = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(process_item, item): item for item in items}
        for fut in as_completed(futs):
            item = futs[fut]
            pid = item["id"]
            done += 1
            result = fut.result()
            elapsed = time.time() - t0

            if result and "_error" not in result:
                results.append(result)
                c = result["metrics"]["cost_usd"]
                total_cost += c
                po = result.get("parsed_output") or {}
                ent_count = len(po.get("entities") or [])
                topic = (po.get("topic") or {}).get("primary", "?")
                has_err = po.get("_parse_error", False)
                print(f"  [{done}/{len(items)}] {pid}: "
                      f"{'PERR' if has_err else 'OK'} | "
                      f"topic={topic:12s} | {ent_count} ent | "
                      f"${c:.4f} | {result['metrics']['latency_ms']/1000:.1f}s | {elapsed:.0f}s")
            elif result:
                print(f"  [{done}/{len(items)}] {pid}: ERR — {result.get('_error', '')[:60]}")
            else:
                print(f"  [{done}/{len(items)}] {pid}: SKIP (no media)")

    wall = time.time() - t0
    ok_count = len(results)
    parse_errs = sum(1 for r in results if (r.get("parsed_output") or {}).get("_parse_error"))

    print(f"\nTier 1 done: {ok_count}/{len(items)} OK | ${total_cost:.4f} | "
          f"{parse_errs} parse errors | {wall:.0f}s")
    print(f"  Avg cost: ${total_cost / ok_count:.5f}/item" if ok_count else "")
    print(f"  Avg latency: {sum(r['metrics']['latency_ms'] for r in results) / ok_count / 1000:.1f}s" if ok_count else "")

    # ── Build search index ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("Building search index with model-constructed embedding text")
    print(f"{'='*60}\n")

    # Load subtitles if available
    sub_path = REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "golden_set_subtitles.json"
    subtitles = json.loads(sub_path.read_text()) if sub_path.exists() else {}

    index_items = []
    embedding_texts = []

    # Map results by ID
    results_by_id = {r["item_id"]: r for r in results}

    for item in items:
        pid = item["id"]
        r = results_by_id.get(pid)
        if not r:
            continue

        po = r.get("parsed_output") or {}
        if not isinstance(po, dict) or po.get("_parse_error"):
            continue

        apify = item.get("apify", {})
        topic = po.get("topic") or {}
        affect = po.get("affect") or {}

        emb_text = po.get("embedding_text") or po.get("summary") or ""
        embedding_texts.append(emb_text)

        index_items.append({
            "id": pid,
            "url": item.get("url", ""),
            "creator": item.get("creator", ""),
            "collection": item.get("collection", ""),
            "thumbnail_url": apify.get("thumbnail_url"),
            "caption": apify.get("caption") or "",
            "duration": apify.get("duration_seconds"),
            "music_metadata": apify.get("music_metadata"),
            "summary": po.get("summary") or "",
            "takeaways": [],
            "entities": po.get("entities") or [],
            "structured_content": None,
            "audio_actual": None,
            "audio_match": None,
            "topic_primary": topic.get("primary") if isinstance(topic, dict) else None,
            "topic_secondary": topic.get("secondary") if isinstance(topic, dict) else None,
            "genre": po.get("genre"),
            "affect": [
                {"label": affect.get("dominant"), "tier": "dominant"},
                {"label": affect.get("secondary"), "tier": "secondary"},
            ] if isinstance(affect, dict) and affect.get("dominant") else [],
            "viewer_orientation": po.get("viewer_orientation"),
            "subtitle_text": subtitles.get(pid),
            "embedding_text_model": emb_text,
        })

    print(f"Generating embeddings for {len(embedding_texts)} items...")
    embeddings = embed_batch(embedding_texts)

    for i, item in enumerate(index_items):
        item["embedding_tier1"] = embeddings[i]

    INDEX_PATH.write_text(json.dumps(index_items, indent=None))
    size_mb = INDEX_PATH.stat().st_size / 1024 / 1024
    print(f"\nSaved: {INDEX_PATH.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")

    # ── Comparison with Tier 2 ─────────────────────────────────────────────
    if compare:
        t2_p2_dir = RESULTS_DIR / "pipeline_v3" / "pass2_classification"
        if t2_p2_dir.exists():
            print(f"\n{'='*60}")
            print("TIER 1 vs TIER 2 COMPARISON")
            print(f"{'='*60}\n")

            topic_agree = 0
            topic_total = 0
            genre_agree = 0
            genre_total = 0
            t1_ent_counts = []
            t2_ent_counts = []

            t2_p1_dir = RESULTS_DIR / "pipeline_v3" / "pass1_perception"

            for item in index_items:
                pid = item["id"]
                t2_path = t2_p2_dir / f"{pid}.json"
                if not t2_path.exists():
                    continue

                t2 = json.loads(t2_path.read_text())
                t2_po = t2.get("parsed_output") or {}
                if not isinstance(t2_po, dict):
                    continue

                # Topic comparison
                t1_topic = item.get("topic_primary")
                t2_topic = (t2_po.get("topic") or {}).get("primary")
                if t1_topic and t2_topic:
                    topic_total += 1
                    if t1_topic == t2_topic:
                        topic_agree += 1

                # Genre comparison
                t1_genre = item.get("genre")
                t2_genre = (t2_po.get("genre") or {}).get("label")
                if t1_genre and t2_genre:
                    genre_total += 1
                    if t1_genre == t2_genre:
                        genre_agree += 1

                # Entity count
                t1_ent_counts.append(len(item.get("entities") or []))
                t1_p1_path = t2_p1_dir / f"{pid}.json"
                if t1_p1_path.exists():
                    t2_p1 = json.loads(t1_p1_path.read_text())
                    t2_p1_po = t2_p1.get("parsed_output") or {}
                    if isinstance(t2_p1_po, dict):
                        t2_ent_counts.append(len(t2_p1_po.get("entities") or []))

            print(f"  Topic agreement: {topic_agree}/{topic_total} ({topic_agree/topic_total:.0%})" if topic_total else "")
            print(f"  Genre agreement: {genre_agree}/{genre_total} ({genre_agree/genre_total:.0%})" if genre_total else "")
            if t1_ent_counts:
                print(f"  Tier 1 entities avg: {sum(t1_ent_counts)/len(t1_ent_counts):.1f}")
            if t2_ent_counts:
                print(f"  Tier 2 entities avg: {sum(t2_ent_counts)/len(t2_ent_counts):.1f}")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("TIER 1 SUMMARY")
    print(f"{'='*60}")
    print(f"  Items: {ok_count}/{len(items)}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Total time: {wall:.0f}s")
    print(f"  Cost per item: ${total_cost / ok_count:.5f}" if ok_count else "")
    print(f"  Projected 1000 items: ${total_cost / ok_count * 1000:.2f}, "
          f"~{wall / ok_count * 1000 / CONCURRENCY:.0f}s" if ok_count else "")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
