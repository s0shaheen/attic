---
description: Implement tasks from the backlog, handling sequencing and parallelization automatically
argument-hint: "[epic_number] [--parallel] [--dry-run]"
---

## Mission

Implement tasks from validated specs. Automatically determine correct sequencing based on dependencies. Use subagents for parallelizable work when `--parallel` flag is provided.

## Arguments

- `epic_number` (optional): Limit to specific epic. Without this, processes all ready specs.
- `--parallel`: Enable subagent delegation for independent tasks
- `--dry-run`: Show execution plan without implementing

## Instructions

### Phase 1: Build Task Queue

1. **Gather Specs**
   ```
   If epic specified:
     specs = docs/MVP/tasks/specs/{epic}-*.md
   Else:
     specs = docs/MVP/tasks/specs/*.md
   
   Filter to: Status in [NOT_STARTED, SPEC_READY, IN_PROGRESS]
   Exclude: Status in [DONE, BLOCKED]
   ```

2. **Parse Dependencies**
   
   For each spec, extract:
   - Task ID (from filename: `{epic}-{task}.md` → `{epic}.{task}`)
   - Dependencies (from "Tasks that must complete first")
   - Components touched (from "Files to create/modify")

3. **Build Dependency Graph**
   ```
   graph = {}
   for spec in specs:
       graph[spec.task_id] = {
           "depends_on": spec.dependencies,
           "components": spec.components,
           "status": spec.status
       }
   ```

4. **Detect Issues**
   - Circular dependencies → ERROR, list the cycle
   - Missing dependencies (referenced but no spec) → ERROR, list missing
   - Unvalidated specs → WARN, suggest running /validate-specs

5. **Determine Execution Waves**

   Apply topological sort with parallelization:
   ```
   Wave 1: Tasks with no dependencies (or all deps DONE)
   Wave 2: Tasks depending only on Wave 1
   Wave 3: Tasks depending on Wave 1 or 2
   ...
   ```

   Within each wave, identify parallelizable tasks:
   - Tasks touching DIFFERENT files/components can run in parallel
   - Tasks touching SAME files must be sequential within wave

### Phase 2: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 EXECUTION PLAN
═══════════════════════════════════════════════════════════

Wave 1 - Foundation (Sequential):
  → 0.1: Backend project scaffolding
  → 0.2: Frontend project scaffolding

Wave 2 - Infrastructure (Parallel Eligible):
  ⇉ 0.3: Supabase project setup [can parallel]
  ⇉ 0.5: AWS infrastructure setup [can parallel]
  
Wave 3 - Database (Sequential, depends on 0.3):
  → 0.4: Database migrations

Wave 4 - Services (Parallel Eligible):
  ⇉ 0.6: CI/CD pipeline [can parallel]
  ⇉ 0.7: Local development environment [can parallel]

───────────────────────────────────────────────────────────
Total: 7 tasks across 4 waves
Estimated time: ~2-3 hours (faster with --parallel)

