#!/usr/bin/env python
"""Day 2 v2: Comprehensive Vision + Classification on 50 random TikToks.

Single-command experiment runner. Includes:
- 50 random items from recent 500 favorites (seed=42)
- Apify fetch with full downloads + 10 comments
- Stage 1 perception: full video (File API) + all slideshow images + subtitles + comments in context
- Stage 2 classification: 5-facet vision-informed vs text-only baseline
- 8-facet redundancy test with inter-facet NMI correlation
- Slideshow image informativeness assessment
- Stratified analysis by text-richness tier
- Self-contained HTML eval UI with 6-dimension rubric

Model: gemini-3-flash-preview
Cost estimate: ~$2-3 total

Usage:
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py --phase setup
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py --phase perception
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py --phase classify
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py --phase analysis
    .venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py --phase eval-ui
"""

import argparse
import base64
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))
load_dotenv(REPO_ROOT / "workbench" / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "results" / "vision_v2"
MEDIA_DIR = DATA_DIR / "media"
RESULTS_DIR = DATA_DIR / "results"
MANIFEST_PATH = DATA_DIR / "manifest.json"
EXPORT_PATH = REPO_ROOT / "workbench" / "data" / "my-export" / "full_anonymized.json"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash"  # gemini-3-flash-preview not available for new users yet
INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 0.60
MAX_OUTPUT_TOKENS = 8192

APIFY_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_POLL_S = 5
APIFY_MAX_WAIT_S = 600

SAMPLE_SIZE = 50
SAMPLE_SEED = 42
RECENT_N = 500

PERCEPTION_CONCURRENCY = 4   # video uploads are heavy
CLASSIFY_CONCURRENCY = 6     # text-only calls are light

_VID_RE = re.compile(r"/video/(\d+)")

for d in [DATA_DIR, MEDIA_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Helpers ─────────────────────────────────────────────────────────────

def estimate_cost(in_tok: int, out_tok: int) -> float:
    return (in_tok * INPUT_COST_PER_M + out_tok * OUTPUT_COST_PER_M) / 1_000_000


def safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text[:text.rfind("```")]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try progressively closing open braces/brackets
        # Count unclosed delimiters and close them
        opens = 0
        in_str = False
        escape = False
        for ch in text:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not escape:
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ('{', '['):
                opens += 1
            elif ch in ('}', ']'):
                opens -= 1

        # If we're inside a string value, close it first
        if in_str:
            text += '"'
        # Try adding a neutral value then closing braces
        for prefix in ['', '0', '0.5', 'null', '""']:
            attempt = text + prefix + ('}' * max(opens, 0))
            # Alternate with ] closers
            for attempt2 in [attempt, text + prefix + ']' + '}' * max(opens - 1, 0)]:
                try:
                    return json.loads(attempt2)
                except json.JSONDecodeError:
                    continue

        return {"_parse_error": True, "_raw_text": text[:5000]}


def parse_vtt(vtt_text: str) -> str:
    lines = []
    for line in vtt_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line or line.isdigit():
            continue
        lines.append(line)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def get_text_tier(caption: str, has_subs: bool) -> str:
    clean = (caption or "").strip()
    if len(clean) >= 50 and has_subs:
        return "rich_text"
    elif len(clean) >= 50:
        return "caption_only"
    return "low_text"


def download_file(url: str, dest: Path) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        resp = httpx.get(url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception:
        return None


def image_to_inline(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"inlineData": {"mimeType": "image/jpeg", "data": b64}}


# ── Gemini Client ───────────────────────────────────────────────────────

def gemini_generate(parts: list[dict], max_tokens: int = MAX_OUTPUT_TOKENS,
                    temperature: float = 0.2, json_mode: bool = True) -> dict:
    gen_config = {"maxOutputTokens": max_tokens, "temperature": temperature}
    if json_mode:
        gen_config["responseMimeType"] = "application/json"
    resp = httpx.post(
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": parts}], "generationConfig": gen_config},
        timeout=120,
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
        resp = client.put(upload_url, headers={
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
            "Content-Length": str(file_size),
        }, content=f.read())
    resp.raise_for_status()
    client.close()
    return resp.json()["file"]["name"]


def gemini_wait_for_file(file_name: str, timeout: int = 120) -> str:
    client = httpx.Client(timeout=30)
    elapsed = 0
    while elapsed < timeout:
        resp = client.get(f"{GEMINI_API_BASE}/{file_name}", params={"key": GEMINI_API_KEY})
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


def gemini_delete_file(file_name: str):
    try:
        httpx.delete(f"{GEMINI_API_BASE}/{file_name}", params={"key": GEMINI_API_KEY}, timeout=10)
    except Exception:
        pass


# ── Result Saving ───────────────────────────────────────────────────────

def save_result(item_id: str, stage: str, prompt: str, api_resp: dict,
                parsed: dict, latency_ms: int, upload_ms: int = 0,
                ctx: dict | None = None) -> dict:
    usage = api_resp.get("usageMetadata", {})
    in_tok = usage.get("promptTokenCount", 0)
    out_tok = usage.get("candidatesTokenCount", 0)
    record = {
        "item_id": item_id, "stage": stage, "model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_text": prompt,
        "raw_response": api_resp,
        "parsed_output": parsed,
        "metrics": {
            "input_tokens": in_tok, "output_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "cost_usd": round(estimate_cost(in_tok, out_tok), 6),
            "latency_ms": latency_ms, "upload_ms": upload_ms,
        },
        "context_used": ctx or {},
    }
    out_dir = RESULTS_DIR / stage
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{item_id}.json", "w") as f:
        json.dump(record, f, indent=2, default=str)
    return record


# ── Context Builder ─────────────────────────────────────────────────────

def build_context(item: dict) -> str:
    apify = item["apify_data"]
    author = apify.get("authorMeta") or {}
    music = apify.get("musicMeta") or {}
    hashtags = [h.get("name", "") for h in (apify.get("hashtags") or []) if isinstance(h, dict)]

    parts = [f"Caption: {item['caption'][:500]}"]
    if hashtags:
        parts.append(f"Hashtags: #{', #'.join(hashtags[:15])}")
    parts.append(f"Creator: @{author.get('name', '?')} ({author.get('nickName', '')})")
    if music.get("musicName"):
        parts.append(f"Music: {music['musicName']} by {music.get('musicAuthor', '?')}")
    parts.append(f"Duration: {item['duration']}s")
    parts.append(f"Engagement: {apify.get('playCount', 0):,} plays, {apify.get('diggCount', 0):,} likes")

    sub = item.get("subtitle_text", "")
    if sub:
        parts.append(f"Subtitle transcript: {sub[:1000]}")

    comments = item.get("comments") or []
    if comments:
        clines = [f'  {j+1}. "{c.get("text","")[:100]}" ({c.get("diggCount",0):,} likes)'
                  for j, c in enumerate(comments[:5])]
        parts.append("Top comments:\n" + "\n".join(clines))

    return "\n".join(parts)


# ── Prompts ─────────────────────────────────────────────────────────────

VIDEO_PERCEPTION_PROMPT = """You are analyzing a TikTok video. Produce a detailed perception report — describe everything you observe. Do not classify or judge.

CONTEXT (metadata from the post):
{context}

Watch the video carefully and return JSON:
{{
  "scene_timeline": [
    {{"time_range": "0:00-0:XX", "visual_description": "what is visually happening",
      "audio_description": "what is being said or heard — transcribe key dialogue verbatim",
      "text_on_screen": "transcribe ALL overlaid text, captions, watermarks",
      "key_objects": ["identifiable objects, products, brands visible in this segment"]}}
  ],
  "overall_summary": "comprehensive 3-5 sentence description of the entire video — what is it about, what happens, what is the point?",
  "people": [{{"description": "appearance, clothing, role, actions", "is_creator": true, "speaking": true, "identified_as": "name if recognizable, null otherwise"}}],
  "entities_detected": [
    {{"name": "specific name (not generic descriptions)", "type": "person|place|product|brand|song|book|movie|tv_show|app|restaurant|website",
      "how_identified": "visual|audio|text_overlay|metadata", "confidence": "high|medium|low"}}
  ],
  "presentation_style": {{
    "primary_format": "talking_head|voiceover|text_overlay|cinematic|tutorial_demo|skit|compilation|reaction|slideshow|before_after|pov|other",
    "camera_work": "static|handheld|panning|transitions|split_screen|overhead|selfie",
    "editing_style": "minimal|jump_cuts|heavy_effects|before_after|montage|slow_motion"
  }},
  "audio_profile": {{
    "speech": true,
    "speech_summary": "brief summary of what is said if speech present",
    "music": "none|background|featured|music_video",
    "music_identified": "song name and artist if identifiable",
    "sound_effects": false
  }},
  "visual_mood": "the emotional atmosphere conveyed by visuals, pacing, lighting, and tone",
  "topic_hints": ["2-3 topic areas this content addresses"],
  "affect_hints": ["emotional tones present — how would a viewer FEEL watching this?"],
  "genre_hints": ["content format types — what KIND of TikTok is this?"]
}}

CRITICAL INSTRUCTIONS:
- Be SPECIFIC. Name every identifiable person, place, product, song, show, brand.
- Transcribe key dialogue and speech VERBATIM where possible.
- Transcribe ALL on-screen text including overlays, captions, watermarks.
- If you recognize a celebrity, character, TV show, movie, or song — NAME IT with confidence level.
- Distinguish between what you SEE, what you HEAR, and what you INFER from metadata.
- Precision over hedging. "Tony Soprano from The Sopranos" not "a man who appears to be a character"."""


def build_slideshow_prompt(n_images: int) -> str:
    image_instruction = "each image carefully, one by one" if n_images > 1 else "the image"
    media_desc = f"photo carousel with {n_images} images" if n_images > 1 else "image post"
    return f"""You are analyzing a TikTok {media_desc}. Produce a detailed perception report. Do not classify or judge.

CONTEXT (metadata from the post):
{{context}}

Analyze {image_instruction} and return JSON:
{{{{
  "per_image": [
    {{{{"image_number": 1, "description": "detailed description of what the image shows",
      "text_detected": "transcribe ALL readable text exactly as written",
      "objects": ["every identifiable object, product, brand, logo"],
      "entities": ["named things: people, places, products, restaurants, apps"]}}}}
  ],
  "overall_summary": "comprehensive 3-5 sentence description — what is this post about, what is the point?",
  "narrative_thread": "what story, message, or recommendation do these images convey together?",
  "entities_detected": [
    {{{{"name": "specific name", "type": "person|place|product|brand|song|book|movie|tv_show|app|restaurant|website",
      "how_identified": "visual|text_overlay|metadata", "confidence": "high|medium|low"}}}}
  ],
  "presentation_style": {{{{
    "primary_format": "text_cards|photo_dump|product_showcase|infographic|meme|screenshot|recommendation_list|room_tour|outfit_layout|other",
    "visual_style": "minimal|aesthetic|informational|meme|collage|professional|casual"
  }}}},
  "visual_mood": "the emotional atmosphere and aesthetic of the images",
  "topic_hints": ["2-3 topic areas"],
  "affect_hints": ["emotional tones — how would a viewer FEEL looking at this?"],
  "genre_hints": ["content format types — what KIND of TikTok is this?"]
}}}}

CRITICAL INSTRUCTIONS:
- Transcribe ALL visible text in every image — menus, signs, labels, captions, watermarks, everything.
- Name every identifiable person, place, product, restaurant, brand, logo.
- For recommendation/list posts: extract every specific item recommended.
- For outfit/room posts: describe specific items, brands, colors, styles.
- Precision over hedging."""


def build_ontology(facets: list[str]) -> str:
    from app.services.ontology import ONTOLOGY_V1
    lines = [f"## Classification Ontology ({len(facets)} Facets)\n"]
    for f in facets:
        lines.append(f"**{f}** — pick exactly ONE:\n  {', '.join(ONTOLOGY_V1[f])}\n")
    lines.append("""INSTRUCTIONS:
- For each facet, select the single best tier-1 label.
- Suggest 1-3 "micro_labels" for nuance (free-form refinements).
- Confidence: 0.0-1.0 (0.5=uncertain, 0.8=confident, 0.95=very sure).
- If content fits multiple labels, pick dominant one, use micro_labels for secondary.
- If no label fits, use "other" and explain in micro_labels.

Return JSON: {"facet": {"label": "...", "micro_labels": [...], "confidence": 0.X}, ...}""")
    return "\n".join(lines)


FIVE_FACETS = ["topic", "genre", "affect", "presentation_style", "content_provenance"]
ALL_FACETS = ["topic", "genre", "affect", "presentation_style", "content_provenance",
              "communicative_intent", "creator_role", "viewer_orientation"]

CLASSIFY_VISION_PROMPT = """Classify this TikTok content using the following ontology.

{ontology}

ALL AVAILABLE CONTEXT:
- Vision analysis (Stage 1): {perception}
- Caption: {caption}
- Hashtags: {hashtags}
- Creator: @{username}
- Music: {music}
- Subtitle transcript: {subtitles}
- Top comments: {comments}
- Engagement: {play_count} plays, {like_count} likes

Use ALL context — especially the vision analysis — for classification.
Return ONLY valid JSON."""

CLASSIFY_TEXT_PROMPT = """Classify this TikTok content using the following ontology.
You do NOT have visual analysis — classify based on text signals only.

{ontology}

TEXT CONTEXT:
- Caption: {caption}
- Hashtags: {hashtags}
- Creator: @{username}
- Music: {music}
- Subtitle transcript: {subtitles}
- Top comments: {comments}
- Engagement: {play_count} plays, {like_count} likes

Where text signals are ambiguous, set lower confidence.
Return ONLY valid JSON."""

INFORMATIVENESS_PROMPT = """For each image in this TikTok carousel, classify as:
- "informational" — unique content, text, recommendations, data, products
- "decorative" — title card, "follow me" card, aesthetic filler, duplicate

Return JSON:
{{"images": [{{"index": 1, "type": "informational|decorative", "reason": "brief reason"}}]}}"""


# ── Apify ───────────────────────────────────────────────────────────────

def apify_fetch(platform_ids: list[str]) -> list[dict]:
    urls = [f"https://www.tiktok.com/share/video/{pid}/" for pid in platform_ids]
    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}", "Content-Type": "application/json"}
    client = httpx.Client(timeout=60)
    resp = client.post(f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs", headers=headers,
        json={"postURLs": urls, "resultsPerPage": len(urls),
              "shouldDownloadVideos": True, "shouldDownloadCovers": True,
              "shouldDownloadSlideshowImages": True, "shouldDownloadSubtitles": True,
              "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES", "commentsPerPost": 10})
    resp.raise_for_status()
    run_id = resp.json()["data"]["id"]
    print(f"  Apify run: {run_id}")
    elapsed = 0
    while elapsed < APIFY_MAX_WAIT_S:
        time.sleep(APIFY_POLL_S)
        elapsed += APIFY_POLL_S
        resp = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}", headers=headers)
        status = resp.json()["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    if status != "SUCCEEDED":
        print(f"  FAILED: {status}")
        client.close()
        return []
    cost = resp.json()["data"].get("usageTotalUsd", 0)
    dataset_id = resp.json()["data"]["defaultDatasetId"]
    resp = client.get(f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json", headers=headers)
    items = resp.json()
    client.close()
    print(f"  Returned {len(items)} items, cost: ${cost:.4f}")
    return items if isinstance(items, list) else []


def fetch_comments(url: str, limit: int = 10) -> list[dict]:
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return []
        c = resp.json()
        return c[:limit] if isinstance(c, list) else []
    except Exception:
        return []


# ── Phase: Setup ────────────────────────────────────────────────────────

def phase_setup():
    print("=" * 60)
    print("PHASE: SETUP — Sample selection + Apify + media download")
    print("=" * 60)

    # 1. Sample selection
    with open(EXPORT_PATH) as f:
        export = json.load(f)
    favs = export["Likes and Favorites"]["Favorite Videos"]["FavoriteVideoList"]
    recent = favs[:RECENT_N]
    random.seed(SAMPLE_SEED)
    sample = random.sample(recent, SAMPLE_SIZE)

    selected = []
    for item in sample:
        url = item.get("Link") or item.get("link", "")
        m = _VID_RE.search(url)
        if m:
            selected.append({"platform_id": m.group(1), "url": url, "date": item.get("Date") or item.get("date")})
    print(f"  Selected {len(selected)} items (seed={SAMPLE_SEED})")

    # 2. Apify fetch
    pids = [s["platform_id"] for s in selected]
    apify_items = apify_fetch(pids)

    by_pid = {}
    for item in apify_items:
        pid = str(item.get("id", ""))
        if pid:
            by_pid[pid] = item
        web = item.get("webVideoUrl", "")
        m = _VID_RE.search(web)
        if m:
            by_pid[m.group(1)] = item

    # 3. Build manifest
    manifest_items = []
    for s in selected:
        pid = s["platform_id"]
        apify = by_pid.get(pid, {})
        vm = apify.get("videoMeta") or {}
        is_ss = bool(apify.get("isSlideshow"))
        has_subs = len(vm.get("subtitleLinks") or []) > 0
        caption = apify.get("text", "")

        manifest_items.append({
            "platform_id": pid, "matched": bool(apify), "date": s["date"],
            "media_type": "slideshow" if is_ss else "video",
            "duration": vm.get("duration", 0), "has_subtitles": has_subs,
            "text_tier": get_text_tier(caption, has_subs),
            "caption": caption,
            "web_url": apify.get("webVideoUrl", ""),
            "apify_data": apify,
        })

    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "total": len(manifest_items),
                "matched": sum(1 for m in manifest_items if m["matched"]),
                "items": manifest_items}
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    matched = [m for m in manifest_items if m["matched"]]
    print(f"  Matched: {len(matched)}/{len(manifest_items)}")
    print(f"  Videos: {sum(1 for m in matched if m['media_type']=='video')}")
    print(f"  Slideshows: {sum(1 for m in matched if m['media_type']=='slideshow')}")

    # 4. Download media + comments + subtitles
    print("\n  Downloading media...")
    stats = {"vid": 0, "thumb": 0, "slide": 0, "sub": 0, "comment_items": 0}

    for item in matched:
        pid = item["platform_id"]
        apify = item["apify_data"]
        vm = apify.get("videoMeta") or {}

        if vm.get("coverUrl"):
            if download_file(vm["coverUrl"], MEDIA_DIR / f"thumb_{pid}.jpg"):
                stats["thumb"] += 1

        if vm.get("downloadAddr") and item["media_type"] == "video":
            if download_file(vm["downloadAddr"], MEDIA_DIR / f"video_{pid}.mp4"):
                stats["vid"] += 1

        for j, link in enumerate(apify.get("slideshowImageLinks") or []):
            url = link.get("downloadLink") or link.get("tiktokLink")
            if url:
                download_file(url, MEDIA_DIR / f"slide_{pid}_{j:03d}.jpg")
        if apify.get("slideshowImageLinks"):
            stats["slide"] += 1

        # Subtitles
        sub_text = ""
        for sl in (vm.get("subtitleLinks") or []):
            dl = sl.get("downloadLink")
            if dl:
                vtt_path = MEDIA_DIR / f"sub_{pid}.vtt"
                if download_file(dl, vtt_path):
                    sub_text = parse_vtt(vtt_path.read_text(errors="replace"))
                    stats["sub"] += 1
                    break
        item["subtitle_text"] = sub_text

        # Comments
        comments_url = apify.get("commentsDatasetUrl")
        comments = fetch_comments(comments_url) if comments_url else []
        if comments:
            stats["comment_items"] += 1
        item["comments"] = comments

    # Save updated manifest
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    tiers = {}
    for m in matched:
        tiers[m["text_tier"]] = tiers.get(m["text_tier"], 0) + 1

    print(f"  Videos: {stats['vid']}, Thumbs: {stats['thumb']}, Slideshows: {stats['slide']}")
    print(f"  Subtitles: {stats['sub']}, Items with comments: {stats['comment_items']}")
    print(f"  Text tiers: {tiers}")
    print("  Setup complete.\n")


# ── Phase: Perception ───────────────────────────────────────────────────

def phase_perception():
    print("=" * 60)
    print("PHASE: PERCEPTION — Stage 1 (concurrent)")
    print("=" * 60)

    with open(MANIFEST_PATH) as f:
        items = [m for m in json.load(f)["items"] if m["matched"]]

    def process_one(item: dict) -> dict | None:
        pid = item["platform_id"]
        context = build_context(item)
        ctx = {"has_caption": bool(item["caption"]),
               "has_subtitles": bool(item.get("subtitle_text")),
               "has_comments": bool(item.get("comments")),
               "subtitle_length": len(item.get("subtitle_text", "")),
               "comment_count": len(item.get("comments", [])),
               "text_richness_tier": item["text_tier"]}

        start = time.time()
        upload_ms = 0
        prompt = ""

        try:
            if item["media_type"] == "video":
                vpath = MEDIA_DIR / f"video_{pid}.mp4"
                if not vpath.exists():
                    return None
                prompt = VIDEO_PERCEPTION_PROMPT.format(context=context)
                t0 = time.time()
                fn = gemini_upload_file(str(vpath), "video/mp4")
                uri = gemini_wait_for_file(fn)
                upload_ms = int((time.time() - t0) * 1000)
                parts = [{"text": prompt}, {"fileData": {"mimeType": "video/mp4", "fileUri": uri}}]
                api_resp = gemini_generate(parts)
                gemini_delete_file(fn)
            else:
                imgs = sorted(MEDIA_DIR.glob(f"slide_{pid}_*.jpg"))
                if not imgs:
                    thumb = MEDIA_DIR / f"thumb_{pid}.jpg"
                    if not thumb.exists():
                        return None
                    imgs = [thumb]
                prompt = build_slideshow_prompt(len(imgs)).replace("{context}", context)
                parts = [{"text": prompt}] + [image_to_inline(p) for p in imgs]
                api_resp = gemini_generate(parts)

            latency = int((time.time() - start) * 1000)
            text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
            parsed = safe_json_parse(text)
            return save_result(pid, "perception", prompt, api_resp, parsed, latency, upload_ms, ctx)

        except Exception as e:
            latency = int((time.time() - start) * 1000)
            save_result(pid, "perception", prompt, {}, {"_error": str(e)}, latency, upload_ms, ctx)
            return {"_error": str(e), "item_id": pid}

    results = []
    total_cost = 0.0
    done = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=PERCEPTION_CONCURRENCY) as ex:
        futs = {ex.submit(process_one, item): item for item in items}
        for fut in as_completed(futs):
            item = futs[fut]
            pid = item["platform_id"]
            done += 1
            r = fut.result()
            elapsed = time.time() - t0
            if r and "_error" not in r:
                results.append(r)
                c = r["metrics"]["cost_usd"]
                total_cost += c
                ent = len(r.get("parsed_output", {}).get("entities_detected", []))
                err = "_parse_error" in r.get("parsed_output", {})
                print(f"  [{done}/{len(items)}] {pid}: {'PERR' if err else 'OK'} | "
                      f"{r['metrics']['input_tokens']}+{r['metrics']['output_tokens']} tok | "
                      f"{ent} ent | ${c:.4f} | {elapsed:.0f}s")
            elif r:
                print(f"  [{done}/{len(items)}] {pid}: ERR — {r.get('_error','')[:60]} | {elapsed:.0f}s")
            else:
                print(f"  [{done}/{len(items)}] {pid}: SKIP | {elapsed:.0f}s")

    wall = time.time() - t0
    perr = sum(1 for r in results if "_parse_error" in r.get("parsed_output", {}))
    print(f"\n  Perception done: {len(results)} items, ${total_cost:.4f}, {perr} parse errors, {wall:.0f}s\n")


# ── Phase: Classify ─────────────────────────────────────────────────────

def _classify_item(item: dict, ontology: str, prompt_tmpl: str, stage: str,
                   perception_text: str | None) -> dict | None:
    pid = item["platform_id"]
    apify = item["apify_data"]
    author = apify.get("authorMeta") or {}
    music = apify.get("musicMeta") or {}
    ht = [h.get("name", "") for h in (apify.get("hashtags") or []) if isinstance(h, dict)]
    comments = item.get("comments") or []
    ct = "; ".join(f'"{c.get("text","")[:80]}"' for c in comments[:5]) if comments else "(none)"

    fmt = {"ontology": ontology, "caption": item["caption"][:300],
           "hashtags": ", ".join(ht[:10]) or "(none)",
           "username": author.get("name", "?"), "music": music.get("musicName", "(none)"),
           "subtitles": item.get("subtitle_text", "(none)")[:500], "comments": ct,
           "play_count": f"{apify.get('playCount',0):,}", "like_count": f"{apify.get('diggCount',0):,}"}
    if perception_text is not None:
        fmt["perception"] = perception_text

    prompt = prompt_tmpl.format(**fmt)
    start = time.time()
    try:
        api_resp = gemini_generate([{"text": prompt}], max_tokens=MAX_OUTPUT_TOKENS)
        latency = int((time.time() - start) * 1000)
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)
        return save_result(pid, stage, prompt, api_resp, parsed, latency,
                           ctx={"has_perception": perception_text is not None,
                                         "text_richness_tier": item["text_tier"]})
    except Exception as e:
        return {"_error": str(e), "item_id": pid}


def phase_classify():
    print("=" * 60)
    print("PHASE: CLASSIFY — 5-facet vision + text-only + 8-facet")
    print("=" * 60)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    items = [m for m in manifest["items"] if m["matched"]]

    # Load perception results
    perc_by_pid = {}
    perc_dir = RESULTS_DIR / "perception"
    if perc_dir.exists():
        for fp in perc_dir.glob("*.json"):
            with open(fp) as f:
                r = json.load(f)
            perc_by_pid[r["item_id"]] = json.dumps(r.get("parsed_output", {}), indent=1, default=str)[:4000]

    ont5 = build_ontology(FIVE_FACETS)
    ont8 = build_ontology(ALL_FACETS)

    for label, tmpl, stage, use_perc, facet_list in [
        ("5-facet VISION", CLASSIFY_VISION_PROMPT, "classify_5facet_vision", True, FIVE_FACETS),
        ("5-facet TEXT-ONLY", CLASSIFY_TEXT_PROMPT, "classify_5facet_text", False, FIVE_FACETS),
        ("8-facet VISION", CLASSIFY_VISION_PROMPT, "classify_8facet_vision", True, ALL_FACETS),
    ]:
        ont = ont5 if len(facet_list) == 5 else ont8
        target = [i for i in items if (not use_perc or i["platform_id"] in perc_by_pid)]
        print(f"\n  --- {label} ({len(target)} items, {CLASSIFY_CONCURRENCY} concurrent) ---")

        results = []
        total_cost = 0.0
        done = 0
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=CLASSIFY_CONCURRENCY) as ex:
            futs = {}
            for item in target:
                perc_text = perc_by_pid.get(item["platform_id"]) if use_perc else None
                futs[ex.submit(_classify_item, item, ont, tmpl, stage, perc_text)] = item

            for fut in as_completed(futs):
                item = futs[fut]
                pid = item["platform_id"]
                done += 1
                r = fut.result()
                if r and "_error" not in r:
                    results.append(r)
                    total_cost += r["metrics"]["cost_usd"]
                    labels = {f: r.get("parsed_output", {}).get(f, {}).get("label", "?")
                              for f in facet_list[:3]}
                    if done % 10 == 0 or done == len(target):
                        print(f"    [{done}/{len(target)}] ${total_cost:.4f} | {time.time()-t0:.0f}s")
                else:
                    err = r.get("_error", "?") if r else "no result"
                    print(f"    [{done}] {pid}: ERR — {str(err)[:50]}")

        print(f"    Done: {len(results)} items, ${total_cost:.4f}, {time.time()-t0:.0f}s")

    # NMI correlation for 8-facet
    print("\n  --- Inter-Facet Correlation (NMI) ---")
    try:
        from sklearn.metrics import normalized_mutual_info_score
        from sklearn.preprocessing import LabelEncoder

        facet_labels = {f: [] for f in ALL_FACETS}
        valid = 0
        ef_dir = RESULTS_DIR / "classify_8facet_vision"
        if ef_dir.exists():
            for fp in ef_dir.glob("*.json"):
                with open(fp) as f:
                    r = json.load(f)
                p = r.get("parsed_output", {})
                if "_parse_error" in p:
                    continue
                ok = True
                for facet in ALL_FACETS:
                    lbl = p.get(facet, {}).get("label") if isinstance(p.get(facet), dict) else None
                    if not lbl:
                        ok = False
                        break
                    facet_labels[facet].append(lbl)
                if ok:
                    valid += 1

        if valid >= 10:
            pairs = [("genre", "communicative_intent"), ("topic", "communicative_intent"),
                     ("genre", "creator_role"), ("affect", "viewer_orientation"),
                     ("presentation_style", "genre"), ("topic", "genre")]
            for fa, fb in pairs:
                if len(facet_labels[fa]) == len(facet_labels[fb]) and len(facet_labels[fa]) >= 10:
                    la = LabelEncoder().fit_transform(facet_labels[fa])
                    lb = LabelEncoder().fit_transform(facet_labels[fb])
                    nmi = normalized_mutual_info_score(la, lb)
                    flag = " *** REDUNDANT" if nmi > 0.5 else ""
                    print(f"    {fa} <-> {fb}: NMI = {nmi:.3f}{flag}")
        else:
            print(f"    Only {valid} valid items — need >=10 for NMI")
    except ImportError:
        print("    sklearn not available — skipping NMI")

    print()


