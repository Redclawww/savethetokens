#!/usr/bin/env python3
"""
Compare two Claude Code /context snapshots and flag token regressions.

Useful for matched A/B tests (without skill vs with skill) where message-token
growth can hide behind tiny skill-token changes.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_NUM_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)")


def _parse_token_value(raw: str) -> Optional[int]:
    match = _NUM_RE.search(raw.replace(",", ""))
    if not match:
        return None

    value = float(match.group(1))
    suffix = match.group(2).lower()
    multiplier = 1
    if suffix == "k":
        multiplier = 1000
    elif suffix == "m":
        multiplier = 1000000
    return int(round(value * multiplier))


def _parse_percent(raw: str) -> Optional[float]:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", raw)
    if not m:
        return None
    return float(m.group(1))


@dataclass
class Snapshot:
    total_used: Optional[int] = None
    total_window: Optional[int] = None
    total_used_pct: Optional[float] = None
    system_prompt: Optional[int] = None
    system_tools: Optional[int] = None
    skills: Optional[int] = None
    messages: Optional[int] = None
    free_space: Optional[int] = None
    autocompact_buffer: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "total_used": self.total_used,
            "total_window": self.total_window,
            "total_used_pct": self.total_used_pct,
            "system_prompt": self.system_prompt,
            "system_tools": self.system_tools,
            "skills": self.skills,
            "messages": self.messages,
            "free_space": self.free_space,
            "autocompact_buffer": self.autocompact_buffer,
        }


def parse_snapshot(text: str) -> Snapshot:
    s = Snapshot()

    total = re.search(
        r"·\s*([0-9.,kKmM]+)\s*/\s*([0-9.,kKmM]+)\s*tokens?\s*\(([^)]+)\)",
        text,
    )
    if total:
        s.total_used = _parse_token_value(total.group(1))
        s.total_window = _parse_token_value(total.group(2))
        s.total_used_pct = _parse_percent(total.group(3))

    field_patterns = {
        "system_prompt": r"System prompt:\s*([0-9.,kKmM]+)\s*tokens?",
        "system_tools": r"System tools:\s*([0-9.,kKmM]+)\s*tokens?",
        "skills": r"Skills:\s*([0-9.,kKmM]+)\s*tokens?",
        "messages": r"Messages:\s*([0-9.,kKmM]+)\s*tokens?",
        "free_space": r"Free space:\s*([0-9.,kKmM]+)",
        "autocompact_buffer": r"Autocompact buffer:\s*([0-9.,kKmM]+)\s*tokens?",
    }

    for field, pattern in field_patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            setattr(s, field, _parse_token_value(m.group(1)))

    return s


def _delta(before: Optional[int], after: Optional[int]) -> dict:
    if before is None or after is None:
        return {"before": before, "after": after, "delta": None, "delta_pct": None}
    delta = after - before
    delta_pct = (delta / before * 100) if before != 0 else None
    return {
        "before": before,
        "after": after,
        "delta": delta,
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
    }


def compare(
    before: Snapshot,
    after: Snapshot,
    *,
    max_total_growth_pct: float,
    max_messages_growth_pct: float,
) -> dict:
    metrics = {
        "total_used": _delta(before.total_used, after.total_used),
        "messages": _delta(before.messages, after.messages),
        "skills": _delta(before.skills, after.skills),
        "free_space": _delta(before.free_space, after.free_space),
        "system_prompt": _delta(before.system_prompt, after.system_prompt),
        "system_tools": _delta(before.system_tools, after.system_tools),
    }

    total_growth_pct = metrics["total_used"]["delta_pct"]
    messages_growth_pct = metrics["messages"]["delta_pct"]

    gates = {
        "total_growth_within_limit": (
            total_growth_pct is None or total_growth_pct <= max_total_growth_pct
        ),
        "messages_growth_within_limit": (
            messages_growth_pct is None
            or messages_growth_pct <= max_messages_growth_pct
        ),
        "messages_not_primary_growth_driver": (
            metrics["messages"]["delta"] is None
            or metrics["skills"]["delta"] is None
            or metrics["messages"]["delta"] <= max(500, metrics["skills"]["delta"] * 20)
        ),
    }

    regression = not all(gates.values())
    likely_cause = "unknown"
    if (
        metrics["messages"]["delta"] is not None
        and metrics["skills"]["delta"] is not None
        and metrics["messages"]["delta"] > 0
        and metrics["messages"]["delta"] > metrics["skills"]["delta"] * 10
    ):
        likely_cause = "message verbosity / repeated retries"
    elif metrics["skills"]["delta"] is not None and metrics["skills"]["delta"] > 1000:
        likely_cause = "skill prompt overhead"

    return {
        "before": before.to_dict(),
        "after": after.to_dict(),
        "metrics": metrics,
        "thresholds": {
            "max_total_growth_pct": max_total_growth_pct,
            "max_messages_growth_pct": max_messages_growth_pct,
        },
        "gates": gates,
        "regression": regression,
        "likely_cause": likely_cause,
    }


def _fmt_change(label: str, m: dict) -> str:
    if m["delta"] is None:
        return f"- {label}: n/a"
    sign = "+" if m["delta"] >= 0 else ""
    pct_sign = "+" if (m["delta_pct"] is not None and m["delta_pct"] >= 0) else ""
    pct = "n/a" if m["delta_pct"] is None else f"{pct_sign}{m['delta_pct']}%"
    return (
        f"- {label}: {m['before']} -> {m['after']} "
        f"({sign}{m['delta']} / {pct})"
    )


def _to_markdown(report: dict) -> str:
    verdict = "REGRESSION" if report["regression"] else "PASS"
    lines = [
        "# Context Snapshot Diff",
        "",
        f"- Verdict: **{verdict}**",
        f"- Likely cause: **{report['likely_cause']}**",
        "",
        "## Key Changes",
        _fmt_change("Total used", report["metrics"]["total_used"]),
        _fmt_change("Messages", report["metrics"]["messages"]),
        _fmt_change("Skills", report["metrics"]["skills"]),
        _fmt_change("Free space", report["metrics"]["free_space"]),
        "",
        "## Gates",
    ]
    for name, passed in report["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} `{name}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two /context snapshots")
    parser.add_argument("--before-file", required=True, help="Path to before snapshot text")
    parser.add_argument("--after-file", required=True, help="Path to after snapshot text")
    parser.add_argument(
        "--max-total-growth-pct",
        type=float,
        default=5.0,
        help="Fail gate if total used grows more than this percentage (default: 5)",
    )
    parser.add_argument(
        "--max-messages-growth-pct",
        type=float,
        default=5.0,
        help="Fail gate if messages grow more than this percentage (default: 5)",
    )
    parser.add_argument(
        "--output-json",
        default="docs/context_snapshot_diff.json",
        help="Output JSON report path",
    )
    parser.add_argument(
        "--output-md",
        default="docs/CONTEXT_SNAPSHOT_DIFF.md",
        help="Output markdown report path",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 when regression is detected",
    )

    args = parser.parse_args()

    before_text = Path(args.before_file).read_text(encoding="utf-8")
    after_text = Path(args.after_file).read_text(encoding="utf-8")

    before = parse_snapshot(before_text)
    after = parse_snapshot(after_text)

    report = compare(
        before,
        after,
        max_total_growth_pct=args.max_total_growth_pct,
        max_messages_growth_pct=args.max_messages_growth_pct,
    )

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_to_markdown(report), encoding="utf-8")

    print(f"Wrote JSON report: {output_json}")
    print(f"Wrote markdown report: {output_md}")
    print(f"Verdict: {'REGRESSION' if report['regression'] else 'PASS'}")

    if args.strict and report["regression"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
