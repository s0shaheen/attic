---
description: Generate task specification files for one or more tasks from the Dev Guide
argument-hint: "<epic_number> [task_ids]"
---

## Mission

Generate detailed task specification files from the Dev Guide task list. Each spec becomes the single source of truth for that task's implementation.

## Instructions

1. **Parse Arguments**
   - If only epic number provided: generate specs for ALL tasks in that epic
   - If task IDs provided: generate specs only for those specific tasks
   - Example: `0` generates all Epic 0 specs, `0 0.1 0.3` generates only those two

2. **Read Context**
   - Read `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` for task list and epic context
   - Read `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` for detailed requirements, API contracts, data model
   - Read `docs/MVP/tasks/SPEC_TEMPLATE.md` for the authoritative spec format
   - Read `CLAUDE.md` for code conventions and security checklist

3. **For Each Task, Generate Spec File**

   Create `docs/MVP/tasks/specs/{epic_number}-{task_number}.md` using the template from `SPEC_TEMPLATE.md`.

   **CRITICAL: Section-by-Section Guidance**

   Only fill out sections that are relevant to the task. Use "N/A - {reason}" for non-applicable sections. Never gloss over a section - either fill it thoroughly or explicitly mark it N/A.

   ### Section 0: Outcome
   - Extract from Dev Guide task description
   - Describe user-visible result, not implementation details
   - Be specific: "User can upload a ZIP file" not "File upload works"

   ### Section 1: Scope
   - **In-scope**: Extract from PRD acceptance criteria for the matching feature (F1, F2, etc.)
   - Each checkbox must be independently verifiable
   - **Out-of-scope**: Explicitly list what this task does NOT do
   - Check related tasks to avoid overlap

   ### Section 2: System context
   - **Components touched**: List ALL files that will be created or modified
     - Check existing codebase patterns for file paths
     - Be specific: `src/backend/app/routers/uploads.py` not just "backend"
   - **Invariants**: Extract from PRD "Production Requirements" sections
   - Skip irrelevant component types with "None"

   ### Section 3: API contracts
   - **If task involves API endpoints**: Copy exact contracts from PRD API section
   - **If task is frontend-only**: Include Zod schemas for any new types
   - **If task is infrastructure**: Mark as "N/A - Infrastructure task"
   - Include ALL status codes that could be returned
   - Include auth requirements for every endpoint

   ### Section 4: Data model changes
   - **If task touches database**:
     - Copy relevant schema from PRD Data Model section
     - Include RLS policies from PRD
     - Describe migration steps
   - **If no DB changes**: "N/A - No database changes"

   ### Section 5: Workflow & state machine
   - **Only for Epic 3 (Pipeline) tasks or tasks involving Step Functions/Lambda**
   - Include retry policies from PRD
   - Document idempotency strategy (CRITICAL for all pipeline steps)
   - **For non-workflow tasks**: "N/A - Not a workflow task"

   ### Section 6: Implementation plan
   - Order matters - dependencies first
   - Include specific file paths
   - Reference patterns from CLAUDE.md

   ### Section 7: Observability
   - Extract from PRD §9 observability requirements
   - Every task should have logging requirements
   - Infrastructure tasks: focus on setup verification
   - Feature tasks: focus on business events

   ### Section 8: Security & privacy checklist
   - Go through CLAUDE.md security checklist
   - Check each item and mark as applicable or N/A with reason
   - For auth/data tasks: extra scrutiny required
   - Reference PRD "Production Requirements" for each feature

   ### Section 9: Test plan
   - **Unit tests**: Test function name format from CLAUDE.md
   - **Integration tests**: Required for API endpoints and DB operations
   - **E2E tests**: Only for user-facing features with UI
   - Be specific: `test_parse_export_valid_zip_extracts_urls` not "test upload"

   ### Section 10: Acceptance criteria
   - These are BINARY (yes/no) checkboxes
   - Include standard verification: tests pass, linting, type checking
   - Add task-specific criteria from PRD acceptance criteria

   ### Section 11: Rollout
   - **For infrastructure tasks**: Focus on deployment order and verification
   - **For feature tasks**: Consider feature flags, backward compatibility
   - **For all tasks**: Include rollback plan

4. **Ensure spec directory exists**
   ```bash
   mkdir -p docs/MVP/tasks/specs/
   ```

5. **Update Dev Guide**
   - After generating specs, update the Dev Guide to add/update the status table for that epic
   - Mark generated tasks as `SPEC_READY`

6. **Report Summary**
   ```
   Generated specs:
   - docs/MVP/tasks/specs/0-0.1.md - Backend scaffolding
   - docs/MVP/tasks/specs/0-0.2.md - Frontend scaffolding
   ...

   Sections marked N/A per task:
   - 0.1: Sections 4, 5 (no DB, no workflow)
   - 0.2: Sections 3, 4, 5 (no API, no DB, no workflow)

   Next: Run /validate-specs 0 to check completeness
   ```

## Quality Standards

When generating specs, ensure:

1. **Specificity over generality**
   - ✗ Bad: "See PRD for details"
   - ✓ Good: "PRD §F2 Upload & Parsing, Data Model: uploads table"

2. **Context References point to SPECIFIC sections**
   - ✗ Bad: "Read the PRD"
   - ✓ Good: "PRD sections: F2 (Upload & Parsing), F3 (Consent), Data Model (uploads, media_events)"

3. **Requirements are atomic checkboxes**
   - ✗ Bad: "Implement upload functionality"
   - ✓ Good: "[ ] POST /api/uploads accepts multipart/form-data with 'file' and 'scope' fields"

4. **Data contracts include actual field names and types**
   - ✗ Bad: "Create request/response models"
   - ✓ Good: Actual Pydantic/Zod code copied from PRD or derived from requirements

5. **Test requirements are specific enough to write tests from**
   - ✗ Bad: "Add tests"
   - ✓ Good: "[ ] test_parse_export_invalid_zip_raises_validation_error"

6. **Dependencies reference actual task IDs that exist**
   - ✗ Bad: "Requires database setup"
   - ✓ Good: "Tasks that must complete first: 0.3, 0.4"

7. **N/A sections are explicit, not missing**
   - ✗ Bad: Empty section or section omitted
   - ✓ Good: "N/A - This task does not involve database changes"

## Cross-Referencing Checklist

Before finalizing each spec, verify:

- [ ] All PRD acceptance criteria for the feature are covered in scope
- [ ] All PRD production requirements are addressed in security checklist
- [ ] API contracts match PRD exactly (or note deviations)
- [ ] Data model matches PRD schema (or note deviations)
- [ ] Dependencies listed match the epic dependency graph in Dev Guide
- [ ] Test cases cover all acceptance criteria
