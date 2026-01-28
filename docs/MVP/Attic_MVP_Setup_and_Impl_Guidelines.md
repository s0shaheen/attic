# Attic: Claude Code Implementation Guide

## Overview

This guide enables you to implement Attic using Claude Code with:
- **Batch processing**: Generate specs, validate, and implement via slash commands
- **Intelligent sequencing**: Claude determines task order and parallelization
- **Spec-as-source-of-truth**: Each task has one spec file tracking all state
- **Context isolation**: Subagents work in clean contexts to avoid bloat

---

## Part 1: Manual Setup (Before Starting Claude Code)

### 1.1 External Service Accounts

Create accounts and gather credentials for:

| Service | What You Need | Notes |
|---------|---------------|-------|
| **Supabase** | Project URL, anon key, service role key | Enable pgvector extension in SQL editor |
| **Google Cloud** | OAuth 2.0 Client ID/Secret | For Supabase Auth Google provider |
| **AWS** | Access Key, Secret Key, Region | IAM user with Step Functions/Lambda/SQS/S3/CloudWatch permissions |
| **Stripe** | Secret key, Webhook secret, Price IDs | Create products for Free/Explorer/Expert/Pioneer |
| **OpenAI** | API key | With billing enabled |
| **Apify** | API token | Subscribe to Clockworks TikTok scraper |
| **Resend** | API key | Verify sending domain |
| **Sentry** | DSN (Python), DSN (JavaScript) | Create two projects |
| **PostHog** | API key, Host URL | Create project |

### 1.2 Local Tools

```bash
# Required tools
brew install python@3.12 node@20 docker docker-compose awscli supabase/tap/supabase

# AWS SAM for local Lambda testing
brew install aws-sam-cli

# Verify
python3 --version  # 3.12+
node --version     # 20+
docker --version
supabase --version
sam --version
```

### 1.3 Supabase Configuration (Web Console)

1. **Create Project** at supabase.com
2. **Enable Extensions** (SQL Editor):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
3. **Authentication → Providers**: Enable Google, add OAuth credentials
4. **Storage**: Create buckets `uploads` (500MB limit) and `temp-media`

### 1.4 Environment Files

Create `.env.local` in your project root (gitignored):

```bash
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# OpenAI
OPENAI_API_KEY=sk-...

# Apify
APIFY_API_TOKEN=apify_api_...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_EXPLORER=price_...
STRIPE_PRICE_EXPERT=price_...
STRIPE_PRICE_PIONEER=price_...

# Resend
RESEND_API_KEY=re_...

# Sentry
SENTRY_DSN_BACKEND=https://...@sentry.io/...
SENTRY_DSN_FRONTEND=https://...@sentry.io/...

# PostHog
POSTHOG_API_KEY=phc_...
POSTHOG_HOST=https://app.posthog.com
```

### 1.5 Claude Code Permissions

When you first run Claude Code, allow these permissions:
- File read/write in project directory
- Bash command execution
- Network access for package installation

---

## Part 2: Project Structure Changes

Add these directories to your existing structure:

```
attic/
├── .claude/
│   ├── agents/                    # ADD: Subagent definitions
│   │   ├── spec-writer.md
│   │   ├── implementer.md
│   │   └── tester.md
│   ├── commands/                  # EXISTS: Slash commands
│   │   ├── generate-specs.md      # ADD
│   │   ├── validate-specs.md      # ADD
│   │   ├── implement-backlog.md   # ADD
│   │   └── run-task-tests.md      # ADD
│   ├── skills/                    # ADD: Domain knowledge
│   │   ├── supabase-patterns/
│   │   │   └── SKILL.md
│   │   └── lambda-patterns/
│   │       └── SKILL.md
│   ├── settings.json              # ADD: Hooks config (git tracked)
│   └── settings.local.json        # EXISTS (gitignored)
├── CLAUDE.md                      # UPDATE (see Part 3)
├── docs/
│   └── MVP/
│       └── tasks/
│           ├── specs/             # ADD: Task spec files
│           │   └── .gitkeep
│           ├── Attic_MVP_Dev_Guide_v1.3.0.md  # UPDATE (add status tracking)
│           └── TASK_SPEC_TEMPLATE.md          # EXISTS
└── scripts/
    └── hooks/                     # ADD: Hook scripts
        ├── post-edit-lint.sh
        └── post-test-report.sh
```

---

## Part 3: Updated CLAUDE.md

Replace your existing CLAUDE.md with this enhanced version:

