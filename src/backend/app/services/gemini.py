"""Gemini 3 Flash client for classification and visual analysis.

Two functions:
- classify(): Classifies a media event using text metadata + ontology prompt.
- analyze_visual(): Analyzes a thumbnail/image with Gemini vision + Google Search grounding.

Both return Result-style dataclasses (never raise on API errors).
"""

import json
import logging
from dataclasses import dataclass, field

import httpx

from app.services.ontology import format_ontology_for_prompt

logger = logging.getLogger(__name__)

# Gemini API endpoint
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.0-flash"

# Request defaults
CLASSIFY_MAX_TOKENS = 1024
VISUAL_MAX_TOKENS = 2048
REQUEST_TIMEOUT = 30.0


@dataclass
class ClassifyResult:
    """Result of a classification request."""

    success: bool
    raw_classification: dict | None = None
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


# Cached ontology prompt (stable across calls for prompt caching)
_ONTOLOGY_PROMPT: str | None = None


def _get_ontology_prompt() -> str:
    global _ONTOLOGY_PROMPT
    if _ONTOLOGY_PROMPT is None:
        _ONTOLOGY_PROMPT = format_ontology_for_prompt()
    return _ONTOLOGY_PROMPT


async def classify(
    api_key: str,
    caption: str | None,
    subtitle: str | None,
    hashtags: list[str] | None,
    creator_username: str | None,
    music_name: str | None,
) -> ClassifyResult:
    """Classify a media event using Gemini 3 Flash.

    Builds a prompt from text metadata and the ontology, asks Gemini to return
    structured JSON with tier-1 labels, micro-labels, and confidence scores.

    Args:
        api_key: Gemini API key.
        caption: Video caption text.
        subtitle: Transcribed subtitle text.
        hashtags: List of hashtags.
        creator_username: Creator's username.
        music_name: Name of the music track.

    Returns:
        ClassifyResult with raw_classification dict or error.
    """
    ontology = _get_ontology_prompt()

    # Build context from available metadata
    context_parts = []
    if caption:
        context_parts.append(f"Caption: {caption}")
    if subtitle:
        context_parts.append(f"Transcript: {subtitle[:500]}")
    if hashtags:
        context_parts.append(f"Hashtags: {', '.join(hashtags[:20])}")
    if creator_username:
        context_parts.append(f"Creator: @{creator_username}")
    if music_name:
        context_parts.append(f"Music: {music_name}")

    if not context_parts:
        return ClassifyResult(success=False, error="No metadata available for classification")

    context = "\n".join(context_parts)

    prompt = (
        f"{ontology}\n\n"
        f"## Content to Classify\n\n{context}\n\n"
        "Classify this TikTok content. Return ONLY valid JSON, no markdown fences."
    )

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
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

            # Parse the JSON response
            classification = json.loads(text)
            return ClassifyResult(success=True, raw_classification=classification)

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
) -> VisualAnalysisResult:
    """Analyze a thumbnail or image using Gemini vision + Google Search grounding.

    Args:
        api_key: Gemini API key.
        image_url: URL of the image/thumbnail to analyze.
        caption: Optional caption for context.

    Returns:
        VisualAnalysisResult with description, detected objects/text, and grounding sources.
    """
    prompt_parts = [
        "Analyze this TikTok thumbnail/image. Provide:",
        "1. A brief description of what's shown",
        "2. Key objects, people, or products visible",
        "3. Any text detected in the image (OCR)",
        "",
        "Return JSON with keys: description (str), objects (list of str), "
        "text_detected (str or null).",
        "Return ONLY valid JSON, no markdown fences.",
    ]
    if caption:
        prompt_parts.insert(0, f"Context caption: {caption}\n")

    prompt = "\n".join(prompt_parts)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
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
