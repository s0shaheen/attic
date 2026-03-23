---
description: Run tests relevant to what you just changed. Smarter than running the full suite.
argument-hint: "[--all] [--file path] [--coverage]"
---

## Logic

If `--all`: run the full suite for both backend and frontend. Skip the smart detection.

If `--file`: run tests for that specific file. Determine the test file path from the source file path:
- `app/services/gemini.py` → `tests/unit/test_gemini.py`
- `app/services/agent_tools.py` → `tests/unit/test_agent_tools.py`
- `app/services/ontology.py` → `tests/unit/test_ontology.py`
- `app/routers/chat.py` → `tests/unit/test_chat.py` and `tests/integration/test_chat_*.py`
- `app/models/*.py` → `tests/test_models.py`

Otherwise, detect what changed and run relevant tests:

```bash
# Get changed files
CHANGED=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only)
```

### Determine which test suites to run

```bash
PYTHON_CHANGED=$(echo "$CHANGED" | grep -c '\.py$' || true)
TS_CHANGED=$(echo "$CHANGED" | grep -c '\.\(ts\|tsx\)$' || true)
AGENT_CHANGED=$(echo "$CHANGED" | grep -cE '(agent|gemini|ontology|prompts|entity_resolvers)' || true)
MODEL_CHANGED=$(echo "$CHANGED" | grep -c 'models/' || true)
MIGRATION_CHANGED=$(echo "$CHANGED" | grep -c 'alembic/' || true)
```

### Run tests

**If agent/AI files changed:**
```bash
cd src/backend
../../.venv/bin/pytest tests/unit/test_agent_tools.py tests/unit/test_gemini.py tests/unit/test_ontology.py tests/unit/test_prompts.py -v --tb=short 2>&1
```

**If model files changed:**
```bash
cd src/backend
../../.venv/bin/pytest tests/test_models.py -v --tb=short 2>&1
```

**If any other Python changed:**
```bash
cd src/backend
../../.venv/bin/pytest tests/ -x --tb=short -q 2>&1
```

**If TypeScript changed:**
```bash
cd src/frontend
npm test 2>&1
```

**If migration files changed:**
```bash
cd src/backend
../../.venv/bin/alembic check 2>&1
```

### Coverage (if --coverage)
```bash
cd src/backend
../../.venv/bin/pytest tests/ --cov=app --cov-report=term-missing --tb=short 2>&1 | tail -30
```

## Output

```
## Test Results

Changed files: {N}
Test suites run: {list}

{test output}

{If all pass}: ✅ All tests pass. Run /preflight for full checks or /ship to merge.
{If failures}: ❌ {N} test(s) failed. Fix before shipping.
```
