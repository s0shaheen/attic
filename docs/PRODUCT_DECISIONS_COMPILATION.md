# Attic — Product Decisions Compilation

**Purpose:** Complete record of product ideas, solutions, tradeoffs, and implementation decisions discussed across this Claude project. Intended as input for GStack's `/plan-ceo-review` command.

**Last Compiled:** 2026-03-14
**PRD Version:** v1.3.0
**Status:** Pre-launch, active development

---

## 1. Product Vision & Evolution

### Origin → Current State

The product has gone through four distinct phases of thinking:

1. **"TikTok Unwrapped"** — A Spotify Wrapped-style viral wedge. Users upload TikTok data export, get a shareable "year in review" experience. One-time purchase ($25-35). Targeting December "wrapped season" cultural moment.

2. **Semantic Search & Library** — Evolved toward organizing saved/favorited content into a searchable personal library. Core insight: "I save videos but can never find them again." Subscription model.

3. **Classification + Entity Extraction** — Pivoted to classifying favorited/saved short-form content into structured personal collections with actionable entity extraction (restaurants, books, places). The product frame shifted from "self-reflection analytics" to "actionable idea extraction."

4. **Dual Open-Source / Paid Strategy** — Plan to open-source the ontology and classification pipeline, sell the hosted convenience layer (Plausible/PostHog model). Open-source repo launches before the paid product as content marketing.

### Core Value Propositions (Competing Frames)

| Frame | Value Prop | Target User | Pricing Fit |
|-------|-----------|-------------|-------------|
| Self-reflection | "Understand your digital consumption patterns" | Curious self-reflectors, 22-35 | Subscription |
| Discovery/search | "Find saved content through intelligent search" | Heavy savers who lose track | Subscription |
| Actionable utility | "Turn your TikTok saves into restaurant lists, book recs, etc." | Anyone who saves TikToks for later | One-time or subscription |
| Wrapped experience | "Your year on TikTok, beautifully visualized" | Viral/social sharing audience | One-time purchase |

**Unresolved tension:** The self-reflection frame is more differentiated but harder to sell. The utility frame ("find my saved restaurants") is more concrete and easier to convert on but less defensible. The current PRD straddles both.

### Mission Statement

"Reflection over optimization" — giving people clarity about their digital selves through a warm, judgment-free experience. Help people understand and reclaim control over their digital consumption.

---

## 2. Product Architecture Decisions

### 2.1 Platform Scope

| Phase | Platforms | Status |
|-------|-----------|--------|
| MVP | TikTok only | In development |
| Phase 1.5 | TikTok Data Portability API (EEA/UK users only) | Identified, post-MVP |
| Phase 2 | Instagram | Designed (adapter architecture ready) |
| Future | YouTube | Not designed |

**TikTok Data Portability API discovery:** TikTok has a GDPR-mandated Data Portability API that provides activity data (liked/favorited videos) via OAuth instead of manual ZIP export. Critical limitation: only available for EEA/UK users. The API returns the same ZIP format as manual exports, so the processing pipeline needs zero changes — only a new ingestion path.

**Decision:** Proceed with ZIP upload for MVP (works globally), add API as Phase 1.5 for European users. The API reduces time-to-value from 1-3 days (manual export) to minutes.

**Instagram considerations:** Instagram API/scraping is touchier (Meta more aggressive about blocking). Carousel posts need multi-media handling. Platform-agnostic adapter architecture already designed to accommodate this.

### 2.2 Data Ingestion

**Primary path (MVP):** User manually exports TikTok data (Settings → Download Data → JSON format), waits 1-3 days for email, downloads ZIP, uploads to Attic via Uppy drag-and-drop.

**Key friction identified:** The manual export process creates a 1-3 day gap between intent and value delivery. This is especially problematic when the product frame is "utility" (actionable restaurant/book lists) because the user has a specific, urgent need. Mitigation: frame the export as a one-time setup, not a recurring task.

**Continuous ingestion (post-MVP):** Share sheet / iOS shortcut that sends individual TikToks to Attic for real-time classification. Single-item pipeline: APIFY_ENRICH → TEXT_CLASSIFY → ENTITY_EXTRACT → ENTITY_RESOLVE → EMBED → AUTO-ROUTE TO COLLECTIONS. Cost: ~$0.003-0.005/item. This is the feature that makes the subscription sticky.

