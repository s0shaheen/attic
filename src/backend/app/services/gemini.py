"""Gemini Flash client for file upload and pipeline support.

Functions:
- upload_file_sync(): Upload a file (video) to Gemini File API for processing.
- wait_for_file_sync(): Poll until an uploaded file reaches ACTIVE state.
- delete_file_sync(): Delete an uploaded file from Gemini.

All return Result-style values (never raise on API errors).

NOTE: classify() and analyze_visual() were removed — the pipeline handles
all classification and visual perception via its own sync implementations.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Gemini API endpoint
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_UPLOAD_BASE = "https://generativelanguage.googleapis.com/upload/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# Request defaults
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
