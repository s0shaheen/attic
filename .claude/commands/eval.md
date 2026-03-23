---
description: Run evaluation suite and report quality metrics. Use after making agent/classification/ontology changes.
argument-hint: "[--facet affect] [--save] [--compare path/to/previous.json] [--quick]"
---

## Purpose

This is your quality gate for agent intelligence changes. It runs classification against the golden set and reports per-facet accuracy. Use it after every prompt, ontology, or retrieval change.

## Step 1: Check prerequisites

```bash
# Golden set exists and has entries
GOLDEN="workbench/data/golden-set.json"
if [ ! -f "$GOLDEN" ]; then
    echo "No golden set at $GOLDEN. Create one first."
    echo "Format: [{id, caption, subtitle, hashtags, creator, music, expected: {affect, topic, genre, ...}, notes}]"
    exit 1
fi

COUNT=$(python3 -c "import json; print(len(json.load(open('$GOLDEN'))))")
echo "Golden set: $COUNT items"
```

If golden set is empty or missing → print instructions on how to create one and stop.

## Step 2: Run evals

```bash
# Full eval
.venv/bin/python workbench/scripts/run_evals.py --verbose

# With facet filter
.venv/bin/python workbench/scripts/run_evals.py --facet affect --verbose

# Quick mode (first 10 items only — for fast iteration)
.venv/bin/python workbench/scripts/run_evals.py --limit 10 --verbose

# Save results
.venv/bin/python workbench/scripts/run_evals.py --save --verbose
```

Pass through the user's flags to the script.

## Step 3: Compare (if --compare provided)

If the user provided a previous eval result to compare against:

```bash
.venv/bin/python -c "
import json, sys

current = json.load(open('workbench/evals/results/latest.json'))  # or the --save output
previous = json.load(open(sys.argv[1]))

print('\\n## Comparison')
print(f'Previous: {previous[\"timestamp\"]}')
print(f'Current:  {current[\"timestamp\"]}')
print()

for facet in set(list(current.get('per_facet', {}).keys()) + list(previous.get('per_facet', {}).keys())):
    prev_acc = previous.get('per_facet', {}).get(facet, {}).get('accuracy', 0)
    curr_acc = current.get('per_facet', {}).get(facet, {}).get('accuracy', 0)
    delta = curr_acc - prev_acc
    arrow = '↑' if delta > 0 else '↓' if delta < 0 else '→'
    print(f'  {facet:25s} {prev_acc:.0%} → {curr_acc:.0%}  {arrow} {abs(delta):.0%}')
"
```

## Step 4: Report

```
## Eval Results

Golden set: {N} items
Timestamp: {ISO timestamp}

### Per-Facet Accuracy

| Facet                  | Correct | Total | Accuracy | Δ vs prev |
|------------------------|---------|-------|----------|-----------|
| affect                 | 24      | 30    | 80%      | +5%       |
| topic                  | 27      | 30    | 90%      | —         |
| genre                  | 20      | 30    | 67%      | -3%       |
| communicative_intent   | 22      | 30    | 73%      | +8%       |
| ...                    |         |       |          |           |

**Overall: {N}% ({correct}/{total})**

### Weakest facets (bottom 3)
1. genre (67%) — common misses: "compilation" classified as "reaction"  
2. communicative_intent (73%) — common misses: "sell" classified as "persuade"
3. ...

### Recommendation
{If accuracy improved}: ✅ Quality improved. Safe to ship.
{If accuracy dropped}: ⚠️ Regression detected in {facets}. Review changes before shipping.
{If accuracy unchanged}: → No quality impact. Ship if the change serves another purpose.

{If --save}: Results saved to workbench/evals/results/eval-{timestamp}.json
```

## Troubleshooting

If the eval script doesn't exist yet:
```
The eval script at workbench/scripts/run_evals.py doesn't exist.
Run the dev environment setup guide first, or create it with:
  - Load golden-set.json
  - For each item, call gemini_classify with the metadata
  - Compare tier1 labels against expected
  - Report per-facet accuracy
```

If GOOGLE_API_KEY is missing:
```
GOOGLE_API_KEY not found in workbench/.env.
Run: ./scripts/setup-env.sh (requires .env.master)
```
