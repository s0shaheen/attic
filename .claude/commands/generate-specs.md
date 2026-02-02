---
description: Generate task specification files from Dev Guide entries or backlog items
argument-hint: "<epic_number> [task_ids] | B-<backlog_id> [--parallel] [--dry-run] [--analyze-branches]"
---

## Mission

Generate detailed task specification files from the Dev Guide task list OR from backlog items. Each spec becomes the single source of truth for that task's implementation. **ALL spec writing is delegated to subagents** to prevent context bloat.

## Orchestrator Discipline (CRITICAL)

To prevent auto-compaction of the main conversation:

**The orchestrator MUST NOT:**
- Read the full PRD
- Read the spec template content
- Read CLAUDE.md in detail
- Write spec content directly
- Accumulate spec file contents in context

**The orchestrator MUST:**
- Only read Dev Guide for task list and metadata
- Delegate ALL spec writing to `spec-writer` subagents
- Run subagents in background (`run_in_background: true`)
- Accept subagent status reports at face value

**Context Budget:**
The orchestrator should stay under ~20% of context window by:
- Spawning subagents for ALL file reading/writing
- Never requesting spec content in subagent responses
- Trusting subagent completion reports

## Arguments

- `epic_number`: Epic to generate specs for
- `task_ids` (optional): Specific task IDs (e.g., `0 0.1 0.3`)
- `B-XXX`: Backlog item ID (alternative to epic/task)
- `--parallel`: Enable parallel subagent spawning
- `--dry-run`: Show execution plan without generating specs
- `--analyze-branches`: Run Phase 7 branching strategy analysis (default: skip)

## Instructions

### Phase 0: Parse Arguments

Determine the input type:

1. **Epic number only** (e.g., `1`): Generate specs for ALL tasks in that epic
2. **Epic + task IDs** (e.g., `0 0.1 0.3`): Generate specs only for those specific tasks
3. **Backlog ID** (e.g., `B-001`): Generate spec from a backlog item (Path A)

---

## Path A: Backlog Item (B-XXX)

When a backlog ID is provided, delegate to a single spec-writer subagent:

```
Task tool parameters:
  subagent_type: spec-writer
  run_in_background: true
  max_turns: 25
  description: "Generate spec from B-{XXX}"
  prompt: |
    Generate a spec from backlog item B-{XXX}.

    Steps:
    1. Read docs/MVP/tasks/BACKLOG.md and locate the item
    2. If in "Ready for Spec": proceed
    3. If in "Needs Design": STOP and report "Needs design first"
    4. If in "Icebox": report "Item is in icebox - confirm promotion"
    5. Determine next task ID from Dev Guide
    6. Generate spec using template
    7. Update Dev Guide with new task
    8. Archive backlog item

    Report back with:
    - Task ID assigned
    - Spec file path created
    - DONE | FAILED (with error) | NEEDS_CONFIRMATION (with reason)
```

Skip to Phase 6 (Report) after subagent completes.

---

## Path B: Epic/Task IDs (Main Flow)

### Phase 1: Build Task Queue

1. **Read Dev Guide** (metadata only)
   - Read `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`
   - Extract task list for the specified epic
   - DO NOT read PRD or other documents here

2. **Filter Tasks**
   - If task IDs provided: only those tasks
   - Otherwise: all tasks in the epic

3. **Check Existing Specs**
   ```bash
   ls docs/MVP/tasks/specs/{epic}-*.md 2>/dev/null
   ```
   - Identify which specs already exist
   - Default: skip existing specs (regenerate only with `--force`)

### Phase 2: Determine Execution Waves

For spec generation, waves are simpler than for implementation (no file overlap concerns):

```
Wave 1: Foundation specs (infrastructure, core interfaces)
Wave 2: Feature specs (dependent on Wave 1)
Wave 3: Integration specs (dependent on multiple Wave 2 specs)
```

For most epics, all specs can run in parallel since spec files don't depend on each other.

### Phase 3: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 SPEC GENERATION PLAN
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline
Tasks: 15 total (12 new, 3 existing)

───────────────────────────────────────────────────────────

Wave 1 [PARALLEL]:
  ⇉ 3.1: Step Functions state machine
  ⇉ 3.13: Capability interfaces
  ○ 3.2: Parse Export Lambda (spec exists - skipping)

Wave 2 [PARALLEL]:
  ⇉ 3.3: Apify Enrich Lambda
  ⇉ 3.4: Media Download Lambda
  ...

───────────────────────────────────────────────────────────
Total: 12 specs to generate
Mode: {sequential | parallel}
Branching analysis: {enabled | disabled}

Legend:
  ⇉ Will generate spec
  ○ Spec exists (skipping)

Proceed? [y/n]
```

If `--dry-run`, stop here.

### Phase 4: Execute Spec Generation

For each task, spawn a spec-writer subagent:

**Sequential Mode (default):**
```
for task in tasks:
    spawn spec-writer subagent (run_in_background: true)
    wait for completion
    record result
    continue to next task
```

**Parallel Mode (--parallel flag):**
```
spawn ALL spec-writer subagents (run_in_background: true)
wait for ALL to complete
record results
```

#### Spawn Spec-Writer Subagent

```
Task tool parameters:
  subagent_type: spec-writer
  run_in_background: true   # CRITICAL: Prevents context bloat
  max_turns: 25
  description: "Generate spec for {task_id}"
  prompt: |
    Generate specification for task {task_id} in Epic {epic}.

    Task from Dev Guide: {task_name}
    Task description: {brief_description}

    Output file: docs/MVP/tasks/specs/{epic}-{task}.md

    Context to read:
    - docs/MVP/tasks/SPEC_TEMPLATE.md
    - docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md (relevant sections only)
    - CLAUDE.md
    - docs/MVP/tasks/specs/ (existing specs for patterns)

    Report back with:
    - Spec file path
    - Sections filled vs N/A
    - DONE | FAILED (with error)
