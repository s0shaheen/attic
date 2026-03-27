# Experiment 03: Pipeline v3 + Search + Unit Economics

**Date**: 2026-03-26 (Day 3)
**Status**: Complete

## Question

Can we build a production-quality two-pass pipeline? Does grounding help? How fast/cheap is Tier 1 (upload-time)? What do unit economics look like?

## Method

### Pipeline v3 (Two-Pass)

- **Pass 1 (Perception + Entity)**: Full video upload + metadata + subtitles + 10 comments → summary, entities, takeaways, audio ID
- **Pass 2 (Classification)**: 3 keyframes + Pass 1 text → 8-facet ontology classification
- 106-item golden set, stratified across 18 user collections

### Experiment A vs B

- **A**: `gemini-3-flash-preview`, no grounding
- **B**: `gemini-2.5-flash`, grounding ON

### Tier 1 (Upload-Time, Keyframe-Based)

- Single pass: 3 keyframes (first/middle/last via ffmpeg) + metadata → combined output
- 106 items from golden set

### E2E Runtime Test

- 100 fresh items (not in golden set) through full Tier 1 pipeline
- Measures: Apify enrichment → keyframe extraction → Gemini processing → embedding generation

## Key Parameters

- Golden set: 106 items across 18 collections
- Pass 1: full video via Gemini File API, concurrent processing
- Pass 2: 3 keyframes (10s interval extraction via ffmpeg)
- Tier 1: 8 concurrent Gemini calls
- Embeddings: OpenAI `text-embedding-3-small` (1536-dim)

## Results

### Experiment A (gemini-3-flash, no grounding) — WINNER

| Metric | Pass 1 | Pass 2 | Total |
|--------|--------|--------|-------|
| Success | 105/106 | 106/106 | — |
| Cost | $0.10 | $0.20 | **$0.30 ($0.003/item)** |
| Time | 304s | 151s | **454s (7.5 min)** |

- 640 entities extracted (avg 6.0/item)
- "inspiring" dominant affect: **11%** (down from 45%)
- "informative" dominant: 62% (new label working)
- Topic-collection alignment: **80-100% for major topics** (food, fashion, travel, sports, music, tech)

### Experiment B (gemini-2.5-flash, grounding ON)

| Metric | Value | vs Exp A |
|--------|-------|----------|
| Cost | $0.78 | **2.6x more expensive** |
| Time | 1068s | **2.4x slower** |
| Grounding triggered | 5/106 (5%) | Barely fires |
| Entities | avg 8.3/item | More but noisier (180 "background" vs 25) |

**Grounding doesn't help for TikTok content analysis.** The model has the video and doesn't need web search.

### Tier 1 (Upload-Time)

| Metric | Value |
|--------|-------|
| Items | 106/106 |
| Time | **127s** |
| Cost | **$0.098 ($0.0009/item Gemini)** |
| Topic agreement with Tier 2 | **83%** (88/106 exact match) |

Users can search within minutes of upload. Main divergence: "Edits" → entertainment_culture (Tier 2: movies_tv).

### E2E Runtime (100 Fresh Items)

| Stage | Time | Cost | % of Total Time |
|-------|------|------|-----------------|
| Apify (metadata + video DL + subs + comments) | 5.7 min | $1.35 | **84%** |
| Keyframe extraction (ffmpeg) | 13.5s | Free | 3% |
| Gemini processing (8 concurrent) | 1.9 min | $0.09 | 23% |
| Embedding generation (OpenAI) | 1.1s | ~$0.001 | <1% |
| **TOTAL** | **8.1 min** | **$1.44** | |

**Bottleneck is Apify video download (84% of wall-clock).** Parallelizing with ThreadPoolExecutor should give 6-10x speedup.

### Unit Economics

| Component | Cost |
|-----------|------|
| Total ingestion | **$0.0194/item** (one-time) |
| Agent query | **$0.005/query** |
| Fixed monthly infra | ~$109/mo |
| Breakeven | ~15-20 paying users |

## Learnings

- **Grounding is useless for TikTok content.** Model already has the video — web search adds noise, not signal. Saves 2.6x cost by disabling.
- **Tier 1 achieves 83% topic agreement with Tier 2** at 1/3 the cost. Good enough for instant search on upload.
- **Apify is the bottleneck, not AI.** Video download is 84% of wall-clock time. Gemini + ffmpeg + embeddings combined is only 2.1 min for 100 items.
- **"informative" affect label works.** 62% dominant vs 11% "inspiring" — the new label captured the most common saved-content feeling.
- **Entity-first agent responses work well.** Users want "restaurants" and "shoes", not TikTok metadata.
- **Enriched embeddings are strictly better** than raw caption+hashtag embeddings for semantic search.
- **gemini-3-flash-preview is the production model.** Cheaper, faster, and cleaner than gemini-2.5-flash.

## Artifacts

```
results/
  pipeline_v3/                     — Two-pass pipeline output
    pass1_perception/              — 106 perception JSONs (Exp A)
    pass2_classification/          — 106 classification JSONs (Exp A)
    exp_b/                         — Experiment B (grounding) results
  pipeline_v3_media/               — 935MB keyframes + videos (GITIGNORED)
  tier1/                           — Tier 1 single-pass results
    results/                       — 106 classification JSONs
    search_index.json              — Tier 1 search index with embeddings
  tier1_e2e_media/                 — 827MB keyframe images (GITIGNORED)
  tier1_test_sample.json           — 100-item E2E test input
  search_index.json                — Full enriched search index (7.6MB)
  experiment_comparison.html       — Side-by-side Exp A vs B comparison UI
```

## Scripts

| Script | Purpose | Run |
|--------|---------|-----|
| `run_pipeline_v3.py` | Two-pass perception + classification | `.venv/bin/python workbench/experiments/03-pipeline-v3/run_pipeline_v3.py` |
| `run_tier1.py` | Fast keyframe-based single-pass | `.venv/bin/python workbench/experiments/03-pipeline-v3/run_tier1.py` |
| `tier1_e2e_test.py` | E2E runtime test (Apify → Gemini → embeddings) | `.venv/bin/python workbench/experiments/03-pipeline-v3/tier1_e2e_test.py` |
| `compare_experiments.py` | Generate Exp A vs B comparison HTML | `.venv/bin/python workbench/experiments/03-pipeline-v3/compare_experiments.py` |
| `build_search_index.py` | Build raw + enriched embedding index | `.venv/bin/python workbench/experiments/03-pipeline-v3/build_search_index.py` |
| `search_server.py` | Search UI + Claude agent at localhost:8899 | `.venv/bin/python workbench/experiments/03-pipeline-v3/search_server.py` |
