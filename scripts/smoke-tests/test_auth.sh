#!/bin/bash
# Test: Authentication Flow
#
# Verifies the authentication system works by:
# - Checking auth endpoints are accessible
# - Validating test user can sign in (if credentials provided)
#
# Environment Variables:
#   TEST_USER_EMAIL    - Test user email
#   TEST_USER_PASSWORD - Test user password
#   SUPABASE_ANON_KEY  - Supabase anonymous key

set -e

SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}
TEST_USER_EMAIL=${TEST_USER_EMAIL:-}
TEST_USER_PASSWORD=${TEST_USER_PASSWORD:-}
TIMEOUT=${TIMEOUT:-10}

# Skip if no Supabase URL configured
if [[ -z "$SUPABASE_URL" ]]; then
    echo "SUPABASE_URL not set, skipping auth test"
    exit 0
fi

# Normalize URL
SUPABASE_URL="${SUPABASE_URL%/}"

# Check auth endpoint is accessible
auth_url="$SUPABASE_URL/auth/v1/settings"
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" \
    -H "apikey: ${SUPABASE_ANON_KEY:-dummy}" \
    "$auth_url" 2>/dev/null || echo -e "\n000")
status_code=$(echo "$response" | tail -n 1)

if [[ "$status_code" -lt 200 || "$status_code" -ge 500 ]]; then
    echo "Auth settings endpoint check failed: HTTP $status_code"
    exit 1
fi

# Test user sign-in if credentials provided
if [[ -n "$TEST_USER_EMAIL" && -n "$TEST_USER_PASSWORD" && -n "$SUPABASE_ANON_KEY" ]]; then
    signin_url="$SUPABASE_URL/auth/v1/token?grant_type=password"
    signin_response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -X POST \
        -H "apikey: $SUPABASE_ANON_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASSWORD\"}" \
        "$signin_url" 2>/dev/null || echo -e "\n000")

    signin_body=$(echo "$signin_response" | head -n -1)
    signin_status=$(echo "$signin_response" | tail -n 1)

    if [[ "$signin_status" == "200" ]]; then
        if echo "$signin_body" | jq -e '.access_token' >/dev/null 2>&1; then
            if [[ "$VERBOSE" == "true" ]]; then
                echo "Test user sign-in successful"
            fi
        else
            echo "Sign-in response missing access_token"
            exit 1
        fi
    else
        echo "Test user sign-in failed: HTTP $signin_status"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "Response: $signin_body"
        fi
        exit 1
    fi
else
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Test user credentials not provided, skipping sign-in test"
    fi
fi

exit 0