### 2.3 Processing Pipeline

**10-step pipeline orchestrated by AWS Step Functions → AWS Lambda:**

| Step | Purpose | Provider | Cost/item | Critical? |
|------|---------|----------|-----------|-----------|
| 1. PARSE_EXPORT | Extract URLs from ZIP, create media_event rows | Lambda | ~$0 | Yes |
| 2. APIFY_ENRICH | Fetch TikTok metadata (batched, 50/call) | Apify | ~$0.005-0.01 | Yes |
| 3. MEDIA_DOWNLOAD | Download video/images to S3 temp | Lambda + S3 | ~$0.001-0.002 | Conditional |
| 4. SUBTITLE_FETCH | Get TikTok's own ASR transcripts via Apify subtitleLinks | Apify data | ~$0 | Yes |
| 5. WHISPER_TRANSCRIBE | Transcribe via OpenAI if no subtitles | OpenAI | ~$0.005-0.01 | Conditional |
| 6. VISION_ANALYSIS | Visual tagging | Gemini Flash | ~$0.0002-0.001 | Tiered |
| 7. TEXT_FUSION | Combine caption + hashtags + transcript + OCR + visual_tags | Lambda | ~$0 | Yes |
| 8. EMBEDDING | Generate 1536-dim vectors (batched, 100/call) | OpenAI | ~$0.0001 | Paid only |
| 9. DERIVED_FIELDS | Compute engagement_rate, interaction_hour, etc. | Lambda | ~$0 | Yes |
| 10. SEARCH_INDEX | Update full-text (GIN) + vector (ivfflat) indexes | Supabase PG | ~$0 | Yes |

**Critical invariant:** Every Lambda function MUST be idempotent. Use upserts and deterministic IDs.

**Key cost insight — Apify subtitle extraction avoids Whisper costs:** TikTok's own ASR transcripts are available via Apify's `subtitleLinks` field. This eliminates expensive GPU transcription for the majority of videos.

### 2.4 Classification Architecture — Tiered Processing

This is the single most impactful architectural decision. Three options were evaluated:

**Option A: Text-first + thumbnail vision (RECOMMENDED)**
- Tier 1 (every item, cheap): Send caption + hashtags + transcript + thumbnail_url to Gemini Flash. One multimodal call.
- Tier 2 (on-demand, expensive): Full GPT-4 Vision with multiple keyframes, only when user opens Detail View.
- Cost: ~$0.005-0.008/video. 1,500 videos = $7-12.
- Time: 15-25 min for 1,500 videos.

**Option B: Text-only, skip vision entirely for MVP**
- Drop MEDIA_DOWNLOAD and VISION_ANALYSIS entirely. Pipeline becomes: PARSE → APIFY_ENRICH → SUBTITLE_FETCH → WHISPER (conditional) → TEXT_CLASSIFY → TEXT_FUSION → EMBEDDING → DERIVED_FIELDS → SEARCH_INDEX.
- Text-only classification achieves ~75-85% accuracy using captions + hashtags alone. Sufficient for aggregate stats and basic categorization.
- Cost: ~$0.004-0.006/video. 1,500 videos = $6-9.
- Time: 10-15 minutes.

**Option C: Full vision on every item (original PRD plan)**
- Every item gets multi-keyframe GPT-4 Vision analysis.
- Cost: ~$0.015-0.02/video. 1,500 videos = $22-30.
- Time: 30-60 min for power users.
- Rejected as default due to cost and speed.

**Decision rationale:** Vision analysis output only matters in Detail View (opened for ~5-10% of items). Aggregate surfaces (Wrapped stats, Library grid, search) work fine with text-only or thumbnail-level classification. Spending $0.012/video on data that appears as a single categorical badge is waste.

### 2.5 LLM Model Selection

**Major finding: GPT-4o mini has a hidden token penalty for images.** GPT-4o mini charges 2,833 tokens per image in low-res mode, making vision requests 2x more expensive than GPT-4o despite lower per-token pricing. This was the catalyst for switching to Gemini.

