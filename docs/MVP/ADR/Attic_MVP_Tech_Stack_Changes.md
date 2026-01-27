# Attic - Plug-and-Play Tool Recommendations

**Analysis Date:** 2026-01-23  
**Purpose:** Replace custom implementations with battle-tested tools/libraries

---

## Executive Summary

Rather than building auth, database management, job queues, and other infrastructure from scratch, leverage proven tools that handle edge cases, security, and scaling. This analysis reviews each system component and recommends the best-in-class tools.

**Key Philosophy:**
- Use managed services for undifferentiated heavy lifting
- Prefer tools with active communities and long-term support
- Balance cost vs. development velocity
- Prioritize security and compliance out-of-the-box

---

## 1. Authentication & User Management

### Current PRD Plan
- Custom OAuth 2.0 implementation
- Custom JWT session management
- Custom user table management
- Manual Apple/Google OAuth integration

### **RECOMMENDED: Supabase Auth**

**Why Supabase:**
- ✅ Drop-in OAuth for Google, Apple, GitHub, etc.
- ✅ JWT management, refresh tokens, session handling built-in
- ✅ Row-level security (RLS) policies for data isolation
- ✅ Email/password fallback if needed
- ✅ Account deletion, password reset flows included
- ✅ PostgreSQL database included (perfect for your needs)
- ✅ Free tier: 50,000 monthly active users

**Implementation:**
```typescript
// Frontend - Next.js example
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'

const supabase = createClientComponentClient()

// Sign in with Google
await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${location.origin}/auth/callback`
  }
})

// Get current user
const { data: { user } } = await supabase.auth.getUser()

// Sign out
await supabase.auth.signOut()
```

**Backend Integration:**
```python
# FastAPI middleware
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(token: str):
    user = supabase.auth.get_user(token)
    return user
```

**Alternative: Clerk**
- More polished UI components
- Easier organization/team features for future
- Higher cost ($25/mo base + usage)
- Better for B2B pivot if needed

**Alternative: Auth0**
- Enterprise-grade
- Overkill for MVP
- More expensive

**Verdict:** Use **Supabase Auth** + Supabase PostgreSQL for database. It's a perfect match for your stack.

---

## 2. Database & ORM

### Current PRD Plan
- Raw PostgreSQL with manual migrations
- Custom SQL for all queries
- Manual connection pooling

### **RECOMMENDED: Supabase PostgreSQL + SQLAlchemy**

**Database: Supabase PostgreSQL**
- ✅ Managed PostgreSQL with pgvector extension (critical for embeddings!)
- ✅ Row-level security for multi-tenant data isolation
- ✅ Automatic backups
- ✅ Connection pooling via PgBouncer
- ✅ Real-time subscriptions (useful for progress updates)
- ✅ Free tier: 500MB database, 2GB bandwidth

**ORM: SQLAlchemy 2.0**
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class MediaEvent(Base):
    __tablename__ = "media_events"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    caption_text: Mapped[str | None]
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(1536))
    # ... rest of fields
```

**Migration Tool: Alembic**
```bash
# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "create media_events table"

# Apply migration
alembic upgrade head
```

**Alternative: Prisma**
- Great TypeScript ORM if you go Node.js route
- Better type safety
- Less Python ecosystem maturity

**Alternative: Django ORM**
- Would require switching to Django framework
- Overkill for API-only backend

**Verdict:** Use **Supabase PostgreSQL + SQLAlchemy 2.0 + Alembic**. Native pgvector support is critical for semantic search.

---

## 3. Backend API Framework

### Current PRD Plan
- Custom FastAPI implementation

### **RECOMMENDED: FastAPI (keep it!) + FastAPI-Users**

**Keep FastAPI:**
- ✅ Already in your plan, excellent choice
- ✅ Async support perfect for I/O-bound tasks
- ✅ Automatic OpenAPI docs
- ✅ Pydantic validation

