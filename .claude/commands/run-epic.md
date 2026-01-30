---
description: Chain the full epic lifecycle with automatic CI monitoring
argument-hint: "<epic_number> [--dry-run] [--auto-merge] [--resume]"
---

## Mission

Run the complete epic lifecycle from spec generation through implementation, CI monitoring, and merge. This is the top-level orchestrator that chains `/generate-specs`, `/validate-specs`, and `/implement-backlog` with additional CI and merge automation.

## Orchestrator Discipline (CRITICAL)

To prevent auto-compaction of the main conversation:

**The orchestrator MUST NOT:**
- Read implementation files (source code, tests)
- Write or edit any source code directly
- Debug test failures or lint errors (delegate to ci-fixer agent)
- Analyze stack traces or error details
- Accumulate implementation context

**The orchestrator MUST:**
- Only read spec files for task metadata (ID, status, dependencies)
- Only read Dev Guide for status tracking
- Delegate ALL implementation work to subagents via /implement-backlog
- Delegate CI fixes to ci-fixer agent
- Delegate conflict resolution to conflict-resolver agent
- Accept subagent status reports at face value
- Persist state for resumability

## Arguments

- `epic_number` (required): The epic number to run (e.g., 2)
- `--dry-run`: Show execution plan without implementing
- `--auto-merge`: Automatically merge passing PRs (default: create PRs only)
- `--resume`: Resume from last saved state (reads from `.claude/epic-runs/`)
- `--parallel`: Enable parallel subagent delegation (passed to implement-backlog)
- `--skip-specs`: Skip spec generation/validation phases

## State Persistence

Epic runs save state to `.claude/epic-runs/{epic}-{timestamp}.json`:

```json
{
  "epic": 2,
  "started_at": "2026-01-30T10:00:00Z",
  "current_phase": "implementation",
  "completed_phases": ["preflight", "spec_generation"],
  "tasks": {
    "2.1": {"status": "done", "pr": 15, "merged": true},
    "2.2": {"status": "in_progress", "pr": null, "merged": false},
    "2.3": {"status": "pending", "pr": null, "merged": false}
  },
  "errors": [],
  "last_updated": "2026-01-30T12:30:00Z"
}
```

## Instructions

### Phase 0: Resume Check (if --resume)

If `--resume` flag is set:

1. **Find Latest State File**
   ```bash
   LATEST=$(ls -t .claude/epic-runs/{epic}-*.json 2>/dev/null | head -1)
   ```

2. **Load State**
   - Parse the JSON state file
   - Identify `current_phase` and `completed_phases`
   - Skip completed phases
   - Resume from last incomplete phase

3. **Display Resume Info**
   ```
   ═══════════════════════════════════════════════════════════
    RESUMING EPIC RUN
   ═══════════════════════════════════════════════════════════

   State file: .claude/epic-runs/2-20260130-100000.json
   Started: 2026-01-30T10:00:00Z
   Last updated: 2026-01-30T12:30:00Z

   Completed phases:
     ✓ Pre-flight
     ✓ Spec Generation

   Current phase: Implementation
   Tasks: 1 done, 1 in_progress, 6 pending

   Resuming from Phase 3: Implementation...
   ───────────────────────────────────────────────────────────
   ```

---

### Phase 1: Pre-flight

1. **Verify Main is Up-to-Date**
   ```bash
   git checkout main
   git fetch origin
   git status  # Check if behind origin/main
   ```

   If behind:
   ```bash
   git pull origin main
   ```

2. **Check Previous Epic Dependencies**

   Read Dev Guide and verify all tasks from previous epics that this epic depends on are DONE:
   ```
   Epic 2 depends on:
     - Epic 0: All tasks DONE ✓
     - Epic 1: All tasks DONE ✓
   ```

   If dependencies not met, list blocked tasks and ask user how to proceed.

3. **Validate No Failing CI on Main**
   ```bash
   gh run list --branch main --limit 1 --json conclusion
   ```

   If last CI run failed:
   - Display warning
   - Ask user if they want to proceed anyway

