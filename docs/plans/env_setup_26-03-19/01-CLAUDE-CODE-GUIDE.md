# Attic Development Environment Setup

## Context for Claude Code

You are setting up the development environment for Attic, a personal content intelligence platform that processes TikTok data exports to classify, organize, and make searchable a user's saved/liked content through an agentic chat interface.

### Why this setup exists

The founder has been building infrastructure (Docker, staging environments, Conductor worktrees) instead of iterating on the core intelligence layer — classification, retrieval, and agent response quality. This setup reorients the entire development workflow around fast feedback loops on AI output quality.

### What's changing

1. **Single Python venv at repo root** (moved from `src/backend/.venv` to `.venv`) — shared by backend, workbench notebooks, and eval scripts
2. **Single `.env.master` file** at repo root → one generation script derives all per-target env files
3. **New `workbench/` directory** with Jupyter notebooks for exploration and Python scripts for automated evals
4. **Custom Claude Code slash commands** replacing Conductor's auto-review, auto-conflict-resolve, and PR creation features
5. **Working database seed script** so full-stack testing has real data from day one
6. **Brand design tokens** centralized from BRAND.md so the planned UI refresh is a theme swap
7. **Production deployment configs** (Vercel + Render) checked in so going live is a deploy command
8. **VS Code as primary IDE** with Claude Code terminals — no Conductor

### Architecture reference

```
Agent: Claude Haiku 4.5 orchestrator (~50-line manual SDK tool loop)
Classification: Gemini Flash via app/services/gemini.py (classify + analyze_visual)
Ontology: 8 facets, two-tier labels (tier-1 validated, tier-2 free-form) in app/services/ontology.py
Tools: query_items, classify, analyze_visual, resolve_entity in app/services/agent_tools.py
Embeddings: OpenAI text-embedding-3-small (1536-dim, pgvector)
Pipeline: SQS + Lambda → parse_export → apify_enrich → subtitle_fetch → embed
Frontend: Next.js 14 App Router, Supabase Auth (Google OAuth), SSE chat
Database: Supabase PostgreSQL + pgvector
```

### Key function signatures (verified from codebase)

```python
# app/services/gemini.py
async def classify(
    api_key: str,
    caption: str | None,
    subtitle: str | None,
    hashtags: list[str] | None,
    creator_username: str | None,
    music_name: str | None,
) -> ClassifyResult:  # ClassifyResult(success, raw_classification, error)

async def analyze_visual(
    api_key: str,
    image_url: str,
    caption: str | None = None,
) -> VisualAnalysisResult:  # VisualAnalysisResult(success, description, objects, text_detected, grounding_sources, error)

# app/services/ontology.py
def validate_classification(raw: dict[str, Any]) -> ClassificationResult:
    # ClassificationResult(tier1: dict, tier2: dict, confidence: dict)

def format_ontology_for_prompt() -> str:

# app/services/agent_tools.py
async def query_items(db, user_id, *, search_text=None, hashtag=None, creator=None, topic=None, affect=None, genre=None, media_type=None, limit=20, offset=0) -> AgentToolResult
async def classify(db, settings, media_event_id, user_id) -> AgentToolResult
async def analyze_visual(db, settings, media_event_id, user_id) -> AgentToolResult
async def resolve_entity(db, settings, entity_type, query, user_id) -> AgentToolResult
```

### Execution instructions

Execute phases in order. Each phase should be committed separately with a conventional commit message. Run verification checks at the end of each phase before moving to the next.

---

## Phase 1: Environment Scaffolding

**Goal:** One source of truth for secrets, one script to propagate them, never think about env files again.

### 1.1 — Create `.env.master.example`

Create at repo root. This IS committed to git — it's the template.

```bash
# .env.master.example — Copy to .env.master and fill in real values
# See docs/setup/environment.md for where to find each value

# --- AI / Classification ---
GOOGLE_API_KEY=AIza_PLACEHOLDER
OPENAI_API_KEY=sk-PLACEHOLDER
ANTHROPIC_API_KEY=sk-ant-PLACEHOLDER
APIFY_API_TOKEN=apify_api_PLACEHOLDER

# --- Database ---
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=<from supabase start output>
SUPABASE_ANON_KEY=<from supabase start output>

# --- AWS (LocalStack) ---
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566

# --- Payments ---
STRIPE_SECRET_KEY=sk_test_PLACEHOLDER
STRIPE_WEBHOOK_SECRET=whsec_PLACEHOLDER

# --- Notifications ---
RESEND_API_KEY=re_PLACEHOLDER

# --- Observability (optional) ---
SENTRY_DSN=
POSTHOG_API_KEY=

# --- App ---
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

### 1.2 — Create `scripts/setup-env.sh`

Generates all derived env files from `.env.master`. Must handle:

- Copy `.env.master` to `src/backend/.env`, append `BACKEND_PORT=8000` and `CORS_ORIGINS=http://localhost:3000`
- Source `.env.master` and generate `src/frontend/.env.local` with the `NEXT_PUBLIC_` prefixed vars
- Extract only AI keys (GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, APIFY_API_TOKEN) into `workbench/.env`
- Must fail fast with clear error if `.env.master` doesn't exist, pointing to `.env.master.example`
- Make executable