```markdown
# CLAUDE.md

## What is Attic?

Personal analytics platform for TikTok data. Users upload their TikTok data export ZIP, and Attic enriches each video with metadata, visual analysis, and semantic tagging.

## Stack

| Layer | Technologies |
|-------|--------------|
| **Auth** | Supabase Auth (Google OAuth) |
| **Database** | Supabase PostgreSQL + pgvector, SQLAlchemy 2.0, Alembic |
| **Backend** | Python 3.12, FastAPI |
| **Frontend** | Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Hook Form |
| **File Upload** | Uppy + Supabase Storage |
| **Workflow** | AWS Step Functions, AWS Lambda, AWS SQS |
| **AI/Enrichment** | Apify (TikTok metadata), OpenAI (vision, transcription, embeddings) |
| **Real-time** | Supabase Realtime |
| **Notifications** | Resend (email) |
| **Payments** | Stripe Billing |
| **Observability** | Sentry (errors), PostHog (analytics) |
| **Hosting** | Vercel (frontend), Render (API) |

## Commands

```bash
# Backend (from src/backend/)
pytest tests/ -v                    # Run all tests
pytest tests/test_file.py -v        # Run single test file
pytest tests/test_file.py::test_fn  # Run single test
ruff check .                        # Lint
ruff format .                       # Format
alembic upgrade head                # Run migrations
alembic revision --autogenerate -m "description"  # Create migration

# Frontend (from src/frontend/)
npm test                            # Run tests
npm run lint                        # Lint
npm run typecheck                   # Type check
npm run build                       # Production build

# Local Development
supabase start                      # Start local Supabase
sam local invoke FunctionName       # Test Lambda locally
docker-compose up                   # Start all local services
```

## Architecture

### Processing Pipeline

10-step async pipeline orchestrated by AWS Step Functions:

1. `PARSE_EXPORT` → Extract URLs from ZIP, create `media_event` rows
2. `APIFY_ENRICH` → Fetch TikTok metadata (batched, 50/call)
3. `MEDIA_DOWNLOAD` → Download video/images to S3 temp
4. `SUBTITLE_FETCH` → Get subtitles if available
5. `WHISPER_TRANSCRIBE` → Transcribe via OpenAI if no subtitles
6. `VISION_ANALYSIS` → GPT-4 Vision tagging (batched, 5 images/call)
7. `TEXT_FUSION` → Combine caption + hashtags + transcript + OCR + visual_tags
8. `EMBEDDING` → Generate 1536-dim vectors (batched, 100/call)
9. `DERIVED_FIELDS` → Compute engagement_rate, interaction_hour, etc.
10. `SEARCH_INDEX` → Update full-text (GIN) + vector (ivfflat) indexes

**CRITICAL**: Every Lambda function MUST be idempotent. Use upserts and deterministic IDs.

### Capability Abstraction

Each processing step uses Protocol interfaces for vendor abstraction:

```python
# src/backend/capabilities/interfaces.py
class VideoMetadataProvider(Protocol):
    def fetch_metadata(self, urls: list[str]) -> list[VideoMetadataResult]: ...

class VisionAnalyzer(Protocol):
    def analyze(self, images: list[bytes], context: VideoContext) -> VisionAnalysisResult: ...

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

## Key Files

- `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` — Product spec, data model, API contracts
- `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` — Epic/task breakdown with status tracking
- `docs/MVP/tasks/specs/` — Individual task specifications
- `docs/MVP/tasks/TASK_SPEC_TEMPLATE.md` — Template for task specs

## Development Workflow

### Task Lifecycle
1. **SPEC**: Generate spec from Dev Guide task using `/generate-specs`
2. **VALIDATE**: Check spec against PRD/production requirements using `/validate-specs`
3. **IMPLEMENT**: Build feature with tests using `/implement-backlog`
4. **VERIFY**: Run task-specific tests using `/run-task-tests`

### Spec File Convention
Each task has ONE spec file at `docs/MVP/tasks/specs/{epic}-{task_id}.md` containing:
- Implementation requirements
- Context references (which files to read)
- Test requirements
- Progress tracking (completed/remaining/blocked)
- Implementation notes

### Status Tracking
Task status is tracked in TWO places:
1. **Spec file**: Detailed progress, notes, blockers
2. **Dev Guide**: Overall status per task (NOT_STARTED | IN_PROGRESS | BLOCKED | DONE)

## Code Conventions

### Python (Backend)
- Type hints required on all functions
- Async for all I/O operations
- Pydantic models for all request/response schemas
- Repository pattern for data access
- Dependency injection via FastAPI's `Depends()`

### TypeScript (Frontend)
- Strict mode enabled
- Zod for runtime validation
- Server components by default
- TanStack Query for data fetching
- React Hook Form for forms

### Database
- All schema changes via Alembic migrations
- Never raw SQL in application code
- RLS policies on all user-owned tables
- Use SQLAlchemy ORM exclusively

### Git
- Branch: `feature/{epic}-{task}-short-name` or `fix/{task}-description`
- Commits: `feat(scope): description` (conventional commits)
- PR per task, squash merge

## Testing Requirements

### Unit Tests
- Every public function must have tests
- Mock external services (Apify, OpenAI, Stripe)
- Test edge cases and error paths

### Integration Tests
- Test API endpoints with test database
- Test Supabase RLS policies
- Test Step Functions state transitions

### Test Naming
```python
# Python
def test_{function_name}_{scenario}_{expected_result}():
    ...

# Example
def test_parse_export_valid_zip_returns_urls():
    ...
```

## Security Checklist (Apply to Every Task)

