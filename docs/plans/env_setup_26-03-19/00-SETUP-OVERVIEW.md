# Setup Overview

## What We're Doing

Reorganizing your development environment around one principle: the fastest possible feedback loop on the thing that makes Attic succeed — classification quality, agent intelligence, retrieval accuracy.

**Before:** Infrastructure-heavy setup with Docker, Conductor worktrees, and env propagation complexity standing between you and seeing real output.

**After:** VS Code + Claude Code. One venv. One env file. Jupyter notebooks for exploration. Scripts for automated evals. One command to seed the database and test the full UI.

---

## Manual Steps (You Do These First)

### 1. Create `.env.master`
Single file at repo root with every secret. Template committed as `.env.master.example`. You fill in real keys once, never think about it again.

### 2. Move `.venv` to repo root
```bash
# From repo root
mv src/backend/.venv .venv
# OR fresh:
python3.13 -m venv .venv && .venv/bin/pip install -r src/backend/requirements.txt
```
Then install workbench dependencies:
```bash
.venv/bin/pip install python-dotenv jupyter matplotlib seaborn pandas
```

### 3. Install Jupyter kernel
```bash
.venv/bin/python -m ipykernel install --user --name attic --display-name "Attic"
```

### 4. Open VS Code, paste the CC guide into Claude Code
The guide handles everything else — env scaffolding, workbench creation, slash commands, database seeding, brand tokens, production configs.

---

## What CC Creates (In Order)

| Phase | What | Why |
|-------|------|-----|
| 1. Env scaffolding | `.env.master.example`, `setup-env.sh`, `check-env.sh`, `.gitignore` updates | Never touch env files again |
| 2. Custom slash commands | `/ship`, `/review`, `/review-agent`, `/review-ui`, `/resolve-conflicts` | Replace Conductor's auto features, project-specific |
| 3. Workbench — notebooks | 5 Jupyter notebooks for exploration (classification, agent traces, retrieval, embeddings, preprocessing) | Your daily lab for understanding and improving the intelligence layer |
| 4. Workbench — scripts | `classify_batch.py`, `run_evals.py`, `generate_test_data.py` | Automated evals, CI-runnable quality gates |
| 5. Database seeding | `seed_db.py` — test user, sample uploads, pre-classified media events | Full-stack UI testing without manual data entry |
| 6. Brand tokens | `design-tokens.ts`, `globals.css` updates from BRAND.md | UI refresh is a theme swap, not a rewrite |
| 7. VS Code config | `settings.json`, `launch.json` | Python interpreter, debugger, Jupyter kernel |
| 8. Production configs | Vercel `vercel.json`, Render `render.yaml` | Deploy when ready, configs already in repo |
| 9. CLAUDE.md updates | Workbench docs, new commands, workflow guidance | CC agents don't break the setup |

---

## Your Daily Workflow

**Most sessions (30-60 min):**
Open VS Code → open a notebook → classify/query/analyze → tweak → measure → `/ship`

**Full-stack testing (when needed):**
`supabase start` → `./scripts/dev-start.sh` → login with test account → see real data

**Terminal layout in VS Code:**
- Terminal 1: Claude Code (your main agent session)
- Terminal 2: Shell for running scripts, git, quick checks
- Terminal 3: Servers (only when testing full stack)