**Add: FastAPI-Users**
```python
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend

# Integrates with Supabase or any auth provider
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)
```

**Add: FastAPI-Pagination**
```python
from fastapi_pagination import Page, add_pagination, paginate

@app.get("/media-events", response_model=Page[MediaEventSchema])
async def list_media_events(session: AsyncSession):
    query = select(MediaEvent)
    return await paginate(session, query)

add_pagination(app)
```

**Add: FastAPI-Cache2**
```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

@cache(expire=300)
@app.get("/media-events/{id}")
async def get_media_event(id: uuid.UUID):
    # Results cached for 5 minutes
    ...
```

**Verdict:** Keep **FastAPI**, add helper libraries for common patterns.

---

## 4. Job Queue & Background Processing

### Current PRD Plan
- Custom Postgres-based queue
- Manual worker polling
- Custom retry logic

### **RECOMMENDED: Temporal.io OR Celery + Redis**

**Option A: Temporal.io** (RECOMMENDED)

Perfect for your multi-step pipeline with retries and observability.

```python
from temporalio import activity, workflow
from datetime import timedelta

@activity.defn
async def enrich_with_apify(video_urls: list[str]) -> dict:
    # Automatic retries, timeouts
    result = await apify_client.enrich(video_urls)
    return result

@workflow.defn
class VideoProcessingWorkflow:
    @workflow.run
    async def run(self, upload_id: str) -> dict:
        # Sequential steps with automatic state management
        urls = await workflow.execute_activity(
            parse_export,
            upload_id,
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        metadata = await workflow.execute_activity(
            enrich_with_apify,
            urls,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy={"maximum_attempts": 3}
        )
        
        # ... continue through pipeline
        return {"status": "complete"}
```

**Why Temporal:**
- ✅ Built for multi-step workflows (your 10-step pipeline)
- ✅ Automatic state persistence
- ✅ Visual workflow UI for debugging
- ✅ Handles retries, timeouts, dead letter queues
- ✅ Can pause/resume long-running workflows
- ✅ Perfect for "user uploads, leaves, comes back" scenario
- ✅ Free self-hosted, or Temporal Cloud

**Option B: Celery + Redis** (Simpler alternative)

```python
from celery import Celery, chain
from celery.result import AsyncResult

app = Celery('attic', broker='redis://localhost:6379/0')

@app.task(bind=True, max_retries=3)
def enrich_with_apify(self, video_urls: list[str]):
    try:
        result = apify_client.enrich(video_urls)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)

# Chain tasks together
pipeline = chain(
    parse_export.s(upload_id),
    enrich_with_apify.s(),
    download_media.s(),
    # ... etc
)
result = pipeline.apply_async()

# Check status
AsyncResult(task_id).status  # 'PENDING', 'SUCCESS', 'FAILURE'
```

**Why Celery:**
- ✅ Python standard for async tasks
- ✅ Simpler than Temporal
- ✅ Good monitoring with Flower UI
- ❌ Less workflow orchestration features
- ❌ Harder to handle complex retry/compensation logic

**Alternative: Modal.com's built-in queue**
Since you're already using Modal for serverless, you could use Modal's `@stub.function` with `allow_concurrent_inputs`:

```python
from modal import Stub, Image, Queue

stub = Stub("attic-processing")
queue = Queue.new()

@stub.function()
async def process_video_batch(batch_id: str):
    # Modal handles concurrency, retries
    ...

# Enqueue work
queue.put.remote({"batch_id": "123"})
```

**Verdict:** Use **Temporal.io** for production robustness OR **Celery + Redis** for simpler MVP. Modal's queue is fine for very simple cases but lacks workflow features.

---

## 5. File Storage & Upload Handling

### Current PRD Plan
- Custom file upload handling
- Temporary storage for processing
- Manual cleanup

### **RECOMMENDED: Supabase Storage OR Cloudflare R2**

**Option A: Supabase Storage** (Easiest)

