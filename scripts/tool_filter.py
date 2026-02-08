#!/usr/bin/env python3
"""
Dynamic tool filter with conservative fail-open behavior.

Input schema:
{
  "tools": [
    {"name": "...", "description": "...", "tags": ["..."], "required": false}
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import tokenize, cosine_score


@dataclass
class ToolScore:
    name: str
    score: float
    required: bool
    reason: str
    payload: dict


def score_tool(query: str, tool: dict) -> ToolScore:
    name = str(tool.get("name", "")).strip()
    description = str(tool.get("description", "")).strip()
    tags = tool.get("tags", [])
    tags_text = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags)
    required = bool(tool.get("required", False))

    query_tokens = tokenize(query)
    doc_tokens = tokenize(" ".join([name, description, tags_text]))
    score = cosine_score(query_tokens, doc_tokens)

    reason = "keyword similarity"
    if required:
        reason = "required tool"
        score = max(score, 1.0)

    return ToolScore(
        name=name,
        score=score,
        required=required,
        reason=reason,
        payload=tool,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter tools for a specific task query")
    parser.add_argument("--input", required=True, help="JSON file containing tools[]")
    parser.add_argument("--query", required=True, help="Current task query")
    parser.add_argument("--top-k", type=int, default=8, help="Max non-required tools to keep")
    parser.add_argument("--min-score", type=float, default=0.08, help="Minimum score to keep")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.20,
        help="If best score is below this value and fail-open is enabled, keep all tools",
    )
    parser.add_argument(
        "--fail-open",
        action="store_true",
        help="If confidence is low, return all tools to avoid false negatives",
    )
    parser.add_argument("--output", default="docs/tool_filter_report.json", help="Output report path")

    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    tools = data.get("tools", data if isinstance(data, list) else [])
    if not isinstance(tools, list):
        raise ValueError("Expected list or object with 'tools' list")

    scored = [score_tool(args.query, t) for t in tools]
    scored_sorted = sorted(scored, key=lambda s: s.score, reverse=True)

    best_score = scored_sorted[0].score if scored_sorted else 0.0
    low_confidence = best_score < args.confidence_threshold

    selected: list[ToolScore] = []
    dropped: list[ToolScore] = []

    if args.fail_open and low_confidence:
        selected = scored_sorted
    else:
        required_tools = [s for s in scored_sorted if s.required]
        selected = required_tools[:]

        non_required = [s for s in scored_sorted if not s.required and s.score >= args.min_score]
        selected_names = {s.name for s in selected}
        for s in non_required:
            if s.name not in selected_names and len([x for x in selected if not x.required]) < args.top_k:
                selected.append(s)
                selected_names.add(s.name)

        selected_set = {s.name for s in selected}
        dropped = [s for s in scored_sorted if s.name not in selected_set]

    report = {
        "query": args.query,
        "total_tools": len(scored),
        "selected_count": len(selected),
        "dropped_count": len(dropped),
        "best_score": round(best_score, 4),
        "low_confidence": low_confidence,
        "fail_open_applied": bool(args.fail_open and low_confidence),
        "thresholds": {
            "min_score": args.min_score,
            "confidence_threshold": args.confidence_threshold,
            "top_k": args.top_k,
        },
        "selected_tools": [
            {
                "name": s.name,
                "score": round(s.score, 4),
                "reason": s.reason,
                "required": s.required,
            }
            for s in selected
        ],
        "dropped_tools": [
            {
                "name": s.name,
                "score": round(s.score, 4),
                "required": s.required,
            }
            for s in dropped
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Selected {len(selected)} / {len(scored)} tools")
    print(f"Low confidence: {'yes' if low_confidence else 'no'}")
    if args.fail_open and low_confidence:
        print("Fail-open applied: kept all tools")
    print(f"Wrote report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
