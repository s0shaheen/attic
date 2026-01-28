---
description: Triage new work - capture, prioritize, and route to appropriate next step
argument-hint: "[description of work]"
---

## Mission

Structured intake for emerging work that isn't already in the Dev Guide. Determines scope, priority, and routes to the appropriate next action. This is the single entrypoint for ALL ad-hoc work.

## Instructions

### Phase 1: Understand the Work

If the argument is vague, ask clarifying questions. Gather:

1. **What triggered this?**
   - Bug found during development
   - Tech debt discovered
   - New requirement emerged
   - Dependency upgrade needed
   - Performance issue
   - Security concern
   - Testing gap

2. **What's the scope?**
   - **Quick fix**: <30 min, no spec needed, just do it
   - **Single task**: Discrete piece of work, fits in existing epic
   - **Multi-task feature**: Related tasks, may need new epic section
   - **New epic**: Significant new area of functionality

3. **What's the urgency?**
   - 🔴 **Blocking**: Can't continue current work without this
   - 🟡 **Soon**: Natural implementation point coming up, or near-term dependency
   - 🟢 **Backlog**: Important but not time-sensitive

4. **Are there dependencies?**
   - What tasks must complete before this?
   - What tasks are blocked by this?
   - Is there a natural sequencing point?

### Phase 2: Read Context

Before making recommendations, read:
- `docs/MVP/tasks/BACKLOG.md` - Check for related items, get next ID
- `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` - Understand current epic structure
- Relevant PRD sections if this relates to product requirements
- Relevant codebase files if this is tech debt or bug fix

### Phase 3: Categorize and Estimate

Based on gathered information:

**Category** (pick one):
- `Infra` - Infrastructure, tooling, CI/CD, environment
- `Feature` - User-facing functionality
- `Tech Debt` - Code quality, refactoring, upgrades
- `Bug Fix` - Defect correction
- `Testing` - Test coverage, test data, test infrastructure
- `Docs` - Documentation updates

**LOE** (Level of Effort):
- `XS` - Less than 1 hour
- `S` - 1-4 hours
- `M` - 4-8 hours (half day to full day)
- `L` - 1-2 days
- `XL` - 3+ days (consider breaking down)

**Target Epic** (if applicable):
- Existing epic number (0-9) if it fits
- "New" if it warrants its own epic
- "TBD" if unclear

### Phase 4: Route

Based on scope assessment:

#### If Quick Fix (XS scope, <30 min)
```
This looks like a quick fix. No formal intake needed.
Would you like me to just do it now?
```
- Don't add to backlog
- Just execute if user confirms

#### If Ready for Spec (clear scope, no design questions)
1. Assign next backlog ID from `docs/MVP/tasks/BACKLOG.md`
2. Add entry to "Ready for Spec" section
3. Ask: "Generate spec now or queue for later?"
4. If now → provide command: `/generate-specs B-XXX`

#### If Needs Design (scope unclear, technical decisions needed)
1. Assign next backlog ID
2. Add entry to "Needs Design" section with open questions
3. Ask: "Would you like to start the design conversation now?"
4. If yes → invoke `designer` agent with context
5. If no → confirm item is captured for later

#### If Icebox (not prioritized)
1. Assign next backlog ID
2. Add entry to "Icebox" section
3. Confirm captured: "Added to icebox. Will review during next planning."

### Phase 5: Update Backlog

After routing decision, update `docs/MVP/tasks/BACKLOG.md`:

1. Increment the "Next Available ID" counter
2. Add the entry to the appropriate section
3. Fill all relevant columns

### Output Format

Always end with a structured summary:

```
═══════════════════════════════════════════════════════════
 INTAKE COMPLETE
═══════════════════════════════════════════════════════════

ID:        B-{XXX}
Title:     {Concise title}
Category:  {Infra | Feature | Tech Debt | Bug Fix | Testing | Docs}
Scope:     {Quick Fix | Single Task | Multi-Task | New Epic}
LOE:       {XS | S | M | L | XL}
Urgency:   {🔴 Blocking | 🟡 Soon | 🟢 Backlog}
Target:    {Epic X | New Epic | TBD}

Decision:  {What was decided}
Status:    {Added to Ready | Added to Needs Design | Added to Icebox | Completed}

Next Action: {Specific next step with command if applicable}
───────────────────────────────────────────────────────────
```

## Examples

### Example 1: Test Data Fixtures
```
User: /intake We need test data fixtures for the media_events table

Intake Summary:
- Trigger: Testing gap discovered during implementation
- Scope: Single task (create fixtures, possibly factory pattern)
- Urgency: 🟡 Soon - needed before integration tests
- Dependencies: Requires 0.4 (migrations) - already done
- Target: Could be Epic 0 addendum or part of testing setup

Decision: Ready for Spec
ID: B-001
Next: /generate-specs B-001 (or queue for later)
```

### Example 2: Node Upgrade
```
User: /intake Need to upgrade from Node 18 to Node 20

Intake Summary:
- Trigger: Tech debt / dependency currency
- Scope: Single task but needs investigation
- Urgency: 🟢 Backlog - no immediate need
- Open Questions: Breaking changes? CI/CD impact? Vercel compatibility?

Decision: Needs Design
ID: B-002
Next: Design conversation to assess impact, or icebox until prioritized
```

### Example 3: Quick Fix
```
User: /intake The smoke test has a typo in the output message

Intake Summary:
- Scope: Quick fix (<5 min)

Decision: Just do it
Next: Making the fix now, no formal tracking needed
```

### Example 4: New Feature Area
```
User: /intake Users are asking for Instagram data import support

Intake Summary:
- Trigger: New requirement (user feedback)
- Scope: New epic (different platform, new parsers, new enrichment)
- Urgency: 🟢 Backlog - not MVP scope

Decision: Icebox
ID: B-003
Next: Captured for post-MVP planning. PRD v2 consideration.
```

## Important Notes

- **Don't skip intake for sizeable work** - Even if you think you know what to do, running through intake ensures consistent tracking
- **Quick fixes don't need intake** - If it's truly <30 min and obvious, just do it
- **When in doubt, add to Needs Design** - Better to have a design conversation than to spec something poorly scoped
- **Blocking items get immediate attention** - If something is 🔴 Blocking, the design conversation happens NOW
- **Update the ID counter** - Always increment after assigning an ID