```

#### Handle Subagent Responses

Read the subagent's output file and parse the final status:

**If DONE:**
- Record spec file created
- Continue to next task

**If FAILED:**
- Log the failure reason
- Mark task as "spec generation failed"
- Continue to next task (don't block others)

### Phase 5: Update Dev Guide

After all specs are generated, update status:

```markdown
| Task | Status |
|------|--------|
| 3.1  | SPEC_READY |
| 3.2  | SPEC_READY |
| 3.3  | FAILED |   <!-- If generation failed -->
```

### Phase 6: Report Summary

```
═══════════════════════════════════════════════════════════
 SPEC GENERATION COMPLETE
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline

───────────────────────────────────────────────────────────

Generated:
  ✓ docs/MVP/tasks/specs/3-3.1.md - Step Functions state machine
  ✓ docs/MVP/tasks/specs/3-3.3.md - Apify Enrich Lambda
  ✓ docs/MVP/tasks/specs/3-3.4.md - Media Download Lambda
  ...

Skipped (existing):
  ○ docs/MVP/tasks/specs/3-3.2.md

Failed:
  ✗ 3.5: Could not determine API contracts from PRD

───────────────────────────────────────────────────────────
Summary:
  Generated: 11 specs
  Skipped: 3 specs (already exist)
  Failed: 1 spec

Next steps:
  1. Review generated specs
  2. Run /validate-specs 3 to check completeness
  3. Optionally: /generate-specs 3 --analyze-branches
```

---

## Phase 7: Branching Strategy Analysis (Optional)

**Only runs when `--analyze-branches` flag is provided.**

This phase analyzes file overlap and dependencies to recommend branching strategies. For large epics, this analysis adds significant context and should be run separately from spec generation.

### When to Use

- After all specs are generated
- Before starting implementation
- When planning work distribution

### How to Run

```bash
/generate-specs 3 --analyze-branches   # Analyze after specs exist
```

### Analysis Steps

1. **Compute File Overlap Matrix**

   For each pair of tasks:
   ```
   shared_files = task_a.components ∩ task_b.components
   overlap_pct = len(shared_files) / len(task_a.components ∪ task_b.components)
   ```

2. **Build Dependency Graph**

   Extract dependency chains from specs:
   ```
   dep_graph[task_id] = {
       "depends_on": spec.dependencies,
       "depended_by": [],  # Populated from reverse lookup
   }
   ```

3. **Identify Patterns**

   - **Linear chain**: A → B → C → D
   - **Fan-out**: A → [B, C, D]
   - **Fan-in**: [A, B, C] → D
   - **Independent**: No dependencies
   - **Mixed**: Combination

4. **Apply Strategy Rules**

   | Pattern | File Overlap | Recommended Strategy |
   |---------|--------------|---------------------|
   | Linear chain | Any | `stacked` |
   | Independent | Low (<20%) | `parallel` |
   | Independent | High (>50%) | `epic-branch` |
   | Fan-out | Low | `parallel` |
   | Fan-out | High | First `parallel`, children `stacked` |
   | Fan-in | Any | All parents `parallel`, final separate wave |

5. **Generate Wave Groupings**

   Group tasks by dependencies and overlap into waves.

6. **Output Strategy Recommendation**

   ```
   ═══════════════════════════════════════════════════════════
    BRANCHING STRATEGY ANALYSIS
   ═══════════════════════════════════════════════════════════

   Epic 3: Processing Pipeline

   File Overlap Analysis:
   ┌─────────────────────────┬────────────────────┬─────────┐
   │ File                    │ Tasks              │ Level   │
   ├─────────────────────────┼────────────────────┼─────────┤
   │ lambdas/parse_export.py │ 3.2                │ NONE    │
   │ lambdas/apify_enrich.py │ 3.3                │ NONE    │
   │ capabilities/*.py       │ 3.13, 3.2-3.11     │ MEDIUM  │
   └─────────────────────────┴────────────────────┴─────────┘

   Recommended Strategy:
   ┌───────┬────────────────────────┬──────────┬───────────────────┐
   │ Wave  │ Tasks                  │ Strategy │ Rationale         │
   ├───────┼────────────────────────┼──────────┼───────────────────┤
   │ 1     │ 3.1, 3.13             │ parallel │ 0% file overlap   │
   │ 2     │ 3.2 → 3.11            │ parallel │ Isolated Lambdas  │
   │ 3     │ 3.12, 3.14, 3.15      │ parallel │ Independent       │
   └───────┴────────────────────────┴──────────┴───────────────────┘
   ```

7. **Write to Dev Guide**

   Update the epic header with strategy configuration.

---

## Quality Standards (Applied by Subagents)

The spec-writer subagent enforces these standards:

1. **Specificity over generality**
   - ✗ Bad: "See PRD for details"
   - ✓ Good: "PRD §F2 Upload & Parsing, Data Model: uploads table"

2. **Atomic, checkable requirements**
   - ✗ Bad: "Implement upload functionality"
   - ✓ Good: "[ ] POST /api/uploads accepts multipart/form-data"

3. **Real data contracts**
   - ✗ Bad: "Define request/response models"
   - ✓ Good: Actual Pydantic/Zod code

4. **Specific test cases**
   - ✗ Bad: "Add tests"
   - ✓ Good: "[ ] test_parse_export_valid_zip_extracts_urls"

5. **Real task ID dependencies**
   - ✗ Bad: "Requires database setup"
   - ✓ Good: "Tasks that must complete first: 0.3, 0.4"

6. **Explicit N/A sections**
   - ✗ Bad: Empty section
   - ✓ Good: "N/A - This task does not involve database changes"