Proceed? [y/n/dry-run details]
```

If `--dry-run`, stop here.

### Phase 3: Execute Tasks

For each wave, for each task:

1. **Pre-Implementation Setup**
   ```bash
   # Create feature branch
   git checkout -b feature/{epic}-{task}-{short-name}
   ```

2. **Load Context**
   - Read the task's spec file completely
   - Read each file in "Context References"
   - Load relevant skills if task involves Supabase, Lambda, etc.

3. **Decide: Main Agent vs Subagent**

   **Use Main Agent when:**
   - First task in an epic (establishes patterns)
   - Task creates shared infrastructure (migrations, base classes)
   - Task is sole item in its wave
   - `--parallel` flag not provided

   **Use Subagent when:**
   - `--parallel` flag provided AND
   - Multiple tasks in same wave AND
   - Tasks touch different file sets AND
   - Task doesn't establish foundational patterns

4. **Execute Implementation**

   **If Main Agent:**
   
   Follow this order strictly:
   
   a. **Data Contracts** (10%)
      - Create Pydantic models in `src/backend/app/models/`
      - Create Zod schemas in `src/frontend/lib/schemas/`
      - Create TypeScript types if needed
   
   b. **Database Migrations** (20%) - if needed
      ```bash
      cd src/backend
      alembic revision --autogenerate -m "{task}: {description}"
      # Review the generated migration
      alembic upgrade head
      ```
   
   c. **Core Implementation** (50%)
      - Follow existing patterns in codebase
      - Type hints on everything (Python)
      - Strict mode compliance (TypeScript)
      - Write unit tests alongside each function
   
   d. **Integration Tests** (15%)
      - API endpoint tests
      - Database interaction tests
   
   e. **Verification** (5%)
      ```bash
      # Python
      cd src/backend && pytest tests/ -v --tb=short
      cd src/backend && ruff check . && ruff format .
      
      # TypeScript
      cd src/frontend && npm run typecheck
      cd src/frontend && npm run lint
      cd src/frontend && npm test
      ```

   **If Subagent:**
   
   Delegate with full context:
   ```
   Use the implementer subagent to implement task {task_id}.
   
   Spec file: docs/MVP/tasks/specs/{spec_file}
   Branch name: feature/{epic}-{task}-{short-name}
   
   Context files to read:
   - {context_file_1}
   - {context_file_2}
   - CLAUDE.md
   
   Implementation order:
   1. Data contracts first
   2. Database migrations if needed
   3. Core implementation with unit tests
   4. Integration tests
   5. Run all verification commands
   
   Update the spec file with progress.
   Report back: DONE | FAILED (with error) | BLOCKED (with reason)
   ```

5. **After Each Task Completes**
   
   a. **Update Spec File**
      - Move completed requirements to "Completed" section
      - Add any implementation notes
      - Set Status: `IN_PROGRESS` → `DONE` (or `BLOCKED` if issues)
   
   b. **Update Dev Guide**
      - Update status in epic's status table
   
   c. **Commit**
      ```bash
      git add -A
      git commit -m "feat({scope}): implement {task_id} - {description}"
      ```

6. **Handle Failures**

   **If tests fail:**
   - Log failure details to spec's Implementation Notes
   - Set status to `BLOCKED`
   - Add to "Blocked By": "Tests failing: {summary}"
   - Continue to next task (don't stop entire backlog)
   
   **If subagent reports BLOCKED:**
   - Update spec with blocker details
   - Set status to `BLOCKED`
   - Continue to next task
   
   **If dependency not ready:**
   - Skip task, it will be picked up in next run

### Phase 4: Summary Report

```
═══════════════════════════════════════════════════════════
 IMPLEMENTATION COMPLETE
═══════════════════════════════════════════════════════════

Completed: 5 tasks
  ✓ 0.1: Backend project scaffolding
  ✓ 0.2: Frontend project scaffolding
  ✓ 0.3: Supabase project setup
  ✓ 0.5: AWS infrastructure setup
  ✓ 0.6: CI/CD pipeline

Blocked: 1 task
  ✗ 0.4: Database migrations
    Reason: Supabase connection failed (check .env.local)

Skipped: 1 task
  ○ 0.7: Local development environment
    Reason: Depends on blocked task 0.4

───────────────────────────────────────────────────────────
Branches created:
  - feature/0-0.1-backend-scaffolding
  - feature/0-0.2-frontend-scaffolding
  - feature/0-0.3-supabase-setup
  - feature/0-0.5-aws-infrastructure
  - feature/0-0.6-cicd-pipeline

Next steps:
  1. Fix blocker for 0.4 (check Supabase credentials)
  2. Run: /implement-backlog 0 (to continue)
```

## Subagent Coordination (--parallel mode)

When running parallel subagents:

1. **Launch subagents for independent tasks:**
   ```
   [Main] Launching Wave 2 in parallel:
   
   [Subagent A] Starting: 0.3 Supabase setup
   [Subagent B] Starting: 0.5 AWS infrastructure
   
   Monitoring for completion...
   ```

2. **Monitor and collect results:**
   ```
   [Subagent A] ✓ Complete: 0.3 (took 12 minutes)
   [Subagent B] ✓ Complete: 0.5 (took 18 minutes)
   
   Wave 2 complete. Proceeding to Wave 3...
   ```

3. **Handle subagent failures:**
   ```
   [Subagent B] ✗ Failed: 0.5
     Error: AWS credentials invalid
     
   [Main] Marking 0.5 as BLOCKED
   [Main] Tasks depending on 0.5 will be skipped
   [Main] Continuing with remaining tasks...
   ```
