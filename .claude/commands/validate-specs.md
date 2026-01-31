---
description: Validate task specifications against PRD and production requirements
argument-hint: "<spec_file_or_epic_number> [--parallel] [--strict] [--fix]"
---

## Mission

Validate that task specifications are complete, consistent with the PRD, and meet production readiness requirements. **ALL validation is delegated to subagents** to prevent context bloat.

## Orchestrator Discipline (CRITICAL)

To prevent auto-compaction of the main conversation:

**The orchestrator MUST NOT:**
- Read spec file contents
- Read the PRD
- Read the template
- Analyze validation details
- Accumulate validation results in context

**The orchestrator MUST:**
- Only list spec files to validate
- Delegate ALL validation to `spec-validator` subagents
- Run subagents in background (`run_in_background: true`)
- Collect only PASS/FAIL + issue count from each subagent
- Accept subagent status reports at face value

**Context Budget:**
The orchestrator should stay under ~20% of context window by:
- Spawning subagents for ALL file reading/validation
- Never requesting detailed validation output in main context
- Trusting subagent completion reports

## Arguments

- `spec_file`: Path to a single spec file (e.g., `docs/MVP/tasks/specs/0-0.1.md`)
- `epic_number`: Validate all specs for an epic (e.g., `3`)
- No argument: Validate all specs
- `--parallel`: Enable parallel subagent spawning
- `--strict`: Fail on warnings (not just errors)
- `--fix`: Attempt to auto-fix simple issues

## Instructions

### Phase 1: Build Validation Queue

1. **Identify Specs to Validate**
   ```
   If file path provided:
     specs = [provided_path]
   Elif epic number provided:
     specs = docs/MVP/tasks/specs/{epic}-*.md
   Else:
     specs = docs/MVP/tasks/specs/*.md
   ```

2. **List Specs** (metadata only - DO NOT read contents)
   ```bash
   ls docs/MVP/tasks/specs/{epic}-*.md 2>/dev/null
   ```

### Phase 2: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 SPEC VALIDATION PLAN
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline
Specs: 15 files

───────────────────────────────────────────────────────────

Files to validate:
  ⇉ docs/MVP/tasks/specs/3-3.1.md
  ⇉ docs/MVP/tasks/specs/3-3.2.md
  ⇉ docs/MVP/tasks/specs/3-3.3.md
  ... (12 more)

───────────────────────────────────────────────────────────
Mode: {sequential | parallel}
Strictness: {normal | strict}
Auto-fix: {enabled | disabled}

Proceed? [y/n]
```

### Phase 3: Execute Validation

For each spec, spawn a spec-validator subagent:

**Sequential Mode (default):**
```
for spec in specs:
    spawn spec-validator subagent (run_in_background: true)
    wait for completion
    record result (PASS/FAIL + count)
    continue to next spec
```

**Parallel Mode (--parallel flag):**
```
spawn ALL spec-validator subagents (run_in_background: true)
wait for ALL to complete
record results
```

#### Spawn Spec-Validator Subagent

```
Task tool parameters:
  subagent_type: spec-validator
  run_in_background: true   # CRITICAL: Prevents context bloat
  description: "Validate {spec_file}"
  prompt: |
    Validate specification file: {spec_file}

    Validation checks to perform:
    1. Structural Completeness - All 12 sections exist (filled or N/A)
    2. Content Quality - Requirements are specific and checkable
    3. PRD Consistency - Aligns with docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md
    4. Production Readiness - Meets PRD §9 requirements
    5. Dependency Correctness - Task IDs exist, no circular deps

    Context to read:
    - The spec file
    - docs/MVP/tasks/SPEC_TEMPLATE.md
    - docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md (relevant sections)

    Auto-fix mode: {enabled | disabled}

    Report back with EXACTLY this format:
    ---
    STATUS: PASS | NEEDS_REVISION
    CHECKS: 5/5 | 4/5 | etc.
    ISSUES: 0 | N
    ISSUE_LIST:
    - {issue 1}
    - {issue 2}
    FIXES_APPLIED: 0 | N (if auto-fix enabled)
    ---
```

#### Handle Subagent Responses

Parse the subagent's structured report:

**If STATUS: PASS:**
- Record as passing
- Continue to next spec

**If STATUS: NEEDS_REVISION:**
- Record issue count
- Store issue summary (brief, not full details)
- Continue to next spec

### Phase 4: Summary Report

```
═══════════════════════════════════════════════════════════
 VALIDATION SUMMARY
═══════════════════════════════════════════════════════════

Epic 3: Processing Pipeline

───────────────────────────────────────────────────────────

