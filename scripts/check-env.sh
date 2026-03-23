#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MISSING=0

check_var() {
  local file="$1" var="$2"
  if ! grep -q "^${var}=.\+" "$file" 2>/dev/null; then
    echo "  MISSING: $var in $file"
    MISSING=$((MISSING + 1))
  fi
}

echo "Checking environment files..."

# --- Backend ---
BACKEND="$REPO_ROOT/src/backend/.env"
if [[ ! -f "$BACKEND" ]]; then
  echo "  MISSING: $BACKEND (run ./scripts/setup-env.sh first)"
  MISSING=$((MISSING + 1))
else
  echo "Backend ($BACKEND):"
  check_var "$BACKEND" "DATABASE_URL"
  check_var "$BACKEND" "SUPABASE_URL"
  check_var "$BACKEND" "SUPABASE_SECRET_KEY"
  check_var "$BACKEND" "OPENAI_API_KEY"
  check_var "$BACKEND" "GEMINI_API_KEY"
  check_var "$BACKEND" "APIFY_API_TOKEN"
fi

# --- Frontend ---
FRONTEND="$REPO_ROOT/src/frontend/.env.local"
if [[ ! -f "$FRONTEND" ]]; then
  echo "  MISSING: $FRONTEND (run ./scripts/setup-env.sh first)"
  MISSING=$((MISSING + 1))
else
  echo "Frontend ($FRONTEND):"
  check_var "$FRONTEND" "NEXT_PUBLIC_SUPABASE_URL"
  check_var "$FRONTEND" "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"
  check_var "$FRONTEND" "NEXT_PUBLIC_API_URL"
fi

# --- Workbench ---
WORKBENCH="$REPO_ROOT/workbench/.env"
if [[ ! -f "$WORKBENCH" ]]; then
  echo "  MISSING: $WORKBENCH (run ./scripts/setup-env.sh first)"
  MISSING=$((MISSING + 1))
else
  echo "Workbench ($WORKBENCH):"
  check_var "$WORKBENCH" "GEMINI_API_KEY"
  check_var "$WORKBENCH" "OPENAI_API_KEY"
fi

echo ""
if [[ $MISSING -gt 0 ]]; then
  echo "FAIL: $MISSING missing variable(s). Fix .env.master and re-run ./scripts/setup-env.sh"
  exit 1
else
  echo "PASS: All required environment variables present."
fi