```typescript
// Frontend - Direct upload
const { data, error } = await supabase.storage
  .from('uploads')
  .upload(`${userId}/${uploadId}/export.zip`, file, {
    cacheControl: '3600',
    upsert: false
  })

// Backend - Retrieve for processing
file_bytes = supabase.storage.from('uploads').download(path)

// Auto-delete after processing
await supabase.storage.from('uploads').remove([path])
```

**Why Supabase Storage:**
- ✅ Integrated with Supabase Auth (automatic RLS)
- ✅ Free tier: 1GB storage
- ✅ Resumable uploads
- ✅ Automatic CDN distribution
- ✅ Image transformations (for thumbnails)

**Option B: Cloudflare R2** (More cost-effective at scale)

```python
import boto3  # R2 is S3-compatible

s3 = boto3.client(
    's3',
    endpoint_url='https://<account>.r2.cloudflarestorage.com',
    aws_access_key_id='...',
    aws_secret_access_key='...'
)

# Upload
s3.upload_fileobj(file, 'attic-uploads', f'{user_id}/{upload_id}.zip')

# Download for processing
s3.download_fileobj('attic-uploads', key, local_file)

# Delete
s3.delete_object(Bucket='attic-uploads', Key=key)
```

**Why R2:**
- ✅ No egress fees (huge savings)
- ✅ S3-compatible API
- ✅ $0.015/GB/month (vs S3's $0.023)
- ✅ Better for large files
- ❌ Requires separate auth management

**For Downloaded Media (videos/thumbnails):**
Use **Cloudflare R2** with CDN for serving to frontend. Supabase Storage works too but R2's zero egress makes it better for user-facing assets.

**Presigned URLs for frontend:**
```python
# Generate presigned URL for direct upload
presigned_url = s3.generate_presigned_url(
    'put_object',
    Params={'Bucket': 'attic-uploads', 'Key': key},
    ExpiresIn=3600
)
# Return to frontend, which uploads directly to R2
```

**Verdict:** Use **Supabase Storage** for MVP simplicity, plan to migrate to **Cloudflare R2** when you hit scaling/cost thresholds.

---

## 6. Vector Search & Embeddings

### Current PRD Plan
- PostgreSQL with pgvector extension
- Manual embedding generation
- Custom similarity search

### **RECOMMENDED: Keep pgvector + Add Qdrant (optional future)**

**Current Plan is Good:**
```python
from sqlalchemy import select, func
from pgvector.sqlalchemy import Vector

# Semantic search with pgvector
query_embedding = openai.embeddings.create(
    input=query,
    model="text-embedding-3-small"
).data[0].embedding

stmt = (
    select(MediaEvent)
    .order_by(MediaEvent.embedding_vector.l2_distance(query_embedding))
    .limit(20)
)
results = await session.execute(stmt)
```

**Why pgvector:**
- ✅ Zero additional infrastructure
- ✅ Good enough for <1M vectors (your MVP scale)
- ✅ ACID guarantees with your data
- ✅ Native Postgres, easy backups

**When to Consider Qdrant/Pinecone:**
- Scaling beyond 1M vectors
- Need sub-50ms search latency
- Want filtered vector search (pgvector's filtering is slow)

**Embedding Generation:**
Keep **OpenAI text-embedding-3-small** ($0.02/1M tokens). Don't overcomplicate.

**Verdict:** Stick with **pgvector in Supabase**. Only add dedicated vector DB if you hit performance walls.

---

## 7. Full-Text Search

### Current PRD Plan
- PostgreSQL full-text search (GIN index)

### **RECOMMENDED: Keep PostgreSQL FTS OR Add Typesense**

**Option A: PostgreSQL FTS** (Keep it!)

```sql
-- Your current plan
CREATE INDEX idx_media_events_fulltext 
ON media_events USING GIN (to_tsvector('english', full_text));

-- Query
SELECT * FROM media_events 
WHERE to_tsvector('english', full_text) @@ plainto_tsquery('english', 'cooking pasta')
ORDER BY ts_rank(to_tsvector('english', full_text), plainto_tsquery('english', 'cooking pasta')) DESC;
```

**Why keep it:**
- ✅ Zero additional infrastructure
- ✅ Handles your scale fine
- ✅ Integrated with your data

**Option B: Typesense** (If you want better search UX)

```python
import typesense

client = typesense.Client({
    'nodes': [{'host': 'xxx.a1.typesense.net', 'port': '443', 'protocol': 'https'}],
    'api_key': '...',
})

# Index document
client.collections['media_events'].documents.create({
    'id': str(event.id),
    'caption': event.caption_text,
    'hashtags': event.hashtags,
    'creator': event.creator_username,
    'mood': event.mood_primary,
})

# Search with typo tolerance, facets
results = client.collections['media_events'].documents.search({
    'q': 'cooking psta',  # Handles typo
    'query_by': 'caption,hashtags',
    'filter_by': 'mood:funny',
    'facet_by': 'creator,mood',
})
```

**Why Typesense:**
- ✅ Typo tolerance (better UX)
- ✅ Instant search (<50ms)
- ✅ Faceted search (filters)
- ✅ Geo-search, scoped API keys
- ✅ Self-hosted or Typesense Cloud ($0.03/hr)
- ❌ Additional infrastructure

**Verdict:** Start with **PostgreSQL FTS**. If search UX becomes a differentiator, add **Typesense**.

---

## 8. Real-time Progress Updates

### Current PRD Plan
- HTTP polling every few seconds

### **RECOMMENDED: Supabase Realtime OR Server-Sent Events (SSE)**

**Option A: Supabase Realtime** (Easiest)

```typescript
// Frontend - Subscribe to upload progress
const channel = supabase
  .channel('upload-progress')
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',
      schema: 'public',
      table: 'upload_pipeline_runs',
      filter: `id=eq.${uploadId}`
    },
    (payload) => {
      setProgress(payload.new.videos_enriched)
    }
  )
  .subscribe()
```

**Why Supabase Realtime:**
- ✅ Zero setup (built into Supabase)
- ✅ Listens to database changes
- ✅ Automatic reconnection
- ✅ Works with RLS policies
- ✅ No polling overhead

**Option B: Server-Sent Events (SSE)**

```python
# FastAPI
from sse_starlette.sse import EventSourceResponse

@app.get("/api/uploads/{upload_id}/progress-stream")
async def progress_stream(upload_id: str):
    async def event_generator():
        while True:
            progress = await get_upload_progress(upload_id)
            yield {
                "event": "progress",
                "data": progress.json()
            }
            if progress.status == "complete":
                break
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())
```

```typescript
// Frontend
const eventSource = new EventSource(`/api/uploads/${uploadId}/progress-stream`)
eventSource.addEventListener('progress', (e) => {
  const progress = JSON.parse(e.data)
  setProgress(progress)
})
```

**Why SSE:**
- ✅ Simpler than WebSockets for one-way updates
- ✅ Auto-reconnect built-in
- ✅ HTTP/2 friendly
- ❌ Requires keeping connection open

**Verdict:** Use **Supabase Realtime** for MVP. It's free, integrated, and handles all edge cases.

---

## 9. Email & SMS Notifications

### Current PRD Plan
- Custom email/SMS integration

### **RECOMMENDED: Resend (Email) + Twilio (SMS)**

**Email: Resend**

```python
import resend

resend.api_key = "re_..."

resend.Emails.send({
    "from": "Attic <notifications@attic.app>",
    "to": user.email,
    "subject": "Your TikTok analysis is ready! ✨",
    "html": render_template("processing_complete.html", user=user)
})
```

**Why Resend:**
- ✅ Modern, developer-friendly API
- ✅ 3,000 emails/month free
- ✅ Built-in templates with React Email
- ✅ Great deliverability
- ✅ Webhooks for bounces/opens
- ✅ Founded by Vercel VP, active development

**Alternative: SendGrid**
- More enterprise features
- More expensive
- Harder to set up

**SMS: Twilio**

```python
from twilio.rest import Client

client = Client(account_sid, auth_token)

message = client.messages.create(
    body="Your Attic analysis is ready! https://attic.app/library",
    from_="+1234567890",
    to=user.phone
)
```

**Why Twilio:**
- ✅ Industry standard for SMS
- ✅ Reliable delivery
- ✅ $15 credit free trial
- ✅ ~$0.0075/SMS in US
- ✅ International support

**Alternative: SNS**
- Cheaper at scale ($0.00645/SMS)
- More setup complexity
- Less dev-friendly API

**Verdict:** Use **Resend for email** and **Twilio for SMS**. Both have excellent free tiers for MVP.

---

## 10. Error Tracking & Monitoring

### Current PRD Plan
- Print statements and logs?

### **RECOMMENDED: Sentry (Errors) + Axiom/Better Stack (Logs)**

**Error Tracking: Sentry**

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://...",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% performance monitoring
)

# Automatic error capture
raise Exception("Something broke")  # → Sentry alert

# Add context
sentry_sdk.set_user({"id": user.id, "email": user.email})
sentry_sdk.set_tag("upload_id", upload_id)
```

**Why Sentry:**
- ✅ Best-in-class error tracking
- ✅ 5,000 errors/month free
- ✅ Stack traces, breadcrumbs, user context
- ✅ Release tracking, performance monitoring
- ✅ Integrations with everything

**Logging: Axiom OR Better Stack**

```python
import structlog
from axiom import Client

logger = structlog.get_logger()

logger.info(
    "video_enriched",
    video_id=video.id,
    user_id=user.id,
    cost_usd=0.0023,
    processing_time_seconds=12.4
)
```

**Why Axiom:**
- ✅ 500GB/month free
- ✅ Structured logging
- ✅ Fast search across all logs
- ✅ No sampling
- ✅ Cost-based queries (track your AI spend!)

**Alternative: Better Stack (Logtail)**
- 1GB/month free
- Prettier UI
- Live tail feature
- Good for smaller projects

**Verdict:** Use **Sentry for errors** and **Axiom for logs**. Both have generous free tiers.

---

## 11. Frontend Framework & UI Components

### Current PRD Plan
- Next.js (good choice!)
- Custom UI components

### **RECOMMENDED: Next.js 14 + shadcn/ui + TanStack Query**

**Framework: Next.js 14 App Router** (Keep it!)

```typescript
// app/library/page.tsx
export default async function LibraryPage() {
  const supabase = createServerComponentClient()
  const { data: events } = await supabase
    .from('media_events')
    .select('*')
    .limit(20)
  
  return <LibraryGrid events={events} />
}
```

**UI Components: shadcn/ui**

```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input dialog
```

```typescript
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog"

export function VideoCard({ event }) {
  return (
    <Card>
      <img src={event.thumbnail_url} />
      <Dialog>
        <DialogTrigger asChild>
          <Button>View Details</Button>
        </DialogTrigger>
        <DialogContent>
          {/* Full video details */}
        </DialogContent>
      </Dialog>
    </Card>
  )
}
```

**Why shadcn/ui:**
- ✅ Copy-paste components (you own the code!)
- ✅ Built on Radix UI (accessibility)
- ✅ Tailwind styling (customizable)
- ✅ No runtime overhead
- ✅ Beautiful defaults, warm aesthetic possible

**Data Fetching: TanStack Query (React Query)**

```typescript
import { useQuery } from '@tanstack/react-query'

function LibraryPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['media-events', { page: 1 }],
    queryFn: () => fetch('/api/media-events?page=1').then(r => r.json())
  })
  
  if (isLoading) return <Spinner />
  return <LibraryGrid events={data.items} />
}
```

**Why TanStack Query:**
- ✅ Caching, background refetching
- ✅ Pagination helpers
- ✅ Optimistic updates
- ✅ Loading/error states
- ✅ DevTools

**Forms: React Hook Form + Zod**

```typescript
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const schema = z.object({
  scope: z.enum(['liked', 'favorited', 'both']),
  consent: z.boolean().refine(val => val === true)
})