4. **Create State File**
   ```bash
   mkdir -p .claude/epic-runs
   STATE_FILE=".claude/epic-runs/${EPIC}-$(date +%Y%m%d-%H%M%S).json"
   ```

   Initialize with:
   ```json
   {
     "epic": 2,
     "started_at": "timestamp",
     "current_phase": "preflight",
     "completed_phases": [],
     "tasks": {},
     "errors": []
   }
   ```

5. **Display Pre-flight Summary**
   ```
   ═══════════════════════════════════════════════════════════
    EPIC RUN: Epic {N}
   ═══════════════════════════════════════════════════════════

   Pre-flight checks:
     ✓ Main branch up-to-date
     ✓ Epic dependencies satisfied
     ✓ CI passing on main

   Proceeding to spec generation...
   ───────────────────────────────────────────────────────────
   ```

---

### Phase 2: Spec Generation (if --skip-specs not set)

1. **Generate Specs for NOT_STARTED Tasks**

   Invoke the generate-specs skill:
   ```
   /generate-specs {epic}
   ```

   This will:
   - Find all NOT_STARTED tasks for the epic
   - Generate spec files from Dev Guide entries
   - Create files at `docs/MVP/tasks/specs/{epic}-{task}.md`

2. **Validate Specs**

   Invoke the validate-specs skill:
   ```
   /validate-specs {epic}
   ```

   This will:
   - Check specs against PRD requirements
   - Verify API contracts are complete
   - Flag any issues

3. **Commit Spec Files**
   ```bash
   git add docs/MVP/tasks/specs/
   git commit -m "docs: generate specs for epic ${EPIC}"
   ```

4. **Update State**
   - Add "spec_generation" to completed_phases
   - Set current_phase to "implementation"

---

### Phase 3: Implementation

1. **Delegate to implement-backlog**

   Invoke the implement-backlog skill with the epic number:
   ```
   /implement-backlog {epic} --parallel
   ```

   This handles:
   - Building dependency graph
   - Determining execution waves
   - Spawning implementer subagents
   - Creating feature branches
   - Running tests

2. **Monitor Subagent Completion**

   For each task completed by implement-backlog:
   - Update state file with task status
   - Record any errors

3. **Handle Blocked Tasks**

   If implement-backlog reports blocked tasks:
   - Record in state file
   - Continue with unblocked tasks
   - Report blocked tasks at end

---

### Phase 4: CI Monitoring & Merge

For each completed task (with committed code):

