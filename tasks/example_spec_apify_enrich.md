# Task 3.4: APIFY_ENRICH Step

> **Epic**: 3 - Processing Pipeline
> **PRD Reference**: F4: Processing Pipeline
> **Status**: Ready
> **Estimated Complexity**: Medium (3-5 days)

---

## Overview

Implement the APIFY_ENRICH pipeline step that fetches TikTok video metadata using the Apify Clockworks Data Extractor. This step transforms raw TikTok URLs into rich metadata including creator info, engagement metrics, captions, and hashtags. It's the foundation for all downstream enrichment and directly enables users to browse their library with meaningful context.

---

## User Story

> As a user who uploaded my TikTok data, I want each video enriched with metadata (creator, caption, engagement stats) so that I can browse and understand my saved content.

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-1 | Accept a batch of TikTok URLs (up to 50) and return metadata for each | Must | Batch size per Apify pricing optimization |
| FR-2 | Extract and normalize all fields defined in `media_events` table | Must | See Data Model section |
| FR-3 | Handle deleted/private videos gracefully (mark as `unavailable`) | Must | ~5-10% of videos may be unavailable |
| FR-4 | Retry transient failures with exponential backoff | Must | Max 3 attempts per batch |
| FR-5 | Track per-video cost in `processing_steps` table | Must | For budget monitoring |
| FR-6 | Support rate limiting to stay within Apify quotas | Should | 100 requests/min on Business tier |
| FR-7 | Cache responses to avoid re-fetching same video within 24h | Could | Reduces cost for re-uploads |

### Non-Functional Requirements

| ID | Requirement | Target | Notes |
|----|-------------|--------|-------|
| NFR-1 | Batch processing latency | < 30s for 50 URLs | Apify typical response time |
| NFR-2 | Success rate | ≥ 95% of available videos | Excluding deleted/private |
| NFR-3 | Cost efficiency | ≤ $0.002 per video | Apify Business tier pricing |

---

## Technical Specification

### Architecture Context

```
                              ┌─────────────────────┐
                              │   job_queue         │
                              │   (apify_enrich)    │
                              └──────────┬──────────┘
                                         │ claim job
                                         ▼
┌─────────────────┐          ┌─────────────────────┐          ┌─────────────────┐
│  media_events   │◀─────────│  ApifyEnrichStep    │─────────▶│  Apify API      │
│  (pending)      │  update  │  (Modal function)   │  HTTP    │  (Clockworks)   │
└─────────────────┘          └──────────┬──────────┘          └─────────────────┘
                                        │
                                        ▼
                              ┌─────────────────────┐
                              │  processing_steps   │
                              │  (audit trail)      │
                              └─────────────────────┘
```

### Data Model

No new tables. Updates to existing `media_events` rows:

```sql
-- Fields populated by APIFY_ENRICH step
UPDATE media_events SET
    -- Creator info
    creator_username = :creator_username,
    creator_name = :creator_name,
    creator_id = :creator_id,
    creator_followers = :creator_followers,
    creator_verified = :creator_verified,
    
    -- Content
    caption_text = :caption_text,
    hashtags = :hashtags,
    mentions = :mentions,
    
    -- Metrics
    play_count = :play_count,
    like_count = :like_count,
    comment_count = :comment_count,
    share_count = :share_count,
    collect_count = :collect_count,
    
    -- Video metadata
    video_duration_seconds = :video_duration_seconds,
    video_created_at = :video_created_at,
    is_ad = :is_ad,
    is_pinned = :is_pinned,
    is_slideshow = :is_slideshow,
    location_created = :location_created,
    
    -- Music
    music_id = :music_id,
    music_name = :music_name,
    music_author = :music_author,
    music_is_original = :music_is_original,
    
    -- Effects
    effect_stickers = :effect_stickers,
    thumbnail_url = :thumbnail_url,
    
    -- State transition
    processing_state = 'enriched',
    processing_substate = NULL,
    updated_at = NOW()
WHERE id = :media_event_id;
```

Insert audit record:

```sql
INSERT INTO processing_steps (
    media_event_id, step_type, provider, status, 
    started_at, finished_at, output_summary, cost_usd
) VALUES (
    :media_event_id, 'APIFY_ENRICH', 'apify_clockworks',
    'succeeded', :started_at, :finished_at, 
    :output_summary, :cost_usd
);
```

### API Contract

This is an internal pipeline step, not a user-facing API. However, we define the internal interface:

#### Internal: `ApifyEnrichStep.execute(batch: list[str]) -> BatchResult`

**Input**:
```python
batch: list[str]  # List of TikTok URLs (max 50)
# Example: ["https://tiktok.com/@user/video/123", ...]
```

