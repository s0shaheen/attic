#!/usr/bin/env python
"""Pipeline v3: 2-pass perception+extraction → classification.

Pass 1 (Perception + Entity Extraction):
  - Input: full video OR all slideshow images + metadata + subtitles + comments
  - Model: gemini-3-flash-preview
  - Optional: Google Search grounding (--grounding flag)
  - Output: perception summary, structured entities, takeaways, audio ID, hints

Pass 2 (Classification):
  - Input: Pass 1 output + metadata + visuals (keyframes at 10s intervals for
    videos, all images for slideshows)
  - Model: gemini-3-flash-preview
  - Output: 8-facet classification with multi-label affect

Usage:
    # Download media first (required for visual pipeline)
    python workbench/experiments/03-pipeline-v3/run_pipeline_v3.py --download-media workbench/data/golden_set_template.json

    # Run experiment A (no grounding)
    python workbench/experiments/03-pipeline-v3/run_pipeline_v3.py workbench/data/golden_set_template.json \\
        --output workbench/data/pipeline_v3/exp_a/

    # Run experiment B (with grounding)
    python workbench/experiments/03-pipeline-v3/run_pipeline_v3.py workbench/data/golden_set_template.json \\
        --grounding --output workbench/data/pipeline_v3/exp_b/

    # Run single item for testing
    python workbench/experiments/03-pipeline-v3/run_pipeline_v3.py workbench/data/golden_set_template.json \\
        --item 7619616880910781726 --output workbench/data/pipeline_v3/test/
"""
import asyncio
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
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-3-flash-preview"
# Grounding is not supported on gemini-3-flash-preview — use 2.5 for grounding experiments
GEMINI_MODEL_GROUNDING = "gemini-2.5-flash"

# Gemini 3 Flash pricing (per million tokens)
INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 0.60

PASS1_MAX_TOKENS = 16384
PASS2_MAX_TOKENS = 8192

PASS1_CONCURRENCY = 4   # video uploads are heavy
PASS2_CONCURRENCY = 6   # lighter — keyframes + text

APIFY_ACTOR_ID = "clockworks~tiktok-scraper"

# ── Prompts ────────────────────────────────────────────────────────────────

PASS1_VIDEO_PROMPT = """ROLE: You are a precise content analyst for a personal media library. Your
output powers user search, browse filters, external API lookups (Spotify,
Google Maps, Amazon), and aggregate stats. Accuracy and completeness directly
affect whether users can find their saved content later.

CONTEXT (metadata from the post):
{context}

Watch the video carefully and return JSON with the following structure.

If approaching output limits, TRUNCATE scene descriptions first. Never
truncate entity extraction.

{{
  "scene_timeline": [
    {{
      "time_range": "0:00-0:XX",
      "visual_description": "semantic meaning, not literal movements. 'Creator demonstrates cable lateral raise technique' NOT 'person lifts arm to the side'",
      "audio_description": "what is said or heard — transcribe key points",
      "text_on_screen": "transcribe ALL overlaid text verbatim",
      "key_objects": ["identifiable objects, products, brands in this segment"]
    }}
  ],
  "overall_summary": "3-5 sentence description: what is this video about, what happens, and what is the main point or takeaway? A user who saved this video should be able to identify it from this summary alone.",
  "people": [
    {{
      "description": "appearance, role, what they're doing",
      "is_creator": true,
      "speaking": true,
      "identified_as": "name if recognizable, null otherwise"
    }}
  ],
  "entities": [
    {{
      "name": "specific name — never generic descriptions",
      "display_name": "human-friendly display name with key specs if applicable",
      "type": "person|place|product|brand|song|artist|book|movie_or_show|app_or_tool|restaurant|exercise|recipe|ingredient|clothing|technique|trend_or_meme|cultural_reference|event|podcast|game",
      "relevance": "primary|supporting|background",
      "source": ["visual", "audio", "text_overlay", "metadata", "comments", "inferred"],
      "specifications": "dimensions, model numbers, reps/sets, prices, sizes — anything that makes this specifically identifiable. null if not applicable",
      "confidence": 4
    }}
  ],
  "takeaways": [
    {{
      "statement": "core opinion, claim, advice, or thesis of this video",
      "source": "voiceover|text_overlay|demonstration|implied",
      "confidence": 4
    }}
  ],
  "structured_content": {{
    "type": "recipe|workout|product_list|recommendation_list|ranking|instructions|null",
    "items": [
      {{
        "name": "item name",
        "details": "specs, ingredients, reps/sets, etc."
      }}
    ]
  }},
  "audio_identification": {{
    "actual_song": "Song Title — Artist (what you HEAR playing, may differ from metadata). null if no music or unidentifiable",
    "metadata_song": "what TikTok metadata says",
    "match": true
  }},
  "extraction_confidence": {{
    "entities_complete": 4,
    "audio_identified": true,
    "notes": "brief note on anything uncertain or likely missed"
  }},
  "presentation_style": {{
    "primary_format": "talking_head|voiceover|text_overlay|cinematic|tutorial_demo|skit|compilation|reaction|slideshow|before_after|pov|room_tour|outfit_showcase|edit|other",
    "camera_work": "static|handheld|panning|transitions|split_screen|overhead|selfie",
    "editing_style": "minimal|jump_cuts|heavy_effects|before_after|montage|slow_motion"
  }},
  "visual_mood": "emotional atmosphere: lighting, pacing, tone, energy level",
  "topic_hints": ["2-3 topic areas this content addresses"],
  "affect_hints": ["emotional tones present — how would a viewer FEEL?"],
  "genre_hints": ["content format — what KIND of TikTok is this?"]
}}

CRITICAL INSTRUCTIONS:
- Be SPECIFIC. Name every identifiable person, place, product, song, show, brand.
- CONFIDENCE SCALE: 1=guessing, 2=weak signal, 3=reasonable inference,
  4=strong evidence, 5=certain/verbatim. Use the full range honestly.
- AUDIO: Identify the actual song playing from the audio, not just metadata.
  TikTok audio metadata frequently does not match the actual audio. If you hear
  a different song than what metadata says, report what you HEAR.
- COMMENTS: The top comments often explain jokes, identify songs/places/products,
  or provide cultural context the video alone doesn't convey. Use them as a
  primary signal for entity identification and cultural references.
- TEXT ON SCREEN: Transcribe ALL overlaid text, including recipe steps, product
  specs, prices, dimensions, instructions.
- CELEBRITIES: If you recognize a person, NAME them. "Kai Cenat" not "another
  person at the table."
- CULTURAL CONTEXT: If this appears to be a meme, trend, or viral format, note
  it. If comments suggest cultural context you wouldn't otherwise know, include it.
- PRECISION: "Tony Soprano from The Sopranos" not "a man who appears to be a
  character."
- SCENE EFFICIENCY: Keep scene descriptions to 1-2 sentences of semantic meaning.
- TAKEAWAY: Always extract the main thesis or point. "Cable lateral raises are
  superior for shoulder isolation" is a takeaway. "This is a sad edit reflecting
  on Spider-Man's journey" is a takeaway.
- NON-ENGLISH CONTENT: If text overlays, audio, or captions are in a non-English
  language, transcribe the original AND provide an English translation. Identify
  the language.
- SELF-ASSESSMENT: Use extraction_confidence to honestly flag what you're unsure
  about. It's better to say "audio unidentifiable, confidence 2" than to guess.

Return ONLY valid JSON. No markdown fences, no preamble, no commentary outside the JSON object."""


