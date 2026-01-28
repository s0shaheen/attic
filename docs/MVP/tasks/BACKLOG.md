# Attic Backlog

**Last Updated:** 2026-01-28

This document captures work that emerged during development and hasn't yet been formally added to the Dev Guide. Items flow through three stages: Needs Design → Ready for Spec → (spec generated, removed from backlog).

---

## Ready for Spec

Items that have been triaged, designed (if needed), and are ready for spec generation via `/generate-specs B-XXX`.

| ID | Title | Category | LOE | Target Epic | Dependencies | Design Notes |
|----|-------|----------|-----|-------------|--------------|--------------|
| | | | | | | |

**LOE Key:** XS (<1hr), S (1-4hr), M (4-8hr), L (1-2 days), XL (3+ days)

**Category Key:** Infra, Feature, Tech Debt, Bug Fix, Testing, Docs

---

## Needs Design

Items captured but requiring design conversation (via `designer` agent) before spec generation.

| ID | Title | Category | Trigger | Urgency | Open Questions |
|----|-------|----------|---------|---------|----------------|
| | | | | | |

**Urgency Key:** 
- 🔴 Blocking - Can't continue current work without this
- 🟡 Soon - Natural implementation point coming up, or dependency for near-term work
- 🟢 Backlog - Important but not time-sensitive

**Trigger Key:** Bug, Tech Debt, New Requirement, Dependency, Performance, Security

---

## Icebox

Captured ideas not currently prioritized. Reviewed periodically for promotion.

| ID | Title | Origin | Captured | Notes |
|----|-------|--------|----------|-------|
| | | | | |

---

## Completed (Archive)

Items that have been converted to specs. Kept for reference.

| ID | Title | Became Task | Completed |
|----|-------|-------------|-----------|
| | | | |

---

## How to Use This Document

### Adding Items
1. Run `/intake` with a description of the work
2. The command will triage and add to the appropriate section
3. Items get assigned IDs in format `B-XXX` (incrementing)

### Moving Items Forward
- **Needs Design → Ready**: Run `/intake` again or use `designer` agent to complete design
- **Ready → Spec**: Run `/generate-specs B-XXX` to create formal spec and update Dev Guide
- **Icebox → Needs Design**: Manual promotion when prioritized

### ID Assignment
- Use the next available number: B-001, B-002, etc.
- IDs are permanent - don't reuse even after completion
- Check the Completed section for the highest used ID

---

## Current ID Counter

**Next Available ID:** B-001