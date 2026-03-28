"""Versioned prompt loader — reads prompts from filesystem with registry.

The registry.json manifest declares prompt sets, their versions, and which
sections compose each set. Prompt text lives in Markdown files under
src/backend/prompts/. Loaded once at startup, cached in memory.

Usage:
    from app.services.prompt_loader import load_prompt, load_prompt_set

    # Load a single prompt section
    text = load_prompt("classify", "tier1")           # uses active version
    text = load_prompt("vision", "books", version="v1")  # explicit version

    # Load all sections for a prompt set (e.g., agent system prompt)
    sections = load_prompt_set("agent")  # returns list of strings in registry order
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve prompts directory relative to the backend root
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # src/backend/
_PROMPTS_DIR = _BACKEND_ROOT / "prompts"

# Module-level caches
_registry_cache: dict[str, Any] | None = None
_prompt_cache: dict[tuple[str, str, str], "PromptInfo"] = {}


@dataclass(frozen=True)
class PromptInfo:
    """Loaded prompt with metadata."""

    set_name: str
    section: str
    version: str
    content: str
    hash: str


def _get_prompts_dir() -> Path:
    """Return the prompts directory path."""
    return _PROMPTS_DIR


def load_registry() -> dict[str, Any]:
    """Load and cache the prompt registry from registry.json."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    registry_path = _get_prompts_dir() / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"Prompt registry not found: {registry_path}")

    with open(registry_path) as f:
        _registry_cache = json.load(f)

    logger.info({"event": "prompt_registry_loaded", "sets": list(_registry_cache.keys())})
    return _registry_cache


def get_active_version(set_name: str) -> str:
    """Return the active version for a prompt set from the registry."""
    registry = load_registry()
    if set_name not in registry:
        raise KeyError(f"Unknown prompt set: {set_name!r}. Available: {list(registry.keys())}")
    return registry[set_name]["active"]


def compute_prompt_hash(content: str) -> str:
    """Compute a SHA-256 hash of prompt content for cache tracking."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def load_prompt(set_name: str, section: str, version: str | None = None) -> str:
    """Load a single prompt section from the filesystem.

    Args:
        set_name: Prompt set (e.g., "agent", "classify", "vision").
        section: Section name within the set (e.g., "identity", "tier1", "books").
        version: Version string (e.g., "v1"). If None, uses registry's active version.

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
        KeyError: If the set_name is not in the registry.
    """
    if version is None:
        version = get_active_version(set_name)

    cache_key = (set_name, section, version)
    if cache_key in _prompt_cache:
        return _prompt_cache[cache_key].content

    prompt_path = _get_prompts_dir() / set_name / version / f"{section}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path} "
            f"(set={set_name!r}, section={section!r}, version={version!r})"
        )

    content = prompt_path.read_text(encoding="utf-8").rstrip("\n")
    prompt_hash = compute_prompt_hash(content)

    info = PromptInfo(
        set_name=set_name,
        section=section,
        version=version,
        content=content,
        hash=prompt_hash,
    )
    _prompt_cache[cache_key] = info

    return content


def load_prompt_set(set_name: str, version: str | None = None) -> list[str]:
    """Load all sections for a prompt set in registry-declared order.

    The registry defines which sections compose each set and their order.
    Uses the 'sections', 'files', or 'modes' key depending on the set.

    Args:
        set_name: Prompt set name (e.g., "agent", "classify", "vision").
        version: Version string. If None, uses registry's active version.

    Returns:
        List of prompt text strings in registry order.
    """
    if version is None:
        version = get_active_version(set_name)

    registry = load_registry()
    set_config = registry[set_name]["versions"][version]

    # Registry uses different keys for different set types
    section_names = (
        set_config.get("sections") or set_config.get("files") or set_config.get("modes") or []
    )

    return [load_prompt(set_name, section, version) for section in section_names]


def validate_all_prompts() -> None:
    """Validate that all registry-declared prompt files exist.

    Call at application startup to fail fast on missing files.

    Raises:
        FileNotFoundError: If any declared prompt file is missing.
    """
    registry = load_registry()
    missing: list[str] = []

    for set_name, set_data in registry.items():
        for version, version_data in set_data["versions"].items():
            section_names = (
                version_data.get("sections")
                or version_data.get("files")
                or version_data.get("modes")
                or []
            )
            for section in section_names:
                path = _get_prompts_dir() / set_name / version / f"{section}.md"
                if not path.exists():
                    missing.append(str(path))

    if missing:
        raise FileNotFoundError(
            f"Missing {len(missing)} prompt file(s):\n" + "\n".join(f"  - {p}" for p in missing)
        )

    # Pre-load all prompts into cache
    for set_name, set_data in registry.items():
        for version, version_data in set_data["versions"].items():
            section_names = (
                version_data.get("sections")
                or version_data.get("files")
                or version_data.get("modes")
                or []
            )
            for section in section_names:
                load_prompt(set_name, section, version)

    total = len(_prompt_cache)
    logger.info({"event": "prompt_validation_complete", "total_prompts": total})


def clear_cache() -> None:
    """Clear all cached prompts and registry. For testing only."""
    global _registry_cache
    _registry_cache = None
    _prompt_cache.clear()
