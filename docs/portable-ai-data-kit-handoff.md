# Handoff Document: Attic → portable-ai-data-kit Migration

## Context

I'm Salman, a PM at Capital One applying for a PM role at Amigo (healthcare AI agents). I need to quickly stand up a polished open-source repo to showcase on my GitHub, website, and resume. 

I previously built a project called "Attic" — a personal data toolkit that parses social media exports (TikTok, YouTube, Instagram) into normalized schemas for AI workflows. The code exists locally but needs to be reorganized and rebranded as an open-source tool called `portable-ai-data-kit`.

**Goal:** Get a minimal but polished public repo up TODAY that I can link from my GitHub profile, website, and resume.

---

## What Attic Already Has (Prior Work)

From previous development sessions, Attic should contain:
- TikTok JSON export parser
- Canonical normalized record schema
- Enrichment pipeline with a "Wrapped"-style summary generator
- CLI with `parse` and `summarize` commands
- Fixture data for testing
- Four documentation files (getting started, schema design, privacy model, design tradeoffs)

**The key differentiator is `docs/tradeoffs.md`** — this documents explicit design decisions with reasoning, which demonstrates PM-level product thinking.

---

## Target State: portable-ai-data-kit

### Repo Name
`portable-ai-data-kit`

### One-Line Description
"Modular toolkit for turning user-authorized social media exports into structured, privacy-aware inputs for AI workflows."

### MVP Scope (Bare Bones)
- TikTok export parser only (other connectors are roadmap)
- CLI-based (`parse` and `summarize` commands)
- Normalized JSON output
- One example use case (wrapped-style summary)
- Clean README with privacy positioning
- `docs/tradeoffs.md` as the PM signal

### Target Folder Structure
```
portable-ai-data-kit/
├── README.md                    # Polished, search-optimized
├── LICENSE                      # MIT
├── .gitignore
├── requirements.txt
├── setup.py or pyproject.toml
│
├── cli.py                       # Entry point
│
├── connectors/
│   └── tiktok/
│       ├── __init__.py
│       └── parser.py            # TikTok export parser
│
├── schema/
│   ├── __init__.py
│   └── normalized.py            # Canonical record schema
│
├── pipelines/
│   ├── __init__.py
│   ├── normalize.py
│   └── summarize.py             # Wrapped-style summary
│
├── examples/
│   ├── sample_output.json       # Example normalized output
│   └── sample_summary.md        # Example wrapped summary
│
├── fixtures/
│   └── tiktok_sample.json       # Sanitized test data
│
└── docs/
    ├── getting-started.md
    ├── schema.md
    ├── privacy.md
    └── tradeoffs.md             # KEY PM ARTIFACT
```

---

## README Template

```markdown
# Portable AI Data Kit

> Modular toolkit for turning user-authorized social media exports into structured, privacy-aware inputs for AI workflows.

**Privacy-first:** Built for user-authorized exports only. Local-first processing with optional redaction before any AI enrichment.

## Why This Exists

- Platforms let you export your data, but exports are messy and hard to analyze
- Raw exports aren't ready for LLMs, embeddings, or semantic search
- This toolkit normalizes personal data into a stable schema for downstream AI workflows

## What It Does

- Parse TikTok data exports (more connectors on roadmap)
- Normalize records into a common schema
- Generate AI-ready outputs (JSONL, summaries, embeddings-ready chunks)
- Create "wrapped"-style insights from your data

## Quickstart

```bash
# Install
pip install -e .

# Parse a TikTok export
python cli.py parse --source tiktok --input ~/Downloads/tiktok_export.json --output normalized.json