| Task | Model | Cost/1K items | Notes |
|------|-------|--------------|-------|
| Vision + OCR (unified) | Gemini 2.0 Flash-Lite | $0.34 | 89-94% cheaper than GPT-4o mini |
| Text classification | Gemini Flash or Flash-Lite | ~$0.04-0.15 | Text-only, structured output |
| Entity extraction | Gemini 2.0 Flash-Lite | $0.045 | 50% cheaper than GPT-4o mini |
| Cluster labeling | Gemini 2.0 Flash-Lite | $0.0025 | Negligible |
| Embeddings | OpenAI text-embedding-3-small | ~$0.01 | Industry standard |
| Whisper (fallback) | OpenAI Whisper | ~$5-10/1K | Only for items without Apify subtitles |

**Total pipeline cost reduction: $3.67 → $0.39 per 1,500 items (89% reduction)** by switching from GPT-4o mini to Gemini Flash-Lite and unifying OCR + visual tagging into a single call.

**Two-stage LLM classification methodology (from ontology v2):**
- Stage 1: Cheap vision model extracts literal description (Gemini Flash)
- Stage 2: Three grouped text-only calls for Content Identity, Interpretive Layer, and Entity Extraction
- No internet access during classification to preserve determinism

**Evaluation framework designed:** Gold standard datasets, Cohen's Kappa inter-rater reliability, confusion matrices, differentiated accuracy thresholds by facet. Build eval before committing to model/prompt choices.

### 2.6 Ontology

**V1 (in PRD v1.3.0):** 5 facets — mood, content_category, creator_archetype, audience_role, content_format. Muddled boundaries, overlapping concerns.

**V2 redesign (completed):** 8 clean orthogonal facets:

| Facet | What it captures | Grounding |
|-------|-----------------|-----------|
| Affect | Emotional tone/mood | Russell's Circumplex Model, Plutchik's Wheel |
| Topic | Subject matter | IAB taxonomy, IPTC NewsCodes |
| Genre/Communicative Practice | Format/medium conventions | Media studies |
| Communicative Intent | Creator's purpose | Uses & Gratifications theory |
| Creator Role | Who made this | Journalism/media archetypes |
| Viewer Orientation | How the viewer relates | Uses & Gratifications (audience side) |
| Presentation Style | Visual/editorial style | Design taxonomy |
| Content Provenance | Original, repost, duet, etc. | Platform metadata |

**Entity model:** Schema.org types with nullable Wikidata IDs.

**Two-tier label system:** Fixed tier-1 ontology labels (stable taxonomy) + open tier-2 LLM-generated micro-labels (for future clustering and emergent categories).

**Positioning:** Dublin Core → documents, IPTC → professional media, IAB → advertising, Attic → users' own content. Nobody has given users a vocabulary for understanding their own short-form video consumption.

### 2.7 Collections (New Concept, Not in PRD v1.3.0)

Collections are the proposed primary product surface (replacing Library as default). Auto-generated from entity extraction categories:

- Restaurants & Places to Eat
- Books to Read
- Movies & Shows to Watch
- Places to Visit
- Products to Try
- Recipes to Cook
- Workouts & Fitness
- Music & Artists

Each collection contains extracted entities with external links (Google Maps for restaurants, Goodreads for books, TMDB for movies, etc.). Entity resolution is lazy — resolves on-demand when user views a collection, cached afterward.

**Open questions:**
- How many categories at launch?
- Collections vs. Library — which is the default landing page for paid users?
- How do items that match multiple collections (restaurant + travel) get handled?
- What does the share sheet / shortcut MVP look like?

---

## 3. Tech Stack Decisions & Evolution

### 3.1 Stack Evolution

| Component | v1.0 (Original) | v1.1 (Managed Services) | v1.3 (Current) |
|-----------|-----------------|------------------------|-----------------|
| Auth | Custom OAuth | Supabase Auth | Supabase Auth |
| Database | Self-managed Postgres | Supabase PostgreSQL | Supabase PostgreSQL + pgvector |
| Backend | FastAPI | FastAPI | FastAPI |
| Orchestration | Custom Postgres queue | Temporal.io → Inngest | AWS Step Functions |
| Compute | Modal (full) | Modal (compute only) | AWS Lambda |
| Queue | — | — | AWS SQS |
| Frontend | Next.js + custom | Next.js + shadcn/ui | Next.js 14 + shadcn/ui |
| Email | Custom | Resend | Resend |
| SMS | Custom | Twilio | Dropped (email only for MVP) |
| Payments | Custom | Stripe Billing | Stripe Billing |
| Monitoring | Multiple tools | Sentry + Axiom + Highlight.io | Sentry + PostHog |
| Rate Limiting | Custom | Upstash | TBD |
| CDN | — | Cloudflare | TBD |

