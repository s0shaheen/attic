---
description: Commit current changes, push, and open a PR. The one-command ship flow.
argument-hint: "short description of what changed"
---

## Steps

1. **Check state**
   ```bash
   git status --porcelain
   git diff --stat
   ```
   If no changes, say "Nothing to ship" and stop.

2. **Determine scope from changed files**
   - `app/services/agent*.py`, `app/services/gemini.py`, `app/services/ontology.py`, `app/services/prompts.py` → scope is `agent`
   - `app/services/entity_resolvers.py` → scope is `entity`
   - `app/routers/` → scope is `api`
   - `src/frontend/` → scope is `frontend`
   - `src/lambdas/`, `app/services/pipeline*` → scope is `pipeline`
   - `workbench/` → scope is `workbench`
   - `scripts/`, `.claude/`, `CLAUDE.md`, `.env*`, `.vscode/` → scope is `dx`
   - `docs/` → scope is `docs`
   - `tests/` → scope is `test`
   - `alembic/` → scope is `db`
   - Multiple unrelated scopes → use the most significant one

3. **Determine commit type**
   - New functionality → `feat`
   - Bug fix → `fix`
   - Refactor (no behavior change) → `refactor`
   - Tests only → `test`
   - Docs only → `docs`
   - Tooling/config → `chore`

4. **Stage and commit**
   ```bash
   git add -A
   git commit -m "{type}({scope}): {user's description}"
   ```

5. **Push**
   ```bash
   git push -u origin HEAD 2>&1
   ```
   If no upstream, this sets it. If upstream exists, this pushes.

6. **Open PR**
   ```bash
   gh pr create --fill --body "## Changes

   {brief summary of what changed and why, 2-3 sentences}

   ## Checklist
   - [ ] Tests pass
   - [ ] Lint clean
   - [ ] Reviewed with /review"
   ```
   If a PR already exists for this branch, skip this step and just print the existing PR URL:
   ```bash
   gh pr view --web 2>/dev/null || gh pr create --fill
   ```

7. **Output** — print the PR URL and nothing else.
