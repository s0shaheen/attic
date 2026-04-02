"""Tests for system prompt builder."""

from app.services.prompts import build_system_prompt


class TestBuildSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_contains_identity(self):
        prompt = build_system_prompt()
        assert "Attic" in prompt
        assert "TikTok" in prompt

    def test_contains_ontology_labels(self):
        """Verify format_ontology_for_prompt() integration — key labels present."""
        prompt = build_system_prompt()
        # Spot-check labels from each facet
        assert "funny" in prompt  # affect
        assert "food" in prompt  # topic
        assert "tutorial" in prompt  # genre
        assert "entertain" in prompt  # communicative_intent
        assert "professional" in prompt  # creator_role

    def test_contains_plan_templates(self):
        """Each of the 5 plan template sections must be present."""
        prompt = build_system_prompt()
        assert "Entity Retrieval" in prompt
        assert "Creator Aggregation" in prompt
        assert "Simple Filter" in prompt
        assert "Interpretive" in prompt
        assert "Ambiguous" in prompt

    def test_contains_recall_check(self):
        prompt = build_system_prompt()
        assert "Recall Check" in prompt
        assert "perception" in prompt.lower()
        assert "low-text" in prompt.lower() or "low text" in prompt.lower()

    def test_contains_cost_awareness(self):
        prompt = build_system_prompt()
        assert "Cost Awareness" in prompt
        assert "cheaper" in prompt.lower() or "prefer" in prompt.lower()

    def test_does_not_duplicate_tool_descriptions(self):
        """Prompt should NOT contain tool schema descriptions — Claude gets
        those from the tools= parameter. DRY check."""
        prompt = build_system_prompt()
        # These phrases are from the old inline prompt's tool descriptions
        assert "Search and filter media events by text, hashtag" not in prompt
        assert "Semantic search — finds items matching the *meaning*" not in prompt

    def test_contains_disambiguation_rules(self):
        prompt = build_system_prompt()
        assert "Disambiguation" in prompt or "clarifying question" in prompt

    def test_contains_formatting_guidelines(self):
        prompt = build_system_prompt()
        assert "markdown" in prompt.lower()
        assert "canonical_url" in prompt or "clickable link" in prompt

    def test_cached_returns_identical_output(self):
        """Repeated calls must return the exact same string (caching)."""
        first = build_system_prompt()
        second = build_system_prompt()
        assert first is second  # Same object reference (lru_cache)

    def test_contains_data_quality_section(self):
        prompt = build_system_prompt()
        assert "Data Quality" in prompt
        assert "pipeline_v2" in prompt

    def test_contains_label_definitions(self):
        """Workbench-validated label definitions should be in the prompt."""
        prompt = build_system_prompt()
        assert "informative" in prompt
        assert "inspiring" in prompt
        # Key definitions from ontology
        assert "fitness:" in prompt.lower() or "fitness" in prompt

    def test_contains_new_labels(self):
        prompt = build_system_prompt()
        assert "informative" in prompt
        assert "room_tour" in prompt
        assert "pov" in prompt