function UploadForm() {
  const { register, handleSubmit } = useForm({
    resolver: zodResolver(schema)
  })
  
  const onSubmit = (data) => {
    // Upload file
  }
  
  return <form onSubmit={handleSubmit(onSubmit)}>...</form>
}
```

**File Upload: Uppy**

```typescript
import Uppy from '@uppy/core'
import { Dashboard } from '@uppy/react'
import AwsS3 from '@uppy/aws-s3'

const uppy = new Uppy()
  .use(AwsS3, {
    getUploadParameters: async (file) => {
      // Get presigned URL from backend
      const { url, fields } = await getPresignedUrl(file.name)
      return { method: 'POST', url, fields }
    }
  })

<Dashboard uppy={uppy} />
```

**Verdict:** Use **Next.js 14 + shadcn/ui + TanStack Query + React Hook Form + Uppy**.

---

## 12. Analytics & Product Metrics

### Current PRD Plan
- Manual tracking?

### **RECOMMENDED: PostHog**

```typescript
import posthog from 'posthog-js'

posthog.init('phc_...', {
  api_host: 'https://app.posthog.com'
})

// Track events
posthog.capture('upload_started', {
  video_count: 1247,
  scope: 'both'
})

posthog.capture('search_performed', {
  query: 'cooking',
  results_count: 23
})

