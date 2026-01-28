#!/bin/bash
# Test: Supabase Connection
#
# Verifies connectivity to the Supabase project by:
# - Checking the REST API health
# - Verifying the project URL is accessible

set -e

SUPABASE_URL=${SUPABASE_URL:-}
TIMEOUT=${TIMEOUT:-10}

# Skip if no Supabase URL configured
if [[ -z "$SUPABASE_URL" ]]; then
    echo "SUPABASE_URL not set, skipping Supabase test"
    exit 0
fi

# Normalize URL (remove trailing slash)
SUPABASE_URL="${SUPABASE_URL%/}"

# Check REST API health
rest_url="$SUPABASE_URL/rest/v1/"
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$rest_url" 2>/dev/null || echo -e "\n000")
status_code=$(echo "$response" | tail -n 1)

# 401 is expected without auth key, but shows the service is running
if [[ "$status_code" -lt 200 || ("$status_code" -ge 400 && "$status_code" != "401") ]]; then
    echo "Supabase REST API check failed: HTTP $status_code"
    exit 1
fi

# Check Auth API
auth_url="$SUPABASE_URL/auth/v1/health"
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$auth_url" 2>/dev/null || echo -e "\n000")
status_code=$(echo "$response" | tail -n 1)

# Auth health should return 200
if [[ "$status_code" != "200" ]]; then
    # Some Supabase configs don't expose this endpoint, warn but don't fail
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Warning: Auth health endpoint returned HTTP $status_code"
    fi
fi

# Verbose output
if [[ "$VERBOSE" == "true" ]]; then
    echo "Supabase URL: $SUPABASE_URL"
    echo "REST API accessible: yes"
fi

exit 0
