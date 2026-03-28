"""Gemini Flash client for classification and visual analysis.

Two functions:
- classify(): Classifies a media event using the Tier 1 prompt (text metadata +
  optional thumbnail). Returns classification, entities, summary, and embedding text.
- analyze_visual(): Analyzes a thumbnail/image with Gemini vision + Google Search grounding.

Both return Result-style dataclasses (never raise on API errors).
"""

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Gemini API endpoint
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# Request defaults
CLASSIFY_MAX_TOKENS = 2048
VISUAL_MAX_TOKENS = 2048
REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Tier 1 classification prompt — ported from workbench/experiments/03-pipeline-v3
# ---------------------------------------------------------------------------

_TIER1_PROMPT = """\
You are processing a TikTok video for a personal media library. Your output \
powers search, browse filters, and aggregate stats. Users will search for \
specific items ("that grilled cheese recipe"), browse by category ("show me \
fitness videos"), and ask questions about their collection ("what topics do I \
save most?").

{image_instruction}

METADATA:
{context}

Return JSON with this exact structure:

{
  "summary": "2-3 sentences: what is this about? Why save it? \
Be specific — name people, products, places.",
  "entities": [
    {
      "name": "specific name (e.g., 'Adidas Samba')",
      "type": "person|place|product|brand|song|artist|book|\
movie_or_show|app_or_tool|restaurant|exercise|recipe|\
ingredient|clothing|technique|trend_or_meme|\
cultural_reference|event|podcast|game",
      "relevance": "primary|supporting"
    }
  ],
  "topic": {
    "primary": "label",
    "secondary": "label or null"
  },
  "genre": "label",
  "affect": {
    "dominant": "label",
    "secondary": "label or null"
  },
  "viewer_orientation": "active_learning|\
passive_consumption|inspiration_saving|\
shopping_research|social_sharing|emotional_regulation",
  "embedding_text": "A 100-150 word paragraph for semantic \
search. Describe the video as if helping someone find it \
later. Include: main subject, key entities by name, what \
happens, content type. Be specific — 'Adidas Samba sneaker \
recommendation for European travel' over 'shoe video'."
}

TOPIC LABELS (pick one primary, optional secondary):
food, fashion, beauty, fitness, travel, music, dance, comedy, education, \
technology, gaming, sports, pets, art, books, movies_tv, news, politics, \
science, nature, diy, finance, relationships, parenting, health, career, \
real_estate, automotive, other

Key definitions:
- fitness: Exercise must be VISIBLE or explicitly discussed. \
NOT content that merely has fitness hashtags.
- comedy: Primary purpose is humor. For funny-but-informative \
content, use the informative topic and let affect capture humor.
- education: Structured teaching. Career advice = career.
- health: Wellbeing/medical. Distinct from fitness (exercise).

GENRE LABELS:
tutorial, review, vlog, skit, storytime, haul, asmr, challenge, reaction, \
compilation, before_after, day_in_life, get_ready_with_me, unboxing, recipe, \
workout, news_commentary, interview, timelapse, meme, duet, room_tour, \
outfit_showcase, ranking, edit, pov, other

AFFECT LABELS:
funny, wholesome, sad, angry, nostalgic, inspiring, informative, cringe, \
satisfying, scary, relaxing, shocking, neutral

Key definitions:
- inspiring: Genuine emotional uplift — NOT merely useful/informative content.
- informative: Saved to LEARN or REFERENCE. Tutorials, tips, advice, recommendations.
- neutral: Only when no other label applies.

INSTRUCTIONS:
- Extract up to 5 entities. Focus on what someone would search for.
- Use comments to identify entities, cultural references, and context.
- On-screen text in images is high-value — transcribe names, products, places.
- Be specific in entity names: "Nike Pegasus 39" not "running shoes".
- The embedding_text field is critical — it determines \
whether users can find this item via search. Write it like \
a rich description, not a label list."""


# ---------------------------------------------------------------------------
# Vision focus modes
# ---------------------------------------------------------------------------


class VisionFocus(StrEnum):
    """Focus mode for targeted vision analysis prompts."""

    GENERAL = "general"
    BOOKS = "books"
    SCENES = "scenes"
    PLACES = "places"
    TEXT = "text"
    PRODUCTS = "products"