# Generate a summary
python cli.py summarize --input normalized.json --output wrapped.md
```

## How It Works

```
Export File → Parse → Normalize → Enrich → Store / Search / Analyze
```

## Supported Sources

| Source | Status |
|--------|--------|
| TikTok | ✅ Supported |
| YouTube | 🗓 Planned |
| Instagram | 🗓 Planned |

## Use Cases

- Build a personal "Wrapped" summary of your content consumption
- Create a searchable archive of your digital history
- Cluster interests and topics over time
- Build a personal memory layer for an AI agent

## Design Principles

- **User-authorized data only** — no scraping, no unofficial APIs
- **Local-first** — all processing happens on your machine
- **Extensible schema** — easy to add new connectors
- **AI-tool-agnostic** — outputs work with any LLM, vector DB, or analysis tool

## Documentation

- [Getting Started](docs/getting-started.md)
- [Schema Reference](docs/schema.md)
- [Privacy Model](docs/privacy.md)
- [Design Tradeoffs](docs/tradeoffs.md) ← *Why I made the decisions I made*

## Roadmap

- [ ] YouTube history export connector
- [ ] Instagram export connector
- [ ] Embeddings-ready chunking
- [ ] Vector store output adapter
- [ ] Topic extraction and clustering

## License

MIT
```

---

## docs/tradeoffs.md Template

This is the key PM artifact. It should document 4-6 design decisions with reasoning.

```markdown
# Design Tradeoffs

This document captures key design decisions and the reasoning behind them. These aren't just implementation notes—they reflect product thinking about user needs, technical constraints, and future extensibility.

## 1. User-Authorized Exports vs. API Scraping

**Decision:** Only support official user data exports, not unofficial API scraping.

**Alternatives considered:**
- Unofficial TikTok API wrappers
- Browser automation / scraping
- Hybrid approach (exports + supplemental scraping)

**Why I chose exports:**
- Legal clarity: user-authorized exports are explicitly permitted by platforms
- Stability: official exports don't break when platforms change their anti-bot measures
- Trust: users can see exactly what data they're providing
- Portability: aligns with GDPR data portability rights

**Tradeoff accepted:** Exports may be incomplete or delayed (TikTok takes up to 30 days). Worth it for legal/ethical clarity.

---

## 2. Flat Normalized Schema vs. Preserving Original Structure

**Decision:** Normalize all sources into a single flat schema rather than preserving source-specific structures.

**Alternatives considered:**
- Keep source-specific schemas and translate at query time
- Hybrid: normalized core fields + source-specific extensions
- Graph-based schema

**Why I chose flat normalization:**
- Simplicity for downstream consumers (LLMs, vector stores)
- Easier to add new sources without breaking existing pipelines
- Reduces cognitive load when working across sources

**Tradeoff accepted:** Some source-specific metadata is lost or flattened. Added `raw_metadata` field as an escape hatch.

---

## 3. CLI-First vs. Library-First

**Decision:** Ship as a CLI tool first, with library usage as secondary.

**Alternatives considered:**
- Python library with optional CLI wrapper
- Web UI
- Jupyter notebook-first

**Why I chose CLI-first:**
- Fastest path to usable tool
- Easy to integrate into shell scripts and automation
- Clear input/output contract
- Lower barrier to contribution

**Tradeoff accepted:** Less ergonomic for notebook-based exploration. Added example notebooks to bridge the gap.

---

## 4. Local-Only Processing vs. Cloud Options

**Decision:** All processing happens locally by default. No cloud features in v1.

**Alternatives considered:**
- Optional cloud sync
- Hosted processing for users without technical setup
- Hybrid with cloud for heavy enrichment (embeddings, LLM calls)

**Why I chose local-only:**
- Privacy is a core value prop—cloud processing undermines it
- Reduces operational complexity
- Avoids cost/scaling questions in v1

**Tradeoff accepted:** Users who want cloud features must build them. May add opt-in cloud adapters later.

---

## 5. Single-File Outputs vs. Database

**Decision:** Output to JSON/JSONL files rather than SQLite or other databases.

**Alternatives considered:**
- SQLite for queryable storage
- DuckDB for analytical queries
- Vector DB (Chroma, etc.) directly

**Why I chose flat files:**
- Maximum portability—JSON works everywhere
- Easy to inspect and debug
- No database setup required
- Users can load into their preferred storage later

**Tradeoff accepted:** Large datasets may be slower to query. Added pagination to CLI for large exports.

---

## 6. Minimal Dependencies vs. Batteries-Included

**Decision:** Keep core dependencies minimal; enrichment features are optional.

**Alternatives considered:**
- Bundle common enrichment (embeddings, OCR, etc.)
- Plugin architecture from day one
- Monorepo with optional packages

**Why I chose minimal:**
- Faster install, fewer version conflicts
- Users only pay for what they use
- Easier to maintain

**Tradeoff accepted:** Users must install extras for enrichment. Clear documentation on optional dependencies.
```