### 3.2 Key Tech Stack Tradeoffs

**AWS Step Functions over Temporal.io:**
- Pro: Pay-per-transition pricing ($0.025/1K transitions), no infrastructure to manage, visual debugging console, native AWS integration
- Con: Less flexible than Temporal for complex workflows, vendor lock-in
- Decision: Step Functions wins for MVP — Temporal is overkill for a 10-step linear pipeline

**AWS Lambda over Modal:**
- Pro: Native AWS integration with Step Functions, pay-per-invocation, simpler deployment
- Con: Cold starts, 15-min timeout limit, less flexible for GPU workloads
- Decision: Lambda for standard pipeline steps; Modal retained as option for future GPU-intensive work

**Supabase over custom infrastructure:**
- Pro: Auth + Postgres + Storage + Realtime in one service, RLS for multi-tenant isolation, pgvector for search
- Con: Vendor dependency, limited customization
- Decision: Overwhelming winner for solo founder — eliminates 200+ hours of custom infrastructure work

**PostHog over Mixpanel/Amplitude:**
- Pro: Open source, self-hostable, 1M events/month free, GDPR compliant, event tracking + session replay + feature flags + A/B testing
- Con: Less mature than competitors
- Decision: Best balance of features, cost, and privacy for indie products

### 3.3 Infrastructure Costs

**Estimated monthly MVP cost: ~$70-80/month**

| Component | Service | Cost |
|-----------|---------|------|
| Frontend | Vercel | $20/mo |
| Backend API | Render | $7/mo |
| Database | Supabase | $25/mo |
| Workflow | AWS Step Functions | ~$5/mo |
| Compute | AWS Lambda | ~$10/mo |
| Queue | AWS SQS | <$1/mo |

---

## 4. Pricing & Monetization

### 4.1 Pricing Models Evaluated

**One-time purchase:**
- Fits the "backlog processing" use case (user uploads, gets collections, done)
- Lower conversion friction ($15 once < $12/month psychologically)
- Matches how most users will actually behave (process backlog, grab lists, leave)
- Risk: No recurring revenue, hard to build a business

**Subscription:**
- Fits continuous ingestion + living library use case
- Higher LTV ($72/6 months vs $20 one-time)
- Aligns with ongoing per-user costs
- Risk: High month-1 churn (40-60% predicted) until continuous ingestion is sticky

**Hybrid (RECOMMENDED):**

| Tier | Price | What You Get |
|------|-------|-------------|
| Free | $0 | 1 platform, 6-month window, 1 category collection, view-only entity list |
| Single Run | $8-15 one-time | Full backlog (all categories, full history), all collections with export/share, Library view. No continuous ingestion, no search, no entity resolution. |
| Attic Pro | $8-12/month | Everything + continuous ingestion, semantic search, entity resolution (external links), multi-platform, re-process anytime |

**Specific recommendation:** Launch with $12.99 one-time + $9.99/month subscription. Free tier cost ceiling: ~$1-2 per user (just Apify + text classification).

### 4.2 Pricing Validation Plan

1. **Fake-door test ($0, 1-2 days):** Landing page with CTA at different price points, measure click-through
2. **First-100-users experiment (weeks 1-4):** Launch at $9.99 one-time, raise to $14.99 after 2 weeks, introduce subscription at $9.99/mo after 2 more weeks
3. **Post-purchase survey:** "What almost stopped you from buying?"
4. **Cohort analysis (months 2-6):** Track retention and LTV by pricing cohort

### 4.3 Comparable Pricing

| Product | Model | Price | Relevance |
|---------|-------|-------|-----------|
| Readwise | Subscription | $8.99/mo | Save and organize highlights |
| Raindrop.io | Subscription | $3-5/mo | Bookmark manager with AI tagging |
| Pocket Premium | Subscription | $5/mo | Save articles with search |
| Screen time apps | Mixed | $0-5/mo | Digital wellness tools |

