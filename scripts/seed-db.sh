#!/bin/bash
# Seed the Attic database with test data.
#
# Usage: ./scripts/seed-db.sh
# Requires: Supabase reachable (cloud or local)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check env files exist
if [[ ! -f "src/backend/.env" ]]; then
    echo "Error: src/backend/.env not found. Run ./scripts/setup-env.sh first."
    exit 1
fi

# Check Supabase is reachable
SUPABASE_URL=$(grep '^SUPABASE_URL=' src/backend/.env | cut -d= -f2- | tr -d '"')
if [[ -z "$SUPABASE_URL" ]]; then
    echo "Error: SUPABASE_URL not set in src/backend/.env"
    exit 1
fi

# Any HTTP response means reachable (even 401 from dummy apikey)
if ! curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${SUPABASE_URL}/auth/v1/settings" -H "apikey: dummy" 2>/dev/null | grep -q "^[2-5]"; then
    echo "Error: Cannot reach Supabase at ${SUPABASE_URL}"
    if [[ "$SUPABASE_URL" == *"localhost"* ]]; then
        echo "Local Supabase detected — run: supabase start"
    else
        echo "Check your internet connection and .env.master values"
    fi
    exit 1
fi

# Run the Python seed script
echo "Running database seed..."
.venv/bin/python workbench/scripts/seed_db.py

echo ""
echo "You can now login at http://localhost:3000 with:"
echo "  Email: test@attic.to"
echo "  Password: testpassword123"
