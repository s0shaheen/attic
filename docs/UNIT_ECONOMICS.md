# Attic — Unit Economics & Per-Item Processing Benchmarks

> **Canonical reference.** Every number includes source, sample size, date, and confidence level.
> Update this doc as new measurements are taken. Supersedes `docs/research-plan-v0/UNIT_ECONOMICS.md`.
>
> **Last updated:** 2026-04-03

**Confidence tags:**

- `MEASURED (N=X)` — directly observed from experiment data
- `ESTIMATED` — derived or extrapolated, not directly measured
- `NOT MEASURED` — no data exists, experiment needed

---

## 0. Per-Item Summary by Media Type

**Production pipeline stages:** enrich (Apify/TikWM) → subtitle_fetch → perceive (Gemini) → classify (Gemini) → embed (OpenAI)

`subtitle_fetch` is currently a no-op state transition (no cost, no time). `embed` is media-type-agnostic ($0.00001/item, <0.1s). The three cost-bearing stages are **enrich**, **perceive**, and **classify**.

### What we have: TikTok video (the only type measured on current model)

All Exp 03 data (106 items, gemini-3-flash-preview) is **100% TikTok video**. The golden set contains 0 slideshows and 0 images. Per-item stats from the existing results:

| Stage                              | Mean cost    | Median cost | p95 cost | Mean time | Median time | p95 time | N   | Source                      |
| ---------------------------------- | ------------ | ----------- | -------- | --------- | ----------- | -------- | --- | --------------------------- |
| Enrich (Apify TT)                  | $0.0139      | —           | —        | ~3.9s     | —           | —        | 903 | Exp 01                      |
| Enrich (TikWM TT)                  | ~$0.001      | —           | —        | 0.45s p50 | —           | —        | 50  | TIKWM_HANDOFF               |
| Perceive (video, full upload)      | $0.00237     | $0.00212    | $0.00389 | 27.4s     | 24.9s       | 43.6s    | 106 | Exp 03 pass1 per-item JSONs |
| Classify (video, keyframes + text) | $0.00188     | $0.00158    | $0.00362 | 8.4s      | 7.8s        | 12.4s    | 106 | Exp 03 pass2 per-item JSONs |
| Embed (OpenAI)                     | ~$0.00001    | —           | —        | <0.1s     | —           | —        | 100 | Exp 03 E2E                  |
| **TikTok video total**             | **~$0.0181** | —           | —        | **~40s**  | —           | —        |     |                             |

Note: Perceive time includes video download + Gemini File API upload + poll + generateContent + delete — this is the heaviest step.

**Token usage (Exp 03, gemini-3-flash-preview, all TikTok video):**

| Stage                          | Mean input tokens | Median input | Mean output tokens | Median output |
| ------------------------------ | ----------------- | ------------ | ------------------ | ------------- |
| Perceive                       | 8,002             | 6,414        | 1,948              | 1,871         |
| Classify                       | 11,199            | 9,178        | 341                | 340           |
| Tier 1 (single-pass keyframes) | 4,277             | 4,271        | 476                | 479           |

### Older per-media-type data (different model, small sample)

Exp 02 v1 measured Gemini perception cost by media type, but on **gemini-2.5-flash** (not current model) with **N=15**:

| Media type                       | Perception cost/item | Richness | Sample | Source    |
| -------------------------------- | -------------------- | -------- | ------ | --------- |
| Video (full upload)              | $0.0065              | 119.4    | N=15   | Exp 02 v1 |
| Slideshow (all images, up to 10) | $0.0005              | 119.2    | N=15   | Exp 02 v1 |
| Thumbnail (single image)         | $0.0003              | 75.1     | N=15   | Exp 02 v1 |

Directionally: video is ~13x more expensive than slideshow for perception. But this ratio is unreliable — different model, tiny sample, and video perception now goes through Gemini File API (upload full video) rather than URL pass-through.

### The matrix we need (and what's missing)

|                               | Enrich          | Perceive       | Classify       | Embed            | **Total**         |
| ----------------------------- | --------------- | -------------- | -------------- | ---------------- | ----------------- |
| **TikTok video** (~30-90s)    | $0.014 / 3.9s   | $0.0024 / 27s  | $0.0019 / 8s   | $0.00001 / <0.1s | **$0.018 / ~40s** |
| **TikTok slideshow**          | ~$0.013 / ~3.5s | `NOT MEASURED` | `NOT MEASURED` | $0.00001 / <0.1s | ?                 |
| **TikTok image**              | ~$0.013 / ~3.5s | `NOT MEASURED` | `NOT MEASURED` | $0.00001 / <0.1s | ?                 |
| **Instagram video** (~30-90s) | `NOT MEASURED`  | `NOT MEASURED` | `NOT MEASURED` | $0.00001 / <0.1s | ?                 |
| **Instagram image**           | `NOT MEASURED`  | `NOT MEASURED` | `NOT MEASURED` | $0.00001 / <0.1s | ?                 |
| **Instagram carousel**        | `NOT MEASURED`  | `NOT MEASURED` | `NOT MEASURED` | $0.00001 / <0.1s | ?                 |

TikTok video is the only fully measured row. Everything else needs the experiment below.

### Experiment: per-media-type benchmark

#### Goal

Fill every `NOT MEASURED` cell in the matrix above with a measured value on the current production stack (gemini-3-flash-preview, Apify Starter, OpenAI text-embedding-3-small).

#### Current data inventory

| Data source                     | Location                                                                         | Count      | Media types available                                                         |
| ------------------------------- | -------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------- |
| TikTok export (raw URLs)        | `workbench/data/my-export/full_anonymized.json`                                  | 903 URLs   | Unknown until enriched (Exp 01 found 76% video, 24% slideshow, 0% image)      |
| TikTok enriched (Apify)         | `workbench/data/apify_all_favorites.json`                                        | 394 items  | **100% video** — no slideshows                                                |
| TikTok golden set               | `workbench/experiments/04-golden-set/results/golden_set_template.json`           | 106 items  | **100% video** — no slideshows                                                |
| Instagram export (raw URLs)     | `workbench/data/instagram_saved_posts.json`                                      | 1,334 URLs | 185 reels, 1,131 posts/carousels, 18 other (by URL pattern `/reel/` vs `/p/`) |
| Exp 03 pass1 results (per-item) | `workbench/experiments/03-pipeline-v3/results/pipeline_v3/pass1_perception/`     | 106 JSONs  | All video — already has usageMetadata (serves as TikTok video baseline)       |
| Exp 03 pass2 results (per-item) | `workbench/experiments/03-pipeline-v3/results/pipeline_v3/pass2_classification/` | 106 JSONs  | All video — already has usageMetadata                                         |

