---
description: Design test strategy and write test stubs BEFORE implementation. Enables TDD workflow.
argument-hint: "<epic_number> [task_id] [--list-tasks] [--parallel] [--wave N] [--dry-run]"
---

## Mission

Generate test files for tasks BEFORE implementation begins. This enables Test-Driven Development (TDD) by creating test stubs that define expected behavior. **ALL test generation is delegated to subagents** to prevent context bloat.

## Orchestrator Discipline (CRITICAL)

To prevent auto-compaction of the main conversation:

**The orchestrator MUST NOT:**
- Read implementation files or existing tests
- Read spec file contents (only metadata: ID, status, dependencies)
- Write test code directly
- Analyze test patterns or existing test files
- Accumulate test file contents in context

**The orchestrator MUST:**
- Only read spec files for task metadata
- Only read Dev Guide for status tracking and wave configuration
- Delegate ALL test design/writing to `test-designer` subagents
- Run subagents in background (`run_in_background: true`)
- Accept subagent status reports at face value

**Context Budget:**
The orchestrator should stay under ~20% of context window by:
- Spawning subagents for ALL file reading/writing
- Never requesting code snippets in subagent responses
- Trusting subagent completion reports

## Arguments

- `epic_number` (required): Epic to generate tests for
- `task_id` (optional): Single task ID to process (e.g., `3.1`) - used by shell orchestrator
- `--list-tasks`: Output task IDs only, one per line (for script consumption)
- `--parallel`: Enable parallel subagent spawning for independent tasks
- `--wave N`: Only process tasks in wave N
- `--dry-run`: Show execution plan without generating tests

## List Tasks Mode

If `--list-tasks` is provided:

1. **Build task queue** (gather specs, parse dependencies)
2. **Output task IDs only**, one per line:
   ```
   3.1
   3.2
   3.3
   3.13
   ```
3. **Exit immediately** - no tests are generated

This output format is designed for script consumption (e.g., by `scripts/generate-tests.sh`).

## Single Task Mode

If a single `task_id` is provided as the second argument:

1. **Locate spec file**: `docs/MVP/tasks/specs/{epic}-{task_id}.md`
2. **Spawn ONE test-designer subagent** for that task
3. **Wait for completion**
4. **Report result and exit**

This mode is used by `scripts/generate-tests.sh` to run each task with fresh context.

**IMPORTANT**: When running all tasks in one session (no `task_id` argument), display this warning:

> ⚠️ Running all tasks in one session may hit context limits.
> For large epics, use: `./scripts/generate-tests.sh {epic}`

## Instructions

### Phase 1: Build Task Queue

1. **Gather Specs**
   ```
   If task IDs provided:
     specs = docs/MVP/tasks/specs/{epic}-{task}.md for each task_id
   Else:
     specs = docs/MVP/tasks/specs/{epic}-*.md

   Filter to: Status in [NOT_STARTED, SPEC_READY]
   Exclude: Status in [DONE, BLOCKED, IN_PROGRESS]
   ```

2. **Parse Dependencies** (metadata only - DO NOT read full content)

   For each spec, extract ONLY:
   - Task ID (from filename: `{epic}-{task}.md` → `{epic}.{task}`)
   - Dependencies (quick grep for "Tasks that must complete first")
   - Status (quick grep for "Status:")

3. **Build Dependency Graph**
   ```
   graph = {}
   for spec in specs:
       graph[spec.task_id] = {
           "depends_on": spec.dependencies,
           "status": spec.status
       }
   ```

