# Experiment 02: Vision Analysis

**Date**: 2026-03-24 (Day 2)
**Status**: Complete

## Question

Does full video analysis meaningfully outperform thumbnail-only? Which prompt variant is optimal? What is the baseline classification quality?

## Method

### Experiment 1 (v1): Prompt Variant Comparison — 15 Items

- 15 hand-picked diverse TikToks (10 videos, 2 images, 3 carousels)
- Content: cooking, self-help, comedy, productivity, fan edits, pizza recs, skiing, cinematic, corecore, movie review
- 13 prompt variants tested across 4 input types (thumbnail, video, slideshow, keyframes)
- Model: `gemini-2.5-flash`
- No subtitles or comments (identified as gap)

### Experiment 2 (v2): Comprehensive Pipeline — 47 Items

- 50 randomly selected from recent 500 favorites (seed=42), 47 matched by Apify
- 28 videos, 19 slideshows
- Model: `gemini-2.5-flash`, max output tokens 8192
- Subtitles + top 5 comments injected into all prompts
- Two-stage: perception then 5-facet + 8-facet classification
- Human evaluation on 6 dimensions (1-3 scale)

## Key Parameters

- v1: 13 prompt variants, 130 total experiments, $0.31
- v2: single comprehensive prompt, 47 items, $0.23 total Gemini cost
- Concurrency: 4 for video upload, 6 for text-only

## Results

### Video vs Thumbnail (v1)

| Input | Wins | Richness Score | Named Entities | Cost/Item |
|-------|------|----------------|----------------|-----------|
| Full video | **12/15** | ~120 | Many | $0.007 |
| Thumbnail | 3/15 | ~70 | **0** | $0.0003 |

**Video is 24x more expensive but categorically better. Thumbnails extracted zero named entities.**

### Prompt Ranking (v1)

1. **V2 (comprehensive perception)** — best overall
2. V4 (perception + classification hints) — same quality, folded into V2
3. V3 (multi-pass sequential) — 3x cost for marginal gain
4. V1 (minimal) — too sparse

### Slideshow Handling (v1)

- S2 (all images) >> S1 (cover only) — pizza recs: 37 entities vs 0
- S3 (first + last) captures ~70% quality at ~40% token cost
- 133 images assessed: 62% informational, 11% decorative, ~10% skippable

### Human Evaluation (v2, 47 items)

| Dimension | Avg Score | Poor (1) | Strong (3) |
|-----------|-----------|----------|------------|
| Accuracy | **2.40** | 15% | 55% |
| Completeness | 1.98 | 23% | 21% |
| Specificity | 1.87 | 28% | 15% |
| Entity Coverage | **1.60** | **51%** | 11% |
| Classification Signal | **1.61** | **53%** | 15% |
| Vision Added Value | 2.17 | 19% | 36% |

**Overall: 11.6/18 avg (64%).** Accuracy is solid but entity coverage and classification signal are the critical gaps.

### Vision vs Text-Only Agreement (v2)

| Text Richness | Topic | Genre | Affect |
|---------------|-------|-------|--------|
| Rich (subs + caption) | 80% | 60% | 90% |
| Caption only | 67% | 43% | 38% |
| Low text | **12%** | **31%** | **44%** |

**Vision is essential for low-text items.** Text-only classification diverges massively when captions are short/empty.

## Learnings

- **Full video via Gemini File API is non-negotiable** despite 24x cost premium. Thumbnails miss everything.
- **Single comprehensive prompt wins.** Multi-pass (V3) costs 3x for marginal gain.
- **Entity extraction is the #1 quality gap** (51% scored Poor). Needs a dedicated entity pass, not just a section in the perception prompt.
- **"Inspiring" was massively overassigned** (45% of items). Fixed in v2 prompt to 11%, but affect classification still needs work.
- **Comedy/satire/meme humor consistently misclassified.** Model doesn't understand irony or TikTok meme formats.
- **11% parse errors** on long videos from output token exhaustion. Doubled to 8192 tokens, still present.
- **Include subtitles + comments in perception prompt** — identified as gap in v1, fixed in v2.
- **All carousel images are essential** — cover-only misses critical content (restaurant lists, product specs).

## Artifacts

```
results/
  vision_analysis_samples/          — v1: 15-item comparison data (130 experiments)
    automated_metrics.json          — Cost/latency/richness across 4 methods
    sample_manifest.json            — Item metadata
    results/                        — Per-method output (grounding/, keyframes/, slideshow/, thumbnail/, video/)
    media/                          — 189MB visual assets (GITIGNORED)
  vision_v2/                        — v2: 47-item full pipeline
    manifest.json                   — Items with Apify data + subtitles + comments
    eval_scores_v2.json             — Human eval scores (6 dimensions)
    eval_ui.html                    — Self-contained HTML evaluation UI
    EXPERIMENT_REPORT.md            — Detailed findings
    experiment_data_for_claude.json — All data exported for Claude analysis (332KB)
    results/                        — Perception + classification output
    media/                          — 382MB visual assets (GITIGNORED)
  v2_items_converted.json           — v2 items in golden set format
```

## Scripts

| Script | Purpose | Run |
|--------|---------|-----|
| `gemini_video_analyzer.py` | v1: 15-item prompt variant comparison | `.venv/bin/python workbench/experiments/02-vision-analysis/gemini_video_analyzer.py` |
| `vision_v2_experiment.py` | v2: 47-item comprehensive pipeline | `.venv/bin/python workbench/experiments/02-vision-analysis/vision_v2_experiment.py` |