- [ ] Server-side auth: Validate Supabase JWT, derive user_id from token
- [ ] RLS policies verified for any new/modified tables
- [ ] No PII in logs (no tokens, emails, raw URLs)
- [ ] Input validation on all endpoints
- [ ] Rate limiting on public endpoints

## Production Readiness (from PRD §9)

Every implementation must satisfy:
1. **Idempotency**: Safe under retries (upserts, deterministic IDs)
2. **Observability**: Correlation IDs, structured logging, cost tracking
3. **Error handling**: Graceful degradation, user-visible error states
4. **Cost controls**: Per-step budget tracking, tier enforcement
```

---

## Part 4: Slash Commands

### 4.1 `/generate-specs` Command

Create `.claude/commands/generate-specs.md`:

```markdown
---
description: Generate task specification files for one or more tasks from the Dev Guide
argument-hint: "<epic_number> [task_ids]"
---

## Mission

Generate detailed task specification files from the Dev Guide task list. Each spec becomes the single source of truth for that task's implementation.

## Instructions

1. **Parse Arguments**
   - If only epic number provided: generate specs for ALL tasks in that epic
   - If task IDs provided: generate specs only for those specific tasks
   - Example: `0` generates all Epic 0 specs, `0 0.1 0.3` generates only those two

2. **Read Context**
   - Read `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` for task list
   - Read `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` for detailed requirements
   - Read `docs/MVP/tasks/TASK_SPEC_TEMPLATE.md` for spec format

3. **For Each Task, Generate Spec File**
   
   Create `docs/MVP/tasks/specs/{epic_number}-{task_number}.md` with:

   ```markdown
   # Task {X.Y}: {Task Name}
   
   **Epic**: {Epic Number} - {Epic Name}
   **Status**: NOT_STARTED
   **Last Updated**: {date}
   
   ## Context References
   
   Before implementing, read these files:
   - `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` sections: {specific sections}
   - `CLAUDE.md` sections: {relevant sections}
   - {Other relevant specs that must complete first}
   
   ## Outcome
   
   {What user-visible capability exists when done - from Dev Guide}
   
   ## Requirements
   
   ### In-Scope
   - [ ] {Requirement 1}
   - [ ] {Requirement 2}
   
   ### Out-of-Scope
   - {Explicitly excluded items}
   
   ## Technical Specification
   
   ### Components
   - **Files to create**: {list}
   - **Files to modify**: {list}
   - **Database changes**: {migrations needed}
   - **API endpoints**: {if applicable}
   
   ### Dependencies
   - **Tasks that must complete first**: {task IDs}
   - **External services**: {Supabase, AWS, etc.}
   
   ### Data Contracts
   
   {Pydantic models, Zod schemas, or TypeScript interfaces for this task}
   
   ## Test Requirements
   
   ### Unit Tests
   - [ ] {Test case 1}
   - [ ] {Test case 2}
   
   ### Integration Tests
   - [ ] {Test case 1}
   
   ## Security & Production Checklist
   
   - [ ] Server-side auth verified
   - [ ] RLS policies added/verified
   - [ ] No PII in logs
   - [ ] Idempotent under retries
   - [ ] Error states handled gracefully
   
   ## Progress Tracking
   
   ### Completed
   - {None yet}
   
   ### Remaining
   - All requirements above
   
   ### Blocked By
   - {None or list blockers}
   
   ### Implementation Notes
   
   {Add notes during implementation}
```

4. **Update Dev Guide**
   - Add status column if not present
   - Mark generated specs as `SPEC_READY`

5. **Report**
   - List all specs generated
   - Note any tasks that couldn't be specified (missing info)
```

### 4.2 `/validate-specs` Command

Create `.claude/commands/validate-specs.md`:

```markdown
---
description: Validate task specifications against PRD and production requirements
argument-hint: "<spec_file_or_epic_number>"
---

## Mission

Validate that task specifications are complete, consistent with the PRD, and meet production readiness requirements.

## Instructions

1. **Identify Specs to Validate**
   - If file path: validate that single spec
   - If epic number: validate all specs in `docs/MVP/tasks/specs/{epic}-*.md`

2. **For Each Spec, Check**

   ### Completeness
   - [ ] All sections from template are present
   - [ ] Context references are specific (not just "see PRD")
   - [ ] Requirements are checkboxes, not prose
   - [ ] Data contracts are defined (Pydantic/Zod schemas)
   - [ ] Test requirements are specific and testable

   ### PRD Consistency
   - [ ] Requirements match PRD acceptance criteria
   - [ ] API contracts match PRD specifications
   - [ ] Data model changes align with PRD schema
   - [ ] No scope creep beyond PRD

   ### Production Readiness
   - [ ] Security checklist items are actionable
   - [ ] Idempotency strategy documented for any DB writes
   - [ ] Error handling approach specified
   - [ ] Observability requirements (logs, metrics) included

   ### Dependency Correctness
   - [ ] Listed dependencies actually exist as tasks
   - [ ] No circular dependencies
   - [ ] Infrastructure tasks (Epic 0) don't depend on feature tasks

3. **Output Validation Report**

   For each spec:
