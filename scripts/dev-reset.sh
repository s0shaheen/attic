#!/bin/bash
# Attic Local Development - Reset All Data
#
# Usage:
#   ./scripts/dev-reset.sh
#   ./scripts/dev-reset.sh --hard  # Also remove Docker volumes
#
# This script:
# 1. Stops all services
# 2. Removes Docker volumes (LocalStack data)
# 3. Resets Supabase database
# 4. Optionally seeds with test data
# 5. Restarts all services

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
HARD_RESET=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --hard)
            HARD_RESET=true
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
echo -e "${BLUE}  Resetting Attic Local Development    ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}WARNING: This will delete all local data!${NC}"
echo ""
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Aborted${NC}"
    exit 1
fi

echo ""

# ---------- Stop Docker Services ----------
echo -e "${YELLOW}Stopping Docker services...${NC}"
if [ "$HARD_RESET" = true ]; then
    docker compose down -v --remove-orphans
    echo -e "${GREEN}Docker services stopped and volumes removed${NC}"
else
    docker compose down
    echo -e "${GREEN}Docker services stopped${NC}"
fi
echo ""

# ---------- Reset Supabase ----------
echo -e "${YELLOW}Resetting Supabase database...${NC}"
if supabase status 2>/dev/null | grep -q "API URL"; then
    supabase db reset --no-seed
    echo -e "${GREEN}Supabase database reset${NC}"
else
    echo -e "${YELLOW}Supabase not running, starting fresh...${NC}"
    supabase start
fi
echo ""

# ---------- Remove LocalStack Volume (if hard reset) ----------
if [ "$HARD_RESET" = true ]; then
    echo -e "${YELLOW}Removing LocalStack volume...${NC}"
    docker volume rm attic-localstack-data 2>/dev/null || true
    echo -e "${GREEN}LocalStack volume removed${NC}"
    echo ""
fi

# ---------- Restart Services ----------
echo -e "${YELLOW}Restarting services...${NC}"
docker compose up -d --build

echo ""

# ---------- Seed Database (if script exists) ----------
if [ -f "$SCRIPT_DIR/seed-db.sh" ]; then
    echo -e "${YELLOW}Seeding database...${NC}"
    "$SCRIPT_DIR/seed-db.sh"
    echo ""
fi

# ---------- Wait for Services ----------
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"

echo -n "  LocalStack: "
RETRIES=30
until curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "running"' 2>/dev/null; do
    RETRIES=$((RETRIES-1))
    if [ $RETRIES -eq 0 ]; then
        echo -e "${RED}TIMEOUT${NC}"
        break
    fi
    sleep 1
done
if [ $RETRIES -gt 0 ]; then
    echo -e "${GREEN}OK${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Reset Complete!                      ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services are running. Check status with:"
echo "  docker compose ps"
echo "  supabase status"
echo ""
