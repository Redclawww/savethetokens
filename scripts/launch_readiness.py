#!/usr/bin/env python3
"""
Launch Readiness Benchmark for Context Governor.

Runs deterministic scenarios and reports:
- Overall token savings
- Savings by section (filtering, pruning/summarization, tiered startup)
- Quality guardrail outcomes
- Launch readiness gates
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from govern import create_execution_plan


def _blob(label: str, target_tokens: int) -> str:
    """Generate deterministic text with approximately target token volume."""
    sentence = (
        f"{label}: context optimization benchmark content with technical details "
        "about architecture, implementation, risk management, and constraints.\n"
    )
    target_chars = max(80, target_tokens * 4)
    repeats = math.ceil(target_chars / len(sentence))
    return (sentence * repeats)[:target_chars]


def _unit(
    unit_id: str,
    unit_type: str,
    tokens: int,
    priority: int,
    path: str | None = None,
) -> dict:
    data = {
        "id": unit_id,
        "type": unit_type,
        "content": _blob(unit_id, tokens),
        "priority": priority,
    }
    if path:
        data["path"] = path
    return data


@dataclass
class Scenario:
    name: str
    intent: str
    budget: int
    query: str
    units: list[dict]
    expects_filter_savings: bool = False


def _scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="monorepo-codegen-heavy-deps",
            intent="code_generation",
            budget=7000,
            query="implement cache decorator and auth flow",
            expects_filter_savings=True,
            units=[
                _unit("system", "system", 160, 100),
                _unit("instructions", "instruction", 260, 95),
                _unit("user_request", "message", 220, 95),
                _unit("src/auth/service.py", "file", 2300, 85, "src/auth/service.py"),
                _unit("src/cache/decorator.py", "file", 1700, 80, "src/cache/decorator.py"),
                _unit("tests/auth_test.py", "file", 900, 55, "tests/auth_test.py"),
                _unit("docs/API.md", "reference", 1300, 45, "docs/API.md"),
                _unit("history_1", "history", 1500, 25),
                _unit("history_2", "history", 1200, 20),
                _unit("deps_1", "file", 5200, 10, "node_modules/react/index.js"),
                _unit("deps_2", "file", 4300, 10, "dist/bundle.js"),
                _unit("deps_3", "file", 2600, 10, "package-lock.json"),
            ],
        ),
        Scenario(
            name="debugging-incident",
            intent="debugging",
            budget=6500,
            query="fix payment timeout error traceback",
            expects_filter_savings=True,
            units=[
                _unit("system", "system", 160, 100),
                _unit("instructions", "instruction", 240, 95),
                _unit("user_request", "message", 200, 95),
                _unit("error_stack", "error", 1500, 98),
                _unit("src/payment/service.py", "file", 2500, 85, "src/payment/service.py"),
                _unit("src/payment/retry.py", "file", 1400, 75, "src/payment/retry.py"),
                _unit("tool_output_latest", "tool_output", 1100, 80),
                _unit("docs/architecture/payment.md", "reference", 1800, 40, "docs/architecture/payment.md"),
                _unit("old_debug_history", "history", 1700, 20),
                _unit("logs_1", "tool_output", 6000, 5, "logs/app.log"),
                _unit("deps_1", "file", 4200, 10, "node_modules/axios/index.js"),
            ],
        ),
        Scenario(
            name="planning-doc-heavy",
            intent="planning",
            budget=6000,
            query="plan migration strategy and risk matrix",
            expects_filter_savings=True,
            units=[
                _unit("system", "system", 150, 100),
                _unit("instructions", "instruction", 240, 95),
                _unit("user_request", "message", 210, 95),
                _unit("CLAUDE.md", "reference", 2800, 85, "CLAUDE.md"),
                _unit("docs/ARCHITECTURE.md", "reference", 2500, 70, "docs/ARCHITECTURE.md"),
                _unit("docs/API.md", "reference", 1800, 65, "docs/API.md"),
                _unit("docs/CHANGELOG.md", "reference", 3600, 30, "docs/CHANGELOG.md"),
                _unit("docs/HISTORY.md", "reference", 2600, 20, "docs/HISTORY.md"),
                _unit("history_1", "history", 1800, 20),
                _unit("deps_venv", "file", 7200, 5, ".venv/lib/site-packages/a.py"),
                _unit("deps_vendor", "file", 5400, 5, "vendor/pkg/mod.go"),
            ],
        ),
        Scenario(
            name="review-pr-large-artifacts",
            intent="review",
            budget=5500,
            query="review auth changes and edge cases",
            expects_filter_savings=True,
            units=[
                _unit("system", "system", 160, 100),
                _unit("instructions", "instruction", 240, 95),
                _unit("user_request", "message", 220, 95),
                _unit("diff_auth_handler", "diff", 1700, 92, "src/auth/handler.ts"),
                _unit("src/auth/validator.ts", "file", 1400, 80, "src/auth/validator.ts"),
                _unit("src/auth/session.ts", "file", 1300, 78, "src/auth/session.ts"),
                _unit("docs/style-guide.md", "reference", 1100, 55, "docs/style-guide.md"),
                _unit("old_review_thread", "history", 2100, 20),
                _unit("coverage_report", "file", 5200, 8, "coverage/lcov.info"),
                _unit("build_output", "file", 4500, 8, "build/output.js"),
            ],
        ),
    ]


def _run_scenario(scenario: Scenario) -> dict:
    with tempfile.TemporaryDirectory(prefix="cg-bench-") as tmpdir:
        plan = create_execution_plan(
            context_units=scenario.units,
            budget=scenario.budget,
            intent=scenario.intent,
            query=scenario.query,
            target_model="claude-sonnet-4",
            auto_filter_packages=True,
            use_tiered_architecture=True,
            use_relevance_scoring=True,
            track_metrics=False,
            project_root=tmpdir,
        )

    breakdown = plan.get("savings_breakdown", {})
    filter_pct = breakdown.get("package_filtering", {}).get("percentage_of_baseline", 0.0)
    prune_pct = breakdown.get("pruning_and_summarization", {}).get("percentage_of_baseline", 0.0)
    overall_pct = breakdown.get("overall", {}).get("percentage_of_baseline", 0.0)
    tiered_pct = breakdown.get("tiered_startup", {}).get("reduction_percentage", 0.0)
    relevance_waste_pct = breakdown.get("relevance_waste", {}).get("waste_percentage", 0.0)

    checks = {
        "quality_preserved": plan.get("quality_assurance", {}).get("quality_preserved", False),
        "has_session_hygiene": "session_hygiene" in plan,
        "budget_safety_behavior": (
            plan.get("validation", {}).get("within_budget", False)
            or any("exceeds budget" in w.lower() for w in plan.get("warnings", []))
        ),
        "filter_savings_expected": (
            (filter_pct > 0.0) if scenario.expects_filter_savings else True
        ),
    }

    return {
        "scenario": scenario.name,
        "intent": scenario.intent,
        "budget": scenario.budget,
        "statistics": plan.get("statistics", {}),
        "savings_breakdown": breakdown,
        "quality_assurance": plan.get("quality_assurance", {}),
        "validation": plan.get("validation", {}),
        "warnings": plan.get("warnings", []),
        "checks": checks,
        "section_percentages": {
            "package_filtering_pct": round(filter_pct, 1),
            "pruning_summarization_pct": round(prune_pct, 1),
            "overall_pct": round(overall_pct, 1),
            "tiered_startup_pct": round(tiered_pct, 1),
            "relevance_waste_pct": round(relevance_waste_pct, 1),
        },
    }


def _aggregate(results: list[dict]) -> dict:
    def avg(key: str) -> float:
        values = [r["section_percentages"][key] for r in results]
        return round(statistics.mean(values), 1) if values else 0.0

    all_checks = [
        all(r["checks"].values()) for r in results
    ]
    quality_ok = all(r["checks"]["quality_preserved"] for r in results)
    overall_avg = avg("overall_pct")
    filter_avg = avg("package_filtering_pct")
    prune_avg = avg("pruning_summarization_pct")

    # Launch gates (conservative defaults)
    gates = {
        "quality_preserved_all_scenarios": quality_ok,
        "all_core_checks_pass": all(all_checks),
        "average_overall_savings_at_least_35pct": overall_avg >= 35.0,
        "average_pruning_savings_at_least_10pct": prune_avg >= 10.0,
        "average_filter_savings_at_least_10pct": filter_avg >= 10.0,
    }

    ready = all(gates.values())

    return {
        "ready_for_claude_code_launch": ready,
        "averages": {
            "package_filtering_pct": filter_avg,
            "pruning_summarization_pct": prune_avg,
            "overall_pct": overall_avg,
            "tiered_startup_pct": avg("tiered_startup_pct"),
            "relevance_waste_pct": avg("relevance_waste_pct"),
        },
        "gates": gates,
    }


def _to_markdown(report: dict) -> str:
    generated = report["generated_at"]
    summary = report["summary"]
    rows = []
    for r in report["scenarios"]:
        pct = r["section_percentages"]
        rows.append(
            f"| {r['scenario']} | {r['intent']} | {pct['package_filtering_pct']}% | "
            f"{pct['pruning_summarization_pct']}% | {pct['overall_pct']}% | "
            f"{pct['tiered_startup_pct']}% | {pct['relevance_waste_pct']}% | "
            f"{'PASS' if all(r['checks'].values()) else 'FAIL'} |"
        )

    gate_lines = [
        f"- {'PASS' if ok else 'FAIL'} `{name}`"
        for name, ok in summary["gates"].items()
    ]

    return "\n".join(
        [
            "# Launch Readiness Report",
            "",
            f"- Generated: {generated}",
            f"- Ready for Claude Code launch: **{'YES' if summary['ready_for_claude_code_launch'] else 'NO'}**",
            "",
            "## Average Savings by Section",
            "",
            f"- Package filtering: **{summary['averages']['package_filtering_pct']}%**",
            f"- Pruning + summarization: **{summary['averages']['pruning_summarization_pct']}%**",
            f"- Overall end-to-end: **{summary['averages']['overall_pct']}%**",
            f"- Tiered startup reduction (potential): **{summary['averages']['tiered_startup_pct']}%**",
            f"- Relevance waste currently present: **{summary['averages']['relevance_waste_pct']}%**",
            "",
            "## Scenario Results",
            "",
            "| Scenario | Intent | Filter % | Prune % | Overall % | Tiered % | Relevance Waste % | Checks |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
            *rows,
            "",
            "## Launch Gates",
            "",
            *gate_lines,
            "",
            "## Notes",
            "",
            "- `Filter %` = savings from package/dependency filtering.",
            "- `Prune %` = savings from pruning and summarization after filtering.",
            "- `Overall %` = total reduction from baseline to final context.",
            "- `Tiered %` is startup-load reduction potential (Tier 1 only).",
            "- `Relevance Waste %` is low/zero relevance share still present in analyzed context.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run launch readiness benchmarks")
    parser.add_argument(
        "--json-out",
        default="docs/launch_readiness_report.json",
        help="Path to output JSON report",
    )
    parser.add_argument(
        "--md-out",
        default="docs/LAUNCH_READINESS.md",
        help="Path to output Markdown report",
    )
    args = parser.parse_args()

    results = [_run_scenario(s) for s in _scenarios()]
    summary = _aggregate(results)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "scenarios": results,
    }

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2))

    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_to_markdown(report))

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(
        "Ready for Claude Code launch: "
        + ("YES" if summary["ready_for_claude_code_launch"] else "NO")
    )
    print(
        "Average overall savings: "
        + f"{summary['averages']['overall_pct']}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