```
   ## {spec_file}

   ✓ Completeness: PASS/FAIL
     - {specific issues if any}

   ✓ PRD Consistency: PASS/FAIL
     - {specific issues if any}

   ✓ Production Readiness: PASS/FAIL
     - {specific issues if any}

   ✓ Dependencies: PASS/FAIL
     - {specific issues if any}

   **Overall**: VALID / NEEDS_REVISION
   ```

4. **For Failed Validations**
   - List specific fixes needed
   - Offer to auto-fix obvious issues (missing sections, formatting)
   ```

### 4.3 `/implement-backlog` Command

Create `.claude/commands/implement-backlog.md`:

```markdown
---
description: Implement tasks from the backlog, handling sequencing and parallelization automatically
argument-hint: "[epic_number] [--parallel]"
---

## Mission

Implement tasks from validated specs, automatically determining correct sequencing and using subagents for parallelizable work.

## Instructions

### Phase 1: Build Task Queue

1. **Gather Specs**
   - If epic specified: `docs/MVP/tasks/specs/{epic}-*.md`
   - Otherwise: all specs with status NOT_STARTED or IN_PROGRESS

2. **Build Dependency Graph**
   - Parse "Dependencies → Tasks that must complete first" from each spec
   - Verify all dependencies are DONE or will be processed
   - Detect and reject circular dependencies

3. **Determine Execution Order**
   
   Apply these rules:
   
   a. **Sequential requirement**: If Task B depends on Task A, A must complete before B starts
   
   b. **Parallel opportunity**: Tasks with NO mutual dependencies can run in parallel via subagents
   
   c. **Infrastructure first**: Epic 0 tasks always execute before feature epics
   
   d. **Context isolation**: Tasks touching different subsystems (backend vs frontend, different Lambda functions) are parallelizable

4. **Display Execution Plan**
```
   Execution Plan:

   Wave 1 (Sequential - Foundation):
     → 0.1: Backend scaffolding
     → 0.2: Frontend scaffolding

   Wave 2 (Parallel - Independent setup):
     ⇉ 0.3: Supabase setup [subagent]
     ⇉ 0.5: AWS infrastructure [subagent]

   Wave 3 (Sequential - Depends on Wave 2):
     → 0.4: Database migrations

   Continue? [y/n]
   ```

### Phase 2: Execute Tasks

For each task in order:

1. **Load Spec Context**
   - Read the task's spec file
   - Read all files listed in "Context References"
   - Load relevant skills if applicable

2. **Check Pre-conditions**
   - Verify dependencies are DONE
   - Verify required services are configured (check .env.local)

3. **Determine Execution Mode**

   **Use Main Agent When**:
   - Task modifies shared state (database migrations, shared types)
   - Task establishes patterns other tasks will follow (first API endpoint, first Lambda)
   - Task is part of a dependency chain

   **Use Subagent When**:
   - Task is independent of currently-running tasks
   - Task touches isolated files/systems
   - Multiple such tasks can run simultaneously

4. **Execute Implementation**

   For each task:
   
   a. **Create branch**: `git checkout -b feature/{epic}-{task}-{short-name}`
   
   b. **Implement in order**:
      1. Data contracts (Pydantic models, Zod schemas) 
      2. Database migrations if needed
      3. Core implementation
      4. Unit tests (alongside implementation)
      5. Integration tests
   
   c. **Run tests**: Execute test suite for affected code
   
   d. **Update spec file**:
      - Move completed items from "Remaining" to "Completed"
      - Add implementation notes
      - Update status to IN_PROGRESS or DONE
   
   e. **Commit**: `git commit -m "feat({scope}): {description}"`

5. **Handle Failures**
   - If tests fail: update spec with failure notes, set status to BLOCKED
   - If blocked by missing dependency: skip and queue for later
   - If external service unavailable: note in spec, continue with mockable work

6. **Update Dev Guide**
   - Change task status: NOT_STARTED → IN_PROGRESS → DONE
   - Note any blockers

### Phase 3: Parallel Execution (when --parallel flag used)

When multiple independent tasks are identified:

1. **Launch Subagents**
   ```
   Launching parallel implementation:

   [subagent-1] Task 3.3: Lambda APIFY_ENRICH
   [subagent-2] Task 3.4: Lambda MEDIA_DOWNLOAD
   [subagent-3] Task 3.5: Lambda SUBTITLE_FETCH

   Main agent monitoring for completion...
   ```

2. **Each Subagent**:
   - Receives: spec file path, context references, branch name
   - Creates own branch
   - Implements according to spec
   - Runs tests
   - Reports: DONE, FAILED, or BLOCKED

3. **Main Agent Waits and Continues**:
   - Monitors subagent completion
   - Collects results
   - Updates Dev Guide
   - Proceeds to next wave

## Subagent Delegation Format

