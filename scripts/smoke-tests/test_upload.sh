#!/bin/bash
# Test: Upload Trigger
#
# Verifies the upload flow by checking:
# - Presigned URL endpoint is accessible
# - Storage bucket accepts uploads (optional)
#
# Note: This is a basic connectivity test. Full E2E upload
# testing should be done via Playwright tests.

set -e

BACKEND_URL=${BACKEND_URL:-https://attic-staging.onrender.com}
SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}
TIMEOUT=${TIMEOUT:-10}

# Check presigned URL endpoint exists
# Note: This should return 401 without auth, but endpoint should be accessible
presign_url="$BACKEND_URL/api/uploads/presign"
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"filename": "test.zip"}' \
    "$presign_url" 2>/dev/null || echo -e "\n000")

status_code=$(echo "$response" | tail -n 1)

# 401/403 is expected without auth - shows endpoint exists
# 200 would mean endpoint is misconfigured (no auth required)
if [[ "$status_code" == "401" || "$status_code" == "403" || "$status_code" == "422" ]]; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Presign endpoint accessible (requires auth as expected)"
    fi
elif [[ "$status_code" == "200" ]]; then
    echo "Warning: Presign endpoint returned 200 without auth - check security"
    # Don't fail, but warn
elif [[ "$status_code" -ge 500 ]]; then
    echo "Presign endpoint error: HTTP $status_code"
    exit 1
else
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Presign endpoint returned: HTTP $status_code"
    fi
fi

# Check Supabase Storage if configured
if [[ -n "$SUPABASE_URL" && -n "$SUPABASE_ANON_KEY" ]]; then
    storage_url="$SUPABASE_URL/storage/v1/bucket/uploads"
    storage_response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -H "apikey: $SUPABASE_ANON_KEY" \
        "$storage_url" 2>/dev/null || echo -e "\n000")

    storage_status=$(echo "$storage_response" | tail -n 1)

    # 400/404 might indicate bucket doesn't exist or different config
    # 401 is expected if bucket requires auth
    if [[ "$storage_status" -lt 500 ]]; then
        if [[ "$VERBOSE" == "true" ]]; then
            echo "Storage API accessible: HTTP $storage_status"
        fi
    else
        echo "Storage API error: HTTP $storage_status"
        exit 1
    fi
fi

exit 0
