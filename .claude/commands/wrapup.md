---
description: "Session handoff: summarize conversation flow, changes made, current state, next steps, and limitations."
---

## Purpose

Generate a detailed session summary so the next conversation (or future-you) can pick up where this one left off. This replaces manually asking "write a summary of what we did."

## Step 1: Conversation flow

Reconstruct what happened in this session chronologically. For each major phase:
- What was the goal / what did the user ask for
- What approach was taken
- What was the outcome (succeeded, pivoted, deferred, abandoned)

Write this as a narrative, not a bullet list. Include pivots and surprises — "Started with X, discovered Y, pivoted to Z." The flow should read like a short story of the session.

## Step 2: Changes made

### Git state
```bash
git status --porcelain
git diff --stat
git log --oneline -10
```

Summarize:
- **Committed**: list commits made this session with one-line descriptions
- **Uncommitted**: list modified/new files with what changed in each
- **Branch**: current branch and its relationship to main

### Non-code artifacts
Note any changes to:
- Plan files, sprint logs, experiment results
- CLAUDE.md, MEMORY.md, or other configuration
- Issues created/updated/closed (check `gh issue list --state all --limit 5`)
- PRs created or updated

## Step 3: Current state

Describe where things stand right now:
- What's working that wasn't before
- What's broken or incomplete
- Any processes still running (background tasks, deploys, long-running ops)
- Environment state (are servers running? which database is connected?)

## Step 4: Known next steps

List concrete next actions, ordered by priority:
1. What should happen next in the current work stream
2. Decisions that need to be made (flag if they need user input vs. can be autonomous)
3. Follow-up items discovered during the session

For each item, note whether it's:
- **Ready** — can be picked up immediately
- **Blocked** — needs something first (specify what)
- **Needs decision** — user must choose an approach

## Step 5: Limitations and risks

Be honest about:
- Things that were tried but didn't work (and why)
- Shortcuts taken that may need revisiting
- Areas where the approach might not scale or might have edge cases
- Technical debt introduced intentionally
- Any "it works but I'm not sure why" situations

## Output format

Write the full summary as a single markdown document. Use `##` headers for each section. Be specific and concrete — names, file paths, issue numbers, exact error messages. The reader has zero context from this session.

Print the summary directly in the conversation. Do NOT write it to a file unless the user asks.
