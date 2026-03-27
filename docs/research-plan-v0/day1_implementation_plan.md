# Plan: Crash Course Day 1 -- Data Profiling + Apify Validation

## Context

The [crash_course.md](crash_course.md) lays out a 7-day research sprint to validate Attic's two-tier processing architecture empirically. Day 1 establishes the data foundation -- profiling Apify responses and validating reliability at scale. Every downstream decision (vision analysis, ontology revision, embedding strategy) depends on knowing what the data actually looks like.

## Prerequisites Checklist

| Prerequisite | Status | Notes |
|---|---|---|
| Dev environment | **READY** | Supabase Cloud, `.venv`, workbench all set |
| Apify API token | **EXISTS** | In `workbench/.env` -- validate with 1-URL test before full run |
| Google AI / OpenAI keys | **EXISTS** | Not needed for Day 1 |
| Real TikTok data export | **User will add** | Place ZIP or extracted JSON in `workbench/data/my-export/` |
| Core Python packages | **READY** | httpx, pandas, numpy, matplotlib, seaborn, Pillow all installed |
| ML packages (Day 4+) | **NOT YET** | open-clip-torch, scikit-learn, hdbscan -- install later |
| FFmpeg | **READY** | `/opt/homebrew/bin/ffmpeg` |

## Day 1 Tasks

### Task 1.1 -- Apify Data Profiler Script

**File:** `workbench/scripts/apify_profiler.py`

**What it does:** Takes a TikTok export (ZIP or extracted JSON), sends URLs through Apify in batches, and produces a structured data quality report.

**Reuse from existing code:**
- **TikTok export parser**: `src/backend/app/services/tiktok_parser.py` -- `parse_tiktok_export()` handles ZIP files with multiple format variants (Like List, Favorite Videos, combined exports). Returns `TikTokVideoReference(url, timestamp, interaction_type)`.
- **Apify batch calling**: `src/backend/app/services/pipeline.py:251-298` -- `_run_apify_batch()` pattern (POST to actor, poll 5s intervals, fetch dataset items)
- **Response field mapping**: `src/backend/app/services/pipeline.py:301-353` -- `_map_apify_to_update()` shows all Apify response fields and their transformations
- **URL normalization**: `src/backend/app/services/pipeline.py:94-110` -- `_normalize_tiktok_url()` (tiktokv.com -> tiktok.com)
- **Platform ID extraction**: `src/backend/app/services/pipeline.py:113-130` -- `_extract_platform_id()` regex
- **Apify constants**: `APIFY_ACTOR_ID = "clockworks~tiktok-scraper"`, `APIFY_BATCH_SIZE = 50`, `APIFY_POLL_INTERVAL_S = 5`, `APIFY_MAX_WAIT_S = 600`

**Implementation approach:**
1. **Input handling**: Accept either a ZIP path (use `parse_tiktok_export()`) or a raw JSON file (Like List.json format: `{"Like List": {"ItemFavoriteList": [{"link": "...", "date": "..."}]}}`)
2. **URL extraction**: Normalize all URLs, extract platform IDs, deduplicate
3. **Apify calls**: Batch of 50, sync httpx (workbench script -- simplicity over perf), poll + fetch results
4. **Profile computation** on each response:
   - **Fill rate per field**: caption_text, hashtags, creator (authorMeta), thumbnail_url (covers.default), video_url, subtitle links, music (musicMeta), play_count (playCount), like_count (diggCount), comment_count, share_count (shareCount), collect_count (collectCount), media_type
   - **Caption analysis**: length distribution histogram, % empty, % emoji-only (`^[\p{Emoji}\s]*$`)
   - **Hashtag count distribution**
   - **Media type breakdown**: video vs image vs slideshow (from imagePost field)
   - **video_url availability**: % with downloadable URLs (critical for Day 2 video analysis)
   - **subtitle availability**: % with subtitle text/links
5. **Save raw responses**: First 20 to `workbench/data/apify_raw_samples/` (for manual inspection)
6. **Output report**: `workbench/data/apify_profile_report.json`
7. **Print summary**: Human-readable table + matplotlib histograms saved as PNGs

**CLI interface:**
```bash
# From ZIP
.venv/bin/python workbench/scripts/apify_profiler.py workbench/data/my-export/export.zip --limit 100

# From extracted JSON
.venv/bin/python workbench/scripts/apify_profiler.py "workbench/data/my-export/Like List.json" --limit 100

# Quick connectivity test
.venv/bin/python workbench/scripts/apify_profiler.py <path> --limit 5
```

**Key design decisions:**
- Synchronous httpx (not async) -- workbench script, clarity over performance
- Saves raw responses so we never re-call Apify for the same URLs
- `dotenv` to load `workbench/.env` for APIFY_API_TOKEN
- Graceful Apify failure handling (log and continue, include failure rate in report)
- Reuses `_normalize_tiktok_url` and `_extract_platform_id` logic inline (copy pattern, not import -- workbench scripts are standalone)

### Task 1.2 -- Scale Test

**Built into the profiler** via `--scale-test` flag. Runs progressively larger batches:

1. 50 URLs -> measure wall-clock time, failure rate
2. 200 URLs -> same
3. 500 URLs -> same (if export large enough)

**Metrics per batch:**
- Wall-clock time total and per-item
- Apify run duration (from status response)
- Failure rate (URLs returning no data)
- Rate limiting events (429s)
- Estimated cost

**Output:** Appended to `apify_profile_report.json` under `scale_tests` key.

### Task 1.3 -- Video URL Stability Test

**File:** `workbench/scripts/url_stability_test.py`

**What it does:** Tests whether Apify's video download URLs expire.

1. Read 10 items with video_url from `apify_raw_samples/`
2. HTTP HEAD each URL -> record status code, content-length, content-type
3. Save results with timestamp to `workbench/data/url_stability_results.json`
4. Print instructions to re-run at +1hr and +6hr to compare

Simple script -- ~60 lines, httpx HEAD requests, JSON output.

## Files Created/Modified

| File | Action |
|---|---|
| `workbench/scripts/apify_profiler.py` | **NEW** -- Main profiler + scale test |
| `workbench/scripts/url_stability_test.py` | **NEW** -- URL expiration tester |
| `workbench/data/apify_raw_samples/` | **NEW dir** -- Raw Apify JSON responses (gitignored) |
| `workbench/data/apify_profile_report.json` | **NEW** -- Structured quality report (gitignored) |
| `workbench/data/url_stability_results.json` | **NEW** -- URL test results (gitignored) |

No existing files modified.

## Verification

1. `--limit 5` smoke test: validates Apify connectivity and token
2. `--limit 50` for initial profile: check `apify_profile_report.json` has fill rates for all fields
3. `apify_raw_samples/` should contain 10-20 saved JSON responses for manual inspection
4. `url_stability_test.py` should show 10 results with HTTP 200 status codes
5. Visual: caption length and hashtag count histograms render correctly

## Execution Order

1. Write `apify_profiler.py`
2. User places TikTok export in `workbench/data/my-export/`
3. Run `--limit 5` smoke test
4. Run `--limit 100` for full profile
5. Run `--scale-test` if export has 500+ URLs
6. Write `url_stability_test.py`
7. Run URL stability test
8. Review report and raw samples
