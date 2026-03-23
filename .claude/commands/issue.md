---
description: Create a well-formed GitHub issue from a description. Enforces the project's issue template and prevents vague parking-lot items.
argument-hint: "description of what needs to happen"
---

## Quality gate

Before creating the issue, evaluate the description against these criteria:

**An issue must have a clear deliverable.** If the description is vague ("improve classification"), ask: "What specifically would be different when this is done? What would you test to verify it's complete?"

**An issue must be a single thing.** If the description contains "and" connecting two unrelated changes, split it into two issues.

**An issue must not be a research question.** "Investigate why affect accuracy is low" is not an issue — it's a notebook session. Instead: "Fix affect misclassification on nostalgia content" with a clear acceptance criterion.

If the description fails these checks, push back and help the user refine it before creating.

## Template

```markdown
## What
{One sentence — what changes in the product/codebase}

## Why
{User-facing impact or technical necessity. Not "because we should" — what gets better?}

## Acceptance Criteria
{2-5 checkboxes. Each must be binary verifiable — you can look at the result and say yes or no.}
- [ ] {specific thing that must be true}
- [ ] {specific thing that must be true}
- [ ] Tests pass for the changed code

## Files Touched
{List files this will modify. Use "NEW: path" for new files. This helps CC agents understand scope.}

## Not In Scope
{What this does NOT include — prevents scope creep}
```

## Steps

1. **Generate the issue body** using the template above, derived from the user's description.

2. **Determine labels** (pick one from each applicable dimension):
   - Component: `agent`, `backend`, `frontend`, `pipeline`, `workbench`
   - If it can be done by CC without founder input: `autonomous`
   - If it needs founder decisions: `founder-only`

3. **Create the issue**
   ```bash
   gh issue create \
     --title "{concise title}" \
     --body "{formatted body}" \
     --label "{labels}"
   ```

4. **Report**
   ```
   Created issue #{N}: {title}
   URL: {url}
   
   To start working on it: /branch "{short-desc}" --issue {N}
   ```
