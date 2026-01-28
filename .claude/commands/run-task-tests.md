---
description: Run tests for a specific task based on its spec file
argument-hint: "<spec_file_or_task_id>"
---

## Mission

Run all tests specified in a task's spec file and report results with actionable feedback.

## Arguments

- `spec_file`: Path to spec file (e.g., `docs/MVP/tasks/specs/0-0.1.md`)
- `task_id`: Task ID (e.g., `0.1`) - will look up spec file

## Instructions

1. **Load Spec**
   - If task_id provided, resolve to `docs/MVP/tasks/specs/{epic}-{task}.md`
   - Read the spec file
   - Extract "Test Requirements" section
   - Extract "Components → Files to create/modify" for test file locations

2. **Identify Test Files**
   
   Map spec components to test locations:
   ```
   Component                    → Test File
   ─────────────────────────────────────────────────────
   src/backend/app/api/auth.py  → src/backend/tests/unit/test_auth.py
   src/backend/app/api/auth.py  → src/backend/tests/integration/test_auth_api.py
   src/frontend/app/login/      → src/frontend/__tests__/login.test.tsx
   ```

3. **Run Tests**

   **Backend tests:**
   ```bash
   cd src/backend
   
   # Run unit tests for this task's components
   pytest tests/unit/test_{component}.py -v --tb=short
   
   # Run integration tests
   pytest tests/integration/test_{feature}.py -v --tb=short
   
   # If specific test file doesn't exist, run pattern match
   pytest tests/ -k "{task_keywords}" -v --tb=short
   ```

   **Frontend tests:**
   ```bash
   cd src/frontend
   
   # Run tests matching component names
   npm test -- --testPathPattern="{pattern}" --verbose
   ```

4. **Collect Results**

   Parse test output to extract:
   - Test name
   - Pass/Fail status
   - Duration
   - Error message (if failed)
   - Stack trace (for failures)

5. **Output Report**

   ```
   ═══════════════════════════════════════════════════════════
    TEST RESULTS: Task 0.3 - Supabase project setup
   ═══════════════════════════════════════════════════════════
   
   UNIT TESTS (src/backend/tests/unit/)
   ─────────────────────────────────────────────────────────────
   ✓ test_supabase_client_init_with_valid_env          0.02s
   ✓ test_supabase_client_raises_on_missing_env        0.01s
   ✗ test_supabase_client_handles_network_error        0.15s
   
   INTEGRATION TESTS (src/backend/tests/integration/)
   ─────────────────────────────────────────────────────────────
   ✓ test_supabase_connection_succeeds                 0.45s
   ✓ test_supabase_rls_blocks_cross_user_access        0.32s
   
   ═══════════════════════════════════════════════════════════
    SUMMARY: 4/5 passed (80%)
   ═══════════════════════════════════════════════════════════
   
   FAILED TESTS:
   
   ▸ test_supabase_client_handles_network_error
     File: tests/unit/test_supabase.py:45
     
     AssertionError: Expected SupabaseNetworkError but got 
     generic ConnectionError
     
     async def test_supabase_client_handles_network_error():
         with patch('httpx.AsyncClient.get', side_effect=NetworkError()):
   >       with pytest.raises(SupabaseNetworkError):
               await client.fetch_user(user_id)
     
     Suggested fix: Wrap ConnectionError in SupabaseNetworkError 
     in src/backend/app/core/supabase.py
   ```

6. **Update Spec File**

   If any tests failed:
   ```markdown
   ### Blocked By
   - Tests failing: test_supabase_client_handles_network_error
     - Error: Expected SupabaseNetworkError but got ConnectionError
     - Fix needed in: src/backend/app/core/supabase.py
   ```

   If all tests passed:
   ```markdown
   ### Implementation Notes
   - All tests passing as of {date}
   - Coverage: 80% (run with --cov for details)
   ```

7. **Update Dev Guide**

   Update the task status in `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`:

   - Find the epic's status table
   - If tests **failed**: Set status to `BLOCKED`
   - If tests **passed** and implementation is complete: Set status to `DONE`
   - Update "Blocked By" column if needed

8. **Coverage Report (Optional)**

   If `--coverage` flag or tests all pass:
   ```bash
   cd src/backend
   pytest tests/ -v --cov=app --cov-report=term-missing | head -50
   ```
   
   Output coverage gaps:
   ```
   COVERAGE REPORT
   ─────────────────────────────────────────────────────────────
   app/core/supabase.py         85%   Missing: 67-72, 89
   app/api/auth.py              92%   Missing: 45
   
   Lines not covered:
   - supabase.py:67-72: Error handling for rate limits
   - auth.py:45: Edge case for expired refresh token
   ```

## Test Discovery Rules

When test files don't follow exact naming:

1. **Search patterns:**
   ```
   # For component src/backend/app/api/uploads.py
   Search:
   - tests/unit/test_uploads.py
   - tests/unit/test_upload*.py
   - tests/unit/*upload*.py
   - tests/integration/test_upload*.py
   ```

2. **Keyword matching:**
   ```
   # For task "Supabase project setup"
   Keywords: supabase, setup, config, connection
   
   pytest tests/ -k "supabase or setup or config"
   ```

3. **If no tests found:**
   ```
   ⚠ No test files found for task 0.3
   
   Expected test locations:
   - src/backend/tests/unit/test_supabase.py (missing)
   - src/backend/tests/integration/test_supabase.py (missing)
   
   Spec requires these test cases:
   - [ ] test_supabase_client_initializes
   - [ ] test_supabase_rls_policy_works
   
   Would you like me to generate test stubs? [y/n]
   ```