Results:
  ✓ 3.1: PASS (5/5 checks)
  ✓ 3.2: PASS (5/5 checks)
  ✗ 3.3: NEEDS_REVISION (3/5 checks, 2 issues)
  ✓ 3.4: PASS (5/5 checks)
  ✗ 3.5: NEEDS_REVISION (4/5 checks, 1 issue)
  ...

───────────────────────────────────────────────────────────
Summary:
  PASS: 12 specs
  NEEDS_REVISION: 3 specs

Specs requiring fixes:
  3.3: Missing Section 4 (Data model), PRD mismatch in API contract
  3.5: Dependency 3.2 not marked as prerequisite
  3.7: No rollback plan in Section 11

───────────────────────────────────────────────────────────

View detailed reports:
  .claude/validation-runs/{timestamp}/3-3.3.md
  .claude/validation-runs/{timestamp}/3-3.5.md
  .claude/validation-runs/{timestamp}/3-3.7.md

Next steps:
  1. Fix issues in flagged specs
  2. Re-run: /validate-specs 3
  3. If all pass: /generate-tests 3
```

### Phase 5: Write Detailed Reports (Optional)

If detailed output is needed, subagents write to:
```
.claude/validation-runs/{timestamp}/{spec_name}.md
```

This keeps detailed validation output out of the main conversation context.

---

## Validation Checks (Performed by Subagent)

The spec-validator subagent performs these checks:

### Check 1: Structural Completeness

Verify all 12 sections exist (0-11 plus Progress Tracking):

- [ ] **Section 0: Outcome** - Describes user-visible result
- [ ] **Section 1: Scope** - Has In-scope checkboxes AND Out-of-scope items
- [ ] **Section 2: System context** - Lists components OR "None" for each type
- [ ] **Section 3: API contracts** - Has actual schemas OR "N/A - {reason}"
- [ ] **Section 4: Data model changes** - Has migrations/RLS OR "N/A - {reason}"
- [ ] **Section 5: Workflow & state machine** - Has states/transitions OR "N/A - {reason}"
- [ ] **Section 6: Implementation plan** - Ordered steps with file paths
- [ ] **Section 7: Observability** - Logs, metrics, events defined
- [ ] **Section 8: Security & privacy checklist** - All items marked
- [ ] **Section 9: Test plan** - Specific test cases
- [ ] **Section 10: Acceptance criteria** - Binary checkboxes
- [ ] **Section 11: Rollout** - Feature flags, compatibility, rollback plan
- [ ] **Progress Tracking** - Status, Completed, Remaining, Blocked By, Notes

### Check 2: Content Quality

For each filled section (not N/A):

**Outcome (0)**:
- [ ] Describes what USER can do, not implementation details
- [ ] Specific enough to verify

**Scope (1)**:
- [ ] In-scope items are checkboxes (not bullets)
- [ ] Each checkbox is independently verifiable
- [ ] Out-of-scope explicitly states exclusions

**API contracts (3)** (if not N/A):
- [ ] Actual Pydantic/Zod code, not placeholders
- [ ] Status codes listed
- [ ] Auth requirements specified

**Test plan (9)**:
- [ ] Test names follow pattern: `test_{function}_{scenario}_{expected}`
- [ ] Covers acceptance criteria

### Check 3: PRD Consistency

Cross-reference with `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md`:

- [ ] Requirements align with PRD acceptance criteria for the feature
- [ ] API contracts match PRD specifications (if applicable)
- [ ] Data model changes align with PRD schema
- [ ] No scope creep beyond what PRD defines

### Check 4: Production Readiness

Based on PRD §9 and `CLAUDE.md` security checklist:

- [ ] Idempotency strategy documented for any database writes
- [ ] Error handling approach specified
- [ ] Observability requirements included
- [ ] Security items are actionable, not boilerplate

### Check 5: Dependency Correctness

- [ ] Listed dependencies are actual task IDs that exist
- [ ] No circular dependencies in the graph
- [ ] Infrastructure tasks don't depend on feature tasks
- [ ] Required specs exist for all dependencies

---

## Auto-Fix Mode (--fix flag)

When enabled, the subagent attempts to fix simple issues:

**Can auto-fix:**
- Missing section headers with N/A placeholder
- Missing "N/A - {reason}" on empty sections
- Standard acceptance criteria additions
- Formatting inconsistencies

**Cannot auto-fix:**
- Missing content that requires PRD analysis
- Incorrect API contracts
- Missing test cases
- Dependency errors

---

## Validation Strictness

**Be strict about:**
- All 12 sections must exist (filled or N/A)
- Data contracts MUST have actual field definitions (not "TBD")
- Test cases MUST be specific enough to implement
- Dependencies MUST reference real task IDs
- N/A sections MUST have a reason

**Be lenient about:**
- Out-of-Scope can be brief if scope is clear
- Implementation Notes can be empty (filled during dev)
- Observability can be minimal for infrastructure tasks
