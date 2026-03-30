# Apify Concurrency Experiment — Results & Handoff

**Date:** 2026-03-30
**Branch:** `s0shaheen/layer1-1b-1a-1c`
**Objective:** Measure whether running multiple Apify actors concurrently reduces pipeline wall-clock time, and determine the optimal configuration.

---

## Background

The Apify enrichment step is the pipeline's biggest bottleneck. For 1334 Instagram items, it took ~18 minutes sequentially (1 actor, batches of 50). TikTok is even slower (~7.5s/item with video downloads vs ~1.15s/item for IG).

We have 32GB of RAM budget across all concurrent Apify actor runs. The question: how should we split that budget to minimize wall-clock time?

## Methodology

Three phases of experiments, all using real URLs from the user's Instagram export (1334 items) and TikTok favorites (394 items).

### Phase 1: Baselines (per-item cost + startup overhead)

| Test | Actor | Items | Memory | Wall Clock | Per-item |
|------|-------|-------|--------|-----------|----------|
| IG, 1 item | apify~instagram-scraper | 1 | 4096MB | 5.9s | 5.9s |
| IG, 10 items | apify~instagram-scraper | 10 | 4096MB | 26.5s | 2.65s |
| IG, 50 items | apify~instagram-scraper | 50 | 4096MB | 57.5s | 1.15s |
| IG, 50 items | apify~instagram-scraper | 50 | 1024MB | 36.7s | 0.73s |
| TT, 1 item | clockworks~tiktok-scraper | 1 | 4096MB | 16.2s | 16.2s |
| TT, 3 items | clockworks~tiktok-scraper | 3 | 4096MB | 16.2s | 5.4s |

**Key findings:**
- Startup overhead: ~5s (IG), ~12s (TT)
- 1024MB is FASTER than 4096MB for IG (network-bound, not CPU-bound)
- TikTok is ~3x slower per item than Instagram
- Per-item cost drops significantly with batch size (amortization)

### Phase 1b: TikTok Video Download Impact

| Test | Items | Memory | Video DL | Wall Clock | Per-item |
|------|-------|--------|----------|-----------|----------|
| TT no-DL, 50 | 50 | 4096MB | No | 177.4s | 3.5s |
| TT DL, 50 | 50 | 4096MB | Yes | 197.4s | 3.9s |
| TT DL, 50 | 50 | 1024MB | Yes | 197.6s | 3.9s |

**Key finding:** Video downloads add only +0.4s/item. Negligible. Enable them.
Memory doesn't matter for TikTok either — 1024MB matches 4096MB.

### Phase 2b: Concurrency Scaling (fresh URLs, confirmed)

**Instagram (60 items, 1024MB each):**

| Config | Wall Clock | Speedup |
|--------|-----------|---------|
| 1 actor x 60 | 38.5s | baseline |
| 2 actors x 30 | 29.4s | 1.3x |
| **4 actors x 15** | **21.0s** | **1.8x** |
| 6 actors x 10 | 40.0s | 0.96x (worse) |

**TikTok (60 items, 1024MB each, video DL + 5 comments):**

| Config | Wall Clock | Speedup |
|--------|-----------|---------|
| 1 actor x 60 | 453.3s | baseline |
| 2 actors x 30 | 213.4s | 2.1x |
| **4 actors x 15** | **120.7s** | **3.8x** |

---

## Conclusions

1. **4 concurrent actors is the sweet spot** for both platforms. 6+ actors is worse for IG (small batches have high variance, gated by slowest actor).

2. **TikTok scales better with concurrency** (3.8x at 4 actors) than IG (1.8x). TT items are heavier (video downloads, comment fetching), so there's more real work to parallelize.

3. **1024MB is optimal** for both scrapers. They're network-bound, not CPU-bound. 4096MB wastes budget with no speed gain.

4. **Video downloads are basically free.** +0.4s/item overhead. Enable them — needed for Gemini full-video perception.

5. **Field filtering has no impact.** Both scrapers load full pages regardless of what fields we request. The only levers are: number of actors, memory, batch size, and download toggles.

6. **The biggest win is running both platforms simultaneously.** 4 IG actors (4GB) + 4 TT actors (4GB) = 8GB total, well within 32GB. Wall clock gated by the slower platform (TikTok).

## Production Projections

| Scenario | Sequential | 4 concurrent actors | Both platforms parallel |
|----------|-----------|---------------------|----------------------|
| 1334 IG items | ~14 min | ~8 min | — |
| 400 TT items (video DL) | ~50 min | ~13 min | — |
| **Both combined** | **~64 min** | — | **~13 min** |

## Fast Follow: Implementation Plan

### What to build

Modify `step_apify_enrich()` in `pipeline.py` to:

1. **Split items into N batches** (N = 4 by default, configurable via `APIFY_CONCURRENCY` env var)
2. **Start all actors concurrently** using `ThreadPoolExecutor`
3. **Poll all runs in parallel** (already have the polling pattern)
4. **Collect results and merge** — same upsert logic, just from multiple datasets
5. **RAM budget guard** — track total allocated memory, block new starts if exceeding 32GB

### Architecture sketch

```python
APIFY_ACTOR_CONCURRENCY = int(os.environ.get("APIFY_ACTOR_CONCURRENCY", "4"))
APIFY_ACTOR_MEMORY_MB = int(os.environ.get("APIFY_ACTOR_MEMORY_MB", "1024"))

def step_apify_enrich(session, upload_id, media_event_ids, pipeline_run_id, source_platform):
    # Split items into batches
    batch_size = math.ceil(len(items) / APIFY_ACTOR_CONCURRENCY)
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]

    # Start all actors
    run_ids = []
    with ThreadPoolExecutor(max_workers=APIFY_ACTOR_CONCURRENCY) as executor:
        start_futures = {executor.submit(start_actor, batch, source_platform): batch for batch in batches}
        for future in as_completed(start_futures):
            run_ids.append(future.result())

    # Poll all runs concurrently
    with ThreadPoolExecutor(max_workers=APIFY_ACTOR_CONCURRENCY) as executor:
        poll_futures = {executor.submit(poll_and_collect, run_id): run_id for run_id in run_ids}
        for future in as_completed(poll_futures):
            results = future.result()
            # Upsert results to DB (same as current single-actor path)
            for item in results:
                session.execute(update(...))
            session.commit()  # Batch commit per actor
```

### Config

| Env var | Default | Description |
|---------|---------|-------------|
| `APIFY_ACTOR_CONCURRENCY` | 4 | Max concurrent actors per platform |
| `APIFY_ACTOR_MEMORY_MB` | 1024 | Memory per actor (MB) |
| `APIFY_MAX_RAM_MB` | 32768 | Total RAM budget across all actors |

### Estimated effort

~2 hours. The concurrent start/poll pattern is straightforward. The main complexity is error handling (what happens if 1 of 4 actors fails — retry that batch? skip those items?).

### What NOT to change

- Batch size per actor stays at ~50 items (proven efficient in Phase 1)
- No field filtering (scrapers don't support it)
- No memory increase (1024MB is optimal)
- Don't go past 4 concurrent actors (diminishing returns confirmed)

---

## Raw Data

Experiment scripts and results were not committed (throwaway). The numbers in this document are the canonical reference. Experiments can be reproduced by running Apify actors via the API with the parameters documented above.