Attic's entity extraction + resolution justifies higher end of range.

### 4.4 Unit Economics

**Free tier:**
- Cost per user: ~$0.85-1.90 (mostly Apify)
- At 5% conversion: ~$19 CAC via free tier
- At 10% conversion: ~$9.50 CAC
- Paid user LTV at $12/mo × 4 months: ~$48
- LTV:CAC ratio: 2.5-5x (healthy)

**Paid pipeline cost per user (full backlog, 2,000 items):**
- Current 10-step pipeline: ~$30-40
- Optimized text-first pipeline: ~$10-16
- Payback period: 1-3 months at $12/month

---

## 5. GTM & Marketing Strategy

### 5.1 Distribution Channels

| Channel | Strategy | Priority |
|---------|----------|----------|
| X (Twitter) | Build in public, technical/builder content | Primary |
| TikTok | AI ethics, digital wellness content | Secondary |
| Instagram | Similar to TikTok | Secondary |
| Reddit | r/TikTok, r/dataisbeautiful, r/digitalminimalism | Launch burst |
| Product Hunt | Launch listing | One-time |
| Creator partnerships | Free premium analysis for honest reviews | Post-launch |

### 5.2 Open-Source as Marketing

**Strategy:** Publish `ONTOLOGY.md` / `PHILOSOPHY.md` and open-source the classification pipeline BEFORE the paid product. This establishes credibility, attracts developers, and creates inbound interest.

**Business model parallel:** spaCy (open-source NLP) + Prodigy (paid annotation tool). The open-source tool drives awareness; the hosted convenience layer drives revenue.

**Positioning:** "The first open taxonomy for understanding personal short-form video consumption."

### 5.3 Launch Tactics (from Starter Story analysis)

- **Waitlist + scarcity:** "First 200 users get 50% lifetime discount"
- **Pre-sale validation:** Consider selling 50 lifetime licenses before full build
- **Tutorial marketing:** Hook on problem → Show blueprint → Position product as one part of solution
- **Build in public daily:** Share wins AND failures for trust-building
- **Reddit/Facebook groups:** One well-crafted post in the right group can drive 1,500 visitors
- **Every feature = new launch:** Don't frame updates as updates; frame them as new products
- **Viral tweet formula:** Familiar interface + aha moment in 20 seconds + tag tools you use

### 5.4 Competitive Landscape

**No direct competitors.** Indirect competitor groups:

1. **Social media analytics platforms** — Serve influencers/marketing teams, not consumers
2. **Screen time / dopamine detox apps** — Reduction-focused, not reflection-focused
3. **"Send here to save" apps** — Work on individual items in niches (restaurants), no historical analysis
4. **Nostalgia apps** — Different value prop

**Moat (ranked by defensibility):**
1. Enrichment ontology — 50+ semantic tags per video in a proprietary taxonomy that doesn't exist elsewhere
2. Published open-source standard — if researchers/developers build around Attic's taxonomy, switching costs emerge
3. Network effects (if data collective ships) — more contributors = richer data
4. Processing pipeline is NOT a moat — reproducible by anyone with LLM API access

---

## 6. Data Marketplace / "Attic Collective" (Future)

### 6.1 Concept

Users opt into sharing anonymized, enriched behavioral data. Buyers get aggregate behavioral profiles, not individual records. Data-for-product-access model (not cash-for-data).

### 6.2 Why Cash-for-Data Fails

Every direct cash-for-data marketplace has failed (Datacoup, Datum, UBDI, Streamr). The gap between user psychological valuation ("my data is worth $50/month") and actual buyer prices ($0.01-0.50/user/month) is fatal. Data-for-product-access survives this gap because the perceived value is the product, not the cash equivalent.

### 6.3 What Would Be Sold

**NOT raw data.** Sell enriched aggregate profiles:

- Tier 1 (safest): Aggregate distributions — "Across 5,000 users aged 22-28, 34% of favorited content is food_cooking"
- Tier 2: Anonymized behavioral vectors — individual profiles stripped of PII, represented as feature vectors across ontology dimensions
- Tier 3: Segment-level datasets — complete anonymized profiles filtered by demographics