# ── Phase: Analysis ─────────────────────────────────────────────────────

def phase_analysis():
    print("=" * 60)
    print("PHASE: ANALYSIS — Slideshow informativeness + stratified summary")
    print("=" * 60)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    items = [m for m in manifest["items"] if m["matched"]]

    # Slideshow informativeness
    ss_items = [m for m in items if m["media_type"] == "slideshow"]
    if ss_items:
        print(f"\n  --- Slideshow informativeness ({len(ss_items)} items) ---")
        total_info, total_deco, total_imgs = 0, 0, 0

        def assess_ss(item):
            pid = item["platform_id"]
            imgs = sorted(MEDIA_DIR.glob(f"slide_{pid}_*.jpg"))
            if len(imgs) < 2:
                return None
            parts = [{"text": INFORMATIVENESS_PROMPT}] + [image_to_inline(p) for p in imgs]
            start = time.time()
            try:
                api = gemini_generate(parts, max_tokens=1024)
                lat = int((time.time() - start) * 1000)
                text = api["candidates"][0]["content"]["parts"][0]["text"]
                parsed = safe_json_parse(text)
                r = save_result(pid, "slideshow_informativeness", INFORMATIVENESS_PROMPT, api, parsed, lat)
                r["_n"] = len(imgs)
                return r
            except Exception as e:
                return {"_error": str(e)}

        with ThreadPoolExecutor(max_workers=CLASSIFY_CONCURRENCY) as ex:
            futs = {ex.submit(assess_ss, item): item for item in ss_items}
            for fut in as_completed(futs):
                r = fut.result()
                if r and "_error" not in r:
                    imgs_data = r.get("parsed_output", {}).get("images", [])
                    ni = sum(1 for x in imgs_data if x.get("type") == "informational")
                    nd = sum(1 for x in imgs_data if x.get("type") == "decorative")
                    total_info += ni
                    total_deco += nd
                    total_imgs += r.get("_n", 0)

        if total_imgs:
            print(f"    Total images: {total_imgs}")
            print(f"    Informational: {total_info} ({total_info/total_imgs*100:.0f}%)")
            print(f"    Decorative: {total_deco} ({total_deco/total_imgs*100:.0f}%)")

    # Stratified analysis
    print("\n  --- Stratified Analysis ---")

    def load_stage(stage):
        d = RESULTS_DIR / stage
        out = {}
        if d.exists():
            for fp in d.glob("*.json"):
                with open(fp) as f:
                    r = json.load(f)
                out[r["item_id"]] = r
        return out

    perc = load_stage("perception")
    cls_v = load_stage("classify_5facet_vision")
    cls_t = load_stage("classify_5facet_text")

    total_cost = sum(r["metrics"]["cost_usd"] for stage in ["perception", "classify_5facet_vision",
                     "classify_5facet_text", "classify_8facet_vision", "slideshow_informativeness"]
                     for r in load_stage(stage).values())

    print(f"\n  Total cost across all stages: ${total_cost:.4f}")
    print(f"  Perception: {len(perc)}, Classify vision: {len(cls_v)}, Classify text: {len(cls_t)}")

    tiers = {"rich_text": [], "caption_only": [], "low_text": []}
    for item in items:
        pid = item["platform_id"]
        if pid in perc and pid in cls_v and pid in cls_t:
            tiers[item["text_tier"]].append(pid)

    for tier, pids in tiers.items():
        if not pids:
            continue
        print(f"\n    {tier} ({len(pids)} items):")
        ent_counts = [len(perc[p].get("parsed_output", {}).get("entities_detected", [])) for p in pids]
        print(f"      Avg entities (Stage 1): {np.mean(ent_counts):.1f}")

        agreements = {f: 0 for f in FIVE_FACETS}
        compared = 0
        for p in pids:
            v = cls_v[p].get("parsed_output", {})
            t = cls_t[p].get("parsed_output", {})
            if "_parse_error" in v or "_parse_error" in t:
                continue
            compared += 1
            for f in FIVE_FACETS:
                vl = v.get(f, {}).get("label") if isinstance(v.get(f), dict) else None
                tl = t.get(f, {}).get("label") if isinstance(t.get(f), dict) else None
                if vl and tl and vl == tl:
                    agreements[f] += 1

        if compared:
            print(f"      Vision vs text-only agreement ({compared} items):")
            for f in FIVE_FACETS:
                pct = agreements[f] / compared * 100
                print(f"        {f}: {pct:.0f}%")

    print()


