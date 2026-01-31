---
description: Implement tasks from the backlog, handling sequencing and parallelization automatically
argument-hint: "[epic_number] [--wave <N|N-M>] [--list-waves] [--parallel] [--dry-run]"
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
- `--wave <N|N-M>`: Run ONLY specified wave(s) (e.g., `--wave 1` or `--wave 1-3`)
- `--list-waves`: Output wave numbers only, one per line (for script consumption)
- `--parallel`: Enable subagent delegation for independent tasks
- `--dry-run`: Show execution plan without implementing
- `--strategy <parallel|stacked|epic-branch>`: Override the epic's default branching strategy

## Wave Filtering

If `--wave` argument is provided, only tasks in the specified wave(s) will be executed:

1. **Build full task queue** and dependency graph (as normal)
2. **Determine all waves** via topological sort
3. **Filter tasks** to only those in specified wave(s)
4. **Check completion status** - skip tasks that are already DONE
5. **Execute filtered tasks** only
6. **Exit** after specified waves complete (do not continue to other waves)

**Wave argument formats:**
- `--wave 1`: Execute only wave 1
- `--wave 2-4`: Execute waves 2, 3, and 4
- `--wave 1,3,5`: Execute waves 1, 3, and 5 (non-contiguous)

## List Waves Mode

If `--list-waves` is provided:

1. **Build dependency graph** and determine wave structure (no implementation)
2. **Output wave numbers only**, one per line:
   ```
   1
   2
   3
   4
   5
   ```
3. **Exit immediately** - no tasks are executed

This output format is designed for script consumption (e.g., by `scripts/run-epic.sh`).

## Branching Strategies

Three strategies control how tasks are branched, committed, and merged:

### 1. `parallel` (Default)
- Each task branches from `main`
- Best for: Independent tasks with no file overlap
- PRs merge independently to `main`

```
main ─────┬─────────────────────────────────────→
          ├─ feature/2-2.1 ──→ PR #1 ──→ merge
          ├─ feature/2-2.2 ──→ PR #2 ──→ merge
          └─ feature/2-2.3 ──→ PR #3 ──→ merge
```

### 2. `stacked`
- Each task branches from the previous task's branch
- Best for: Sequential tasks with significant file overlap
- PRs target parent branch, then retarget to `main` after parent merges

```
main ──┬─────────────────────────────────────────→
       └─ 2-2.1 ─┬─────────────────────→ merge to main
                 └─ 2-2.2 ─┬───────────→ merge to 2-2.1 (then main)
                           └─ 2-2.3 ───→ merge to 2-2.2 (then 2-2.1, then main)
```

### 3. `epic-branch`
- Single branch for entire epic/wave
- All tasks commit sequentially to this branch
- Best for: Tightly coupled tasks, major refactors
- One PR at wave/epic completion

```
main ──┬───────────────────────────────→
       └─ feature/epic-2 ─────────────→ single PR
           ├─ commit: 2-2.1
           ├─ commit: 2-2.2
           └─ commit: 2-2.3
```

### Strategy Configuration in Dev Guide

Strategies are defined in the Dev Guide at the epic level with optional wave overrides:

```markdown
## Epic 2: Upload & Consent (F2)
**Default Strategy**: `stacked`
**Wave Overrides**:
  - Wave 1 (2-2.1, 2-2.4): `parallel`
  - Wave 2 (2-2.5 → 2-2.6 → 2-2.7): `stacked`
```

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

6. **Handle --list-waves (if specified)**

   If `--list-waves` flag is set:
   ```
   # Output wave numbers only, one per line
   for wave_num in sorted(waves.keys()):
       print(wave_num)

   # Exit immediately - no execution
   exit(0)
   ```

   Example output:
   ```
   1
   2
   3
   4
   5
   ```

7. **Apply Wave Filter (if --wave specified)**

   If `--wave` argument is set:
   ```python
   # Parse wave specification
   if '-' in wave_arg:
       start, end = wave_arg.split('-')
       selected_waves = range(int(start), int(end) + 1)
   elif ',' in wave_arg:
       selected_waves = [int(w) for w in wave_arg.split(',')]
   else:
       selected_waves = [int(wave_arg)]

   # Filter waves
   waves = {k: v for k, v in waves.items() if k in selected_waves}

   # Check prerequisites
   for wave_num in selected_waves:
       for task in waves[wave_num]:
           for dep in task.dependencies:
               if dep.status != 'DONE':
                   # Check if dep is in an earlier selected wave
                   dep_wave = find_wave(dep)
                   if dep_wave not in selected_waves or dep_wave >= wave_num:
                       warn(f"Task {task.id} depends on {dep.id} which is not DONE")
   ```