**Pricing: $5-50 per 1,000 profiles**, depending on richness and segment specificity.

### 6.4 Technical Architecture

- New tables: `data_collective_consents`, `dataset_exports`, `dataset_buyers`
- New Step Functions workflow: EXTRACT → ANONYMIZE → AGGREGATE → K-ANONYMITY CHECK → PACKAGE → DELIVER
- Read-only export layer on existing DB (no data duplication)
- Buyer vetting: manual approval, verified orgs, stated use cases

### 6.5 Legal Questions (Unresolved, Blocking)

Five specific questions need legal counsel ($500-4,000 budget):

1. Can users re-sell/license their own GDPR/CCPA data exports?
2. Does Apify scraping of public TikTok metadata from user-provided URLs violate TOS?
3. Does properly anonymized data still qualify as "personal data" under CCPA/GDPR?
4. What consent framework is needed for aggregate data sharing?
5. Can anonymized behavioral datasets be sold under CCPA's broad "sale" definition?

**Critical sequencing: Do NOT build any marketplace features until after MVP launch AND legal green-light.**

---

## 7. Security, Privacy & Production Readiness

### 7.1 Privacy Principles

- Store ONLY processed outputs — no raw video/audio retained
- Raw ZIP deleted immediately after parsing (including on failure paths)
- Subscription-tied data retention
- Delete-on-request within 24 hours
- No user identifiers or behavioral data shared with 3rd parties
- Explicit consent screen with clear, readable privacy notes
- Whitelist-based access for third-party services

### 7.2 Production-Ready Ship Gate

Explicit criteria that must be met before inviting external users:

| Dimension | Requirements |
|-----------|-------------|
| Security | Server-side auth enforcement, RLS on all user-owned tables, rate limiting, least-privilege secrets |
| Privacy | Whitelist-only export parsing, deterministic ZIP deletion, automated retention/deletion policies |
| Reliability | Idempotent pipeline activities, dedupe/upsert semantics, partial failure as first-class |
| Performance | Meet MVP NFR targets, baseline tests |
| Observability | Correlation IDs, structured logs, error tracking, alerts, dashboards, kill switches |
| Release | CI gates, staging smoke tests, rollback plan, incident runbooks |

### 7.3 Alternatives Considered

