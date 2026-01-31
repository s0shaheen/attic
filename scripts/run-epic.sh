#!/bin/bash
#
# Multi-session Epic Orchestrator
#
# Runs each phase of an epic in a separate Claude session to prevent
# context limit issues on large epics.
#
# Usage: ./scripts/run-epic.sh <epic_number> [--dry-run]
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
AUTO_MERGE=""
SKIP_SPECS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --auto-merge)
            AUTO_MERGE="--auto-merge"
            shift
            ;;
        --skip-specs)
            SKIP_SPECS="--skip-specs"
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
    echo "Usage: ./scripts/run-epic.sh <epic_number> [--dry-run] [--auto-merge] [--skip-specs]"
    exit 1
fi

# Validate epic number
if ! [[ "$EPIC" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Error: Epic number must be a positive integer${NC}"
    exit 1
fi

# State management
STATE_DIR=".claude/epic-runs"
mkdir -p "$STATE_DIR"
STATE_FILE="$STATE_DIR/${EPIC}-$(date +%Y%m%d-%H%M%S).json"
LATEST_LINK="$STATE_DIR/${EPIC}-latest.json"

# Initialize state file
init_state() {
    cat > "$STATE_FILE" << EOF
{
  "epic": $EPIC,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "current_phase": "preflight",
  "current_wave": 0,
  "completed_phases": [],
  "waves": {},
  "tasks": {},
  "errors": [],
  "last_updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    # Create/update symlink to latest state file
    ln -sf "$(basename "$STATE_FILE")" "$LATEST_LINK"
}

# Update state file with completed phase
update_state_phase() {
    local phase="$1"
    local status="$2"

    if command -v jq &> /dev/null; then
        local tmp_file=$(mktemp)
        jq --arg phase "$phase" --arg status "$status" --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '.completed_phases += [$phase] | .current_phase = $status | .last_updated = $time' \
            "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
    else
        # Fallback: just update timestamp
        sed -i.bak "s/\"last_updated\": \"[^\"]*\"/\"last_updated\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"/" "$STATE_FILE"
        rm -f "${STATE_FILE}.bak"
    fi
}

# Print section header
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Print phase status
print_phase() {
    local phase_num="$1"
    local phase_name="$2"
    local status="$3"

    case $status in
        "running")
            echo -e "${YELLOW}[Phase ${phase_num}/5] ${phase_name}...${NC}"
            ;;
        "done")
            echo -e "${GREEN}[Phase ${phase_num}/5] ${phase_name} ✓${NC}"
            ;;
        "skipped")
            echo -e "${YELLOW}[Phase ${phase_num}/5] ${phase_name} (skipped)${NC}"
            ;;
        "failed")
            echo -e "${RED}[Phase ${phase_num}/5] ${phase_name} ✗${NC}"
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
print_header "EPIC $EPIC - MULTI-SESSION ORCHESTRATOR"

if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}Running in DRY-RUN mode - no changes will be made${NC}"
    echo ""
fi

# Initialize state
init_state
echo "State file: $STATE_FILE"
echo ""

# ═══════════════════════════════════════════════════════════
# Phase 1: Preflight
# ═══════════════════════════════════════════════════════════
print_phase 1 "Preflight checks" "running"

if ! run_claude "/run-epic $EPIC --phase preflight $DRY_RUN" "Running preflight checks"; then
    print_phase 1 "Preflight checks" "failed"
    echo -e "${RED}Preflight failed. Aborting.${NC}"
    exit 1
fi

update_state_phase "preflight" "specs"
print_phase 1 "Preflight checks" "done"

# ═══════════════════════════════════════════════════════════
# Phase 2: Spec Generation
# ═══════════════════════════════════════════════════════════
print_phase 2 "Generating specs" "running"

if [[ -n "$SKIP_SPECS" ]]; then
    print_phase 2 "Generating specs" "skipped"
