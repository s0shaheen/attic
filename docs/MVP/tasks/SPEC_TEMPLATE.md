# Task X.Y: Task Name

## 0) Outcome

What user-visible capability exists when done? Be specific about what the user can do or see after this task is complete.

## 1) Scope

### In-scope
- [ ] Atomic requirement 1 (independently verifiable)
- [ ] Atomic requirement 2

### Out-of-scope / Non-goals
- Explicitly excluded functionality
- Items deferred to future tasks

## 2) System context

### Components touched
- **Next.js route(s)**: `app/route/page.tsx` (if applicable)
- **FastAPI endpoint(s)**: `POST /api/endpoint` (if applicable)
- **DB tables/columns**: `table_name.column` (if applicable)
- **Step Functions state**: State name (if applicable)
- **Lambda function(s)**: `function-name` (if applicable)
- **Third parties**: Apify, OpenAI, Stripe, etc. (if applicable)

### Invariants (must always be true)
- System property that must hold before, during, and after this task
- Example: "All media_events must have a valid user_id"

## 3) API contracts (authoritative)

### Request/Response

```python
# Python (Pydantic) - if backend changes
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class ExampleRequest(BaseModel):
    field: str = Field(..., description="Description")
    optional_field: int | None = None

class ExampleResponse(BaseModel):
    id: UUID
    created_at: datetime
```

```typescript
// TypeScript (Zod) - if frontend changes
import { z } from 'zod';

export const exampleSchema = z.object({
  field: z.string(),
  optionalField: z.number().optional(),
});

export type ExampleType = z.infer<typeof exampleSchema>;
```

### Status codes
- `200 OK` - Success response
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Missing/invalid auth
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Unexpected error

### Pagination rules
- Default page size: 20
- Max page size: 100
- Cursor-based or offset-based (specify)

### Auth requirements
- Required: Supabase JWT
- user_id derived from token, never from client

## 4) Data model changes

### Migrations (Alembic)
```python
# Describe migration steps
# alembic revision --autogenerate -m "X.Y: description"
```

### Indexes
- Index name and columns (if adding)

### RLS policy updates
```sql
-- Example RLS policy
CREATE POLICY "policy_name" ON table_name
  FOR SELECT USING (auth.uid() = user_id);
```

### Backfill strategy (if needed)
- How to populate data for existing records

## 5) Workflow & state machine (if applicable)

### States
- State 1: Description
- State 2: Description

### Transitions
- State 1 → State 2: On event/condition

### Retry policy + timeouts
- Max retries: N
- Backoff: exponential
- Timeout: X seconds

### Idempotency strategy
- How the operation is safe under retries
- Deterministic IDs, upserts, etc.

### Failure modes + user-facing behavior
- Failure scenario: What user sees

## 6) Implementation plan (ordered)

1. Create data contracts (Pydantic models, Zod schemas)
2. Add database migration (if needed)
3. Implement core logic
4. Add API endpoint (if needed)
5. Add frontend component (if needed)
6. Write unit tests
7. Write integration tests
8. Verify all checks pass

## 7) Observability & analytics

### Logs (required fields)
- `user_id`, `upload_id`, `correlation_id`
- Step-specific: `step_name`, `attempt`, `duration_ms`
- Cost tracking: `vendor`, `cost_usd`

### Metrics (latency, throughput, cost)
- Metric name and what it measures

### Sentry tags/breadcrumbs
- Tags: `task_id`, `user_tier`
- Breadcrumbs: Key operations

### PostHog events (name + properties)
- Event name: `{action}_{resource}`
- Properties: `{ resource_id, user_tier, ... }`

## 8) Security & privacy checklist

- [ ] Data minimization checks (only necessary fields)
- [ ] Secrets handling (no hardcoded secrets, use env vars)
- [ ] RLS verification (policies tested)
- [ ] Third-party payload review (minimal data sent)
- [ ] PII-safe logging (no tokens, emails, raw URLs in logs)
- [ ] Server-side auth (JWT validation, user_id from token)
- [ ] Input validation (all endpoints validated)

## 9) Test plan

### Unit tests
- [ ] `test_{function}_{scenario}_{expected}` - Description
- [ ] `test_{function}_{edge_case}` - Description

### Integration tests
- [ ] `test_{endpoint}_{scenario}` - Description
- [ ] `test_{feature}_with_{dependency}` - Description

### E2E (Playwright) - if UI changes
- [ ] User can complete flow from start to finish
- [ ] Error states display correctly

## 10) Acceptance criteria (binary)

- [ ] Criterion 1: Specific, measurable, binary (yes/no)
- [ ] Criterion 2: Another specific criterion
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Linting passes (ruff/eslint)
- [ ] Type checking passes

## 11) Rollout

### Feature flags
- Flag name (if applicable), or "None"

### Backward compatibility
- Breaking changes (if any), migration path

### Migration order
- Order of operations for safe deployment

### Rollback plan
- Steps to revert if issues found

---

## Progress Tracking

**Status**: NOT_STARTED | IN_PROGRESS | BLOCKED | DONE
**Last Updated**: YYYY-MM-DD
**Merged**: No | Yes (YYYY-MM-DD) | Conflict
**Branch**: feature/{epic}-{task}-{short-name} | Deleted (merged via PR #123)

### Completed
- {Nothing yet}

### Remaining
- All acceptance criteria above

### Blocked By
- {Nothing, or specific blockers}

### Implementation Notes
- {Filled during implementation}
