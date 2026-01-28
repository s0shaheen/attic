---
description: Generate task specification files from Dev Guide entries or backlog items
argument-hint: "<epic_number> [task_ids] | B-<backlog_id>"
---

## Mission

Generate detailed task specification files from the Dev Guide task list OR from backlog items. Each spec becomes the single source of truth for that task's implementation.

## Instructions

### Phase 0: Parse Arguments

Determine the input type:

1. **Epic number only** (e.g., `1`): Generate specs for ALL tasks in that epic
2. **Epic + task IDs** (e.g., `0 0.1 0.3`): Generate specs only for those specific tasks
3. **Backlog ID** (e.g., `B-001`): Generate spec from a backlog item (NEW)

---

## Path A: Backlog Item (B-XXX)

When a backlog ID is provided:

### Step 1: Read Backlog Entry

Read `docs/MVP/tasks/BACKLOG.md` and locate the item:

- **If in "Ready for Spec"**: Proceed to Step 2
- **If in "Needs Design"**: Stop and suggest: "This item needs design first. Run the `designer` agent or `/intake` to complete design."
- **If in "Icebox"**: Confirm with user: "This item is in icebox. Promote to Ready for Spec and generate?"
- **If not found**: Error: "Backlog item B-{XXX} not found"

### Step 2: Extract Backlog Context

From the backlog entry, gather:
- Title
- Category (Infra, Feature, Tech Debt, Bug Fix, Testing, Docs)
- LOE estimate
- Target Epic
- Dependencies
- Design Notes (in the row or from design conversation)

### Step 3: Determine Task ID

**If Target Epic is specified (e.g., "0" or "3")**:
1. Read `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`
2. Find the highest task number in that epic
3. Assign next number (e.g., if 0.9 exists, assign 0.10)

**If Target Epic is "New"**:
1. Determine the next epic number (e.g., if Epic 9 exists, create Epic 10)
2. Create new epic section in Dev Guide
3. Assign task X.1

**If Target Epic is "TBD"**:
1. Ask user: "Which epic should this task belong to?"
2. Provide options based on category fit

### Step 4: Generate Spec

Create spec at `docs/MVP/tasks/specs/{epic}-{task}.md`:

1. Read `docs/MVP/tasks/SPEC_TEMPLATE.md` for structure
2. Read `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` for relevant requirements
3. Read `CLAUDE.md` for conventions
4. Check existing specs in `docs/MVP/tasks/specs/` for patterns

Fill the spec using:
- Backlog title → Task name
- Backlog category → Guides which sections are relevant
- Backlog LOE → Helps scope the requirements
- Design notes → Informs technical approach, scope boundaries

### Step 5: Update Dev Guide

Add the new task to `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`:

1. Find the target epic's task table
2. Add new row with task ID, name, description
3. Add to the epic's status table with status `NOT_STARTED`

### Step 6: Update Backlog

In `docs/MVP/tasks/BACKLOG.md`:

1. Remove the entry from "Ready for Spec" section
2. Add entry to "Completed (Archive)" section:
   ```
   | B-{XXX} | {Title} | {X.Y} | {YYYY-MM-DD} |
   ```

### Step 7: Report

```
═══════════════════════════════════════════════════════════
 SPEC GENERATED FROM BACKLOG
═══════════════════════════════════════════════════════════

Backlog Item: B-{XXX} "{Title}"
Became Task:  {X.Y}: {Task Name}
Epic:         {X} - {Epic Name}

Files Created/Updated:
- docs/MVP/tasks/specs/{X}-{X.Y}.md (created)
- docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md (updated)
- docs/MVP/tasks/BACKLOG.md (item archived)

Sections filled: {list}
Sections N/A: {list with reasons}

Next Steps:
1. Review spec: docs/MVP/tasks/specs/{X}-{X.Y}.md
2. Validate: /validate-specs {X}.{Y}
3. Implement: /implement-backlog {X}
───────────────────────────────────────────────────────────
```

---

## Path B: Epic/Task IDs (Existing Flow)

