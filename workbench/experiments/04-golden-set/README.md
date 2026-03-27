# Experiment 04: Golden Set Assembly

**Date**: 2026-03-25 to 2026-03-26 (cross-cutting)
**Status**: Infrastructure complete, annotation in progress

## Question

How do we build a ground-truth evaluation set for measuring classification quality across experiments?

## Method

1. **Sample selection**: 106 items stratified across 18 user collections by difficulty (hard/medium/easy)
2. **Apify enrichment**: Fetch full metadata + media for selected items
3. **Subtitle extraction**: Parse WebVTT from TikTok CDN links
4. **Annotation UI**: Browser-based tool with localStorage persistence for human labeling
5. **Assembly**: Merge annotations + v2 experiment reference data, deduplicate by video ID

### Assembly Pipeline

```
build_golden_set.py          — Sample items from collections, generate templates + Apify input
        ↓
[Apify enrichment (external)] — Run actor with apify_golden_set_input.json
        ↓
merge_apify_golden_set.py    — Populate templates with Apify metadata
        ↓
build_annotation_ui.py       — Generate interactive HTML annotation tool
        ↓
[Human annotation (browser)]  — Label items using the UI, export JSON
        ↓
assemble_golden_set.py       — Merge annotated + v2 experiment items, deduplicate
```

## Key Parameters

- 106 items across 18 collections
- Difficulty distribution: hard (ambiguous/multi-topic), medium, easy (clear single topic)
- Schema: `human` annotation fields + `human_deep` for hard items + `apify` metadata
- 82/106 subtitles downloaded (avg 1696 chars)

## Results

- 394 TikToks enriched via Apify (100% match rate for golden set URLs)
- Annotation UI functional with per-collection grouping and difficulty hints
- v2 experiment data (47 items) converted to golden set format for overlap comparison
- **Annotation work still pending** — UI built, labels not yet applied

## Learnings

- **Stratified sampling by collection gives natural topic diversity** — user's own organization is a useful proxy for ground truth.
- **Difficulty tiers matter** — hard items (memes, multi-topic, cultural context) expose model weaknesses that easy items miss.
- **Assembly must be idempotent** — multiple data sources (annotations, v2 experiment, future experiments) need clean merge logic with priority rules.

## Artifacts

```
results/
  golden_set_template.json        — 106-item template with Apify metadata + empty annotation fields
  golden_set_subtitles.json       — 82 subtitle texts keyed by video ID
  golden_set_annotator.html       — Interactive HTML annotation UI (490KB, regenerable)
  apify_golden_set_input.json     — Apify actor input (107 URLs)
  apify_golden_set_output.json    — Raw Apify response (607KB)
  apify_golden_set_urls.txt       — Plain text URL list
```

## Scripts

| Script | Purpose | Run |
|--------|---------|-----|
| `build_golden_set.py` | Sample items, generate templates + Apify input | `.venv/bin/python workbench/experiments/04-golden-set/build_golden_set.py` |
| `merge_apify_golden_set.py` | Populate templates with Apify metadata | `.venv/bin/python workbench/experiments/04-golden-set/merge_apify_golden_set.py` |
| `build_annotation_ui.py` | Generate browser-based annotation tool | `.venv/bin/python workbench/experiments/04-golden-set/build_annotation_ui.py` |
| `convert_v2_to_golden.py` | Convert v2 experiment output to golden set format | `.venv/bin/python workbench/experiments/04-golden-set/convert_v2_to_golden.py` |
| `assemble_golden_set.py` | Merge annotations + v2 data, deduplicate | `.venv/bin/python workbench/experiments/04-golden-set/assemble_golden_set.py` |
