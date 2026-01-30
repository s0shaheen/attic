"""Tier management service.

This module provides tier limit checking and validation for user subscription tiers.
Tier limits determine how many videos a user can process from their TikTok export.

Tier Limits (from PRD):
- free: 200 videos
- explorer: 1,500 videos
- expert: 3,000 videos
- pioneer: 7,500 videos
"""

import logging
from enum import Enum
from typing import Final

logger = logging.getLogger(__name__)


class SubscriptionTier(str, Enum):
    """User subscription tiers.

    String-based enum for database compatibility.
    """

    FREE = "free"
    EXPLORER = "explorer"
    EXPERT = "expert"
    PIONEER = "pioneer"


# Tier video limits as defined in PRD
TIER_LIMITS: Final[dict[str, int]] = {
    SubscriptionTier.FREE.value: 200,
    SubscriptionTier.EXPLORER.value: 1_500,
    SubscriptionTier.EXPERT.value: 3_000,
    SubscriptionTier.PIONEER.value: 7_500,
}


def get_tier_limit(tier: str) -> int:
    """Get the video limit for a subscription tier.

    Args:
        tier: The subscription tier (free, explorer, expert, pioneer)

    Returns:
        Maximum number of videos the tier can process

    Raises:
        ValueError: If tier is not recognized
    """
    tier_lower = tier.lower()
    if tier_lower not in TIER_LIMITS:
        valid_tiers = list(TIER_LIMITS.keys())
        raise ValueError(f"Unknown tier: {tier}. Valid tiers: {valid_tiers}")
    return TIER_LIMITS[tier_lower]


def check_within_limit(tier: str, count: int) -> bool:
    """Check if a video count is within a tier's limit.

    Args:
        tier: The subscription tier
        count: The number of videos to check

    Returns:
        True if count is within the tier's limit, False otherwise

    Raises:
        ValueError: If tier is not recognized
    """
    limit = get_tier_limit(tier)
    return count <= limit


def get_next_tier(current_tier: str) -> str | None:
    """Get the next higher tier from the current tier.

    Args:
        current_tier: The current subscription tier

    Returns:
        The next higher tier, or None if already at highest tier

    Raises:
        ValueError: If tier is not recognized
    """
    tier_order = [
        SubscriptionTier.FREE.value,
        SubscriptionTier.EXPLORER.value,
        SubscriptionTier.EXPERT.value,
        SubscriptionTier.PIONEER.value,
    ]

    current_lower = current_tier.lower()
    if current_lower not in tier_order:
        valid_tiers = tier_order
        raise ValueError(f"Unknown tier: {current_tier}. Valid tiers: {valid_tiers}")

    current_index = tier_order.index(current_lower)
    if current_index >= len(tier_order) - 1:
        return None  # Already at highest tier
    return tier_order[current_index + 1]


def get_tier_that_fits(count: int) -> str | None:
    """Get the lowest tier that can accommodate a video count.

    Args:
        count: The number of videos to accommodate

    Returns:
        The lowest tier that can process this many videos,
        or None if count exceeds all tier limits
    """
    tier_order = [
        SubscriptionTier.FREE.value,
        SubscriptionTier.EXPLORER.value,
        SubscriptionTier.EXPERT.value,
        SubscriptionTier.PIONEER.value,
    ]

    for tier in tier_order:
        if TIER_LIMITS[tier] >= count:
            return tier
    return None


def estimate_processing_minutes(total_items: int) -> int:
    """Estimate processing time in minutes for a given number of items.

    Based on PRD performance requirements:
    - 1000 videos: ~10-15 minutes
    - Approximately 0.5 seconds per video average across all steps
    - ~1 minute per 100 videos with 30% buffer

    Args:
        total_items: Number of items to process

    Returns:
        Estimated processing time in minutes (minimum 1)
    """
    if total_items <= 0:
        return 0

    # ~1 minute per 100 videos
    base_minutes = max(1, total_items // 100)
    # 30% buffer for variability
    buffer = base_minutes * 0.3
    return int(base_minutes + buffer)
