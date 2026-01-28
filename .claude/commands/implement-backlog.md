---
description: Implement tasks from the backlog, handling sequencing and parallelization automatically
argument-hint: "[epic_number] [--parallel] [--dry-run]"
---

## Mission

Implement tasks from validated specs. Automatically determine correct sequencing based on dependencies. **ALL implementation is delegated to subagents** to prevent context bloat in the main orchestrator.

## Orchestrator Discipline (CRITICAL)

To prevent auto-compaction of the main conversation:

**The orchestrator MUST NOT:**
- Read implementation files (source code, tests)
- Write or edit any source code directly
- Debug test failures or lint errors
- Analyze stack traces or error details
- Accumulate implementation context

**The orchestrator MUST:**
- Only read spec files for task metadata (ID, status, dependencies)
- Only read Dev Guide for status tracking
- Delegate ALL implementation work to subagents
- Run subagents in background (`run_in_background: true`)
- Accept subagent status reports at face value
- Escalate to user ONLY when subagent reports BLOCKED with `NEEDS_USER` flag

**Context Budget:**
The orchestrator should stay under ~20% of context window by:
- Spawning subagents for any file reading/writing
- Never requesting code snippets in subagent responses
- Trusting subagent completion reports

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

3. **ALWAYS Delegate to Subagent**

   **CRITICAL**: To prevent context bloat and auto-compaction, the orchestrator
   NEVER implements directly. Every task is delegated to an implementer subagent.

   The orchestrator's role is ONLY to:
   - Build and display the execution plan
   - Spawn subagents (sequentially or in parallel)
   - Monitor subagent status via their reports
   - Update Dev Guide with final status
   - Handle critical escalations that require user input

   **Sequential Mode (default):**
   - Spawn ONE subagent at a time
   - Wait for DONE/FAILED/BLOCKED before spawning next
   - Run subagents in background to preserve orchestrator context

   **Parallel Mode (--parallel flag):**
   - Spawn multiple subagents for independent tasks in same wave
   - Wait for all to complete before proceeding to next wave

4. **Spawn Implementer Subagent**

   Delegate with full context using the Task tool:
   ```
   Task tool parameters:
     subagent_type: implementer
     run_in_background: true   # CRITICAL: Prevents context bloat
     description: "Implement {task_id}"
     prompt: |
       Implement task {task_id}.

       Spec file: docs/MVP/tasks/specs/{spec_file}
       Branch name: feature/{epic}-{task}-{short-name}

       Context files to read:
       - {context_file_1}
       - {context_file_2}
       - CLAUDE.md

       Report back: DONE | FAILED (with error) | BLOCKED (with reason)
   ```

   **Monitoring Background Subagents:**
   - The Task tool returns an `output_file` path
   - Check progress periodically: `Read` the output file or `Bash(tail -50 {output_file})`
   - Wait for the subagent to report DONE/FAILED/BLOCKED before proceeding
   - For parallel mode: launch multiple subagents, then monitor all output files

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

6. **Handle Subagent Responses**

   Read the subagent's output file and parse the final status:

   **If DONE:**
   - Update spec status to `DONE`
   - Update Dev Guide status table
   - Proceed to merge step
   - Continue to next task

   **If FAILED:**
   - Update spec status to `BLOCKED`
   - Add failure reason to spec's Implementation Notes
   - DO NOT attempt to debug (you lack context)
   - Continue to next task

   **If BLOCKED (without NEEDS_USER):**
   - Update spec with blocker details
   - Set status to `BLOCKED`
   - Continue to next task (will be retried later)

   **If BLOCKED: NEEDS_USER:**
   - STOP and surface to user immediately
   - Display the decision/question to user
   - Wait for user input before continuing
   - This is the ONLY case where orchestrator pauses for intervention

   **If subagent appears stuck (no output for extended period):**
   - Check output file for progress
   - If truly stuck, mark as `BLOCKED: Subagent timeout`
   - Continue to next task

### Phase 3.5: Merge Completed Tasks (After Each Wave)

After all tasks in a wave complete (or are blocked/skipped):

1. **Collect completed branches for this wave**
   ```
   completed_branches = [task.branch for task in wave if task.status == DONE]
   ```

2. **Merge each completed branch to main**
   ```bash
   git checkout main
   git pull origin main 2>/dev/null || true

   for branch in completed_branches:
       git merge {branch} --no-ff -m "Merge {task_id}: {description}"
       if merge_failed:
           git merge --abort
           mark task as "Merge Conflict"
           continue
       git branch -d {branch}
   ```

3. **Update tracking after merges**
   - Spec files: Set `**Merged**: Yes (YYYY-MM-DD)`
   - Dev Guide: Set Merged column to `Yes`
   - Commit tracking updates: `git commit -m "docs: update merge status for wave N"`

4. **Proceed to next wave** (which can now use merged code)

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
Merged to main:
  ✓ feature/0-0.1-backend-scaffolding
  ✓ feature/0-0.2-frontend-scaffolding
  ✓ feature/0-0.3-supabase-setup
  ✓ feature/0-0.5-aws-infrastructure
  ✓ feature/0-0.6-cicd-pipeline

Merge conflicts (manual resolution needed):
  ✗ {none or list branches with conflicts}

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
