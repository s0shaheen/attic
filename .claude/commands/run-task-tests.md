---
description: Run tests for a specific task based on its spec file
argument-hint: "<spec_file_or_task_id> | <epic_number> --all [--parallel] [--coverage]"
---

## Mission

Run all tests specified in a task's spec file and report results with actionable feedback. Supports single-task mode and epic-wide mode. **Epic-wide mode delegates to subagents** to prevent context bloat.

## Orchestrator Discipline (Epic Mode)

When running tests for an entire epic:

**The orchestrator MUST NOT:**
- Read test file contents
- Analyze test outputs in detail
- Debug test failures
- Accumulate test results in context

**The orchestrator MUST:**
- Only identify test files from spec metadata
- Delegate ALL test execution to `tester` subagents
- Run subagents in background (`run_in_background: true`)
- Collect only PASS/FAIL + counts from each subagent

**Context Budget:**
The orchestrator should stay under ~20% of context window by:
- Spawning subagents for ALL test execution
- Never requesting test output in main context
- Trusting subagent completion reports

## Arguments

### Single-Task Mode
- `spec_file`: Path to spec file (e.g., `docs/MVP/tasks/specs/0-0.1.md`)
- `task_id`: Task ID (e.g., `0.1`) - will look up spec file

### Epic-Wide Mode
- `epic_number --all`: Run tests for all tasks in epic (e.g., `3 --all`)
- `--parallel`: Enable parallel subagent spawning
- `--coverage`: Include coverage report

## Instructions

---

## Mode A: Single Task

When a single spec file or task ID is provided:

### Step 1: Load Spec

- If task_id provided, resolve to `docs/MVP/tasks/specs/{epic}-{task}.md`
- Read the spec file
- Extract "Test Requirements" section
- Extract "Components → Files to create/modify" for test file locations

### Step 2: Identify Test Files

Map spec components to test locations:
```
Component                    → Test File
─────────────────────────────────────────────────────
src/backend/app/api/auth.py  → src/backend/tests/unit/test_auth.py
src/backend/app/api/auth.py  → src/backend/tests/integration/test_auth_api.py
src/frontend/app/login/      → src/frontend/__tests__/login.test.tsx
```

### Step 3: Run Tests

**Backend tests:**
```bash
cd src/backend

# Run unit tests for this task's components
pytest tests/unit/test_{component}.py -v --tb=short

# Run integration tests
pytest tests/integration/test_{feature}.py -v --tb=short

# If specific test file doesn't exist, run pattern match
pytest tests/ -k "{task_keywords}" -v --tb=short
```

**Frontend tests:**
```bash
cd src/frontend

# Run tests matching component names
npm test -- --testPathPattern="{pattern}" --verbose
```

### Step 4: Collect Results

Parse test output to extract:
- Test name
- Pass/Fail status
- Duration
- Error message (if failed)
- Stack trace (for failures)

### Step 5: Output Report

```
═══════════════════════════════════════════════════════════
 TEST RESULTS: Task 0.3 - Supabase project setup
═══════════════════════════════════════════════════════════

UNIT TESTS (src/backend/tests/unit/)
─────────────────────────────────────────────────────────────
✓ test_supabase_client_init_with_valid_env          0.02s
✓ test_supabase_client_raises_on_missing_env        0.01s
✗ test_supabase_client_handles_network_error        0.15s

INTEGRATION TESTS (src/backend/tests/integration/)
─────────────────────────────────────────────────────────────
✓ test_supabase_connection_succeeds                 0.45s
✓ test_supabase_rls_blocks_cross_user_access        0.32s

═══════════════════════════════════════════════════════════
 SUMMARY: 4/5 passed (80%)
═══════════════════════════════════════════════════════════

FAILED TESTS:

▸ test_supabase_client_handles_network_error
  File: tests/unit/test_supabase.py:45

  AssertionError: Expected SupabaseNetworkError but got
  generic ConnectionError

  Suggested fix: Wrap ConnectionError in SupabaseNetworkError
  in src/backend/app/core/supabase.py
```

### Step 6: Update Spec File

If any tests failed:
```markdown
### Blocked By
- Tests failing: test_supabase_client_handles_network_error
  - Error: Expected SupabaseNetworkError but got ConnectionError
  - Fix needed in: src/backend/app/core/supabase.py
```

If all tests passed:
```markdown
### Implementation Notes
- All tests passing as of {date}
- Coverage: 80% (run with --cov for details)
```

### Step 7: Update Dev Guide

Update the task status in `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`:

- Find the epic's status table
- If tests **failed**: Set status to `BLOCKED`
- If tests **passed** and implementation is complete: Set status to `DONE`
- Update "Blocked By" column if needed

---

## Mode B: Epic-Wide (--all flag)

When epic number with `--all` flag is provided:

### Phase 1: Build Test Queue

1. **List all specs for the epic**
   ```bash
   ls docs/MVP/tasks/specs/{epic}-*.md 2>/dev/null
   ```

2. **Filter to DONE or IN_PROGRESS tasks**
   - Only run tests for tasks that have been implemented
   - Skip NOT_STARTED and SPEC_READY tasks