When delegating to subagent, provide:
   ```
Use the implementer subagent to implement task {task_id}.

Spec file: docs/MVP/tasks/specs/{spec_file}
Branch: feature/{epic}-{task}-{short-name}
Context to read first:
- {file1}
- {file2}

Implementation order:
1. Data contracts
2. Core implementation  
3. Unit tests
4. Integration tests

Report back: DONE | FAILED | BLOCKED with notes
```
```

### 4.4 `/run-task-tests` Command

Create `.claude/commands/run-task-tests.md`:

```markdown
---
description: Run tests for a specific task based on its spec
argument-hint: "<task_spec_file>"
---

## Mission

Run all tests specified in a task's spec file and report results.

## Instructions

1. **Load Spec**
   - Read the specified spec file
   - Extract test requirements section

2. **Identify Test Files**
   - Parse "Components → Files to create/modify" for test file locations
   - Map to actual test files in `tests/` directories

3. **Run Tests**
   
   Backend (from src/backend/):
   ```bash
   # Run specific test file
   pytest tests/unit/test_{component}.py -v
   pytest tests/integration/test_{feature}.py -v
```

   Frontend (from src/frontend/):
   ```bash
   npm test -- --testPathPattern="{pattern}"
   ```

4. **Report Results**
   ```
   ## Test Results for {task_id}
   
   ### Unit Tests
   ✓ test_parse_export_valid_zip_returns_urls (0.12s)
   ✓ test_parse_export_invalid_zip_raises_error (0.08s)
   ✗ test_parse_export_empty_zip_returns_empty_list (0.15s)
     AssertionError: Expected [] but got None
   
   ### Integration Tests
   ✓ test_upload_endpoint_creates_record (0.45s)
   
   **Summary**: 3/4 passed
   
   ### Failed Test Details
   {full error output for failures}
   ```

5. **Update Spec If Failures**
   - Add failing tests to "Blocked By" section
   - Add error details to "Implementation Notes"
```

---

## Part 5: Subagents

### 5.1 Spec Writer Subagent

Create `.claude/agents/spec-writer.md`:

```markdown
---
name: spec-writer
description: Generates detailed task specifications from Dev Guide entries. Use when batch-generating specs for an epic or when a task needs its spec written.
tools: Read, Write, Glob, Grep
model: sonnet
---

You are a technical specification writer for the Attic project.

## Your Role

Transform high-level task descriptions from the Dev Guide into detailed, implementable specifications.

## Process

1. Read the task entry from `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`
2. Find relevant details in `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md`
3. Check existing specs for patterns: `docs/MVP/tasks/specs/`
4. Generate spec following `docs/MVP/tasks/TASK_SPEC_TEMPLATE.md`

## Output Requirements

- Spec file at: `docs/MVP/tasks/specs/{epic}-{task}.md`
- All requirements as checkboxes
- Specific file paths, not vague references
- Data contracts with actual field names
- Test cases that are specific and measurable

## Quality Checklist

Before completing, verify:
- [ ] Context References list specific files and sections
- [ ] Requirements are atomic and checkable
- [ ] Data contracts use proper types (not `any` or `dict`)
- [ ] Test requirements include both success and error cases
- [ ] Security checklist is filled in, not just copied
- [ ] Dependencies are actual task IDs that exist
```

### 5.2 Implementer Subagent

Create `.claude/agents/implementer.md`:

```markdown
---
name: implementer
description: Implements a single task from its spec file. Use for parallel task implementation when tasks are independent.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

You are an implementation specialist for the Attic project.

## Your Role

Implement a single task according to its specification file. You work in isolation on tasks that don't share dependencies with other in-progress work.

## Before Starting

1. Read the spec file provided to you
2. Read ALL files listed in "Context References"
3. Read `CLAUDE.md` for project conventions
4. Create your feature branch

## Implementation Order (STRICT)

1. **Data Contracts First**
   - Pydantic models in `src/backend/app/models/`
   - Zod schemas in `src/frontend/lib/schemas/`
   - TypeScript types in `src/frontend/types/`

2. **Database Migrations** (if needed)
   - Create migration: `alembic revision --autogenerate -m "{description}"`
   - Review generated migration
   - Apply: `alembic upgrade head`

3. **Core Implementation**
   - Follow patterns in existing code
   - Type hints on everything (Python)
   - Strict mode compliance (TypeScript)

4. **Tests Alongside Code**
   - Write unit test immediately after each function
   - Don't wait until end

5. **Integration Tests**
   - After core implementation works

## Code Standards

Python:
- Async for all I/O
- Type hints required
- Pydantic for validation

TypeScript:
- Strict mode
- Zod for runtime validation
- Server components by default

## After Each File

Run relevant checks:
```bash
# Python
ruff check src/backend/
ruff format src/backend/

# TypeScript  
npm run typecheck
npm run lint
```

## Completion

1. Run all tests for your changes
2. Update spec file:
   - Move items from "Remaining" to "Completed"
   - Add any notes to "Implementation Notes"
   - Set status to DONE (or BLOCKED with reason)
3. Commit with conventional commit message
4. Report: DONE | FAILED | BLOCKED
```

### 5.3 Tester Subagent

Create `.claude/agents/tester.md`:

```markdown
---
name: tester
description: Writes and runs tests for implemented features. Use when implementation is complete but tests are missing or failing.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

