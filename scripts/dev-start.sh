#!/bin/bash
# Attic Local Development - Start All Services
#
# Usage:
#   ./scripts/dev-start.sh                  # Backend + Frontend (default)
#   ./scripts/dev-start.sh --with-localstack # Also start LocalStack (requires Docker)
#   ./scripts/dev-start.sh --backend-only    # Skip frontend
#
# Database: Supabase Cloud (always on, no startup needed)
# Optional: LocalStack for S3/SQS pipeline testing (requires Docker)

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
WITH_LOCALSTACK=false
BACKEND_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-localstack)
            WITH_LOCALSTACK=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: ./scripts/dev-start.sh [--with-localstack] [--backend-only]"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Attic Development Environment        ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ---------- Prerequisites Check ----------
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [[ ! -f "src/backend/.env" ]]; then
    echo -e "${RED}Error: src/backend/.env not found${NC}"
    echo "Run: ./scripts/setup-env.sh"
    exit 1
fi

if [[ ! -f "src/frontend/.env.local" ]]; then
    echo -e "${RED}Error: src/frontend/.env.local not found${NC}"
    echo "Run: ./scripts/setup-env.sh"
    exit 1
fi

echo -e "${GREEN}Env files OK${NC}"
echo ""

# ---------- Check Supabase Connectivity ----------
echo -e "${YELLOW}Checking Supabase connection...${NC}"

SUPABASE_URL=$(grep '^SUPABASE_URL=' src/backend/.env | cut -d= -f2- | tr -d '"')

if [[ -z "$SUPABASE_URL" ]]; then
    echo -e "${RED}Error: SUPABASE_URL not set in src/backend/.env${NC}"
    exit 1
fi

# Use -s --max-time (not -f) — any HTTP response means reachable, even 401
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${SUPABASE_URL}/auth/v1/settings" -H "apikey: dummy" 2>/dev/null | grep -q "^[2-5]"; then
    echo -e "${GREEN}Supabase reachable at ${SUPABASE_URL}${NC}"
else
    echo -e "${YELLOW}WARNING: Cannot reach Supabase at ${SUPABASE_URL}${NC}"
    if [[ "$SUPABASE_URL" == *"localhost"* ]]; then
        echo "Local Supabase detected — run: supabase start"
    else
        echo "Check your internet connection and .env.master values"
    fi
fi
echo ""

# ---------- Run Migrations ----------
echo -e "${YELLOW}Running database migrations...${NC}"
cd "$PROJECT_ROOT/src/backend"
../../.venv/bin/alembic upgrade head 2>&1 | tail -3
cd "$PROJECT_ROOT"
echo ""

# ---------- Start LocalStack (optional) ----------
if [ "$WITH_LOCALSTACK" = true ]; then
    echo -e "${YELLOW}Starting LocalStack...${NC}"

    if ! command -v docker &> /dev/null || ! docker info &> /dev/null 2>&1; then
        echo -e "${YELLOW}WARNING: Docker not running — skipping LocalStack${NC}"
        echo "Start Docker Desktop and re-run with --with-localstack"
    else
        docker compose up -d localstack

        echo -n "  LocalStack: "
        RETRIES=30
        until curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "running"' 2>/dev/null; do
            RETRIES=$((RETRIES-1))
            if [ $RETRIES -eq 0 ]; then
                echo -e "${RED}TIMEOUT${NC}"
                echo -e "${RED}LocalStack failed to start. Check: docker compose logs localstack${NC}"
                break
            fi
            sleep 1
        done
        if [ $RETRIES -gt 0 ]; then
            echo -e "${GREEN}OK${NC}"
        fi
    fi
    echo ""
fi

# ---------- Start Backend ----------
echo -e "${YELLOW}Starting backend...${NC}"
cd "$PROJECT_ROOT/src/backend"
../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd "$PROJECT_ROOT"

echo -n "  Backend API: "
RETRIES=15
until curl -s http://localhost:8000/health 2>/dev/null | grep -q '"status"' 2>/dev/null; do
    RETRIES=$((RETRIES-1))
    if [ $RETRIES -eq 0 ]; then
        echo -e "${YELLOW}PENDING (may still be starting)${NC}"
        break
    fi
    sleep 1
done
if [ $RETRIES -gt 0 ]; then
    echo -e "${GREEN}OK${NC}"
fi
echo ""

# ---------- Start Frontend ----------
if [ "$BACKEND_ONLY" = false ]; then
    echo -e "${YELLOW}Starting frontend...${NC}"
    cd "$PROJECT_ROOT/src/frontend"
    npm run dev &
    FRONTEND_PID=$!
    cd "$PROJECT_ROOT"
    echo ""
fi

# ---------- Print Service URLs ----------
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Services Started Successfully!        ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service URLs:${NC}"
echo "  Backend API:      http://localhost:8000"
echo "  API Docs:         http://localhost:8000/docs"
if [ "$BACKEND_ONLY" = false ]; then
echo "  Frontend:         http://localhost:3000"
fi
echo "  Supabase:         ${SUPABASE_URL} (cloud — always on)"
echo "  Supabase Studio:  https://supabase.com/dashboard"
if [ "$WITH_LOCALSTACK" = true ]; then
echo "  LocalStack:       http://localhost:4566"
fi
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  Stop services:    Ctrl+C or kill backend/frontend PIDs"
echo "  Seed data:        ./scripts/seed-db.sh"
echo "  Run tests:        cd src/backend && ../../.venv/bin/pytest tests/ -x"
echo ""
echo -e "${YELLOW}Test account: test@attic.to / testpassword123${NC}"
echo ""

# Wait for background processes
wait
