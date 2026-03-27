---
description: "Attic-specific ship: stage, commit (conventional), run tests, push, open PR with Closes #N. Use /ship for gstack's full workflow instead."
argument-hint: "short description of what changed"
---

## Step 0: Detect base branch

1. Check if a PR already exists:
   `gh pr view --json baseRefName -q .baseRefName 2>/dev/null`
   If this succeeds, use the returned branch name.

2. If no PR exists, detect default branch:
   `gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null`

3. Fallback: `main`.

Use this as `<base>` in all subsequent steps.

## Step 1: Pre-flight

```bash
git status --porcelain
git diff --stat
git diff <base>...HEAD --stat
git log <base>..HEAD --oneline
```

If no changes (status clean AND no commits ahead of base), say "Nothing to land" and stop.

If on the base branch, say "You're on the base branch. Land from a feature branch." and stop.

## Step 2: Merge base branch

Ensure the feature branch is up to date so tests run against merged state:

```bash
git fetch origin <base> && git merge origin/<base> --no-edit
```

If merge conflicts, **stop** and show them.
If already up to date, continue silently.

## Step 3: Run tests

Run backend and frontend checks in parallel:

```bash
cd src/backend && ../../.venv/bin/pytest tests/ -v --tb=short 2>&1 &
cd src/frontend && npm run typecheck 2>&1 &
wait
```

**If tests fail, classify:**
- **In-branch failure** (test file or code it tests was changed on this branch): **stop**. Show failures.
- **Pre-existing failure** (unrelated to branch changes): note it and continue. Mention in PR body.

## Step 4: Stage and commit

### Determine scope from changed files

- `app/services/agent*.py`, `app/services/gemini.py`, `app/services/ontology.py`, `app/services/prompts.py` → `agent`
- `app/services/entity_resolvers.py` → `entity`
- `app/routers/` → `api`
- `src/frontend/` → `frontend`
- `src/lambdas/`, `app/services/pipeline*` → `pipeline`
- `workbench/` → `workbench`
- `scripts/`, `.claude/`, `CLAUDE.md`, `.env*`, `.vscode/` → `dx`
- `docs/` → `docs`
- `tests/` → `test`
- `alembic/` → `db`
- Multiple unrelated scopes → use the most significant one

### Determine commit type

- New functionality → `feat`
- Bug fix → `fix`
- Refactor (no behavior change) → `refactor`
- Tests only → `test`
- Docs only → `docs`
- Tooling/config → `chore`

### Commit

```bash
git add -A
git commit -m "{type}({scope}): {user's description}"
```

## Step 5: Lint check

```bash
cd src/backend && ../../.venv/bin/ruff check . 2>&1
```

If lint fails on files you changed, fix and amend the commit. If pre-existing, note and continue.

## Step 6: Push

```bash
git push -u origin HEAD 2>&1
```

## Step 7: Open PR

### Find the linked issue

Check the branch name for an issue number (e.g., `s0shaheen/issue-42-foo` → `#42`).
If found, include `Closes #N` in the PR body. This is **mandatory** per project rules.
If no issue number in branch name, warn: "No issue linked. Consider creating one with /issue first."

### Create or update PR

If a PR already exists for this branch, just push (already done) and print the existing PR URL:
```bash
gh pr view --web
```

If no PR exists:
```bash
gh pr create --title "{type}({scope}): {user's description}" --body "$(cat <<'EOF'
## Summary

{2-3 sentences: what changed and why}

Closes #N

## Test results

- Backend: {pass/fail summary}
- Frontend typecheck: {pass/fail summary}
{if pre-existing failures were skipped, note them here}

## Checklist
- [ ] Tests pass
- [ ] Lint clean
EOF
)"
```

## Step 8: Output

Print the PR URL and a one-line summary. Nothing else.
