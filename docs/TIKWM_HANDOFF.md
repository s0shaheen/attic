# TikWM Integration Handoff

**Issue:** #123
**Date:** 2026-03-30
**Status:** Experiment complete, implementation ready

---

## What

Replace Apify as the primary TikTok enrichment provider with [TikWM API](https://tikwmapi.com/docs.html). Instagram stays on Apify.

## Why

Apify is 72% of per-item ingestion cost ($0.014 of $0.0194 total).

| | TikWM | Apify |
|--|-------|-------|
| Cost/item | ~$0.001 | $0.014 |
| Latency (50 items) | ~25s | ~2 min |
| Per-request | 0.45s p50 | batch model |
| Throughput | ~120 items/min | ~25 items/min |

## Experiment Results (50 real URLs from our data)

- **100% success rate** (50/50)
- **21/28 fields populated**, all 5 critical fields covered
- **98% video download success**, 100% thumbnail + audio
- **15 fields exact match** with Apify, 6 differ only in formatting

### Field Coverage

**Exact match (15):** creator_username, creator_name, creator_id, comment_count, share_count, collect_count, video_duration, video_created_at, is_ad, media_type, music_id, music_author, music_is_original, play_count, like_count

**Format differs but equivalent (6):** caption_text (TikWM strips \n — cleaner), hashtags (parsed from title, 88% match), thumbnail_url (TikWM 100% vs Apify 0%), music_name (TikWM appends " - artist"), location_created (region code vs name), mentions (empty string vs array)

**Not available, non-critical (4):** creator_followers, creator_verified (need extra /user/info call), is_pinned, effect_stickers

**Untested (3):** is_slideshow, image_count, image_urls (no slideshows in sample)

## TikWM API Details

- **Base URL:** `https://api.tikwmapi.com`
- **Auth:** `x-tikwmapi-key` header
- **Video endpoint:** `GET /?url={tiktok_url}` — returns full metadata + download URLs
- **User endpoint:** `GET /user/info?unique_id={id}` — for follower count/verified (extra quota)
- **Rate limits:** BASIC plan = 120 RPM / 5 RPS / 1000 quota/month (free)
- **Key:** In `.env.master` as `TIKWM_API_KEY`
- **Paid plan pricing:** Unknown — dashboard requires login to view

## Implementation Plan

### New functions (pipeline.py)

```python
TIKWM_API_KEY = os.environ.get("TIKWM_API_KEY", "")
TIKWM_BASE_URL = "https://api.tikwmapi.com"
TIKWM_DELAY_S = 0.25  # Stay under 5 RPS

def _tikwm_get(path, params) -> dict       # HTTP helper
def _run_tikwm_batch(urls) -> list[dict]    # Sequential with delay, skips failures
def _map_tikwm_to_update(data) -> dict      # Maps to MediaEvent columns
```

### Key mapping logic

```python
title = data["title"]                          # "Caption text #hashtag1 #hashtag2"
hashtags = re.findall(r"#(\w+)", title)        # ["hashtag1", "hashtag2"]
caption = re.sub(r"\s*#\w+", "", title).strip() # "Caption text"

author = data["author"]
music = data["music_info"]
# creator_username = author["unique_id"]
# music_id = str(music["id"])
# create_time = data["create_time"]  (unix timestamp, same as Apify)
```

### Modified step_apify_enrich()

```
if TIKWM_API_KEY:
    1. Run _run_tikwm_batch(urls) for all TikTok items
    2. Map results via _map_tikwm_to_update()
    3. Collect failures (items TikWM missed)
    4. If failures and APIFY_API_TOKEN: run _run_apify_batch() on failures only
    5. Log tikwm_count + apify_fallback_count
elif APIFY_API_TOKEN:
    (existing Apify-only path)
else:
    (dev mode fake data)
```

### Files to modify

- `src/backend/app/services/pipeline.py` — add TikWM functions + modify step_apify_enrich
- `src/backend/tests/unit/test_pipeline_steps.py` — add tests for mapping + batch
- `.env.master` — already has `TIKWM_API_KEY`

### No new dependencies needed

TikWM is plain HTTP GET — uses existing `urllib.request`.

## Open Questions

1. **Paid tier pricing** — need to log into tikwmapi.com/dashboard/plan to see plans
2. **Slideshow handling** — no slideshows in our test data. Need to find a slideshow TikTok URL and verify TikWM returns image data
3. **Quota at scale** — free tier is 1000/month. Need paid plan for production
4. **Reliability over time** — TikWM is a third-party wrapper. Monitor for outages. The Apify fallback mitigates this

## Verification Checklist

- [ ] Check paid plan pricing at tikwmapi.com
- [ ] Test with a slideshow/image TikTok URL
- [ ] Implement the changes per plan above
- [ ] Run unit tests (expect ~13 new tests)
- [ ] Run full pipeline with TIKWM_API_KEY set, verify items enriched
- [ ] Monitor first production run for TikWM success rate vs Apify fallback rate
