#!/usr/bin/env bash
# End-to-end test of the Attic local dev flow.
# Requires: local Supabase running, backend running on :8000
#
# Usage: ./scripts/test-flow.sh
#   or:  make test-flow

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS="${GREEN}PASS${NC}"
FAIL="${RED}FAIL${NC}"
FAKE="${YELLOW}FAKE${NC}"
SKIP="${YELLOW}SKIP${NC}"

API_URL="${API_URL:-http://localhost:8000}"
SUPABASE_URL="${SUPABASE_URL:-http://127.0.0.1:54321}"

RESULTS=()
PASSED=0
FAILED=0

check() {
    local name="$1"
    local status="$2"
    local detail="${3:-}"
    RESULTS+=("$name|$status|$detail")
    if [ "$status" = "PASS" ] || [ "$status" = "FAKE" ]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
}

# ---------- Check prerequisites ----------

echo -e "${CYAN}${BOLD}Attic E2E Test Flow${NC}"
echo ""

# Check backend is running
if ! curl -sf "$API_URL/health" >/dev/null 2>&1 && ! curl -sf "$API_URL/docs" >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Backend not running at $API_URL${NC}"
    echo "Start it: cd src/backend && uv run uvicorn app.main:app --reload"
    exit 1
fi

# ---------- 1. Auth login ----------

echo -n "  Testing auth login... "
LOGIN_RESP=$(curl -sf -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "Content-Type: application/json" \
    -H "apikey: $(cd src/backend && grep SUPABASE_SECRET_KEY .env 2>/dev/null | cut -d= -f2 | tr -d '"' || echo '')" \
    -d '{"email":"test@attic.dev","password":"testtest123"}' 2>/dev/null || echo "FAIL")

if echo "$LOGIN_RESP" | grep -q "access_token"; then
    TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    echo -e "$PASS"
    check "Auth login" "PASS" "test@attic.dev"
else
    echo -e "$FAIL"
    check "Auth login" "FAIL" "Could not get access token"
    echo -e "${RED}Cannot continue without auth. Run: make seed${NC}"
    exit 1
fi

# ---------- 2. Dev status ----------

echo -n "  Checking dev status... "
DEV_STATUS=$(curl -sf "$API_URL/api/dev-status" 2>/dev/null || echo "FAIL")
if echo "$DEV_STATUS" | grep -q "environment"; then
    echo -e "$PASS"
    check "Dev status endpoint" "PASS"
else
    echo -e "$SKIP (endpoint may not exist yet)"
    check "Dev status endpoint" "SKIP" "not implemented"
fi

# ---------- 3. Presigned URL ----------

echo -n "  Testing presigned URL... "
PRESIGNED_RESP=$(curl -sf -X POST "$API_URL/api/uploads/presigned-url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"filename":"test-export.zip","content_type":"application/zip"}' 2>/dev/null || echo "FAIL")

if echo "$PRESIGNED_RESP" | grep -q "presigned_url"; then
    UPLOAD_ID=$(echo "$PRESIGNED_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['upload_id'])" 2>/dev/null)
    STORAGE_PATH=$(echo "$PRESIGNED_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['storage_path'])" 2>/dev/null)
    echo -e "$PASS (upload_id: ${UPLOAD_ID:0:8}...)"
    check "Presigned URL" "PASS" "upload_id=$UPLOAD_ID"
else
    echo -e "$FAIL"
    check "Presigned URL" "FAIL" "$PRESIGNED_RESP"
fi

# ---------- 4. Chat endpoint ----------

echo -n "  Testing chat endpoint... "
CHAT_RESP=$(curl -sf -X POST "$API_URL/api/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"hello"}' 2>/dev/null || echo "FAIL")

if [ "$CHAT_RESP" = "FAIL" ]; then
    # Check if it's a config issue (no Anthropic key)
    CHAT_ERR=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/chat" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"message":"hello"}' 2>/dev/null)
    if [ "$CHAT_ERR" = "500" ] || [ "$CHAT_ERR" = "503" ]; then
        echo -e "$SKIP (no ANTHROPIC_API_KEY)"
        check "Chat endpoint" "SKIP" "no API key configured"
    else
        echo -e "$FAIL (HTTP $CHAT_ERR)"
        check "Chat endpoint" "FAIL" "HTTP $CHAT_ERR"
    fi
else
    echo -e "$PASS"
    check "Chat endpoint" "PASS"
fi

# ---------- Summary ----------

echo ""
echo -e "${CYAN}${BOLD}┌────────────────────────────────────────┐${NC}"
echo -e "${CYAN}${BOLD}│       ATTIC E2E TEST RESULTS           │${NC}"
echo -e "${CYAN}${BOLD}├────────────────────────────────────────┤${NC}"

for result in "${RESULTS[@]}"; do
    IFS='|' read -r name status detail <<< "$result"
    case "$status" in
        PASS) icon="$PASS" ;;
        FAIL) icon="$FAIL" ;;
        FAKE) icon="$FAKE" ;;
        SKIP) icon="$SKIP" ;;
        *)    icon="$status" ;;
    esac
    printf "${CYAN}${BOLD}│${NC}  %-24s %b${CYAN}${BOLD}  │${NC}\n" "$name" "$icon"
done

echo -e "${CYAN}${BOLD}├────────────────────────────────────────┤${NC}"
if [ "$FAILED" -eq 0 ]; then
    printf "${CYAN}${BOLD}│${NC}  ${GREEN}${BOLD}%d passed, %d failed${NC}                  ${CYAN}${BOLD}│${NC}\n" "$PASSED" "$FAILED"
else
    printf "${CYAN}${BOLD}│${NC}  ${RED}${BOLD}%d passed, %d failed${NC}                  ${CYAN}${BOLD}│${NC}\n" "$PASSED" "$FAILED"
fi
echo -e "${CYAN}${BOLD}└────────────────────────────────────────┘${NC}"

exit "$FAILED"