1. **Push and Create PR**
   ```bash
   git checkout feature/{epic}-{task}-{name}
   git push -u origin feature/{epic}-{task}-{name}

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

2. **Wait for CI**
   ```bash
   gh pr checks {pr_number} --watch --interval 30
   ```

   Timeout: 15 minutes per PR

3. **Handle CI Results**

   **If CI passes and --auto-merge:**
   ```bash
   gh pr merge {pr_number} --squash --delete-branch
   ```

   Update state:
   ```json
   {"2.1": {"status": "done", "pr": 15, "merged": true}}
   ```

   **If CI fails:**

   a. Spawn ci-fixer agent:
   ```
   Task tool:
     subagent_type: ci-fixer
     description: "Fix CI for PR #{pr_number}"
     prompt: |
       Fix the CI failures for PR #{pr_number}.
       Branch: feature/{branch-name}

       Report back: FIXED | UNFIXABLE (with reason)
   ```

   b. If ci-fixer reports FIXED:
   - Push fixes
   - Wait for CI again
   - Max 2 fix attempts

   c. If ci-fixer reports UNFIXABLE or max attempts reached:
   - Mark task as CI_FAILED
   - Continue with other tasks
   - Report at end

4. **Handle Merge Conflicts**

   If PR has merge conflicts:

   a. Spawn conflict-resolver agent:
   ```
   Task tool:
     subagent_type: conflict-resolver
     description: "Resolve conflicts for PR #{pr_number}"
     prompt: |
       Resolve merge conflicts for PR #{pr_number}.
       Branch: feature/{branch-name}

       Report back: RESOLVED | UNRESOLVABLE (with reason)
   ```

   b. If resolved, push and re-run CI check

   c. If unresolvable, mark as CONFLICT and report

---

### Phase 5: Retrospective

1. **Update All Spec Files**

   For merged tasks:
   ```markdown
   **Status**: DONE
   **Merged**: Yes (PR #{number})
   **Last Updated**: {date}
   ```

2. **Update Dev Guide Status Table**

   For each task, update the status table in Dev Guide.

3. **Generate Summary Report**

   ```
   ═══════════════════════════════════════════════════════════
    EPIC RUN COMPLETE
   ═══════════════════════════════════════════════════════════

   Epic 2: Upload & Consent
   Duration: 2h 45m
   State file: .claude/epic-runs/2-20260130-100000.json

   ───────────────────────────────────────────────────────────

   Tasks Summary:
     ✓ 2.1: Supabase Storage bucket (PR #15, merged)
     ✓ 2.2: Presigned URL API (PR #16, merged)
     ✓ 2.3: Uppy integration (PR #17, merged)
     ✓ 2.4: TikTok export parser (PR #18, merged)
     ✗ 2.5: Upload validation (PR #19, CI failed - type errors)
     ○ 2.6: Scope selection (blocked by 2.5)
     ○ 2.7: Consent screen (blocked by 2.6)
     ○ 2.8: Upload page (blocked by 2.7)

   ───────────────────────────────────────────────────────────

   Results:
     Completed: 4 tasks
     CI Failed: 1 task
     Blocked: 3 tasks

   Next steps:
     1. Fix CI failures for PR #19 (2.5: type errors in validation)
     2. Run: /run-epic 2 --resume

   ───────────────────────────────────────────────────────────
   ```

4. **Send Notification (if configured)**

   If `SLACK_WEBHOOK_URL` environment variable is set:
   ```bash
   curl -X POST "$SLACK_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Epic 2 run complete: 4 merged, 1 failed, 3 blocked",
       "blocks": [...]
     }'
   ```

---

## Dry Run Mode

If `--dry-run` is set, display the full execution plan without making changes:

```
═══════════════════════════════════════════════════════════
 DRY RUN: Epic {N}
═══════════════════════════════════════════════════════════

Phase 1: Pre-flight
  - Will verify main is up-to-date
  - Will check epic dependencies
  - Will validate CI status

Phase 2: Spec Generation
  - Will generate specs for: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
  - Will validate specs against PRD

Phase 3: Implementation (via /implement-backlog)
  - Wave 1 [PARALLEL]: 2.1, 2.4
  - Wave 2: 2.2
  - Wave 3: 2.3
  - Wave 4 [STACKED]: 2.5 → 2.6 → 2.7
  - Wave 5: 2.8

Phase 4: CI & Merge
  - Will create 8 PRs
  - Will wait for CI on each
  - Auto-merge: {Yes|No}

Phase 5: Retrospective
  - Will update spec files
  - Will update Dev Guide
  - Will generate summary

───────────────────────────────────────────────────────────
Estimated: 8 tasks across 5 waves
To execute: /run-epic {N}
───────────────────────────────────────────────────────────
```

---

## Error Handling

### Transient Errors (retry)
- Network timeouts → Retry 3x with exponential backoff
- GitHub API rate limits → Wait and retry
- git push conflicts → Pull, rebase, push

### Recoverable Errors (delegate to agent)
- CI failures → ci-fixer agent (max 2 attempts)
- Merge conflicts → conflict-resolver agent

### Unrecoverable Errors (save state and report)
- Missing secrets/credentials → Save state, report, exit
- Spec validation failures → Save state, report, prompt user
- Agent repeated failures → Mark task blocked, continue with others

### State Recovery

If run-epic crashes or is interrupted:
```bash
/run-epic {N} --resume
```

This loads the last state file and continues from where it left off.

---

## Integration with GitHub Actions

This command can be invoked from the `claude-code-remote.yml` workflow:

```yaml
- name: Run Epic
  run: |
    claude --dangerously-skip-permissions "/run-epic ${{ inputs.epic_number }} --auto-merge"
```

The state file and summary are committed back to the repo for visibility.