**Output**:
```python
@dataclass
class VideoMetadata:
    platform_id: str
    url: str
    status: Literal["success", "unavailable", "error"]
    
    # Populated if status == "success"
    creator_username: str | None
    creator_name: str | None
    creator_id: str | None
    creator_followers: int | None
    creator_verified: bool | None
    
    caption_text: str | None
    hashtags: list[str]
    mentions: list[str]
    
    play_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None
    collect_count: int | None
    
    video_duration_seconds: int | None
    video_created_at: datetime | None
    is_ad: bool
    is_pinned: bool
    is_slideshow: bool
    location_created: str | None
    
    music_id: str | None
    music_name: str | None
    music_author: str | None
    music_is_original: bool | None
    
    effect_stickers: list[str]
    thumbnail_url: str | None
    
    # Error info if status != "success"
    error_code: str | None
    error_message: str | None

@dataclass
class BatchResult:
    results: list[VideoMetadata]
    total_cost_usd: Decimal
    request_duration_ms: int
```

**Error Handling**:
| Error | Handling |
|-------|----------|
| Apify rate limit (429) | Exponential backoff, re-queue batch |
| Apify timeout | Retry up to 3 times |
| Invalid URL format | Mark video as `error`, continue batch |
| Video unavailable | Mark as `unavailable`, not an error |
| Apify API error (5xx) | Retry with backoff, then fail batch |

### Component Design

#### Key Interfaces

```python
# src/backend/capabilities/interfaces.py

class VideoMetadataProvider(Protocol):
    """Fetches metadata for TikTok videos."""
    
    name: str  # Provider identifier, e.g., "apify_clockworks"
    max_batch_size: int  # Maximum URLs per request
    cost_per_video: Decimal  # For budget tracking
    
    async def fetch_metadata(
        self, 
        urls: list[str],
        timeout_seconds: int = 60
    ) -> BatchResult:
        """
        Fetch metadata for a batch of URLs.
        
        Args:
            urls: List of TikTok video URLs (max: max_batch_size)
            timeout_seconds: Request timeout
            
        Returns:
            BatchResult with metadata for each URL
            
        Raises:
            RateLimitError: If provider rate limit exceeded
            ProviderError: If provider returns non-retryable error
        """
        ...
```

```python
# src/backend/capabilities/apify_clockworks.py

class ApifyClockworksProvider:
    """Apify Clockworks Data Extractor implementation."""
    
    name = "apify_clockworks"
    max_batch_size = 50
    cost_per_video = Decimal("0.002")
    
    def __init__(self, api_token: str, base_url: str = "https://api.apify.com"):
        self.api_token = api_token
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=90)
    
    async def fetch_metadata(
        self, 
        urls: list[str],
        timeout_seconds: int = 60
    ) -> BatchResult:
        # Implementation details...
```

#### Implementation Notes

1. **Batching Strategy**: Process URLs in batches of 50 to optimize Apify costs. Each batch is a single Apify actor run.

2. **Field Mapping**: Apify returns data in a specific schema. We maintain a mapping layer to normalize to our `media_events` schema. This isolates us from Apify schema changes.

3. **Concurrency**: Within a pipeline run, process multiple batches concurrently (max 3) to improve throughput while respecting rate limits.

4. **Idempotency**: Track processed URLs by `platform_id`. If a URL was already enriched (same `platform_id` exists with `processing_state != 'pending'`), skip it.

5. **Cost Tracking**: Log cost per video in `processing_steps.cost_usd` and aggregate in `upload_pipeline_runs.total_cost_usd`.

### File Structure

```
src/backend/
├── capabilities/
│   ├── __init__.py
│   ├── interfaces.py           # Protocol definitions
│   └── apify_clockworks.py     # Apify implementation
├── pipeline/
│   ├── __init__.py
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── base.py             # BasePipelineStep abstract class
│   │   └── apify_enrich.py     # ApifyEnrichStep implementation
│   └── orchestrator.py         # Pipeline coordinator
└── models/
    └── pipeline.py             # Pydantic models for pipeline data
```

---

## Dependencies

### Upstream Dependencies

| Task | Description | Status | Blocking? |
|------|-------------|--------|-----------|
| 3.1 | Job queue infrastructure | Required | Yes |
| 3.2 | Pipeline orchestrator | Required | Yes |
| 3.3 | PARSE_EXPORT step | Provides URLs to enrich | Yes |
| 3.13 | Capability interfaces | Protocol definitions | Yes |

### Downstream Dependents

| Task | Description | Impact |
|------|-------------|--------|
| 3.5 | MEDIA_DOWNLOAD | Needs `thumbnail_url`, `is_slideshow` |
| 3.6 | SUBTITLE_FETCH | Needs Apify response for subtitle links |
| 3.11 | DERIVED_FIELDS | Needs engagement metrics |
| 5.1 | Library API | Needs creator, caption, metrics |

### External Dependencies

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| Apify Clockworks | Latest | TikTok metadata | Business tier required |
| httpx | ≥0.25.0 | Async HTTP client | For Apify API calls |
| tenacity | ≥8.0.0 | Retry logic | Exponential backoff |

---

## Test Strategy

