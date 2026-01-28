#!/bin/bash
# Attic Staging Smoke Test Runner
#
# Runs a comprehensive suite of smoke tests against the staging environment
# to validate deployments before they can be promoted to production.
#
# Usage:
#   ./scripts/smoke-tests/run.sh [--env staging|production] [--skip-auth] [--verbose]
#
# Environment Variables:
#   STAGING_BACKEND_URL    - Backend API URL (default: https://attic-staging.onrender.com)
#   STAGING_FRONTEND_URL   - Frontend URL (default: Vercel preview URL)
#   STAGING_SUPABASE_URL   - Supabase project URL
#   STAGING_AWS_REGION     - AWS region for staging resources (default: us-east-1)
#   TEST_USER_EMAIL        - Test user email for auth tests
#   TEST_USER_PASSWORD     - Test user password for auth tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${ENVIRONMENT:-staging}
BACKEND_URL=${STAGING_BACKEND_URL:-https://attic-staging.onrender.com}
FRONTEND_URL=${STAGING_FRONTEND_URL:-}
SUPABASE_URL=${STAGING_SUPABASE_URL:-}
AWS_REGION=${STAGING_AWS_REGION:-us-east-1}
SKIP_AUTH=${SKIP_AUTH:-false}
VERBOSE=${VERBOSE:-false}

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-auth)
            SKIP_AUTH=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_failure() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Run individual test scripts
run_test() {
    local test_name=$1
    local test_script=$2

    log_info "Running: $test_name"

    if [[ -x "$test_script" ]]; then
        if "$test_script"; then
            log_success "$test_name"
        else
            log_failure "$test_name"
        fi
    else
        log_skip "$test_name (script not found or not executable)"
    fi
}

# Header
echo ""
echo "=============================================="
echo "  Attic Staging Smoke Tests"
echo "  Environment: $ENVIRONMENT"
echo "=============================================="
echo ""

# Export variables for child scripts
export BACKEND_URL
export FRONTEND_URL
export SUPABASE_URL
export AWS_REGION
export SKIP_AUTH
export VERBOSE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run test scripts
run_test "Backend Health Check" "$SCRIPT_DIR/test_health.sh"
run_test "Frontend Accessibility" "$SCRIPT_DIR/test_frontend.sh"
run_test "Supabase Connection" "$SCRIPT_DIR/test_supabase.sh"
run_test "AWS Resources" "$SCRIPT_DIR/test_aws.sh"

if [[ "$SKIP_AUTH" != "true" ]]; then
    run_test "Authentication Flow" "$SCRIPT_DIR/test_auth.sh"
    run_test "Upload Trigger" "$SCRIPT_DIR/test_upload.sh"
else
    log_skip "Authentication Flow (--skip-auth)"
    log_skip "Upload Trigger (--skip-auth)"
fi

# Summary
echo ""
echo "=============================================="
echo "  Test Summary"
echo "=============================================="
echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
echo "=============================================="
echo ""

# Exit with failure if any tests failed
if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Smoke tests failed. Deployment should not proceed.${NC}"
    exit 1
fi

echo -e "${GREEN}All smoke tests passed!${NC}"
exit 0
