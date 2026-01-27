# Attic - Product Requirements Document

**Version:** 1.1.0
**Last Updated:** 2026-01-24
**Status:** MVP Development

---

## Executive Summary

Attic is a personal analytics platform that transforms social media consumption data into deep behavioral insights. Users upload their TikTok data export, and Attic enriches each video with metadata, visual analysis, and semantic tagging to intelligently filter / query their interaction history and gain insights about their consumption.

### Core Value Proposition

- **Self-reflection**: Understand your digital consumption patterns
- **Discovery**: Find saved content through intelligent search
- **Insight**: See yourself through your algorithmic footprint

### MVP Scope

- **Platform**: TikTok only (Instagram, YouTube in future)
- **Data Sources**: Liked and Favorited videos from user export
- **Features**: Upload, enrichment, browse library, keyword + semantic search
- **Pricing**: Free + paid tiers

---

## Technology Stack

This section summarizes the core technologies. For detailed rationale and alternatives, see [ADR: Tech Stack Changes](./ADR/Attic_MVP_Tech_Stack_Changes.md).

| Component | Technology | Notes |
|-----------|------------|-------|
| **Auth** | Supabase Auth | Google/Apple OAuth, JWT, session management |
| **Database** | Supabase PostgreSQL + pgvector | Managed Postgres with vector extensions |
| **ORM** | SQLAlchemy 2.0 + Alembic | Async support, migrations |
| **Backend** | FastAPI | Async Python API with FastAPI-Users, FastAPI-Pagination |
| **Frontend** | Next.js 14 + shadcn/ui | App Router, TanStack Query, React Hook Form |
| **File Upload** | Uppy + Supabase Storage | Direct uploads, progress tracking |
| **Job Queue** | Temporal.io | Multi-step workflow orchestration |
| **Processing** | Modal | Serverless Python for pipeline steps |
| **Real-time** | Supabase Realtime | WebSocket progress updates |
| **Email** | Resend | Transactional notifications |
| **SMS** | Twilio | Optional completion notifications |
| **Payments** | Stripe Billing | Subscription management |
| **Hosting** | Vercel (frontend) + Render (API) + Modal (jobs) | Managed infrastructure |
| **Error Tracking** | Sentry | Error monitoring and alerting |
| **Logging** | Axiom | Structured log aggregation |
| **Analytics** | PostHog | Product analytics and events |
| **CDN/Security** | Cloudflare | DDoS protection, CDN |
| **Rate Limiting** | Upstash | Edge-based rate limiting |
| **Observability** | Highlight.io | Session replay, APM |
| **Testing** | Pytest + Playwright | Backend tests + E2E tests |

---

## Table of Contents