8. **Parse Branching Strategy**

   Read strategy from Dev Guide for each epic:
   ```
   epic_strategy = parse_dev_guide_strategy(epic_number)

   # Structure:
   {
     "default": "parallel" | "stacked" | "epic-branch",
     "wave_overrides": {
       "1": {"strategy": "parallel", "tasks": ["2-2.1", "2-2.4"]},
       "2": {"strategy": "stacked", "tasks": ["2-2.5", "2-2.6", "2-2.7"]}
     }
   }
   ```

   **Priority order:**
   1. Command-line `--strategy` flag (overrides everything)
   2. Wave override from Dev Guide
   3. Epic default strategy from Dev Guide
   4. Global default: `parallel`

9. **Assign Strategy Per Wave**

   For each wave, determine its strategy:
   ```
   for wave in waves:
       # Check if any task in wave has a wave override
       wave_tasks = [task for task in wave.tasks]
       override = find_wave_override(wave_tasks, epic_strategy.wave_overrides)

       if override:
           wave.strategy = override.strategy
       else:
           wave.strategy = epic_strategy.default
   ```

### Phase 2: Display Execution Plan

```
═══════════════════════════════════════════════════════════
 EXECUTION PLAN
═══════════════════════════════════════════════════════════

Epic 2: Upload & Consent
Default Strategy: stacked
Strategy Source: Dev Guide (wave overrides active)

───────────────────────────────────────────────────────────

Wave 1 - Infrastructure [PARALLEL]:
  ⇉ 2-2.1: Supabase Storage bucket setup
  ⇉ 2-2.4: TikTok export parser
  Branching: Each task → main

Wave 2 - Backend API [PARALLEL]:
  → 2-2.2: Presigned URL API
  Branching: Task → main

Wave 3 - Frontend Integration [PARALLEL]:
  → 2-2.3: Uppy integration
  Branching: Task → main

Wave 4 - Core Upload Flow [STACKED]:
  ⊢ 2-2.5: Upload validation & error handling
  ├─ 2-2.6: Scope selection API (branches from 2-2.5)
  └─ 2-2.7: Consent screen UI (branches from 2-2.6)
  Branching: Chain → each targets previous branch
  Auto-rebase: Enabled (downstream branches updated after each merge)

Wave 5 - Integration [PARALLEL]:
  → 2-2.8: Upload page frontend
  Branching: Task → main

───────────────────────────────────────────────────────────
Total: 8 tasks across 5 waves
Strategies: 4 parallel waves, 1 stacked wave

Legend:
  ⇉ Can run in parallel (--parallel flag)
  → Sequential task
  ⊢ Stack root (branches from main)
  ├─ Stack child (branches from previous)
  └─ Stack leaf (branches from previous)

Proceed? [y/n/dry-run details]
```

If `--dry-run`, stop here.

### Phase 3: Execute Tasks

For each wave, execute based on the wave's branching strategy:

---

#### Strategy: `parallel` (Default)

For each task in the wave:

1. **Pre-Implementation Setup**
   ```bash
   # Always branch from main
   git checkout main && git pull origin main
   git checkout -b feature/{epic}-{task}-{short-name}
   ```

---

#### Strategy: `stacked`

For tasks in stacked waves, maintain a branch chain:

1. **Pre-Implementation Setup (Stacked)**
   ```bash
   # First task in stack: branch from main
   if is_first_in_stack:
       git checkout main && git pull origin main
       git checkout -b feature/{epic}-{task}-{short-name}
       stack_root = current_branch

   # Subsequent tasks: branch from previous task's branch
   else:
       git checkout {previous_task_branch}
       git checkout -b feature/{epic}-{task}-{short-name}
   ```

2. **Track Stack Chain**
   ```
   stack_chain = []
   for task in stacked_wave.tasks:
       stack_chain.append({
           "task_id": task.id,
           "branch": task.branch,
           "parent_branch": previous_task.branch or "main",
           "pr_number": None  # Set after PR creation
       })
   ```