When epic number (and optional task IDs) are provided:

### Step 1: Parse Arguments

- If only epic number provided: generate specs for ALL tasks in that epic
- If task IDs provided: generate specs only for those specific tasks
- Example: `0` generates all Epic 0 specs, `0 0.1 0.3` generates only those two

### Step 2: Read Context

- Read `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` for task list and epic context
- Read `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` for detailed requirements
- Read `docs/MVP/tasks/SPEC_TEMPLATE.md` for the authoritative spec format
- Read `CLAUDE.md` for code conventions and security checklist

### Step 3: For Each Task, Generate Spec File

Create `docs/MVP/tasks/specs/{epic_number}-{task_number}.md` using the template.

**CRITICAL: Section-by-Section Guidance**

Only fill out sections that are relevant to the task. Use "N/A - {reason}" for non-applicable sections. Never gloss over a section - either fill it thoroughly or explicitly mark it N/A.

#### Section 0: Outcome
- Extract from Dev Guide task description
- Describe user-visible result, not implementation details
- Be specific: "User can upload a ZIP file" not "File upload works"

#### Section 1: Scope
- **In-scope**: Extract from PRD acceptance criteria for the matching feature (F1, F2, etc.)
- Each checkbox must be independently verifiable
- **Out-of-scope**: Explicitly list what this task does NOT do
- Check related tasks to avoid overlap

#### Section 2: System context
- **Components touched**: List ALL files that will be created or modified
  - Check existing codebase patterns for file paths
  - Be specific: `src/backend/app/routers/uploads.py` not just "backend"
- **Invariants**: Extract from PRD "Production Requirements" sections
- Skip irrelevant component types with "None"

#### Section 3: API contracts
- **If task involves API endpoints**: Copy exact contracts from PRD API section
- **If task is frontend-only**: Include Zod schemas for any new types
- **If task is infrastructure**: Mark as "N/A - Infrastructure task"
- Include ALL status codes that could be returned
- Include auth requirements for every endpoint

#### Section 4: Data model changes
- **If task touches database**:
  - Copy relevant schema from PRD Data Model section
  - Include RLS policies from PRD
  - Describe migration steps
- **If no DB changes**: "N/A - No database changes"

#### Section 5: Workflow & state machine
- **Only for Epic 3 (Pipeline) tasks or tasks involving Step Functions/Lambda**
- Include retry policies from PRD
- Document idempotency strategy (CRITICAL for all pipeline steps)
- **For non-workflow tasks**: "N/A - Not a workflow task"

#### Section 6: Implementation plan
- Order matters - dependencies first
- Include specific file paths
- Reference patterns from CLAUDE.md

#### Section 7: Observability
- Extract from PRD §9 observability requirements
- Every task should have logging requirements
- Infrastructure tasks: focus on setup verification
- Feature tasks: focus on business events

#### Section 8: Security & privacy checklist
- Go through CLAUDE.md security checklist
- Check each item and mark as applicable or N/A with reason
- For auth/data tasks: extra scrutiny required
- Reference PRD "Production Requirements" for each feature

#### Section 9: Test plan
- **Unit tests**: Test function name format from CLAUDE.md
- **Integration tests**: Required for API endpoints and DB operations
- **E2E tests**: Only for user-facing features with UI
- Be specific: `test_parse_export_valid_zip_extracts_urls` not "test upload"

#### Section 10: Acceptance criteria
- These are BINARY (yes/no) checkboxes
- Include standard verification: tests pass, linting, type checking
- Add task-specific criteria from PRD acceptance criteria

#### Section 11: Rollout
- **For infrastructure tasks**: Focus on deployment order and verification
- **For feature tasks**: Consider feature flags, backward compatibility
- **For all tasks**: Include rollback plan

### Step 4: Ensure spec directory exists

```bash
mkdir -p docs/MVP/tasks/specs/
```

### Step 5: Update Dev Guide

After generating specs, update the Dev Guide to add/update the status table for that epic:
- Mark generated tasks as `SPEC_READY`

### Step 6: Report Summary

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

---

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