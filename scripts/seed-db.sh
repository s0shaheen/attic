#!/bin/bash
# Attic Local Development - Seed Database
#
# Usage:
#   ./scripts/seed-db.sh
#
# This script seeds the local database with test data for development.
# It requires Supabase to be running.
#
# TODO: Implement actual seed data when database schema is finalized
# This will include:
# - Test users (for local auth bypass)
# - Sample uploads
# - Sample media_events with various processing states
# - Sample tags and categories

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Seeding Attic Development Database   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Supabase is running
if ! supabase status 2>/dev/null | grep -q "API URL"; then
    echo -e "${YELLOW}Warning: Supabase is not running${NC}"
    echo "Please start Supabase first: supabase start"
    exit 1
fi

# Supabase connection string for local development
DB_URL="postgresql://postgres:postgres@localhost:54322/postgres"

echo -e "${YELLOW}Note: Database seeding not yet implemented${NC}"
echo ""
echo "When the database schema is finalized, this script will:"
echo "  1. Insert test users for local authentication"
echo "  2. Create sample uploads with various states"
echo "  3. Add sample media_events with enrichment data"
echo "  4. Populate tags and categories for testing"
echo ""
echo "For now, you can manually add test data via Supabase Studio:"
echo "  http://localhost:54323"
echo ""

# Placeholder for future implementation
# Example of how seeding would work:
#
# echo "Inserting test data..."
# psql "$DB_URL" <<EOF
# -- Insert test user (for local development only)
# INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at)
# VALUES (
#     'test-user-00000000-0000-0000-0000-000000000001',
#     'test@example.com',
#     'placeholder',
#     NOW(),
#     NOW(),
#     NOW()
# ) ON CONFLICT (id) DO NOTHING;
#
# -- Insert sample upload
# INSERT INTO uploads (id, user_id, status, filename, created_at)
# VALUES (
#     'test-upload-0000-0000-0000-000000000001',
#     'test-user-00000000-0000-0000-0000-000000000001',
#     'completed',
#     'test_export.zip',
#     NOW()
# ) ON CONFLICT (id) DO NOTHING;
# EOF
# echo "Test data inserted"

echo -e "${GREEN}Seed script executed (placeholder)${NC}"
echo ""
