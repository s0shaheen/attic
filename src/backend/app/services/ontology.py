"""Two-tier ontology for TikTok content classification.

Tier-1: Fixed validated labels from ONTOLOGY_V1. Drives collections and aggregation.
Tier-2: Free-form micro-labels from LLM. Drives discovery and ontology evolution.

Eight facets cover affect, topic, genre, communicative intent, creator role,
viewer orientation, presentation style, and content provenance.
"""

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# ONTOLOGY_V1 — Tier-1 validated labels
# ---------------------------------------------------------------------------
# Each facet maps to a list of allowed labels. The agent's classify tool
# must pick from these; anything else is treated as a Tier-2 micro-label.

ONTOLOGY_V1: dict[str, list[str]] = {
    "affect": [
        "funny",
        "wholesome",
        "sad",
        "angry",
        "nostalgic",
        "inspiring",
        "cringe",
        "satisfying",
        "scary",
        "relaxing",
        "shocking",
        "neutral",
    ],
    "topic": [
        "food",
        "fashion",
        "beauty",
        "fitness",
        "travel",
        "music",
        "dance",
        "comedy",
        "education",
        "technology",
        "gaming",
        "sports",
        "pets",
        "art",
        "books",
        "movies_tv",
        "news",
        "politics",
        "science",
        "nature",
        "diy",
        "finance",
        "relationships",
        "parenting",
        "health",
        "career",
        "real_estate",
        "automotive",
        "other",
    ],
    "genre": [
        "tutorial",
        "review",
        "vlog",
        "skit",
        "storytime",
        "haul",
        "asmr",
        "challenge",
        "reaction",
        "compilation",
        "before_after",
        "day_in_life",
        "get_ready_with_me",
        "unboxing",
        "recipe",
        "workout",
        "news_commentary",
        "interview",
        "timelapse",
        "meme",
        "duet",
        "other",
    ],
    "communicative_intent": [
        "entertain",
        "inform",
        "persuade",
        "inspire",
        "sell",
        "vent",
        "document",
        "connect",
        "provoke",
    ],
    "creator_role": [
        "professional",
        "amateur",
        "brand",
        "influencer",
        "journalist",
        "educator",
        "artist",
        "activist",
        "anonymous",
    ],
    "viewer_orientation": [
        "passive_consumption",
        "active_learning",
        "social_sharing",
        "inspiration_saving",
        "background_noise",
        "emotional_regulation",
        "shopping_research",
    ],
    "presentation_style": [
        "talking_head",
        "voiceover",
        "text_overlay",
        "screen_recording",
        "slideshow",
        "cinematic",
        "raw_footage",
        "animation",
        "mixed",
    ],
    "content_provenance": [
        "original",
        "repost",
        "duet",
        "stitch",
        "remix",
        "clip",
        "ai_generated",
        "unknown",
    ],
}

# Precompute for fast validation
_VALID_LABELS: dict[str, frozenset[str]] = {
    facet: frozenset(labels) for facet, labels in ONTOLOGY_V1.items()
}

FACET_NAMES: list[str] = list(ONTOLOGY_V1.keys())


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result of classifying a single media event."""

    tier1: dict[str, str]  # facet → validated label
    tier2: dict[str, list[str]]  # facet → free-form micro-labels
    confidence: dict[str, float]  # facet → confidence score (0-1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_classification(raw: dict[str, Any]) -> ClassificationResult:
    """Validate and split a raw classification dict into tier-1/tier-2 labels.

    For each facet, the primary label is checked against ONTOLOGY_V1:
    - If valid → tier-1
    - If not in ONTOLOGY_V1 → stored as tier-2 micro-label, tier-1 gets "other" or closest match

    Args:
        raw: Dict with facet names as keys. Each value should be a dict with
             "label" (str), optionally "micro_labels" (list[str]),
             and optionally "confidence" (float).

    Returns:
        ClassificationResult with validated tier-1 and tier-2 labels.
    """
    tier1: dict[str, str] = {}
    tier2: dict[str, list[str]] = {}
    confidence: dict[str, float] = {}

    for facet in FACET_NAMES:
        facet_data = raw.get(facet)
        if facet_data is None:
            continue

        if isinstance(facet_data, str):
            # Simple string value
            label = facet_data.lower().strip()
            micro_labels: list[str] = []
            conf = 0.5
        elif isinstance(facet_data, dict):
            label = str(facet_data.get("label", "")).lower().strip()
            micro_labels = facet_data.get("micro_labels", [])
            conf = float(facet_data.get("confidence", 0.5))
        else:
            continue

        valid_labels = _VALID_LABELS.get(facet, frozenset())

        if label in valid_labels:
            tier1[facet] = label
        else:
            # Label not in ontology — treat as micro-label, use fallback
            if label:
                micro_labels = [label] + [m for m in micro_labels if m != label]
            # Use "other" if the facet has it, otherwise skip tier-1
            if "other" in valid_labels:
                tier1[facet] = "other"
            elif "unknown" in valid_labels:
                tier1[facet] = "unknown"
            elif "neutral" in valid_labels:
                tier1[facet] = "neutral"

        if micro_labels:
            tier2[facet] = [str(m).strip() for m in micro_labels if str(m).strip()]

        confidence[facet] = max(0.0, min(1.0, conf))

    return ClassificationResult(tier1=tier1, tier2=tier2, confidence=confidence)


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def format_ontology_for_prompt() -> str:
    """Format the ontology as a string for inclusion in LLM prompts.

    Returns a compact representation listing each facet and its valid labels,
    designed for prompt-caching efficiency (stable text across calls).
    """
    lines = ["## Classification Ontology (Tier-1 Labels)", ""]
    for facet, labels in ONTOLOGY_V1.items():
        facet_display = facet.replace("_", " ").title()
        labels_str = ", ".join(labels)
        lines.append(f"**{facet_display}**: {labels_str}")
    lines.append("")
    lines.append(
        "For each facet, pick exactly one tier-1 label. "
        "You may also suggest micro-labels (tier-2) for nuance."
    )
    lines.append(
        "Return JSON with facet names as keys, each containing: "
        '"label" (tier-1), "micro_labels" (list of strings), "confidence" (0-1).'
    )
    return "\n".join(lines)