// User properties
posthog.identify(user.id, {
  email: user.email,
  subscription_tier: 'explorer'
})
```

**Why PostHog:**
- ✅ Open source, self-hostable
- ✅ Event tracking + session replay + feature flags + A/B testing
- ✅ 1M events/month free
- ✅ GDPR compliant
- ✅ Funnels, cohorts, retention analysis
- ✅ SQL access to raw data

**Alternative: Mixpanel**
- More mature
- Better for mobile apps
- More expensive

**Alternative: Amplitude**
- Best-in-class product analytics
- Free tier: 10M events/month
- Steeper learning curve

**Verdict:** Use **PostHog**. It's the best balance of features, cost, and privacy for indie products.

---

## 13. Rate Limiting & DDoS Protection

### Current PRD Plan
- Custom rate limiting

### **RECOMMENDED: Cloudflare (DDoS) + Upstash Rate Limit**

**Cloudflare for DDoS & CDN:**
- ✅ Free tier includes DDoS protection
- ✅ Global CDN for static assets
- ✅ Page Rules for caching
- ✅ WAF (Web Application Firewall)
- ✅ Analytics

**Rate Limiting: Upstash Rate Limit**

```typescript
import { Ratelimit } from "@upstash/ratelimit"
import { Redis } from "@upstash/redis"

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(100, "1 m"), // 100 req/min
  analytics: true,
})

