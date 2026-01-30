"""Tests for tier management service.

This module contains comprehensive tests for tier limits and validation including:
- Tier limit lookups
- Limit checking
- Processing time estimation
- Tier upgrade paths
"""

import os

# Set environment variables BEFORE importing anything from app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-for-testing-only")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "test-stripe-key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-stripe-webhook")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")

import pytest

from app.services.tiers import (
    TIER_LIMITS,
    SubscriptionTier,
    check_within_limit,
    estimate_processing_minutes,
    get_next_tier,
    get_tier_limit,
    get_tier_that_fits,
)


# =============================================================================
# get_tier_limit Tests
# =============================================================================


class TestGetTierLimit:
    """Tests for get_tier_limit function."""

    def test_free_tier_limit_is_200(self):
        """Free tier has 200 video limit."""
        assert get_tier_limit("free") == 200

    def test_explorer_tier_limit_is_1500(self):
        """Explorer tier has 1,500 video limit."""
        assert get_tier_limit("explorer") == 1_500

    def test_expert_tier_limit_is_3000(self):
        """Expert tier has 3,000 video limit."""
        assert get_tier_limit("expert") == 3_000

    def test_pioneer_tier_limit_is_7500(self):
        """Pioneer tier has 7,500 video limit."""
        assert get_tier_limit("pioneer") == 7_500

    def test_tier_case_insensitive(self):
        """Tier names are case insensitive."""
        assert get_tier_limit("FREE") == 200
        assert get_tier_limit("Free") == 200
        assert get_tier_limit("EXPLORER") == 1_500

    def test_unknown_tier_raises_value_error(self):
        """Unknown tier raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_tier_limit("unknown")
        assert "Unknown tier" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)


# =============================================================================
# check_within_limit Tests
# =============================================================================


class TestCheckWithinLimit:
    """Tests for check_within_limit function."""

    def test_within_free_tier_limit_returns_true(self):
        """200 videos on free tier returns True."""
        assert check_within_limit("free", 200) is True

    def test_within_free_tier_limit_exact_returns_true(self):
        """Exact limit returns True."""
        assert check_within_limit("free", 200) is True
        assert check_within_limit("explorer", 1_500) is True
        assert check_within_limit("expert", 3_000) is True
        assert check_within_limit("pioneer", 7_500) is True

    def test_exceeds_free_tier_limit_returns_false(self):
        """201 videos on free tier returns False."""
        assert check_within_limit("free", 201) is False

    def test_zero_count_within_limit(self):
        """Zero count is always within limit."""
        assert check_within_limit("free", 0) is True
        assert check_within_limit("explorer", 0) is True

    def test_explorer_tier_accepts_1500(self):
        """Explorer tier accepts up to 1,500 videos."""
        assert check_within_limit("explorer", 1_500) is True
        assert check_within_limit("explorer", 1_501) is False

    def test_expert_tier_accepts_3000(self):
        """Expert tier accepts up to 3,000 videos."""
        assert check_within_limit("expert", 3_000) is True
        assert check_within_limit("expert", 3_001) is False

    def test_pioneer_tier_accepts_7500(self):
        """Pioneer tier accepts up to 7,500 videos."""
        assert check_within_limit("pioneer", 7_500) is True
        assert check_within_limit("pioneer", 7_501) is False

    def test_unknown_tier_raises_value_error(self):
        """Unknown tier raises ValueError."""
        with pytest.raises(ValueError):
            check_within_limit("invalid_tier", 100)


# =============================================================================
# estimate_processing_minutes Tests
# =============================================================================


class TestEstimateProcessingMinutes:
    """Tests for estimate_processing_minutes function."""

    def test_zero_items_returns_zero(self):
        """Zero items returns 0 minutes."""
        assert estimate_processing_minutes(0) == 0

    def test_negative_items_returns_zero(self):
        """Negative items returns 0 minutes."""
        assert estimate_processing_minutes(-10) == 0

    def test_small_count_returns_minimum(self):
        """Small counts return at least 1 minute."""
        assert estimate_processing_minutes(1) >= 1
        assert estimate_processing_minutes(50) >= 1

    def test_100_items_estimate_reasonable(self):
        """100 items gives roughly 1 minute + buffer."""
        result = estimate_processing_minutes(100)
        assert 1 <= result <= 2

    def test_1000_items_within_prd_spec(self):
        """1000 items within PRD spec of 10-15 minutes."""
        result = estimate_processing_minutes(1000)
        # PRD says 1000 videos should take ~10-15 minutes
        # Our estimate: 10 base + 3 buffer = 13 minutes
        assert 10 <= result <= 15

    def test_estimate_scales_with_count(self):
        """Estimate increases with item count."""
        small = estimate_processing_minutes(100)
        medium = estimate_processing_minutes(500)
        large = estimate_processing_minutes(1000)

        assert small < medium < large

    def test_large_count_estimate_reasonable(self):
        """Large count (7500) gives reasonable estimate."""
        result = estimate_processing_minutes(7_500)
        # 75 base minutes + 22.5 buffer = 97 minutes (~1.5 hours)
        assert 90 <= result <= 100


# =============================================================================
# get_next_tier Tests
# =============================================================================


class TestGetNextTier:
    """Tests for get_next_tier function."""

    def test_free_to_explorer(self):
        """Free tier upgrades to explorer."""
        assert get_next_tier("free") == "explorer"

    def test_explorer_to_expert(self):
        """Explorer tier upgrades to expert."""
        assert get_next_tier("explorer") == "expert"

    def test_expert_to_pioneer(self):
        """Expert tier upgrades to pioneer."""
        assert get_next_tier("expert") == "pioneer"

    def test_pioneer_has_no_next(self):
        """Pioneer tier has no higher tier."""
        assert get_next_tier("pioneer") is None

    def test_tier_case_insensitive(self):
        """Tier names are case insensitive."""
        assert get_next_tier("FREE") == "explorer"
        assert get_next_tier("PIONEER") is None

    def test_unknown_tier_raises_value_error(self):
        """Unknown tier raises ValueError."""
        with pytest.raises(ValueError):
            get_next_tier("invalid")


# =============================================================================
# get_tier_that_fits Tests
# =============================================================================


class TestGetTierThatFits:
    """Tests for get_tier_that_fits function."""

    def test_small_count_fits_free(self):
        """Small counts fit in free tier."""
        assert get_tier_that_fits(100) == "free"
        assert get_tier_that_fits(200) == "free"

    def test_201_needs_explorer(self):
        """201 videos need explorer tier."""
        assert get_tier_that_fits(201) == "explorer"

    def test_1501_needs_expert(self):
        """1501 videos need expert tier."""
        assert get_tier_that_fits(1_501) == "expert"

    def test_3001_needs_pioneer(self):
        """3001 videos need pioneer tier."""
        assert get_tier_that_fits(3_001) == "pioneer"

    def test_exceeds_all_returns_none(self):
        """Count exceeding all tiers returns None."""
        assert get_tier_that_fits(7_501) is None
        assert get_tier_that_fits(10_000) is None

    def test_zero_fits_free(self):
        """Zero count fits free tier."""
        assert get_tier_that_fits(0) == "free"


# =============================================================================
# Tier Constants Tests
# =============================================================================


class TestTierConstants:
    """Tests for tier constants."""

    def test_tier_limits_dict_has_all_tiers(self):
        """TIER_LIMITS has all expected tiers."""
        expected_tiers = ["free", "explorer", "expert", "pioneer"]
        for tier in expected_tiers:
            assert tier in TIER_LIMITS

    def test_subscription_tier_enum_values(self):
        """SubscriptionTier enum has correct values."""
        assert SubscriptionTier.FREE.value == "free"
        assert SubscriptionTier.EXPLORER.value == "explorer"
        assert SubscriptionTier.EXPERT.value == "expert"
        assert SubscriptionTier.PIONEER.value == "pioneer"

    def test_tier_limits_are_positive(self):
        """All tier limits are positive integers."""
        for tier, limit in TIER_LIMITS.items():
            assert limit > 0
            assert isinstance(limit, int)

    def test_tier_limits_increase(self):
        """Higher tiers have higher limits."""
        assert TIER_LIMITS["free"] < TIER_LIMITS["explorer"]
        assert TIER_LIMITS["explorer"] < TIER_LIMITS["expert"]
        assert TIER_LIMITS["expert"] < TIER_LIMITS["pioneer"]