### 1.3 — Create `scripts/check-env.sh`

Validates all required env vars are present and non-empty in their respective files. Check:
- Backend: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, APIFY_API_TOKEN
- Frontend: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
- Workbench: GOOGLE_API_KEY, OPENAI_API_KEY

Report each missing var with its file, exit 1 if any missing. Make executable.

### 1.4 — Update `.gitignore`

Add these entries if not present:

```
.env.master
workbench/.env
workbench/data/my-export/
workbench/evals/results/
*.ipynb_checkpoints/
```

### 1.5 — Verify

- Run `./scripts/setup-env.sh` (will fail if no `.env.master` — that's correct, user creates it manually)
- Confirm `.env.master.example` is NOT in `.gitignore`
- Commit: `feat(env): add single-source env management with .env.master`

---

## Phase 2: Custom Slash Commands

**Goal:** Replace Conductor's auto-PR, auto-conflict-resolve, and review features with project-specific Claude Code commands.

All commands go in `.claude/commands/`. Each is a markdown file.

### 2.1 — Create `.claude/commands/ship.md`

```markdown
---
description: Commit, push, and open a PR for current changes
argument-hint: "description of what changed"
---

1. Run `git status` to see what changed
2. Stage all changes with `git add -A`
3. Create a conventional commit message based on the description provided:
   - Use the format from CLAUDE.md: `feat(scope): description`, `fix(scope): description`, etc.
   - Scope should be one of: agent, ontology, frontend, pipeline, env, workbench, docs
4. Push to current branch. If no upstream exists, set it with `git push -u origin HEAD`
5. Open a PR using `gh pr create --fill` (uses commit message as title/body)
6. Print the PR URL
```

### 2.2 — Create `.claude/commands/resolve-conflicts.md`

```markdown
---
description: Rebase current branch on main and resolve conflicts
---

1. Run `git fetch origin main`
2. Run `git rebase origin/main`
3. If conflicts exist:
   a. For each conflicted file, read both sides
   b. Resolve favoring the feature branch's intent while keeping main's structural changes
   c. For frontend components: prefer the feature branch's component logic, but keep main's design token usage
   d. For database migrations: always prefer main's version, then re-apply feature changes on top
   e. `git add` resolved files, `git rebase --continue`
4. After rebase completes, run the relevant test suite:
   - If Python files changed: `cd src/backend && ../../.venv/bin/pytest tests/ -x --tb=short`
   - If TypeScript files changed: `cd src/frontend && npm run typecheck && npm run lint`
5. Report what was resolved and test results
```

### 2.3 — Create `.claude/commands/review.md`

```markdown
---
description: Review current changes against Attic project standards
argument-hint: "[--diff-only]"
---

Review the current `git diff --staged` (or `git diff` if nothing staged) against these criteria.

### Code Quality
- Python: type hints on all functions, async for I/O, Pydantic for schemas
- TypeScript: strict mode, Zod for runtime validation
- No raw SQL — SQLAlchemy ORM exclusively
- Result objects for service returns, never exceptions for business logic
- Dependency injection via FastAPI Depends()

### Security
- No secrets in committed files (grep for API key patterns)
- RLS policies on user-owned tables
- Input validation on all endpoints
- PII-safe logging — no user content in log messages

### Agent Layer
- Tools return AgentToolResult (never raise)
- All tool results cached to DB inline before returning to agent loop
- Ontology labels validated through validate_classification()
- Gemini calls use the cached ontology prompt (_get_ontology_prompt)

### Frontend (from BRAND.md)
- Colors must use CSS custom property tokens, never hardcoded hex
- Cinnamon accent ONLY in: landing hero, CTAs, reveal stats, badges, onboarding, focus rings
- Cinnamon NEVER in: chat bubbles, entity cards, nav, everyday chips, collections, settings, upload
- DM Sans for all product UI. Crimson Pro ONLY for: wordmark, landing headlines, reveal stat numbers
- Borders over shadows for surface definition (shadows only on modals/popovers)

### Testing
- Public functions have tests
- External services mocked
- Test naming: test_{function}_{scenario}_{expected}

### Output
List issues by severity: MUST FIX / SHOULD FIX / SUGGESTION
For each: file, line range, issue, fix
End with: SHIP IT / NEEDS WORK / BLOCK
```

### 2.4 — Create `.claude/commands/review-agent.md`

```markdown
---
description: Deep review of agent, classification, or ontology changes
---

Review the current diff focusing on agent intelligence quality.

### Prompt Changes
- Are ontology instructions clear and unambiguous for Gemini?
- Any contradictions with existing tool definitions?
- Will this change affect classification on content types OTHER than the target? (unintended regression)
- Is the prompt structure optimized for Gemini's response format (JSON mode)?

### Tool Definition Changes
- Do parameter descriptions help Claude Haiku decide WHEN to use each tool?
- Are there missing parameters the agent might need for a query?
- Does the tool return enough data for the agent to formulate a good response?

### Ontology Changes
- Are new labels orthogonal to existing ones?
- Could they be confused with similar labels? (e.g., "wholesome" vs "inspiring")
- Is the tier-1/tier-2 boundary correct? (tier-1 = fixed vocabulary, tier-2 = free-form)
- Does validate_classification handle the new labels?

### Retrieval Changes
- Does query construction handle synonyms/related terms? (user says "cooking" but topic might be "food" and genre might be "recipe")
- Are filters too narrow (missing results) or too broad (noise)?
- For embedding search: is the similarity threshold appropriate?

For each issue, explain the likely USER-FACING impact — what query would break, what would the user see?
```

### 2.5 — Create `.claude/commands/review-ui.md`

```markdown
---
description: Review frontend changes against BRAND.md design system
---

Review the current diff for BRAND.md compliance.

Reference: docs/BRAND.md (read this file first if not already in context)

### Color Compliance
Check every color value in the diff:
- Must be a CSS custom property (--color-*), never a hardcoded hex
- Cinnamon variants: verify the component is in the "WHERE CINNAMON DOES APPEAR" list
- If Cinnamon is used in chat, entity cards, nav, chips, collections, settings, or upload → BLOCK

### Typography Compliance
- All product UI text must use DM Sans (font-sans)
- Crimson Pro (font-display) only in: wordmark, landing page hero, reveal stat numbers, marketing headlines
- Check font weights: DM Sans allows only 400 and 500. Crimson Pro allows 400, 500, 600.
- Check sizes match the type scale in BRAND.md

### Component Patterns
- Chat bubbles: user=Soft Black bg + Parchment text, assistant=White bg + Ink text + Border stroke
- Entity cards: White bg, Border stroke, 12px radius, 44px square thumbnail
- Chips: Subtle bg, Stone text, pill shape. NO Cinnamon except marketing badges
- Thumbnail grids: 3-4 columns, 3px gap, 6px outer radius, no individual borders
- Surfaces: 0.5px warm gray borders, NOT shadows (shadows only on modals/popovers)

### Token Usage
- If a value doesn't exist in design-tokens.ts, flag it
- New values should be added to tokens first, then consumed via CSS custom properties

Output: PASS / FAIL with specific violations
```

### 2.6 — Commit

`feat(commands): add project-specific slash commands for ship, review, resolve-conflicts`

---

## Phase 3: Workbench — Jupyter Notebooks

**Goal:** Create the exploration environment. Notebooks are for interactive investigation, visualization, and developing intuition about data and model behavior.

### 3.1 — Create directory structure

```
workbench/
  README.md
  .env                          ← (gitignored, generated by setup-env.sh)
  notebooks/
    01_explore_export.ipynb
    02_classification_lab.ipynb
    03_agent_traces.ipynb
    04_retrieval_quality.ipynb
    05_embedding_analysis.ipynb
  scripts/
    classify_batch.py
    run_evals.py
    generate_test_data.py
    seed_db.py
  data/
    my-export/                   ← (gitignored, user's real TikTok export)
    golden-set.json
    sample-videos.json
  evals/
    results/                     ← (gitignored, timestamped eval outputs)
    prompts/                     ← (committed, prompt versions under test)
```

Create `golden-set.json` and `sample-videos.json` as empty arrays `[]`.
Create `.gitkeep` files in `evals/results/`, `evals/prompts/`, `data/my-export/`.

### 3.2 — Create `workbench/README.md`

Requirements:
- Explain the workbench purpose: fast iteration on Attic's intelligence layer without running the full stack
- List each notebook with a one-line description
- List each script with usage examples
- Document the data directory structure and what goes where
- Note that `.env` is auto-generated by `scripts/setup-env.sh`
- Note that the `attic` Jupyter kernel must be installed (see setup overview)
- Keep under 80 lines

### 3.3 — Create `workbench/notebooks/01_explore_export.ipynb`

Requirements for notebook content (create as a valid .ipynb with markdown and code cells):

**Purpose:** Load and explore a real TikTok data export to understand the raw data before processing.

**Cells to include:**
1. Markdown: title and purpose
2. Code: imports, sys.path setup to find `src/backend`, load `workbench/.env` with dotenv
3. Code: load a TikTok export JSON file from `workbench/data/my-export/` (the export contains `FavoriteVideos` and/or `LikedVideos` lists with `Date` and `Link` fields — reference the existing parser at `src/backend/app/services/` or `src/lambdas/` for the exact format)
4. Code: basic stats — total count, date range, frequency distribution by month
5. Code: show a sample of 10 items
6. Markdown: "Next steps" — notes on what to feed into classification

**The notebook should work with just Python stdlib + pandas + matplotlib (already in the venv from the manual setup step).**

### 3.4 — Create `workbench/notebooks/02_classification_lab.ipynb`

**Purpose:** Run classification on individual videos and small batches, inspect all 8 facets, compare prompt versions.

**Cells to include:**
1. Markdown: title, purpose
2. Code: imports — `sys.path` setup, dotenv, import `gemini.classify`, `ontology.validate_classification`, `ontology.format_ontology_for_prompt`, `ontology.ONTOLOGY_V1`, `ontology.FACET_NAMES`
3. Code: helper function `classify_video(caption, subtitle, hashtags, creator, music)` that calls `gemini.classify()` with the `GOOGLE_API_KEY` from env, runs `validate_classification()`, and returns a dict with `raw`, `tier1`, `tier2`, `confidence`
4. Code: classify a single video with example metadata, print the full output (all facets, tiers, confidence)
5. Code: classify a batch from `sample-videos.json`, collect results into a pandas DataFrame
6. Code: per-facet confidence distribution (histogram or box plot using matplotlib/seaborn)
7. Code: confusion analysis — compare against expected labels from `golden-set.json` if available, show per-facet accuracy
8. Markdown: section header "Prompt comparison"
9. Code: side-by-side comparison — run the same video through two different prompt versions (have the user save alternative prompt functions in `workbench/evals/prompts/` as Python files that the notebook imports)

**Critical: the `classify` call from `app.services.gemini` makes a real Gemini API call. The notebook should include a cost estimate note (Gemini Flash is cheap but not free).**

### 3.5 — Create `workbench/notebooks/03_agent_traces.ipynb`

**Purpose:** Send queries to the agent loop and see the full decision trace — every tool call, arguments, results, and final response.

**Requirements:**
- This notebook needs to invoke the agent loop. The agent loop in `app/services/agent.py` is coupled to `AsyncSession` (SQLAlchemy) and `Settings` (FastAPI config).
- The notebook should create a **standalone lightweight version** of the agent loop that:
  - Uses the same system prompt and tool definitions from `agent.py`
  - Replaces DB-backed tools with in-memory adapters (load pre-classified videos from `sample-videos.json`)
  - Calls the Anthropic API directly using `ANTHROPIC_API_KEY` from workbench `.env`
  - Captures and displays each step: system prompt sent, user query, each tool_use block (name + input), each tool_result, and the final assistant response
- Read `app/services/agent.py` to extract the system prompt template and tool definitions. Adapt them — don't import directly if the coupling is too tight.
- Display traces in a structured, readable format. Consider a simple HTML display in the notebook using `IPython.display.HTML` for color-coded tool calls.
- Include cells for:
  1. Setup and imports
  2. Load test data
  3. Define the standalone agent loop with trace capture
  4. Run a single query and display the full trace
  5. Compare: run the same query after modifying the system prompt, display both traces

### 3.6 — Create `workbench/notebooks/04_retrieval_quality.ipynb`

**Purpose:** Evaluate whether `query_items`-style queries return the right videos, independent of the agent.

**Requirements:**
- Load pre-classified videos from `sample-videos.json` into a pandas DataFrame
- Implement the same filtering logic as `query_items` in `app/services/agent_tools.py` (text search, hashtag, creator, topic, affect, genre, media_type) — but in-memory against the DataFrame
- For embedding-based search: load or compute embeddings for the sample set, implement cosine similarity search
- Define test queries with expected results (relevance judgments). Format:
  ```python
  test_queries = [
      {"query": "funny cooking videos", "filters": {"topic": "food", "affect": "funny"}, "expected_ids": ["id1", "id2", ...]},
      {"query": "that pasta place in Brooklyn", "type": "entity_search", "expected_entity": "restaurant"},
  ]
  ```
- For each test query: run the filter, compute precision/recall against expected results
- Visualize: show which expected items were returned and which were missed, with their metadata

### 3.7 — Create `workbench/notebooks/05_embedding_analysis.ipynb`

**Purpose:** Sanity-check that the embedding space makes sense — similar videos should be close, dissimilar should be far.

**Requirements:**
- Load videos with embeddings (either from the database if Supabase is running, or from a cached JSON file)
- Compute pairwise cosine similarity matrix for a subset (50-100 videos)
- Visualize with a heatmap (seaborn)
- Run t-SNE or UMAP dimensionality reduction, plot the 2D projection colored by topic or affect label
- Identify clusters and outliers
- Include a cell to compute embeddings for new text using the same model (OpenAI text-embedding-3-small) for ad-hoc similarity checks

### 3.8 — Commit

`feat(workbench): add Jupyter notebooks for classification, agent traces, retrieval, and embedding analysis`

---

## Phase 4: Workbench — Automated Scripts

**Goal:** CI-runnable eval scripts that produce reproducible accuracy reports.

### 4.1 — Create `workbench/scripts/classify_batch.py`

This script classifies a batch of videos and outputs structured results. It's the engine behind both the eval script and the notebooks.

Use this exact implementation:

```python
#!/usr/bin/env python
"""Classify a batch of videos and output structured results.

Usage:
    python workbench/scripts/classify_batch.py workbench/data/sample-videos.json
    python workbench/scripts/classify_batch.py workbench/data/sample-videos.json --output results.json
    python workbench/scripts/classify_batch.py workbench/data/sample-videos.json --limit 10
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os
from app.services.gemini import classify as gemini_classify
from app.services.ontology import validate_classification


async def classify_one(item: dict, api_key: str) -> dict:
    """Classify a single item and return structured result."""
    start = time.time()
    try:
        result = await gemini_classify(
            api_key=api_key,
            caption=item.get("caption"),
            subtitle=item.get("subtitle"),
            hashtags=item.get("hashtags"),
            creator_username=item.get("creator"),
            music_name=item.get("music"),
        )
        elapsed = time.time() - start

        if not result.success:
            return {"id": item.get("id", "unknown"), "success": False, "error": result.error, "elapsed": elapsed}

        validated = validate_classification(result.raw_classification or {})
        return {
            "id": item.get("id", "unknown"),
            "success": True,
            "raw": result.raw_classification,
            "tier1": validated.tier1,
            "tier2": validated.tier2,
            "confidence": validated.confidence,
            "elapsed": elapsed,
        }
    except Exception as e:
        return {"id": item.get("id", "unknown"), "success": False, "error": str(e), "elapsed": time.time() - start}


async def main():
    if len(sys.argv) < 2:
        print("Usage: python classify_batch.py <input.json> [--output results.json] [--limit N]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    items = json.loads(input_path.read_text())

    output_path = None
    limit = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = Path(sys.argv[i + 1])
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if limit:
        items = items[:limit]

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in workbench/.env")
        sys.exit(1)

    print(f"Classifying {len(items)} items...")
    results = []
    for i, item in enumerate(items):
        result = await classify_one(item, api_key)
        status = "OK" if result["success"] else f"FAIL: {result.get('error', 'unknown')}"
        print(f"  [{i+1}/{len(items)}] {item.get('id', 'unknown')[:20]:20s} {status} ({result['elapsed']:.1f}s)")
        results.append(result)

    successes = sum(1 for r in results if r["success"])
    print(f"\nDone: {successes}/{len(results)} succeeded")

    if output_path:
        output_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"Results saved to {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 — Create `workbench/scripts/run_evals.py`

Requirements:
- Load `workbench/data/golden-set.json`. Each item has the shape:
  ```json
  {
    "id": "unique-id",
    "caption": "...",
    "subtitle": "...",
    "hashtags": ["..."],
    "creator": "...",
    "music": "...",
    "expected": { "affect": "funny", "topic": "food", "genre": "recipe" },
    "notes": "Why this is correct"
  }
  ```
- Classify each item using `classify_batch.classify_one()`
- Compare `tier1[facet]` against `expected[facet]` for each facet present in `expected`
- Report per-facet accuracy (correct / total) and overall accuracy
- Support `--facet <name>` to evaluate a single facet
- Support `--save` to write timestamped JSON to `workbench/evals/results/eval-YYYYMMDD-HHMMSS.json`
- Support `--verbose` to print each item's predicted vs expected with PASS/FAIL
- Handle Gemini API errors gracefully (log, count as failure, don't crash)
- Print a summary table at the end showing per-facet accuracy
- Exit code 0 if overall accuracy >= 60%, exit code 1 otherwise (this becomes a CI quality gate later)

### 4.3 — Create `workbench/scripts/generate_test_data.py`

Requirements:
- Generate synthetic test cases for classification evaluation
- Input: a "scenario" description (e.g., "cooking videos with emoji-only captions", "edit TikToks with song lyrics")
- Uses the Anthropic API (ANTHROPIC_API_KEY from workbench/.env) to generate realistic-looking TikTok metadata:
  - caption_text, hashtags, creator_username, music_name, subtitle_text
  - And the expected correct classification (affect, topic, genre, etc.)
- Output: appends generated items to a specified JSON file (default: `sample-videos.json`)
- Include a `--count` parameter for how many to generate (default 5)
- Each generated item gets a UUID id
- The Anthropic prompt should include the full ontology (from `format_ontology_for_prompt()`) so generated expected labels are valid tier-1 values

### 4.4 — Commit

`feat(workbench): add batch classification, eval runner, and test data generator scripts`

---

## Phase 5: Database Seeding

**Goal:** One command populates the local database with realistic data so the full-stack UI shows real content.

### 5.1 — Replace `scripts/seed-db.sh` placeholder with `workbench/scripts/seed_db.py`

Requirements:
- Python script (not bash) — needs to work with SQLAlchemy models and generate realistic data
- Requires Supabase to be running locally (`supabase start`)
- Creates:
  1. **Test user** in `auth.users` via Supabase service key API (use the REST API at `SUPABASE_URL/auth/v1/admin/users` with service key). Email: `test@attic.to`, password: `testpassword123`. This bypasses Google OAuth for local development.
  2. **Sample upload** linked to the test user, status `completed`
  3. **50-100 media_events** with diverse, realistic data:
     - Mix of media types: ~70% video, ~20% image, ~10% slideshow
     - Mix of processing states: ~80% complete (with cached_classifications), ~10% pending, ~10% failed
     - For complete items: realistic cached_classifications with tier-1 labels spanning all 8 facets, tier-2 micro-labels, and confidence scores
     - Diverse topic distribution across the ontology (food, fashion, comedy, education, etc.)
     - Realistic metadata: caption_text, hashtags, creator_username, music_name, play_count, like_count, thumbnail_url (can use placeholder URLs)
     - Some items should have embedding_vector (1536-dim, can be random normalized vectors for testing — real embeddings come from the pipeline)
  4. **UploadPipelineRun** linked to the upload, status `completed`
- Uses the database connection from `.env.master` (or `src/backend/.env`)
- Idempotent: running twice doesn't create duplicates (use upserts or check-before-insert)
- Reference the MediaEvent model at `src/backend/app/models/media_event.py` for exact column names and types
- Reference `ONTOLOGY_V1` in `src/backend/app/services/ontology.py` for valid tier-1 labels
- Print summary of what was created

### 5.2 — Update `scripts/seed-db.sh`

Replace the placeholder content with a script that:
1. Checks Supabase is running
2. Runs `python workbench/scripts/seed_db.py`
3. Reports success/failure

### 5.3 — Commit

`feat(seed): implement database seeding with test user and diverse media events`

---

## Phase 6: Brand Design Tokens

**Goal:** Centralize the BRAND.md color palette and typography as code so the planned UI refresh is a theme swap.

### 6.1 — Create `src/frontend/src/lib/design-tokens.ts`

Requirements:
- Export all color tokens from BRAND.md as a TypeScript object
- Structure:

```typescript
export const tokens = {
  colors: {
    parchment: "#F8F7F4",
    white: "#FFFFFF",
    ink: "#1C1B18",
    softBlack: "#2C2926",
    stone: "#9C9890",
    border: "#E6E4DE",
    borderHover: "#D0CCC4",
    subtle: "#F0EEE8",
    cinnamon: {
      default: "#A06840",
      light: "#BC8058",
      dark: "#7E5030",
      subtle: "rgba(160, 104, 64, 0.07)",
      border: "rgba(160, 104, 64, 0.15)",
    },
    semantic: {
      error: { color: "#B54040", bg: "#FDF2F2", border: "#E8BCBC", text: "#8C2D2D" },
      success: { color: "#3D7A4A", bg: "#F2F8F3", border: "#BCE8C4", text: "#2E5E38" },
      warning: { color: "#A07830", bg: "#FDF8F0", border: "#E8D8B8", text: "#7A5C24" },
      info: { color: "#4A6A8A", bg: "#F0F4F8", border: "#B8CCE0", text: "#3A5470" },
    },
  },
  typography: {
    fonts: {
      display: "var(--font-display)", // Crimson Pro
      sans: "var(--font-sans)",       // DM Sans
      mono: "var(--font-mono)",       // DM Mono
    },
    scale: {
      xs: "12px",
      sm: "13px",
      base: "14px",
      md: "15px",
      lg: "17px",
      xl: "20px",
      "2xl": "24px",
      "3xl": "30px",
      "4xl": "48px",
    },
  },
  spacing: {
    radius: {
      sm: "6px",
      md: "8px",
      lg: "12px",
      full: "9999px",
    },
  },
} as const;
```

### 6.2 — Update `src/frontend/src/app/globals.css`

Requirements:
- Add CSS custom properties generated from the token values
- These should be in a `:root` block
- All component styles should reference `var(--color-*)`, `var(--font-*)`, etc.
- Include the font loading setup from BRAND.md (Crimson Pro, DM Sans, DM Mono via `next/font`)
- DO NOT break existing styles — add the token custom properties alongside whatever exists, and gradually components can migrate to tokens

### 6.3 — Update `src/frontend/src/app/layout.tsx`

Requirements:
- Set up font loading for all three fonts (Crimson Pro, DM Sans, DM Mono) using `next/font/google` as specified in BRAND.md
- Apply font CSS variables to the `<body>` element
- If fonts are already configured differently, update to match BRAND.md spec

### 6.4 — Commit

`feat(design): add centralized design tokens from BRAND.md`

---

## Phase 7: VS Code Configuration

### 7.1 — Create/update `.vscode/settings.json`

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.envFile": "${workspaceFolder}/src/backend/.env",
  "jupyter.kernels.filter": [
    { "path": "${workspaceFolder}/.venv/bin/python", "type": "pythonEnvironment" }
  ],
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/.next": true,
    "**/node_modules": true,
    "**/.ipynb_checkpoints": true
  },
  "search.exclude": {
    "**/node_modules": true,
    "**/.next": true,
    "**/workbench/evals/results": true,
    "**/workbench/data/my-export": true
  }
}
```

### 7.2 — Create `.vscode/launch.json`

Debugger configs for stepping through the agent loop and backend:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend (FastAPI)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--port", "8000", "--reload"],
      "cwd": "${workspaceFolder}/src/backend",
      "envFile": "${workspaceFolder}/src/backend/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Classify One (Workbench)",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/workbench/scripts/classify_batch.py",
      "args": ["${workspaceFolder}/workbench/data/sample-videos.json", "--limit", "1"],
      "envFile": "${workspaceFolder}/workbench/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Run Evals",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/workbench/scripts/run_evals.py",
      "args": ["--verbose"],
      "envFile": "${workspaceFolder}/workbench/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

### 7.3 — Commit

`feat(vscode): add workspace settings, debugger configs, and Jupyter kernel config`

---

## Phase 8: Production Deployment Configs

**Goal:** Configs checked into the repo so going live requires only account setup and a deploy command — not a week of infrastructure work.

### 8.1 — Create `vercel.json`

Requirements:
- Configure for the Next.js frontend at `src/frontend/`
- Set the root directory to `src/frontend`
- Framework preset: Next.js
- Build command: `npm run build`
- Output directory: `.next`
- Environment variables needed: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_ENVIRONMENT`
- Add a comment or README note: "Create a Vercel project, link to this repo, set env vars in Vercel dashboard, deploy"

### 8.2 — Create `render.yaml`

Requirements:
- Blueprint spec for the FastAPI backend
- Service type: web
- Runtime: Python 3.13
- Build command: `pip install -r src/backend/requirements.txt`
- Start command: `cd src/backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: list all required backend vars (reference `.env.master.example`)
- Health check path: `/health`
- Add a comment: "Create a Render web service, connect to this repo, set env vars in Render dashboard, deploy"

### 8.3 — Create `docs/setup/production.md`

Requirements — brief deployment guide covering:
- DNS: point `attic.to` to Vercel (frontend) and configure API subdomain for Render (backend)
- Supabase: use the production project (not local), configure Google OAuth redirect URIs for production domain
- Environment variables: which ones change between dev and prod (all the SUPABASE_*, STRIPE live keys, real AWS credentials)
- Deployment: `git push` triggers auto-deploy on both Vercel and Render
- Keep under 100 lines. This is a checklist, not a tutorial.

### 8.4 — Commit

`feat(deploy): add Vercel, Render, and production deployment configs`

---

## Phase 9: Update CLAUDE.md

### 9.1 — Add workbench documentation

Under "Key Files", add:
```
- `workbench/notebooks/` — Jupyter notebooks for classification, agent traces, retrieval, embedding analysis
- `workbench/scripts/classify_batch.py` — Batch classification with structured output
- `workbench/scripts/run_evals.py` — Golden set accuracy evaluation
- `workbench/scripts/generate_test_data.py` — Synthetic test case generator
- `workbench/scripts/seed_db.py` — Database seeding for local dev
```

Under commands section (or create one), add:
```
## Custom Commands

- `/ship "description"` — Commit, push, open PR
- `/review` — Full project standards review
- `/review-agent` — Agent/classification/ontology specific review
- `/review-ui` — BRAND.md design system compliance review
- `/resolve-conflicts` — Rebase on main and resolve conflicts
```

Under "Local Development" commands, add:
```
# Workbench (no infrastructure needed — just Python + API keys)
.venv/bin/python workbench/scripts/classify_batch.py workbench/data/sample-videos.json --limit 5
.venv/bin/python workbench/scripts/run_evals.py --verbose --save
.venv/bin/python workbench/scripts/generate_test_data.py "cooking videos with emoji captions" --count 10

# Database seeding (requires Supabase running)
.venv/bin/python workbench/scripts/seed_db.py

# Environment setup
./scripts/setup-env.sh
./scripts/check-env.sh
```

### 9.2 — Add workflow guidance

Add a section to CLAUDE.md:

```
## Development Workflow

Primary environment: VS Code + Claude Code terminals.

### Terminal layout
- Terminal 1: Claude Code (main working session)
- Terminal 2: Shell (scripts, git, quick checks)
- Terminal 3: Servers (only when full-stack testing)

### Iteration loop (most sessions)
1. Open workbench notebook or script
2. Classify / query / analyze
3. Tweak prompts, ontology, or tool definitions
4. Re-run, compare
5. /review or /review-agent on the diff
6. /ship when satisfied

### Full-stack testing (when needed)
1. supabase start
2. ./scripts/dev-start.sh
3. Login: test@attic.to / testpassword123
4. http://localhost:3000

### Design system
All colors and typography are centralized in src/frontend/src/lib/design-tokens.ts.
Reference docs/BRAND.md for usage rules. Use /review-ui to check compliance.
```

### 9.3 — Commit

`docs: update CLAUDE.md with workbench, commands, and workflow guidance`

---

## Phase 10: Final Verification

Run these in order. Every check must pass.

1. `./scripts/setup-env.sh` — generates all env files (requires `.env.master` to exist)
2. `./scripts/check-env.sh` — all required vars present
3. `.venv/bin/python -c "from app.services.ontology import ONTOLOGY_V1; print(f'{len(ONTOLOGY_V1)} facets')"` (run from `src/backend/`) — imports work
4. `.venv/bin/python workbench/scripts/classify_batch.py workbench/data/sample-videos.json --limit 1` — if sample-videos.json has entries (may be empty, which is OK — it'll just report 0 items)
5. `cd src/backend && ../../.venv/bin/pytest tests/ -x --tb=short` — existing tests pass
6. `cd src/frontend && npm run typecheck && npm run lint` — frontend checks pass
7. Verify all 5 slash commands exist in `.claude/commands/`
8. Verify all 5 notebooks exist in `workbench/notebooks/`
9. Verify `design-tokens.ts` exists and exports the token object
10. Verify `vercel.json` and `render.yaml` exist

Report results. If any fail, fix before committing the final verification.

Final commit: `chore: verify dev environment setup complete`