export async function middleware(request: NextRequest) {
  const identifier = request.ip ?? "anonymous"
  const { success } = await ratelimit.limit(identifier)
  
  if (!success) {
    return new Response("Too Many Requests", { status: 429 })
  }
  
  return NextResponse.next()
}
```

**Why Upstash:**
- ✅ Serverless Redis (pay per request)
- ✅ Global edge caching
- ✅ 10,000 requests/day free
- ✅ Works with Vercel Edge Functions

**Alternative: Redis + Custom Middleware**
- More control
- More setup
- Requires managing Redis instance

**Verdict:** Use **Cloudflare Free** for DDoS and **Upstash Rate Limit** for API throttling.

---

## 14. Payment Processing

### Current PRD Plan
- Subscription billing system needed

### **RECOMMENDED: Stripe Billing**

```python
import stripe

stripe.api_key = "sk_..."

# Create customer
customer = stripe.Customer.create(
    email=user.email,
    metadata={"user_id": str(user.id)}
)

# Create subscription
subscription = stripe.Subscription.create(
    customer=customer.id,
    items=[{"price": "price_explorer_monthly"}],
)

# Webhook handling
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    
    event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    
    if event.type == "customer.subscription.deleted":
        # Schedule user data deletion in 30 days
        schedule_data_deletion(event.data.object.customer)