- "Ship features first, harden later" — Rejected (highest risk of data leak, uncontrolled cost)
- "Rely only on vendor defaults" — Rejected (misconfiguration risk)
- "Build fewer guardrails, accept manual ops" — Rejected (doesn't scale even to small cohort)

---

## 8. Frontend & Design

### 8.1 Design Aesthetic

"Warm Minimal" — dark charcoal, cream, amber, Inter typography. Notebook-esque feel throughout, with selective "Data Forward" elements in library view for usability. Desktop-first, absolutely must be mobile responsive.

### 8.2 Frontend Stack

| Library | Purpose |
|---------|---------|
| Next.js 14 (App Router) | Server components, routing |
| shadcn/ui | Copy-paste components, Radix accessibility |
| Tailwind CSS | Utility-first styling |
| TanStack Query | Data fetching, caching, pagination |
| React Hook Form + Zod | Type-safe forms |
| Uppy | File upload with progress |
| Lucide React | Icons |

### 8.3 Key UX Decisions

- Library view unlocks after Apify enrichment (before full processing), but search/interaction disabled until processing completes
- Step-by-step processing progress visible in frontend
- Email notifications when processing completes (SMS dropped)
- Google OAuth only (Apple OAuth dropped for MVP simplicity)
- v0.dev for rapid component prototyping

---

## 9. Development Methodology

### 9.1 Spec-Driven Development

- Task specification files as source of truth per task
- Dev Guide tracks project-level completion across epics
- Claude Code slash commands for batch operations:
  - `/generate-specs` — Create spec files from Dev Guide
  - `/validate-specs` — Check specs for completeness
  - `/implement-backlog` — Build tasks from specs
  - `/run-task-tests` — Run task-specific tests

### 9.2 Epic Structure

| Phase | Epics |
|-------|-------|
| Phase 1: Foundation | Epic 0: Infrastructure & Foundation |
| Phase 2: Core Journey | Epic 1: Auth, Epic 2: Upload & Consent, Epic 3: Processing Pipeline |
| Phase 3: UI | Epic 4: Progress & Notifications, Epic 5: Library View, Epic 7: Detail View |
| Phase 4: Discovery | Epic 6: Search |
| Phase 5: Polish | Epic 8: User Settings & Landing |

### 9.3 Capability Abstraction

Protocol interfaces for vendor abstraction in processing:

```python
class VideoMetadataProvider(Protocol):
    def fetch_metadata(self, urls: list[str]) -> list[VideoMetadataResult]: ...

class VisionAnalyzer(Protocol):
    def analyze(self, images: list[bytes], context: VideoContext) -> VisionAnalysisResult: ...

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

This makes model swaps (e.g., Gemini → future cheaper model) trivial.

---

## 10. Open Questions & Unresolved Decisions

### Product

- [ ] Final product frame: self-reflection vs. utility vs. both?
- [ ] How many entity categories at launch?
- [ ] Collections vs. Library as default landing page for paid users?
- [ ] Is there a one-time purchase option for "process my backlog" without subscribing?
- [ ] Should free users get a second free category after N days (re-engagement hook)?
- [ ] What does the share sheet / shortcut MVP look like? iOS only to start?
- [ ] Should VISION_ANALYSIS be cut entirely from MVP or kept as paid detail-view enhancement?

### Technical

- [ ] Entity extraction accuracy targets — is 60% extraction rate acceptable at launch?
- [ ] Auto-routing logic for continuous ingestion: keyword-based or embedding-similarity?
- [ ] How to handle items that match multiple collections (restaurant + travel)?
- [ ] Per-platform video limits or total across all platforms?

### Business

- [ ] Free tier cost ceiling — what's the max to spend per free user?
- [ ] Continuous ingestion cost tracking — per-item budget per subscriber per month?
- [ ] When does multi-platform (Instagram) launch relative to TikTok?
- [ ] Legal counsel for TOS/privacy questions — timeline and budget?

### Go-to-Market

- [ ] Launch timing — is there still a "wrapped season" play or has that window passed?
- [ ] Open-source repo launch timing relative to paid product?
- [ ] Waitlist/early interest building — when to start?
- [ ] Influencer budget allocation?

---

## 11. Key Learnings & Principles

1. **Ship over research polish.** Repeatedly identified as the primary risk — over-designing before shipping.
2. **Text-first classification is dramatically cheaper.** 75-85% accuracy at a fraction of vision pipeline costs. Vision reserved for cases where it adds clear value.
3. **Gemini Flash over GPT-4o mini for vision.** Hidden token penalty on GPT-4o mini makes it 10x more expensive than Gemini Flash for equivalent quality.
4. **Ontology is the moat.** The processing pipeline is reproducible; the labeled dataset at scale and the published taxonomy are not.
5. **Data marketplace price disparity is fatal for cash-for-data.** Only data-for-product-access survives.
6. **Managed services over custom builds.** Supabase + Step Functions + Lambda saves 200+ dev hours vs. custom infrastructure.
7. **Apify subtitle extraction avoids Whisper costs.** TikTok's own ASR transcripts are free via Apify.
8. **Open-source before paid.** Launch the ontology/philosophy doc and repo first to build credibility.
9. **Every Lambda must be idempotent.** Non-negotiable for async pipeline reliability.
10. **Evaluation-first mindset.** Build eval frameworks before committing to model/prompt choices.

---

## 12. Success Metrics

### MVP Launch (First 30 Days)

| Metric | Target |
|--------|--------|
| Signups | 500 users |
| Uploads completed | 200 |
| Free → paid conversion | 10% |
| Processing success rate | > 95% |
| Avg processing time (1,000 videos) | < 15 minutes |

### Growth Indicators

| Metric | Target |
|--------|--------|
| Weekly active users | Users who search or browse library |
| 30-day retention | Users who return after initial upload |
| NPS | > 40 |

---

## 13. Resource Constraints

- **Solo founder, bootstrapping with personal funds**
- **No existing audience** (0 followers across all platforms at project start)
- **Job searching in parallel** — limited time bandwidth
- **No legal counsel yet** — identified as a gap
- **Marketing budget: ~$1,000** (flexible)
- **Runway: bootstrapped** — no external funding pressure but also no cushion
