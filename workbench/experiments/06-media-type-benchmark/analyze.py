#!/usr/bin/env python
"""Phase 3: Analyze benchmark results and generate per-media-type matrix.

Reads per-item results from Phase 2, groups by platform × media_type,
computes statistics, and outputs the matrix for UNIT_ECONOMICS.md.

Usage:
    python workbench/experiments/06-media-type-benchmark/analyze.py

    # Include Exp 03 TikTok video data as baseline comparison
    python workbench/experiments/06-media-type-benchmark/analyze.py --include-exp03

Output:
    results/summary.json          — machine-readable aggregate stats
    results/RESULTS.md            — human-readable report with matrix
    stdout                        — markdown table for UNIT_ECONOMICS.md
"""

import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
RESULTS_DIR = SCRIPT_DIR / "results"

# Exp 03 paths for comparison
EXP03_DIR = (
    REPO_ROOT
    / "workbench"
    / "experiments"
    / "03-pipeline-v3"
    / "results"
    / "pipeline_v3"
)


def load_results(stage: str) -> list[dict]:
    """Load all per-item result JSONs for a given stage."""
    stage_dir = RESULTS_DIR / stage
    if not stage_dir.exists():
        return []
    results = []
    for f in stage_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            po = data.get("parsed_output") or {}
            if (
                isinstance(po, dict)
                and not po.get("_error")
                and not po.get("_parse_error")
            ):
                results.append(data)
        except Exception:
            pass
    return results


def load_data_items() -> dict[str, dict]:
    """Load collected data items keyed by ID, to get platform/media_type."""
    items = {}
    for json_file in DATA_DIR.glob("*.json"):
        if json_file.name.startswith("all_items"):
            continue
        for item in json.loads(json_file.read_text()):
            items[item["id"]] = item
    return items


def load_exp03_results(stage: str) -> list[dict]:
    """Load Exp 03 results for baseline comparison."""
    stage_dir = EXP03_DIR / stage
    if not stage_dir.exists():
        return []
    results = []
    for f in stage_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            po = data.get("parsed_output") or {}
            if (
                isinstance(po, dict)
                and not po.get("_error")
                and not po.get("_parse_error")
            ):
                # Add platform/media_type from context or default
                ctx = data.get("context_used", {})
                data["_platform"] = "tiktok"
                data["_media_type"] = (
                    "slideshow" if ctx.get("is_slideshow") else "video"
                )
                results.append(data)
        except Exception:
            pass
    return results


def compute_stats(values: list[float]) -> dict:
    """Compute summary statistics for a list of values."""
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)
    return {
        "n": n,
        "mean": round(statistics.mean(s), 6),
        "median": round(statistics.median(s), 6),
        "p5": round(s[max(0, int(n * 0.05))], 6),
        "p95": round(s[min(n - 1, int(n * 0.95))], 6),
        "min": round(s[0], 6),
        "max": round(s[-1], 6),
    }


def format_cost(v: float) -> str:
    if v < 0.001:
        return f"${v:.5f}"
    return f"${v:.4f}"