4. **Determine Execution Waves**

   Apply topological sort:
   ```
   Wave 1: Tasks with no dependencies (or all deps DONE)
   Wave 2: Tasks depending only on Wave 1 tasks
   Wave 3: Tasks depending on Wave 1 or 2
   ...
   ```

   Within each wave, all tasks can run in parallel (tests don't have file conflicts like implementations).

5. **Handle --list-tasks (if specified)**

   If `--list-tasks` flag is set:
   ```
   # Output task IDs only, one per line (in wave order)
   for wave in waves:
       for task in wave.tasks:
           print(task.id)

   # Exit immediately - no execution
   exit(0)
   ```

### Phase 2: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 TEST GENERATION PLAN
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline
Tasks: 15 total

───────────────────────────────────────────────────────────

Wave 1 [PARALLEL]:
  ⇉ 3.1: Step Functions state machine
  ⇉ 3.13: Capability interfaces

Wave 2 [PARALLEL]:
  ⇉ 3.2: Parse Export Lambda
  ⇉ 3.3: Apify Enrich Lambda
  ⇉ 3.4: Media Download Lambda
  ... (remaining Lambda functions)

Wave 3 [PARALLEL]:
  ⇉ 3.12: SQS trigger configuration
  ⇉ 3.14: Error handling patterns
  ⇉ 3.15: Progress update mechanism

───────────────────────────────────────────────────────────
Total: 15 tasks across 3 waves
Mode: {sequential | parallel}

Legend:
  ⇉ Can run in parallel (--parallel flag)
  → Sequential task

Proceed? [y/n]
```

If `--dry-run`, stop here.

### Phase 3: Execute Test Generation

For each wave, spawn test-designer subagents:

**Sequential Mode (default):**
```
for task in wave.tasks:
    spawn test-designer subagent (run_in_background: true)
    wait for completion
    record result
    continue to next task
```

**Parallel Mode (--parallel flag):**
```
for wave in waves:
    spawn ALL test-designer subagents for wave.tasks (run_in_background: true)
    wait for ALL to complete
    record results
    continue to next wave
```

#### Spawn Test-Designer Subagent

```
Task tool parameters:
  subagent_type: test-designer
  run_in_background: true   # CRITICAL: Prevents context bloat
  description: "Generate tests for {task_id}"
  prompt: |
    Generate test stubs for task {task_id}.

    Spec file: docs/MVP/tasks/specs/{spec_file}

    Context to read:
    - The spec file (for requirements)
    - CLAUDE.md (for test conventions)
    - Existing test patterns in tests/ directories

    Create test files with:
    - Test function stubs (not full implementations)
    - AAA pattern comments (Arrange/Act/Assert)
    - Expected assertions as TODOs

    Report back with:
    - Files created
    - Test count per file
    - DONE | FAILED (with error)
```

#### Handle Subagent Responses

Read the subagent's output file and parse the final status:

**If DONE:**
- Record test files created
- Continue to next task/wave

**If FAILED:**
- Log the failure reason
- Mark task as "test generation failed"
- Continue to next task (don't block others)

### Phase 4: Summary Report

```
═══════════════════════════════════════════════════════════
 TEST GENERATION COMPLETE
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline

───────────────────────────────────────────────────────────

Wave 1 - Complete:
  ✓ 3.1: Step Functions state machine
    → tests/unit/test_state_machine.py (8 test stubs)
    → tests/integration/test_step_functions.py (4 test stubs)
  ✓ 3.13: Capability interfaces
    → tests/unit/test_capabilities.py (12 test stubs)

Wave 2 - Complete:
  ✓ 3.2: Parse Export Lambda
    → tests/unit/lambdas/test_parse_export.py (6 test stubs)
  ✓ 3.3: Apify Enrich Lambda
    → tests/unit/lambdas/test_apify_enrich.py (5 test stubs)
  ...

Wave 3 - Complete:
  ✓ 3.12: SQS trigger configuration
    → tests/integration/test_sqs_triggers.py (3 test stubs)
  ✓ 3.14: Error handling patterns
    → tests/unit/test_error_handling.py (7 test stubs)
  ✓ 3.15: Progress update mechanism
    → tests/unit/test_progress.py (4 test stubs)

───────────────────────────────────────────────────────────
Summary:
  Tasks processed: 15
  Test files created: 18
  Total test stubs: 72

Next steps:
  1. Review generated test stubs
  2. Run /implement-backlog 3 to implement features
  3. Run /run-task-tests 3 --all to verify implementations
```

### Phase 5: Update Dev Guide

Update task status to indicate tests are ready:

```markdown
| Task | Status | Tests |
|------|--------|-------|
| 3.1  | SPEC_READY | ✓ Generated |
| 3.2  | SPEC_READY | ✓ Generated |
```

## Test Stub Format

The test-designer subagent creates stubs like:

```python
# tests/unit/lambdas/test_parse_export.py

import pytest
from app.lambdas.parse_export import handler

class TestParseExportLambda:
    """Tests for parse_export Lambda function."""

    @pytest.mark.asyncio
    async def test_valid_zip_extracts_urls(self):
        """Test that valid TikTok export ZIP extracts video URLs."""
        # Arrange
        # TODO: Create test ZIP with mock liked videos

        # Act
        # TODO: Call handler with S3 event

        # Assert
        # TODO: Verify URLs extracted and stored in media_events table
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_invalid_zip_returns_error(self):
        """Test that invalid ZIP returns appropriate error."""
        # Arrange
        # TODO: Create invalid ZIP content

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify error response and status update
        pytest.skip("Test stub - implement during task 3.2")
```

## Wave Override Option

To process only specific waves:

```bash
/generate-tests 3 --wave 1         # Only Wave 1 tasks
/generate-tests 3 --wave 2         # Only Wave 2 tasks
```

This is useful for:
- Large epics where you want incremental progress
- Retrying a failed wave without re-running completed waves
- Testing the workflow on a subset before full execution
