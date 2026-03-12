# 📦 Project Archived

This project has been archived and is no longer under active development.

## Why Archived

Attic was an ambitious personal analytics platform for TikTok data. After completing the foundation (authentication, upload pipeline, data parsing), I realized:

1. **Scope creep**: The full vision required 10+ Lambda functions, multiple AI APIs, and ongoing infrastructure costs
2. **Focus shift**: The most valuable piece — parsing messy platform exports into clean schemas — deserved to be extracted as a standalone tool
3. **Open-source opportunity**: A focused data portability toolkit would be more useful to others than a monolithic personal app

## What Was Built

- **Production-ready TikTok parser** — 634 lines, security-hardened, handles multiple export format variations
- **Full authentication system** — JWT validation, Supabase integration, GDPR-compliant deletion
- **Comprehensive schema design** — 5 migrations, 70+ fields per media event, pgvector embeddings
- **Test-driven development** — 60+ tests, synthetic fixtures, edge case coverage
- **Infrastructure as code** — AWS SAM template, Step Functions state machine, Lambda architecture
- **Documentation-first approach** — PRD, dev guide, 37 task specs, setup guides

## Successor Project

The data parsing work continues in **[portable-ai-data-kit](https://github.com/s0shaheen/portable-ai-data-kit)** — a focused, open-source CLI tool for turning platform exports into AI-ready data.

## Lessons Learned

See [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md) for architecture retrospective.

---

*Archived March 2026*