---

## Prompts for Migration Session

Use these prompts in sequence with a fresh Claude conversation. Upload any existing Attic code/files you have.

### Prompt 1: Assessment

```
I have an existing project called "Attic" that I need to reorganize into a new open-source repo called "portable-ai-data-kit". 

First, help me assess what I have. I'm uploading my existing code. Please:
1. List all the files/modules that exist
2. Identify what's reusable vs. what needs to be rewritten
3. Flag any code that references "Attic" that needs renaming
4. Note any incomplete or placeholder code

[Upload your Attic files here]
```

### Prompt 2: Cleanup Plan

```
Based on your assessment, create a concrete cleanup plan:

1. Files to DELETE (dead code, experiments, etc.)
2. Files to RENAME (Attic → portable-ai-data-kit)
3. Files to RESTRUCTURE (move to new folder structure)
4. Files to CREATE (missing pieces for MVP)
5. Order of operations (what to do first)

Target structure:
portable-ai-data-kit/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── cli.py
├── connectors/tiktok/parser.py
├── schema/normalized.py
├── pipelines/normalize.py, summarize.py
├── examples/
├── fixtures/
└── docs/getting-started.md, schema.md, privacy.md, tradeoffs.md
```

### Prompt 3: Execute Cleanup

```
Execute the cleanup plan step by step. For each step:
1. Show me what you're doing
2. Create/modify the files
3. Confirm completion before moving to next step

Start with deleting dead code, then renaming, then restructuring.
```

### Prompt 4: README and Docs

```
Now create the polished README.md and docs/ files. Use this template as a starting point but improve it based on what the actual code does:

[Paste the README template from the handoff doc]

For docs/tradeoffs.md, make sure to document real decisions from the code, not hypothetical ones. This is the key artifact that shows PM thinking.
```

### Prompt 5: Final Validation

```
Before I push to GitHub, validate:
1. Run the CLI commands and confirm they work
2. Check that all imports resolve
3. Verify the example outputs are realistic
4. Review README for any claims that don't match the code
5. Ensure no "Attic" references remain

Give me a final checklist of anything I need to fix.
```

### Prompt 6: GitHub Prep

```
Help me prepare for GitHub push:
1. Generate a good .gitignore for Python projects
2. Create a LICENSE file (MIT)
3. Write a short repo description for the GitHub About section
4. Suggest 8-10 GitHub topics/tags for discoverability
5. Draft a one-paragraph "About this project" for my GitHub profile README
```

---

## Quick Reference: What "Done" Looks Like

**Minimum viable public repo:**
- [ ] Clean folder structure (no dead code, no "Attic" references)
- [ ] README that looks professional and explains the project
- [ ] CLI that actually runs (`python cli.py parse --help` works)
- [ ] At least one working command (parse TikTok export)
- [ ] Example output file showing what normalized data looks like
- [ ] `docs/tradeoffs.md` with 4-6 real design decisions
- [ ] MIT LICENSE
- [ ] .gitignore

**Nice to have but not blocking:**
- Summarize command working
- Multiple example outputs
- Comprehensive schema docs
- GitHub Actions CI

---

## Timeline Estimate

If Attic code is mostly intact:
- Assessment: 10 min
- Cleanup/restructure: 20-30 min
- README/docs polish: 15 min
- Validation: 10 min
- GitHub push: 5 min

**Total: ~1 hour to public repo**

If significant rewriting needed:
- Add 30-60 min for code fixes

---

## Contact Context

This repo supports a job application for Amigo (healthcare AI PM role). The hiring manager is a UIUC connection who said "would love to chat" — so this is warm outreach, not cold. The repo needs to look credible but doesn't need to be production-grade. Signal over polish.