PASS1_SLIDESHOW_PROMPT = """ROLE: You are a precise content analyst for a personal media library. This is
a TikTok slideshow with {image_count} images. Your per-image extraction will be
used for entity search, classification, and external API lookups (Spotify,
Google Maps, Amazon).

CONTEXT (metadata from the post):
{context}

Analyze ALL {image_count} images and return JSON.

MANDATORY: You MUST output one entry in "per_image" for EVERY image provided.
If there are {image_count} images, there must be exactly {image_count} entries.
No exceptions. Do not summarize multiple images into one entry.
If there are more than 20 images, output detailed per_image entries for the
first 15 and last 5 — briefly note skipped images in overall_summary.

{{
  "per_image": [
    {{
      "image_number": 1,
      "description": "what this specific image shows — be precise",
      "text_detected": "transcribe ALL readable text EXACTLY as written, including brand names, specs, dimensions, prices, model numbers",
      "primary_content": "what this slide represents if part of a list (e.g., 'Restaurant: Kasama, Filipino bakery, West Town')",
      "entities": [
        {{
          "name": "specific name",
          "type": "person|place|product|brand|song|artist|book|movie_or_show|app_or_tool|restaurant|exercise|recipe|ingredient|clothing|technique|event|podcast|game",
          "specifications": "any dimensions, specs, model numbers, sizes visible"
        }}
      ]
    }}
  ],
  "overall_summary": "3-5 sentences: what is this post about? What is the user likely saving it for?",
  "carousel_type": "recommendation_list|product_showcase|ranking|outfit_layout|recipe_steps|infographic|meme|screenshot|photo_dump|room_tour|text_cards|other",
  "narrative_thread": "what story, message, or recommendation do these images convey as a set?",
  "entities": [
    {{
      "name": "specific name",
      "display_name": "human-friendly name with key specs",
      "type": "person|place|product|brand|song|artist|book|movie_or_show|app_or_tool|restaurant|clothing|technique|trend_or_meme|cultural_reference|event|podcast|game",
      "relevance": "primary|supporting|background",
      "source": ["visual", "text_overlay", "metadata", "comments", "inferred"],
      "slide_number": 1,
      "specifications": "dimensions, specs, model numbers if visible",
      "confidence": 4
    }}
  ],
  "takeaways": [
    {{
      "statement": "core recommendation, opinion, or thesis",
      "source": "text_overlay|implied",
      "confidence": 4
    }}
  ],
  "structured_content": {{
    "type": "recipe|workout|product_list|recommendation_list|ranking|instructions|null",
    "items": [
      {{
        "name": "item name",
        "details": "specs, ingredients, etc.",
        "slide_number": 1
      }}
    ]
  }},
  "audio_identification": {{
    "actual_song": "Song — Artist if identifiable from metadata. null if no music",
    "metadata_song": "what TikTok metadata says",
    "match": true
  }},
  "extraction_confidence": {{
    "entities_complete": 4,
    "notes": "brief note on anything uncertain or likely missed"
  }},
  "presentation_style": {{
    "primary_format": "text_cards|photo_dump|product_showcase|infographic|meme|screenshot|recommendation_list|room_tour|outfit_layout|ranking|recipe_steps|other",
    "visual_style": "minimal|aesthetic|informational|meme|collage|professional"
  }},
  "visual_mood": "emotional atmosphere and aesthetic",
  "topic_hints": ["2-3 topic areas"],
  "affect_hints": ["how would a viewer FEEL looking at this?"],
  "genre_hints": ["what KIND of TikTok is this?"]
}}

CRITICAL INSTRUCTIONS:
- CONFIDENCE SCALE: 1=guessing, 2=weak signal, 3=reasonable inference,
  4=strong evidence, 5=certain/verbatim. Use the full range honestly.
- EVERY SLIDE MATTERS: For recommendation/list posts, each slide typically
  represents one item. Extract the specific item name, details, and any
  visible specifications PER SLIDE.
- TEXT EXTRACTION IS CRITICAL: Transcribe ALL visible text in every image —
  menus, signs, labels, prices, dimensions, specs, model numbers.
- Name every identifiable person, place, product, restaurant, brand, logo.
- COMMENTS provide crucial context for entity identification. Use them.
- NON-ENGLISH CONTENT: If text overlays or captions are in a non-English
  language, transcribe the original AND provide an English translation.
  Identify the language.
- SELF-ASSESSMENT: Use extraction_confidence to honestly flag what you're
  unsure about.
- Precision over hedging.

Return ONLY valid JSON. No markdown fences, no preamble, no commentary outside the JSON object."""