1. [User Personas](#user-personas)
2. [User Journey](#user-journey)
3. [Feature Requirements](#feature-requirements)
4. [Data Model](#data-model)
5. [Processing Pipeline](#processing-pipeline)
6. [API Contracts](#api-contracts)
7. [Frontend Requirements](#frontend-requirements)
8. [Non-Functional Requirements](#non-functional-requirements)
9. [Operational Services](#operational-services)
10. [Pricing & Limits](#pricing--limits)
11. [Success Metrics](#success-metrics)

---

## User Personas

### Primary: The Curious Self-Reflector

**Profile**: 22-35 years old, heavy TikTok user (2+ hours/day), interested in personal development and self-awareness.

**Motivations**:
- "I want to understand what my TikTok habits say about me"
- "I save videos but can never find them again"
- "I'm curious if my interests have changed over time"

**Pain Points**:
- TikTok's native search is terrible for finding saved content
- No way to see patterns across thousands of liked videos
- Feels like consumption is mindless; wants it to be meaningful

### Secondary: The Content Professional

**Profile**: 25-40 years old, works in marketing/content/research, uses TikTok for professional trend-spotting.

**Motivations**:
- "I need to understand what content resonates with me and why"
- "I want to analyze my saved videos for content patterns"
- "I'm researching trends and need organized data"

---

## User Journey

### Happy Path Flow

```
1. Landing Page
   └── Learn what Attic does, see example insights

2. Sign Up (Google/Apple OAuth via Supabase Auth)
   └── Create account, accept terms

3. Data Export Guide
   └── Step-by-step instructions to download TikTok export

4. Upload ZIP
   └── Drag-and-drop upload via Uppy, file validation

5. Scope Selection
   └── Choose: Liked only, Favorited only, or Both
   └── See estimated video count and processing time
   └── Confirm (free tier has limits)

6. Processing (async via Temporal.io)
   └── Real-time progress via Supabase Realtime
   └── Can leave; get SMS/email when done

7. Library (unlocks when enrichment phase completes)
   └── Browse all videos (basic metadata only until full processing done)
   └── Search and click disabled until complete

8. Full Experience (after processing complete)
   └── Search (keyword + semantic)
   └── Filter by creator, mood, category, date
   └── Click video for detail view with all enrichment data
```

### Data Export Instructions (for user guide)

TikTok Data Export steps:
1. Open TikTok app → Profile → Menu (≡) → Settings and privacy
2. Account → Download your data
3. Select "JSON" format (not TXT)
4. Request data, wait for email (usually 1-3 days)
5. Download ZIP from TikTok and upload to Attic

---

## Feature Requirements

### F1: Authentication

**User Story**: As a user, I can sign in with Google or Apple so I don't need to remember another password.

**Requirements**:
- Google OAuth via Supabase Auth
- Apple Sign-In via Supabase Auth
- Session management handled by Supabase (JWT with refresh tokens)
- Account deletion (within 24 hours)

**Acceptance Criteria**:
- [ ] User can sign in with Google via Supabase Auth
- [ ] User can sign in with Apple via Supabase Auth
- [ ] Session persists across browser refresh (Supabase handles token refresh)
- [ ] User can sign out
- [ ] User can delete account and all data

---

### F2: Upload & Parsing

**User Story**: As a user, I can upload my TikTok data export ZIP and have Attic extract my liked/favorited videos.

**Requirements**:
- Accept ZIP file upload (max 500MB) via Uppy component
- Upload to Supabase Storage with presigned URLs
- Parse TikTok export JSON format
- Extract ONLY: Liked Videos, Favorited Videos (whitelist approach)
- Validate file structure before processing
- Show item counts and request scope selection

**Acceptance Criteria**:
- [ ] User can drag-and-drop or click to upload ZIP via Uppy
- [ ] File uploads directly to Supabase Storage
- [ ] Invalid files show clear error message
- [ ] Correct item counts displayed before processing
- [ ] User can select scope (liked/favorited/both)
- [ ] Raw ZIP is deleted immediately after parsing

**Security Notes**:
- Never persist raw ZIP file
- Ignore all other data in export (DMs, search history, etc.)
- Log file hash for debugging, not content

---

### F3: Explicit Consent

**User Story**: As a user, I understand exactly what data Attic accesses and how it's used before processing begins.

**Requirements**:
- Show explicit consent screen before processing
- List exactly what data is extracted
- Explain what third parties receive (Apify gets URLs, OpenAI gets images)
- Require explicit acceptance

**Consent Screen Content**:
```
Attic will analyze your TikTok data. Here's what we access:

✅ What we extract:
- Liked video URLs and timestamps
- Favorited video URLs and timestamps

❌ What we ignore (never accessed):
- Direct messages
- Search history
- Comments you posted
- Your profile information
- Watch history

🔒 How we process:
- Video URLs are sent to our enrichment service (Apify) to fetch public metadata
- Video thumbnails are sent to OpenAI for visual analysis
- No personal identifiers are sent to third parties

📅 Data retention:
- Your data is stored until you delete it or 30 days after your subscription ends

[Cancel] [I Understand, Continue]
```

---

### F4: Processing Pipeline

**User Story**: As a user, my videos are enriched with metadata and analysis in the background while I can track progress.

**Requirements**:
- Asynchronous processing orchestrated by Temporal.io workflows
- Real-time progress updates via Supabase Realtime
- Email notification (via Resend) / SMS notification (via Twilio) on completion
- Graceful handling of failures (partial data is still valuable)

**Processing Steps** (in order):
1. `PARSE_EXPORT` - Extract URLs from uploaded data
2. `APIFY_ENRICH` - Fetch metadata from TikTok via Apify
3. `MEDIA_DOWNLOAD` - Download video/images via Apify
4. `SUBTITLE_FETCH` - Get subtitles if available
5. `WHISPER_TRANSCRIBE` - Transcribe if subtitles unavailable
6. `VISION_ANALYSIS` - GPT-5.1 visual tagging
7. `TEXT_FUSION` - Combine all text fields
8. `EMBEDDING` - Generate search embeddings
9. `DERIVED_FIELDS` - Compute engagement rate, etc.
10. `SEARCH_INDEX` - Update search index

**Acceptance Criteria**:
- [ ] Temporal.io workflow manages pipeline state and retries
- [ ] Progress updates visible in real-time via Supabase Realtime
- [ ] User can leave page; processing continues
- [ ] User receives notification (email via Resend, SMS via Twilio) when done
- [ ] Partial failures don't block entire upload

---

### F5: Library View

**User Story**: As a user, I can browse all my analyzed videos in a visual gallery or list view.

**Requirements**:
- Gallery view (default): thumbnails in grid
- List view: compact rows with more metadata
- Toggle between views; preference saved
- Pagination or infinite scroll
- Sort by: date liked, engagement, creator

**Visible Fields (Gallery)**:
- Thumbnail
- Creator username
- Primary mood (with confidence indicator)

**Visible Fields (List)**:
- Thumbnail (small)
- Creator username + name
- Caption (truncated)
- Primary mood + content category
- Like/play counts
- Date liked

**Acceptance Criteria**:
- [ ] Gallery view displays 20+ items per page
- [ ] List view displays 50+ items per page
- [ ] View toggle persists across sessions
- [ ] Sort options work correctly
- [ ] Infinite scroll or pagination works smoothly

---

### F6: Search

**User Story**: As a user, I can find specific videos using keywords or natural language queries.

**Requirements**:
- Keyword search across: caption, hashtags, transcript, OCR text, visual tags
- Semantic search using embeddings
- Hybrid results (keyword matches + semantic matches)
- Filter by: creator, mood, content category, date range

**Search UX**:
- Search bar at top of library
- Filters in sidebar (collapsible on mobile)
- Results update as user types (debounced)
- Clear indication of which filters are active

**Acceptance Criteria**:
- [ ] Keyword search returns relevant results
- [ ] Semantic search finds conceptually similar videos
- [ ] Filters can be combined (AND logic)
- [ ] Empty state shows helpful message
- [ ] Search is fast (<500ms for typical queries)

---

### F7: Detail View

**User Story**: As a user, I can see all enrichment data for a specific video.

**Requirements**:
- Full metadata display
- Visual tags with confidence indicators
- All text content (caption, transcript, OCR)
- Link to original TikTok
- Creator information

**Confidence Indicators**:
- Dark green: confidence > 0.7
- Light green: confidence 0.5-0.7
- Yellow: confidence < 0.5

**Acceptance Criteria**:
- [ ] All enrichment fields displayed
- [ ] Confidence indicators visible for applicable fields
- [ ] Link to original TikTok works
- [ ] Mobile-friendly layout

---

### F8: Progress & Notifications

**User Story**: As a user, I can see processing progress and get notified when complete.

**Requirements**:
- Real-time progress via Supabase Realtime subscriptions
- Step-by-step breakdown (not just percentage)
- Estimated time remaining
- Email notification on completion (via Resend)
- Optional SMS notification (via Twilio)

**Progress Display**:
```
Processing your TikTok data...

✓ Parsing export (complete)
✓ Fetching metadata (1,247 of 1,247)
⟳ Downloading media (892 of 1,247)
○ Analyzing visuals
○ Generating embeddings
○ Building search index

Estimated time remaining: ~8 minutes

[Notify me by email when done]
[Also text me: (___) ___-____]
```

**Acceptance Criteria**:
- [ ] Progress updates in real-time via Supabase Realtime
- [ ] Estimated time is reasonably accurate
- [ ] Email notification sent via Resend on completion
- [ ] SMS notification via Twilio works if opted in
- [ ] Progress page works if user leaves and returns

---

## Data Model

### Core Tables

#### `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    auth_provider VARCHAR(50) NOT NULL,  -- 'google', 'apple'
    auth_provider_id VARCHAR(255) NOT NULL,
    subscription_tier VARCHAR(50) DEFAULT 'free',  -- 'free', 'explorer', 'expert', 'pioneer'
    subscription_ends_at TIMESTAMPTZ,
    stripe_customer_id VARCHAR(255),  -- Stripe customer reference
    phone VARCHAR(20),  -- for SMS notifications
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,  -- soft delete
    UNIQUE(auth_provider, auth_provider_id)
);
```

#### `uploads`
```sql
CREATE TABLE uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_platform VARCHAR(50) DEFAULT 'tiktok',
    scope VARCHAR(50) NOT NULL,  -- 'liked', 'favorited', 'both'
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'complete', 'failed'
    total_items INT,
    processed_items INT DEFAULT 0,
    file_hash VARCHAR(64),  -- for debugging, not content
    temporal_workflow_id VARCHAR(255),  -- Temporal.io workflow reference
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

#### `upload_pipeline_runs`
```sql
CREATE TABLE upload_pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID REFERENCES uploads(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processing', 'complete', 'failed'
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    total_videos INT,
    videos_enriched INT DEFAULT 0,
    videos_media_downloaded INT DEFAULT 0,
    videos_transcribed INT DEFAULT 0,
    videos_vision_done INT DEFAULT 0,
    videos_embedded INT DEFAULT 0,
    videos_complete INT DEFAULT 0,
    videos_failed INT DEFAULT 0,
    total_cost_usd DECIMAL(10,4) DEFAULT 0,
    estimated_completion_at TIMESTAMPTZ,
    error_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `media_events`
```sql
CREATE TABLE media_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    upload_id UUID REFERENCES uploads(id) ON DELETE CASCADE,

    -- Source identifiers
    platform VARCHAR(50) DEFAULT 'tiktok',
    platform_id VARCHAR(255) NOT NULL,  -- TikTok's video ID
    canonical_url TEXT,
    interaction_type VARCHAR(50),  -- 'liked', 'favorited'
    interaction_at TIMESTAMPTZ,

    -- Processing state
    processing_state VARCHAR(50) DEFAULT 'pending',
    processing_substate VARCHAR(100),

    -- From Apify enrichment
    caption_text TEXT,
    hashtags TEXT[],
    mentions TEXT[],
    creator_username VARCHAR(255),
    creator_name VARCHAR(255),
    creator_id VARCHAR(255),
    creator_followers INT,
    creator_verified BOOLEAN,
    play_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    share_count BIGINT,
    collect_count BIGINT,
    video_duration_seconds INT,
    video_created_at TIMESTAMPTZ,
    is_ad BOOLEAN,
    is_pinned BOOLEAN,
    is_slideshow BOOLEAN,
    location_created VARCHAR(100),
    music_id VARCHAR(255),
    music_name VARCHAR(255),
    music_author VARCHAR(255),
    music_is_original BOOLEAN,
    effect_stickers TEXT[],
    thumbnail_url TEXT,

    -- From transcription
    subtitle_text TEXT,
    subtitle_source VARCHAR(50),  -- 'apify', 'whisper', null

    -- From GPT-5.1 Vision (distributions stored as JSONB)
    visual_tags TEXT[],
    ocr_text TEXT,

    -- Distribution fields (JSONB for full distribution)
    mood_distribution JSONB,  -- {"funny": 0.7, "inspirational": 0.2}
    mood_primary VARCHAR(50),
    mood_primary_confidence FLOAT,

    content_category_distribution JSONB,
    content_category_primary VARCHAR(50),
    content_category_primary_confidence FLOAT,

    creator_archetype_distribution JSONB,
    creator_archetype_primary VARCHAR(50),
    creator_archetype_primary_confidence FLOAT,

    audience_role_distribution JSONB,
    audience_role_primary VARCHAR(50),
    audience_role_primary_confidence FLOAT,

    -- Single-value fields with confidence
    is_satire BOOLEAN,
    satire_confidence FLOAT,

    setting VARCHAR(100),
    setting_confidence FLOAT,

    aesthetic_style VARCHAR(100),
    aesthetic_style_confidence FLOAT,

    content_format VARCHAR(100),
    content_format_confidence FLOAT,

    meme_format VARCHAR(100),
    meme_format_confidence FLOAT,

    apparent_intent TEXT,

    -- Typed entities (JSONB array)
    entities JSONB,  -- [{"surface": "Atomic Habits", "type": "book", "canonical": "..."}]

    -- Derived fields
    engagement_rate FLOAT,
    interaction_hour INT,  -- 0-23
    interaction_day_of_week INT,  -- 0-6
    creator_is_repeat BOOLEAN,
    hashtag_count INT,
    caption_length INT,
    inferred_user_role VARCHAR(50),  -- 'wind_down', 'learning', etc.

    -- For search
    full_text TEXT,  -- Fused searchable text
    embedding_vector vector(1536),  -- pgvector

    -- Future clustering (nullable for MVP)
    cluster_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, platform, platform_id)
);

-- Indexes
CREATE INDEX idx_media_events_user ON media_events(user_id);
CREATE INDEX idx_media_events_upload ON media_events(upload_id);
CREATE INDEX idx_media_events_platform_id ON media_events(platform_id);
CREATE INDEX idx_media_events_processing ON media_events(processing_state) WHERE processing_state != 'complete';
CREATE INDEX idx_media_events_creator ON media_events(creator_username);
CREATE INDEX idx_media_events_mood ON media_events(mood_primary);
CREATE INDEX idx_media_events_interaction ON media_events(interaction_at);

-- Full-text search index
CREATE INDEX idx_media_events_fulltext ON media_events USING GIN (to_tsvector('english', full_text));

-- Vector similarity index
CREATE INDEX idx_media_events_embedding ON media_events USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);
```

#### `processing_steps`
```sql
CREATE TABLE processing_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_event_id UUID REFERENCES media_events(id) ON DELETE CASCADE,
    step_type VARCHAR(50) NOT NULL,  -- 'APIFY_ENRICH', 'MEDIA_DOWNLOAD', etc.
    provider VARCHAR(100),  -- 'apify_clockworks', 'openai_gpt5.1', etc.
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'running', 'succeeded', 'failed', 'skipped'
    attempt INT DEFAULT 1,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    input_summary JSONB,
    output_summary JSONB,
    error_message TEXT,
    cost_usd DECIMAL(10,6),
    prompt_version VARCHAR(50),  -- For LLM steps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(media_event_id, step_type, attempt)
);

CREATE INDEX idx_processing_steps_media ON processing_steps(media_event_id);
CREATE INDEX idx_processing_steps_pending ON processing_steps(status) WHERE status IN ('pending', 'running');
CREATE INDEX idx_processing_steps_step ON processing_steps(step_type, status);
```

#### `prompt_templates`
```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,  -- 'video_analysis', 'cluster_labeling'
    version VARCHAR(20) NOT NULL,  -- 'v1', 'v2', etc.
    model VARCHAR(100) NOT NULL,  -- 'gpt-5.1', 'gpt-4o-mini'
    temperature FLOAT DEFAULT 0.0,
    max_tokens INT,
    system_prompt TEXT,
    user_prompt_template TEXT,  -- With {placeholders}
    response_schema JSONB,  -- Expected JSON structure
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,

    UNIQUE(name, version)
);
```

#### `cost_models`
```sql
CREATE TABLE cost_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(100) NOT NULL,  -- 'openai', 'apify', 'modal'
    sku VARCHAR(100) NOT NULL,  -- 'gpt-5.1:input_tokens', 'clockworks:video'
    metric VARCHAR(50) NOT NULL,  -- 'tokens', 'videos', 'gpu_seconds'
    unit_price_usd DECIMAL(12,8) NOT NULL,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    notes TEXT,

    UNIQUE(provider, sku, effective_from)
);

-- Seed with initial pricing
INSERT INTO cost_models (provider, sku, metric, unit_price_usd, notes) VALUES
('apify', 'clockworks_data_extractor:video', 'videos', 0.002, 'Business tier'),
('openai', 'gpt-5.1:input_tokens', 'tokens', 0.00000125, '$1.25/1M'),
('openai', 'gpt-5.1:output_tokens', 'tokens', 0.00001, '$10/1M'),
('openai', 'text-embedding-3-small:tokens', 'tokens', 0.00000002, '$0.02/1M'),
('openai', 'whisper:audio_seconds', 'seconds', 0.0001, '$0.006/min'),
('modal', 'cpu:seconds', 'seconds', 0.000014, 'Standard CPU'),
('modal', 'memory_gb:seconds', 'seconds', 0.000004, 'Per GB-second');
```

---

## Processing Pipeline

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Upload                              │
│                    (Uppy → Supabase Storage)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  TEMPORAL WORKFLOW STARTS                                        │
│  - Creates upload_pipeline_run                                   │
│  - Manages state, retries, timeouts                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  PARSE_EXPORT (Activity)                                         │
│  - Extract URLs from ZIP                                         │
│  - Create media_event rows (status: pending)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  APIFY_ENRICH (batched, 50 URLs per call)                        │
│  Provider: apify_clockworks                                      │
│  - Fetch metadata, captions, hashtags, creator info              │
│  - Batch process for efficiency                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  MEDIA_DOWNLOAD (per video)                                      │
│  Provider: apify_clockworks (media download option)              │
│  - Download video file or slideshow images                       │
│  - Store temporarily for vision analysis                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  SUBTITLE_FETCH (per video)                                      │
│  - Check if Apify returned subtitle links                        │
│  - Download subtitle file if available                           │
│  - Mark subtitle_source = 'apify'                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  WHISPER_TRANSCRIBE (only if no subtitles)                       │
│  Provider: openai_whisper or local_whisper                       │
│  - Transcribe audio from downloaded video                        │
│  - Mark subtitle_source = 'whisper'                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  VISION_ANALYSIS (batched, 5 images per call)                    │
│  Provider: openai_gpt5.1_vision                                  │
│  - Extract keyframes from video                                  │
│  - Analyze with GPT-5.1 Vision                                   │
│  - Output: visual_tags, mood, content_category, etc.             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  TEXT_FUSION (per video, local)                                  │
│  - Combine: caption + hashtags + transcript + OCR + visual_tags  │
│  - Create full_text for search                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  EMBEDDING (batched, 100 texts per call)                         │
│  Provider: openai_text_embedding_3_small                         │
│  - Generate 1536-dim vector from full_text                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  DERIVED_FIELDS (per video, local)                               │
│  - engagement_rate = (likes + comments + shares) / plays         │
│  - interaction_hour, interaction_day_of_week                     │
│  - creator_is_repeat (lookup previous events)                    │
│  - inferred_user_role (heuristic)                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  SEARCH_INDEX (batched, 100 rows)                                │
│  - Update full-text search index                                 │
│  - Update vector index                                           │
│  - Mark processing_state = 'complete'                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW COMPLETE                                               │
│  - Update upload_pipeline_run status                             │
│  - Send notification via Resend (email) / Twilio (SMS)           │
└─────────────────────────────────────────────────────────────────┘
```

### Capability Abstraction

Each processing step uses a capability interface, not a specific vendor:

```python
# Interfaces (in src/backend/capabilities/interfaces.py)

class VideoMetadataProvider(Protocol):
    """Fetches metadata for TikTok videos."""
    name: str

    def fetch_metadata(self, urls: list[str]) -> list[VideoMetadataResult]:
        """Fetch metadata for a batch of URLs."""
        ...

class MediaDownloader(Protocol):
    """Downloads video/image files."""
    name: str

    def download(self, url: str, video_id: str) -> DownloadResult:
        """Download media and return local path."""
        ...

class TranscriptionProvider(Protocol):
    """Transcribes audio to text."""
    name: str

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe audio file."""
        ...

class VisionAnalyzer(Protocol):
    """Analyzes images/frames for content."""
    name: str

    def analyze(self, images: list[bytes], context: VideoContext) -> VisionAnalysisResult:
        """Analyze images with optional text context."""
        ...

class EmbeddingProvider(Protocol):
    """Generates text embeddings."""
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        ...
```

### Workflow Architecture (Temporal.io)

```python
# Example Temporal.io workflow definition

from temporalio import activity, workflow
from datetime import timedelta

@activity.defn
async def parse_export(upload_id: str) -> list[str]:
    """Extract URLs from uploaded ZIP."""
    ...

@activity.defn
async def enrich_with_apify(video_urls: list[str]) -> dict:
    """Fetch metadata via Apify."""
    ...

@workflow.defn
class VideoProcessingWorkflow:
    @workflow.run
    async def run(self, upload_id: str) -> dict:
        # Parse export
        urls = await workflow.execute_activity(
            parse_export,
            upload_id,
            start_to_close_timeout=timedelta(minutes=5)
        )

        # Enrich with Apify (with retries)
        metadata = await workflow.execute_activity(
            enrich_with_apify,
            urls,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Continue through remaining steps...

        return {"status": "complete", "videos_processed": len(urls)}
```

**Why Temporal.io:**
- Automatic state persistence across workflow steps
- Built-in retry policies with exponential backoff
- Visual workflow UI for debugging failed uploads
- Handles long-running workflows (user uploads, leaves, comes back)
- Activity-level timeout and cancellation support

---

## API Contracts

### Authentication

#### `POST /api/auth/google`
Exchange Google OAuth code for session (via Supabase Auth).

**Request:**
```json
{
  "code": "google_oauth_code",
  "redirect_uri": "https://attic.app/auth/callback"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "User Name"
  },
  "access_token": "jwt_token",
  "refresh_token": "refresh_token"
}
```

---

### Uploads

#### `POST /api/uploads`
Create a new upload and begin processing.

**Request:** `multipart/form-data`
- `file`: ZIP file
- `scope`: `"liked"` | `"favorited"` | `"both"`

**Response:**
```json
{
  "upload_id": "uuid",
  "status": "processing",
  "total_items": 1247,
  "estimated_minutes": 12,
  "temporal_workflow_id": "workflow-uuid"
}
```

#### `GET /api/uploads/{upload_id}/status`
Get processing status for an upload.

**Response:**
```json
{
  "upload_id": "uuid",
  "status": "processing",
  "progress": {
    "total_videos": 1247,
    "videos_enriched": 1247,
    "videos_media_downloaded": 892,
    "videos_transcribed": 850,
    "videos_vision_done": 720,
    "videos_embedded": 650,
    "videos_complete": 650,
    "videos_failed": 12
  },
  "estimated_seconds_remaining": 480,
  "current_step": "vision_analysis",
  "started_at": "2026-01-18T10:00:00Z",
  "updated_at": "2026-01-18T10:08:30Z"
}
```

---

### Media Events (Library)

#### `GET /api/media-events`
List media events with filtering and search.

**Query Parameters:**
- `q`: Search query (keyword search)
- `semantic_q`: Semantic search query (uses embeddings)
- `creator`: Filter by creator username
- `mood`: Filter by mood_primary
- `category`: Filter by content_category_primary
- `date_from`, `date_to`: Filter by interaction_at
- `sort`: `"date"` | `"engagement"` | `"relevance"` (default for search)
- `page`, `per_page`: Pagination

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "platform_id": "7123456789",
      "canonical_url": "https://tiktok.com/@user/video/7123456789",
      "thumbnail_url": "https://...",
      "creator_username": "creator",
      "creator_name": "Creator Name",
      "caption_text": "Caption here #hashtag",
      "mood_primary": "funny",
      "mood_primary_confidence": 0.82,
      "content_category_primary": "entertainment",
      "interaction_at": "2026-01-15T20:30:00Z",
      "processing_state": "complete"
    }
  ],
  "total": 1247,
  "page": 1,
  "per_page": 20,
  "has_more": true
}
```

#### `GET /api/media-events/{id}`
Get full details for a single media event.

**Response:**
```json
{
  "id": "uuid",
  "platform_id": "7123456789",
  "canonical_url": "https://tiktok.com/@user/video/7123456789",
  "thumbnail_url": "https://...",

  "creator": {
    "username": "creator",
    "name": "Creator Name",
    "followers": 125000,
    "verified": false
  },

  "content": {
    "caption_text": "Full caption here #hashtag #another",
    "hashtags": ["hashtag", "another"],
    "subtitle_text": "Transcribed speech...",
    "ocr_text": "On-screen text...",
    "visual_tags": ["person", "kitchen", "cooking"]
  },

  "analysis": {
    "mood": {
      "distribution": {"funny": 0.7, "inspirational": 0.2, "neutral": 0.1},
      "primary": "funny",
      "confidence": 0.7
    },
    "content_category": {
      "distribution": {"tutorial": 0.8, "entertainment": 0.2},
      "primary": "tutorial",
      "confidence": 0.8
    },
    "creator_archetype": {
      "primary": "educator",
      "confidence": 0.75
    },
    "audience_role": {
      "primary": "learner",
      "confidence": 0.8
    },
    "is_satire": false,
    "satire_confidence": 0.1,
    "setting": "kitchen",
    "aesthetic_style": "lo-fi",
    "content_format": "tutorial",
    "meme_format": null,
    "apparent_intent": "teach cooking technique",
    "inferred_user_role": "learning"
  },

  "entities": [
    {"surface": "garlic press", "type": "product", "canonical": null},
    {"surface": "pasta", "type": "food", "canonical": "Pasta"}
  ],

  "metrics": {
    "play_count": 125000,
    "like_count": 8500,
    "comment_count": 234,
    "share_count": 567,
    "engagement_rate": 0.074
  },

  "music": {
    "id": "music123",
    "name": "Original Sound",
    "author": "creator",
    "is_original": true
  },

  "timestamps": {
    "video_created_at": "2026-01-10T15:00:00Z",
    "interaction_at": "2026-01-15T20:30:00Z",
    "interaction_hour": 20,
    "interaction_day_of_week": 3
  },

  "processing_state": "complete"
}
```

---

### User

#### `GET /api/user/me`
Get current user profile.

#### `DELETE /api/user/me`
Request account deletion (processed within 24 hours).

#### `PATCH /api/user/me/notifications`
Update notification preferences.

**Request:**
```json
{
  "email_notifications": true,
  "sms_notifications": true,
  "phone": "+1234567890"
}
```

---

## Frontend Requirements

### Technology Stack

- **Framework**: Next.js 14 with App Router
- **UI Components**: shadcn/ui (Radix UI + Tailwind CSS)
- **Data Fetching**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation
- **File Upload**: Uppy with Supabase Storage integration
- **Auth**: Supabase Auth helpers for Next.js
- **State**: Server components by default, minimal client state

### Visual Design

**Style**: Warm Minimal with selective Data-forward elements in library view

**Key Principles**:
- Soft, warm color palette (cream backgrounds, muted accents)
- Plenty of whitespace
- Rounded corners, gentle shadows
- Typography: clean sans-serif (Inter or similar)
- Library view uses more structured cards/grids for usability

**Brand Voice**:
- Thoughtful, not clinical
- Personal, not corporate
- Curious, not judgmental

### Pages

1. **Landing Page** (`/`)
   - Hero with value proposition
   - Example insights visualization
   - How it works (3 steps)
   - Pricing preview
   - CTA to sign up

2. **Auth Pages** (`/auth/login`, `/auth/callback`)
   - Google/Apple sign-in buttons (via Supabase Auth)
   - Clean, minimal design

3. **Upload Page** (`/upload`)
   - Data export guide (collapsible)
   - Uppy drag-and-drop upload component
   - Scope selection
   - Consent screen (modal)
   - Processing redirect

4. **Processing Page** (`/processing/{upload_id}`)
   - Real-time progress via Supabase Realtime
   - Step-by-step breakdown
   - Estimated time
   - Notification opt-in (email via Resend, SMS via Twilio)
   - "We'll email you" message if leaving

5. **Library Page** (`/library`)
   - Search bar (top)
   - Filter sidebar (collapsible)
   - View toggle (gallery/list)
   - Media event grid/list via TanStack Query
   - Infinite scroll

6. **Detail Page** (`/library/{id}`)
   - Full enrichment display
   - Link to original TikTok
   - Back to library

7. **Settings Page** (`/settings`)
   - Profile info
   - Notification preferences
   - Subscription status (Stripe Billing Portal link)
   - Delete account

### Responsive Breakpoints

- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

Library view should work well on mobile (single column gallery).

---

## Non-Functional Requirements

### Performance

- **Page load**: < 2 seconds (LCP)
- **Search response**: < 500ms
- **API response**: < 200ms (p95)
- **Processing throughput**: 1000 videos in 10-15 minutes

### Security

- **Authentication**: OAuth 2.0 via Supabase Auth
- **Data encryption**: TLS in transit, AES-256 at rest (Supabase default)
- **Session management**: Supabase JWT with automatic refresh
- **Rate limiting**: Cloudflare + Upstash (100 requests/minute per user)
- **Data isolation**: Row-level security (RLS) policies in Supabase
- **DDoS Protection**: Cloudflare Free tier

### Privacy

- **Data minimization**: Only extract liked/favorited lists
- **Third-party disclosure**: Transparent about what goes to Apify/OpenAI
- **Retention**: Data deleted 30 days after subscription ends
- **Right to delete**: Within 24 hours of request
- **No training**: User data never used for AI training

### Reliability

- **Uptime target**: 99.5%
- **Graceful degradation**: Partial processing failures don't block entire upload
- **Idempotent operations**: Safe to retry any step (Temporal.io guarantees)

### Scalability

- **MVP scale**: 1000 users, 1M total media events
- **Per-user limit**: 10,000 media events
- **Concurrent processing**: 10 uploads simultaneously

### Observability

- **Error tracking**: Sentry for exceptions and alerting
- **Logging**: Axiom for structured log aggregation
- **Session replay**: Highlight.io for debugging user issues
- **APM**: Highlight.io for performance monitoring

---

## Operational Services

### Monitoring & Alerting

| Service | Purpose | Notes |
|---------|---------|-------|
| **Sentry** | Error tracking | Captures exceptions, stack traces, user context |
| **Axiom** | Log aggregation | Structured logging with cost tracking queries |
| **Highlight.io** | Session replay + APM | Debugging user-reported issues |

### Analytics

| Service | Purpose | Notes |
|---------|---------|-------|
| **PostHog** | Product analytics | Event tracking, funnels, cohorts, retention |

### Payments

| Service | Purpose | Notes |
|---------|---------|-------|
| **Stripe Billing** | Subscription management | Customer portal, trials, prorations, dunning |

### Infrastructure

| Component | Service | Cost (MVP) |
|-----------|---------|-----------|
| **Frontend** | Vercel | Free |
| **Backend API** | Render | $7/mo |
| **Database** | Supabase | Free → $25/mo |
| **Jobs** | Modal | Pay per use (~$20/mo) |
| **CDN/Security** | Cloudflare | Free |

**Estimated Total MVP Cost: ~$50-75/month** (primarily Modal usage for processing)

---

## Pricing & Limits

### Tier Structure

| Tier | Price | Video Limit | Features |
|------|-------|-------------|----------|
| **Free** | $0 | 200 videos, one-time | Basic enrichment, limited search |
| **Explorer** | $12/mo | 1,500 videos | Full enrichment, full search |
| **Expert** | $24/mo | 3,000 videos | Everything in Explorer |
| **Pioneer** | $49/mo | 7,500 videos | Everything in Expert, priority processing |

### Cost Controls

- Hard cap on videos processed per tier
- Budget alerts when approaching 80% of cost threshold
- Automatic degradation (skip expensive steps) if over budget

---

## Success Metrics

### MVP Launch (First 30 Days)

- **Signups**: 500 users
- **Uploads completed**: 200
- **Conversion (free → paid)**: 10%
- **Processing success rate**: > 95%
- **Average processing time (1000 videos)**: < 15 minutes

### Growth Indicators

- **Weekly active users**: Users who search or browse library
- **Retention (30-day)**: Users who return after initial upload
- **NPS**: > 40

---

## Appendix

### A. TikTok Export Structure

Expected JSON structure in export ZIP:

```
Activity/
├── Like List.json        # {"LikeList": [{"Date": "...", "Link": "..."}]}
├── Favorite Videos.json  # {"FavoriteList": [{"Date": "...", "Link": "..."}]}
└── ... (other files ignored)
```

### B. Ontology Label Values

**Mood** (`mood_primary`):
- `upbeat_positive`
- `heartfelt`
- `calm_soothing`
- `sad_melancholic`
- `angry_outraged`
- `anxious_stressed`
- `eerie_unsettling`
- `funny`
- `inspirational`
- `neutral`

**Content Category** (`content_category_primary`):
- `tutorial`
- `entertainment`
- `news_commentary`
- `personal_story`
- `product_review`
- `art_creative`
- `fitness_health`
- `food_cooking`
- `travel`
- `technology`
- `relationship_advice`
- `other`

**Creator Archetype** (`creator_archetype_primary`):
- `educator`
- `comedian`
- `lifestyle_vlogger`
- `activist_commentator`
- `artist_designer`
- `brand_marketer`
- `news_journalist`
- `expert_practitioner`
- `other`

**Audience Role** (`audience_role_primary`):
- `passive_spectator`
- `learner`
- `participant`
- `supporter_fan`
- `evaluator`
- `shopper`
- `other`

**Content Format** (`content_format`):
- `talking_head`
- `tutorial_demo`
- `vlog`
- `duet`
- `stitch`
- `green_screen`
- `slideshow`
- `animation`
- `screen_recording`
- `montage`
- `other`

**Inferred User Role** (`inferred_user_role`):
- `wind_down` (late night + calm content)
- `learning` (tutorials + favorited)
- `entertainment` (comedy + high engagement)
- `inspiration` (motivational content)
- `discovery` (diverse categories)
- `unknown`

### C. Error Codes

| Code | Description |
|------|-------------|
| `INVALID_FILE` | Uploaded file is not a valid ZIP |
| `INVALID_EXPORT` | ZIP doesn't contain expected TikTok export structure |
| `EMPTY_EXPORT` | No liked/favorited videos found |
| `PROCESSING_FAILED` | Processing failed for entire upload |
| `RATE_LIMITED` | Too many requests |
| `QUOTA_EXCEEDED` | Video limit exceeded for tier |

---

## Changelog

### v1.1.0 (2026-01-24)
- **Tech Stack Modernization**: Replaced custom implementations with battle-tested tools
  - Auth: Custom OAuth → Supabase Auth
  - Job Queue: Postgres-based queue → Temporal.io workflows
  - File Storage: Custom handling → Supabase Storage (with R2 migration path)
  - Real-time: HTTP polling → Supabase Realtime
  - Email: Custom → Resend
  - SMS: Custom → Twilio
  - Frontend: Added shadcn/ui, TanStack Query, React Hook Form, Uppy
  - Payments: Added Stripe Billing
  - Security: Added Cloudflare, Upstash rate limiting
  - Observability: Added Sentry, Axiom, Highlight.io, PostHog
  - Testing: Specified Pytest + Playwright
  - Hosting: Specified Vercel + Render + Modal
- Added Technology Stack summary section
- Added Operational Services section
- Updated data model with Stripe and Temporal references

### v1.0.0 (2026-01-18)
- Initial PRD for MVP
- TikTok support only
- Core features: upload, enrichment, library, search
