"""Tests for the versioned prompt loader."""

import hashlib

import pytest

from app.services.prompt_loader import (
    clear_cache,
    compute_prompt_hash,
    get_active_version,
    load_prompt,
    load_prompt_set,
    load_registry,
    validate_all_prompts,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Clear prompt cache before each test."""
    clear_cache()
    yield
    clear_cache()


class TestLoadRegistry:
    def test_returns_dict_with_expected_sets(self):
        registry = load_registry()
        assert "agent" in registry
        assert "classify" in registry
        assert "vision" in registry

    def test_each_set_has_active_version(self):
        registry = load_registry()
        for set_name, set_data in registry.items():
            assert "active" in set_data, f"{set_name} missing 'active' key"
            assert "versions" in set_data, f"{set_name} missing 'versions' key"

    def test_caches_result(self):
        first = load_registry()
        second = load_registry()
        assert first is second  # Same object reference


class TestGetActiveVersion:
    def test_returns_v1_for_all_sets(self):
        assert get_active_version("agent") == "v1"
        assert get_active_version("classify") == "v1"
        assert get_active_version("vision") == "v1"

    def test_unknown_set_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown prompt set"):
            get_active_version("nonexistent")


class TestLoadPrompt:
    def test_returns_content_for_existing_file(self):
        content = load_prompt("agent", "identity")
        assert "Attic" in content
        assert "TikTok" in content

    def test_uses_active_version_when_none_specified(self):
        content = load_prompt("agent", "identity")
        content_explicit = load_prompt("agent", "identity", version="v1")
        assert content == content_explicit

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            load_prompt("agent", "nonexistent_section")

    def test_missing_set_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown prompt set"):
            load_prompt("nonexistent_set", "identity")

    def test_caches_result(self):
        content1 = load_prompt("agent", "identity")
        content2 = load_prompt("agent", "identity")
        assert content1 == content2

    def test_classify_tier1_loads_correctly(self):
        content = load_prompt("classify", "tier1")
        assert "METADATA" in content
        assert "{context}" in content
        assert "TOPIC LABELS" in content

    def test_vision_modes_all_load(self):
        for mode in ["general", "books", "scenes", "places", "text", "products"]:
            content = load_prompt("vision", mode)
            assert "Return ONLY valid JSON" in content


class TestLoadPromptSet:
    def test_agent_returns_all_sections_in_order(self):
        sections = load_prompt_set("agent")
        assert len(sections) == 7  # 7 agent sections
        # First section should be identity
        assert "Attic" in sections[0]
        # Last section should be formatting
        assert "Response Formatting" in sections[-1]

    def test_classify_returns_tier1(self):
        sections = load_prompt_set("classify")
        assert len(sections) == 1
        assert "METADATA" in sections[0]

    def test_vision_returns_all_modes(self):
        sections = load_prompt_set("vision")
        assert len(sections) == 6


class TestValidateAllPrompts:
    def test_passes_with_complete_files(self):
        # Should not raise
        validate_all_prompts()

    def test_populates_cache(self):
        from app.services.prompt_loader import _prompt_cache

        validate_all_prompts()
        # 7 agent + 1 classify + 6 vision = 14
        assert len(_prompt_cache) == 14


class TestComputePromptHash:
    def test_deterministic(self):
        h1 = compute_prompt_hash("test content")
        h2 = compute_prompt_hash("test content")
        assert h1 == h2

    def test_changes_on_content_change(self):
        h1 = compute_prompt_hash("version 1")
        h2 = compute_prompt_hash("version 2")
        assert h1 != h2

    def test_returns_16_char_hex(self):
        h = compute_prompt_hash("test")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestPromptRegressionSnapshot:
    """Ensure the refactored prompt output matches the pre-refactor hash."""

    def test_build_system_prompt_matches_snapshot(self):
        from app.services.prompts import build_system_prompt

        build_system_prompt.cache_clear()
        prompt = build_system_prompt()
        h = hashlib.sha256(prompt.encode()).hexdigest()
        expected = "9169dd19a1f1e4e6a1b74bc4867cee72041bf0e99b7f3428598cdceb1d4c4c04"
        assert h == expected, (
            f"System prompt hash changed! Expected {expected}, got {h}. "
            "This means the prompt content changed during the refactor, "
            "which will break Anthropic prompt caching."
        )
