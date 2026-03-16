# Auth & Login Flow — Expansion Plan

**Created:** 2026-03-16
**Mode:** SCOPE EXPANSION
**Status:** Eng review complete
**Branch:** `s0shaheen/review-run-guide`

---

## Problem Statement

`dev-setup.sh` creates a test user (`test@attic.dev`) in the database, but there is **no way to actually log in locally**. The login page only offers Google OAuth, which requires external Google Cloud configuration. This blocks all local development and automated QA testing of authenticated flows.

## Decisions Made

### CEO Review Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Local auth method | Supabase email/password | Uses built-in auth, zero custom code, automatable by /qa |
| 2 | Auth testing strategy | Email/password form is automatable | Headless browsers fill form, same flow as real users |
| 3 | Email/password scope | Everywhere (dev + prod) | One auth UX, no feature flags, enables /qa against all envs |
| 4 | Seed script safety | Environment check | Refuse to run unless DB URL contains localhost/127.0.0.1 |
| 5 | Logout UX | Full settings page | Email, tier, sign out, delete account. Extensible. |
| 6 | Post-login redirect | ?next= param through login flow | Standard UX, prevents losing context on redirect |
| 7 | Frontend tests | Vitest + React Testing Library now | Login is security-critical, closes TODO 4 |
| 8 | Auth observability | PostHog events | Auth funnel data is high-value for pre-launch |
| 9 | Password reset | Build now | Standard auth expectation, Supabase handles heavy lifting |
| 10 | Email verification | Build now | Production requirement, local dev keeps it disabled |
| 11 | Account deletion | Build now (settings page) | Backend GDPR endpoint already exists, just needs UI wiring |

### Eng Review Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| E1 | Auth state management | AuthProvider context | Fetch session once, share via context, onAuthStateChange for reactive updates. Best-practice pattern for production Next.js + Supabase. |
| E2 | Header/navigation | Shared AppHeader component | Persistent app shell with logo, nav, UserMenu dropdown. Reused by chat/upload/settings. Extensible for future nav items. |
| E3 | PostHog integration | Full setup (install SDK, provider, env var) | PostHog wasn't in frontend at all. One-time setup enables all future analytics. |
| E4 | ?next= security | Sanitize to relative paths only | Prevents open redirect vulnerability (OWASP A01). Reject URLs containing :// |
| E5 | Rate limit UX | Detect Supabase rate limit errors, show countdown | 10 lines, real UX gap for production users |
| E6 | Root redirect | Already exists (app/page.tsx) | Task 7 eliminated — just verify it still works |
| E7 | CLAUDE.md update | Update Auth stack row | Keep canonical reference accurate |

## Architecture

### Component Hierarchy

```
  layout.tsx
    └── Providers (existing)
         ├── QueryClientProvider (existing)
         └── AuthProvider (NEW — lib/auth-context.tsx)
              │
              │  Fetches session ONCE on mount
              │  Listens to onAuthStateChange
              │  Re-renders children on login/logout
              │
              └── children
                   ├── DevBanner (NEW, conditional on NEXT_PUBLIC_ENVIRONMENT)
                   └── page content
                        ├── / (page.tsx) ── existing, redirect to /login or /chat
                        ├── /login ── email/pass + Google OAuth + dev quick-login
                        │    └── ?next= param awareness (sanitized, relative only)
                        ├── /auth/callback ── existing, reads ?next=
                        ├── /auth/verify ── NEW, "check your email" after sign-up
                        ├── /auth/reset-password ── NEW, set new password
                        ├── /chat ── existing, refactored with AppHeader
                        │    └── AppHeader (NEW — components/app-header.tsx)
                        │         ├── Logo → /chat
                        │         ├── Nav: Chat | Upload
                        │         ├── [page-specific actions slot]
                        │         └── UserMenu dropdown
                        │              ├── New Chat (chat-specific action)
                        │              ├── Settings → /settings
                        │              └── Sign Out
                        ├── /upload ── existing, refactored with AppHeader
                        └── /settings ── NEW
                             ├── User info (email, tier from useAuth())
                             ├── Sign Out → signOut() + redirect
                             └── Delete Account → confirm dialog → DELETE /api/user/me
```