---

#### Strategy: `epic-branch`

For epic-branch waves, all tasks share one branch:

1. **Pre-Implementation Setup (Epic Branch)**
   ```bash
   # Create epic branch if not exists
   if not epic_branch_exists:
       git checkout main && git pull origin main
       git checkout -b feature/epic-{epic_number}

   # Otherwise checkout existing epic branch
   else:
       git checkout feature/epic-{epic_number}
       git pull origin feature/epic-{epic_number}
   ```

2. **No separate branches per task** - all commits go to the epic branch

---

#### Common Steps (All Strategies)

For all tasks regardless of strategy:

1. **Pre-Implementation Setup** (Strategy-Specific)
   ```bash
   # See strategy-specific setup above
   git checkout -b feature/{epic}-{task}-{short-name}  # parallel/stacked only
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

### Phase 3.5: Create PRs and Merge (After Each Wave)

After all tasks in a wave complete (or are blocked/skipped), handle based on strategy:

---

#### Strategy: `parallel` (Default Behavior)

1. **Push branches and create PRs for completed tasks**
   ```bash
   for task in completed_tasks:
       git checkout {task.branch}
       git push -u origin {task.branch}

       gh pr create \
         --base main \
         --title "feat({scope}): {task_id} - {description}" \
         --body "$(cat <<'EOF'
   ## Task
   Implements {task_id}: {task_name} from Dev Guide

   ## Changes
   {brief summary from spec}

   ## Spec
   See: docs/MVP/tasks/specs/{spec_file}
   EOF
   )"
   ```

2. **Merge PRs independently** (no ordering required)

---

#### Strategy: `stacked`

1. **Push all branches in the stack**
   ```bash
   for task in stack_chain:
       git checkout {task.branch}
       git push -u origin {task.branch}
   ```

2. **Create PRs targeting parent branches**
   ```bash
   for task in stack_chain:
       if task.is_first_in_stack:
           base_branch = "main"
       else:
           base_branch = task.parent_branch

       gh pr create \
         --base {base_branch} \
         --head {task.branch} \
         --title "feat({scope}): {task_id} - {description}" \
         --body "$(cat <<'EOF'
   ## Task
   Implements {task_id}: {task_name} from Dev Guide

   ## Stack Position
   {position} of {total} in stacked wave
   Parent: {base_branch}
   Children: {child_branches or "None (leaf)"}

   ## Changes
   {brief summary from spec}

   ## Spec
   See: docs/MVP/tasks/specs/{spec_file}
   EOF
   )"

       task.pr_number = created_pr_number
   ```

3. **Merge in order (root first)**
   ```bash
   for task in stack_chain:  # Already ordered root-to-leaf
       # Wait for CI
       gh pr checks {task.pr_number} --watch

       if checks_passed:
           # Merge to parent (or main for root)
           gh pr merge {task.pr_number} --squash --delete-branch

           # CRITICAL: Retarget downstream PRs to main
           for downstream_task in stack_chain.after(task):
               # Update base to main since parent just merged
               gh pr edit {downstream_task.pr_number} --base main

               # Rebase downstream branch onto updated main
               git checkout {downstream_task.branch}
               git fetch origin
               git rebase origin/main
               git push --force-with-lease
       else:
           # Block all downstream tasks
           mark_downstream_blocked(task, stack_chain)
           break
   ```

4. **Auto-Rebase Logic for Stacked Strategy**

   After each PR merge in the stack:
   ```bash
   # 1. Identify remaining unmerged branches in the stack
   remaining_branches = get_unmerged_downstream(merged_branch, stack_chain)

   # 2. Rebase each onto new main
   for branch in remaining_branches:
       git checkout {branch}
       git fetch origin
       git rebase origin/main

       # Handle rebase conflicts
       if rebase_has_conflicts:
           git rebase --abort
           notify_user("Rebase conflict in {branch}. Manual resolution required.")
           mark_task_blocked(branch, "Rebase conflict after {merged_branch} merge")
           break

       # Push updated branch
       git push --force-with-lease

       # Update PR base to main
       pr_number = gh pr view {branch} --json number -q '.number'
       gh pr edit {pr_number} --base main
   ```

---

#### Strategy: `epic-branch`

1. **After all tasks in the wave complete, push the epic branch**
   ```bash
   git checkout feature/epic-{epic_number}
   git push -u origin feature/epic-{epic_number}
   ```

2. **Create a single PR for the entire wave/epic**
   ```bash
   gh pr create \
     --base main \
     --head feature/epic-{epic_number} \
     --title "feat({scope}): Epic {epic_number} - {epic_name}" \
     --body "$(cat <<'EOF'
   ## Epic Summary
   Implements Epic {epic_number}: {epic_name}

   ## Tasks Included
   {for each task: - {task_id}: {task_name}}

   ## Changes
   {combined summary from all specs}

   ## Specs
   {for each task: - docs/MVP/tasks/specs/{spec_file}}
   EOF
   )"
   ```

3. **Merge the single PR** after all CI passes

---

#### Common: Handle CI Failures

**Within a wave (parallel strategy):**
- Tasks in the same wave are independent (touch different files)
- If PR #15 (task 0.4) fails CI, PR #16 (task 0.5) can still merge
- The failed PR stays open; task marked as "CI Failed"
- Fix locally, push, CI re-runs, merge when passing

**Within a stacked wave:**
- Failures block ALL downstream tasks in the stack
- Must fix from the point of failure, not skip ahead
- The stack maintains sequential integrity

**Across waves (all strategies):**
- If ANY task in Wave N fails CI, do NOT start Wave N+1 yet
- Later waves depend on earlier waves
- Options:
  a. Fix the failing task, merge, then proceed
  b. Skip the failing task (mark BLOCKED), proceed if no dependents
  c. Stop the backlog run, report status

**Decision logic:**
```
if task_ci_failed:
    if strategy == "stacked":
        BLOCK all_downstream_in_stack  # Must fix before continuing
    elif has_dependent_tasks_in_later_waves:
        BLOCK later_waves  # Must fix before continuing
    else:
        CONTINUE  # Independent task, can fix later
