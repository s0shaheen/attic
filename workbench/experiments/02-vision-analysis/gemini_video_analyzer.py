#!/usr/bin/env python
"""Day 2: Vision Analysis Experimentation — Gemini video/image analyzer.

Compares thumbnail, keyframe, and full-video approaches with multiple prompt
variants to find the optimal Stage 1 perception prompt for Attic's two-tier
classification pipeline.

Usage:
    # Step 0: Fetch 15 test items from Apify + download media
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase setup

    # Dry run (estimate cost, no API calls)
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase all --dry-run

    # Run specific phases
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase thumbnail
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase video
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase slideshow
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase keyframes
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase grounding

    # Run everything
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase all

    # Generate comparison reports
    .venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py --phase compare
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / "workbench" / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash"

# Apify actor
APIFY_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_POLL_INTERVAL_S = 5
APIFY_MAX_WAIT_S = 600

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "results" / "vision_analysis_samples"
MEDIA_DIR = DATA_DIR / "media"
RESULTS_DIR = DATA_DIR / "results"
COMPARISONS_DIR = DATA_DIR / "comparisons"
MANIFEST_PATH = DATA_DIR / "sample_manifest.json"

# Cost rates (Gemini 2.5 Flash — per million tokens)
INPUT_COST_PER_M = 0.15   # $0.15/M input tokens
OUTPUT_COST_PER_M = 0.60   # $0.60/M output tokens (non-thinking)
VIDEO_TOKENS_PER_SEC = 263
AUDIO_TOKENS_PER_SEC = 32
IMAGE_TOKENS = 258  # per image

# Timeouts
GENERATE_TIMEOUT = 120.0
UPLOAD_TIMEOUT = 300.0
FILE_POLL_TIMEOUT = 120

# ── The 15 Test Items ───────────────────────────────────────────────────────

SAMPLE_ITEMS = [
    {"platform_id": "7449805282663730465", "type": "video", "description": "Recipe / cooking"},
    {"platform_id": "7444730264225434926", "type": "video", "description": "Self help"},
    {"platform_id": "7445960995224210718", "type": "image", "description": "Thoughtful quote over meme photo"},
    {"platform_id": "7453243752853884203", "type": "video", "description": "Sincere + funny video about missing girlfriend"},
    {"platform_id": "7447017695310040362", "type": "video", "description": "Comedy POV meme about brown family parties"},
    {"platform_id": "7452692724307791136", "type": "video", "description": "Productivity related"},
    {"platform_id": "7443060682406235400", "type": "image", "description": "Attack on Titan fan post w/ Kendrick Lamar"},
    {"platform_id": "7446186256205204744", "type": "carousel", "description": "NYC pizza recommendations"},
    {"platform_id": "7438318246736022827", "type": "video", "description": "Career advice"},
    {"platform_id": "7450154856829979935", "type": "carousel", "description": "Male room tour"},
    {"platform_id": "7457247449665637654", "type": "carousel", "description": "Men's style inspiration — outfit layouts, no text"},
    {"platform_id": "7204493467324665093", "type": "video", "description": "Instructive skiing tutorial for beginners"},
    {"platform_id": "7458375076895903022", "type": "video", "description": "Cinematic short film teaser"},
    {"platform_id": "7458381815716367649", "type": "video", "description": "Corecore edit — Tony Soprano, Rust Cohle, etc. over Radiohead"},
    {"platform_id": "7429027711529553183", "type": "video", "description": "Movie review of Hostiles with somber music"},
]

_TIKTOK_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


# ── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class SampleItem:
    platform_id: str
    expected_type: str  # video, image, carousel
    description: str
    apify_data: dict = field(default_factory=dict)

    @property
    def is_video(self) -> bool:
        return self.expected_type == "video"

    @property
    def is_carousel(self) -> bool:
        return self.expected_type == "carousel"

    @property
    def is_image(self) -> bool:
        return self.expected_type == "image"

    @property
    def is_slideshow(self) -> bool:
        return self.is_carousel or self.is_image

    @property
    def duration(self) -> int:
        return (self.apify_data.get("videoMeta") or {}).get("duration", 0)

    @property
    def cover_url(self) -> str | None:
        return (self.apify_data.get("videoMeta") or {}).get("coverUrl")

    @property
    def download_url(self) -> str | None:
        return (self.apify_data.get("videoMeta") or {}).get("downloadAddr")

    @property
    def slideshow_image_urls(self) -> list[str]:
        links = self.apify_data.get("slideshowImageLinks") or []
        return [l.get("downloadLink") or l.get("tiktokLink", "") for l in links if isinstance(l, dict)]

    @property
    def caption(self) -> str:
        return self.apify_data.get("text", "")

    @property
    def hashtags(self) -> list[str]:
        return [h.get("name", "") for h in (self.apify_data.get("hashtags") or []) if isinstance(h, dict)]

    @property
    def creator_username(self) -> str:
        return (self.apify_data.get("authorMeta") or {}).get("name", "")

    @property
    def creator_nickname(self) -> str:
        return (self.apify_data.get("authorMeta") or {}).get("nickName", "")

    @property
    def music_name(self) -> str:
        return (self.apify_data.get("musicMeta") or {}).get("musicName", "")

    @property
    def music_author(self) -> str:
        return (self.apify_data.get("musicMeta") or {}).get("musicAuthor", "")

    @property
    def play_count(self) -> int:
        return self.apify_data.get("playCount", 0)

    @property
    def like_count(self) -> int:
        return self.apify_data.get("diggCount", 0)

    @property
    def subtitle_links(self) -> list[dict]:
        return (self.apify_data.get("videoMeta") or {}).get("subtitleLinks") or []


@dataclass
class ExperimentResult:
    item_id: str
    approach: str       # thumbnail, video, keyframes, slideshow, grounding
    variant: str        # T1, T2, V1, V2, etc.
    model: str
    timestamp: str
    prompt_text: str
    raw_response: dict = field(default_factory=dict)
    parsed_output: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    upload_ms: int = 0
    process_wait_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "approach": self.approach,
            "variant": self.variant,
            "model": self.model,
            "timestamp": self.timestamp,
            "prompt_text": self.prompt_text,
            "parsed_output": self.parsed_output,
            "metrics": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
                "latency_ms": self.latency_ms,
                "cost_usd": round(self.cost_usd, 6),
                "upload_ms": self.upload_ms,
                "process_wait_ms": self.process_wait_ms,
            },
            "error": self.error,
            "raw_response": self.raw_response,
        }


# ── Gemini Client (sync httpx) ─────────────────────────────────────────────

_gemini_client: httpx.Client | None = None


def _get_gemini_client() -> httpx.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = httpx.Client(timeout=GENERATE_TIMEOUT)
    return _gemini_client


def gemini_generate(
    parts: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.2,
    json_mode: bool = True,
    tools: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Call Gemini generateContent. Returns (parsed_output, raw_response).

    If json_mode is True, sets responseMimeType to application/json and
    parses the text output as JSON. Otherwise returns raw text in parsed_output
    as {"text": "..."}.
    """
    client = _get_gemini_client()
    gen_config: dict = {
        "maxOutputTokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        gen_config["responseMimeType"] = "application/json"

    body: dict = {
        "contents": [{"parts": parts}],
        "generationConfig": gen_config,
    }
    if tools:
        body["tools"] = tools

    resp = client.post(
        f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()

    # Parse response
    candidate = data["candidates"][0]
    text = candidate["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})

    if json_mode:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"_raw_text": text, "_parse_error": True}
    else:
        parsed = {"text": text}
        # Extract grounding if present
        grounding_meta = candidate.get("groundingMetadata", {})
        grounding = []
        for chunk in grounding_meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                grounding.append({"uri": web["uri"], "title": web.get("title", "")})
        if grounding:
            parsed["grounding_sources"] = grounding

    raw = {
        "usage": usage,
        "finish_reason": candidate.get("finishReason"),
    }
    return parsed, raw


def gemini_upload_file(file_path: str, mime_type: str) -> str:
    """Upload a file to Gemini File API. Returns the file URI (files/xxx)."""
    file_size = os.path.getsize(file_path)
    display_name = Path(file_path).name

    client = httpx.Client(timeout=UPLOAD_TIMEOUT)

    # Step 1: Initiate resumable upload
    resp = client.post(
        "https://generativelanguage.googleapis.com/upload/v1beta/files",
        params={"key": GEMINI_API_KEY},
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
        },
        json={"file": {"displayName": display_name}},
    )
    resp.raise_for_status()
    upload_url = resp.headers["X-Goog-Upload-URL"]

    # Step 2: Upload file bytes
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
    file_info = resp.json().get("file", {})
    file_name = file_info["name"]  # e.g. "files/abc123"
    client.close()

    return file_name


def gemini_wait_for_file(file_name: str, timeout: int = FILE_POLL_TIMEOUT) -> str:
    """Poll until a Gemini file is ACTIVE. Returns the file URI."""
    client = httpx.Client(timeout=30)
    elapsed = 0
    while elapsed < timeout:
        resp = client.get(
            f"{GEMINI_API_BASE}/{file_name}",
            params={"key": GEMINI_API_KEY},
        )
        resp.raise_for_status()
        state = resp.json().get("state", "")
        if state == "ACTIVE":
            uri = resp.json().get("uri", f"https://generativelanguage.googleapis.com/v1beta/{file_name}")
            client.close()
            return uri
        if state == "FAILED":
            client.close()
            raise RuntimeError(f"File processing failed: {file_name}")
        time.sleep(2)
        elapsed += 2

    client.close()
    raise TimeoutError(f"File {file_name} did not become ACTIVE within {timeout}s")


def gemini_delete_file(file_name: str) -> None:
    """Delete a file from Gemini storage."""
    client = httpx.Client(timeout=15)
    try:
        client.delete(
            f"{GEMINI_API_BASE}/{file_name}",
            params={"key": GEMINI_API_KEY},
        )
    except Exception:
        pass  # best effort cleanup
    finally:
        client.close()


# ── Media Helpers ───────────────────────────────────────────────────────────

def download_file(url: str, dest: Path) -> Path | None:
    """Download a URL to a local file. Returns None on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    try:
        client = httpx.Client(timeout=120, follow_redirects=True)
        resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        client.close()
        return dest
    except httpx.HTTPStatusError as e:
        print(f"    WARNING: Download failed ({e.response.status_code}): {url[:80]}...")
        return None
    except httpx.HTTPError as e:
        print(f"    WARNING: Download error: {e}")
        return None


def extract_keyframes(video_path: Path, threshold: float = 0.3) -> list[Path]:
    """Extract keyframes from a video using FFmpeg scene detection."""
    out_dir = video_path.parent / f"keyframes_{video_path.stem}"
    out_dir.mkdir(exist_ok=True)

    # Check if already extracted
    existing = sorted(out_dir.glob("frame_*.jpg"))
    if existing:
        return existing

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfn",
        str(out_dir / "frame_%04d.jpg"),
        "-y", "-loglevel", "warning",
    ]
    result = subprocess.run(cmd, capture_output=True)

    frames = sorted(out_dir.glob("frame_*.jpg"))
    # If scene detection found 0 frames or failed, fallback to fps-based extraction
    if not frames:
        cmd_fallback = [
            "ffmpeg", "-i", str(video_path),
            "-vf", "fps=0.5",
            "-vsync", "vfn",
            str(out_dir / "frame_%04d.jpg"),
            "-y", "-loglevel", "warning",
        ]
        subprocess.run(cmd_fallback, capture_output=True)
        frames = sorted(out_dir.glob("frame_*.jpg"))

    return frames


def image_to_inline_data(path_or_url: str | Path) -> dict:
    """Convert an image file or URL to Gemini inlineData part."""
    if isinstance(path_or_url, Path) or (isinstance(path_or_url, str) and not path_or_url.startswith("http")):
        img_bytes = Path(path_or_url).read_bytes()
    else:
        resp = httpx.get(path_or_url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        img_bytes = resp.content
    b64 = base64.b64encode(img_bytes).decode()
    return {"inlineData": {"mimeType": "image/jpeg", "data": b64}}


# ── Apify Fetch (for Step 0) ───────────────────────────────────────────────

def fetch_apify_items(platform_ids: list[str]) -> list[dict]:
    """Fetch items from Apify with full download options."""
    urls = [f"https://www.tiktok.com/share/video/{pid}/" for pid in platform_ids]

    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }
    client = httpx.Client(timeout=60)

    # Start run
    print(f"  Starting Apify run for {len(urls)} URLs...")
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
    run_id = resp.json()["data"]["id"]
    print(f"  Run ID: {run_id}")

    # Poll for completion
    elapsed = 0
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

    if status != "SUCCEEDED":
        print(f"  ERROR: Apify run ended with status: {status}")
        client.close()
        return []

    cost = status_data.get("usageTotalUsd", 0)
    print(f"  Apify run succeeded. Cost: ${cost:.4f}")

    # Fetch dataset items
    dataset_id = status_data["defaultDatasetId"]
    resp = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers,
    )
    resp.raise_for_status()
    items = resp.json()
    client.close()

    return items if isinstance(items, list) else []


# ── Prompt Registries ───────────────────────────────────────────────────────

# -- Thumbnail prompts --

THUMBNAIL_PROMPTS = {
    "T1": {
        "name": "Minimal Unstructured",
        "context": "vision_only",
        "prompt": (
            "Describe what you see in this TikTok thumbnail.\n"
            'Return JSON: {"description": "...", "objects": [...], "text_detected": "..."}'
        ),
    },
    "T2": {
        "name": "Structured Extraction",
        "context": "vision_only",
        "prompt": (
            "Analyze this TikTok thumbnail. Extract in JSON:\n"
            "{\n"
            '  "scene_description": "2-3 sentences describing the scene",\n'
            '  "visible_people": "count, appearance, actions, expressions",\n'
            '  "objects_and_products": ["every identifiable object, product, brand"],\n'
            '  "text_on_screen": "ALL visible text including overlays, watermarks",\n'
            '  "setting_and_location": "where this appears to take place",\n'
            '  "presentation_style": "talking_head|text_overlay|overhead_shot|cinematic|selfie|screenshot|other",\n'
            '  "visual_mood": "emotional tone from colors, lighting, composition",\n'
            '  "content_type_guess": "best guess at content type"\n'
            "}\n"
            "Be SPECIFIC. Name products, brands, locations if identifiable."
        ),
    },
    "T3": {
        "name": "Vision-Only No Metadata",
        "context": "vision_only",
        "prompt": (
            "You are analyzing this image with no other context. "
            "Only describe what is visually present. "
            "Do not speculate about audio, narration, or off-screen content.\n\n"
            "Analyze this TikTok thumbnail. Extract in JSON:\n"
            "{\n"
            '  "scene_description": "2-3 sentences describing the scene",\n'
            '  "visible_people": "count, appearance, actions, expressions",\n'
            '  "objects_and_products": ["every identifiable object, product, brand"],\n'
            '  "text_on_screen": "ALL visible text including overlays, watermarks",\n'
            '  "setting_and_location": "where this appears to take place",\n'
            '  "presentation_style": "talking_head|text_overlay|overhead_shot|cinematic|selfie|screenshot|other",\n'
            '  "visual_mood": "emotional tone from colors, lighting, composition",\n'
            '  "content_type_guess": "best guess at content type"\n'
            "}\n"
            "Be SPECIFIC. Name products, brands, locations if identifiable."
        ),
    },
    "T4": {
        "name": "Vision + Full Metadata",
        "context": "vision_plus_metadata",
        "prompt_template": (
            "Metadata for this TikTok:\n"
            "- Caption: {caption}\n"
            "- Hashtags: {hashtags}\n"
            "- Creator: @{username} ({nickname})\n"
            "- Music: {music_name} by {music_author}\n"
            "- Duration: {duration}s\n"
            "- Engagement: {play_count} plays, {like_count} likes\n\n"
            "IMPORTANT: Prefix descriptions with \"VISIBLE:\" for things you see "
            "or \"INFERRED:\" for things you derive from metadata.\n\n"
            "Analyze this TikTok thumbnail. Extract in JSON:\n"
            "{{\n"
            '  "scene_description": "2-3 sentences describing the scene",\n'
            '  "visible_people": "count, appearance, actions, expressions",\n'
            '  "objects_and_products": ["every identifiable object, product, brand"],\n'
            '  "text_on_screen": "ALL visible text including overlays, watermarks",\n'
            '  "setting_and_location": "where this appears to take place",\n'
            '  "presentation_style": "talking_head|text_overlay|overhead_shot|cinematic|selfie|screenshot|other",\n'
            '  "visual_mood": "emotional tone from colors, lighting, composition",\n'
            '  "content_type_guess": "best guess at content type"\n'
            "}}\n"
            "Be SPECIFIC. Name products, brands, locations if identifiable."
        ),
    },
}

# -- Video prompts --

VIDEO_PROMPTS = {
    "V1": {
        "name": "Minimal Temporal",
        "prompt": (
            "Watch this TikTok video and describe what happens.\n"
            "Return JSON:\n"
            "{\n"
            '  "overall_summary": "2-3 sentences",\n'
            '  "scene_descriptions": [{"timestamp": "0:00-0:15", "description": "..."}],\n'
            '  "objects": [...],\n'
            '  "text_on_screen": "...",\n'
            '  "audio_description": "..."\n'
            "}"
        ),
    },
    "V2": {
        "name": "Comprehensive Perception (Stage 1 candidate)",
        "prompt": (
            "You are a content analysis system performing Stage 1 perception on a TikTok video.\n"
            "Your job is to DESCRIBE what you observe — do not classify or judge.\n\n"
            "Return JSON:\n"
            "{\n"
            '  "scene_timeline": [\n'
            '    {"time_range": "0:00-0:XX", "visual_description": "...",\n'
            '     "audio_description": "...", "text_on_screen": "...", "key_objects": [...]}\n'
            "  ],\n"
            '  "overall_summary": "comprehensive 3-5 sentence description",\n'
            '  "people": [{"description": "...", "is_creator": true, "speaking": true}],\n'
            '  "entities_detected": [{"name": "...", "type": "person|place|product|brand|song|book|movie|app", "confidence": "high|medium|low"}],\n'
            '  "presentation_style": {\n'
            '    "primary_format": "talking_head|voiceover|text_overlay|cinematic|tutorial_demo|skit|compilation|other",\n'
            '    "camera_work": "static|handheld|panning|transitions|split_screen",\n'
            '    "editing_style": "minimal|jump_cuts|heavy_effects|before_after|montage"\n'
            "  },\n"
            '  "audio_profile": {"speech": true, "music": "none|background|featured", "sound_effects": false},\n'
            '  "visual_mood": "emotional atmosphere from visuals and pacing"\n'
            "}\n\n"
            "Be SPECIFIC. Name things — books, restaurants, products, songs. Precision over hedging."
        ),
    },
    "V3_visual": {
        "name": "Sequential Multi-Pass: Visual",
        "prompt": (
            "Focus ONLY on VISUAL elements in this TikTok video.\n"
            "Describe: scenes, objects, people, settings, text on screen, camera work, editing style.\n"
            "Ignore audio completely.\n\n"
            "Return JSON:\n"
            "{\n"
            '  "scene_timeline": [{"time_range": "...", "visual_description": "...", "text_on_screen": "...", "key_objects": [...]}],\n'
            '  "people": [{"description": "...", "actions": "..."}],\n'
            '  "presentation_style": {"primary_format": "...", "camera_work": "...", "editing_style": "..."},\n'
            '  "visual_mood": "..."\n'
            "}"
        ),
    },
    "V3_audio": {
        "name": "Sequential Multi-Pass: Audio",
        "prompt": (
            "Focus ONLY on AUDIO elements in this TikTok video.\n"
            "Describe: speech content (transcribe key phrases), music (identify song/artist if possible), sound effects.\n"
            "Ignore visual elements.\n\n"
            "Return JSON:\n"
            "{\n"
            '  "speech_content": "transcription or summary of speech",\n'
            '  "music": {"identified_song": "...", "artist": "...", "genre": "...", "mood": "..."},\n'
            '  "sound_effects": ["list of notable sounds"],\n'
            '  "audio_dominance": "speech|music|effects|silence"\n'
            "}"
        ),
    },
    "V3_entities": {
        "name": "Sequential Multi-Pass: Entities",
        "prompt": (
            "Focus ONLY on IDENTIFYING ENTITIES in this TikTok video.\n"
            "List ALL specific people, places, products, brands, songs, books, movies, TV shows, "
            "apps, websites, or named things mentioned or shown.\n\n"
            "Return JSON:\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "...", "type": "person|place|product|brand|song|book|movie|tv_show|app|other", '
            '"how_identified": "visual|audio|text_overlay", "confidence": "high|medium|low"}\n'
            "  ]\n"
            "}"
        ),
    },
    "V4": {
        "name": "Perception + Classification Hints",
        "prompt": (
            "You are a content analysis system performing Stage 1 perception on a TikTok video.\n"
            "Your job is to DESCRIBE what you observe — do not classify or judge.\n\n"
            "Return JSON:\n"
            "{\n"
            '  "scene_timeline": [\n'
            '    {"time_range": "0:00-0:XX", "visual_description": "...",\n'
            '     "audio_description": "...", "text_on_screen": "...", "key_objects": [...]}\n'
            "  ],\n"
            '  "overall_summary": "comprehensive 3-5 sentence description",\n'
            '  "people": [{"description": "...", "is_creator": true, "speaking": true}],\n'
            '  "entities_detected": [{"name": "...", "type": "person|place|product|brand|song|book|movie|app", "confidence": "high|medium|low"}],\n'
            '  "presentation_style": {\n'
            '    "primary_format": "talking_head|voiceover|text_overlay|cinematic|tutorial_demo|skit|compilation|other",\n'
            '    "camera_work": "static|handheld|panning|transitions|split_screen",\n'
            '    "editing_style": "minimal|jump_cuts|heavy_effects|before_after|montage"\n'
            "  },\n"
            '  "audio_profile": {"speech": true, "music": "none|background|featured", "sound_effects": false},\n'
            '  "visual_mood": "emotional atmosphere from visuals and pacing",\n'
            '  "topic_hints": ["2-3 topic areas this might be about"],\n'
            '  "affect_hints": ["emotional tones present"],\n'
            '  "genre_hints": ["content format types"]\n'
            "}\n\n"
            "The hints are suggestions for downstream classification, not final labels.\n"
            "Be SPECIFIC. Name things — books, restaurants, products, songs. Precision over hedging."
        ),
    },
}

# -- Slideshow/Carousel prompts --

SLIDESHOW_PROMPTS = {
    "S1": {
        "name": "Cover Image Only",
        "prompt_image": (
            "This is a TikTok image post. Analyze what you see.\n"
            "Extract in JSON:\n"
            "{\n"
            '  "scene_description": "2-3 sentences",\n'
            '  "objects_and_products": [...],\n'
            '  "text_on_screen": "ALL visible text",\n'
            '  "entities_detected": [{"name": "...", "type": "..."}],\n'
            '  "content_type_guess": "..."\n'
            "}"
        ),
        "prompt_carousel": (
            "This is the cover image of a TikTok photo carousel. Analyze what you see.\n"
            "Extract in JSON:\n"
            "{\n"
            '  "scene_description": "2-3 sentences",\n'
            '  "objects_and_products": [...],\n'
            '  "text_on_screen": "ALL visible text",\n'
            '  "entities_detected": [{"name": "...", "type": "..."}],\n'
            '  "content_type_guess": "..."\n'
            "}"
        ),
    },
    "S2": {
        "name": "All Carousel Images",
        "prompt_template": (
            "These are {n} images from a TikTok photo carousel, shown in order.\n"
            "For each image: describe what you see, extract text, list objects.\n"
            "Then synthesize:\n"
            "{{\n"
            '  "per_image": [{{"image_number": 1, "description": "...", "text_detected": "...", "objects": [...]}}],\n'
            '  "overall_summary": "...",\n'
            '  "narrative_thread": "what story or message do these images tell together?",\n'
            '  "entities_detected": [{{"name": "...", "type": "..."}}],\n'
            '  "content_type_guess": "..."\n'
            "}}"
        ),
    },
    "S3": {
        "name": "First + Last Image",
        "prompt_template": (
            "These are the first and last images from a {n}-image TikTok carousel.\n"
            "Analyze what you see and infer what the full carousel might contain.\n"
            "{{\n"
            '  "first_image_description": "...",\n'
            '  "last_image_description": "...",\n'
            '  "inferred_narrative": "what the full carousel likely covers",\n'
            '  "entities_detected": [{{"name": "...", "type": "..."}}],\n'
            '  "content_type_guess": "..."\n'
            "}}"
        ),
    },
}

# -- Keyframe prompts --

KEYFRAME_PROMPTS = {
    "K1": {
        "name": "Individual Frame Analysis",
        "prompt_template": (
            "These are {n} keyframes from a {duration}s TikTok video, in chronological order.\n"
            "Describe each frame. Then synthesize a narrative of the full video.\n"
            "Return JSON:\n"
            "{{\n"
            '  "per_frame": [{{"frame_number": 1, "description": "...", "text_on_screen": "...", "objects": [...]}}],\n'
            '  "overall_summary": "...",\n'
            '  "entities_detected": [{{"name": "...", "type": "..."}}],\n'
            '  "presentation_style": {{"primary_format": "...", "editing_style": "..."}},\n'
            '  "content_type_guess": "..."\n'
            "}}"
        ),
    },
    "K2": {
        "name": "Frame Sequence With Inference",
        "prompt_template": (
            "These are {n} keyframes from a {duration}s TikTok video, extracted at scene boundaries.\n"
            "For each frame, describe what you see. Then:\n"
            "1. Describe the narrative progression from frame to frame\n"
            "2. Infer what likely happens between frames\n"
            "Return JSON:\n"
            "{{\n"
            '  "per_frame": [{{"frame_number": 1, "description": "...", "text_on_screen": "...", "objects": [...]}}],\n'
            '  "frame_transitions": [{{"from": 1, "to": 2, "inferred_content": "..."}}],\n'
            '  "overall_summary": "...",\n'
            '  "entities_detected": [{{"name": "...", "type": "..."}}],\n'
            '  "content_type_guess": "..."\n'
            "}}"
        ),
    },
}


# ── Cost Estimation ─────────────────────────────────────────────────────────

def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_COST_PER_M + output_tokens * OUTPUT_COST_PER_M) / 1_000_000


# ── Experiment Runners ──────────────────────────────────────────────────────

def _save_result(result: ExperimentResult) -> Path:
    """Save experiment result to JSON file."""
    out_dir = RESULTS_DIR / result.approach / result.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result.item_id}.json"
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    return out_path


def run_thumbnail_experiment(item: SampleItem, variant: str) -> ExperimentResult:
    """Run a thumbnail-based experiment."""
    prompt_info = THUMBNAIL_PROMPTS[variant]

    # Build prompt
    if variant == "T4":
        prompt = prompt_info["prompt_template"].format(
            caption=item.caption[:200],
            hashtags=", ".join(item.hashtags[:10]),
            username=item.creator_username,
            nickname=item.creator_nickname,
            music_name=item.music_name,
            music_author=item.music_author,
            duration=item.duration,
            play_count=f"{item.play_count:,}",
            like_count=f"{item.like_count:,}",
        )
    else:
        prompt = prompt_info["prompt"]

    # Download thumbnail
    cover_path = MEDIA_DIR / f"thumb_{item.platform_id}.jpg"
    if item.cover_url:
        download_file(item.cover_url, cover_path)
    else:
        return ExperimentResult(
            item_id=item.platform_id, approach="thumbnail", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error="No cover URL available",
        )

    # Build parts
    parts = [{"text": prompt}, image_to_inline_data(cover_path)]

    # Call Gemini
    start = time.time()
    try:
        parsed, raw = gemini_generate(parts)
    except Exception as e:
        return ExperimentResult(
            item_id=item.platform_id, approach="thumbnail", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=str(e),
        )
    latency_ms = int((time.time() - start) * 1000)

    usage = raw.get("usage", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    result = ExperimentResult(
        item_id=item.platform_id,
        approach="thumbnail",
        variant=variant,
        model=GEMINI_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_text=prompt,
        raw_response=raw,
        parsed_output=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(input_tokens, output_tokens),
    )
    _save_result(result)
    return result


def run_video_experiment(item: SampleItem, variant: str) -> ExperimentResult:
    """Run a video-based experiment using Gemini File API."""
    if variant.startswith("V3_"):
        prompt = VIDEO_PROMPTS[variant]["prompt"]
    else:
        prompt = VIDEO_PROMPTS[variant]["prompt"]

    # Download video
    video_path = MEDIA_DIR / f"video_{item.platform_id}.mp4"
    if item.download_url:
        download_file(item.download_url, video_path)
    else:
        return ExperimentResult(
            item_id=item.platform_id, approach="video", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error="No video download URL available",
        )

    # Upload to Gemini File API
    upload_start = time.time()
    try:
        file_name = gemini_upload_file(str(video_path), "video/mp4")
        file_uri = gemini_wait_for_file(file_name)
    except Exception as e:
        return ExperimentResult(
            item_id=item.platform_id, approach="video", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=f"File upload failed: {e}",
        )
    upload_ms = int((time.time() - upload_start) * 1000)

    # Build parts
    parts = [
        {"text": prompt},
        {"fileData": {"mimeType": "video/mp4", "fileUri": file_uri}},
    ]

    # Call Gemini
    start = time.time()
    try:
        parsed, raw = gemini_generate(parts, max_tokens=4096)
    except Exception as e:
        gemini_delete_file(file_name)
        return ExperimentResult(
            item_id=item.platform_id, approach="video", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=str(e), upload_ms=upload_ms,
        )
    latency_ms = int((time.time() - start) * 1000)

    # Cleanup
    gemini_delete_file(file_name)

    usage = raw.get("usage", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    result = ExperimentResult(
        item_id=item.platform_id,
        approach="video",
        variant=variant,
        model=GEMINI_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_text=prompt,
        raw_response=raw,
        parsed_output=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(input_tokens, output_tokens),
        upload_ms=upload_ms,
    )
    _save_result(result)
    return result


def run_slideshow_experiment(item: SampleItem, variant: str) -> ExperimentResult:
    """Run an image/carousel experiment."""
    image_urls = item.slideshow_image_urls
    n_images = len(image_urls)

    if variant == "S1":
        # Cover image only
        prompt = SLIDESHOW_PROMPTS["S1"]["prompt_carousel" if item.is_carousel else "prompt_image"]
        cover_path = MEDIA_DIR / f"thumb_{item.platform_id}.jpg"
        if item.cover_url:
            download_file(item.cover_url, cover_path)
        parts = [{"text": prompt}, image_to_inline_data(cover_path)]

    elif variant == "S2":
        if not image_urls or item.is_image:
            # For single images, S2 = S1
            return run_slideshow_experiment(item, "S1")
        prompt = SLIDESHOW_PROMPTS["S2"]["prompt_template"].format(n=n_images)
        parts = [{"text": prompt}]
        for i, url in enumerate(image_urls):
            img_path = MEDIA_DIR / f"slide_{item.platform_id}_{i:03d}.jpg"
            download_file(url, img_path)
            parts.append(image_to_inline_data(img_path))

    elif variant == "S3":
        if not image_urls or len(image_urls) < 2 or item.is_image:
            return run_slideshow_experiment(item, "S1")
        prompt = SLIDESHOW_PROMPTS["S3"]["prompt_template"].format(n=n_images)
        first_path = MEDIA_DIR / f"slide_{item.platform_id}_000.jpg"
        last_path = MEDIA_DIR / f"slide_{item.platform_id}_{n_images-1:03d}.jpg"
        download_file(image_urls[0], first_path)
        download_file(image_urls[-1], last_path)
        parts = [{"text": prompt}, image_to_inline_data(first_path), image_to_inline_data(last_path)]
    else:
        return ExperimentResult(
            item_id=item.platform_id, approach="slideshow", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text="", error=f"Unknown variant: {variant}",
        )

    # Call Gemini
    start = time.time()
    try:
        parsed, raw = gemini_generate(parts)
    except Exception as e:
        return ExperimentResult(
            item_id=item.platform_id, approach="slideshow", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=str(e),
        )
    latency_ms = int((time.time() - start) * 1000)

    usage = raw.get("usage", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    result = ExperimentResult(
        item_id=item.platform_id,
        approach="slideshow",
        variant=variant,
        model=GEMINI_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_text=prompt,
        raw_response=raw,
        parsed_output=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(input_tokens, output_tokens),
    )
    _save_result(result)
    return result


def run_keyframe_experiment(item: SampleItem, variant: str) -> ExperimentResult:
    """Run a keyframe-based experiment."""
    video_path = MEDIA_DIR / f"video_{item.platform_id}.mp4"
    if not video_path.exists() and item.download_url:
        download_file(item.download_url, video_path)

    if not video_path.exists():
        return ExperimentResult(
            item_id=item.platform_id, approach="keyframes", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text="", error="No video file available",
        )

    frames = extract_keyframes(video_path)
    prompt_info = KEYFRAME_PROMPTS[variant]
    prompt = prompt_info["prompt_template"].format(n=len(frames), duration=item.duration)

    parts = [{"text": prompt}]
    for frame_path in frames:
        parts.append(image_to_inline_data(frame_path))

    start = time.time()
    try:
        parsed, raw = gemini_generate(parts)
    except Exception as e:
        return ExperimentResult(
            item_id=item.platform_id, approach="keyframes", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=str(e),
        )
    latency_ms = int((time.time() - start) * 1000)

    usage = raw.get("usage", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    # Add keyframe metadata
    parsed["_keyframe_count"] = len(frames)
    parsed["_native_video_tokens"] = VIDEO_TOKENS_PER_SEC * item.duration

    result = ExperimentResult(
        item_id=item.platform_id,
        approach="keyframes",
        variant=variant,
        model=GEMINI_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_text=prompt,
        raw_response=raw,
        parsed_output=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(input_tokens, output_tokens),
    )
    _save_result(result)
    return result


def run_grounding_experiment(item: SampleItem, with_grounding: bool) -> ExperimentResult:
    """Run thumbnail T2 with/without Google Search grounding."""
    prompt = THUMBNAIL_PROMPTS["T2"]["prompt"]
    variant = "grounding_on" if with_grounding else "grounding_off"

    cover_path = MEDIA_DIR / f"thumb_{item.platform_id}.jpg"
    if item.cover_url:
        download_file(item.cover_url, cover_path)

    parts = [{"text": prompt}, image_to_inline_data(cover_path)]
    tools = [{"googleSearch": {}}] if with_grounding else None

    start = time.time()
    try:
        parsed, raw = gemini_generate(parts, json_mode=not with_grounding, tools=tools)
    except Exception as e:
        return ExperimentResult(
            item_id=item.platform_id, approach="grounding", variant=variant,
            model=GEMINI_MODEL, timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_text=prompt, error=str(e),
        )
    latency_ms = int((time.time() - start) * 1000)

    usage = raw.get("usage", {})
    input_tokens = usage.get("promptTokenCount", 0)
    output_tokens = usage.get("candidatesTokenCount", 0)

    result = ExperimentResult(
        item_id=item.platform_id,
        approach="grounding",
        variant=variant,
        model=GEMINI_MODEL,
        timestamp=datetime.now(timezone.utc).isoformat(),
        prompt_text=prompt,
        raw_response=raw,
        parsed_output=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=estimate_cost(input_tokens, output_tokens),
    )
    _save_result(result)
    return result


# ── Phase Runners ───────────────────────────────────────────────────────────

def load_manifest() -> list[SampleItem]:
    """Load the sample manifest."""
    if not MANIFEST_PATH.exists():
        print("ERROR: sample_manifest.json not found. Run --phase setup first.")
        sys.exit(1)
    with open(MANIFEST_PATH) as f:
        data = json.load(f)
    items = []
    for entry in data["items"]:
        items.append(SampleItem(
            platform_id=entry["platform_id"],
            expected_type=entry["expected_type"],
            description=entry["description"],
            apify_data=entry.get("apify_data", {}),
        ))
    return items


def phase_setup():
    """Step 0: Fetch items from Apify and download media."""
    print("=" * 60)
    print("PHASE: SETUP")
    print("=" * 60)

    if not APIFY_API_TOKEN:
        print("ERROR: APIFY_API_TOKEN not set")
        sys.exit(1)

    # Fetch from Apify
    platform_ids = [s["platform_id"] for s in SAMPLE_ITEMS]
    apify_items = fetch_apify_items(platform_ids)
    print(f"  Apify returned {len(apify_items)} items")

    # Index by platform_id
    by_pid: dict[str, dict] = {}
    for item in apify_items:
        pid = str(item.get("id", ""))
        if pid:
            by_pid[pid] = item
        web_url = item.get("webVideoUrl", "")
        match = _TIKTOK_VIDEO_ID_RE.search(web_url)
        if match:
            by_pid[match.group(1)] = item

    # Build manifest
    manifest_items = []
    for spec in SAMPLE_ITEMS:
        pid = spec["platform_id"]
        apify = by_pid.get(pid, {})
        matched = bool(apify)
        print(f"  {pid}: {'MATCHED' if matched else 'NOT FOUND'} — {spec['description']}")
        manifest_items.append({
            "platform_id": pid,
            "expected_type": spec["type"],
            "description": spec["description"],
            "matched": matched,
            "apify_data": apify,
        })

    # Save manifest
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(manifest_items),
        "matched": sum(1 for m in manifest_items if m["matched"]),
        "items": manifest_items,
    }
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"\n  Manifest saved to {MANIFEST_PATH}")

    # Download media
    print("\n  Downloading media...")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    for entry in manifest_items:
        if not entry["matched"]:
            continue
        pid = entry["platform_id"]
        apify = entry["apify_data"]
        vm = apify.get("videoMeta") or {}

        # Thumbnail
        cover_url = vm.get("coverUrl")
        if cover_url:
            result = download_file(cover_url, MEDIA_DIR / f"thumb_{pid}.jpg")
            print(f"    {pid}: thumbnail {'OK' if result else 'FAILED'}")

        # Video
        dl_url = vm.get("downloadAddr")
        if dl_url and entry["expected_type"] == "video":
            result = download_file(dl_url, MEDIA_DIR / f"video_{pid}.mp4")
            print(f"    {pid}: video {'OK' if result else 'FAILED'}")

        # Slideshow images
        slide_links = apify.get("slideshowImageLinks") or []
        slide_ok = 0
        for i, link in enumerate(slide_links):
            url = link.get("downloadLink") or link.get("tiktokLink")
            if url:
                r = download_file(url, MEDIA_DIR / f"slide_{pid}_{i:03d}.jpg")
                if r:
                    slide_ok += 1
        if slide_links:
            print(f"    {pid}: {slide_ok}/{len(slide_links)} slideshow images OK")

    print("\n  Setup complete.")


def phase_thumbnail(items: list[SampleItem], dry_run: bool = False):
    """Step 1: Thumbnail experiments."""
    print("\n" + "=" * 60)
    print("PHASE: THUMBNAIL (15 items x 4 variants = 60 calls)")
    print("=" * 60)

    if dry_run:
        est_tokens = 15 * 4 * (IMAGE_TOKENS + 200 + 400)  # image + prompt + output
        print(f"  Estimated: {15*4} calls, ~{est_tokens:,} tokens, ~${estimate_cost(est_tokens, 15*4*400):.3f}")
        return

    variants = ["T1", "T2", "T3", "T4"]
    for variant in variants:
        print(f"\n  --- {variant}: {THUMBNAIL_PROMPTS[variant]['name']} ---")
        for item in items:
            result = run_thumbnail_experiment(item, variant)
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            print(f"    {item.platform_id}: {status} | {result.input_tokens}+{result.output_tokens} tok | {result.latency_ms}ms | ${result.cost_usd:.4f}")
            time.sleep(0.5)  # gentle rate limiting


def phase_slideshow(items: list[SampleItem], dry_run: bool = False):
    """Step 2: Image + Carousel experiments."""
    slideshow_items = [i for i in items if i.is_slideshow]
    n = len(slideshow_items)
    print(f"\n{'='*60}")
    print(f"PHASE: SLIDESHOW ({n} items x 3 variants = {n*3} calls)")
    print("=" * 60)

    if dry_run:
        est_tokens = n * 3 * (5 * IMAGE_TOKENS + 300 + 600)
        print(f"  Estimated: {n*3} calls, ~{est_tokens:,} tokens, ~${estimate_cost(est_tokens, n*3*600):.3f}")
        return

    variants = ["S1", "S2", "S3"]
    for variant in variants:
        print(f"\n  --- {variant}: {SLIDESHOW_PROMPTS[variant]['name']} ---")
        for item in slideshow_items:
            result = run_slideshow_experiment(item, variant)
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            print(f"    {item.platform_id}: {status} | {result.input_tokens}+{result.output_tokens} tok | {result.latency_ms}ms | ${result.cost_usd:.4f}")
            time.sleep(0.5)


def phase_video(items: list[SampleItem], dry_run: bool = False):
    """Step 3: Video experiments."""
    video_items = [i for i in items if i.is_video]
    n = len(video_items)
    print(f"\n{'='*60}")
    print(f"PHASE: VIDEO ({n} items x 4 variants = {n*4} calls + V3 multi-pass on 5)")
    print("=" * 60)

    if dry_run:
        avg_dur = 60  # seconds
        tokens_per_vid = avg_dur * VIDEO_TOKENS_PER_SEC + avg_dur * AUDIO_TOKENS_PER_SEC + 500
        est_main = n * 3 * (tokens_per_vid + 1200)  # V1/V2/V4
        est_v3 = 5 * 3 * (tokens_per_vid + 800)  # V3 on 5 items, 3 passes
        total = est_main + est_v3
        print(f"  Estimated: {n*3 + 15} calls, ~{total:,} tokens, ~${estimate_cost(total, (n*3+15)*1200):.3f}")
        return

    # V1, V2, V4 on all video items
    for variant in ["V1", "V2", "V4"]:
        print(f"\n  --- {variant}: {VIDEO_PROMPTS[variant]['name']} ---")
        for item in video_items:
            result = run_video_experiment(item, variant)
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            print(f"    {item.platform_id}: {status} | {result.input_tokens}+{result.output_tokens} tok | {result.latency_ms}ms | ${result.cost_usd:.4f} | upload:{result.upload_ms}ms")
            time.sleep(1)  # rate limit for video uploads

    # V3 multi-pass on first 5 video items
    v3_items = video_items[:5]
    print(f"\n  --- V3: Sequential Multi-Pass (5 items x 3 passes) ---")
    for item in v3_items:
        for sub_variant in ["V3_visual", "V3_audio", "V3_entities"]:
            result = run_video_experiment(item, sub_variant)
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            label = sub_variant.split("_")[1]
            print(f"    {item.platform_id} [{label}]: {status} | {result.input_tokens}+{result.output_tokens} tok | ${result.cost_usd:.4f}")
            time.sleep(1)


def phase_keyframes(items: list[SampleItem], dry_run: bool = False):
    """Step 4: Keyframe experiments."""
    # Items #1, #12, #13, #14, #15 (cooking, skiing, cinematic, corecore, movie review)
    keyframe_pids = {
        "7449805282663730465", "7204493467324665093", "7458375076895903022",
        "7458381815716367649", "7429027711529553183",
    }
    kf_items = [i for i in items if i.platform_id in keyframe_pids and i.is_video]
    n = len(kf_items)
    print(f"\n{'='*60}")
    print(f"PHASE: KEYFRAMES ({n} items x 2 variants = {n*2} calls)")
    print("=" * 60)

    if dry_run:
        est_tokens = n * 2 * (8 * IMAGE_TOKENS + 400 + 800)
        print(f"  Estimated: {n*2} calls, ~{est_tokens:,} tokens, ~${estimate_cost(est_tokens, n*2*800):.3f}")
        return

    for variant in ["K1", "K2"]:
        print(f"\n  --- {variant}: {KEYFRAME_PROMPTS[variant]['name']} ---")
        for item in kf_items:
            result = run_keyframe_experiment(item, variant)
            kf_count = result.parsed_output.get("_keyframe_count", "?")
            native_tokens = result.parsed_output.get("_native_video_tokens", "?")
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            print(f"    {item.platform_id}: {status} | {kf_count} frames | {result.input_tokens} tok (vs {native_tokens} native) | ${result.cost_usd:.4f}")
            time.sleep(0.5)


def phase_grounding(items: list[SampleItem], dry_run: bool = False):
    """Step 5: Grounding sub-experiment."""
    # Entity-rich items: #7 (fan edit), #8 (pizza recs), #14 (corecore), #15 (movie review), #1 (cooking)
    grounding_pids = {
        "7443060682406235400", "7446186256205204744", "7458381815716367649",
        "7429027711529553183", "7449805282663730465",
    }
    g_items = [i for i in items if i.platform_id in grounding_pids]
    n = len(g_items)
    print(f"\n{'='*60}")
    print(f"PHASE: GROUNDING ({n} items x 2 variants = {n*2} calls)")
    print("=" * 60)

    if dry_run:
        est_tokens = n * 2 * (IMAGE_TOKENS + 200 + 400)
        print(f"  Estimated: {n*2} calls, ~{est_tokens:,} tokens, ~${estimate_cost(est_tokens, n*2*400):.3f}")
        return

    for item in g_items:
        for with_grounding in [False, True]:
            result = run_grounding_experiment(item, with_grounding)
            label = "grounding ON" if with_grounding else "grounding OFF"
            status = "OK" if not result.error else f"ERR: {result.error[:50]}"
            grounding_count = len(result.parsed_output.get("grounding_sources", []))
            print(f"    {item.platform_id} [{label}]: {status} | sources:{grounding_count} | ${result.cost_usd:.4f}")
            time.sleep(0.5)


HEDGE_WORDS = {"possibly", "likely", "appears", "seems", "might", "could be", "perhaps", "probably", "may be"}


def _get_parsed(result: dict) -> dict:
    """Extract the actual parsed output, handling _raw_text wrapper."""
    parsed = result.get("parsed_output", {})
    if "_raw_text" in parsed:
        try:
            return json.loads(parsed["_raw_text"])
        except (json.JSONDecodeError, TypeError):
            return parsed
    return parsed


def _compute_auto_metrics(result: dict) -> dict:
    """Compute automated quality metrics from a single experiment result."""
    parsed = _get_parsed(result)
    m = result.get("metrics", {})
    text_blob = json.dumps(parsed).lower()

    # Entity count
    entities = parsed.get("entities_detected", [])
    if not entities:
        entities = parsed.get("entities", [])
    entity_count = len(entities)
    named = sum(1 for e in entities if isinstance(e, dict) and len(e.get("name", "")) > 2)

    # Text detected
    text_detected = parsed.get("text_on_screen", "") or parsed.get("text_detected", "") or ""
    if isinstance(text_detected, list):
        text_detected = " ".join(str(t) for t in text_detected)

    # Scene count (video only)
    scenes = parsed.get("scene_timeline", []) or parsed.get("scene_descriptions", [])
    scene_count = len(scenes) if isinstance(scenes, list) else 0

    # Description word count
    summary = parsed.get("overall_summary", "") or parsed.get("scene_description", "") or parsed.get("description", "") or ""
    word_count = len(summary.split()) if summary else 0

    # Field completeness — count non-empty top-level fields
    total_fields = 0
    filled_fields = 0
    for k, v in parsed.items():
        if k.startswith("_"):
            continue
        total_fields += 1
        if v and v != "null" and v != [] and v != {}:
            filled_fields += 1
    completeness = filled_fields / total_fields if total_fields > 0 else 0

    # Hedge word count
    hedge_count = sum(text_blob.count(w) for w in HEDGE_WORDS)

    # Objects count
    objects = parsed.get("objects", []) or parsed.get("objects_and_products", []) or parsed.get("key_objects", [])
    if isinstance(objects, list):
        object_count = len(objects)
    else:
        object_count = 0

    return {
        "output_tokens": m.get("output_tokens", 0),
        "cost_usd": m.get("cost_usd", 0),
        "latency_ms": m.get("latency_ms", 0),
        "entity_count": entity_count,
        "named_entity_count": named,
        "text_detected_length": len(text_detected),
        "scene_count": scene_count,
        "description_word_count": word_count,
        "object_count": object_count,
        "field_completeness": round(completeness, 2),
        "hedge_word_count": hedge_count,
        # Composite richness score for auto-selecting "best" variant
        "richness_score": round(
            word_count * 0.3 + entity_count * 5 + object_count * 2
            + (len(text_detected) > 0) * 10 + scene_count * 3 + completeness * 20,
            1,
        ),
    }


def _select_best_variant(results: list[dict], approach: str) -> dict | None:
    """Select the best variant for an approach using richness_score."""
    approach_results = [r for r in results if r["approach"] == approach and not r.get("error")]
    if not approach_results:
        return None
    scored = [(r, _compute_auto_metrics(r)["richness_score"]) for r in approach_results]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def _format_output_readable(parsed: dict) -> str:
    """Format parsed output as readable text (not raw JSON)."""
    lines = []
    # Summary / description
    for key in ("overall_summary", "scene_description", "description"):
        val = parsed.get(key)
        if val:
            lines.append(f"**Summary**: {val}\n")
            break

    # Scene timeline
    scenes = parsed.get("scene_timeline") or parsed.get("scene_descriptions") or []
    if scenes and isinstance(scenes, list):
        lines.append("**Scenes**:")
        for s in scenes:
            if isinstance(s, dict):
                ts = s.get("time_range") or s.get("timestamp", "")
                desc = s.get("visual_description") or s.get("description", "")
                audio = s.get("audio_description", "")
                lines.append(f"- `{ts}`: {desc}")
                if audio:
                    lines.append(f"  Audio: {audio}")
            elif isinstance(s, str):
                lines.append(f"- {s}")
        lines.append("")

    # People
    people = parsed.get("people") or parsed.get("visible_people")
    if people:
        if isinstance(people, list):
            lines.append("**People**:")
            for p in people:
                if isinstance(p, dict):
                    lines.append(f"- {p.get('description', str(p))}")
                else:
                    lines.append(f"- {p}")
        elif isinstance(people, str):
            lines.append(f"**People**: {people}")
        lines.append("")

    # Entities
    entities = parsed.get("entities_detected") or parsed.get("entities") or []
    if entities:
        lines.append("**Entities**:")
        for e in entities:
            if isinstance(e, dict):
                lines.append(f"- {e.get('name', '?')} ({e.get('type', '?')}) [{e.get('confidence', '')}]")
            else:
                lines.append(f"- {e}")
        lines.append("")

    # Objects
    objects = parsed.get("objects") or parsed.get("objects_and_products") or []
    if objects and isinstance(objects, list):
        lines.append(f"**Objects**: {', '.join(str(o) for o in objects[:15])}")
        if len(objects) > 15:
            lines.append(f"  ... and {len(objects) - 15} more")
        lines.append("")

    # Text on screen
    text = parsed.get("text_on_screen") or parsed.get("text_detected") or ""
    if text and text != "null":
        lines.append(f"**Text on screen**: {str(text)[:500]}")
        lines.append("")

    # Presentation style
    style = parsed.get("presentation_style")
    if style:
        if isinstance(style, dict):
            lines.append(f"**Style**: {style.get('primary_format', '')} | camera: {style.get('camera_work', '')} | editing: {style.get('editing_style', '')}")
        else:
            lines.append(f"**Style**: {style}")
        lines.append("")

    # Audio profile
    audio = parsed.get("audio_profile")
    if audio and isinstance(audio, dict):
        lines.append(f"**Audio**: speech={audio.get('speech')}, music={audio.get('music')}, sfx={audio.get('sound_effects')}")
        lines.append("")

    # Mood
    mood = parsed.get("visual_mood")
    if mood:
        lines.append(f"**Mood**: {mood}")
        lines.append("")

    # Classification hints (V4)
    for hint_key in ("topic_hints", "affect_hints", "genre_hints"):
        hints = parsed.get(hint_key)
        if hints:
            lines.append(f"**{hint_key}**: {hints}")

    # Per-image (slideshows)
    per_image = parsed.get("per_image") or parsed.get("per_frame") or []
    if per_image:
        lines.append("**Per-image/frame**:")
        for img in per_image[:6]:
            if isinstance(img, dict):
                num = img.get("image_number") or img.get("frame_number", "?")
                desc = img.get("description", "")
                lines.append(f"- [{num}]: {desc[:150]}")
        if len(per_image) > 6:
            lines.append(f"  ... and {len(per_image) - 6} more")
        lines.append("")

    narrative = parsed.get("narrative_thread") or parsed.get("inferred_narrative")
    if narrative:
        lines.append(f"**Narrative**: {narrative}")
        lines.append("")

    return "\n".join(lines) if lines else json.dumps(parsed, indent=2)[:2000]


def phase_compare():
    """Generate evaluation sheets with automated metrics and blank scoring rubrics."""
    print(f"\n{'='*60}")
    print("PHASE: COMPARE — Evaluation Framework")
    print("=" * 60)

    if not RESULTS_DIR.exists():
        print("  No results found. Run experiments first.")
        return

    eval_dir = COMPARISONS_DIR / "eval_sheets"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest for item metadata
    manifest_items = {}
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            for entry in json.load(f).get("items", []):
                manifest_items[entry["platform_id"]] = entry

    # Load all results
    all_results: dict[str, list[dict]] = {}
    for approach_dir in sorted(RESULTS_DIR.iterdir()):
        if not approach_dir.is_dir():
            continue
        for variant_dir in sorted(approach_dir.iterdir()):
            if not variant_dir.is_dir():
                continue
            for result_file in sorted(variant_dir.glob("*.json")):
                with open(result_file) as f:
                    data = json.load(f)
                pid = data["item_id"]
                if pid not in all_results:
                    all_results[pid] = []
                all_results[pid].append(data)

    # Compute all automated metrics
    all_auto_metrics: dict[str, dict[str, dict]] = {}  # pid -> {approach_variant -> metrics}
    for pid, results in all_results.items():
        all_auto_metrics[pid] = {}
        for r in results:
            key = f"{r['approach']}_{r['variant']}"
            all_auto_metrics[pid][key] = _compute_auto_metrics(r)

    # Generate per-item eval sheets
    item_order = [s["platform_id"] for s in SAMPLE_ITEMS]
    for idx, pid in enumerate(item_order):
        if pid not in all_results:
            continue

        results = all_results[pid]
        spec = next((s for s in SAMPLE_ITEMS if s["platform_id"] == pid), {})
        manifest = manifest_items.get(pid, {})
        apify = manifest.get("apify_data", {})
        caption = apify.get("text", "")
        hashtags = [h.get("name", "") for h in (apify.get("hashtags") or []) if isinstance(h, dict)]
        duration = (apify.get("videoMeta") or {}).get("duration", 0)
        has_subs = len((apify.get("videoMeta") or {}).get("subtitleLinks") or []) > 0

        lines = [
            f"# {idx+1}. {spec.get('description', pid)}",
            f"**ID**: `{pid}` | **Type**: {spec.get('type', '?')} | **Duration**: {duration}s | **Subtitles**: {'yes' if has_subs else 'no'}",
            f"\n**Caption**: {caption[:300]}",
            f"**Hashtags**: {', '.join(hashtags[:10]) if hashtags else '(none)'}",
            "",
            "---",
        ]

        # Determine which approaches to show
        approaches_present = set(r["approach"] for r in results)
        # Primary comparison: thumbnail vs video (or slideshow)
        primary_approaches = []
        if "thumbnail" in approaches_present:
            primary_approaches.append("thumbnail")
        if "video" in approaches_present:
            primary_approaches.append("video")
        if "slideshow" in approaches_present:
            primary_approaches.append("slideshow")

        best_results = {}
        for approach in primary_approaches:
            best = _select_best_variant(results, approach)
            if best:
                best_results[approach] = best

        for approach in primary_approaches:
            best = best_results.get(approach)
            if not best:
                lines.append(f"\n## {approach.upper()}\n*No successful results.*\n")
                continue

            variant = best["variant"]
            m = best.get("metrics", {})
            auto = _compute_auto_metrics(best)
            parsed = _get_parsed(best)

            lines.extend([
                f"\n## {approach.upper()} (best: {variant})",
                "",
                _format_output_readable(parsed),
                "",
                f"| Metric | Value |",
                f"|---|---|",
                f"| Tokens | {m.get('input_tokens',0)} in / {m.get('output_tokens',0)} out |",
                f"| Cost | ${m.get('cost_usd',0):.4f} |",
                f"| Latency | {m.get('latency_ms',0)}ms |",
                f"| Entities | {auto['entity_count']} ({auto['named_entity_count']} named) |",
                f"| Objects | {auto['object_count']} |",
                f"| Text detected | {auto['text_detected_length']} chars |",
                f"| Scenes | {auto['scene_count']} |",
                f"| Description words | {auto['description_word_count']} |",
                f"| Field completeness | {auto['field_completeness']:.0%} |",
                f"| Hedge words | {auto['hedge_word_count']} |",
                f"| Richness score | {auto['richness_score']} |",
                "",
                "### Scores (1=Poor, 2=Adequate, 3=Strong)",
                "| Accuracy | Completeness | Specificity | Class. Utility | Added Value | Total |",
                "|---|---|---|---|---|---|",
                "| /3 | /3 | /3 | /3 | /3 | /15 |",
                "",
                "**Notes**: ",
                "",
                "---",
            ])

        # Delta section
        if len(best_results) >= 2:
            approaches = list(best_results.keys())
            costs = {a: best_results[a].get("metrics", {}).get("cost_usd", 0) for a in approaches}
            cheap = min(costs.values())
            expensive = max(costs.values())
            multiplier = expensive / cheap if cheap > 0 else 0

            lines.extend([
                "\n## DELTA",
                f"**Cost multiplier**: {multiplier:.0f}x (${expensive:.4f} / ${cheap:.4f})",
                f"**Quality delta**: ___",
                f"**Verdict**: `THUMBNAIL_SUFFICIENT` / `VIDEO_JUSTIFIED` / `VIDEO_ESSENTIAL`",
                "",
            ])

        with open(eval_dir / f"{idx+1:02d}_{pid}.md", "w") as f:
            f.write("\n".join(lines))

    # Generate aggregate eval summary
    summary_lines = [
        "# Vision Analysis — Evaluation Summary",
        f"\nGenerated: {datetime.now(timezone.utc).isoformat()}",
        f"Total experiments: {sum(len(r) for r in all_results.values())}",
        f"Total cost: ${sum(m.get('metrics',{}).get('cost_usd',0) for rs in all_results.values() for m in rs):.4f}",
        "",
        "## Automated Metrics by Approach (averaged across items)",
        "",
        "| Approach | Avg Entities | Avg Objects | Avg Words | Avg Scenes | Avg Richness | Avg Cost |",
        "|---|---|---|---|---|---|---|",
    ]

    # Average metrics per approach (using best variant per item)
    approach_agg: dict[str, list[dict]] = {}
    for pid, results in all_results.items():
        for approach in ("thumbnail", "video", "slideshow"):
            best = _select_best_variant(results, approach)
            if best:
                if approach not in approach_agg:
                    approach_agg[approach] = []
                approach_agg[approach].append(_compute_auto_metrics(best))

    for approach, metrics_list in sorted(approach_agg.items()):
        n = len(metrics_list)
        avg = lambda key: sum(m[key] for m in metrics_list) / n
        summary_lines.append(
            f"| {approach} | {avg('entity_count'):.1f} | {avg('object_count'):.1f} | "
            f"{avg('description_word_count'):.0f} | {avg('scene_count'):.1f} | "
            f"{avg('richness_score'):.1f} | ${avg('cost_usd'):.4f} |"
        )

    summary_lines.extend([
        "",
        "## Per-Item Best Variants",
        "",
        "| # | Description | Thumb Best | Video/Slide Best | Cost Δ |",
        "|---|---|---|---|---|",
    ])

    for idx, spec in enumerate(SAMPLE_ITEMS):
        pid = spec["platform_id"]
        if pid not in all_results:
            continue
        results = all_results[pid]
        thumb = _select_best_variant(results, "thumbnail")
        video = _select_best_variant(results, "video")
        slide = _select_best_variant(results, "slideshow")
        other = video or slide

        thumb_v = thumb["variant"] if thumb else "-"
        other_v = f"{(video or slide or {}).get('approach','')}/{(video or slide or {}).get('variant','')}" if other else "-"
        thumb_cost = thumb.get("metrics", {}).get("cost_usd", 0) if thumb else 0
        other_cost = other.get("metrics", {}).get("cost_usd", 0) if other else 0
        delta = f"{other_cost/thumb_cost:.0f}x" if thumb_cost > 0 and other_cost > 0 else "-"

        summary_lines.append(
            f"| {idx+1} | {spec['description'][:35]} | {thumb_v} | {other_v} | {delta} |"
        )

    summary_lines.extend([
        "",
        "## Human Scoring Summary",
        "",
        "*Fill in after scoring eval sheets*",
        "",
        "| # | Description | Thumb Score | Video Score | Verdict |",
        "|---|---|---|---|---|",
    ])
    for idx, spec in enumerate(SAMPLE_ITEMS):
        summary_lines.append(f"| {idx+1} | {spec['description'][:35]} | /15 | /15 | |")

    with open(COMPARISONS_DIR / "eval_summary.md", "w") as f:
        f.write("\n".join(summary_lines))

    # Save automated metrics JSON
    with open(DATA_DIR / "automated_metrics.json", "w") as f:
        json.dump(all_auto_metrics, f, indent=2)

    # Cost report
    total_cost = sum(m.get("metrics", {}).get("cost_usd", 0) for rs in all_results.values() for m in rs)
    total_tokens = sum(m.get("metrics", {}).get("total_tokens", 0) for rs in all_results.values() for m in rs)
    cost_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_experiments": sum(len(r) for r in all_results.values()),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
    }
    with open(DATA_DIR / "cost_report.json", "w") as f:
        json.dump(cost_report, f, indent=2)

    n_sheets = len(list(eval_dir.glob("*.md")))
    print(f"  Eval sheets: {eval_dir}/ ({n_sheets} files)")
    print(f"  Summary: {COMPARISONS_DIR / 'eval_summary.md'}")
    print(f"  Automated metrics: {DATA_DIR / 'automated_metrics.json'}")
    print(f"  Cost report: {DATA_DIR / 'cost_report.json'}")
    print(f"\n  Total cost: ${total_cost:.4f} across {sum(len(r) for r in all_results.values())} experiments")
    print(f"\n  Next: open eval sheets in your editor and fill in 1-5 scores per approach.")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Day 2: Vision Analysis Experimentation")
    parser.add_argument("--phase", required=True,
                        choices=["setup", "thumbnail", "slideshow", "video", "keyframes", "grounding", "compare", "all"],
                        help="Which experiment phase to run")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model to use")
    parser.add_argument("--dry-run", action="store_true", help="Estimate cost without calling APIs")
    args = parser.parse_args()

    global GEMINI_MODEL
    GEMINI_MODEL = args.model

    if args.phase == "setup":
        phase_setup()
        return

    if args.phase == "compare":
        phase_compare()
        return

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Check workbench/.env")
        sys.exit(1)

    items = load_manifest()
    print(f"Loaded {len(items)} items from manifest (model: {GEMINI_MODEL})")

    phases = {
        "thumbnail": lambda: phase_thumbnail(items, args.dry_run),
        "slideshow": lambda: phase_slideshow(items, args.dry_run),
        "video": lambda: phase_video(items, args.dry_run),
        "keyframes": lambda: phase_keyframes(items, args.dry_run),
        "grounding": lambda: phase_grounding(items, args.dry_run),
    }

    if args.phase == "all":
        for name, fn in phases.items():
            fn()
        if not args.dry_run:
            phase_compare()
    else:
        phases[args.phase]()


if __name__ == "__main__":
    main()