**Key gap:** The original Apify profiler (Exp 01) ran on all 903 URLs and found 186 slideshows, but the enriched results were not committed. `apify_all_favorites.json` was a separate run on a 394-item subset that happened to be all video. We need to re-enrich a sample that includes slideshows.

**TikTok single images:** 0 out of 903 favorites were single images. This media type may be too rare in TikTok favorites to benchmark. Skip unless encountered during enrichment.

#### Phase 1: Data collection (~$15-20 Apify cost, ~30 min)

**Step 1a — TikTok slideshows:**

1. Take the 903 TikTok URLs from `full_anonymized.json` → `Likes and Favorites` → `Favorite Videos` → `FavoriteVideoList`
2. Run Apify `clockworks~tiktok-scraper` on a random sample of 200 URLs (to get ~48 slideshows at the 24% rate from Exp 01)
   - Config: `shouldDownloadVideos: true, shouldDownloadCovers: true, shouldDownloadSlideshowImages: true, shouldDownloadSubtitles: true, commentsPerPost: 10`
   - Estimated cost: 200 × $0.014 = ~$2.80
3. Filter results by `isSlideshow` / `imagePost` fields
4. Select 15 slideshows and 15 videos (for comparison with Exp 03 baseline)
5. If any single images appear, include them

**Step 1b — Instagram:**

1. Take the 1,334 Instagram URLs from `instagram_saved_posts.json`
2. Select 50 `/reel/` URLs (video) and 50 `/p/` URLs (post — could be image or carousel)
3. Run Apify `apify~instagram-scraper` on the 100 URLs
   - Config: same download settings as TikTok
   - Estimated cost: ~100 × $0.014 = ~$1.40 (IG cost likely similar to TT)
4. Categorize results: video (reel), single image, carousel (multiple images)
5. Target: 15+ items per media type

**Step 1 output:** JSON files with enriched metadata, grouped by platform × media_type:

```
workbench/experiments/06-media-type-benchmark/data/
  tiktok_video.json       (15 items, control group)
  tiktok_slideshow.json   (15+ items)
  tiktok_image.json       (if any exist)
  instagram_video.json    (15+ items)
  instagram_image.json    (15+ items)
  instagram_carousel.json (15+ items)
```

#### Phase 2: Gemini benchmark (~$1-3 Gemini cost, ~1 hour)

**Step 2a — Run perceive + classify on each item:**

1. Adapt `run_pipeline_v3.py` (already captures usageMetadata, cost, latency per item) to accept the Phase 1 JSON files as input
2. Run Pass 1 (perception) on each item — the script already handles video/slideshow/image paths correctly based on `is_slideshow` and media URL presence
3. Run Pass 2 (classification) on each item using Pass 1 output
4. Run OpenAI embedding on each item's classification output

