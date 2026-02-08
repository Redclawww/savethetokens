#!/usr/bin/env python3
"""
Live A/B telemetry analyzer for Context Governor.

Compares `control` vs `optimized` sessions from recorded metrics and reports:
- Measured token savings by section (filtering, pruning, overall)
- Cost and quality guardrails
- Statistical confidence (bootstrap CI + permutation p-value)
"""

import argparse
import json
import random
import statistics
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from metrics_collector import MetricsCollector, SessionMetrics


DEFAULT_REQUIRED_INTENTS = [
    "code_generation",
    "debugging",
    "planning",
    "review",
]


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.median(values)


def _percentile(values: list[float], pct: float) -> float:
    """Linear interpolation percentile with pct in [0, 100]."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    ordered = sorted(values)
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _bootstrap_diff_ci(
    a: list[float],
    b: list[float],
    *,
    iterations: int,
    alpha: float,
    seed: int = 13
) -> tuple[float, float]:
    """
    Bootstrap CI for mean(a) - mean(b).
    """
    if not a or not b:
        return (0.0, 0.0)

    rng = random.Random(seed)
    diffs: list[float] = []

    for _ in range(iterations):
        sample_a = [a[rng.randrange(len(a))] for _ in range(len(a))]
        sample_b = [b[rng.randrange(len(b))] for _ in range(len(b))]
        diffs.append(_mean(sample_a) - _mean(sample_b))

    low = _percentile(diffs, (alpha / 2) * 100)
    high = _percentile(diffs, (1 - alpha / 2) * 100)
    return (low, high)


def _permutation_p_value(
    a: list[float],
    b: list[float],
    *,
    iterations: int,
    seed: int = 29
) -> float:
    """
    Two-sided permutation test p-value for difference in means.
    """
    if not a or not b:
        return 1.0

    rng = random.Random(seed)
    observed = abs(_mean(a) - _mean(b))
    combined = a + b
    a_size = len(a)
    extreme = 0

    for _ in range(iterations):
        shuffled = combined[:]
        rng.shuffle(shuffled)
        perm_a = shuffled[:a_size]
        perm_b = shuffled[a_size:]
        if abs(_mean(perm_a) - _mean(perm_b)) >= observed:
            extreme += 1

    # Add-one smoothing to avoid zero p-values.
    return (extreme + 1) / (iterations + 1)


def _extract(records: list[SessionMetrics], accessor: Callable[[SessionMetrics], float]) -> list[float]:
    return [float(accessor(r)) for r in records]


def _summarize_group(records: list[SessionMetrics]) -> dict:
    if not records:
        return {
            "sessions": 0,
            "intents": [],
        }

    baselines = _extract(records, lambda r: r.baseline_tokens or r.total_tokens)
    outputs = _extract(records, lambda r: r.output_tokens or r.total_tokens)
    filter_pct = _extract(records, lambda r: r.package_filter_pct)
    prune_pct = _extract(records, lambda r: r.pruning_pct)
    overall_pct = _extract(records, lambda r: r.overall_pct)
    costs = _extract(records, lambda r: r.estimated_cost_usd)
    misses = _extract(records, lambda r: r.context_miss_count)

    quality_rate = (
        sum(1 for r in records if r.quality_preserved) / len(records) * 100
    )
    within_budget_rate = (
        sum(1 for r in records if r.within_budget) / len(records) * 100
    )

    return {
        "sessions": len(records),
        "intents": sorted({r.intent for r in records}),
        "mean_baseline_tokens": round(_mean(baselines), 1),
        "median_baseline_tokens": round(_median(baselines), 1),
        "mean_output_tokens": round(_mean(outputs), 1),
        "median_output_tokens": round(_median(outputs), 1),
        "section_savings_pct": {
            "package_filtering": {
                "mean": round(_mean(filter_pct), 2),
                "median": round(_median(filter_pct), 2),
            },
            "pruning_summarization": {
                "mean": round(_mean(prune_pct), 2),
                "median": round(_median(prune_pct), 2),
            },
            "overall": {
                "mean": round(_mean(overall_pct), 2),
                "median": round(_median(overall_pct), 2),
            },
        },
        "quality_preserved_rate_pct": round(quality_rate, 2),
        "within_budget_rate_pct": round(within_budget_rate, 2),
        "avg_context_miss_count": round(_mean(misses), 3),
        "avg_cost_usd": round(_mean(costs), 6),
    }


def _summarize_by_intent(records: list[SessionMetrics]) -> dict:
    by_intent: dict[str, list[SessionMetrics]] = {}
    for record in records:
        by_intent.setdefault(record.intent or "generic", []).append(record)

    summary = {}
    for intent, rows in sorted(by_intent.items()):
        overall = _extract(rows, lambda r: r.overall_pct)
        filter_pct = _extract(rows, lambda r: r.package_filter_pct)
        prune_pct = _extract(rows, lambda r: r.pruning_pct)
        summary[intent] = {
            "sessions": len(rows),
            "package_filtering_mean_pct": round(_mean(filter_pct), 2),
            "pruning_mean_pct": round(_mean(prune_pct), 2),
            "overall_mean_pct": round(_mean(overall), 2),
        }
    return summary


def _intent_balance_status(
    optimized: list[SessionMetrics],
    control: list[SessionMetrics],
    required_intents: list[str],
    min_samples_per_intent: int
) -> dict:
    """
    Verify that both variants have enough data for each required intent.
    """
    opt_counts: dict[str, int] = {}
    ctrl_counts: dict[str, int] = {}

    for row in optimized:
        key = row.intent or "generic"
        opt_counts[key] = opt_counts.get(key, 0) + 1
    for row in control:
        key = row.intent or "generic"
        ctrl_counts[key] = ctrl_counts.get(key, 0) + 1

    per_intent = {}
    for intent in required_intents:
        opt_n = opt_counts.get(intent, 0)
        ctrl_n = ctrl_counts.get(intent, 0)
        per_intent[intent] = {
            "optimized": opt_n,
            "control": ctrl_n,
            "met": opt_n >= min_samples_per_intent and ctrl_n >= min_samples_per_intent,
        }

    passed = all(v["met"] for v in per_intent.values()) if required_intents else True
    return {
        "required_intents": required_intents,
        "min_samples_per_intent_per_variant": min_samples_per_intent,
        "optimized_counts": opt_counts,
        "control_counts": ctrl_counts,
        "per_intent": per_intent,
        "gate_passed": passed,
    }


def _compare_variants(
    optimized: list[SessionMetrics],
    control: list[SessionMetrics],
    *,
    alpha: float,
    bootstrap_iterations: int,
    permutation_iterations: int
) -> dict:
    opt_overall = _extract(optimized, lambda r: r.overall_pct)
    ctrl_overall = _extract(control, lambda r: r.overall_pct)

    opt_output = _extract(optimized, lambda r: r.output_tokens or r.total_tokens)
    ctrl_output = _extract(control, lambda r: r.output_tokens or r.total_tokens)

    overall_lift = _mean(opt_overall) - _mean(ctrl_overall)
    output_token_delta = _mean(ctrl_output) - _mean(opt_output)  # positive is good
    output_token_delta_pct = (
        (output_token_delta / _mean(ctrl_output) * 100) if _mean(ctrl_output) > 0 else 0.0
    )

    overall_ci_low, overall_ci_high = _bootstrap_diff_ci(
        opt_overall,
        ctrl_overall,
        iterations=bootstrap_iterations,
        alpha=alpha,
    )
    output_ci_low, output_ci_high = _bootstrap_diff_ci(
        ctrl_output,
        opt_output,
        iterations=bootstrap_iterations,
        alpha=alpha,
    )

    overall_p = _permutation_p_value(
        opt_overall,
        ctrl_overall,
        iterations=permutation_iterations,
    )
    output_p = _permutation_p_value(
        ctrl_output,
        opt_output,
        iterations=permutation_iterations,
    )

    return {
        "primary_metric": "overall_savings_pct_mean_difference",
        "overall_savings_lift_pct_points": round(overall_lift, 3),
        "overall_savings_ci_pct_points": {
            "low": round(overall_ci_low, 3),
            "high": round(overall_ci_high, 3),
        },
        "overall_savings_p_value": round(overall_p, 6),
        "output_token_reduction_vs_control": {
            "mean_tokens": round(output_token_delta, 2),
            "mean_pct": round(output_token_delta_pct, 2),
            "ci_tokens": {
                "low": round(output_ci_low, 2),
                "high": round(output_ci_high, 2),
            },
            "p_value": round(output_p, 6),
        },
    }


def _claim_gates(
    optimized_summary: dict,
    control_summary: dict,
    comparison: dict,
    *,
    min_samples: int,
    alpha: float,
    intent_balance_passed: bool,
) -> dict:
    opt_n = optimized_summary.get("sessions", 0)
    ctrl_n = control_summary.get("sessions", 0)

    ci = comparison.get("overall_savings_ci_pct_points", {})
    p_value = comparison.get("overall_savings_p_value", 1.0)
    lift = comparison.get("overall_savings_lift_pct_points", 0.0)

    gates = {
        "min_samples_each_variant": opt_n >= min_samples and ctrl_n >= min_samples,
        "intent_balanced_coverage": intent_balance_passed,
        "optimized_beats_control_on_overall_savings": lift > 0,
        "overall_ci_excludes_zero": ci.get("low", 0.0) > 0,
        "overall_p_value_significant": p_value < alpha,
        "optimized_quality_preserved_at_least_95pct":
            optimized_summary.get("quality_preserved_rate_pct", 0.0) >= 95.0,
    }
    return gates


def _to_markdown(report: dict) -> str:
    summary = report["summary"]
    opt = summary["optimized"]
    ctrl = summary["control"]
    cmpv = summary["comparison"]
    intent_balance = summary.get("intent_balance", {})
    intent_rows = []
    for intent in intent_balance.get("required_intents", []):
        row = intent_balance.get("per_intent", {}).get(intent, {})
        intent_rows.append(
            f"| {intent} | {row.get('optimized', 0)} | {row.get('control', 0)} | "
            f"{'PASS' if row.get('met', False) else 'FAIL'} |"
        )

    gate_lines = [
        f"- {'PASS' if ok else 'FAIL'} `{name}`"
        for name, ok in summary["gates"].items()
    ]

    return "\n".join(
        [
            "# Live Telemetry A/B Report",
            "",
            f"- Generated: {report['generated_at']}",
            f"- Experiment: `{report['experiment_id']}`",
            f"- Ready to claim measured savings publicly: **{'YES' if summary['claim_ready'] else 'NO'}**",
            "",
            "## Sample Size",
            "",
            f"- Optimized sessions: **{opt.get('sessions', 0)}**",
            f"- Control sessions: **{ctrl.get('sessions', 0)}**",
            f"- Window: **{report['window_days']} days**",
            "",
            "## Intent Balance",
            "",
            (
                f"- Required intents: "
                f"`{', '.join(intent_balance.get('required_intents', [])) or 'none'}`"
            ),
            (
                f"- Min samples per intent per variant: "
                f"**{intent_balance.get('min_samples_per_intent_per_variant', 0)}**"
            ),
            "",
            "| Intent | Optimized N | Control N | Coverage |",
            "|---|---:|---:|---|",
            *intent_rows,
            "",
            "## Section Savings (Measured)",
            "",
            "| Variant | Filter Mean % | Prune Mean % | Overall Mean % | Overall Median % |",
            "|---|---:|---:|---:|---:|",
            (
                f"| optimized | {opt.get('section_savings_pct', {}).get('package_filtering', {}).get('mean', 0)} "
                f"| {opt.get('section_savings_pct', {}).get('pruning_summarization', {}).get('mean', 0)} "
                f"| {opt.get('section_savings_pct', {}).get('overall', {}).get('mean', 0)} "
                f"| {opt.get('section_savings_pct', {}).get('overall', {}).get('median', 0)} |"
            ),
            (
                f"| control | {ctrl.get('section_savings_pct', {}).get('package_filtering', {}).get('mean', 0)} "
                f"| {ctrl.get('section_savings_pct', {}).get('pruning_summarization', {}).get('mean', 0)} "
                f"| {ctrl.get('section_savings_pct', {}).get('overall', {}).get('mean', 0)} "
                f"| {ctrl.get('section_savings_pct', {}).get('overall', {}).get('median', 0)} |"
            ),
            "",
            "## Effect Estimate",
            "",
            (
                f"- Overall savings lift vs control: **{cmpv.get('overall_savings_lift_pct_points', 0)} "
                f"percentage points**"
            ),
            (
                f"- 95% CI (overall lift): **[{cmpv.get('overall_savings_ci_pct_points', {}).get('low', 0)}, "
                f"{cmpv.get('overall_savings_ci_pct_points', {}).get('high', 0)}]**"
            ),
            f"- p-value (overall lift): **{cmpv.get('overall_savings_p_value', 1.0)}**",
            (
                f"- Output token reduction vs control (mean): "
                f"**{cmpv.get('output_token_reduction_vs_control', {}).get('mean_tokens', 0)} tokens "
                f"({cmpv.get('output_token_reduction_vs_control', {}).get('mean_pct', 0)}%)**"
            ),
            "",
            "## Claim Gates",
            "",
            *gate_lines,
            "",
            "## Notes",
            "",
            "- Savings percentages are measured from live telemetry rows, not synthetic benchmarks.",
            "- Run this report after collecting enough sessions in both variants.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze live A/B telemetry for Context Governor")
    parser.add_argument("--experiment-id", required=True, help="Experiment ID to analyze")
    parser.add_argument("--days", type=int, default=14, help="Lookback window in days")
    parser.add_argument("--metrics-dir", help="Override metrics directory")
    parser.add_argument("--min-samples", type=int, default=20, help="Min sessions per variant")
    parser.add_argument(
        "--required-intents",
        default=",".join(DEFAULT_REQUIRED_INTENTS),
        help="Comma-separated intents required for claim readiness"
    )
    parser.add_argument(
        "--min-samples-per-intent",
        type=int,
        default=5,
        help="Min sessions per required intent per variant"
    )
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold")
    parser.add_argument("--bootstrap-iterations", type=int, default=3000)
    parser.add_argument("--permutation-iterations", type=int, default=3000)
    parser.add_argument(
        "--json-out",
        default="docs/live_telemetry_report.json",
        help="Path to JSON output"
    )
    parser.add_argument(
        "--md-out",
        default="docs/LIVE_TELEMETRY.md",
        help="Path to Markdown output"
    )
    parser.add_argument(
        "--strict-claim-mode",
        action="store_true",
        default=False,
        help="Exit with code 2 and print failure details when claim_ready is false"
    )
    parser.add_argument(
        "--json-stdout",
        action="store_true",
        default=False,
        help="Print final report JSON to stdout (in addition to file output)"
    )
    args = parser.parse_args()

    collector = MetricsCollector(Path(args.metrics_dir) if args.metrics_dir else None)
    all_rows = collector.load_metrics(days=args.days)

    relevant = [
        row for row in all_rows
        if row.experiment_id == args.experiment_id
        and row.variant in {"control", "optimized"}
    ]
    optimized = [row for row in relevant if row.variant == "optimized"]
    control = [row for row in relevant if row.variant == "control"]

    optimized_summary = _summarize_group(optimized)
    control_summary = _summarize_group(control)
    required_intents = [
        intent.strip()
        for intent in args.required_intents.split(",")
        if intent.strip()
    ]
    intent_balance = _intent_balance_status(
        optimized,
        control,
        required_intents=required_intents,
        min_samples_per_intent=args.min_samples_per_intent,
    )
    comparison = _compare_variants(
        optimized,
        control,
        alpha=args.alpha,
        bootstrap_iterations=args.bootstrap_iterations,
        permutation_iterations=args.permutation_iterations,
    )
    gates = _claim_gates(
        optimized_summary,
        control_summary,
        comparison,
        min_samples=args.min_samples,
        alpha=args.alpha,
        intent_balance_passed=intent_balance["gate_passed"],
    )
    claim_ready = all(gates.values())

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": args.experiment_id,
        "window_days": args.days,
        "parameters": {
            "alpha": args.alpha,
            "min_samples": args.min_samples,
            "required_intents": required_intents,
            "min_samples_per_intent": args.min_samples_per_intent,
            "bootstrap_iterations": args.bootstrap_iterations,
            "permutation_iterations": args.permutation_iterations,
        },
        "summary": {
            "claim_ready": claim_ready,
            "optimized": optimized_summary,
            "control": control_summary,
            "intent_balance": intent_balance,
            "comparison": comparison,
            "gates": gates,
        },
        "by_intent": {
            "optimized": _summarize_by_intent(optimized),
            "control": _summarize_by_intent(control),
        },
        "raw_counts": {
            "all_loaded_rows": len(all_rows),
            "matching_experiment_rows": len(relevant),
            "optimized_rows": len(optimized),
            "control_rows": len(control),
        },
        "sample_rows_preview": [asdict(row) for row in relevant[:5]],
    }

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2))

    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_to_markdown(report))

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(f"Experiment: {args.experiment_id}")
    print(f"Optimized sessions: {optimized_summary.get('sessions', 0)}")
    print(f"Control sessions: {control_summary.get('sessions', 0)}")
    print(f"Claim ready: {'YES' if claim_ready else 'NO'}")

    if args.json_stdout:
        print(json.dumps(report, indent=2))

    if args.strict_claim_mode and not claim_ready:
        failing = [name for name, ok in gates.items() if not ok]
        print("")
        print("STRICT CLAIM MODE: claim_ready is FALSE — cannot claim measured savings.")
        print(f"Failing gates ({len(failing)}):")
        for gate_name in failing:
            print(f"  - {gate_name}")
        if "intent_balanced_coverage" in failing:
            print("")
            print("Intent coverage shortfall (min required per variant: "
                  f"{args.min_samples_per_intent}):")
            for intent in required_intents:
                info = intent_balance.get("per_intent", {}).get(intent, {})
                opt_n = info.get("optimized", 0)
                ctrl_n = info.get("control", 0)
                status = "OK" if info.get("met", False) else "MISSING"
                print(f"  {intent}: optimized={opt_n}, control={ctrl_n} [{status}]")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
