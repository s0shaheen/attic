---
description: Review current changes against Attic project standards. Runs all relevant checks based on which files changed.
argument-hint: "[--staged] [--file path] [--fix]"
---

## Overview

This is a layered, project-specific code review. It reads the diff, determines which layers of the stack are affected, and runs only the relevant checks. Output uses three severity levels:

- **BLOCK** — Must fix before merge. Security holes, broken contracts, data loss risk.
- **WARN** — Should fix. Pattern violations, missing tests, brand non-compliance.
- **NOTE** — Suggestion. Style preferences, potential improvements, future considerations.

## Step 1: Read the diff

```bash
# If --staged flag: review only staged changes
# If --file flag: review only that file
# Default: review all uncommitted changes
git diff --stat
git diff  # or git diff --staged
```

Determine which layers are touched:
- **Backend Python** — any `.py` file under `src/backend/` or `app/`
- **Agent/AI** — `agent.py`, `agent_tools.py`, `gemini.py`, `ontology.py`, `prompts.py`, `entity_resolvers.py`
- **Frontend** — any file under `src/frontend/`
- **Pipeline** — `src/lambdas/`, pipeline-related files
- **Database** — `alembic/`, model files, migration files
- **Workbench** — `workbench/`
- **Config/DX** — `.claude/`, `scripts/`, `.env*`, `.vscode/`, `CLAUDE.md`

## Step 2: Universal checks (always run)

### Security scan
- Grep the diff for potential secret patterns: API keys, tokens, passwords, connection strings with credentials
  ```bash
  git diff | grep -inE '(sk-[a-zA-Z0-9]{20,}|sk_live_|sk_test_|eyJ[a-zA-Z0-9]{30,}|AIza[a-zA-Z0-9]{30,}|ghp_|AKIA[A-Z0-9]{16}|password\s*=\s*["\x27][^"\x27]+["\x27])' || true
  ```
- If ANY match found → **BLOCK**: "Potential secret in committed code"

### File hygiene
- Any file over 500 lines being modified? → **WARN**: "Consider splitting — see #76"
- Any `print()` statements added (not in workbench/)? → **WARN**: "Use logger, not print"
- Any `TODO` or `FIXME` added without a linked issue number? → **NOTE**: "Add issue reference to TODO"
- Any `# type: ignore` added? → **WARN**: "Fix the type error instead of ignoring"

## Step 3: Backend Python checks (if backend files changed)

### Architecture patterns
- **Async I/O**: Any new function doing I/O (HTTP, DB, file) that's NOT `async def`? → **BLOCK**
- **Result objects**: Any service function that `raise`s for business logic instead of returning a Result/Error type? → **BLOCK** (tools must return `AgentToolResult`, services should follow same pattern)
- **Pydantic models**: Any endpoint accepting/returning raw dicts instead of Pydantic models? → **WARN**
- **Dependency injection**: Any endpoint accessing DB/settings directly instead of via `Depends()`? → **WARN**
- **Raw SQL**: Any `db.execute(text(...))` or raw SQL strings? → **BLOCK**: "Use SQLAlchemy ORM exclusively"

### Error handling
- Any bare `except:` or `except Exception:` without logging? → **WARN**
- Any tool function that can raise instead of returning `AgentToolResult(success=False)`? → **BLOCK**
- Any HTTP client call without timeout? → **WARN**: "Add explicit timeout"

### Testing
- New public function added without a corresponding test? Check `tests/` for `test_{function_name}`. → **WARN**
- Test uses real API calls (no mock/patch on external services)? → **BLOCK**: "Mock external services"
- Test naming doesn't follow `test_{function}_{scenario}_{expected}`? → **NOTE**

## Step 4: Agent/AI checks (if agent files changed)

### Ontology integrity
- If `ontology.py` changed: verify `ONTOLOGY_V1` dict structure is intact — every facet has a list, no empty lists, no duplicate labels within a facet
- If new labels added: check they don't overlap semantically with existing labels → **WARN** if ambiguous
- If labels removed: check nothing references them in `prompts.py` or test fixtures → **BLOCK** if broken references