**Step 2b — Capture per-item metrics:**
Each result JSON already contains (from `run_pipeline_v3.py`'s `save_result()`):

```json
{
  "item_id": "...",
  "stage": "pass1_perception",
  "metrics": {
    "input_tokens": 8002,
    "output_tokens": 1948,
    "total_tokens": 9950,
    "cost_usd": 0.003538,
    "latency_ms": 33972,
    "upload_ms": 12604
  },
  "context_used": {
    "is_slideshow": false,
    "has_video": true,
    "has_thumbnail": true
  }
}
```

**Step 2 output:** Per-item result JSONs in:

```
workbench/experiments/06-media-type-benchmark/results/
  pass1_perception/{item_id}.json
  pass2_classification/{item_id}.json
```

#### Phase 3: Analysis (~30 min)

**Step 3a — Aggregate by platform × media_type:**
Script reads all result JSONs, groups by media type, computes:

- mean / median / p95 for: cost_usd, latency_ms, input_tokens, output_tokens
- Separate stats for pass1 and pass2
- Total cost/time per media type (sum of pass1 + pass2 + embed)

**Step 3b — Update this document:**
Fill in the matrix in Section 0. Replace `NOT MEASURED` cells with measured values + confidence tags.

**Step 3 output:**

```
workbench/experiments/06-media-type-benchmark/RESULTS.md   — experiment report
workbench/experiments/06-media-type-benchmark/summary.json — machine-readable aggregate
```

#### Estimated total cost

| Phase                                     | Apify cost | Gemini cost | OpenAI cost | Total      |
| ----------------------------------------- | ---------- | ----------- | ----------- | ---------- |
| 1a: TikTok enrichment (200 items)         | ~$2.80     | —           | —           | $2.80      |
| 1b: Instagram enrichment (100 items)      | ~$1.40     | —           | —           | $1.40      |
| 2: Gemini perceive + classify (~90 items) | —          | ~$0.50      | ~$0.001     | $0.50      |
| **Total**                                 |            |             |             | **~$4.70** |

#### Effort estimate

| Phase                          | Time                             | Blocked on                        |
| ------------------------------ | -------------------------------- | --------------------------------- |
| Phase 1: Data collection       | ~30 min active + Apify wait time | Apify API keys, IG scraper access |
| Phase 2: Gemini benchmark      | ~1 hour (mostly waiting for API) | Gemini API key                    |
| Phase 3: Analysis + doc update | ~30 min                          | Phase 2 completion                |
| **Total**                      | **~2-3 hours**                   |                                   |

#### Dependencies & prerequisites

- `APIFY_API_TOKEN` in `.env.master` (already configured)
- `GEMINI_API_KEY` in `.env.master` (already configured)
- `OPENAI_API_KEY` in `.env.master` (already configured)
- Instagram scraper actor access (`apify~instagram-scraper`) — verify Apify account has access
- Sufficient Apify credit (~$5 on Starter plan's $29 prepaid)

---

## 1. Per-Item Cost Breakdown

### Ingestion Pipeline (one-time per item, at upload)

#### Enrichment (Step 2: apify_enrich)

| Provider                          | Platform  | Cost/item | Sample | Date       | Source                                    | Confidence         |
| --------------------------------- | --------- | --------- | ------ | ---------- | ----------------------------------------- | ------------------ |
| Apify (clockworks~tiktok-scraper) | TikTok    | $0.0139   | N=903  | 2026-03-24 | Exp 01: Apify profiling, Sprint Log Day 1 | `MEASURED (N=903)` |
| Apify (apify~instagram-scraper)   | Instagram | —         | —      | —          | —                                         | `NOT MEASURED`     |
| TikWM API                         | TikTok    | ~$0.001   | N=50   | 2026-03-30 | TIKWM_HANDOFF.md                          | `MEASURED (N=50)`  |

**Apify cost composition** (pay-per-event, Starter tier):

| Event                   | Cost                  | Notes                            |
| ----------------------- | --------------------- | -------------------------------- |
| Actor start             | $0.001/run            | 1 run per batch of 50            |
| Result returned         | $0.003/item           |                                  |
| Video download          | $0.001/item           |                                  |
| Comment (10/post)       | $0.001/comment        | $0.01/item for 10 comments       |
| Subtitle download       | Free                  | With `DOWNLOAD_SUBTITLES` option |
| Transcription (Whisper) | $0.041/started minute | NOT USED — opted for native subs |
| Date filter             | $0.001/item           | NOT USED                         |
| Popularity filter       | $0.001/item           | NOT USED                         |

**Apify cost at scale by plan tier:**

| Plan     | Subscription | PPE/item | Items from prepaid | Source                  |
| -------- | ------------ | -------- | ------------------ | ----------------------- |
| Starter  | $29/mo       | $0.0140  | ~2,071             | UNIT_ECONOMICS.md (old) |
| Scale    | $199/mo      | $0.0106  | ~18,774            | UNIT_ECONOMICS.md (old) |
| Business | $999/mo      | $0.0073  | ~136,849           | UNIT_ECONOMICS.md (old) |

**TikWM vs Apify comparison:**

| Metric                  | TikWM   | Apify               | Source                    |
| ----------------------- | ------- | ------------------- | ------------------------- |
| Cost/item               | ~$0.001 | $0.014              | TIKWM_HANDOFF.md          |
| Cost ratio              | 1x      | 14x                 | Derived                   |
| Fields populated        | 21/28   | 28/28               | TIKWM_HANDOFF.md          |
| Critical fields covered | 5/5     | 5/5                 | TIKWM_HANDOFF.md          |
| Video download success  | 98%     | 100%                | TIKWM_HANDOFF.md          |
| Success rate (N=50)     | 100%    | 86.1% (14% deleted) | TIKWM_HANDOFF.md / Exp 01 |

#### Gemini Processing (Steps 4-5: perceive + classify)

| Step                                                       | Model                  | Cost/item | Sample | Date       | Source                           | Confidence         |
| ---------------------------------------------------------- | ---------------------- | --------- | ------ | ---------- | -------------------------------- | ------------------ |
| Tier 1: keyframe perception + classification (single pass) | gemini-3-flash-preview | $0.0009   | N=106  | 2026-03-26 | Exp 03: Pipeline v3, Tier 1 test | `MEASURED (N=106)` |
| Tier 2 Pass 1: full video perception                       | gemini-3-flash-preview | $0.00094  | N=106  | 2026-03-26 | Exp 03: Exp A ($0.10/106 items)  | `MEASURED (N=106)` |
| Tier 2 Pass 2: classification                              | gemini-3-flash-preview | $0.00189  | N=106  | 2026-03-26 | Exp 03: Exp A ($0.20/106 items)  | `MEASURED (N=106)` |
| Tier 2 combined (perception + classification)              | gemini-3-flash-preview | $0.0028   | N=106  | 2026-03-26 | Exp 03: Exp A ($0.30/106 items)  | `MEASURED (N=106)` |
| Tier 2 with grounding                                      | gemini-2.5-flash       | $0.0074   | N=106  | 2026-03-26 | Exp 03: Exp B ($0.78/106 items)  | `MEASURED (N=106)` |

**Earlier experiment data (different model, smaller sample):**

| Step                               | Model            | Cost/item | Sample | Date       | Source                     | Confidence        |
| ---------------------------------- | ---------------- | --------- | ------ | ---------- | -------------------------- | ----------------- |
| Perception (full video)            | gemini-2.5-flash | $0.0034   | N=47   | 2026-03-24 | Exp 02 v2 ($0.16/47 items) | `MEASURED (N=47)` |
| 5-facet classification (vision)    | gemini-2.5-flash | $0.00043  | N=47   | 2026-03-24 | Exp 02 v2 ($0.02/47 items) | `MEASURED (N=47)` |
| 5-facet classification (text-only) | gemini-2.5-flash | $0.00021  | N=47   | 2026-03-24 | Exp 02 v2 ($0.01/47 items) | `MEASURED (N=47)` |
| 8-facet classification (vision)    | gemini-2.5-flash | $0.00064  | N=47   | 2026-03-24 | Exp 02 v2 ($0.03/47 items) | `MEASURED (N=47)` |

**Per-approach vision cost (Exp 02 v1, gemini-2.5-flash):**

| Approach               | Cost/item | Richness score | Entities/item | Sample | Source                    |
| ---------------------- | --------- | -------------- | ------------- | ------ | ------------------------- |
| Thumbnail              | $0.0003   | 75.1           | 0.0           | N=15   | Exp 02 v1 eval_summary.md |
| Full video             | $0.0065   | 119.4          | 8.6           | N=15   | Exp 02 v1 eval_summary.md |
| Slideshow (all images) | $0.0005   | 119.2          | 12.2          | N=15   | Exp 02 v1 eval_summary.md |

Note: Video is 22x more expensive than thumbnail but extracts dramatically more entities and richer descriptions. Slideshow achieves video-quality richness at thumbnail-like cost.

#### Embedding (Step 6: embed)

| Provider | Model                             | Cost/item | Sample | Date       | Source                         | Confidence         |
| -------- | --------------------------------- | --------- | ------ | ---------- | ------------------------------ | ------------------ |
| OpenAI   | text-embedding-3-small (1536-dim) | ~$0.00001 | N=100  | 2026-03-26 | Exp 03 E2E (~$0.001/100 items) | `MEASURED (N=100)` |

Note: Embedding cost is negligible — less than 0.1% of total ingestion cost.

#### Total Ingestion Cost

| Configuration                                 | Cost/item    | Composition                                                           | Confidence                                  |
| --------------------------------------------- | ------------ | --------------------------------------------------------------------- | ------------------------------------------- |
| **Current pipeline (Apify + Tier 2 + embed)** | **$0.0194**  | Apify $0.0140 + Gemini T2 $0.0043 + embed $0.0001 + Gemini T1 $0.0009 | `MEASURED`                                  |
| **With TikWM for TikTok**                     | **~$0.0064** | TikWM $0.001 + Gemini T2 $0.0043 + embed $0.0001 + Gemini T1 $0.0009  | `ESTIMATED` — TikWM only tested on 50 items |
| **Tier 1 only (upload-time)**                 | **$0.0150**  | Apify $0.0140 + Gemini T1 $0.0009 + embed $0.0001                     | `MEASURED`                                  |
| **Tier 1 with TikWM**                         | **~$0.0020** | TikWM $0.001 + Gemini T1 $0.0009 + embed $0.0001                      | `ESTIMATED`                                 |

### Agent Queries (per query, ongoing)

| Component                        | Cost/query  | Sample | Date       | Source                               | Confidence                          |
| -------------------------------- | ----------- | ------ | ---------- | ------------------------------------ | ----------------------------------- |
| Claude Haiku 4.5 (~3 tool calls) | $0.005      | N=1    | 2026-03-28 | Exp 05 agent eval (17,460 tokens)    | **`ESTIMATED`** — single query only |
| OpenAI embedding (query vector)  | $0.0001     | —      | —          | Derived from embedding model pricing | `ESTIMATED`                         |
| **QUERY TOTAL**                  | **~$0.005** |        |            |                                      | **`ESTIMATED`**                     |

**The $0.005/query figure is low-confidence.** It's based on a single eval query ("what restaurants do i have saved?") that used 1 tool call and 17,460 tokens. Complex queries with multiple tool calls, semantic search, or entity resolution will cost more. This is the single most important gap to fill — see Section 8.

### Entity Resolution (per resolution, on-demand)

| Provider           | API            | Cost/call | Sample | Confidence     |
| ------------------ | -------------- | --------- | ------ | -------------- |
| Google Maps Places | Text Search    | —         | —      | `NOT MEASURED` |
| Google Books       | Volumes Search | —         | —      | `NOT MEASURED` |
| TMDB               | Multi-search   | —         | —      | `NOT MEASURED` |
| Spotify            | Search         | —         | —      | `NOT MEASURED` |

Note: Entity resolution is triggered by the agent's `resolve_entity` tool, not during pipeline ingestion. Results are cached in `media_events.cached_entities` after first resolution, so cost is per-unique-entity, not per-query.

---

## 2. Per-Item Timing Breakdown

### E2E Pipeline (100 fresh items, Tier 1 path)

| Stage                                         | Wall-clock  | Per-item  | % of total | Concurrency            | Source                         |
| --------------------------------------------- | ----------- | --------- | ---------- | ---------------------- | ------------------------------ |
| Apify (metadata + video DL + subs + comments) | 5.7 min     | 3.42s     | **84%**    | 1 actor, batches of 50 | Exp 03 E2E, `MEASURED (N=100)` |
| Keyframe extraction (ffmpeg)                  | 13.5s       | 0.14s     | 3%         | Sequential             | Exp 03 E2E, `MEASURED (N=100)` |
| Gemini processing                             | 1.9 min     | 1.14s     | 23%        | 8 concurrent           | Exp 03 E2E, `MEASURED (N=100)` |
| Embedding generation (OpenAI)                 | 1.1s        | 0.01s     | <1%        | 1 batch                | Exp 03 E2E, `MEASURED (N=100)` |
| **TOTAL**                                     | **8.1 min** | **4.86s** |            |                        |                                |

Note: Percentages sum to >100% because Gemini processing overlapped with Apify polling.

**Bottleneck: Apify is 84% of wall-clock time.** The AI stack (Gemini + OpenAI) combined is only 2.1 minutes for 100 items. TikWM would eliminate this bottleneck (~25s for 50 items vs ~2 min for Apify).

### Tier 2 Pipeline (106 golden set items, perception + classification)

| Stage                                   | Wall-clock         | Per-item  | Concurrency   | Source                           |
| --------------------------------------- | ------------------ | --------- | ------------- | -------------------------------- |
| Pass 1: Perception (gemini-3-flash)     | 304s               | 2.87s     | Not specified | Exp 03 Exp A, `MEASURED (N=106)` |
| Pass 2: Classification (gemini-3-flash) | 151s               | 1.42s     | Not specified | Exp 03 Exp A, `MEASURED (N=106)` |
| **TOTAL Tier 2**                        | **454s (7.5 min)** | **4.28s** |               |                                  |

With grounding (gemini-2.5-flash): 1068s (17.8 min) — 2.4x slower. Source: Exp 03 Exp B.

### Apify Per-Item Timing

| Platform  | Config                       | Per-item | Total (50 items) | Source                          |
| --------- | ---------------------------- | -------- | ---------------- | ------------------------------- |
| TikTok    | 1 actor, 4096MB, video DL    | 3.9s     | 197.4s           | Apify concurrency exp, Phase 1b |
| TikTok    | 1 actor, 1024MB, video DL    | 3.9s     | 197.6s           | Apify concurrency exp, Phase 1b |
| TikTok    | 1 actor, 4096MB, no video DL | 3.5s     | 177.4s           | Apify concurrency exp, Phase 1b |
| Instagram | 1 actor, 4096MB              | 1.15s    | 57.5s            | Apify concurrency exp, Phase 1  |
| Instagram | 1 actor, 1024MB              | 0.73s    | 36.7s            | Apify concurrency exp, Phase 1  |

**Key findings:**

- TikTok is ~3-5x slower per item than Instagram
- Video download adds only +0.4s/item (negligible)
- 1024MB is faster or equal to 4096MB (network-bound, not CPU-bound)
- Startup overhead: ~5s (IG), ~12s (TT)

### TikWM Per-Request Timing

| Metric           | Value          | Source                 |
| ---------------- | -------------- | ---------------------- |
| p50 per-request  | 0.45s          | TIKWM_HANDOFF.md, N=50 |
| Throughput       | ~120 items/min | TIKWM_HANDOFF.md       |
| Apify throughput | ~25 items/min  | TIKWM_HANDOFF.md       |

### Agent Query Latency

| Metric               | Value   | Sample | Source           | Confidence                               |
| -------------------- | ------- | ------ | ---------------- | ---------------------------------------- |
| Single query latency | 7,435ms | N=1    | Exp 05 eval JSON | **`MEASURED (N=1)`** — single data point |

### Apify Concurrency Scaling

**Instagram (60 items, 1024MB each):**

| Config            | Wall-clock | Speedup       | Source                       |
| ----------------- | ---------- | ------------- | ---------------------------- |
| 1 actor x 60      | 38.5s      | baseline      | APIFY_CONCURRENCY_EXPERIMENT |
| 2 actors x 30     | 29.4s      | 1.3x          | APIFY_CONCURRENCY_EXPERIMENT |
| **4 actors x 15** | **21.0s**  | **1.8x**      | APIFY_CONCURRENCY_EXPERIMENT |
| 6 actors x 10     | 40.0s      | 0.96x (worse) | APIFY_CONCURRENCY_EXPERIMENT |

**TikTok (60 items, 1024MB each, video DL + 5 comments):**

| Config            | Wall-clock | Speedup  | Source                       |
| ----------------- | ---------- | -------- | ---------------------------- |
| 1 actor x 60      | 453.3s     | baseline | APIFY_CONCURRENCY_EXPERIMENT |
| 2 actors x 30     | 213.4s     | 2.1x     | APIFY_CONCURRENCY_EXPERIMENT |
| **4 actors x 15** | **120.7s** | **3.8x** | APIFY_CONCURRENCY_EXPERIMENT |

**Optimal: 4 concurrent actors** for both platforms. 6+ actors degrades IG performance.

### Production Projections

| Scenario                | Sequential  | 4 concurrent actors | Both platforms parallel | Source                       |
| ----------------------- | ----------- | ------------------- | ----------------------- | ---------------------------- |
| 1334 IG items           | ~14 min     | ~8 min              | —                       | APIFY_CONCURRENCY_EXPERIMENT |
| 400 TT items (video DL) | ~50 min     | ~13 min             | —                       | APIFY_CONCURRENCY_EXPERIMENT |
| **Both combined**       | **~64 min** | —                   | **~13 min**             | APIFY_CONCURRENCY_EXPERIMENT |

---

## 3. Per-Item Token Usage

### Gemini (Pipeline v3, gemini-3-flash-preview)

| Step                          | Avg input tokens | Avg output tokens | Max output config | Sample | Source           |
| ----------------------------- | ---------------- | ----------------- | ----------------- | ------ | ---------------- |
| Tier 2 Pass 1: Perception     | 8,002            | 1,948             | 16,384            | N=106  | Sprint Log Day 3 |
| Tier 2 Pass 2: Classification | 11,199           | 341               | 2,048             | N=106  | Sprint Log Day 3 |

Note: Classification input is larger than perception input because it includes the perception JSON dump (up to 6000 chars truncated) plus 3 keyframe images plus metadata.

**Production gap:** The pipeline code (`pipeline.py`) does NOT read `usageMetadata` from Gemini API responses. Token counts above are from experiment scripts only. Production token usage is untracked.

### Gemini (Vision Exp v1, gemini-2.5-flash)

| Metric          | Value     | Source           |
| --------------- | --------- | ---------------- |
| Total API calls | 130       | cost_report.json |
| Total tokens    | 1,842,562 | cost_report.json |
| Avg tokens/call | ~14,174   | Derived          |
| Total cost      | $0.314    | cost_report.json |

### Claude Haiku 4.5 (Agent)

| Metric                   | Value  | Sample | Source                  | Confidence           |
| ------------------------ | ------ | ------ | ----------------------- | -------------------- |
| Total tokens per query   | 17,460 | N=1    | Exp 05 eval JSON        | **`MEASURED (N=1)`** |
| Tool calls per query     | 1      | N=1    | Exp 05 eval JSON        | **`MEASURED (N=1)`** |
| Estimated avg tool calls | ~3     | —      | UNIT_ECONOMICS.md (old) | **`ESTIMATED`**      |

**Critical gap:** The "~3 tool calls avg" is an estimate with no measurement backing it. The single eval query used only 1 tool call. Multi-turn queries with semantic search + entity resolution could use 5-10+ tool calls.

### OpenAI Embeddings

| Metric                           | Value                   | Source                  |
| -------------------------------- | ----------------------- | ----------------------- |
| Model                            | text-embedding-3-small  | pipeline.py (hardcoded) |
| Dimensions                       | 1536                    | pipeline.py (hardcoded) |
| Input: avg embedding text length | ~1,934 chars (enriched) | Sprint Log Day 3        |
| Input: avg raw text length       | ~266 chars              | Sprint Log Day 3        |
| Pricing                          | $0.02/1M tokens         | DB seed, alembic/001    |

---

## 4. Quality Metrics

### Tier 1 vs Tier 2 Classification Agreement

| Metric            | Value                                                                                         | Sample | Source             | Confidence         |
| ----------------- | --------------------------------------------------------------------------------------------- | ------ | ------------------ | ------------------ |
| Topic exact match | **83%** (88/106)                                                                              | N=106  | Exp 03 Tier 1 test | `MEASURED (N=106)` |
| Main divergences  | "Edits" → entertainment_culture (T2: movies_tv), "startup building" → technology (T2: career) |        | Sprint Log Day 3   |                    |

### Human Evaluation (6 dimensions, 3-point scale)

Scored by founder across 47 items from Exp 02 v2 (gemini-2.5-flash, 2026-03-24):

| Dimension             | Avg (out of 3)    | Poor (1) | Adequate (2) | Strong (3) |
| --------------------- | ----------------- | -------- | ------------ | ---------- |
| Accuracy              | **2.40**          | 7 (15%)  | 14 (30%)     | 26 (55%)   |
| Completeness          | **1.98**          | 11 (23%) | 26 (55%)     | 10 (21%)   |
| Specificity           | **1.87**          | 13 (28%) | 27 (57%)     | 7 (15%)    |
| Entity Coverage       | **1.60**          | 24 (51%) | 18 (38%)     | 5 (11%)    |
| Classification Signal | **1.61**          | 25 (53%) | 14 (30%)     | 7 (15%)    |
| Vision Added Value    | **2.17**          | 9 (19%)  | 20 (43%)     | 17 (36%)   |
| **Overall**           | **11.6/18 (64%)** |          |              |            |

Source: `workbench/experiments/02-vision-analysis/results/vision_v2/eval_scores_v2.json`

**Key weaknesses:** Entity Coverage (51% Poor) and Classification Signal (53% Poor) are the two most product-critical dimensions and scored worst. These were scored on gemini-2.5-flash; the production pipeline now uses gemini-3-flash-preview with revised prompts — **no human eval exists for the current production model/prompts.**

### Vision vs Text-Only Classification Agreement (by text tier)

| Text tier                  | Topic   | Genre   | Affect  | Style   | Provenance | Sample |
| -------------------------- | ------- | ------- | ------- | ------- | ---------- | ------ |
| Rich text (caption + subs) | 80%     | 60%     | 90%     | 30%     | 100%       | N=10   |
| Caption only               | 67%     | 43%     | 38%     | 24%     | 90%        | N=21   |
| Low text                   | **12%** | **31%** | **44%** | **12%** | 94%        | N=16   |

Source: Exp 02 v2, Sprint Log Day 2. `MEASURED (N=47)`

**Interpretation:** Vision is essential for low-text items — Topic agreement drops to 12% without it.

### Parse Error Rates

| Experiment                           | Rate         | Cause                         | Source           |
| ------------------------------------ | ------------ | ----------------------------- | ---------------- |
| Exp 02 v1 (maxOutputTokens=4096)     | 10% (13/130) | Truncated JSON on long videos | Sprint Log Day 2 |
| Exp 02 v2 (maxOutputTokens=8192)     | 11% (5/47)   | Truncated JSON on long videos | Exp 02 v2 report |
| Exp 03 Exp A (maxOutputTokens=16384) | 0.9% (1/106) | Single parse error            | Exp 03 README    |

### Classification Accuracy vs Golden Set

| Metric             | Value | Confidence         |
| ------------------ | ----- | ------------------ |
| Overall accuracy   | —     | **`NOT MEASURED`** |
| Per-facet accuracy | —     | **`NOT MEASURED`** |

`run_evals.py` exists with a 60% pass threshold, but `workbench/evals/results/` is empty — no eval has ever been saved against the golden set.

### Affect Label Distribution (Pipeline v3 vs previous)

| Label                     | Exp 02 v2 (gemini-2.5-flash) | Exp 03 Exp A (gemini-3-flash) |
| ------------------------- | ---------------------------- | ----------------------------- |
| "inspiring" as dominant   | ~45%                         | **11%**                       |
| "informative" as dominant | —                            | **62%**                       |

Source: Sprint Log Day 2 and Day 3. The "informative" label was added between experiments to address "inspiring" overassignment.

---

## 5. Throughput & Scaling

### Current Pipeline Configuration

| Parameter               | Value                          | Source                  |
| ----------------------- | ------------------------------ | ----------------------- |
| `PERCEIVE_CONCURRENCY`  | 20                             | pipeline.py             |
| `CLASSIFY_CONCURRENCY`  | 20                             | pipeline.py             |
| `EMBEDDING_BATCH_SIZE`  | 100                            | pipeline.py             |
| `APIFY_BATCH_SIZE`      | 50                             | pipeline.py             |
| `STEP_TIME_BUDGET_S`    | 360 (6 min)                    | pipeline.py             |
| `TIKWM_DELAY_S`         | 0.25 (stay under 5 RPS)        | pipeline.py             |
| `APIFY_POLL_INTERVAL_S` | 5                              | pipeline.py             |
| `APIFY_MAX_WAIT_S`      | 600                            | pipeline.py             |
| `GEMINI_MODEL`          | gemini-3-flash-preview (env)   | pipeline.py             |
| `EMBEDDING_MODEL`       | text-embedding-3-small         | pipeline.py (hardcoded) |
| `EMBEDDING_DIMENSIONS`  | 1536                           | pipeline.py (hardcoded) |
| `REQUEST_TIMEOUT`       | 30s (90s for video perception) | pipeline.py             |

### Agent Rate Limits

| Parameter                    | Value | Source    |
| ---------------------------- | ----- | --------- |
| `MAX_TOOL_CALLS_PER_QUERY`   | 50    | agent.py  |
| `MAX_TOOL_CALLS_PER_HOUR`    | 200   | agent.py  |
| `chat_rate_limit_per_minute` | 20    | config.py |

### Projected Pipeline Times

| Items | Apify (4 actors) | Gemini (20 concurrent) | Embedding | Total (estimated) |
| ----- | ---------------- | ---------------------- | --------- | ----------------- |
| 100   | ~2 min           | ~2 min                 | ~1s       | ~4 min            |
| 500   | ~10 min          | ~10 min                | ~5s       | ~20 min           |
| 1,000 | ~20 min          | ~20 min                | ~10s      | ~40 min           |
| 2,000 | ~40 min          | ~40 min                | ~20s      | ~80 min           |

These projections assume 4 concurrent Apify actors (optimal per experiment), 20 concurrent Gemini calls, and linear scaling. Confidence: `ESTIMATED` — no measurements at 500+ items.

---

## 6. Model & Provider Reference

### Current Model Stack

| Role                        | Provider  | Model                     | Input pricing | Output pricing | Source                             |
| --------------------------- | --------- | ------------------------- | ------------- | -------------- | ---------------------------------- |
| Agent orchestrator          | Anthropic | claude-haiku-4-5-20251001 | $1.00/MTok    | $5.00/MTok     | CEO_PLAN_REVIEW                    |
| Perception + classification | Google    | gemini-3-flash-preview    | ~$0.10/MTok   | ~$0.40/MTok    | Sprint Log Day 3 (model selection) |
| Embeddings                  | OpenAI    | text-embedding-3-small    | $0.02/MTok    | —              | DB seed (alembic/001)              |

Note: Gemini pricing above is approximate based on gemini-2.5-flash rates ($0.30/$2.50 per MTok for input/output); gemini-3-flash-preview pricing may differ. The measured per-item costs in Section 1 are more reliable than model-price-derived estimates.

### DB-Seeded Pricing Constants

From `alembic/versions/001_initial_schema.py`:

| Provider | SKU                    | Unit price                  |
| -------- | ---------------------- | --------------------------- |
| Apify    | clockworks video       | $0.002/video                |
| OpenAI   | gpt-5.1 input          | $1.25/MTok                  |
| OpenAI   | gpt-5.1 output         | $10.00/MTok                 |
| OpenAI   | text-embedding-3-small | $0.02/MTok                  |
| OpenAI   | Whisper                | $0.006/min ($0.0001/second) |

Note: These are reference prices seeded in the `cost_models` table. The pipeline does not currently join these against actual usage — `UploadPipelineRun.total_cost_usd` stays at 0.

### Apify Plan Pricing

| Plan     | Subscription | PPE/item (TikTok)      | Recommended at      | Source                  |
| -------- | ------------ | ---------------------- | ------------------- | ----------------------- |
| Starter  | $29/mo       | $0.0140                | 0-15 paying users   | UNIT_ECONOMICS.md (old) |
| Scale    | $199/mo      | $0.0106 (24% discount) | 15-100 paying users | UNIT_ECONOMICS.md (old) |
| Business | $999/mo      | $0.0073 (48% discount) | 100+ paying users   | UNIT_ECONOMICS.md (old) |

### TikWM Pricing

| Plan       | Cost    | Quota                            | Confidence                                                         |
| ---------- | ------- | -------------------------------- | ------------------------------------------------------------------ |
| Free/BASIC | Free    | 1000 quota/month, 120 RPM, 5 RPS | `MEASURED`                                                         |
| Paid tiers | Unknown | Unknown                          | **`NOT MEASURED`** — requires login to tikwmapi.com/dashboard/plan |

---

## 7. Business Context

### Total Cost Per User by Library Size

Assumes Apify Starter plan, 50 agent queries/month:

| Library size | Ingestion (one-time) | Monthly agent (50 queries) | Total month 1 | Ongoing/mo |
| ------------ | -------------------- | -------------------------- | ------------- | ---------- |
| 200          | $3.88                | $0.25                      | $4.13         | $0.25      |
| 500          | $9.70                | $0.25                      | $9.95         | $0.25      |
| 1,000        | $19.40               | $0.25                      | $19.65        | $0.25      |
| 2,000        | $38.80               | $0.25                      | $39.05        | $0.25      |

Source: UNIT_ECONOMICS.md (old), derived from measured per-item costs.

**Key insight:** Ingestion is the dominant cost. A 1000-item user costs ~$19.40 to onboard but only ~$0.25/mo ongoing.

### Fixed Monthly Infrastructure

| Service                    | Cost/mo      | Notes                       |
| -------------------------- | ------------ | --------------------------- |
| Apify Starter subscription | $29          | Includes $29 prepaid credit |
| Supabase Pro               | $25          | DB + auth + storage         |
| Render (API hosting)       | $25          | Starter instance            |
| Vercel Pro (frontend)      | $20          |                             |
| AWS Lambda (pipeline)      | ~$5          | At <100 users               |
| Sentry + PostHog           | $0           | Free tiers                  |
| Domain + email (Resend)    | ~$5          |                             |
| **TOTAL**                  | **~$109/mo** |                             |

### Breakeven

- At $10/mo subscription: 11 paying users
- At $15/mo subscription: 8 paying users
- At $20/mo subscription: 6 paying users
- **Overall breakeven: ~15-20 paying users** (with user mix)

### Margin by Tier

| Tier               | Revenue/user/mo | Month 1 COGS  | Month 1 margin       | Month 2+ COGS | Month 2+ margin | Payback    |
| ------------------ | --------------- | ------------- | -------------------- | ------------- | --------------- | ---------- |
| Free               | $0              | $3.88 + $0.25 | -$4.13 (loss leader) | $0.25         | -$0.25          | Never      |
| Starter (1K items) | $9              | $14 + $1      | -67%                 | $0 + $1       | **89%**         | 1.8 months |
| Pro (3K items)     | $19             | $42 + $1      | -126%                | $0 + $1       | **95%**         | 2.3 months |
| Power (10K items)  | $39             | $140 + $1     | -262%                | $0 + $1       | **97%**         | 3.7 months |

Source: UNIT_ECONOMICS.md (old). All tiers profitable by month 3.

### Pricing Structure

|                | Free  | Starter    | Pro         | Power      |
| -------------- | ----- | ---------- | ----------- | ---------- |
| Monthly price  | $0    | $9/mo      | $19/mo      | $39/mo     |
| Items included | 200   | 1,000/mo   | 3,000/mo    | 10,000/mo  |
| Agent queries  | 20/mo | 200/mo     | Unlimited   | Unlimited  |
| Overage        | —     | $0.03/item | $0.025/item | $0.02/item |

---

## 8. Data Gaps & Proposed Experiments

### Gap 1: Agent Query Cost (HIGH PRIORITY)

**What's missing:** The $0.005/query figure is based on a single eval query with 1 tool call and 17,460 tokens. Real usage will include multi-turn conversations, semantic search (OpenAI embedding call), entity resolution (external API calls), and complex queries requiring 3-10+ tool calls.

**Why it matters:** Agent queries are the ongoing cost driver. If the real average is $0.01-0.02/query, the $0.25/month estimate for 50 queries doubles or quadruples, affecting all margin calculations.

**Proposed experiment:**

1. Expand `workbench/experiments/05-agent-eval/queries.json` with 20-30 diverse queries covering: simple retrieval, filtered search, semantic search, entity resolution, multi-turn, statistical, and edge cases
2. Run `run_agent_eval.py` with the full query set
3. Capture per-query: `total_tokens`, `tool_calls_count`, `tool_sequence`, `elapsed_ms`
4. Compute: mean/median/p95 tokens, mean/median/p95 cost, cost by query complexity tier
5. **Effort:** ~2 hours (write queries + run + analyze)

### Gap 2: Entity Resolution Cost (MEDIUM PRIORITY)

**What's missing:** Zero measurements for Google Maps Places, Google Books, TMDB, or Spotify API costs per resolution call. These are triggered by the agent's `resolve_entity` tool.

**Why it matters:** Entity resolution is a key product feature (linking "that pizza place" to a Google Maps result). If resolution is expensive, it affects whether to resolve eagerly (pipeline) vs lazily (agent).

**Proposed experiment:**

1. Select 50 items with entities spanning all 4 provider types (places, books, movies, music)
2. Call each resolver with timing + request counting
3. Measure: latency per call, rate limit behavior, any per-call costs (most of these APIs have free tiers with limits)
4. **Effort:** ~1 hour

### Gap 3: Classification Accuracy vs Golden Set (MEDIUM PRIORITY)

**What's missing:** `run_evals.py` exists with a 60% pass threshold and a golden set of 106 items, but no eval has ever been saved. We don't know the production pipeline's classification accuracy.

**Why it matters:** Classification quality directly affects search and agent response quality. Without a baseline measurement, we can't track quality regressions when prompts change.

**Proposed experiment:**

1. Annotate golden set items with expected classification (if not already done)
2. Run `run_evals.py --verbose --save` against current pipeline
3. Save results to `workbench/evals/results/`
4. Report per-facet accuracy and overall score
5. **Effort:** ~3 hours (annotation is the bottleneck if not done)

### Gap 4: Per-Item Gemini Token Tracking in Production (LOW PRIORITY)

**What's missing:** The pipeline code discards `usageMetadata` from Gemini API responses. Token counts are only available from experiment scripts.

**Why it matters:** As prompts evolve, per-item cost will drift. Without token tracking, cost changes are invisible until the bill arrives.

**Proposed fix:**

1. Read `usageMetadata.promptTokenCount` and `usageMetadata.candidatesTokenCount` from Gemini responses in `_perceive_one_sync` and `_classify_one_sync`
2. Write to `ProcessingStep` table (schema already exists, never populated)
3. **Effort:** ~1 hour code change + tests

### Gap 5: TikWM Paid Tier Pricing (LOW PRIORITY)

**What's missing:** TikWM paid plan pricing is unknown — the free tier (1000 quota/month) is insufficient for production.

**Why it matters:** TikWM is 14x cheaper than Apify per item. If paid tier pricing is reasonable, it fundamentally changes the unit economics.

**Proposed action:** Log into tikwmapi.com/dashboard/plan and document paid tier pricing.
**Effort:** 10 minutes

### Gap 6: Instagram-Specific Per-Item Cost (LOW PRIORITY)

**What's missing:** All Apify profiling was done on TikTok. Instagram per-item cost is not separately measured.

**Why it matters:** Instagram items may have different cost profiles (no video download for carousels, different comment structures).

**Proposed experiment:**

1. Run Apify profiler on 50-100 Instagram items
2. Measure per-item cost and compare to TikTok
3. **Effort:** ~30 minutes

### Gap 7: Human Eval on Current Production Model (MEDIUM PRIORITY)

**What's missing:** Human eval scores (Section 4) are from gemini-2.5-flash with older prompts. The production pipeline now uses gemini-3-flash-preview with revised prompts (v2 perception, v2 classification). No human eval exists for the current setup.

**Why it matters:** The quality numbers cited everywhere may not reflect current production quality.

**Proposed experiment:**

1. Run current production pipeline on 30-50 diverse items
2. Score using same 6-dimension rubric from Exp 02 v2
3. Compare against Exp 02 v2 baseline (64% overall)
4. **Effort:** ~4 hours (pipeline run + manual scoring)

---

## Appendix: Data Provenance

Every experiment referenced in this document:

| ID          | Name                              | Date       | Items       | Model                     | Key artifact                                                                      |
| ----------- | --------------------------------- | ---------- | ----------- | ------------------------- | --------------------------------------------------------------------------------- |
| Exp 01      | Apify Profiling                   | 2026-03-24 | 903         | —                         | `workbench/experiments/01-apify-profiling/README.md`                              |
| Exp 02 v1   | Vision Analysis (prompt variants) | 2026-03-24 | 15          | gemini-2.5-flash          | `workbench/experiments/02-vision-analysis/results/vision_analysis_samples/`       |
| Exp 02 v2   | Vision Analysis (full pipeline)   | 2026-03-24 | 47          | gemini-2.5-flash          | `workbench/experiments/02-vision-analysis/results/vision_v2/EXPERIMENT_REPORT.md` |
| Exp 03 A    | Pipeline v3 (no grounding)        | 2026-03-26 | 106         | gemini-3-flash-preview    | `workbench/experiments/03-pipeline-v3/README.md`                                  |
| Exp 03 B    | Pipeline v3 (grounding ON)        | 2026-03-26 | 106         | gemini-2.5-flash          | `workbench/experiments/03-pipeline-v3/README.md`                                  |
| Exp 03 T1   | Tier 1 (keyframes)                | 2026-03-26 | 106         | gemini-3-flash-preview    | `workbench/experiments/03-pipeline-v3/README.md`                                  |
| Exp 03 E2E  | E2E Runtime Test                  | 2026-03-26 | 100         | gemini-3-flash-preview    | `workbench/experiments/03-pipeline-v3/README.md`                                  |
| Exp 05      | Agent Eval                        | 2026-03-28 | 1 query     | claude-haiku-4-5-20251001 | `workbench/experiments/05-agent-eval/results/eval_20260328_045545.json`           |
| TikWM       | TikWM Validation                  | 2026-03-30 | 50          | —                         | `docs/TIKWM_HANDOFF.md`                                                           |
| Apify Conc. | Apify Concurrency                 | 2026-03-30 | 60 per test | —                         | `docs/APIFY_CONCURRENCY_EXPERIMENT.md`                                            |
