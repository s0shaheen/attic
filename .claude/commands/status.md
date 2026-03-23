---
description: Quick project health check — git state, tests, env, and eval status at a glance.
---

## Run these checks and report results in a compact table.

### Git state
```bash
BRANCH=$(git branch --show-current)
UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "?")
LAST_COMMIT=$(git log -1 --format="%h %s" 2>/dev/null)
OPEN_PRS=$(gh pr list --state open --json number --jq 'length' 2>/dev/null || echo "?")
```

### Backend health
```bash
cd src/backend
TEST_RESULT=$(../../.venv/bin/pytest tests/ -x --tb=no -q 2>&1 | tail -1)
LINT_RESULT=$(../../.venv/bin/ruff check . 2>&1 | tail -1)
cd ../..
```

### Frontend health
```bash
cd src/frontend
TYPE_RESULT=$(npm run typecheck 2>&1 | tail -1)
LINT_FE_RESULT=$(npm run lint 2>&1 | tail -1)
cd ..
```

### Env health
```bash
ENV_RESULT=$(./scripts/check-env.sh 2>&1 | tail -1)
```

### Eval status
```bash
GOLDEN_COUNT=$(python3 -c "import json; print(len(json.load(open('workbench/data/golden-set.json'))))" 2>/dev/null || echo "0")
LATEST_EVAL=$(ls -t workbench/evals/results/eval-*.json 2>/dev/null | head -1)
if [ -n "$LATEST_EVAL" ]; then
    EVAL_DATE=$(python3 -c "import json; print(json.load(open('$LATEST_EVAL')).get('timestamp', 'unknown')[:10])" 2>/dev/null || echo "?")
    EVAL_ACC=$(python3 -c "import json; d=json.load(open('$LATEST_EVAL')); print(f\"{d.get('overall_accuracy', 0):.0%}\")" 2>/dev/null || echo "?")
else
    EVAL_DATE="never"
    EVAL_ACC="—"
fi
```

### Supabase
```bash
SUPA_STATUS=$(supabase status 2>/dev/null | grep -c "API URL" || echo "0")
```

## Output

```
## Project Status

| Area            | Status | Detail                           |
|-----------------|--------|----------------------------------|
| Branch          | —      | {BRANCH}                         |
| Uncommitted     | {✓/⚠}  | {UNCOMMITTED} files              |
| Ahead of main   | —      | {AHEAD} commits                  |
| Last commit     | —      | {LAST_COMMIT}                    |
| Open PRs        | —      | {OPEN_PRS}                       |
| Backend tests   | {✓/✗}  | {TEST_RESULT}                    |
| Backend lint    | {✓/✗}  | {LINT_RESULT}                    |
| Frontend types  | {✓/✗}  | {TYPE_RESULT}                    |
| Frontend lint   | {✓/✗}  | {LINT_FE_RESULT}                 |
| Env vars        | {✓/✗}  | {ENV_RESULT}                     |
| Supabase        | {✓/✗}  | {running/stopped}                |
| Golden set      | —      | {GOLDEN_COUNT} items             |
| Last eval       | —      | {EVAL_DATE} ({EVAL_ACC})         |

{If anything is broken, add a one-line suggestion for each:}
→ Backend tests failing: run `cd src/backend && ../../.venv/bin/pytest tests/ -x --tb=short` to see details
→ Env missing: run `./scripts/setup-env.sh`
→ No golden set: create workbench/data/golden-set.json with hand-labeled test cases
```