```

---

#### Common: Update Tracking After Merges

For all strategies:
- Spec files: Set `**Merged**: Yes (YYYY-MM-DD)`
- Spec files: Set `**Branch**: Deleted (merged via PR #{number})`
- Dev Guide: Set Merged column to `Yes`
- Commit: `git commit -m "docs: update merge status for wave N"`

Proceed to next wave (which can now use merged code)

### Phase 4: Summary Report

```
═══════════════════════════════════════════════════════════
 IMPLEMENTATION COMPLETE
═══════════════════════════════════════════════════════════

Epic 2: Upload & Consent
Strategy: stacked (with wave overrides)

───────────────────────────────────────────────────────────

Wave 1 [PARALLEL] - Complete:
  ✓ PR #12: feat(storage): 2-2.1 - Supabase Storage bucket [merged]
  ✓ PR #13: feat(parser): 2-2.4 - TikTok export parser [merged]

Wave 2 [PARALLEL] - Complete:
  ✓ PR #14: feat(api): 2-2.2 - Presigned URL API [merged]

Wave 3 [PARALLEL] - Complete:
  ✓ PR #15: feat(upload): 2-2.3 - Uppy integration [merged]

Wave 4 [STACKED] - Partial:
  ✓ PR #16: feat(upload): 2-2.5 - Upload validation [merged → main]
  ✓ PR #17: feat(upload): 2-2.6 - Scope selection [merged → main, rebased after #16]
  ✗ PR #18: feat(consent): 2-2.7 - Consent screen [CI failed: type errors]
    → Stack blocked at this point
    → Auto-rebase was successful, CI failure is in new code

Wave 5 [PARALLEL] - Not started (waiting on Wave 4):
  ○ 2-2.8: Upload page frontend [blocked by 2-2.7]

───────────────────────────────────────────────────────────
Summary:
  Merged: 6 PRs (4 parallel, 2 stacked)
  CI Failed: 1 PR (2-2.7 - type errors in consent component)
  Blocked: 1 task (depends on 2-2.7)
  Stacked merges: 2/3 successful (auto-rebase worked)

Next steps:
  1. Fix CI failures for PR #18 (2-2.7: Consent screen)
  2. Run: /implement-backlog 2 (to continue from Wave 4)
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
