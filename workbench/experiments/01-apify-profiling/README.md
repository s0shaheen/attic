# Experiment 01: Data Profiling + Apify Validation

**Date**: 2026-03-24 (Day 1)
**Status**: Complete

## Question

What does a real TikTok export look like, and can Apify reliably enrich it? What are the data quality baselines?

## Method

1. Profiled 903 favorited TikToks from a real user export
2. Sent all URLs to Apify `clockworks~tiktok-scraper` (build 0.0.503) in 19 batches of 50
3. Measured match rate, field fill rates, media availability, subtitle coverage
4. Tested URL stability over time (KV store vs TikTok CDN)

## Key Parameters

- Apify actor: `clockworks~tiktok-scraper` v0.0.503
- Batch size: 50 URLs
- Concurrency: 7 actor runs
- Options: `shouldDownloadVideos`, `shouldDownloadCovers`, `shouldDownloadSlideshowImages`, `DOWNLOAD_SUBTITLES`, 10 comments/post

## Results

| Metric | Value |
|--------|-------|
| Match rate | **86.1%** (777/903) — 126 deleted/unavailable |
| Caption fill rate | 96.8% (median 102 chars) |
| Subtitle coverage | 54.3% (ASR + MT + LC + MU) |
| Media types | 76% video, **24% slideshow** (expected 10%) |
| Median video duration | 56s |
| Cost | **$10.79 total ($0.0139/item)** |
| Wall-clock time | 338s (5.6 min) for 903 items |

### URL Stability

| Asset | Hosted On | Expires? |
|-------|-----------|----------|
| Video, Thumbnail, Subtitles | Apify KV store | No (retention-based) |
| Slideshow images | TikTok CDN | **~30 days** |

## Learnings

- **24% slideshows is 2.4x the expected rate.** Pipeline must handle multi-image content as a first-class case, not an edge case.
- **Slideshow images are the only expiring asset.** Must be cached locally before ~30 day expiration. All other assets persist on Apify KV store.
- **54% subtitle coverage is better than expected** but leaves 46% relying on captions + visual analysis only.
- **Core metadata is near-100% fill rate.** Caption, creator, music, engagement stats are always present.
- **Apify response schema has drifted** from what production `pipeline.py` expects. Field mappings need updating.
- **User's favorites skew popular** (median 634K views) — expect professionally produced content with clear topical signals.

## Artifacts

```
results/
  apify_profile_report.json      — Structured quality metrics
  apify_raw_samples/              — 45 raw Apify responses for inspection
  profiler_plots/                 — Caption/hashtag/duration histograms
  url_stability_results.json     — URL accessibility test results
```

## Scripts

| Script | Purpose | Run |
|--------|---------|-----|
| `apify_profiler.py` | Full Apify enrichment + profiling | `.venv/bin/python workbench/experiments/01-apify-profiling/apify_profiler.py workbench/data/my-export/full_anonymized.json` |
| `url_stability_test.py` | Test URL expiration over time | `.venv/bin/python workbench/experiments/01-apify-profiling/url_stability_test.py` |