### Auth Flow Diagram

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    BROWSER (Next.js)                             │
  │                                                                  │
  │  / ──middleware──▶ session? ──yes──▶ /chat                       │
  │                    │no                                           │
  │                    ▼                                             │
  │                  /login?next={sanitized_path}                    │
  │                    ├── "Continue with Google" (OAuth)             │
  │                    │    └── redirectTo includes ?next= param     │
  │                    ├── Email/Password form (Supabase Auth)       │
  │                    │    └── signInWithPassword → router.push(next)│
  │                    └── [dev] Quick Login (auto-filled creds)     │
  │                                                                  │
  │  AuthProvider (context) ← onAuthStateChange                      │
  │    └── useAuth() consumed by: AppHeader, Settings, pages         │
  │                                                                  │
  │  PostHogProvider ← captures auth events                          │
  └──────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                  LOCAL DEV SEED                                  │
  │                                                                  │
  │  seed_local.py                                                   │
  │    ├── Guard: refuse if DB URL is not localhost/127.0.0.1        │
  │    ├── Supabase Admin API: POST /auth/v1/admin/users             │
  │    │   (createUser with email + password, idempotent)            │
  │    ├── Insert into public.users (app table, upsert)              │
  │    ├── Insert media_events + embeddings                          │
  │    └── Print: "Login with test@attic.dev / testtest123"          │
  └──────────────────────────────────────────────────────────────────┘
```

### Data Flow — Email/Password Login (Four Paths)

```
  INPUT (email+pass)──▶ VALIDATION ──▶ SUPABASE AUTH ──▶ SESSION ──▶ REDIRECT
       │                    │              │                │           │
       ▼                    ▼              ▼                ▼           ▼
  [nil email?]         [empty pass?]  [wrong creds?]   [cookie       [?next= has
   → form error]       → form error]  → 400 from        write fail?]  ://? → reject
  [nil pass?]          [too short?]    Supabase          → catch,      → use /chat]
   → form error]       → min 6 char]  → show error]      show error]
                                       [rate limited?]
                                        → "Too many
                                          attempts" msg]
```

### Account Deletion Flow

```
  /settings → "Delete Account" button
    → Confirmation dialog ("Type DELETE to confirm")
    → User types "DELETE" + clicks confirm
    → Frontend: DELETE /api/user/me (with Bearer token)
    → Backend: UserDeletionService.delete_user_account()
        ├── Delete storage files (non-blocking)
        ├── Delete from Supabase Auth (required)
        └── Send confirmation email (non-blocking)
    → Frontend: on 202 success → supabase.auth.signOut()
    → AuthProvider detects state change → all components update
    → router.push('/login?message=account_deleted')