### Tool contract
- Every tool function must have signature `async def tool_name(db, settings|user_id, ...) -> AgentToolResult`
- Every tool must have a docstring explaining when the agent should use it
- Every tool must cache results to DB before returning (check for `db.flush()` or equivalent)
- If a tool's parameters changed: check if the tool definition in the agent's system prompt / tool schema matches → **BLOCK** if mismatch

### Gemini client
- If prompt templates changed: verify JSON mode is still requested (`responseMimeType: "application/json"`)
- If temperature changed from 0.2: → **WARN**: "Low temperature is intentional for classification consistency"
- If model name changed: → **WARN**: "Verify pricing and rate limits for new model"

### System prompt (prompts.py)
- If query plan templates changed: are all 5 types still covered? (entity retrieval, creator aggregation, simple filter, interpretive/vibe, ambiguous/broad)
- If tool descriptions changed in the prompt: do they match the actual tool parameter schemas?
- Is the ontology still included via `format_ontology_for_prompt()`?

## Step 5: Frontend checks (if frontend files changed)

### Brand compliance (from docs/BRAND.md)

**Colors — scan every color value in the diff:**
- Hardcoded hex color (not a CSS variable)? → **BLOCK**: "Use design token CSS variable"
- Cinnamon color (`#A06840`, `#BC8058`, `#7E5030`, or rgba with 160,104,64) used in:
  - Chat components → **BLOCK**: "Cinnamon not allowed in chat UI"
  - Entity cards → **BLOCK**: "Cinnamon not allowed in entity cards"
  - Navigation → **BLOCK**: "Cinnamon not allowed in nav"
  - Everyday chips/tags → **BLOCK**: "Cinnamon not allowed in product chips"
  - Collections, settings, upload → **BLOCK**
  - Landing page, CTAs, badges, onboarding, focus rings → OK

**Typography — scan font usage:**
- `font-display` or `Crimson Pro` class used outside of: wordmark, landing hero, reveal stats, marketing headlines → **BLOCK**
- Font weight other than 400 or 500 on DM Sans → **BLOCK**: "DM Sans uses only 400 (regular) and 500 (medium)"
- `text-transform: uppercase` on anything other than single-word labels → **WARN**
- Missing `font-sans` class on product UI text element → **WARN**

**Component patterns:**
- Box shadow used on anything other than modal/popover → **WARN**: "Use borders, not shadows"
- New component without design token references → **WARN**: "Check design-tokens.ts first"

### React patterns
- Component with required props but no default values → **WARN**
- `useEffect` with missing dependency array → **BLOCK**
- State management in a server component → **BLOCK**
- Missing `"use client"` directive on component using hooks → **BLOCK**

### Accessibility
- Interactive element without `aria-label` or visible text → **WARN**
- Image without `alt` text → **WARN**
- Color contrast: Stone (#9C9890) text on Parchment (#F8F7F4) is 3.2:1 — only valid for large text (≥18px). On smaller text → **WARN**

## Step 6: Database checks (if migration or model files changed)

- New table without RLS policy? → **BLOCK**
- New user-facing column without index? → **NOTE**: "Consider indexing if used in queries"
- Migration not reversible (no `downgrade` function)? → **WARN**
- Column allows NULL but code doesn't handle None? → **WARN**
- New JSONB column without GIN index? → **NOTE**: "Add if you'll query inside the JSON"

## Step 7: Output

Format as:

```
## Review: {branch name}

Files changed: {count}
Layers touched: {backend, agent, frontend, etc.}

### BLOCK ({count})
1. **[security]** src/backend/app/config.py:42 — Potential API key in committed code
   Fix: Move to .env.master, reference via Settings class

### WARN ({count})  
1. **[testing]** src/backend/app/services/new_tool.py — New public function `analyze_trends` has no test
   Fix: Add test_analyze_trends_* in tests/unit/test_agent_tools.py

### NOTE ({count})
1. **[style]** src/frontend/src/components/ChatMessage.tsx:15 — Consider using Stone color token for muted text
   
---
Verdict: {SHIP IT | NEEDS WORK | BLOCK}
```

If `--fix` flag is provided: for any issue that has a clear automated fix (adding missing imports, fixing lint errors, adding `async`), apply the fix directly and note "Auto-fixed" next to the finding.