3. **Identify test files** for each task (metadata only)

### Phase 2: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 TEST EXECUTION PLAN
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline
Tasks with tests: 12 of 15

───────────────────────────────────────────────────────────

Tasks to test:
  ⇉ 3.1: Step Functions state machine (8 tests)
  ⇉ 3.2: Parse Export Lambda (6 tests)
  ⇉ 3.3: Apify Enrich Lambda (5 tests)
  ... (9 more)

Skipped (no implementation):
  ○ 3.14: Error handling (NOT_STARTED)
  ○ 3.15: Progress updates (NOT_STARTED)
  ○ 3.13: Capability interfaces (SPEC_READY)

───────────────────────────────────────────────────────────
Mode: {sequential | parallel}
Coverage: {enabled | disabled}

Proceed? [y/n]
```

### Phase 3: Execute Tests via Subagents

For each task, spawn a tester subagent:

**Sequential Mode (default):**
```
for task in tasks:
    spawn tester subagent (run_in_background: true)
    wait for completion
    record result (PASS/FAIL + counts)
    continue to next task
```

**Parallel Mode (--parallel flag):**
```
spawn ALL tester subagents (run_in_background: true)
wait for ALL to complete
record results
```

#### Spawn Tester Subagent

```
Task tool parameters:
  subagent_type: tester
  run_in_background: true   # CRITICAL: Prevents context bloat
  description: "Run tests for {task_id}"
  prompt: |
    Run tests for task {task_id}.

    Spec file: docs/MVP/tasks/specs/{spec_file}

    Steps:
    1. Read the spec to identify test requirements
    2. Find test files for this task's components
    3. Run pytest/npm test as appropriate
    4. Report results

    Coverage mode: {enabled | disabled}

    Report back with EXACTLY this format:
    ---
    STATUS: PASS | FAIL
    TOTAL: N
    PASSED: N
    FAILED: N
    SKIPPED: N
    COVERAGE: N% (if enabled)
    FAILED_TESTS:
    - {test_name}: {brief_reason}
    ---
```

#### Handle Subagent Responses

Parse the subagent's structured report:

**If STATUS: PASS:**
- Record as passing
- Continue to next task

**If STATUS: FAIL:**
- Record failure count
- Store failed test names (brief, not full output)
- Continue to next task

### Phase 4: Summary Report

```
═══════════════════════════════════════════════════════════
 TEST RESULTS: Epic 3
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline

───────────────────────────────────────────────────────────

Results by Task:
  ✓ 3.1: 12/12 passed
  ✓ 3.2: 8/8 passed
  ✗ 3.3: 5/7 passed (2 failures)
  ✓ 3.4: 6/6 passed
  ✗ 3.5: 3/5 passed (2 failures)
  ✓ 3.6: 4/4 passed
  ...
  ○ 3.14: No tests (not implemented)
  ○ 3.15: No tests (not implemented)

───────────────────────────────────────────────────────────
Summary:
  Total tests: 52
  Passed: 45 (87%)
  Failed: 7
  Skipped: 3 (no implementation)

Failed tests:
  3.3:
    - test_apify_batch_handles_rate_limit: Timeout exceeded
    - test_apify_metadata_validates_response: Missing field
  3.5:
    - test_whisper_transcribe_handles_silence: Empty result
    - test_whisper_falls_back_on_error: Wrong exception type

Coverage: 78% (if --coverage enabled)

───────────────────────────────────────────────────────────

Next steps:
  1. Fix failing tests in 3.3 and 3.5
  2. Re-run: /run-task-tests 3 --all
  3. When all pass: Update Dev Guide statuses
```

---

## Test Discovery Rules

When test files don't follow exact naming:

1. **Search patterns:**
   ```
   # For component src/backend/app/api/uploads.py
   Search:
   - tests/unit/test_uploads.py
   - tests/unit/test_upload*.py
   - tests/unit/*upload*.py
   - tests/integration/test_upload*.py
   ```

2. **Keyword matching:**
   ```
   # For task "Supabase project setup"
   Keywords: supabase, setup, config, connection

   pytest tests/ -k "supabase or setup or config"
   ```

3. **If no tests found:**
   ```
   ⚠ No test files found for task 0.3

   Expected test locations:
   - src/backend/tests/unit/test_supabase.py (missing)
   - src/backend/tests/integration/test_supabase.py (missing)

   Spec requires these test cases:
   - [ ] test_supabase_client_initializes
   - [ ] test_supabase_rls_policy_works

   Run /generate-tests 0 0.3 to create test stubs.
   ```

---

## Coverage Report (--coverage flag)

When coverage is requested:

```bash
cd src/backend
pytest tests/ -v --cov=app --cov-report=term-missing | head -50
```

Output coverage gaps:
```
COVERAGE REPORT
─────────────────────────────────────────────────────────────
app/core/supabase.py         85%   Missing: 67-72, 89
app/api/auth.py              92%   Missing: 45

Lines not covered:
- supabase.py:67-72: Error handling for rate limits
- auth.py:45: Edge case for expired refresh token
```
