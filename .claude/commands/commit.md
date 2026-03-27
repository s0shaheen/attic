---
description: "Smart commit: analyze changes, decide split strategy, create clean conventional commits, push."
argument-hint: "[description] [--hierarchical]"
---

## Step 1: Analyze all changes

```bash
git status --porcelain
git diff --stat
git diff --staged --stat
```

If no changes, say "Nothing to commit" and stop.

Read the actual diff content to understand what changed:
```bash
git diff
git diff --staged
```

Also check for untracked files that should be included:
```bash
git ls-files --others --exclude-standard
```

## Step 2: Decide commit strategy

Classify every changed file into logical groups by asking: "If someone reverted one of these commits, would the codebase still make sense?"

### Grouping rules

1. **Same feature/fix** — files that implement a single logical change go together
2. **Config/tooling** — `.claude/`, `scripts/`, `.vscode/`, `CLAUDE.md` changes group together
3. **Tests** — test files go with the code they test, NOT in a separate "tests" commit
4. **Docs** — documentation changes can stand alone if unrelated to code changes
5. **Formatting/lint** — auto-format or lint fixes group separately from logic changes
6. **Migrations** — database migrations go with the model changes they support

### Split decision

- **Single commit** if: all changes serve one purpose (a feature, a fix, a refactor)
- **2-3 commits** if: changes span distinct concerns (e.g., a feature + unrelated config cleanup + docs update)
- **Never more than 4 commits** — if you're tempted to split further, the groups are too granular

For each group, determine:
- **Type**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- **Scope**: `agent`, `frontend`, `pipeline`, `api`, `db`, `workbench`, `dx`, `docs`, `test`, `entity`, `env`
  - `app/services/agent*.py`, `gemini.py`, `ontology.py`, `prompts.py` → `agent`
  - `app/services/entity_resolvers.py` → `entity`
  - `app/routers/` → `api`
  - `src/frontend/` → `frontend`
  - `src/lambdas/`, `app/services/pipeline*` → `pipeline`
  - `workbench/` → `workbench`
  - `scripts/`, `.claude/`, `CLAUDE.md`, `.env*`, `.vscode/` → `dx`
  - `docs/` → `docs`
  - `tests/` → `test`
  - `alembic/` → `db`
  - Multiple scopes in one group → use the most significant
- **Message**: concise description of what and why

## Step 3: Present the plan

Show the commit plan before executing:

```
Commit plan:
  1. feat(agent): add genre-based filtering to query_items
     - app/services/agent_tools.py
     - app/services/ontology.py
     - tests/unit/test_agent_tools.py

  2. chore(dx): update CLAUDE.md with new command reference
     - CLAUDE.md
     - .claude/commands/new-command.md
```

If the user provided a description as an argument, use it to inform the commit messages but still apply the split logic. If the description clearly covers everything ("update readme"), use a single commit.

If `--hierarchical` flag is provided, output commit plan as a tree showing file grouping visually. Then proceed without asking.

## Step 4: Execute commits

For each commit group, in dependency order (migrations before model code, code before tests if separated):

```bash
git add <specific files for this group>
git commit -m "{type}({scope}): {message}"
```

Stage files by name — never `git add -A` or `git add .` unless everything belongs in one commit.

## Step 5: Push

```bash
git push -u origin HEAD 2>&1
```

If no upstream exists, this sets it. If push fails due to divergence, show the error and stop — don't force push.

## Step 6: Output

```
Committed:
  abc1234 feat(agent): add genre-based filtering to query_items (3 files)
  def5678 chore(dx): update CLAUDE.md with new command reference (2 files)

Pushed to origin/{branch}
```

If a single commit, just show the one line. Keep output minimal.
