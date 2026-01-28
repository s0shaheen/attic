---
description: Validate task specifications against PRD and production requirements
argument-hint: "<spec_file_or_epic_number>"
---

## Mission

Validate that task specifications are complete, consistent with the PRD, and meet production readiness requirements. Validates against the exhaustive template in `docs/MVP/tasks/SPEC_TEMPLATE.md`.

## Instructions

1. **Identify Specs to Validate**
   - If file path provided: validate that single spec
   - If epic number provided: validate all specs in `docs/MVP/tasks/specs/{epic}-*.md`
   - If no argument: validate all specs

2. **Read the Template** from `docs/MVP/tasks/SPEC_TEMPLATE.md` for expected structure

3. **For Each Spec, Run Validation Checks**

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
   - [ ] **Section 8: Security & privacy checklist** - All items marked (checked, unchecked, or N/A)
   - [ ] **Section 9: Test plan** - Specific test cases for unit, integration, E2E
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

   **System context (2)**:
   - [ ] File paths are specific (`src/backend/app/...` not just "backend")
   - [ ] Invariants are stated (if applicable)

   **API contracts (3)** (if not N/A):
   - [ ] Actual Pydantic/Zod code, not placeholders
   - [ ] Status codes listed
   - [ ] Auth requirements specified

   **Data model (4)** (if not N/A):
   - [ ] Migration steps described
   - [ ] RLS policies included
   - [ ] Indexes specified

   **Workflow (5)** (if not N/A):
   - [ ] States and transitions defined
   - [ ] Retry policy specified
   - [ ] Idempotency strategy documented

   **Implementation plan (6)**:
   - [ ] Steps are ordered
   - [ ] File paths included
   - [ ] Dependencies addressed first

   **Observability (7)**:
   - [ ] Required log fields listed
   - [ ] Metrics defined (even if basic)

   **Security (8)**:
   - [ ] Each checklist item addressed (checked, unchecked, or N/A with reason)
   - [ ] Not just copied boilerplate

   **Test plan (9)**:
   - [ ] Test names follow pattern: `test_{function}_{scenario}_{expected}`
   - [ ] Covers acceptance criteria

   **Acceptance criteria (10)**:
   - [ ] Binary yes/no format
   - [ ] Includes standard checks (tests pass, lint, typecheck)

   **Rollout (11)**:
   - [ ] Rollback plan specified

   ### Check 3: PRD Consistency

   Cross-reference with `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md`:

   - [ ] Requirements align with PRD acceptance criteria for the feature
   - [ ] API contracts match PRD specifications (if applicable)
   - [ ] Data model changes align with PRD schema
   - [ ] No scope creep beyond what PRD defines
   - [ ] Production requirements from PRD are addressed

   ### Check 4: Production Readiness

   Based on PRD §9 and `CLAUDE.md` security checklist:

   - [ ] Idempotency strategy documented for any database writes
   - [ ] Error handling approach specified
   - [ ] Observability requirements included (logging, metrics)
   - [ ] Security items are actionable, not just copied boilerplate

   ### Check 5: Dependency Correctness

   - [ ] Listed dependencies are actual task IDs that exist
   - [ ] No circular dependencies in the graph
   - [ ] Infrastructure tasks (Epic 0) don't depend on feature tasks
   - [ ] Required specs exist for all dependencies

4. **Output Validation Report**

   For each spec file:
   ```
   ## docs/MVP/tasks/specs/0-0.1.md

   ### Structural Completeness: PASS | FAIL
   - ✓ Section 0: Outcome
   - ✓ Section 1: Scope
   - ✓ Section 2: System context
   - ✓ Section 3: API contracts (N/A - valid)
   - ✗ Section 4: Data model - MISSING (should be N/A if no DB changes)
   - ✓ Section 5: Workflow (N/A - valid)
   ...

   ### Content Quality: PASS | FAIL
   - ✓ Outcome is user-focused
   - ✗ API contracts: Missing actual Pydantic models
   - ✓ Test cases are specific

   ### PRD Consistency: PASS | FAIL
   - ✓ Requirements match PRD F1 acceptance criteria

   ### Production Readiness: PASS | FAIL
   - ✗ Idempotency: Not addressed (task involves DB writes)

   ### Dependencies: PASS | FAIL
   - ✓ No circular dependencies

   **Overall**: PASS | NEEDS_REVISION

   **Required Fixes** (if NEEDS_REVISION):
   1. Add Section 4 (mark N/A if no DB changes)
   2. Add Pydantic model definitions to Section 3
   3. Document idempotency approach for database inserts
   ```

5. **Summary**
   ```
   Validation Summary for Epic 0:

   VALID: 5 specs
   NEEDS_REVISION: 3 specs

   Specs requiring fixes:
   - 0-0.3.md: Missing Section 4 (Data model)
   - 0-0.5.md: Dependency 0.3 not marked as prerequisite
   - 0-0.7.md: No rollback plan in Section 11

   Run /generate-specs to regenerate, or edit specs manually.
   ```

6. **Auto-Fix Offer**

   For simple issues (missing section headers, N/A not stated), offer to fix:
   ```
   Would you like me to auto-fix these issues?
   - Add missing section headers with N/A placeholder (3 specs)
   - Add standard acceptance criteria (2 specs)

   [y/n]
   ```

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