PASS2_CLASSIFICATION_PROMPT = """ROLE: You are classifying TikTok content for a personal media library. Your
labels will be used for:
1. BROWSE FILTERS: Users filter their collection by topic, genre, affect
2. AGGREGATE STATS: "Your top topics this month", "affect breakdown"
3. SEARCH REFINEMENT: Narrowing search results by category

Classify based on how a USER would naturally categorize this content — not how
an academic media researcher would.

IMPORTANT: The Stage 1 perception analysis below is your PRIMARY evidence.
It has already watched/analyzed the full content. Raw metadata (caption,
hashtags, etc.) is SUPPLEMENTARY context for disambiguation only. When
Stage 1's interpretation conflicts with hashtags or metadata, trust Stage 1.

## Perception + Entity Summary (from Stage 1)

{pass1_summary}

## Supplementary Metadata (use for disambiguation, not as primary signal)

Caption: {caption}
Hashtags: {hashtags}
Creator: @{creator}
Music: {music}
Duration: {duration}s

{subtitles_section}

{comments_section}

## Classification Ontology

### Topic — Primary subject matter (assign primary + optional secondary)

- food: Cooking, recipes, restaurants, food reviews, meal prep, food science
- fashion: Clothing, outfits, style advice, fashion shows, wardrobe content
- beauty: Makeup, skincare, haircare, beauty products, beauty routines
- fitness: Content where physical exercise is the VISIBLE PRIMARY SUBJECT. A
  person must be demonstrably exercising or discussing exercise technique.
  NOT: any content that merely has fitness hashtags or is by a fitness creator
  discussing non-fitness topics. For "morning routine" or "wellness" content
  that includes brief exercise, use secondary topic if exercise is minor.
- travel: Destinations, travel tips, cultural experiences, travel vlogs
- music: Music performance, music discussion, artist spotlights, song rankings.
  NOT: videos that merely have background music.
- dance: Dance performance, choreography, dance tutorials
- comedy: Content whose primary purpose is humor. Skits, standup, observational
  comedy. For content that is BOTH funny AND informative, use the primary
  purpose as topic (e.g., food for a funny cooking video) and let affect
  capture the humor (funny + informative).
- education: Structured knowledge transfer with clear pedagogical intent —
  the creator is explicitly teaching a concept or skill. If you're unsure
  whether something is education vs. career/finance/health advice, prefer
  the domain-specific label and use secondary=education if teaching is present.
- technology: Tech products, software, gadgets, tech industry, coding, AI
- gaming: Video games, game reviews, gaming culture, esports
- sports: Athletic events, sports commentary, team fandom, highlights
- pets: Animal content, pet care, animal behavior
- art: Visual art, illustration, photography, creative process, digital art
- books: Book recommendations, reading content, literary discussion
- movies_tv: Film/TV discussion, reviews, scene reactions, fan content, edits
- news: Current events reporting, news commentary
- politics: Political commentary, policy discussion, civic engagement
- science: Scientific concepts, research, experiments, natural phenomena
- nature: Wildlife, landscapes, environmental content, outdoor activities
- diy: Home improvement, crafts, building, handmade projects
- finance: Personal finance, investing, economics, wealth building
- relationships: Dating, friendships, family dynamics, social skills
- parenting: Child-rearing, family life, parenthood experiences
- health: Medical information, mental health, wellness, nutrition science.
  Distinct from fitness: health is about wellbeing/medical topics, fitness is
  about exercise. For content that blends both (e.g., "morning routine for
  energy" with stretching), use primary for the dominant focus, secondary for
  the other.
- career: Professional development, job advice, workplace dynamics,
  entrepreneurship, productivity methods
- real_estate: Property, housing, home buying/selling
- automotive: Cars, motorcycles, vehicle content, car culture
- other: Use when no label above fits. Always include a micro_label description.

### Genre — Content format (single label + confidence)

- tutorial: Step-by-step instruction with clear teaching intent
- review: Opinion/evaluation of a product, place, or experience
- vlog: Personal documentation of daily life or experiences
- skit: Scripted comedic or dramatic performance
- storytime: Narrative personal anecdote
- haul: Showing purchased items
- asmr: Autonomous sensory meridian response content
- challenge: Participating in a viral challenge or trend
- reaction: Responding to other content
- compilation: Collection of clips or items (montage, ranking)
- before_after: Transformation content
- day_in_life: Documenting a typical or notable day
- get_ready_with_me: Preparation/getting ready content
- unboxing: Opening and revealing products
- recipe: Cooking demonstration with ingredients/steps
- workout: Exercise demonstration
- news_commentary: Discussion/opinion on current events
- interview: Conversation with a guest/subject
- timelapse: Time-compressed footage
- meme: Viral format, template-based humor, cultural reference
- duet: Side-by-side with another creator's content
- room_tour: Showing a space/environment
- outfit_showcase: Displaying clothing/style
- ranking: Ordered list of items by preference/quality
- edit: Fan-made creative compilation, usually with music
- pov: First-person perspective scenario
- other: Include description

### Affect — Viewer emotional experience (MULTI-LABEL with categorical tiers)

Assign each applicable affect label a tier:
- "dominant": The primary emotional experience (usually 1, max 2)
- "secondary": Clearly present but not the main vibe (0-2 labels)
- "minor": Detectable but subtle (0-2 labels)
Only include labels that genuinely apply. Omit labels that don't.

- funny: Makes the viewer laugh or smile — comedy, satire, ironic juxtaposition,
  meme humor, dry wit. Includes subtle/cultural humor.
- wholesome: Warm, heartfelt, emotionally tender content
- sad: Evokes sadness, grief, loss, melancholy
- angry: Provokes outrage, frustration, injustice
- nostalgic: Triggers memories, longing for the past, retro aesthetics
- inspiring: Makes the viewer feel motivated to change, improve, or overcome.
  Requires genuine emotional uplift — NOT merely useful or informative content.
  If the primary value is "this is useful info," use informative instead.
- informative: Content primarily consumed for its factual or practical value.
  Tutorials, how-tos, tips, explainers, advice, recommendations. The viewer
  saves this to LEARN or REFERENCE, not to feel emotionally uplifted.
- cringe: Secondhand embarrassment, awkwardness
- satisfying: Sense of completion, order, sensory pleasure
- scary: Fear, suspense, horror, startling content
- relaxing: Calming, soothing, meditative, ambient
- shocking: Surprise, disbelief, unexpected twist
- neutral: No dominant emotional charge. Use only when no other label applies.

### Presentation Style (up to 2 labels)

- talking_head, voiceover, text_overlay, screen_recording, slideshow,
  cinematic, raw_footage, animation, mixed

### Content Provenance (single label)

- original, repost, duet, stitch, remix, clip, ai_generated, unknown

### Communicative Intent (single label)

- entertain, inform, persuade, inspire, sell, vent, document, connect, provoke

### Creator Role (single label)

- professional, amateur, brand, influencer, journalist, educator, artist,
  activist, anonymous

### Viewer Orientation (single label — why did the user SAVE this?)

- passive_consumption, active_learning, social_sharing, inspiration_saving,
  background_noise, emotional_regulation, shopping_research

## Output Format

Return JSON:
{{
  "topic": {{
    "primary": "label",
    "secondary": "label or null",
    "micro_labels": ["specific refinements"],
    "confidence": 0.85
  }},
  "genre": {{
    "label": "label",
    "micro_labels": [],
    "confidence": 0.9
  }},
  "affect": [
    {{"label": "informative", "tier": "dominant"}},
    {{"label": "funny", "tier": "secondary"}},
    {{"label": "satisfying", "tier": "minor"}}
  ],
  "presentation_style": ["talking_head", "text_overlay"],
  "content_provenance": {{
    "label": "original",
    "confidence": 0.95
  }},
  "communicative_intent": {{
    "label": "inform",
    "confidence": 0.85
  }},
  "creator_role": {{
    "label": "amateur",
    "confidence": 0.8
  }},
  "viewer_orientation": {{
    "label": "active_learning",
    "confidence": 0.75
  }}
}}"""


