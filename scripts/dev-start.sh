#!/bin/bash
# Attic Local Development - Start All Services
#
# Usage:
#   ./scripts/dev-start.sh
#   ./scripts/dev-start.sh --skip-supabase  # Skip Supabase if already running
#   ./scripts/dev-start.sh --build          # Force rebuild containers
#
# Services started:
# - Supabase (PostgreSQL, Auth, Storage, Studio)
# - LocalStack (S3, SQS, Step Functions, Lambda)
# - Backend API (FastAPI with hot-reload)

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
SKIP_SUPABASE=false
BUILD_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-supabase)
            SKIP_SUPABASE=true
            shift
            ;;
        --build)
            BUILD_FLAG="--build"
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
echo -e "${BLUE}  Attic Local Development Environment  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ---------- Prerequisites Check ----------
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running${NC}"
    echo "Please start Docker Desktop"
    exit 1
fi

if ! command -v supabase &> /dev/null; then
    echo -e "${RED}Error: Supabase CLI is not installed${NC}"
    echo "Please install: brew install supabase/tap/supabase"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# ---------- Start Supabase ----------
if [ "$SKIP_SUPABASE" = false ]; then
    echo -e "${YELLOW}Starting Supabase...${NC}"

    # Check if Supabase is already running
    if supabase status 2>/dev/null | grep -q "API URL"; then
        echo -e "${GREEN}Supabase is already running${NC}"
    else
        supabase start
    fi
    echo ""
else
    echo -e "${YELLOW}Skipping Supabase (--skip-supabase flag)${NC}"
    echo ""
fi

# ---------- Start Docker Services ----------
echo -e "${YELLOW}Starting Docker services (LocalStack, Backend)...${NC}"

docker compose up -d $BUILD_FLAG

echo ""

# ---------- Wait for Services ----------
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"

# Wait for LocalStack
echo -n "  LocalStack: "
RETRIES=30
until curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "running"' 2>/dev/null; do
    RETRIES=$((RETRIES-1))
    if [ $RETRIES -eq 0 ]; then
        echo -e "${RED}TIMEOUT${NC}"
        echo -e "${RED}LocalStack failed to start. Check logs: docker compose logs localstack${NC}"
        exit 1
    fi
    sleep 1
done
echo -e "${GREEN}OK${NC}"

# Wait for Backend
echo -n "  Backend API: "
RETRIES=30
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

# ---------- Print Service URLs ----------
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Services Started Successfully!        ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service URLs:${NC}"
echo "  Frontend:         http://localhost:3000  (start with: cd src/frontend && npm run dev)"
echo "  Backend API:      http://localhost:8000"
echo "  API Docs:         http://localhost:8000/docs"
echo "  Supabase Studio:  http://localhost:54323"
echo "  Supabase API:     http://localhost:54321"
echo "  Supabase DB:      postgresql://postgres:postgres@localhost:54322/postgres"
echo "  LocalStack:       http://localhost:4566"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  View logs:        docker compose logs -f"
echo "  Backend logs:     docker compose logs -f backend"
echo "  LocalStack logs:  docker compose logs -f localstack"
echo "  Supabase logs:    supabase logs"
echo "  Stop services:    ./scripts/dev-stop.sh"
echo "  Reset data:       ./scripts/dev-reset.sh"
echo ""
echo -e "${BLUE}AWS LocalStack Commands:${NC}"
echo "  List S3 buckets:  awslocal s3 ls"
echo "  List SQS queues:  awslocal sqs list-queues"
echo ""
echo -e "${YELLOW}Note: Start frontend separately:${NC}"
echo "  cd src/frontend && npm run dev"
echo ""
