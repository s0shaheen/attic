# Experiment 05: Agent Evaluation

Test the production agent against real TikTok data from the golden set.

## Setup

```bash
# 1. Ensure base test user exists
.venv/bin/python workbench/tools/seed_db.py

# 2. Seed real Apify data + Tier 1 classifications + embeddings
.venv/bin/python workbench/experiments/05-agent-eval/seed_from_apify.py

# Or seed just 47 items for a quick test
.venv/bin/python workbench/experiments/05-agent-eval/seed_from_apify.py --limit 47
```

## Run

```bash
# Full eval suite (12 queries)
.venv/bin/python workbench/experiments/05-agent-eval/run_agent_eval.py --verbose

# Quick test (first 3 queries)
.venv/bin/python workbench/experiments/05-agent-eval/run_agent_eval.py --limit 3 -v

# Ad-hoc query
.venv/bin/python workbench/experiments/05-agent-eval/run_agent_eval.py --query "what books have I saved?" -v
```

## What it tests

- **Simple Filter**: topic/affect/genre/creator filters via query_items
- **Overview**: get_stats for broad questions
- **Vibe/Semantic**: search_similar for interpretive queries
- **Entity Retrieval**: finding books, restaurants, etc.
- **Multi-step**: queries requiring multiple tool calls

## Results

Saved to `results/eval_YYYYMMDD_HHMMSS.json` with:
- Per-query: tool sequence, latency, response text, structured events
- Summary: success rate, tool match rate, avg latency, total tokens

## Data flow

```
golden_set_template.json (106 items, real Apify metadata)
  + tier1/results/*.json (Tier 1 classifications from experiment 03)
  + golden_set_subtitles.json (subtitle text)
      ↓
seed_from_apify.py → media_events table (with classifications + embeddings)
      ↓
run_agent_eval.py → agent loop → tool calls → SSE events → results/
```
