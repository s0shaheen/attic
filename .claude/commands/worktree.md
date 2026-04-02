---
description: Create a git worktree for parallel feature work
argument-hint: "branch-name"
---

1. Run `git worktree list` to show current worktrees
2. Create the worktree: `git worktree add ../attic-$ARGUMENTS $ARGUMENTS`
   - If the branch doesn't exist yet, use `-b` to create it from main
3. Copy `.env.master` into the new worktree if it exists
4. Run `cd ../attic-$ARGUMENTS && npm install --prefix src/frontend`
5. Run `cd ../attic-$ARGUMENTS && python -m venv .venv && .venv/bin/pip install -e "src/backend[dev]"`
6. Print: "Worktree ready at ../attic-$ARGUMENTS"
7. Print: "Open it: code ../attic-$ARGUMENTS"
