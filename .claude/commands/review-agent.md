---
description: Deep review of agent, classification, ontology, or prompt changes. Evaluates likely impact on user-facing quality.
argument-hint: "[--diff-only] [--versus main]"
---

## When to use

Use this instead of `/review` when the change is primarily about agent intelligence — prompt wording, tool definitions, ontology labels, classification logic, retrieval strategy. This review cares about output quality, not code quality (use `/review` for that).

## Step 1: Identify what changed

Read the diff. Categorize changes into:
- **Prompt changes** — system prompt, ontology prompt, tool descriptions
- **Tool changes** — tool parameters, tool logic, new tools, removed tools
- **Ontology changes** — new labels, removed labels, facet restructuring
- **Retrieval changes** — query construction, filter logic, embedding search
- **Classification changes** — Gemini prompt, temperature, model, response parsing

## Step 2: Prompt change analysis

If the system prompt or ontology prompt changed:

1. **Read the full before and after** (not just the diff). Context matters for prompts — a small change can shift meaning of surrounding instructions.
   ```bash
   git show HEAD:app/services/prompts.py > /tmp/prompt_before.py 2>/dev/null || echo "new file"
   cat app/services/prompts.py > /tmp/prompt_after.py
   ```

2. **Check for contradictions**: Does the new instruction conflict with any existing instruction? For example:
   - "Always use classify before responding" vs "Prefer cheap tools first" — when does each apply?
   - "Default to most specific intent" vs "Fallback to semantic search" — what triggers the fallback?

3. **Check for ambiguity**: Would the model know exactly what to do given this instruction, or could it interpret it multiple ways? Flag vague language:
   - "Try to..." → What if it can't? What's the fallback?
   - "When appropriate..." → Define when.
   - "Consider..." → Does it mean "always do" or "optionally do"?

4. **Check for regression risk**: Does this change affect cases BEYOND the intended target?
   - Changing affect classification prompts affects ALL content, not just the type being fixed
   - Adding a new query plan template is safe; modifying an existing one affects all queries matching that pattern
   - For each change, name 2-3 query types that could be affected unintentionally

5. **Evaluate cost impact**:
   - More tools called per query → higher cost per query
   - Longer system prompt → more input tokens per turn
   - New `analyze_visual` calls → Gemini vision is expensive
   - Quantify: "This adds ~X tokens to every query" or "This adds a Gemini call for Y% of queries"

## Step 3: Tool change analysis

If tool definitions or implementations changed:

1. **Contract check**: Does the tool's docstring/description match what it actually does?
   - Agent decides to call a tool based on the description
   - If description says "search by topic" but the function also accepts affect/genre, the agent won't know to use those parameters

2. **Schema consistency**: If tool parameters changed, verify:
   - The tool definition in the system prompt matches
   - The agent's tool JSON schema matches (check where tools are defined for the Anthropic API call)
   - Any mock in tests matches the new signature

3. **Return value completeness**: Does the tool return enough data for the agent to write a good response?
   - `query_items` returns items — does it include enough metadata (caption, creator, thumbnail) for the agent to describe results naturally?
   - `classify` returns tier1/tier2 — does the agent know how to present this to the user?

4. **Error paths**: What does the user see when this tool fails?
   - Tool returns `AgentToolResult(success=False, error=...)` — the agent should explain gracefully
   - Does the error message help the agent explain to the user? ("Gemini API timeout" is technical; "Classification unavailable" is user-friendly)

## Step 4: Ontology change analysis

If `ONTOLOGY_V1` or `validate_classification` changed:

1. **Orthogonality check**: New labels should be non-overlapping with existing ones.
   For each new label, ask: "If I showed a human a piece of content, could they reasonably assign BOTH this label and an existing label?" If yes → **WARN**: these overlap.
   
   Common overlaps to check:
   - affect: "wholesome" vs "inspiring" — wholesome implies warmth, inspiring implies motivation
   - topic: "fitness" vs "health" — fitness is activity-focused, health is broader
   - genre: "tutorial" vs "recipe" — recipe IS a tutorial subtype

2. **Coverage check**: Does the new label fill a gap that existing labels can't cover?
   - Ask: "What content would get this label that currently gets 'other' or a wrong label?"
   - If you can't name specific content → the label might be unnecessary

3. **Tier boundary check**: Should this be tier-1 (fixed vocabulary, drives collections) or tier-2 (free-form, drives discovery)?
   - Tier-1 test: "Would a user create a filter/collection with this label?" If yes → tier-1
   - Tier-2 test: "Is this label too specific for broad filtering but useful for micro-categorization?" If yes → tier-2

4. **Downstream impact**: What breaks?
   - Eval golden set has expected labels — do they need updating?
   - Query strategies in agent tools reference specific labels — do they handle the new label?
   - Any frontend code renders label names to users — does it handle the new label gracefully?

## Step 5: Retrieval change analysis

If `query_items` or embedding search logic changed:

1. **Synonym coverage**: Does the query strategy handle common ways users refer to the same thing?
   - User says "cooking" → topic could be "food", genre could be "recipe"
   - User says "funny" → affect is "funny", but also check genre "skit", "meme", "comedy" topic
   - User says "that restaurant" → this is an entity query, not a filter query

2. **Filter precision vs recall tradeoff**:
   - Adding more filters → higher precision, lower recall (might miss relevant items)
   - Fewer filters → lower precision, higher recall (more noise)
   - For a chat product, err toward recall — better to show too much than miss the right thing

3. **Embedding search sanity**: If cosine similarity threshold changed:
   - Lower threshold → more results, more noise
   - Higher threshold → fewer results, might miss relevant items
   - Test mentally: "At this threshold, would 'cooking tutorial' and 'recipe video' match? What about 'cooking tutorial' and 'cat video'?"

## Output format

```
## Agent Review: {description of change}

### Change Summary
{1-2 sentences: what changed and why}

### Quality Impact Assessment

**Intended improvement:**
{What queries/content types should get better}

**Regression risk:**
{What queries/content types could get worse, with specific examples}

**Cost impact:**
{Token/API call change per query, if any}

### Findings

1. **[RISK]** Prompt contradiction between lines X and Y
   Impact: Agent may oscillate between two strategies for vague queries
   Fix: Clarify priority order

2. **[GAP]** Tool description doesn't mention the new `genre` parameter
   Impact: Agent won't use genre-based filtering
   Fix: Update tool description in system prompt

3. **[OK]** Ontology change is orthogonal — no overlap detected

### Recommendation
{SHIP — quality should improve}
{HOLD — run evals first to measure}  
{RETHINK — regression risk is too high without mitigation}
```

If the recommendation is **HOLD**, suggest specific eval queries to test before shipping:
```
Run these queries against the golden set before and after:
1. "show me funny cooking videos" (tests affect + topic intersection)
2. "what restaurants have I saved" (tests entity retrieval)
3. "content from @specificcreator" (tests creator filtering)
```