_VISION_PROMPTS: dict[VisionFocus, str] = {
    VisionFocus.GENERAL: (
        "Analyze this TikTok thumbnail/image. Provide:\n"
        "1. A brief description of what's shown\n"
        "2. Key objects, people, or products visible\n"
        "3. Any text detected in the image (OCR)\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
    VisionFocus.BOOKS: (
        "Analyze this image for book-related content. Look for:\n"
        "- Book covers, spines, or pages\n"
        "- Titles, author names, publisher logos\n"
        "- ISBN barcodes or bookshelf contents\n"
        "- Any reading material (magazines, comics, textbooks)\n"
        "\n"
        "List each identifiable book with title and author if visible.\n"
        "Capture any visible text on covers, spines, or pages.\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
    VisionFocus.SCENES: (
        "Analyze this image for movie, TV show, or entertainment content. Look for:\n"
        "- Recognizable actors, characters, or celebrities\n"
        "- Movie or TV show scenes, frames, or posters\n"
        "- Streaming service UI or video player screenshots\n"
        "- Award shows, premieres, or entertainment events\n"
        "\n"
        "Identify specific movies, TV shows, or actors if recognizable.\n"
        "Note any on-screen text like titles or credits.\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
    VisionFocus.PLACES: (
        "Analyze this image for place and location content. Look for:\n"
        "- Restaurant facades, interiors, or menus\n"
        "- Store signage, business names, or logos\n"
        "- Landmarks, monuments, or recognizable buildings\n"
        "- Street signs, addresses, or neighborhood features\n"
        "\n"
        "Identify specific businesses, restaurants, or landmarks if recognizable.\n"
        "Capture all visible signage text, addresses, and business names.\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
    VisionFocus.TEXT: (
        "Focus on extracting ALL visible text from this image. This may be:\n"
        "- A screenshot of an app, website, or message\n"
        "- A recipe, ingredient list, or instructions\n"
        "- A note, list, article, or caption card\n"
        "- Overlaid text, subtitles, or watermarks\n"
        "\n"
        "Transcribe ALL readable text as accurately as possible.\n"
        "Preserve formatting like line breaks and bullet points where visible.\n"
        "Put all transcribed text in the text_detected field.\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
    VisionFocus.PRODUCTS: (
        "Analyze this image for products and commercial items. Look for:\n"
        "- Product packaging, labels, or brand logos\n"
        "- Price tags, store displays, or shopping content\n"
        "- Unboxing content or product reviews\n"
        "- Specific brand names, model numbers, or product names\n"
        "\n"
        "Identify specific brands and product names if visible.\n"
        "Capture any text on labels, packaging, or price tags.\n"
        "\n"
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).\n"
        "Return ONLY valid JSON, no markdown fences."
    ),
}


# Module-level client for connection reuse across calls
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    return _client


@dataclass
class ClassifyResult:
    """Result of a classification request.

    The Tier 1 prompt returns structured JSON with classification labels,
    entities, a summary, and embedding text — all stored here.
    """

    success: bool
    raw_classification: dict | None = None
    summary: str | None = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    embedding_text: str | None = None
    error: str | None = None


@dataclass
class VisualAnalysisResult:
    """Result of a visual analysis request."""

    success: bool
    description: str | None = None
    objects: list[str] = field(default_factory=list)
    text_detected: str | None = None
    grounding_sources: list[dict] = field(default_factory=list)
    error: str | None = None


def _build_classify_context(
    caption: str | None,
    subtitle: str | None,
    hashtags: list[str] | None,
    creator_username: str | None,
    music_name: str | None,
    duration_seconds: int | None,
    comments: list[str] | None,
) -> str | None:
    """Build the METADATA context block for the classify prompt.

    Returns None if no metadata is available.
    """
    parts: list[str] = []
    if caption:
        parts.append(f"Caption: {caption}")
    if subtitle:
        parts.append(f"Transcript: {subtitle[:500]}")
    if hashtags:
        parts.append(f"Hashtags: {', '.join(hashtags[:20])}")
    if creator_username:
        parts.append(f"Creator: @{creator_username}")
    if music_name:
        parts.append(f"Music: {music_name}")
    if duration_seconds is not None:
        parts.append(f"Duration: {duration_seconds}s")
    if comments:
        top_comments = comments[:10]
        parts.append(f"Top comments: {' | '.join(top_comments)}")
    return "\n".join(parts) if parts else None


async def classify(
    api_key: str,
    caption: str | None,
    subtitle: str | None,
    hashtags: list[str] | None,
    creator_username: str | None,
    music_name: str | None,
    *,
    duration_seconds: int | None = None,
    thumbnail_url: str | None = None,
    comments: list[str] | None = None,
    model: str | None = None,
) -> ClassifyResult:
    """Classify a media event using the Tier 1 prompt.

    Builds a rich prompt from text metadata (and optionally a thumbnail image),
    asks Gemini to return structured JSON with classification labels, entities,
    a summary, and embedding text optimized for semantic search.

    Args:
        api_key: Gemini API key.
        caption: Video caption text.
        subtitle: Transcribed subtitle text.
        hashtags: List of hashtags.
        creator_username: Creator's username.
        music_name: Name of the music track.
        duration_seconds: Video duration in seconds.
        thumbnail_url: URL of thumbnail image (included as visual input).
        comments: Top comments for context.
        model: Gemini model name override (defaults to DEFAULT_GEMINI_MODEL).

    Returns:
        ClassifyResult with raw_classification, summary, entities, embedding_text,
        or error.
    """
    context = _build_classify_context(
        caption,
        subtitle,
        hashtags,
        creator_username,
        music_name,
        duration_seconds,
        comments,
    )

    if context is None:
        return ClassifyResult(success=False, error="No metadata available for classification")

    # Build prompt from template
    if thumbnail_url:
        image_instruction = (
            "You are seeing a thumbnail image from the video. "
            "Extract what you can from this image plus the metadata below."
        )
    else:
        image_instruction = "No image is available. Classify based on the metadata below."

    # Use replace instead of .format() to avoid crashes when user content
    # contains braces (e.g., caption "Use {this} for cooking")
    prompt = _TIER1_PROMPT.replace("{context}", context).replace(
        "{image_instruction}", image_instruction
    )
    gemini_model = model or DEFAULT_GEMINI_MODEL

    # Build request parts — text first, then optional image
    parts: list[dict[str, Any]] = [{"text": prompt}]
    if thumbnail_url:
        parts.append(
            {
                "fileData": {
                    "mimeType": "image/jpeg",
                    "fileUri": thumbnail_url,
                }
            }
        )

    try:
        client = _get_client()
        resp = await client.post(
            f"{GEMINI_API_BASE}/models/{gemini_model}:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "maxOutputTokens": CLASSIFY_MAX_TOKENS,
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
        )

        if resp.status_code != 200:
            logger.warning(
                {
                    "event": "gemini_classify_error",
                    "status": resp.status_code,
                    "body": resp.text[:200],
                }
            )
            return ClassifyResult(
                success=False,
                error=f"Gemini API error: {resp.status_code}",
            )

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        classification = json.loads(text)

        return ClassifyResult(
            success=True,
            raw_classification=classification,
            summary=classification.get("summary"),
            entities=classification.get("entities") or [],
            embedding_text=classification.get("embedding_text"),
        )

    except httpx.TimeoutException:
        logger.warning({"event": "gemini_classify_timeout"})
        return ClassifyResult(success=False, error="Gemini classification timed out")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning({"event": "gemini_classify_parse_error", "error": str(e)})
        return ClassifyResult(success=False, error=f"Failed to parse Gemini response: {e}")
    except httpx.HTTPError as e:
        logger.warning({"event": "gemini_classify_http_error", "error": str(e)})
        return ClassifyResult(success=False, error=f"Gemini request failed: {e}")


async def analyze_visual(
    api_key: str,
    image_url: str,
    caption: str | None = None,
    focus: VisionFocus = VisionFocus.GENERAL,
    *,
    model: str | None = None,
) -> VisualAnalysisResult:
    """Analyze a thumbnail or image using Gemini vision + Google Search grounding.

    Args:
        api_key: Gemini API key.
        image_url: URL of the image/thumbnail to analyze.
        caption: Optional caption for context.
        focus: Vision analysis focus mode for targeted extraction.
        model: Gemini model name override (defaults to DEFAULT_GEMINI_MODEL).

    Returns:
        VisualAnalysisResult with description, detected objects/text, and grounding sources.
    """
    base_prompt = _VISION_PROMPTS[focus]
    if caption:
        prompt = f"Context caption: {caption}\n\n{base_prompt}"
    else:
        prompt = base_prompt

    gemini_model = model or DEFAULT_GEMINI_MODEL

    try:
        client = _get_client()
        resp = await client.post(
            f"{GEMINI_API_BASE}/models/{gemini_model}:generateContent",
            params={"key": api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "fileData": {
                                    "mimeType": "image/jpeg",
                                    "fileUri": image_url,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": VISUAL_MAX_TOKENS,
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
                "tools": [{"googleSearch": {}}],
            },
        )

        if resp.status_code != 200:
            logger.warning(
                {
                    "event": "gemini_visual_error",
                    "status": resp.status_code,
                    "body": resp.text[:200],
                }
            )
            return VisualAnalysisResult(
                success=False,
                error=f"Gemini API error: {resp.status_code}",
            )

        data = resp.json()
        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
        parsed = json.loads(text)

        # Extract grounding metadata if present
        grounding = []
        grounding_meta = candidate.get("groundingMetadata", {})
        for chunk in grounding_meta.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                grounding.append({"uri": web["uri"], "title": web.get("title", "")})

        return VisualAnalysisResult(
            success=True,
            description=parsed.get("description"),
            objects=parsed.get("objects", []),
            text_detected=parsed.get("text_detected"),
            grounding_sources=grounding,
        )

    except httpx.TimeoutException:
        logger.warning({"event": "gemini_visual_timeout"})
        return VisualAnalysisResult(success=False, error="Gemini visual analysis timed out")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning({"event": "gemini_visual_parse_error", "error": str(e)})
        return VisualAnalysisResult(success=False, error=f"Failed to parse Gemini response: {e}")
    except httpx.HTTPError as e:
        logger.warning({"event": "gemini_visual_http_error", "error": str(e)})
        return VisualAnalysisResult(success=False, error=f"Gemini request failed: {e}")
