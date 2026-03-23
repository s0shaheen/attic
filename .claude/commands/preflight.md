---
description: Run all quality checks before committing. The gate that must pass before /ship.
argument-hint: "[--fix] [--skip-tests]"
---

## Purpose

This is the "is my code ready to commit?" check. It runs fast (under 60 seconds for a clean codebase) and catches the common issues that would fail CI. Run this before `/ship`.

If `--fix` is provided, auto-fix what can be fixed (lint, format).
If `--skip-tests` is provided, skip the test suite (for when you're iterating fast and will test later).

## Checks

Run all of these and collect results. Do NOT stop on first failure — run everything and report all issues at once.

### 1. Python lint + format

```bash
cd src/backend
../../.venv/bin/ruff check . 2>&1 | tail -20
../../.venv/bin/ruff format --check . 2>&1 | tail -10
```

If `--fix`:
```bash
../../.venv/bin/ruff check --fix .
../../.venv/bin/ruff format .
```

### 2. TypeScript typecheck + lint

```bash
cd src/frontend
npm run typecheck 2>&1 | tail -20
npm run lint 2>&1 | tail -10
```

### 3. Backend tests (unless --skip-tests)

```bash
cd src/backend
../../.venv/bin/pytest tests/ -x --tb=short -q 2>&1 | tail -10
```

### 4. Frontend build check

```bash
cd src/frontend
npm run build 2>&1 | tail -10
```

### 5. Secret scan

```bash
# Scan staged files for potential secrets
git diff --staged --diff-filter=ACMR -- '*.py' '*.ts' '*.tsx' '*.js' '*.env*' '*.json' '*.yaml' '*.yml' | \
  grep -inE '(sk-[a-zA-Z0-9]{20,}|sk_live_|eyJ[a-zA-Z0-9]{30,}|AIza[a-zA-Z0-9]{30,}|ghp_|AKIA[A-Z0-9]{16})' || true
```

### 6. Env check

```bash
./scripts/check-env.sh 2>&1
```

## Output

```
## Preflight Check

| Check          | Status | Details              |
|----------------|--------|----------------------|
| Python lint    | ✓/✗    | {clean / N issues}   |
| Python format  | ✓/✗    | {clean / N files}    |
| TS typecheck   | ✓/✗    | {clean / N errors}   |
| TS lint        | ✓/✗    | {clean / N issues}   |
| Backend tests  | ✓/✗/⊘  | {N passed / failed / skipped} |
| Frontend build | ✓/✗    | {success / failed}   |
| Secret scan    | ✓/✗    | {clean / FOUND}      |
| Env check      | ✓/✗    | {all present / N missing} |

{If all pass}: ✅ Ready to ship. Run /ship "description"
{If any fail}: ❌ Fix {N} issues before shipping.
{If --fix applied}: 🔧 Auto-fixed {N} issues. Re-run /preflight to verify.
```
