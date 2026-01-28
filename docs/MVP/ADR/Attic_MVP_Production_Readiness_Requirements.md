# ADR-0002: Define “Production-Ready MVP” Ship Gate for Attic

## Status
Accepted — 2026-01-25

## Context
Attic’s MVP is an end-user product that ingests personal social-media exports and runs an asynchronous enrichment pipeline (parsing → metadata → AI/vision/transcription → search). This creates predictable production risks:

- **Security risk:** multi-tenant user data access must be correctly isolated across DB + API.
- **Privacy risk:** we handle sensitive user exports and must enforce minimization + deletion guarantees.
- **Reliability risk:** async pipelines and third-party calls must be retry-safe (no duplicates, no inconsistent states).
- **Operational risk:** without observability and guardrails, failures are undiagnosable and costs can spike.
- **User trust risk:** unclear AI provenance/confidence, inconsistent UX states, and silent failures reduce trust quickly.

Prior docs described functionality and some NFRs, but the bar for “prod-ready” was implicit and not fully enforced by engineering work items.

## Decision
We are adding an explicit **Production-Ready MVP Ship Gate** to the PRD and implementing it via new/updated Epics/Tasks in the Dev Guide.

This ship gate defines the minimum conditions for an MVP to be considered “production-ready” (safe to onboard real users) across these dimensions:

1) **Security**
- Server-side auth boundary enforcement (no “trust the client”)
- Verified, enforced multi-tenant isolation via **RLS on all user-owned tables**
- Rate limiting for abuse and auth-sensitive routes
- Least-privilege secrets handling and environment separation

2) **Privacy**
- Strict data minimization: parse **only whitelisted export files**
- Deterministic lifecycle: **raw ZIP deleted immediately after parsing** (including failure paths)
- Automated retention and deletion policies:
  - delete-on-request within 24h
  - auto-deletion after subscription end + retention window (if applicable)
- Third-party data sharing constrained to disclosed fields (no unintended identifiers)

3) **Reliability**
- Temporal workflow activities are **idempotent under retries**
- Dedupe/upsert semantics prevent duplicate media events and double-billing of costs
- Partial failure is first-class (clear user-visible status + consistent audit trail)

4) **Performance**
- Meet MVP NFR targets for API/search responsiveness and realistic processing throughput
- Guard against regressions with baseline tests and monitoring

5) **Observability / Operability**
- Correlation IDs across frontend → API → workflow → compute
- Structured logs + error tracking + workflow traceability
- Alerts/dashboards for failures, latency, and cost spikes
- Kill switches / degradation controls for expensive steps

6) **Release Discipline**
- CI gates (lint/test/build)
- Staging smoke tests
- Rollback plan + minimal incident runbooks

## Why this makes the MVP “Production-Ready”
Production-ready does **not** mean “no bugs.” It means the product can safely serve real users with:
- **Minimized risk:** enforced security + privacy constraints and transparent data handling
- **Predictable behavior under failure:** retries don’t corrupt state; partial failures are coherent
- **Operability:** issues are diagnosable, alertable, and reversible
- **Scalable foundation:** the system’s boundaries (auth, lifecycle, workflows, cost controls) are stable enough to extend without re-architecting

In other words: the ship gate converts “intent” (requirements) into **enforced mechanisms + verification** (tasks, tests, and operational controls).

## Implementation Notes (Dev Guide alignment)
We will implement the ship gate through a cross-cutting “Production Readiness & Guardrails” epic plus edits to existing epics where needed. Work includes:
- RLS hardening + regression tests
- Auth boundary tests (positive + negative access control cases)
- Data lifecycle enforcement jobs (retention/delete) + audit logging
- Idempotency/dedupe framework for Temporal activities
- Cost and quota enforcement + kill switches
- Performance baselines + load tests (MVP-appropriate)
- Observability conventions (IDs, logs, alerts, dashboards)
- Staging + release checklist + rollback playbook

## Alternatives Considered
1) **Ship features first, harden later**
- Rejected: highest likelihood of data leak, uncontrolled cost, and untraceable failures.

2) **Rely only on vendor defaults (Supabase, Temporal, Modal)**
- Rejected: defaults reduce work but don’t guarantee correct boundaries; misconfiguration risk remains.

3) **Build fewer guardrails and accept manual ops**
- Rejected: doesn’t scale even to a small cohort; debugging async pipelines manually is a time sink.

## Consequences
### Positive
- Clear, repeatable definition of “prod-ready”
- Reduced risk of cross-user data exposure and privacy violations
- Less fragile pipeline behavior under retries
- Faster debugging and safer iteration cycles
- Predictable cost and abuse controls

### Negative / Tradeoffs
- More upfront engineering work and tests
- Additional operational surface area (alerts, dashboards, scheduled jobs)
- Some MVP velocity is traded for safety and correctness

## Rollout / Validation
Minimum validation before inviting external users:
- RLS verification suite passes; manual adversarial checks performed
- ZIP deletion verified in success + failure paths
- Delete-on-request and retention workflows tested end-to-end
- Idempotency tests demonstrate safe retry behavior
- Basic load/perf checks meet NFR targets
- Observability + alerting confirmed on staging
- Release checklist completed; rollback plan documented

## References
- Attic MVP PRD v1.2.0 — Production Readiness (MVP Ship Gate)
- Attic MVP Dev Guide v1.2.0 — Epic: Production Readiness & Guardrails