```

**Why Stripe:**
- ✅ Industry standard
- ✅ Handles all subscription complexity (trials, prorations, dunning)
- ✅ PCI compliance handled
- ✅ Great documentation
- ✅ Stripe Billing Portal (customer self-service)
- ✅ Fraud prevention built-in

**Alternative: Paddle**
- Merchant of record (handles sales tax for you)
- Better for SaaS in EU
- Higher fees (5% + payment processing)

**Alternative: LemonSqueezy**
- Newer, simpler than Stripe
- Good for indie hackers
- Merchant of record
- Still maturing

**Verdict:** Use **Stripe Billing**. It's the safe, standard choice.

---

## 15. Infrastructure & Deployment

### Current PRD Plan
- Modal for processing
- Need hosting for API + frontend

### **RECOMMENDED: Vercel (Frontend) + Modal (Processing) + Render/Railway (API)**

**Frontend: Vercel**
- ✅ Zero-config Next.js deployment
- ✅ Global CDN
- ✅ Automatic HTTPS
- ✅ Preview deployments
- ✅ Free hobby tier (generous)
- ✅ Serverless functions for simple APIs

**Processing Jobs: Modal** (Keep it!)
- ✅ Already in your stack
- ✅ Perfect for bursty workloads
- ✅ GPU support if needed
- ✅ Pay per use

**Backend API: Render OR Railway**

**Option A: Render**
```yaml
# render.yaml
services:
  - type: web
    name: attic-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    autoDeploy: true
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: attic-db
          property: connectionString

databases:
  - name: attic-db
    plan: starter  # $7/mo
```

**Why Render:**
- ✅ Simple, Heroku-like experience
- ✅ Automatic deployments from Git
- ✅ Managed PostgreSQL included
- ✅ Free SSL
- ✅ $7/mo for starter API + DB
- ❌ Cold starts on free tier

**Option B: Railway**
- Similar to Render
- Better developer experience
- Slightly more expensive
- $5/mo base + usage

**Alternative: Self-host on Fly.io**
- More control
- Cheaper at scale
- More DevOps work

**Verdict:** Use **Vercel (frontend)** + **Render (API)** + **Modal (jobs)**. Simplest stack with great DX.

---

## 16. Observability & APM

### Current PRD Plan
- Basic logging

### **RECOMMENDED: Datadog OR Highlight.io**

**Option A: Datadog** (If you have budget)
- Full observability suite
- APM, logs, metrics, traces
- Real user monitoring
- $15/host/month minimum
- Overkill for MVP

**Option B: Highlight.io** (RECOMMENDED for MVP)

```typescript
import { H } from 'highlight.run'

H.init('...', {
  tracingOrigins: true,
  networkRecording: { enabled: true }
})

// Automatic error tracking + session replay
```

```python
import highlight_io

H = highlight_io.H("...", instrument_logging=True)

with H.trace("enrich_video"):
    # Automatic performance tracking
    result = enrich_with_apify(urls)
```

**Why Highlight.io:**
- ✅ Session replay (see what users see)
- ✅ Error monitoring
- ✅ Performance monitoring
- ✅ Backend tracing
- ✅ 500 sessions/month free
- ✅ Open source

**Verdict:** Use **Highlight.io** for MVP, upgrade to Datadog if you raise funding.

---

## 17. Testing

### Current PRD Plan
- Not specified

### **RECOMMENDED: Pytest + Playwright**

**Backend Testing: Pytest**

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    return TestClient(app)

def test_upload_endpoint(client):
    response = client.post("/api/uploads", files={"file": ...})
    assert response.status_code == 200
    assert "upload_id" in response.json()
```

