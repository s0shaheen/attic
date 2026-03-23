# Claude Code Custom Commands

## Installation

Copy all `.md` files from this directory into your repo at `.claude/commands/`:

```bash
cp claude-commands/*.md /path/to/attic/.claude/commands/
```

These coexist with your existing commands (generate-tests.md, implement-backlog.md, validate-specs.md). No conflicts.

---

## Command Reference

### Daily workflow

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/status` | Project health dashboard — git, tests, lint, env, eval status | Start of session, quick "where am I?" |
| `/branch "desc"` | Create properly named branch from latest main | Starting new work |
| `/test` | Run tests for changed files only (smart detection) | After making changes |
| `/preflight` | Full quality gate — lint, types, tests, secrets, env | Before committing |
| `/review` | Layered code review against project standards | Before shipping |
| `/ship "desc"` | Commit, push, open PR — one command | When ready to merge |

### Agent/AI development

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/review-agent` | Deep review of prompts, tools, ontology changes | After any agent intelligence change |
| `/eval` | Run classification evals, report per-facet accuracy | After prompt/ontology changes |

### Frontend

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/review-ui` | Check BRAND.md compliance — colors, typography, patterns | After any frontend change |

### Infrastructure

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/start` | Launch full local stack with health checks | When you need the UI running |
| `/resolve-conflicts` | Rebase on main, resolve conflicts by file type | When branch is behind main |
| `/deploy` | Production deployment checklist and execution | When ready to go live |

### Project management

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/issue "desc"` | Create well-formed GitHub issue with quality gate | When you have a clear, specific task to track |

---

## Typical Flows

### "I'm tweaking the classification prompt" (30 min session)

```
/status                              → see where things stand
/branch "improve-affect-nostalgia"   → new branch
  ... edit ontology.py or prompts.py ...
/eval --quick                        → fast check on first 10 items
  ... iterate ...
/eval --save                         → full eval, save results
/review-agent                        → check for regressions
/preflight                           → lint + tests
/ship "improve nostalgia detection"  → commit + PR
```

### "I'm building a new UI component" (1 hour session)

```
/branch "entity-card-component"      → new branch
  ... build the component ...
/review-ui                           → check brand compliance
/test                                → run relevant tests
/preflight                           → full checks
/review                              → general review
/ship "add entity card component"    → commit + PR
```

### "I need to test the full app" (setup)

```
/start                               → launches everything
  ... test in browser at localhost:3000 ...
  ... test account: test@attic.to / testpassword123 ...
```

### "My branch has conflicts"

```
/resolve-conflicts                   → rebase + auto-resolve
/test                                → verify nothing broke
```

### "I want to deploy"

```
/deploy --dry-run                    → see checklist without deploying
  ... fix any issues ...
/deploy                              → go live
```

---

## Design Principles

These commands were built with specific principles:

1. **Project-specific over generic.** Every review command encodes Attic's actual patterns — BRAND.md colors, agent tool contracts, ontology structure. Generic linters (ruff, eslint) handle syntax. These commands handle architecture and design.

2. **Layered severity.** BLOCK/WARN/NOTE, not pass/fail. You can ship with WARN items and fix them later. BLOCK items must be fixed.

3. **Smart detection over manual flags.** `/test` figures out which tests to run from the diff. `/review` determines which layers to check from the changed files. You don't need to specify.

4. **One-command flows.** `/ship` does stage + commit + push + PR in one step. `/preflight` runs all checks in one step. Fewer commands = less friction = more shipping.

5. **Quality gates, not gatekeepers.** These commands help you ship better code faster. They don't prevent you from shipping. If you disagree with a finding, override it — you're the founder.
