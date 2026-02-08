#!/usr/bin/env python3
"""
Semantic skill selector for on-demand loading recommendations.

Conservative behavior:
- Returns ranked candidates.
- Marks auto-activation as unsafe when confidence is low.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import tokenize, cosine_score


def parse_skill_frontmatter(skill_md: Path) -> dict | None:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    front = parts[1]

    name = None
    description = None
    for line in front.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip()
    if not name:
        return None
    return {
        "name": name,
        "description": description or "",
        "path": str(skill_md.parent),
    }


def discover_skills(roots: list[Path]) -> list[dict]:
    found: list[dict] = []
    seen_paths: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for skill_md in root.rglob("SKILL.md"):
            info = parse_skill_frontmatter(skill_md)
            if not info:
                continue
            key = info["path"]
            if key in seen_paths:
                continue
            seen_paths.add(key)
            found.append(info)
    return found


def load_skills(input_file: Path | None, roots: list[Path]) -> list[dict]:
    if input_file:
        data = json.loads(input_file.read_text(encoding="utf-8"))
        skills = data.get("skills", data if isinstance(data, list) else [])
        if not isinstance(skills, list):
            raise ValueError("Expected list or object with 'skills' list")
        return skills
    return discover_skills(roots)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank relevant skills for a task query")
    parser.add_argument("--query", required=True, help="Current task query")
    parser.add_argument("--input", help="Optional JSON file containing skills[]")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=["~/.claude/skills", ".claude/skills"],
        help="Skill root directories to scan when --input is not provided",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Max skills to return")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.18,
        help="Minimum top score to consider auto-activation",
    )
    parser.add_argument(
        "--margin-threshold",
        type=float,
        default=0.05,
        help="Top1-top2 score margin required for auto-activation",
    )
    parser.add_argument("--output", default="docs/skill_selector_report.json", help="Output report path")
    args = parser.parse_args()

    roots = [Path(r).expanduser() for r in args.roots]
    input_file = Path(args.input).expanduser() if args.input else None
    skills = load_skills(input_file, roots)

    query_tokens = tokenize(args.query)
    ranked = []
    for skill in skills:
        name = str(skill.get("name", "")).strip()
        desc = str(skill.get("description", "")).strip()
        doc_tokens = tokenize(f"{name} {desc}")
        score = cosine_score(query_tokens, doc_tokens)
        ranked.append(
            {
                "name": name,
                "description": desc,
                "path": skill.get("path"),
                "score": score,
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    top = ranked[: args.top_k]

    top1 = top[0]["score"] if len(top) >= 1 else 0.0
    top2 = top[1]["score"] if len(top) >= 2 else 0.0
    margin = top1 - top2

    auto_activation_safe = (
        top1 >= args.confidence_threshold and margin >= args.margin_threshold
    )

    report = {
        "query": args.query,
        "total_skills": len(skills),
        "top_k": args.top_k,
        "confidence": {
            "top1": round(top1, 4),
            "top2": round(top2, 4),
            "margin": round(margin, 4),
            "thresholds": {
                "confidence_threshold": args.confidence_threshold,
                "margin_threshold": args.margin_threshold,
            },
            "auto_activation_safe": auto_activation_safe,
        },
        "recommended_skills": [
            {
                "name": r["name"],
                "score": round(r["score"], 4),
                "path": r.get("path"),
                "description": r["description"],
            }
            for r in top
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Ranked {len(skills)} skills")
    print(f"Top recommendation: {top[0]['name'] if top else 'none'}")
    print(f"Auto-activation safe: {'yes' if auto_activation_safe else 'no'}")
    print(f"Wrote report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