You are a test specialist for the Attic project.

## Your Role

Write comprehensive tests for implemented features, ensuring production readiness.

## Test Categories

### Unit Tests
- Test individual functions in isolation
- Mock external dependencies
- Cover success, error, and edge cases

### Integration Tests
- Test API endpoints with test database
- Test service interactions
- Test Supabase RLS policies

## Test Patterns

Python (pytest):
```python
# Naming: test_{function}_{scenario}_{expected}
def test_parse_export_valid_zip_returns_urls():
    # Arrange
    zip_file = create_test_zip(["Like List.json"])
    
    # Act
    result = parse_export(zip_file)
    
    # Assert
    assert len(result) > 0
    assert all(url.startswith("https://") for url in result)

# Fixtures in conftest.py
@pytest.fixture
def test_user(db_session):
    return create_user(email="test@example.com")

# Mock external services
@patch("app.services.apify.ApifyClient")
def test_enrich_calls_apify(mock_client):
    ...
```

TypeScript (Jest/Vitest):
```typescript
// Naming: describe > it should...
describe("parseExport", () => {
  it("should return URLs from valid zip", async () => {
    const zip = createTestZip();
    const result = await parseExport(zip);
    expect(result).toHaveLength(greaterThan(0));
  });
});
```

## Coverage Requirements

- All public functions must have tests
- Error paths must be tested
- Edge cases: empty input, max limits, invalid data

## Before Completing

1. Run full test suite
2. Check coverage: `pytest --cov=app --cov-report=term-missing`
3. Update spec file with test status
```

---

## Part 6: Settings and Hooks

### 6.1 Project Settings

Create `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(pytest*)",
      "Bash(ruff*)",
      "Bash(npm test*)",
      "Bash(npm run*)",
      "Bash(alembic*)",
      "Bash(supabase*)",
      "Bash(git*)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(*--force*delete*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/hooks/post-edit-lint.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/hooks/post-session-summary.sh"
          }
        ]
      }
    ]
  }
}
```

### 6.2 Post-Edit Lint Hook

Create `scripts/hooks/post-edit-lint.sh`:

```bash
#!/bin/bash
# Post-edit hook: Run linters on modified files

# Read the tool input from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Determine file type and run appropriate linter
case "$FILE_PATH" in
    *.py)
        cd src/backend && ruff check --fix "$FILE_PATH" 2>/dev/null
        cd src/backend && ruff format "$FILE_PATH" 2>/dev/null
        ;;
    *.ts|*.tsx)
        cd src/frontend && npm run lint --fix "$FILE_PATH" 2>/dev/null
        ;;
esac

exit 0
```

Make executable: `chmod +x scripts/hooks/post-edit-lint.sh`

---

## Part 7: Skills

### 7.1 Supabase Patterns Skill

Create `.claude/skills/supabase-patterns/SKILL.md`:

```markdown
---
name: supabase-patterns
description: Patterns for working with Supabase Auth, Storage, Realtime, and RLS in the Attic project. Apply when implementing auth, file uploads, real-time features, or database security.
---

# Supabase Patterns for Attic

## Authentication

### Validating JWT in FastAPI

```python
# src/backend/app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Validate Supabase JWT and return user data."""
    try:
        # Verify JWT with Supabase's JWT secret
        payload = jwt.decode(
            credentials.credentials,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return {"user_id": payload["sub"], "email": payload.get("email")}
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
```

### Using in Endpoints

```python
@router.get("/uploads")
async def list_uploads(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # user["user_id"] is guaranteed to be from valid JWT
    return await upload_repo.list_by_user(db, user["user_id"])
```

## Storage

### Presigned Upload URLs

```python
async def create_upload_url(user_id: str, filename: str) -> str:
    """Generate presigned URL for direct upload to Supabase Storage."""
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    
    # Path includes user_id for RLS
    path = f"{user_id}/{uuid4()}/{filename}"
    
    # URL valid for 1 hour
    result = supabase.storage.from_("uploads").create_signed_upload_url(path)
    return result["signedUrl"]
```

### RLS for Storage

```sql
-- In Supabase SQL Editor
CREATE POLICY "Users can upload to their folder"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'uploads' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "Users can read their uploads"
ON storage.objects FOR SELECT
TO authenticated
USING (
    bucket_id = 'uploads' AND
    (storage.foldername(name))[1] = auth.uid()::text
);
```

## Realtime

### Subscribing to Pipeline Progress (Frontend)

```typescript
// src/frontend/hooks/usePipelineProgress.ts
import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

export function usePipelineProgress(uploadId: string) {
  const [progress, setProgress] = useState<PipelineProgress | null>(null);
  
  useEffect(() => {
    const supabase = createClient();
    
    const channel = supabase
      .channel(`pipeline:${uploadId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'upload_pipeline_runs',
          filter: `upload_id=eq.${uploadId}`
        },
        (payload) => {
          setProgress(payload.new as PipelineProgress);
        }
      )
      .subscribe();
    
    return () => {
      supabase.removeChannel(channel);
    };
  }, [uploadId]);
  
  return progress;
}
```

## RLS Policies

### Standard User-Owned Table Pattern

```sql
-- Enable RLS
ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;

