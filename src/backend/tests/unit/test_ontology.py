"""Tests for ontology validation and prompt formatting."""

from app.services.ontology import (
    FACET_NAMES,
    ONTOLOGY_V1,
    ClassificationResult,
    format_ontology_for_prompt,
    validate_classification,
)


class TestOntologyConstants:
    """Test ontology structure and constants."""

    def test_ontology_has_eight_facets(self):
        assert len(ONTOLOGY_V1) == 8

    def test_facet_names_match_ontology_keys(self):
        assert FACET_NAMES == list(ONTOLOGY_V1.keys())

    def test_all_facets_have_labels(self):
        for facet, labels in ONTOLOGY_V1.items():
            assert len(labels) > 0, f"Facet '{facet}' has no labels"

    def test_no_duplicate_labels_per_facet(self):
        for facet, labels in ONTOLOGY_V1.items():
            assert len(labels) == len(set(labels)), f"Facet '{facet}' has duplicate labels"


class TestValidateClassification:
    """Test validate_classification function."""

    def test_valid_tier1_labels_pass_through(self):
        raw = {
            "affect": {"label": "funny", "confidence": 0.9},
            "topic": {"label": "food", "confidence": 0.8},
        }
        result = validate_classification(raw)
        assert result.tier1["affect"] == "funny"
        assert result.tier1["topic"] == "food"

    def test_invalid_label_falls_back_to_other(self):
        raw = {
            "topic": {"label": "nonexistent_topic", "confidence": 0.5},
        }
        result = validate_classification(raw)
        assert result.tier1["topic"] == "other"
        assert "nonexistent_topic" in result.tier2.get("topic", [])

    def test_invalid_affect_falls_back_to_neutral(self):
        raw = {
            "affect": {"label": "nonexistent_affect", "confidence": 0.5},
        }
        result = validate_classification(raw)
        assert result.tier1["affect"] == "neutral"

    def test_invalid_content_provenance_falls_back_to_unknown(self):
        raw = {
            "content_provenance": {"label": "nonexistent", "confidence": 0.5},
        }
        result = validate_classification(raw)
        assert result.tier1["content_provenance"] == "unknown"

    def test_string_value_accepted(self):
        raw = {"affect": "funny"}
        result = validate_classification(raw)
        assert result.tier1["affect"] == "funny"

    def test_case_insensitive_labels(self):
        raw = {"affect": {"label": "FUNNY", "confidence": 0.9}}
        result = validate_classification(raw)
        assert result.tier1["affect"] == "funny"

    def test_label_with_whitespace_stripped(self):
        raw = {"affect": {"label": "  funny  ", "confidence": 0.9}}
        result = validate_classification(raw)
        assert result.tier1["affect"] == "funny"

    def test_micro_labels_preserved(self):
        raw = {
            "topic": {
                "label": "food",
                "micro_labels": ["italian", "pasta"],
                "confidence": 0.8,
            },
        }
        result = validate_classification(raw)
        assert result.tier2["topic"] == ["italian", "pasta"]

    def test_confidence_clamped_to_0_1(self):
        raw = {
            "affect": {"label": "funny", "confidence": 1.5},
            "topic": {"label": "food", "confidence": -0.3},
        }
        result = validate_classification(raw)
        assert result.confidence["affect"] == 1.0
        assert result.confidence["topic"] == 0.0

    def test_missing_facets_skipped(self):
        raw = {"affect": {"label": "funny", "confidence": 0.9}}
        result = validate_classification(raw)
        assert "topic" not in result.tier1
        assert "topic" not in result.confidence

    def test_empty_input_returns_empty_result(self):
        result = validate_classification({})
        assert result.tier1 == {}
        assert result.tier2 == {}
        assert result.confidence == {}

    def test_unknown_facets_ignored(self):
        raw = {"nonexistent_facet": {"label": "whatever", "confidence": 0.5}}
        result = validate_classification(raw)
        assert result.tier1 == {}

    def test_non_dict_non_string_values_skipped(self):
        raw = {"affect": 42, "topic": ["food"]}
        result = validate_classification(raw)
        assert result.tier1 == {}

    def test_default_confidence_is_0_5(self):
        raw = {"affect": "funny"}
        result = validate_classification(raw)
        assert result.confidence["affect"] == 0.5

    def test_result_is_classification_result(self):
        result = validate_classification({})
        assert isinstance(result, ClassificationResult)


class TestFormatOntologyForPrompt:
    """Test format_ontology_for_prompt function."""

    def test_returns_string(self):
        result = format_ontology_for_prompt()
        assert isinstance(result, str)

    def test_contains_all_facets(self):
        result = format_ontology_for_prompt()
        for facet in FACET_NAMES:
            facet_display = facet.replace("_", " ").title()
            assert facet_display in result

    def test_contains_sample_labels(self):
        result = format_ontology_for_prompt()
        assert "funny" in result
        assert "food" in result
        assert "tutorial" in result

    def test_contains_instructions(self):
        result = format_ontology_for_prompt()
        assert "tier-1" in result.lower()
        assert "JSON" in result

    def test_contains_label_definitions(self):
        result = format_ontology_for_prompt()
        assert "Key Definitions" in result
        assert "inspiring:" in result
        assert "informative:" in result
        assert "fitness:" in result

    def test_contains_new_genre_definitions(self):
        result = format_ontology_for_prompt()
        assert "room_tour:" in result
        assert "outfit_showcase:" in result
        assert "ranking:" in result


class TestNewLabels:
    """Test that new labels added in v3 are recognized."""

    def test_informative_is_valid_affect(self):
        assert "informative" in ONTOLOGY_V1["affect"]

    def test_validate_classification_accepts_informative(self):
        raw = {"affect": {"label": "informative", "confidence": 0.9}}
        result = validate_classification(raw)
        assert result.tier1["affect"] == "informative"

    def test_new_genre_labels_exist(self):
        genres = ONTOLOGY_V1["genre"]
        for label in ["room_tour", "outfit_showcase", "ranking", "edit", "pov"]:
            assert label in genres, f"Genre '{label}' missing from ONTOLOGY_V1"

    def test_validate_classification_accepts_new_genres(self):
        for label in ["room_tour", "outfit_showcase", "ranking", "edit", "pov"]:
            raw = {"genre": {"label": label, "confidence": 0.8}}
            result = validate_classification(raw)
            assert result.tier1["genre"] == label
