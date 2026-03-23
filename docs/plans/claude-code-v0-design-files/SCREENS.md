# Attic — Screen Inventory

**Last updated:** 2026-03-16
**Source:** REPO_STATUS.md, CURRENT_PLAN.md, TODO.md, CEO_PLAN_REVIEW_2026-03-14.md

---

## Screen Summary

| # | Route | Screen | Status | Priority | Work |
|---|-------|--------|--------|----------|------|
| 1 | `/` | Landing | Placeholder exists | P2 | Redesign |
| 2 | `/login` | Login | Built (Google OAuth) | P4 | Reskin |
| 3 | `/auth/callback` | OAuth callback | Built | — | No UI change |
| 4 | `/upload` | Upload flow | Built (5 sub-steps) | P3 | Reskin |
| 5 | `/processing/[id]` | Processing | Placeholder exists | P3 | Build |
| 6 | `/reveal/[id]` | Reveal | Does not exist | P2 | Build (new) |
| 7 | `/chat` | Chat | Minimal SSE exists | P1 | Rebuild |
| 8 | `/chat/[id]` | Past conversation | Does not exist | P1 | Build (new) |
| 9 | `/settings` | Settings | Placeholder + delete | P4 | Reskin |

---

## User Flows

### Flow 1: First-time user

```
Landing (/) → Login (/login) → Upload (/upload) → Processing (/processing/[id]) → Reveal (/reveal/[id]) → Chat (/chat)
```

This is the full onboarding funnel. Every screen must work. The reveal screen is the emotional hook — the "Wrapped moment" that validates the upload wait.

### Flow 2: Returning user

```
Login (/login) → Chat (/chat)
```

Returning users skip landing, upload, processing, and reveal. Chat is the home screen. From chat they can:
- Start a new conversation
- Browse past conversations (sidebar)
- Navigate to Settings
- Navigate to Upload (for a new export)

### Flow 3: New upload (existing user)

```
Chat (/chat) → Upload (/upload) → Processing (/processing/[id]) → Reveal (/reveal/[id]) → Chat (/chat)
```

---

## Detailed Screen Specs

### 1. Landing page — `/`

**Status:** Placeholder exists
**Work:** Full redesign with brand system
**Data:** Static (no API calls)

**Purpose:** Convert visitors to sign up. First impression of the brand.

**Sections:**
- Hero: Crimson Pro headline ("Remember what you forgot you loved."), subhead in DM Sans, primary CTA
- Social proof / example: Mock reveal stats or screenshot
- How it works: 3 steps (upload → wait → explore)
- Value props: 3-4 cards (search, collections, reveal, privacy)
- Pricing preview (or "free during beta")
- Footer CTA

**Design references:** Readwise.io landing, Perplexity.ai landing, Letterboxd homepage
**Key components:** Hero section, feature cards, step indicator, footer

---

### 2. Login — `/login`

**Status:** Built — Google OAuth via Supabase
**Work:** Reskin with Parchment + Ink palette
**Data:** Supabase Auth

**Existing components:**
- `LoginContent.tsx` — login page layout
- `GoogleSignInButton.tsx` — OAuth trigger
- `AuthError.tsx` — error display

**Design:** Centered card on parchment background. "attic" wordmark in Crimson Pro above the card. Google sign-in button. Minimal — one card, one button. No hero, no marketing copy.

---

### 3. Upload flow — `/upload`

**Status:** Built — full 5-step flow
**Work:** Reskin with Parchment + Ink palette
**Data:** Upload API (`POST /api/uploads/presigned-url`, validation, scope, consent)

**Existing components:**
- `UploadFlow.tsx` — multi-step orchestration
- `ExportGuide.tsx` — TikTok export instructions (collapsible)
- `TikTokUploader.tsx` — Uppy drag-and-drop
- `UploadProgress.tsx` — progress display
- `ScopeSelector.tsx` — liked/favorited scope selection
- `UploadSummary.tsx` — tier usage and estimated time
- `ConsentModal.tsx` — data consent collection
- `UploadError.tsx`, `ValidationError.tsx` — error states

**Sub-steps (in order):**
1. Export guide — how to request your TikTok data
2. File upload — drag-and-drop ZIP
3. Validation — parsing results, error handling
4. Scope selection — liked, favorited, or both
5. Consent — data processing agreement

**Design notes:** Step indicator at top. Each step occupies the same centered card layout. Export guide is collapsible for returning users. The upload zone should feel inviting (not a clinical file picker).

---

### 4. Processing — `/processing/[id]`

**Status:** Placeholder exists
**Work:** Build real progress UI
**Data:** Supabase Realtime (progress updates), pipeline status

**Purpose:** Keep users informed while pipeline runs. Offer notification opt-in for long waits.

**Components to build:**
- Progress indicator (step-by-step or percentage)
- Estimated time remaining
- Step descriptions ("parsing your export...", "enriching metadata...", "generating embeddings...")
- Notification opt-in (email via Resend): "We'll email you when it's ready"
- "Leave and come back" reassurance