-- Users can only see their own uploads
CREATE POLICY "Users view own uploads"
ON uploads FOR SELECT
TO authenticated
USING (user_id = auth.uid());

-- Users can only insert their own uploads
CREATE POLICY "Users create own uploads"
ON uploads FOR INSERT
TO authenticated
WITH CHECK (user_id = auth.uid());

-- Users can only update their own uploads
CREATE POLICY "Users update own uploads"
ON uploads FOR UPDATE
TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- Users can only delete their own uploads
CREATE POLICY "Users delete own uploads"
ON uploads FOR DELETE
TO authenticated
USING (user_id = auth.uid());
```

### Testing RLS

```python
# tests/integration/test_rls.py
async def test_user_cannot_see_other_users_uploads(
    test_client, user_a_token, user_b_upload
):
    """User A should not see User B's uploads."""
    response = await test_client.get(
        f"/api/uploads/{user_b_upload.id}",
        headers={"Authorization": f"Bearer {user_a_token}"}
    )
    assert response.status_code == 404  # Not 403 - don't reveal existence
```
```

### 7.2 Lambda Patterns Skill

Create `.claude/skills/lambda-patterns/SKILL.md`:

```markdown
---
name: lambda-patterns
description: Patterns for AWS Lambda functions in the Attic processing pipeline. Apply when implementing pipeline steps, handling Step Functions integration, or ensuring idempotency.
---

# Lambda Patterns for Attic Pipeline

## Idempotency (CRITICAL)

Every Lambda function MUST be idempotent. Step Functions will retry on failure.

### Pattern: Deterministic IDs

```python
# Generate ID from content, not randomly
def get_media_event_id(user_id: str, platform_id: str) -> str:
    """Deterministic ID ensures upsert on retry."""
    return str(uuid5(NAMESPACE_URL, f"{user_id}:{platform_id}"))

# Use in upsert
async def save_media_event(db: AsyncSession, event: MediaEvent):
    stmt = insert(MediaEventModel).values(**event.dict())
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "caption_text": stmt.excluded.caption_text,
            "updated_at": func.now()
        }
    )
    await db.execute(stmt)
```

### Pattern: Idempotency Key in Processing Steps

```python
async def record_processing_step(
    db: AsyncSession,
    media_event_id: str,
    step_type: str,
    attempt: int,
    **kwargs
):
    """Record step with unique constraint on (media_event_id, step_type, attempt)."""
    stmt = insert(ProcessingStepModel).values(
        media_event_id=media_event_id,
        step_type=step_type,
        attempt=attempt,
        **kwargs
    ).on_conflict_do_nothing()  # Skip if already recorded
    await db.execute(stmt)
```

## Lambda Handler Structure

```python
# src/backend/lambdas/apify_enrich/handler.py
import json
import logging
from typing import Any