### Unit Tests

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Happy path: valid URLs | 5 valid TikTok URLs | All 5 return status="success" with metadata |
| Partial success | 3 valid, 2 deleted videos | 3 success, 2 unavailable |
| Invalid URL format | Malformed URL | status="error", error_code="INVALID_URL" |
| Empty batch | Empty list | Empty BatchResult, no API call |
| Max batch size | 51 URLs | Raises ValueError (exceeds max_batch_size) |
| Field normalization | Apify response | All fields correctly mapped to our schema |
| Cost calculation | 50 URLs | total_cost_usd = 0.10 |

### Integration Tests

| Scenario | Components Involved | Verification |
|----------|---------------------|--------------|
| Full batch processing | ApifyEnrichStep + DB | media_events updated, processing_steps created |
| Rate limit handling | ApifyEnrichStep + job_queue | Job requeued with backoff |
| Pipeline integration | Orchestrator + ApifyEnrichStep | Step completes, triggers next step |

### Manual Testing Checklist

- [ ] Upload 10 videos, verify all enriched correctly
- [ ] Upload mix of valid/deleted videos, verify graceful handling
- [ ] Verify cost tracking in pipeline run dashboard
- [ ] Verify retry behavior by simulating network failure

---

## Acceptance Criteria

**Definition of Done**:

- [ ] `ApifyClockworksProvider` implements `VideoMetadataProvider` protocol
- [ ] `ApifyEnrichStep` processes batches from job queue
- [ ] All `media_events` fields from Apify are populated
- [ ] `processing_steps` records created for audit trail
- [ ] Cost tracking accurate to ±$0.001
- [ ] Retry logic handles transient failures
- [ ] Unavailable videos marked correctly (not failed)
- [ ] Unit test coverage ≥ 85%
- [ ] Integration test with real Apify API passes

**Verification Steps**:

1. Create test upload with 10 known TikTok URLs
2. Trigger pipeline, wait for APIFY_ENRICH to complete
3. Query `media_events` and verify:
   - `processing_state = 'enriched'`
   - `creator_username`, `caption_text`, `play_count` populated
   - `thumbnail_url` is valid image URL
4. Query `processing_steps` and verify:
   - `step_type = 'APIFY_ENRICH'`
   - `status = 'succeeded'`
   - `cost_usd ≈ 0.02` (10 videos × $0.002)
5. Test with known deleted video URL, verify `status = 'unavailable'`

---

## Security Considerations

- [ ] **Authentication**: Apify API token stored in secrets manager (not env var)
- [ ] **Authorization**: Pipeline runs scoped to user's own uploads
- [ ] **Data Validation**: Sanitize all Apify response fields before DB insert
- [ ] **Sensitive Data**: No PII sent to Apify (only public video URLs)
- [ ] **Rate Limiting**: Respect Apify quotas to avoid account suspension

---

## Observability

### Logging

| Event | Level | Fields | Purpose |
|-------|-------|--------|---------|
| `apify_batch_started` | INFO | batch_id, url_count, upload_id | Track batch processing |
| `apify_batch_completed` | INFO | batch_id, success_count, fail_count, duration_ms, cost_usd | Performance monitoring |
| `apify_video_unavailable` | WARN | platform_id, url | Track content churn |
| `apify_rate_limited` | WARN | retry_after_seconds | Capacity planning |
| `apify_batch_failed` | ERROR | batch_id, error_code, error_message | Incident response |

### Metrics

| Metric | Type | Labels | Alert Threshold |
|--------|------|--------|-----------------|
| `apify_requests_total` | counter | status, provider | - |
| `apify_videos_processed_total` | counter | status (success/unavailable/error) | - |
| `apify_batch_duration_seconds` | histogram | batch_size | p99 > 60s |
| `apify_cost_usd_total` | counter | - | Daily > $50 |
| `apify_error_rate` | gauge | - | > 10% |

---

## Rollout Plan

1. **Feature Flag**: `pipeline_apify_enrich_enabled` — Enable for internal testing first
2. **Migration**: None (uses existing tables)
3. **Rollback**: Disable feature flag, failed jobs will be retried when re-enabled

---

## Open Questions

| Question | Owner | Due Date | Resolution |
|----------|-------|----------|------------|
| Should we cache Apify responses for duplicate URLs across users? | Backend | 2026-01-25 | Defer to post-MVP |
| What's the retry strategy for permanently unavailable videos? | Backend | 2026-01-22 | Mark as unavailable after 1 attempt if Apify confirms deleted |

---

## References

- [PRD Section: Processing Pipeline](../docs/Attic_MVP_PRD_v1.0.1.md#f4-processing-pipeline)
- [Apify Clockworks Documentation](https://apify.com/clockworks/tiktok-scraper)
- [Task 3.1: Job Queue Infrastructure](./3-pipeline/3.1-job-queue.md)
- [Task 3.13: Capability Interfaces](./3-pipeline/3.13-capability-interfaces.md)

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-22 | Claude | Initial draft from PRD |