else
    if ! run_claude "/generate-specs $EPIC" "Generating spec files"; then
        print_phase 2 "Generating specs" "failed"
        echo -e "${RED}Spec generation failed. Aborting.${NC}"
        exit 1
    fi

    if ! run_claude "/validate-specs $EPIC" "Validating specs"; then
        print_phase 2 "Generating specs" "failed"
        echo -e "${RED}Spec validation failed. Aborting.${NC}"
        exit 1
    fi

    update_state_phase "specs" "implementation"
    print_phase 2 "Generating specs" "done"
fi

# ═══════════════════════════════════════════════════════════
# Phase 3: Implementation (wave by wave)
# ═══════════════════════════════════════════════════════════
print_phase 3 "Implementation" "running"

echo -e "  ${BLUE}→ Discovering waves...${NC}"

# Get the wave list
if [[ -n "$DRY_RUN" ]]; then
    echo -e "  ${YELLOW}[DRY-RUN] Would query waves via: /implement-backlog $EPIC --list-waves${NC}"
    WAVES="1 2 3"  # Example waves for dry-run
else
    # Run claude to get wave list and capture output
    WAVES_OUTPUT=$(claude --dangerously-skip-permissions -p "/implement-backlog $EPIC --list-waves" 2>&1 || true)

    # Extract just the wave numbers (lines that are just digits)
    WAVES=$(echo "$WAVES_OUTPUT" | grep -E '^[0-9]+$' | tr '\n' ' ')

    if [[ -z "$WAVES" ]]; then
        echo -e "  ${YELLOW}No waves found or could not parse wave output${NC}"
        # Fallback: try to implement all at once
        WAVES="all"
    else
        echo -e "  ${GREEN}Found waves: $WAVES${NC}"
    fi
fi

# Execute each wave
for wave in $WAVES; do
    echo ""
    echo -e "  ${BLUE}[Wave $wave]${NC} Implementing..."

    if [[ "$wave" == "all" ]]; then
        run_claude "/implement-backlog $EPIC --parallel $DRY_RUN" "Implementing all tasks"
    else
        run_claude "/implement-backlog $EPIC --wave $wave --parallel $DRY_RUN" "Implementing wave $wave"
    fi

    # Update state with wave progress
    if command -v jq &> /dev/null && [[ -z "$DRY_RUN" ]]; then
        local tmp_file=$(mktemp)
        jq --arg wave "$wave" --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            ".current_wave = ($wave | tonumber) | .waves[\$wave] = {\"status\": \"done\"} | .last_updated = \$time" \
            "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
    fi

    echo -e "  ${GREEN}[Wave $wave] Complete ✓${NC}"
done

update_state_phase "implementation" "ci-merge"
print_phase 3 "Implementation" "done"

# ═══════════════════════════════════════════════════════════
# Phase 4: CI Monitoring & Merge
# ═══════════════════════════════════════════════════════════
print_phase 4 "CI monitoring and merge" "running"

MERGE_ARGS="$DRY_RUN"
if [[ -n "$AUTO_MERGE" ]]; then
    MERGE_ARGS="$MERGE_ARGS $AUTO_MERGE"
fi

if ! run_claude "/run-epic $EPIC --phase ci-merge $MERGE_ARGS" "Creating PRs and monitoring CI"; then
    print_phase 4 "CI monitoring and merge" "failed"
    echo -e "${YELLOW}CI/merge phase had issues. Check state file for details.${NC}"
    # Don't exit - continue to retrospective
fi

update_state_phase "ci-merge" "retrospective"
print_phase 4 "CI monitoring and merge" "done"

# ═══════════════════════════════════════════════════════════
# Phase 5: Retrospective
# ═══════════════════════════════════════════════════════════
print_phase 5 "Retrospective" "running"

if ! run_claude "/run-epic $EPIC --phase retrospective $DRY_RUN" "Generating retrospective"; then
    print_phase 5 "Retrospective" "failed"
fi

update_state_phase "retrospective" "complete"
print_phase 5 "Retrospective" "done"

# ═══════════════════════════════════════════════════════════
# Complete
# ═══════════════════════════════════════════════════════════
print_header "EPIC $EPIC COMPLETE"

echo "State file: $STATE_FILE"
echo ""

if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}This was a dry-run. No changes were made.${NC}"
    echo "To execute for real, run: ./scripts/run-epic.sh $EPIC"
fi