from app.capabilities.interfaces import VideoMetadataProvider
from app.capabilities.apify import ApifyProvider
from app.core.config import settings
from app.db.session import get_db_session

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for APIFY_ENRICH step.
    
    Input (from Step Functions):
    {
        "upload_id": "uuid",
        "user_id": "uuid",
        "batch_index": 0,
        "video_urls": ["url1", "url2", ...]
    }
    
    Output:
    {
        "upload_id": "uuid",
        "batch_index": 0,
        "processed_count": 50,
        "failed_count": 2,
        "cost_usd": 0.104
    }
    """
    upload_id = event["upload_id"]
    user_id = event["user_id"]
    batch_index = event["batch_index"]
    video_urls = event["video_urls"]
    
    logger.info(json.dumps({
        "event": "apify_enrich_start",
        "upload_id": upload_id,
        "batch_index": batch_index,
        "url_count": len(video_urls)
    }))
    
    try:
        provider: VideoMetadataProvider = ApifyProvider(settings.APIFY_API_TOKEN)
        
        with get_db_session() as db:
            results = provider.fetch_metadata(video_urls)
            
            processed = 0
            failed = 0
            total_cost = 0.0
            
            for result in results:
                if result.success:
                    # Upsert media event with metadata
                    await save_media_event(db, user_id, upload_id, result.data)
                    processed += 1
                else:
                    failed += 1
                    logger.warning(json.dumps({
                        "event": "apify_enrich_video_failed",
                        "upload_id": upload_id,
                        "url": result.url,
                        "error": result.error
                    }))
                
                total_cost += result.cost_usd
            
            # Record step completion
            await record_processing_step(
                db,
                upload_id=upload_id,
                step_type="APIFY_ENRICH",
                batch_index=batch_index,
                status="succeeded",
                cost_usd=total_cost
            )
            
            db.commit()
        
        return {
            "upload_id": upload_id,
            "batch_index": batch_index,
            "processed_count": processed,
            "failed_count": failed,
            "cost_usd": total_cost
        }
        
    except Exception as e:
        logger.error(json.dumps({
            "event": "apify_enrich_error",
            "upload_id": upload_id,
            "batch_index": batch_index,
            "error": str(e)
        }))
        raise  # Let Step Functions handle retry
```

## Step Functions Integration

### State Machine Definition (ASL)

```json
{
  "Comment": "Attic Video Processing Pipeline",
  "StartAt": "ParseExport",
  "States": {
    "ParseExport": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:attic-parse-export",
      "Next": "CreateBatches",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "HandleFailure"
        }
      ]
    },
    "CreateBatches": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${region}:${account}:function:attic-create-batches",
      "Next": "ProcessBatches"
    },
    "ProcessBatches": {
      "Type": "Map",
      "ItemsPath": "$.batches",
      "MaxConcurrency": 10,
      "Iterator": {
        "StartAt": "ApifyEnrich",
        "States": {
          "ApifyEnrich": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${region}:${account}:function:attic-apify-enrich",
            "End": true,
            "Retry": [
              {
                "ErrorEquals": ["States.TaskFailed"],
                "IntervalSeconds": 5,
                "MaxAttempts": 3,
                "BackoffRate": 2
              }
            ]
          }
        }
      },
      "Next": "UpdateProgress"
    }
  }
}
```

## Testing Lambdas Locally

```bash
# Using SAM CLI
sam local invoke ApifyEnrichFunction -e events/apify_enrich.json

# Event file: events/apify_enrich.json
{
  "upload_id": "test-upload-123",
  "user_id": "test-user-456", 
  "batch_index": 0,
  "video_urls": [
    "https://www.tiktok.com/@user/video/123"
  ]
}
```

## Structured Logging

Always log with these fields:
- `upload_id`: Correlation ID
- `user_id`: For debugging (never log email)
- `step_name`: Current pipeline step
- `cost_usd`: For cost tracking

```python
logger.info(json.dumps({
    "event": "step_complete",
    "upload_id": upload_id,
    "step_name": "APIFY_ENRICH",
    "duration_ms": 1234,
    "cost_usd": 0.052,
    "items_processed": 50
}))
```
```

---

## Part 8: Dev Guide Status Format

Update your Dev Guide to include status tracking. Add this section after each epic's task table:

```markdown
### Epic 0 Status

| Task | Status | Spec | Notes |
|------|--------|------|-------|
| 0.1 | NOT_STARTED | [spec](specs/0-0.1.md) | |
| 0.2 | NOT_STARTED | [spec](specs/0-0.2.md) | |
| 0.3 | NOT_STARTED | [spec](specs/0-0.3.md) | Requires Supabase account |
| ... | | | |

**Status Values**: `NOT_STARTED` | `SPEC_READY` | `IN_PROGRESS` | `BLOCKED` | `DONE`
```

---

## Part 9: Execution Workflow

### Daily Workflow

```bash
# 1. Open Claude Code in project root
cd ~/projects/attic
claude

# 2. Generate specs for an epic
/generate-specs 0

# 3. Validate the generated specs
/validate-specs 0

# 4. Fix any validation issues
# (Claude will show what needs fixing)

# 5. Start implementation
/implement-backlog 0

# 6. For parallel work (after Epic 0 foundation is done)
/implement-backlog 3 --parallel
```

### Resuming Work

When returning to the project:

```bash
# Check current status
cat docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md | grep -A 20 "Epic.*Status"

# Resume any IN_PROGRESS tasks
/implement-backlog  # Will pick up where left off
```

### Handling Blockers

When a task is blocked:

1. Spec file is updated with blocker details
2. Dev Guide shows BLOCKED status
3. `/implement-backlog` skips blocked tasks
4. Fix blocker, update spec, change status to IN_PROGRESS
5. Re-run `/implement-backlog`

---

## Part 10: Quick Reference

### File Locations

| Purpose | Location |
|---------|----------|
| Task specs | `docs/MVP/tasks/specs/{epic}-{task}.md` |
| Status tracking | `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` |
| Product requirements | `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` |
| Project conventions | `CLAUDE.md` |
| Subagents | `.claude/agents/` |
| Commands | `.claude/commands/` |
| Skills | `.claude/skills/` |
| Hooks config | `.claude/settings.json` |

### Commands

| Command | Purpose |
|---------|---------|
| `/generate-specs <epic> [tasks]` | Create spec files from Dev Guide |
| `/validate-specs <epic or file>` | Check specs for completeness |
| `/implement-backlog [epic] [--parallel]` | Implement tasks from specs |
| `/run-task-tests <spec_file>` | Run tests for a specific task |

### Task Status Values

| Status | Meaning |
|--------|---------|
| `NOT_STARTED` | No work begun |
| `SPEC_READY` | Spec generated, ready for implementation |
| `IN_PROGRESS` | Currently being implemented |
| `BLOCKED` | Waiting on dependency or issue |
| `DONE` | Complete with tests passing |

### Sequencing Rules

1. **Epic 0 first**: Infrastructure before features
2. **Dependencies respected**: Task B waits for Task A if specified
3. **Parallel when safe**: Independent tasks can use subagents
4. **Test with implementation**: Not a separate phase
