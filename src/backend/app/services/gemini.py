"""Gemini Flash client for classification, visual analysis, and file upload.

Functions:
- classify(): Classifies a media event using the classification prompt.
- analyze_visual(): Analyzes a thumbnail/image with Gemini vision + Google Search grounding.
- upload_file(): Upload a file (video) to Gemini File API for processing.
- wait_for_file(): Poll until an uploaded file reaches ACTIVE state.
- delete_file(): Delete an uploaded file from Gemini.

All return Result-style dataclasses (never raise on API errors).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from app.services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

# Gemini API endpoint
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_UPLOAD_BASE = "https://generativelanguage.googleapis.com/upload/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# Request defaults
CLASSIFY_MAX_TOKENS = 2048
VISUAL_MAX_TOKENS = 2048
PERCEPTION_MAX_TOKENS = 16384
REQUEST_TIMEOUT = 30.0
UPLOAD_TIMEOUT = 300.0
FILE_POLL_INTERVAL_S = 2
FILE_POLL_TIMEOUT_S = 120


# ---------------------------------------------------------------------------
# Gemini File API — upload, poll, delete (for video processing)
# ---------------------------------------------------------------------------


def upload_file_sync(
    api_key: str,
    file_path: str,
    mime_type: str = "video/mp4",
) -> str | None:
    """Upload a file to Gemini File API via resumable upload protocol.

    Args:
        api_key: Gemini API key.
        file_path: Local path to the file to upload.
        mime_type: MIME type of the file.

    Returns:
        File resource name (e.g., "files/abc123") or None on failure.
    """
    import os

    file_size = os.path.getsize(file_path)

    try:
        with httpx.Client(timeout=UPLOAD_TIMEOUT) as client:
            # Step 1: Initiate resumable upload
            resp = client.post(
                f"{GEMINI_UPLOAD_BASE}/files",
                params={"key": api_key},
                headers={
                    "X-Goog-Upload-Protocol": "resumable",
                    "X-Goog-Upload-Command": "start",
                    "X-Goog-Upload-Header-Content-Length": str(file_size),
                    "X-Goog-Upload-Header-Content-Type": mime_type,
                },
                json={"file": {"displayName": f"attic-pipeline-{int(time.time())}"}},
            )
            resp.raise_for_status()

            upload_url = resp.headers.get("X-Goog-Upload-URL")
            if not upload_url:
                logger.warning("Gemini upload: no upload URL in response headers")
                return None

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

            file_name = resp.json().get("file", {}).get("name")
            if file_name:
                logger.info(
                    "Gemini file uploaded",
                    extra={"file_name": file_name, "size_bytes": file_size},
                )
            return file_name

    except Exception as e:
        logger.warning("Gemini file upload failed", extra={"error": str(e)})
        return None


def wait_for_file_sync(
    api_key: str,
    file_name: str,
    timeout: int = FILE_POLL_TIMEOUT_S,
) -> str | None:
    """Poll until a Gemini file reaches ACTIVE state.

    Args:
        api_key: Gemini API key.
        file_name: File resource name (e.g., "files/abc123").
        timeout: Maximum wait time in seconds.

    Returns:
        File URI for use in generateContent, or None if failed/timed out.
    """
    elapsed = 0
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            while elapsed < timeout:
                resp = client.get(
                    f"{GEMINI_API_BASE}/{file_name}",
                    params={"key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                state = data.get("state", "")

                if state == "ACTIVE":
                    return data.get("uri", f"{GEMINI_API_BASE}/{file_name}")

                if state == "FAILED":
                    logger.warning(
                        "Gemini file processing failed",
                        extra={"file_name": file_name},
                    )
                    return None

                time.sleep(FILE_POLL_INTERVAL_S)
                elapsed += FILE_POLL_INTERVAL_S

    except Exception as e:
        logger.warning(
            "Gemini file poll error",
            extra={"file_name": file_name, "error": str(e)},
        )

    logger.warning(
        "Gemini file poll timed out",
        extra={"file_name": file_name, "timeout": timeout},
    )
    return None


def delete_file_sync(api_key: str, file_name: str) -> None:
    """Delete a file from Gemini File API. Best-effort, never raises."""
    try:
        with httpx.Client(timeout=10) as client:
            client.delete(
                f"{GEMINI_API_BASE}/{file_name}",
                params={"key": api_key},
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tier 1 classification prompt — loaded from prompts/classify/v1/tier1.md
# ---------------------------------------------------------------------------


def _get_tier1_prompt() -> str:
    """Load the Tier 1 classification prompt from the versioned filesystem."""
    return load_prompt("classify", "tier1")


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


def _get_vision_prompt(focus: VisionFocus) -> str:
    """Load a vision focus prompt from the versioned filesystem."""
    return load_prompt("vision", focus.value)


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
    prompt = (
        _get_tier1_prompt()
        .replace("{context}", context)
        .replace("{image_instruction}", image_instruction)
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
    base_prompt = _get_vision_prompt(focus)
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