**Design references:** Vercel deploy log (step-by-step progress), Spotify Wrapped loading screen (anticipation building)
**Emotional tone:** Anticipation, not anxiety. "We're reading through your saves" not "Processing upload..."

---

### 5. Reveal — `/reveal/[id]`  ← NEW

**Status:** Does not exist in codebase
**Work:** Build from scratch
**Data:** Chat API summary endpoint (or first agent query)

**Purpose:** The Wrapped moment. Emotional hook between processing and chat. Shows aggregate stats about the user's data before they start chatting.

**Components to build:**
- Full-screen stat cards (scrollable or animated sequence):
  - Total saves count
  - Date range of activity
  - Top topics/categories
  - Number of restaurants/books/places found
  - Top creators
  - "Most saved" highlight
- Transition CTA → "Start exploring" → navigates to `/chat`

**Design references:** Spotify Wrapped 2024/2025, Apple Music Replay
**Emotional tone:** Delight and surprise. "You saved 847 TikToks across 23 topics. Let's see what's in there."

**Typography:** Crimson Pro for stat numbers and editorial commentary. DM Sans for labels and CTA. Cinnamon accent for stat numbers — this is one of the few places the accent color appears in the product.

---

### 6. Chat — `/chat`  ← REBUILD (P1)

**Status:** Minimal SSE streaming exists (plain text bubbles)
**Work:** Full rebuild — this is the product
**Data:** Chat SSE API (`POST /api/chat`), agent tools (query_items, classify, analyze_visual, resolve_entity)

**Existing components (to replace):**
- `chat/page.tsx` — basic message list + textarea + SSE handling

**Components to build:**

**Layout:**
- Conversation sidebar (left, collapsible on mobile)
- Message area (center, scrollable)
- Input area (bottom, fixed)

**Message types:**
- User message bubble (soft black #2C2926, right-aligned)
- Assistant text response (white card, left-aligned)
- Assistant entity card (restaurant, book, movie, music — structured)
- Assistant thumbnail grid (3-4 col grid of TikTok thumbnails)
- Assistant collection preview (named collection with thumbnail strip)
- Streaming indicator (typing/thinking state)
- Error message

**Entity card variants:**
- Restaurant: thumbnail, name, neighborhood, rating, save count, "directions" link
- Book: cover image, title, author, "Goodreads" link
- Movie/TV: poster, title, year, "TMDB" link
- Music: album art, track/artist, "Spotify" link
- Generic: thumbnail, title, description, source link

**Other components:**
- Empty state with suggested prompts (based on user's actual data)
- Suggested follow-up chips after assistant response
- Conversation history sidebar (list of past chats with timestamps)
- "New chat" button

**Design references:**
- Perplexity.ai — inline structured answers mixed with prose
- Claude.ai — conversational warmth, artifact-style inline renders
- Apple Photos — thumbnail grid as primary visual
- ChatGPT — suggested prompts, conversation sidebar

---

### 7. Past conversation — `/chat/[id]`  ← NEW

**Status:** Does not exist
**Work:** Build (shares all components with `/chat`, just loads existing conversation)
**Data:** Chat API with `conversation_id` parameter, DB messages table

**Same layout as `/chat` but pre-populated with historical messages. The conversation sidebar highlights the active conversation.**

---

### 8. Settings — `/settings`

**Status:** Placeholder with delete account modal
**Work:** Reskin with Parchment + Ink palette
**Data:** User API, Supabase Auth

**Existing components:**
- Settings page with delete account modal

**Sections:**
- Profile info (email, account created date)
- Upload history (list of past uploads with date, item count, status)
- Notification preferences (email opt-in/out)
- Danger zone: delete account (with confirmation modal)
- (Future: subscription status, Stripe Billing Portal link)

---

## Mockup Priority Order

| Priority | Screen | Reason | Estimated effort |
|----------|--------|--------|------------------|
| P1 | Chat | 80% of product value. Most components. | High — many sub-components |
| P2 | Reveal | Emotional hook, viral potential. Novel. | Medium — stat cards + animation |
| P2 | Landing | First impression, conversion. | Medium — marketing layout |
| P3 | Upload flow | Already built, just reskin. | Low — apply new palette |
| P3 | Processing | Simple progress UI. | Low — progress + copy |
| P4 | Login | One card, one button. | Trivial |
| P4 | Settings | Functional, low-stakes. | Low — form layout |

---

## Files

This document is the screen-level planning reference. It maps to:
- `docs/BRAND.md` — visual design spec (colors, typography, components)
- `docs/BRAND_ATTRIBUTES.md` — brand strategy, voice, users
- `src/frontend/src/lib/design-tokens.ts` — code-level design tokens
- `docs/CEO_PLAN_REVIEW_2026-03-14.md` — architecture decisions
- `docs/CURRENT_PLAN.md` — implementation task checklist
