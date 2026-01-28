#!/bin/bash
# Attic Local Development - Stop All Services
#
# Usage:
#   ./scripts/dev-stop.sh
#   ./scripts/dev-stop.sh --keep-supabase  # Keep Supabase running
#
# Stops:
# - Docker Compose services (LocalStack, Backend)
# - Supabase (PostgreSQL, Auth, Storage, Studio)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
KEEP_SUPABASE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-supabase)
            KEEP_SUPABASE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Stopping Attic Local Development     ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ---------- Stop Docker Services ----------
echo -e "${YELLOW}Stopping Docker services...${NC}"
docker compose down
echo -e "${GREEN}Docker services stopped${NC}"
echo ""

# ---------- Stop Supabase ----------
if [ "$KEEP_SUPABASE" = false ]; then
    echo -e "${YELLOW}Stopping Supabase...${NC}"
    if supabase status 2>/dev/null | grep -q "API URL"; then
        supabase stop
        echo -e "${GREEN}Supabase stopped${NC}"
    else
        echo -e "${GREEN}Supabase was not running${NC}"
    fi
else
    echo -e "${YELLOW}Keeping Supabase running (--keep-supabase flag)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services stopped                 ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
