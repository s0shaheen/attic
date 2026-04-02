"""System prompt for the Claude orchestrator agent.

Provides build_system_prompt() which composes the full system prompt including:
- Identity and role
- Data quality awareness (pipeline classification tiers)
- 5 query plan templates with explicit tool sequences
- Full ontology (tier-1 labels with key definitions)
- Recall check, cost awareness, disambiguation rules
- Formatting guidelines

Prompt sections are loaded from versioned Markdown files via prompt_loader.
The prompt is cached after first build for Anthropic prompt caching efficiency.
"""

from functools import lru_cache

from app.services.ontology import format_ontology_for_prompt
from app.services.prompt_loader import load_prompt_set

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    """Build the full system prompt for the Claude orchestrator.

    Loads sections from prompts/agent/v1/ in registry-declared order,
    then appends the dynamically-generated ontology section.

    Cached via lru_cache — the ontology and all sections are static, so the
    output is identical across calls. This maximizes Anthropic prompt caching
    efficiency (stable system prefix = cache hits).

    Returns:
        The complete system prompt string.
    """
    # Load all agent sections from filesystem in registry order
    sections = load_prompt_set("agent")

    # Ontology section is dynamically generated from ontology.py
    ontology_section = (
        "## Available Classification Labels\n\n"
        "When interpreting cached classifications from the pipeline, "
        "these are the valid tier-1 labels:\n\n" + format_ontology_for_prompt()
    )

    # Insert ontology after query_plan_templates (index 2), before recall_check
    # Registry order: identity, data_quality, query_plan_templates, recall_check, ...
    # Insert ontology at position 3 (after the first 3 sections)
    sections.insert(3, ontology_section)

    return "\n\n".join(sections)
