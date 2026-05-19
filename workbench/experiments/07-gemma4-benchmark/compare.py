#!/usr/bin/env python
"""Compare benchmark results between models.

Reads per-item JSON results from results/{model_a}/ and results/{model_b}/,
produces a comparison report with 4 metric categories:
  1. Classification accuracy (agreement between models)
  2. Cost per item
  3. Latency per item
  4. Schema validity / failure rate

Usage:
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/compare.py
    .venv/bin/python workbench/experiments/07-gemma4-benchmark/compare.py --models gemini-3-flash-preview,gemma-4-27b-it
"""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"


# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------


def load_model_results(model: str) -> dict[str, dict]:
    """Load all per-item results for a model. Returns {item_id: result_dict}."""
    model_dir = RESULTS_DIR / model
    if not model_dir.exists():
        print(f"  WARNING: No results for {model} at {model_dir}")
        return {}
    results = {}
    for path in sorted(model_dir.glob("*.json")):
        data = json.loads(path.read_text())
        results[data["item_id"]] = data
    return results


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_v):
        return sorted_v[f]
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


def stats_summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": 0, "median": 0, "p5": 0, "p95": 0, "min": 0, "max": 0}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 6),
        "median": round(statistics.median(values), 6),
        "p5": round(percentile(values, 5), 6),
        "p95": round(percentile(values, 95), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


# ---------------------------------------------------------------------------
# 1. Classification accuracy (inter-model agreement)
# ---------------------------------------------------------------------------

SINGLE_LABEL_FACETS = [
    "topic",
    "genre",
    "communicative_intent",
    "creator_role",
    "viewer_orientation",
    "content_provenance",
]


def extract_tier1(result: dict) -> dict[str, str]:
    """Extract tier1 labels from a result, either from pre-validated or raw output."""
    t1 = result.get("pass2_classification", {}).get("tier1")
    if isinstance(t1, dict) and t1:
        return t1
    # Fallback: extract from raw parsed_output
    raw = result.get("pass2_classification", {}).get("parsed_output", {})
    if not isinstance(raw, dict) or not raw:
        return {}
    extracted = {}
    for facet in SINGLE_LABEL_FACETS:
        val = raw.get(facet)
        if isinstance(val, dict):
            extracted[facet] = (
                str(val.get("label") or val.get("primary") or "").lower().strip()
            )
        elif isinstance(val, str):
            extracted[facet] = val.lower().strip()
    # affect: dominant label
    affect = raw.get("affect")
    if isinstance(affect, list):
        for entry in affect:
            if isinstance(entry, dict) and entry.get("tier") == "dominant":
                extracted["affect"] = str(entry.get("label", "")).lower().strip()
                break
    # presentation_style: first label
    ps = raw.get("presentation_style")
    if isinstance(ps, list) and ps:
        extracted["presentation_style"] = str(ps[0]).lower().strip()
    elif isinstance(ps, dict):
        extracted["presentation_style"] = str(ps.get("label", "")).lower().strip()
    return extracted


def compute_agreement(results_a: dict, results_b: dict) -> dict:
    """Compute per-facet agreement between two models."""
    common_ids = set(results_a.keys()) & set(results_b.keys())
    facet_match: dict[str, list[bool]] = {
        f: [] for f in SINGLE_LABEL_FACETS + ["affect", "presentation_style"]
    }
    disagreements: dict[str, list[dict]] = {f: [] for f in facet_match}

    for item_id in sorted(common_ids):
        t1_a = extract_tier1(results_a[item_id])
        t1_b = extract_tier1(results_b[item_id])

        for facet in facet_match:
            a_val = t1_a.get(facet, "")
            b_val = t1_b.get(facet, "")
            if not a_val or not b_val:
                continue
            match = a_val == b_val
            facet_match[facet].append(match)
            if not match:
                disagreements[facet].append(
                    {
                        "item_id": item_id,
                        "model_a": a_val,
                        "model_b": b_val,
                    }
                )

    report = {}
    for facet, matches in facet_match.items():
        n = len(matches)
        exact = sum(matches)
        report[facet] = {
            "n": n,
            "exact_match": exact,
            "accuracy_pct": round(100 * exact / n, 1) if n else 0,
            "top_disagreements": disagreements[facet][:5],
        }
    return report


# ---------------------------------------------------------------------------
# 2-4. Cost, latency, schema validity
# ---------------------------------------------------------------------------


def compute_metrics(results: dict) -> dict:
    """Compute aggregate cost, latency, and validity metrics for one model."""
    p1_costs, p2_costs = [], []
    p1_latencies, p2_latencies = [], []
    p1_input_tok, p1_output_tok, p1_thoughts_tok = [], [], []
    p2_input_tok, p2_output_tok, p2_thoughts_tok = [], [], []
    p1_errors, p2_errors = 0, 0
    p2_valid, p2_invalid = 0, 0
    validation_error_counts: Counter = Counter()
    video_upload_success = 0
    video_upload_total = 0
    by_type: dict[str, dict[str, list]] = {}

    for item_id, r in results.items():
        media_type = r.get("type_key", r.get("media_type", "unknown"))
        if media_type not in by_type:
            by_type[media_type] = {
                "p1_cost": [],
                "p2_cost": [],
                "p1_lat": [],
                "p2_lat": [],
            }

        p1 = r.get("pass1_perception", {})
        p2 = r.get("pass2_classification", {})
        p1m = p1.get("metrics", {})
        p2m = p2.get("metrics", {})

        if p1.get("error"):
            p1_errors += 1
        else:
            c = p1m.get("cost_usd", 0)
            lat = p1m.get("latency_ms", 0)
            p1_costs.append(c)
            p1_latencies.append(lat)
            p1_input_tok.append(p1m.get("input_tokens", 0))
            p1_output_tok.append(p1m.get("output_tokens", 0))
            p1_thoughts_tok.append(p1m.get("thoughts_tokens", 0))
            by_type[media_type]["p1_cost"].append(c)
            by_type[media_type]["p1_lat"].append(lat)

        if r.get("media_type") == "video":
            video_upload_total += 1
            if p1m.get("video_uploaded"):
                video_upload_success += 1

        if p2.get("error"):
            p2_errors += 1
        else:
            c = p2m.get("cost_usd", 0)
            lat = p2m.get("latency_ms", 0)
            p2_costs.append(c)
            p2_latencies.append(lat)
            p2_input_tok.append(p2m.get("input_tokens", 0))
            p2_output_tok.append(p2m.get("output_tokens", 0))
            p2_thoughts_tok.append(p2m.get("thoughts_tokens", 0))
            by_type[media_type]["p2_cost"].append(c)
            by_type[media_type]["p2_lat"].append(lat)

            if p2.get("valid"):
                p2_valid += 1
            else:
                p2_invalid += 1
                for err in p2.get("validation_errors", []):
                    validation_error_counts[err] += 1

    return {
        "total_items": len(results),
        "perceive": {
            "cost": stats_summary(p1_costs),
            "latency_ms": stats_summary(p1_latencies),
            "input_tokens": stats_summary(p1_input_tok),
            "output_tokens": stats_summary(p1_output_tok),
            "thoughts_tokens": stats_summary(p1_thoughts_tok),
            "errors": p1_errors,
            "video_upload_rate": (
                f"{video_upload_success}/{video_upload_total}"
                if video_upload_total
                else "n/a"
            ),
        },
        "classify": {
            "cost": stats_summary(p2_costs),
            "latency_ms": stats_summary(p2_latencies),
            "input_tokens": stats_summary(p2_input_tok),
            "output_tokens": stats_summary(p2_output_tok),
            "thoughts_tokens": stats_summary(p2_thoughts_tok),
            "errors": p2_errors,
            "schema_valid": p2_valid,
            "schema_invalid": p2_invalid,
            "validity_pct": round(100 * p2_valid / (p2_valid + p2_invalid), 1)
            if (p2_valid + p2_invalid)
            else 0,
            "top_validation_errors": validation_error_counts.most_common(5),
        },
        "total_cost": round(sum(p1_costs) + sum(p2_costs), 4),
        "by_type": {
            k: {
                "p1_cost": stats_summary(v["p1_cost"]),
                "p2_cost": stats_summary(v["p2_cost"]),
                "p1_latency_ms": stats_summary(v["p1_lat"]),
                "p2_latency_ms": stats_summary(v["p2_lat"]),
            }
            for k, v in by_type.items()
        },
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_markdown(
    model_a: str,
    model_b: str,
    metrics_a: dict,
    metrics_b: dict,
    agreement: dict,
) -> str:
    lines = [
        "# Gemma 4 vs Gemini Flash — Tier 2 Benchmark Results",
        "",
        f"**Model A:** `{model_a}` (reference)",
        f"**Model B:** `{model_b}` (challenger)",
        f"**Items:** {metrics_a['total_items']}",
        "",
    ]

    # 1. Agreement
    lines.append("## 1. Classification Agreement (Model A as reference)")
    lines.append("")
    lines.append("| Facet | N | Exact Match | Agreement % |")
    lines.append("|-------|---|-------------|-------------|")
    overall_matches = 0
    overall_n = 0
    for facet, data in agreement.items():
        lines.append(
            f"| {facet} | {data['n']} | {data['exact_match']} | {data['accuracy_pct']}% |"
        )
        overall_matches += data["exact_match"]
        overall_n += data["n"]
    if overall_n:
        lines.append(
            f"| **Overall** | {overall_n} | {overall_matches} | "
            f"**{round(100 * overall_matches / overall_n, 1)}%** |"
        )
    lines.append("")

    # Top disagreements
    lines.append("### Notable Disagreements")
    lines.append("")
    for facet, data in agreement.items():
        if data["top_disagreements"]:
            lines.append(f"**{facet}:**")
            for d in data["top_disagreements"][:3]:
                lines.append(
                    f"- `{d['item_id']}`: {model_a}={d['model_a']}, {model_b}={d['model_b']}"
                )
            lines.append("")

    # 2. Cost
    lines.append("## 2. Cost Comparison")
    lines.append("")
    lines.append("| Metric | Model A | Model B |")
    lines.append("|--------|---------|---------|")
    for label, key in [
        ("Perceive mean", ("perceive", "cost", "mean")),
        ("Classify mean", ("classify", "cost", "mean")),
        ("Total run cost", ("total_cost",)),
    ]:
        if len(key) == 3:
            va = metrics_a[key[0]][key[1]][key[2]]
            vb = metrics_b[key[0]][key[1]][key[2]]
            lines.append(f"| {label} | ${va:.5f} | ${vb:.5f} |")
        else:
            va = metrics_a[key[0]]
            vb = metrics_b[key[0]]
            lines.append(f"| {label} | ${va:.4f} | ${vb:.4f} |")
    lines.append("")

    # By media type cost
    all_types = sorted(
        set(list(metrics_a["by_type"].keys()) + list(metrics_b["by_type"].keys()))
    )
    if all_types:
        lines.append("### Cost by Media Type")
        lines.append("")
        lines.append("| Type | Model A (P+C) | Model B (P+C) |")
        lines.append("|------|---------------|---------------|")
        for t in all_types:
            a_p = metrics_a["by_type"].get(t, {}).get("p1_cost", {}).get("mean", 0)
            a_c = metrics_a["by_type"].get(t, {}).get("p2_cost", {}).get("mean", 0)
            b_p = metrics_b["by_type"].get(t, {}).get("p1_cost", {}).get("mean", 0)
            b_c = metrics_b["by_type"].get(t, {}).get("p2_cost", {}).get("mean", 0)
            lines.append(f"| {t} | ${a_p + a_c:.5f} | ${b_p + b_c:.5f} |")
        lines.append("")

    # 3. Latency
    lines.append("## 3. Latency Comparison")
    lines.append("")
    lines.append("| Metric | Model A | Model B |")
    lines.append("|--------|---------|---------|")
    for label, stage in [("Perceive", "perceive"), ("Classify", "classify")]:
        for stat in ["mean", "median", "p95"]:
            va = metrics_a[stage]["latency_ms"][stat]
            vb = metrics_b[stage]["latency_ms"][stat]
            lines.append(f"| {label} {stat} | {va:.0f}ms | {vb:.0f}ms |")
    lines.append("")

    # 4. Schema validity
    lines.append("## 4. Schema Validity")
    lines.append("")
    lines.append("| Metric | Model A | Model B |")
    lines.append("|--------|---------|---------|")
    lines.append(
        f"| Valid JSON + ontology | "
        f"{metrics_a['classify']['schema_valid']}/{metrics_a['total_items']} "
        f"({metrics_a['classify']['validity_pct']}%) | "
        f"{metrics_b['classify']['schema_valid']}/{metrics_b['total_items']} "
        f"({metrics_b['classify']['validity_pct']}%) |"
    )
    lines.append(
        f"| Perceive errors | {metrics_a['perceive']['errors']} | {metrics_b['perceive']['errors']} |"
    )
    lines.append(
        f"| Classify errors | {metrics_a['classify']['errors']} | {metrics_b['classify']['errors']} |"
    )
    lines.append(
        f"| Video upload rate | {metrics_a['perceive']['video_upload_rate']} | "
        f"{metrics_b['perceive']['video_upload_rate']} |"
    )
    lines.append("")

    # Token usage
    lines.append("## 5. Token Usage")
    lines.append("")
    lines.append("| Metric | Model A | Model B |")
    lines.append("|--------|---------|---------|")
    for label, stage in [("Perceive", "perceive"), ("Classify", "classify")]:
        for tok_type in ["input_tokens", "output_tokens", "thoughts_tokens"]:
            va = metrics_a[stage][tok_type]["mean"]
            vb = metrics_b[stage][tok_type]["mean"]
            lines.append(
                f"| {label} {tok_type.replace('_', ' ')} (mean) | {va:.0f} | {vb:.0f} |"
            )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated model names (auto-detected from results/ if empty)",
    )
    args = parser.parse_args()

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = sorted(
            [
                d.name
                for d in RESULTS_DIR.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
        )

    if len(models) < 2:
        print(f"Need at least 2 models to compare. Found: {models}")
        print("Run run_benchmark.py first with --models model_a,model_b")
        return

    print("=" * 60)
    print("Benchmark Comparison")
    print("=" * 60)
    print(f"  Models: {', '.join(models)}")

    model_a, model_b = models[0], models[1]
    results_a = load_model_results(model_a)
    results_b = load_model_results(model_b)

    print(f"  {model_a}: {len(results_a)} items")
    print(f"  {model_b}: {len(results_b)} items")

    if not results_a or not results_b:
        print("ERROR: Need results for both models.")
        return

    metrics_a = compute_metrics(results_a)
    metrics_b = compute_metrics(results_b)
    agreement = compute_agreement(results_a, results_b)

    # Write structured data
    comparison = {
        "models": [model_a, model_b],
        "metrics": {model_a: metrics_a, model_b: metrics_b},
        "agreement": agreement,
    }
    comparison_path = SCRIPT_DIR / "comparison.json"
    comparison_path.write_text(json.dumps(comparison, indent=2, default=str))
    print(f"\n  Structured data: {comparison_path}")

    # Write markdown report
    md = generate_markdown(model_a, model_b, metrics_a, metrics_b, agreement)
    results_md_path = SCRIPT_DIR / "RESULTS.md"
    results_md_path.write_text(md)
    print(f"  Report: {results_md_path}")
    print()
    print(md)


if __name__ == "__main__":
    main()
