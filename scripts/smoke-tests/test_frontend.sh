#!/bin/bash
# Test: Frontend Accessibility
#
# Verifies the frontend loads successfully by checking:
# - HTTP 200 response
# - Valid HTML content
# - Key page elements present

set -e

FRONTEND_URL=${FRONTEND_URL:-}
TIMEOUT=${TIMEOUT:-15}

# Skip if no frontend URL configured
if [[ -z "$FRONTEND_URL" ]]; then
    echo "FRONTEND_URL not set, skipping frontend test"
    exit 0
fi

# Make request
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$FRONTEND_URL" 2>/dev/null || echo -e "\n000")

# Split response body and status code
body=$(echo "$response" | head -n -1)
status_code=$(echo "$response" | tail -n 1)

# Validate status code (allow redirects)
if [[ "$status_code" -lt 200 || "$status_code" -ge 400 ]]; then
    echo "Frontend check failed: HTTP $status_code"
    exit 1
fi

# Validate HTML content
if ! echo "$body" | grep -q "<!DOCTYPE html\|<html"; then
    echo "Invalid response: not HTML content"
    exit 1
fi

# Check for Next.js markers (optional, won't fail if missing)
if echo "$body" | grep -q "__NEXT_DATA__"; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Next.js app detected"
    fi
fi

# Verbose output
if [[ "$VERBOSE" == "true" ]]; then
    echo "Frontend URL: $FRONTEND_URL"
    echo "Status Code: $status_code"
    echo "Content Length: $(echo "$body" | wc -c) bytes"
fi

exit 0