# ── Phase: Eval UI ──────────────────────────────────────────────────────

def phase_eval_ui():
    print("=" * 60)
    print("PHASE: EVAL UI — Generating HTML")
    print("=" * 60)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    def load_stage(stage):
        d = RESULTS_DIR / stage
        out = {}
        if d.exists():
            for fp in d.glob("*.json"):
                with open(fp) as f:
                    r = json.load(f)
                out[r["item_id"]] = r
        return out

    perc = load_stage("perception")
    cls_v = load_stage("classify_5facet_vision")
    cls_t = load_stage("classify_5facet_text")

    eval_items = []
    for item in manifest["items"]:
        if not item["matched"]:
            continue
        pid = item["platform_id"]
        if pid not in perc:
            continue

        p = perc[pid].get("parsed_output", {})
        cv = cls_v.get(pid, {}).get("parsed_output", {})
        ct = cls_t.get(pid, {}).get("parsed_output", {})

        eval_items.append({
            "id": pid,
            "web_url": item.get("web_url", ""),
            "caption": item["caption"][:300],
            "hashtags": [h.get("name", "") for h in (item["apify_data"].get("hashtags") or []) if isinstance(h, dict)][:10],
            "media_type": item["media_type"],
            "duration": item["duration"],
            "text_tier": item["text_tier"],
            "has_subtitles": item.get("has_subtitles", False),
            "perception_summary": p.get("overall_summary", json.dumps(p, default=str)[:500]),
            "perception_entities": p.get("entities_detected", []),
            "perception_scenes": p.get("scene_timeline", []),
            "perception_style": p.get("presentation_style", {}),
            "perception_mood": p.get("visual_mood", ""),
            "perception_topics": p.get("topic_hints", []),
            "classify_vision": {f: (cv.get(f, {}) if isinstance(cv.get(f), dict) else {}) for f in FIVE_FACETS} if cv and "_parse_error" not in cv else {},
            "classify_text": {f: (ct.get(f, {}) if isinstance(ct.get(f), dict) else {}) for f in FIVE_FACETS} if ct and "_parse_error" not in ct else {},
            "cost": perc[pid].get("metrics", {}).get("cost_usd", 0),
        })

    ej = json.dumps(eval_items, indent=None, default=str)

    html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Attic Eval v2</title><style>'
    html += '*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#F8F7F4;color:#1C1B18;padding:20px}'
    html += '.hdr{display:flex;justify-content:space-between;align-items:center;padding:16px;background:#fff;border:1px solid #E6E4DE;border-radius:8px;margin-bottom:16px}'
    html += '.card{background:#fff;border:1px solid #E6E4DE;border-radius:8px;padding:20px;margin-bottom:12px}'
    html += '.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;background:#F0EEE8;margin:2px}'
    html += '.tag.rich_text{background:#d4edda}.tag.caption_only{background:#fff3cd}.tag.low_text{background:#f8d7da}'
    html += '.pre{white-space:pre-wrap;font-size:13px;background:#FAFAF8;padding:10px;border-radius:6px;max-height:250px;overflow-y:auto}'
    html += '.ent{display:inline-block;padding:2px 6px;border-radius:4px;font-size:11px;background:#E6E4DE;margin:2px}'
    html += '.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.facet{display:flex;justify-content:space-between;padding:3px 0;font-size:13px;border-bottom:1px solid #F0EEE8}'
    html += '.dim{display:flex;align-items:center;gap:8px;margin:6px 0}.dim-name{width:140px;font-size:13px;font-weight:500}'
    html += '.dim button{width:32px;height:32px;border:1px solid #E6E4DE;border-radius:6px;background:#fff;cursor:pointer;font-size:13px}'
    html += '.dim button.sel{background:#2C2926;color:#fff;border-color:#2C2926}'
    html += '.hint{font-size:11px;color:#9C9890}textarea{width:100%;padding:6px;border:1px solid #E6E4DE;border-radius:6px;font-size:13px;min-height:50px;resize:vertical;margin-top:8px}'
    html += 'button.nav{padding:6px 14px;border:1px solid #E6E4DE;border-radius:6px;background:#fff;cursor:pointer}button.exp{padding:8px 16px;background:#2C2926;color:#fff;border:none;border-radius:6px;cursor:pointer}'
    html += '</style></head><body>'
    html += '<div class="hdr"><b>Attic Eval v2</b><span id="prog"></span><div><button class="nav" onclick="prev()">Prev</button> <button class="nav" onclick="next()">Next</button> <button class="exp" onclick="exp()">Export</button></div></div>'
    html += '<div id="c"></div><script>'
    html += 'const I=' + ej + ';'
    html += '''const D=[{k:"accuracy",n:"Accuracy",h:["Major errors","Mostly correct","All correct"]},{k:"completeness",n:"Completeness",h:["Surface only","Got gist","Full content"]},{k:"specificity",n:"Specificity",h:["All vague","Mix named/generic","Named everything"]},{k:"entity_coverage",n:"Entity Coverage",h:["Missed obvious","Got major","Caught all"]},{k:"classification_signal",n:"Class Signal",h:["Topic ambiguous","Topic/Genre clear","All 5 facets"]},{k:"vision_added_value",n:"Vision Value",h:["Nothing new","Useful detail","Major reveal"]}];
let ci=0,sc=JSON.parse(localStorage.getItem("av2")||"{}");
function r(){const i=I[ci],s=sc[i.id]||{},ent=(i.perception_entities||[]).slice(0,12),scenes=(i.perception_scenes||[]).slice(0,6);
let sh=scenes.map(s=>`<div style="font-size:12px;margin:3px 0"><b>${s.time_range||""}</b>: ${s.visual_description||s.description||""}${s.audio_description?"<br><i>"+s.audio_description+"</i>":""}</div>`).join("");
let ch="";const ff=["topic","genre","affect","presentation_style","content_provenance"];
if(Object.keys(i.classify_vision).length){ch=`<div class="grid"><div><b style="font-size:12px;color:#9C9890">Vision-Informed</b>${ff.map(f=>{const v=i.classify_vision[f]||{};return`<div class="facet"><span>${f}</span><span style="color:#9C9890">${v.label||"?"}</span></div>`}).join("")}</div><div><b style="font-size:12px;color:#9C9890">Text-Only</b>${ff.map(f=>{const v=i.classify_text[f]||{};return`<div class="facet"><span>${f}</span><span style="color:#9C9890">${v.label||"?"}</span></div>`}).join("")}</div></div>`}
let rb=D.map(d=>{const v=s[d.k]||0;return`<div class="dim"><span class="dim-name">${d.n}</span>${[1,2,3].map(n=>`<button class="${v===n?"sel":""}" onclick="ss('${d.k}',${n})">${n}</button>`).join("")}<span class="hint">${d.h[v-1]||""}</span></div>`}).join("");
const tot=D.reduce((a,d)=>a+(s[d.k]||0),0);
document.getElementById("c").innerHTML=`<div class="card"><h3>${ci+1}/${I.length} — ${i.id}</h3><div style="margin:6px 0"><span class="tag">${i.media_type}</span><span class="tag">${i.duration}s</span><span class="tag ${i.text_tier}">${i.text_tier}</span>${i.has_subtitles?'<span class="tag">subs</span>':""}</div><p style="font-size:13px"><b>Caption:</b> ${i.caption}</p><p style="font-size:12px;color:#9C9890">Hashtags: ${i.hashtags.map(h=>"#"+h).join(" ")}</p>${i.web_url?`<a href="${i.web_url}" target="_blank" style="color:#A06840;font-size:13px">Open on TikTok</a>`:""}</div><div class="card"><b style="font-size:12px;color:#9C9890">STAGE 1: PERCEPTION</b><div class="pre">${i.perception_summary||"(none)"}</div>${sh?`<div style="margin-top:8px"><b style="font-size:12px">Scenes:</b>${sh}</div>`:""}<div style="margin-top:6px">${ent.map(e=>`<span class="ent">${e.name||"?"} (${e.type||"?"})</span>`).join("")}</div><p style="font-size:11px;color:#9C9890;margin-top:6px">Style: ${JSON.stringify(i.perception_style)} | Mood: ${i.perception_mood} | Cost: $${(i.cost||0).toFixed(4)}</p></div><div class="card"><b style="font-size:12px;color:#9C9890">STAGE 2: CLASSIFICATION</b>${ch||"<p>No results</p>"}</div><div class="card" style="background:#FAFAF8"><b>Score (1=Poor 2=Adequate 3=Strong)</b>${rb}<textarea placeholder="Notes..." oninput="sn(this.value)">${s.notes||""}</textarea><div style="margin-top:6px;font-weight:500">Total: ${tot}/18</div></div>`;
document.getElementById("prog").textContent=Object.values(sc).filter(s=>D.some(d=>s[d.k])).length+"/"+I.length+" scored"}
function ss(d,v){const i=I[ci];if(!sc[i.id])sc[i.id]={};sc[i.id][d]=v;localStorage.setItem("av2",JSON.stringify(sc));r()}
function sn(t){const i=I[ci];if(!sc[i.id])sc[i.id]={};sc[i.id].notes=t;localStorage.setItem("av2",JSON.stringify(sc))}
function prev(){if(ci>0){ci--;r();scrollTo(0,0)}}function next(){if(ci<I.length-1){ci++;r();scrollTo(0,0)}}
function exp(){const b=new Blob([JSON.stringify(sc,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="eval_scores_v2.json";a.click()}
document.addEventListener("keydown",e=>{if(e.key==="ArrowLeft")prev();if(e.key==="ArrowRight")next()});r();'''
    html += '</script></body></html>'

    path = DATA_DIR / "eval_ui.html"
    path.write_text(html)
    print(f"  Eval UI: {path}")
    print(f"  Items: {len(eval_items)}")
    print(f"  Open: file://{path}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Day 2 v2: Vision + Classification Experiment")
    parser.add_argument("--phase", default="all",
                        choices=["all", "setup", "perception", "classify", "analysis", "eval-ui"])
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    if not APIFY_API_TOKEN and args.phase in ("all", "setup"):
        print("ERROR: APIFY_API_TOKEN not set")
        sys.exit(1)

    phases = {
        "setup": phase_setup,
        "perception": phase_perception,
        "classify": phase_classify,
        "analysis": phase_analysis,
        "eval-ui": phase_eval_ui,
    }

    if args.phase == "all":
        for name, fn in phases.items():
            fn()
    else:
        phases[args.phase]()


if __name__ == "__main__":
    main()