```

## Error & Rescue Registry

```
  METHOD                    | EXCEPTION              | RESCUED? | USER SEES
  --------------------------|------------------------|----------|----------------------------
  signInWithPassword        | AuthError(wrong pw)    | ✅       | "Invalid credentials"
  signInWithPassword        | AuthError(no user)     | ✅       | "Invalid credentials"
  signInWithPassword        | AuthError(rate limit)  | ✅       | "Too many attempts. Try again in 60s"
  signInWithPassword        | Network error          | ✅       | "Can't reach server"
  signUp                    | AuthError(exists)      | ✅       | "Already registered"
  signUp                    | AuthError(short pw)    | ✅       | "Password too short"
  signOut                   | Network error          | ✅       | Clear local + redirect
  resetPasswordForEmail     | AuthError              | ✅       | Error message on form
  resetPasswordForEmail     | Network error          | ✅       | "Can't reach server"
  DELETE /api/user/me       | 500                    | ✅       | "Deletion failed" on settings
  DELETE /api/user/me       | Network error          | ✅       | "Can't reach server"
  ?next= param              | External URL (://)     | ✅       | Silently use /chat instead
  seed: Admin API           | ConnectError           | ✅       | "Supabase not running"
  seed: Admin API           | 422 (exists)           | ✅       | Skip (idempotent)
  seed: env check           | Non-local DB           | ✅       | "Refusing to seed prod"
```

## Failure Modes Registry

```
  CODEPATH          | FAILURE MODE        | RESCUED? | TEST? | USER SEES?       | LOGGED?
  ------------------|---------------------|----------|-------|------------------|--------
  Login form        | Wrong creds         | ✅       | ✅    | Error message    | PostHog
  Login form        | Network failure     | ✅       | ✅    | Error message    | PostHog
  Login form        | Double-click        | ✅       | ✅    | Button disabled  | N/A
  Login form        | Rate limited        | ✅       | ✅    | Countdown msg    | PostHog
  Sign up           | Email exists        | ✅       | ✅    | Error message    | PostHog
  Sign up           | Pwd too short       | ✅       | ✅    | Error message    | PostHog
  Password reset    | Expired link        | ✅       | Nice  | Error on page    | PostHog
  Middleware        | Supabase down       | ✅       | No    | Redirect login   | No
  Settings: delete  | API 500             | ✅       | ✅    | Error message    | PostHog
  Settings: delete  | User cancels        | ✅       | ✅    | No action        | N/A
  ?next= redirect   | External URL        | ✅       | ✅    | Sanitized to /chat| No
  Seed script       | Non-local DB        | ✅       | ✅    | Refuses to run   | Stderr
  Seed script       | User exists         | ✅       | No    | Skips (silent)   | Stdout
  AuthProvider      | getSession fails    | ✅       | ✅    | Loading state    | No
  PostHog           | SDK fails to load   | ✅       | No    | Nothing (async)  | Silent (OK)
```

No critical gaps (no row with RESCUED=N AND TEST=N AND SILENT).

## Security Checklist

- [x] No custom crypto — Supabase handles bcrypt, sessions, PKCE
- [x] service_role key only in seed script, never in frontend/backend
- [x] Seed script refuses to run against production databases
- [x] RLS policies unaffected (same JWT structure for email/password)
- [x] No new API endpoints (all Supabase client-side auth)
- [x] Rate limiting on login handled by Supabase (built-in)
- [x] PostHog events contain no PII (event names only, no emails)
- [x] ?next= parameter sanitized to relative paths only (open redirect prevention)
- [ ] Email verification enabled in production Supabase Dashboard
- [ ] GDPR delete confirmation requires typed confirmation ("DELETE")

## Task List (Ordered, Updated After Eng Review)

| # | Task | Files | Effort | Notes |
|---|------|-------|--------|-------|
| 0 | AuthProvider context | `lib/auth-context.tsx`, `components/providers.tsx` | S | Foundation — all subsequent tasks consume useAuth(). Includes onAuthStateChange listener. |
| 1 | Vitest + React Testing Library setup | `vitest.config.ts`, `package.json`, test utils | S | Closes TODO 4. |
| 2 | PostHog frontend setup | `package.json`, `components/providers.tsx`, `.env` files | S | Install posthog-js, add PostHogProvider, NEXT_PUBLIC_POSTHOG_KEY env var. One-time cost. |
| 3 | seed_local.py → Supabase Admin API | `scripts/seed_local.py` | S | Replace raw auth.users SQL with Admin API createUser(). Add env safety check. Idempotent. |
| 4 | AppHeader + UserMenu component | `components/app-header.tsx` | M | Shared header: logo, nav (Chat, Upload), actions slot, UserMenu dropdown (Settings, Sign Out). |
| 5 | Email/password login form | `src/frontend/src/app/login/page.tsx` | M | Email+password fields, sign-in/sign-up toggle, error handling (including rate limit detection), dev quick login, ?next= awareness. PostHog events. |
| 6 | Password reset flow | `login/page.tsx`, new `auth/reset-password/page.tsx` | S | "Forgot password?" link, resetPasswordForEmail(), callback page for new password entry. |
| 7 | Email verification screen | New `auth/verify/page.tsx` | S | "Check your email" screen after production sign-up. |
| 8 | Middleware: protect /upload + ?next= param + sanitize | `lib/supabase/middleware.ts` | S | Extend protection to /upload and /settings. Pass ?next= (relative paths only, reject ://). |
| 9 | Settings page | New `src/frontend/src/app/settings/page.tsx` | M | User email, subscription tier, Sign Out, Delete Account (typed confirm dialog → DELETE /api/user/me → signOut → redirect). PostHog events. |
| 10 | Refactor chat + upload pages | `chat/page.tsx`, `upload/page.tsx` | S | Replace inline auth + header with useAuth() + AppHeader. Pass page-specific actions as props. |
| 11 | Welcome message on first chat | `chat/page.tsx` | S | Check for zero conversations, show assistant welcome message. |
| 12 | Dev mode banner | `layout.tsx` or wrapper | S | Subtle top banner when NEXT_PUBLIC_ENVIRONMENT=development. |
| 13 | Dead code cleanup | `src/backend/app/services/agent.py` | S | Remove old SYSTEM_PROMPT constant (lines 63-97). |
| 14 | Update dev-setup.sh + CLAUDE.md | `scripts/dev-setup.sh`, `CLAUDE.md` | S | Update instructions for email/password login. Update Auth stack row. |
| 15 | Auth flow Vitest tests | `__tests__/` | M | 12 must-have tests: login form (4), sign-up (2), logout (1), deletion (2), dev banner (1), middleware (1), AuthProvider (1). Plus ?next= sanitization test. |

**Estimated total: ~8-10 hours** (revised up from 6-8 due to AuthProvider, PostHog setup, AppHeader extraction)

## NOT in Scope

- Apple OAuth (P3 in TODO.md)
- Multi-session management (Supabase handles)
- Connected accounts UI in settings
- Notification preferences in settings
- Data export from settings
- CI E2E test pipeline (Vitest component tests only)
- Conversation history sidebar
- Profile photo upload

## What Already Exists (Reuse)

| Sub-problem | Existing code | Reused? |
|---|---|---|
| JWT validation | `auth.py` — works identically for email/password | ✅ |
| Account deletion backend | `user_deletion.py` + `DELETE /api/user/me` | ✅ |
| Supabase client/server/middleware | `lib/supabase/` (3 files) | ✅ |
| Session refresh | `middleware.ts → updateSession()` | ✅ |
| Root page redirect | `app/page.tsx` (already exists!) | ✅ Task eliminated |
| TanStack Query provider | `components/providers.tsx` | ✅ AuthProvider + PostHog added here |
| Test fixture | `user_bob.json` + seed data | ✅ |

## Dream State Delta

```
  THIS PLAN DELIVERS:                       REMAINING TO 12-MONTH IDEAL:
  ✅ Local dev login works                  ○ Apple OAuth
  ✅ Email/password in production           ○ Full onboarding wizard
  ✅ /qa can test authenticated flows       ○ CI E2E test pipeline
  ✅ Logout exists (settings page)          ○ Conversation history sidebar
  ✅ Full settings page (extensible)        ○ Profile photo upload
  ✅ Middleware protects all auth routes     ○ 2FA / passkeys
  ✅ PostHog auth funnel tracking           ○ Branded email templates (TODO 7)
  ✅ Frontend test infra (Vitest)
  ✅ Seed script uses real Supabase auth
  ✅ Password reset flow
  ✅ Email verification (production)
  ✅ Account deletion from settings
  ✅ Welcome message on first chat
  ✅ Dev mode banner + auto-fill login
  ✅ Shared AppHeader + UserMenu
  ✅ AuthProvider context (reactive auth)
  ✅ Rate limit UX feedback
  ✅ Open redirect prevention
  ✅ Dead code cleanup
```

## Supabase Dashboard Configuration Required

### Local (Supabase CLI)
- Email auth provider: enabled by default
- Email confirmation: disabled by default (good for dev)
- No changes needed

### Production
- Enable "Email" auth provider (if not already)
- Enable email confirmation
- Configure email templates (optional, Supabase defaults work — see TODO 7)
- Ensure Google OAuth remains configured

## Rollback Plan

1. Revert frontend changes (git revert)
2. Disable email provider in Supabase Dashboard (production)
3. Google OAuth continues working throughout — no breaking change
4. Reversibility: 5/5

## Implementation Notes (from Eng Review)

### Account deletion frontend flow
After `DELETE /api/user/me` returns 202, the user's session is invalidated server-side (Supabase Auth user deleted). Frontend must explicitly call `supabase.auth.signOut()` to clear local session, then redirect to `/login?message=account_deleted`.

### ?next= through OAuth flow
Login page passes ?next= to the OAuth redirectTo URL:
```
redirectTo: `${origin}/auth/callback?next=${encodeURIComponent(sanitizedNext)}`
```
The callback route already reads `searchParams.get("next")`.

### Diagrams to add in code
- `lib/auth-context.tsx` — comment showing Provider → useAuth() → components data flow
- `components/app-header.tsx` — comment showing layout structure (logo | nav | actions | user-menu)