**Frontend Testing: Playwright**

```typescript
import { test, expect } from '@playwright/test'

test('can upload TikTok export', async ({ page }) => {
  await page.goto('/upload')
  
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles('test-export.zip')
  
  await page.click('text=Upload')
  await expect(page).toHaveURL(/\/processing\/.*/)
})
```

**Why Playwright:**
- ✅ Cross-browser testing
- ✅ Auto-wait for elements
- ✅ Video recording, screenshots
- ✅ Trace viewer for debugging
- ✅ Better than Cypress for modern apps

**Verdict:** Use **Pytest for backend** and **Playwright for E2E**. Skip unit tests for React components initially.

---

## Summary: Recommended Stack

### **Core Infrastructure**
| Component | Tool | Why | Cost (MVP) |
|-----------|------|-----|-----------|
| **Auth** | Supabase Auth | OAuth, JWT, user management | Free |
| **Database** | Supabase PostgreSQL | Managed Postgres + pgvector | Free |
| **ORM** | SQLAlchemy 2.0 | Python standard, async support | Free |
| **Backend** | FastAPI | Async, fast, great DX | Free |
| **Frontend** | Next.js 14 | React, SSR, app router | Free |
| **UI Components** | shadcn/ui | Copy-paste, customizable | Free |
| **File Storage** | Supabase Storage → R2 | Start simple, scale cheap | Free → $1/mo |
| **Job Queue** | Temporal.io | Multi-step workflows | Free (self-host) |
| **Processing** | Modal | Serverless Python, GPU | Pay per use |

### **Supporting Services**
| Component | Tool | Cost (MVP) |
|-----------|------|-----------|
| **Email** | Resend | Free (3k/mo) |
| **SMS** | Twilio | ~$15 credit |
| **Errors** | Sentry | Free (5k errors/mo) |
| **Logs** | Axiom | Free (500GB/mo) |
| **Analytics** | PostHog | Free (1M events/mo) |
| **Payments** | Stripe | 2.9% + $0.30 |
| **CDN/DDoS** | Cloudflare | Free |
| **Rate Limit** | Upstash | Free (10k req/day) |
| **Monitoring** | Highlight.io | Free (500 sessions/mo) |

### **Hosting**
| Component | Service | Cost (MVP) |
|-----------|---------|-----------|
| **Frontend** | Vercel | Free |
| **Backend API** | Render | $7/mo |
| **Database** | Supabase | Free → $25/mo |
| **Jobs** | Modal | Pay per use (~$20/mo) |

**Total MVP Cost: ~$50-75/month** (mostly Modal usage for processing)

---

## Migration Path

### **Phase 1: MVP (Week 1-2)**
1. Set up Supabase (auth + database)
2. Deploy Next.js to Vercel
3. Deploy FastAPI to Render
4. Connect Modal for processing
5. Add Resend for emails
6. Add Sentry for errors

### **Phase 2: Pre-Launch (Week 3-4)**
7. Add Temporal.io for workflow orchestration
8. Add PostHog for analytics
9. Add Stripe for payments
10. Add Cloudflare for CDN/security

### **Phase 3: Post-Launch Scaling**
11. Migrate to Cloudflare R2 for storage
12. Add Typesense if search UX needs improvement
13. Add Highlight.io for session replay
14. Consider dedicated vector DB (Qdrant) if needed

---

## Key Principles Applied

1. ✅ **Use managed services**: Supabase, Render, Vercel handle ops
2. ✅ **Generous free tiers**: Most services free until you hit scale
3. ✅ **Battle-tested tools**: Stripe, Sentry, Postgres are industry standards
4. ✅ **Migration paths**: Can move from Supabase → self-hosted Postgres later
5. ✅ **Developer experience**: Great docs, active communities
6. ✅ **Security by default**: OAuth, RLS, rate limiting included

**You'll spend more time building features, less time on infrastructure.**