---
description: Create a new feature branch with proper naming and optional GitHub issue linking.
argument-hint: "short-description [--issue N]"
---

## Steps

1. **Ensure clean state**
   ```bash
   git status --porcelain
   ```
   If uncommitted changes exist, warn: "You have uncommitted changes. Stash or commit first."

2. **Start from latest main**
   ```bash
   git checkout main
   git pull origin main
   ```

3. **Create branch**

   Branch naming convention: `s0shaheen/issue-{N}-{short-description}` if issue provided, otherwise `s0shaheen/{short-description}`

   ```bash
   # With issue
   git checkout -b s0shaheen/issue-{N}-{short-description}
   
   # Without issue
   git checkout -b s0shaheen/{short-description}
   ```

   Rules for `short-description`:
   - Lowercase, hyphens between words
   - Max 40 characters
   - No special characters
   - Descriptive: `improve-affect-classification`, not `fix-stuff`

4. **Report**
   ```
   Created branch: s0shaheen/issue-{N}-{short-description}
   Based on: main ({commit hash})
   {If issue}: Linked to #{N}: {issue title}
   
   Ready to work. When done: /preflight then /ship "description"
   ```
