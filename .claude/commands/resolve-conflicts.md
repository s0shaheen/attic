---
description: Rebase current branch on main and resolve any conflicts intelligently
---

## Step 1: Pre-flight

```bash
# Check we're not on main
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ]; then
    echo "Already on main, nothing to rebase"
    exit 0
fi

# Check for uncommitted changes
git status --porcelain
```

If there are uncommitted changes, stash them first:
```bash
git stash push -m "auto-stash before rebase"
```

## Step 2: Fetch and rebase

```bash
git fetch origin main
git rebase origin/main
```

If rebase succeeds with no conflicts → skip to Step 4.

## Step 3: Resolve conflicts

For each conflicted file:

```bash
git diff --name-only --diff-filter=U
```

Read each conflicted file. Apply these resolution strategies based on file type:

### Database migrations (`alembic/versions/`)
**Always prefer main's version.** Migrations must be linear. If the feature branch added a migration, it needs to be re-generated after rebase to have the correct `down_revision`.
- Accept main's version of the migration
- After rebase completes, regenerate the feature branch's migration

### SQLAlchemy models (`app/models/`)
**Merge both — keep all columns/indexes from both sides.** Model changes are usually additive (new columns, new indexes). If truly conflicting (same column modified differently), prefer the feature branch's version and note it.

### Frontend components (`src/frontend/`)
**Prefer feature branch logic, but keep main's design token/style changes.** If main updated component styling to use new tokens, keep those. If the feature branch changed component behavior, keep that.

### Agent/prompt files (`app/services/agent.py`, `prompts.py`, `ontology.py`)
**Prefer feature branch.** These are the files you're actively developing. Main's version is the baseline; your branch is the improvement.

### Test files
**Keep both sets of tests.** Tests are additive. If the same test was modified on both sides, prefer the feature branch's version (it's testing your new code).

### Config files (`CLAUDE.md`, `pyproject.toml`, `package.json`)
**Merge carefully.** These often have structural changes on main (dependency updates) and content changes on the feature branch. Keep both.

For each resolved file:
```bash
git add {file}
```

Continue rebase:
```bash
git rebase --continue
```

If multiple conflict rounds, repeat Step 3 for each.

## Step 4: Verify

Run the test suite for affected areas:

```bash
# Always run
cd src/backend && ../../.venv/bin/pytest tests/ -x --tb=short -q 2>&1 | tail -5

# If frontend files were conflicted
cd src/frontend && npm run typecheck 2>&1 | tail -5
cd src/frontend && npm run lint 2>&1 | tail -5
```

## Step 5: Restore stash (if applicable)

```bash
git stash list | head -1
# If "auto-stash before rebase" exists:
git stash pop
```

## Step 6: Report

```
## Rebase Complete

Branch: {branch} rebased on origin/main
Conflicts resolved: {count}
Files affected: {list}

Resolution summary:
- {file}: {what was done}

Test results:
- Backend: {pass/fail}
- Frontend: {pass/fail}

{If any resolution was ambiguous, flag it: "⚠️ Manual review recommended for {file} — both sides modified the same function"}
```
