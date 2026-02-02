#!/bin/bash
#
# Multi-session Test Generation Orchestrator
#
# Runs each task's test generation in a separate Claude session to prevent
# context limit issues on large epics.
#
# Usage: ./scripts/generate-tests.sh <epic_number> [--dry-run] [--parallel]
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
EPIC=""
DRY_RUN=""
PARALLEL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --parallel)
            PARALLEL="--parallel"
            shift
            ;;
        *)
            if [[ -z "$EPIC" ]]; then
                EPIC="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$EPIC" ]]; then
    echo -e "${RED}Error: Epic number is required${NC}"
    echo "Usage: ./scripts/generate-tests.sh <epic_number> [--dry-run] [--parallel]"
    exit 1
fi

# Validate epic number
if ! [[ "$EPIC" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Error: Epic number must be a positive integer${NC}"
    exit 1
fi

# Print section header
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Print task status
print_task() {
    local task_id="$1"
    local status="$2"

    case $status in
        "running")
            echo -e "${YELLOW}[Task $task_id] Generating tests...${NC}"
            ;;
        "done")
            echo -e "${GREEN}[Task $task_id] Tests generated ✓${NC}"
            ;;
        "failed")
            echo -e "${RED}[Task $task_id] Failed ✗${NC}"
            ;;
    esac
}

# Run a Claude command and capture exit status
run_claude() {
    local prompt="$1"
    local description="$2"

    echo -e "  ${BLUE}→ $description${NC}"

    if [[ -n "$DRY_RUN" ]]; then
        echo -e "  ${YELLOW}[DRY-RUN] Would execute: claude -p \"$prompt\"${NC}"
        return 0
    fi

    if claude --dangerously-skip-permissions -p "$prompt"; then
        return 0
    else
        local exit_code=$?
        echo -e "  ${RED}Command failed with exit code $exit_code${NC}"
        return $exit_code
    fi
}

# Main execution
print_header "GENERATE TESTS - EPIC $EPIC - MULTI-SESSION ORCHESTRATOR"

if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}Running in DRY-RUN mode - no changes will be made${NC}"
    echo ""
fi

# ═══════════════════════════════════════════════════════════
# Step 1: Get list of tasks
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}[Step 1] Discovering tasks...${NC}"

if [[ -n "$DRY_RUN" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN] Would query tasks via: /generate-tests $EPIC --list-tasks${NC}"
    # Example tasks for dry-run
    TASKS="3.1 3.2 3.3 3.13"
    echo -e "  ${YELLOW}[DRY-RUN] Using example tasks: $TASKS${NC}"
else
    # Run claude to get task list and capture output
    TASKS_OUTPUT=$(claude --dangerously-skip-permissions -p "/generate-tests $EPIC --list-tasks" 2>&1 || true)

    # Extract task IDs (lines that match pattern like 3.1, 3.2, etc.)
    TASKS=$(echo "$TASKS_OUTPUT" | grep -E '^[0-9]+\.[0-9]+$' | tr '\n' ' ')

    if [[ -z "$TASKS" ]]; then
        echo -e "${YELLOW}No tasks found or could not parse task output${NC}"
        echo -e "${YELLOW}Raw output was:${NC}"
        echo "$TASKS_OUTPUT"
        exit 1
    else
        echo -e "${GREEN}Found tasks: $TASKS${NC}"
    fi
fi

# Count tasks
TASK_ARRAY=($TASKS)
TASK_COUNT=${#TASK_ARRAY[@]}
echo -e "Total tasks: ${TASK_COUNT}"
echo ""

# ═══════════════════════════════════════════════════════════
# Step 2: Run each task in a fresh session
# ═══════════════════════════════════════════════════════════
echo -e "${BLUE}[Step 2] Generating tests for each task...${NC}"
echo ""

COMPLETED=0
FAILED=0
FAILED_TASKS=""

for task in $TASKS; do
    print_task "$task" "running"

    if run_claude "/generate-tests $EPIC $task $DRY_RUN" "Generating tests for task $task"; then
        print_task "$task" "done"
        ((COMPLETED++))
    else
        print_task "$task" "failed"
        ((FAILED++))
        FAILED_TASKS="$FAILED_TASKS $task"
    fi

    echo ""
done

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print_header "TEST GENERATION COMPLETE"

echo "Epic: $EPIC"
echo "Total tasks: $TASK_COUNT"
echo -e "Completed: ${GREEN}$COMPLETED${NC}"

if [[ $FAILED -gt 0 ]]; then
    echo -e "Failed: ${RED}$FAILED${NC}"
    echo -e "Failed tasks:${FAILED_TASKS}"
fi

echo ""

if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}This was a dry-run. No changes were made.${NC}"
    echo "To execute for real, run: ./scripts/generate-tests.sh $EPIC"
fi