def format_time(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def main() -> None:
    include_exp03 = "--include-exp03" in sys.argv

    data_items = load_data_items()
    p1_results = load_results("pass1_perception")
    p2_results = load_results("pass2_classification")

    if not p1_results and not include_exp03:
        print("No results found. Run run_benchmark.py first.")
        sys.exit(1)

    # Optionally include Exp 03 baseline
    if include_exp03:
        exp03_p1 = load_exp03_results("pass1_perception")
        exp03_p2 = load_exp03_results("pass2_classification")
        print(
            f"Loaded {len(exp03_p1)} Exp 03 pass1 + {len(exp03_p2)} pass2 results as baseline"
        )

    # ── Group results by platform × media_type ────────────────────────────

    groups: dict[str, dict] = {}  # key -> {"pass1": [...], "pass2": [...]}

    for r in p1_results:
        pid = r["item_id"]
        ctx = r.get("context_used", {})
        platform = ctx.get("platform", data_items.get(pid, {}).get("platform", "?"))
        media_type = ctx.get(
            "media_type", data_items.get(pid, {}).get("media_type", "?")
        )
        key = f"{platform}_{media_type}"
        groups.setdefault(key, {"pass1": [], "pass2": []})
        groups[key]["pass1"].append(r)

    for r in p2_results:
        pid = r["item_id"]
        ctx = r.get("context_used", {})
        platform = ctx.get("platform", data_items.get(pid, {}).get("platform", "?"))
        media_type = ctx.get(
            "media_type", data_items.get(pid, {}).get("media_type", "?")
        )
        key = f"{platform}_{media_type}"
        groups.setdefault(key, {"pass1": [], "pass2": []})
        groups[key]["pass2"].append(r)

    if include_exp03:
        for r in exp03_p1:
            key = f"{r['_platform']}_{r['_media_type']}"
            # Only add if we don't already have benchmark data for this type
            exp03_key = f"{key}_exp03"
            groups.setdefault(exp03_key, {"pass1": [], "pass2": []})
            groups[exp03_key]["pass1"].append(r)
        for r in exp03_p2:
            key = f"{r['_platform']}_{r['_media_type']}"
            exp03_key = f"{key}_exp03"
            groups.setdefault(exp03_key, {"pass1": [], "pass2": []})
            groups[exp03_key]["pass2"].append(r)

    # ── Compute per-group statistics ──────────────────────────────────────

    summary = {}
    for key in sorted(groups.keys()):
        g = groups[key]
        p1_costs = [r["metrics"]["cost_usd"] for r in g["pass1"]]
        p1_lats = [r["metrics"]["latency_ms"] for r in g["pass1"]]
        p1_in_tok = [r["metrics"]["input_tokens"] for r in g["pass1"]]
        p1_out_tok = [r["metrics"]["output_tokens"] for r in g["pass1"]]

        p2_costs = [r["metrics"]["cost_usd"] for r in g["pass2"]]
        p2_lats = [r["metrics"]["latency_ms"] for r in g["pass2"]]
        p2_in_tok = [r["metrics"]["input_tokens"] for r in g["pass2"]]
        p2_out_tok = [r["metrics"]["output_tokens"] for r in g["pass2"]]

        summary[key] = {
            "pass1_perception": {
                "cost": compute_stats(p1_costs),
                "latency_ms": compute_stats(p1_lats),
                "input_tokens": compute_stats(p1_in_tok),
                "output_tokens": compute_stats(p1_out_tok),
            },
            "pass2_classification": {
                "cost": compute_stats(p2_costs),
                "latency_ms": compute_stats(p2_lats),
                "input_tokens": compute_stats(p2_in_tok),
                "output_tokens": compute_stats(p2_out_tok),
            },
        }

    # ── Save JSON summary ─────────────────────────────────────────────────

    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved summary to {summary_path.relative_to(REPO_ROOT)}")

    # ── Generate markdown matrix ──────────────────────────────────────────

    EMBED_COST = 0.00001

    lines = []
    lines.append("## Per-Media-Type Cost & Time Matrix")
    lines.append("")
    lines.append(
        f"*Generated {__import__('datetime').datetime.now().strftime('%Y-%m-%d')} "
        f"from Exp 06 benchmark results*"
    )
    lines.append("")
    lines.append(
        "| Type | N | Perceive cost | Perceive time | Classify cost | "
        "Classify time | Embed cost | **Gemini total** |"
    )
    lines.append(
        "|------|---|---------------|---------------|---------------|"
        "---------------|------------|------------------|"
    )

    for key in sorted(groups.keys()):
        if key.endswith("_exp03"):
            continue
        s = summary[key]
        p1 = s["pass1_perception"]
        p2 = s["pass2_classification"]
        n = p1["cost"].get("n", 0)
        if n == 0:
            continue

        p1_cost = format_cost(p1["cost"]["mean"])
        p1_time = (
            format_time(p1["latency_ms"]["mean"]) if p1["latency_ms"].get("n") else "—"
        )
        p2_cost = format_cost(p2["cost"]["mean"]) if p2["cost"].get("n") else "—"
        p2_time = (
            format_time(p2["latency_ms"]["mean"]) if p2["latency_ms"].get("n") else "—"
        )

        p1_mean = p1["cost"]["mean"]
        p2_mean = p2["cost"].get("mean", 0)
        total = p1_mean + p2_mean + EMBED_COST

        label = key.replace("_", " ").title()
        lines.append(
            f"| **{label}** | {n} | {p1_cost} | {p1_time} | "
            f"{p2_cost} | {p2_time} | ${EMBED_COST:.5f} | "
            f"**{format_cost(total)}** |"
        )

    # Add Exp 03 baseline if available
    if include_exp03 and "tiktok_video_exp03" in summary:
        s = summary["tiktok_video_exp03"]
        p1 = s["pass1_perception"]
        p2 = s["pass2_classification"]
        n = p1["cost"].get("n", 0)
        if n:
            p1_mean = p1["cost"]["mean"]
            p2_mean = p2["cost"].get("mean", 0)
            total = p1_mean + p2_mean + EMBED_COST
            lines.append(
                f"| *TT video (Exp 03 baseline)* | {n} | "
                f"{format_cost(p1_mean)} | {format_time(p1['latency_ms']['mean'])} | "
                f"{format_cost(p2_mean)} | {format_time(p2['latency_ms']['mean'])} | "
                f"${EMBED_COST:.5f} | *{format_cost(total)}* |"
            )

    lines.append("")
    lines.append("### Detailed Token Usage")
    lines.append("")
    lines.append(
        "| Type | P1 input tok | P1 output tok | P2 input tok | P2 output tok |"
    )
    lines.append("|------|-------------|---------------|-------------|---------------|")

    for key in sorted(groups.keys()):
        if key.endswith("_exp03"):
            continue
        s = summary[key]
        p1 = s["pass1_perception"]
        p2 = s["pass2_classification"]
        if p1["cost"].get("n", 0) == 0:
            continue
        label = key.replace("_", " ").title()
        p1_in = (
            f"{p1['input_tokens'].get('mean', 0):.0f}"
            if p1["input_tokens"].get("n")
            else "—"
        )
        p1_out = (
            f"{p1['output_tokens'].get('mean', 0):.0f}"
            if p1["output_tokens"].get("n")
            else "—"
        )
        p2_in = (
            f"{p2['input_tokens'].get('mean', 0):.0f}"
            if p2["input_tokens"].get("n")
            else "—"
        )
        p2_out = (
            f"{p2['output_tokens'].get('mean', 0):.0f}"
            if p2["output_tokens"].get("n")
            else "—"
        )
        lines.append(f"| {label} | {p1_in} | {p1_out} | {p2_in} | {p2_out} |")

    report = "\n".join(lines)

    # Save report
    report_path = RESULTS_DIR / "RESULTS.md"
    report_path.write_text(report)
    print(f"Saved report to {report_path.relative_to(REPO_ROOT)}")

    # Print to stdout for easy copy-paste
    print(f"\n{'=' * 70}")
    print("COPY THIS INTO docs/UNIT_ECONOMICS.md Section 0:")
    print(f"{'=' * 70}\n")
    print(report)

    # ── Print detailed per-group stats ────────────────────────────────────

    print(f"\n{'=' * 70}")
    print("DETAILED STATS")
    print(f"{'=' * 70}")

    for key in sorted(groups.keys()):
        s = summary[key]
        p1 = s["pass1_perception"]
        n = p1["cost"].get("n", 0)
        if n == 0:
            continue
        print(f"\n--- {key} (N={n}) ---")
        print(
            f"  Pass 1 cost:    mean={format_cost(p1['cost']['mean'])}  "
            f"median={format_cost(p1['cost']['median'])}  "
            f"p95={format_cost(p1['cost']['p95'])}"
        )
        print(
            f"  Pass 1 latency: mean={format_time(p1['latency_ms']['mean'])}  "
            f"median={format_time(p1['latency_ms']['median'])}  "
            f"p95={format_time(p1['latency_ms']['p95'])}"
        )

        p2 = s["pass2_classification"]
        if p2["cost"].get("n", 0):
            print(
                f"  Pass 2 cost:    mean={format_cost(p2['cost']['mean'])}  "
                f"median={format_cost(p2['cost']['median'])}  "
                f"p95={format_cost(p2['cost']['p95'])}"
            )
            print(
                f"  Pass 2 latency: mean={format_time(p2['latency_ms']['mean'])}  "
                f"median={format_time(p2['latency_ms']['median'])}  "
                f"p95={format_time(p2['latency_ms']['p95'])}"
            )


if __name__ == "__main__":
    main()
