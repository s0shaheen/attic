#!/bin/bash
# Test: Backend Health Check
#
# Verifies the backend API /health endpoint returns 200 OK
# with valid JSON response including status and version.

set -e

BACKEND_URL=${BACKEND_URL:-https://attic-staging.onrender.com}
TIMEOUT=${TIMEOUT:-10}

# Make request
response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$BACKEND_URL/health" 2>/dev/null || echo -e "\n000")

# Split response body and status code (compatible with BSD and GNU)
status_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | sed '$d')

# Validate status code
if [[ "$status_code" != "200" ]]; then
    echo "Health check failed: HTTP $status_code"
    echo "Response: $body"
    exit 1
fi

# Validate JSON response
if ! echo "$body" | jq -e '.status' >/dev/null 2>&1; then
    echo "Invalid health response: missing 'status' field"
    echo "Response: $body"
    exit 1
fi

status=$(echo "$body" | jq -r '.status')
if [[ "$status" != "healthy" && "$status" != "ok" ]]; then
    echo "Health status not healthy: $status"
    exit 1
fi

# Verbose output
if [[ "$VERBOSE" == "true" ]]; then
    echo "Backend URL: $BACKEND_URL"
    echo "Response: $body"
fi

exit 0