# ── Helpers ────────────────────────────────────────────────────────────────

def estimate_cost(in_tok: int, out_tok: int) -> float:
    return (in_tok * INPUT_COST_PER_M + out_tok * OUTPUT_COST_PER_M) / 1_000_000


def safe_json_parse(text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown fences and list wrapping."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        parsed = json.loads(text)
        # Handle model wrapping response in an array
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return parsed[0]
        if isinstance(parsed, list):
            # Multiple items — take first dict or wrap
            for item in parsed:
                if isinstance(item, dict):
                    return item
            return {"_parse_error": True, "_raw_text": text[:2000]}
        return parsed
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw_text": text[:2000]}


def image_to_inline(path: Path) -> dict:
    """Convert local image file to Gemini inline data part."""
    b64 = base64.b64encode(path.read_bytes()).decode()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return {"inlineData": {"mimeType": mime, "data": b64}}


def build_context(item: dict) -> str:
    """Build metadata context string from a golden set item."""
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

    return "\n".join(parts)


# ── Gemini Client ──────────────────────────────────────────────────────────

def gemini_generate(parts: list[dict], max_tokens: int = PASS1_MAX_TOKENS,
                    temperature: float = 0.2, json_mode: bool = True,
                    grounding: bool = False) -> dict:
    """Call Gemini generateContent API."""
    # gemini-3-flash-preview lists grounding support but doesn't trigger search in practice.
    # Use gemini-2.5-flash for grounding experiments — it's the only model that actually searches.
    model = GEMINI_MODEL_GROUNDING if grounding else GEMINI_MODEL

    gen_config = {"maxOutputTokens": max_tokens, "temperature": temperature}
    # JSON mode (responseMimeType) is incompatible with grounding tools —
    # when grounding is enabled, let the model return free text and parse JSON from it
    if json_mode and not grounding:
        gen_config["responseMimeType"] = "application/json"

    body: dict = {
        "contents": [{"parts": parts}],
        "generationConfig": gen_config,
    }
    if grounding:
        body["tools"] = [{"googleSearch": {}}]

    resp = httpx.post(
        f"{GEMINI_API_BASE}/models/{model}:generateContent",
        params={"key": GEMINI_API_KEY},
        json=body,
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def gemini_upload_file(file_path: str, mime_type: str) -> str:
    """Upload a file to Gemini File API, return file resource name."""
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
    """Poll until file is ACTIVE, return URI."""
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


def gemini_delete_file(file_name: str) -> None:
    try:
        httpx.delete(f"{GEMINI_API_BASE}/{file_name}",
                     params={"key": GEMINI_API_KEY}, timeout=10)
    except Exception:
        pass


# ── Media Handling ─────────────────────────────────────────────────────────

def get_video_path(item_id: str) -> Path | None:
    """Get local video file path for an item."""
    path = MEDIA_DIR / f"video_{item_id}.mp4"
    return path if path.exists() else None


def get_slideshow_images(item_id: str) -> list[Path]:
    """Get local slideshow image paths for an item."""
    return sorted(MEDIA_DIR.glob(f"slide_{item_id}_*.jpg"))


def get_thumbnail_path(item_id: str) -> Path | None:
    """Get local thumbnail path for an item."""
    path = MEDIA_DIR / f"thumb_{item_id}.jpg"
    return path if path.exists() else None


def extract_keyframes(video_path: Path, interval_seconds: int = 10) -> list[Path]:
    """Extract keyframes from video at given interval using ffmpeg."""
    output_pattern = MEDIA_DIR / f"keyframe_{video_path.stem}_%03d.jpg"
    # Clean previous keyframes
    for old in MEDIA_DIR.glob(f"keyframe_{video_path.stem}_*.jpg"):
        old.unlink()

    try:
        subprocess.run([
            "ffmpeg", "-i", str(video_path),
            "-vf", f"fps=1/{interval_seconds}",
            "-q:v", "2",
            str(output_pattern),
        ], capture_output=True, timeout=60, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    return sorted(MEDIA_DIR.glob(f"keyframe_{video_path.stem}_*.jpg"))


def download_thumbnail(item: dict) -> Path | None:
    """Download thumbnail from Apify CDN URL."""
    url = (item.get("apify") or {}).get("thumbnail_url")
    if not url:
        return None
    dest = MEDIA_DIR / f"thumb_{item['id']}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception:
        return None


# ── Result Saving ──────────────────────────────────────────────────────────

def save_result(item_id: str, stage: str, prompt: str, api_resp: dict,
                parsed: dict, latency_ms: int, output_dir: Path,
                upload_ms: int = 0, ctx: dict | None = None) -> dict:
    """Save per-item result to JSON file."""
    usage = api_resp.get("usageMetadata", {})
    in_tok = usage.get("promptTokenCount", 0)
    out_tok = usage.get("candidatesTokenCount", 0)

    # Extract grounding metadata if present
    grounding_sources = []
    candidates = api_resp.get("candidates", [])
    if candidates:
        gm = candidates[0].get("groundingMetadata", {})
        for chunk in gm.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                grounding_sources.append({"uri": web["uri"], "title": web.get("title", "")})

    record = {
        "item_id": item_id,
        "stage": stage,
        "model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parsed_output": parsed,
        "grounding_sources": grounding_sources,
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
    stage_dir = output_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"{item_id}.json").write_text(json.dumps(record, indent=2, default=str))
    return record


# ── Pipeline Passes ────────────────────────────────────────────────────────

def run_pass1(item: dict, output_dir: Path, grounding: bool = False) -> dict | None:
    """Pass 1: Perception + Entity Extraction with full visual input."""
    pid = item["id"]
    apify = item.get("apify", {})
    context = build_context(item)
    is_slideshow = apify.get("is_slideshow", False)

    start = time.time()
    upload_ms = 0
    file_name = None

    try:
        if is_slideshow:
            imgs = get_slideshow_images(pid)
            if not imgs:
                # Fall back to thumbnail
                thumb = get_thumbnail_path(pid) or download_thumbnail(item)
                imgs = [thumb] if thumb else []
            if not imgs:
                return None
            img_count = len(imgs)
            prompt = PASS1_SLIDESHOW_PROMPT.format(
                context=context, image_count=img_count)
            parts = [{"text": prompt}] + [image_to_inline(p) for p in imgs]
        else:
            video_path = get_video_path(pid)
            if video_path:
                t0 = time.time()
                file_name = gemini_upload_file(str(video_path), "video/mp4")
                uri = gemini_wait_for_file(file_name)
                upload_ms = int((time.time() - t0) * 1000)
                prompt = PASS1_VIDEO_PROMPT.format(context=context)
                parts = [{"text": prompt},
                         {"fileData": {"mimeType": "video/mp4", "fileUri": uri}}]
            else:
                # Fall back to thumbnail
                thumb = get_thumbnail_path(pid) or download_thumbnail(item)
                if not thumb:
                    return None
                prompt = PASS1_VIDEO_PROMPT.format(context=context)
                parts = [{"text": prompt}, image_to_inline(thumb)]

        # When grounding is ON, disable JSON mode (incompatible with tools)
        api_resp = gemini_generate(parts, max_tokens=PASS1_MAX_TOKENS,
                                   grounding=grounding,
                                   json_mode=not grounding)

        if file_name:
            gemini_delete_file(file_name)

        latency = int((time.time() - start) * 1000)
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)

        ctx = {
            "is_slideshow": is_slideshow,
            "has_video": get_video_path(pid) is not None,
            "has_thumbnail": get_thumbnail_path(pid) is not None,
            "grounding_enabled": grounding,
        }
        return save_result(pid, "pass1_perception", prompt, api_resp,
                           parsed, latency, output_dir, upload_ms, ctx)

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        if file_name:
            gemini_delete_file(file_name)
        save_result(pid, "pass1_perception", "", {},
                    {"_error": str(e)}, latency, output_dir)
        return {"_error": str(e), "item_id": pid}


def run_pass2(item: dict, pass1_result: dict, output_dir: Path) -> dict | None:
    """Pass 2: Classification with Pass 1 output + visual keyframes."""
    pid = item["id"]
    apify = item.get("apify", {})
    is_slideshow = apify.get("is_slideshow", False)

    # Build Pass 1 summary for the classification prompt
    p1 = pass1_result.get("parsed_output", {})
    pass1_summary = json.dumps(p1, indent=2, default=str)[:4000]

    # Build metadata sections
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
        # Build visual parts for classification
        visual_parts: list[dict] = []

        if is_slideshow:
            imgs = get_slideshow_images(pid)
            if not imgs:
                thumb = get_thumbnail_path(pid) or download_thumbnail(item)
                if thumb:
                    imgs = [thumb]
            visual_parts = [image_to_inline(p) for p in imgs]
        else:
            video_path = get_video_path(pid)
            if video_path:
                keyframes = extract_keyframes(video_path, interval_seconds=10)
                visual_parts = [image_to_inline(kf) for kf in keyframes]
            else:
                thumb = get_thumbnail_path(pid) or download_thumbnail(item)
                if thumb:
                    visual_parts = [image_to_inline(thumb)]

        parts = [{"text": prompt}] + visual_parts
        api_resp = gemini_generate(parts, max_tokens=PASS2_MAX_TOKENS)

        latency = int((time.time() - start) * 1000)
        text = api_resp["candidates"][0]["content"]["parts"][0]["text"]
        parsed = safe_json_parse(text)

        ctx = {
            "is_slideshow": is_slideshow,
            "visual_input": "slideshow_images" if is_slideshow else
                           ("keyframes_10s" if get_video_path(pid) else "thumbnail"),
            "keyframe_count": len(visual_parts),
        }
        return save_result(pid, "pass2_classification", prompt, api_resp,
                           parsed, latency, output_dir, ctx=ctx)

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        save_result(pid, "pass2_classification", "", {},
                    {"_error": str(e)}, latency, output_dir)
        return {"_error": str(e), "item_id": pid}


# ── Media Download ─────────────────────────────────────────────────────────

def download_media_for_items(items: list[dict]) -> None:
    """Download videos and slideshow images via Apify with media downloads enabled."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # Collect URLs that need media download
    urls_needing_media = []
    for item in items:
        pid = item["id"]
        is_slideshow = (item.get("apify") or {}).get("is_slideshow", False)
        if is_slideshow:
            if not get_slideshow_images(pid):
                urls_needing_media.append(item["url"])
        else:
            if not get_video_path(pid):
                urls_needing_media.append(item["url"])

    if not urls_needing_media:
        print("All media already downloaded.")
        return

    print(f"Need to download media for {len(urls_needing_media)} items via Apify...")
    print(f"Estimated cost: ~${len(urls_needing_media) * 0.015:.2f}")

    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}",
               "Content-Type": "application/json"}
    client = httpx.Client(timeout=60)

    # Run Apify with media downloads enabled
    resp = client.post(
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs",
        headers=headers,
        json={
            "postURLs": urls_needing_media,
            "resultsPerPage": len(urls_needing_media),
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": True,
            "shouldDownloadSlideshowImages": True,
            "shouldDownloadSubtitles": True,
            "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES",
        },
    )
    resp.raise_for_status()
    run_id = resp.json()["data"]["id"]
    print(f"Apify run started: {run_id}")

    # Poll for completion
    start = time.time()
    while time.time() - start < 900:
        time.sleep(15)
        elapsed = int(time.time() - start)
        resp = client.get(f"https://api.apify.com/v2/actor-runs/{run_id}",
                          headers=headers)
        resp.raise_for_status()
        sd = resp.json()["data"]
        status = sd["status"]
        print(f"  [{elapsed}s] {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"ERROR: Apify run ended with {status}")
        return

    cost = sd.get("usageTotalUsd", "?")
    print(f"Apify run succeeded. Cost: ${cost}")

    # Fetch results
    dataset_id = sd["defaultDatasetId"]
    resp = client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers, timeout=120)
    resp.raise_for_status()
    apify_items = resp.json()

    # Download media files from Apify KV store URLs
    downloaded = 0
    for ai in apify_items:
        vid_id = str(ai.get("id", ""))
        if not vid_id:
            continue

        is_slide = ai.get("isSlideshow", False)

        if is_slide:
            slide_links = ai.get("slideshowImageLinks") or []
            for j, sl in enumerate(slide_links):
                dl_url = sl.get("downloadLink") or sl.get("tiktokLink")
                if dl_url:
                    dest = MEDIA_DIR / f"slide_{vid_id}_{j:03d}.jpg"
                    if not dest.exists():
                        try:
                            r = httpx.get(dl_url, timeout=60, follow_redirects=True)
                            r.raise_for_status()
                            dest.write_bytes(r.content)
                            downloaded += 1
                        except Exception:
                            pass
        else:
            # Video — check mediaUrls or downloadAddr
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

        # Always grab thumbnail
        cover = (ai.get("videoMeta") or {}).get("coverUrl")
        if cover:
            thumb_dest = MEDIA_DIR / f"thumb_{vid_id}.jpg"
            if not thumb_dest.exists():
                try:
                    r = httpx.get(cover, timeout=30, follow_redirects=True)
                    r.raise_for_status()
                    thumb_dest.write_bytes(r.content)
                except Exception:
                    pass

    print(f"Downloaded {downloaded} media files to {MEDIA_DIR.relative_to(REPO_ROOT)}")
    client.close()


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline_v3.py <golden_set.json> [options]")
        print("  --output DIR        Output directory (default: workbench/data/pipeline_v3/)")
        print("  --grounding         Enable Google Search grounding on Pass 1")
        print("  --item ID           Run single item only")
        print("  --download-media    Download media files via Apify before running")
        print("  --limit N           Process only first N items")
        print("  --pass1-only        Run only Pass 1")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    items = json.loads(input_path.read_text())

    # Parse args
    grounding = "--grounding" in sys.argv
    download_media = "--download-media" in sys.argv
    pass1_only = "--pass1-only" in sys.argv

    output_dir = RESULTS_DIR / "pipeline_v3"
    single_item = None
    limit = None

    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_dir = Path(sys.argv[i + 1])
        if arg == "--item" and i + 1 < len(sys.argv):
            single_item = sys.argv[i + 1]
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter items
    if single_item:
        items = [i for i in items if i["id"] == single_item]
        if not items:
            print(f"ERROR: Item {single_item} not found")
            sys.exit(1)
    if limit:
        items = items[:limit]

    print(f"Pipeline v3 — {len(items)} items")
    print(f"  Model: {GEMINI_MODEL}")
    print(f"  Grounding: {'ON' if grounding else 'OFF'}")
    print(f"  Output: {output_dir}")

    # Download media if requested
    if download_media:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        download_media_for_items(items)

    # Check media availability
    has_video = sum(1 for i in items if get_video_path(i["id"]))
    has_slides = sum(1 for i in items if get_slideshow_images(i["id"]))
    has_thumb = sum(1 for i in items if get_thumbnail_path(i["id"]))
    print(f"  Media: {has_video} videos, {has_slides} slideshows, {has_thumb} thumbnails")
    if has_video == 0 and has_slides == 0:
        print("  WARNING: No video/slideshow media found. Will use thumbnails only.")
        print("  Run with --download-media first to get full visual input.")

    # ── Pass 1 ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PASS 1: Perception + Entity Extraction")
    print(f"{'='*60}\n")

    pass1_results: dict[str, dict] = {}
    total_cost = 0.0
    t0 = time.time()

    # Load existing good results to skip re-processing
    pass1_dir = output_dir / "pass1_perception"
    items_to_run = []
    for item in items:
        existing = pass1_dir / f"{item['id']}.json"
        if existing.exists():
            try:
                r = json.loads(existing.read_text())
                po = r.get("parsed_output") or {}
                if isinstance(po, dict) and not po.get("_error") and not po.get("_parse_error"):
                    pass1_results[item["id"]] = r
                    continue
            except Exception:
                pass
        items_to_run.append(item)

    if pass1_results:
        print(f"  Loaded {len(pass1_results)} cached Pass 1 results, running {len(items_to_run)} remaining")
    items_for_pass1 = items_to_run

    def do_pass1(item: dict) -> tuple[str, dict | None]:
        return item["id"], run_pass1(item, output_dir, grounding=grounding)

    done = 0
    total_to_run = len(items_for_pass1)
    with ThreadPoolExecutor(max_workers=PASS1_CONCURRENCY) as ex:
        futs = {ex.submit(do_pass1, item): item for item in items_for_pass1}
        for fut in as_completed(futs):
            item = futs[fut]
            pid = item["id"]
            done += 1
            item_id, result = fut.result()
            elapsed = time.time() - t0

            if result and "_error" not in result:
                pass1_results[item_id] = result
                c = result["metrics"]["cost_usd"]
                total_cost += c
                po = result.get("parsed_output") or {}
                if not isinstance(po, dict):
                    po = {}
                ent_count = len(po.get("entities") or [])
                has_err = po.get("_parse_error", False)
                print(f"  [{done}/{total_to_run}] {pid}: "
                      f"{'PERR' if has_err else 'OK'} | "
                      f"{result['metrics']['input_tokens']}+{result['metrics']['output_tokens']} tok | "
                      f"{ent_count} ent | ${c:.4f} | {elapsed:.0f}s")
            elif result:
                err_msg = result.get('_error', '') if isinstance(result, dict) else str(result)
                print(f"  [{done}/{total_to_run}] {pid}: ERR — {err_msg[:60]}")
            else:
                print(f"  [{done}/{total_to_run}] {pid}: SKIP (no media)")

    wall1 = time.time() - t0
    parse_errs = sum(1 for r in pass1_results.values()
                     if "_parse_error" in r.get("parsed_output", {}))
    print(f"\nPass 1 done: {len(pass1_results)} items | ${total_cost:.4f} | "
          f"{parse_errs} parse errors | {wall1:.0f}s")

    if pass1_only:
        print("\n--pass1-only flag set. Stopping.")
        return

    # ── Pass 2 ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PASS 2: Classification")
    print(f"{'='*60}\n")

    pass2_cost = 0.0
    pass2_count = 0
    t0 = time.time()

    def do_pass2(item: dict) -> tuple[str, dict | None]:
        p1 = pass1_results.get(item["id"])
        if not p1:
            return item["id"], None
        return item["id"], run_pass2(item, p1, output_dir)

    done = 0
    with ThreadPoolExecutor(max_workers=PASS2_CONCURRENCY) as ex:
        futs = {ex.submit(do_pass2, item): item for item in items if item["id"] in pass1_results}
        for fut in as_completed(futs):
            item = futs[fut]
            pid = item["id"]
            done += 1
            item_id, result = fut.result()
            elapsed = time.time() - t0

            if result and "_error" not in result:
                pass2_count += 1
                c = result["metrics"]["cost_usd"]
                pass2_cost += c
                po = result.get("parsed_output") or {}
                if not isinstance(po, dict):
                    po = {}
                topic = po.get("topic") or {}
                topic_str = topic.get("primary", "?") if isinstance(topic, dict) else "?"
                has_err = po.get("_parse_error", False)
                print(f"  [{done}/{len(pass1_results)}] {pid}: "
                      f"{'PERR' if has_err else 'OK'} | "
                      f"topic={topic_str} | ${c:.4f} | {elapsed:.0f}s")
            elif result:
                err_msg = result.get('_error', '') if isinstance(result, dict) else str(result)
                print(f"  [{done}/{len(pass1_results)}] {pid}: ERR — {err_msg[:60]}")
            else:
                print(f"  [{done}/{len(pass1_results)}] {pid}: SKIP")

    wall2 = time.time() - t0
    print(f"\nPass 2 done: {pass2_count} items | ${pass2_cost:.4f} | {wall2:.0f}s")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print(f"{'='*60}")
    print(f"  Items processed: {len(pass1_results)}/{len(items)}")
    print(f"  Pass 1 cost: ${total_cost:.4f}")
    print(f"  Pass 2 cost: ${pass2_cost:.4f}")
    print(f"  Total cost:  ${total_cost + pass2_cost:.4f}")
    print(f"  Total time:  {wall1 + wall2:.0f}s")
    print(f"  Output dir:  {output_dir}")
    print(f"  Grounding:   {'ON' if grounding else 'OFF'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
