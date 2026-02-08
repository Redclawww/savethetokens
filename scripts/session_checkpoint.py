#!/usr/bin/env python3
"""
Session Checkpoint - Save task state before compacting or clearing context.

Creates a lightweight checkpoint file with:
- Task objective
- Completed work
- Next steps
- Key decisions/risks
- Git snapshot (branch + touched files)
- Restart prompt for a fresh session
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _run_git(project_root: Path, args: list[str]) -> tuple[bool, str]:
    """Run git command and return (success, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, ""

    if result.returncode != 0:
        return False, ""

    return True, result.stdout.strip()


def _git_snapshot(project_root: Path) -> dict:
    """Collect branch and file change summary."""
    ok_branch, branch = _run_git(project_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    ok_staged, staged = _run_git(project_root, ["diff", "--cached", "--name-only"])
    ok_unstaged, unstaged = _run_git(project_root, ["diff", "--name-only"])
    ok_untracked, untracked = _run_git(
        project_root, ["ls-files", "--others", "--exclude-standard"]
    )

    staged_files = [line for line in staged.splitlines() if line] if ok_staged else []
    unstaged_files = (
        [line for line in unstaged.splitlines() if line] if ok_unstaged else []
    )
    untracked_files = (
        [line for line in untracked.splitlines() if line] if ok_untracked else []
    )

    touched = sorted(set(staged_files + unstaged_files + untracked_files))

    return {
        "git_available": ok_branch or ok_staged or ok_unstaged or ok_untracked,
        "branch": branch if ok_branch and branch else "(unknown)",
        "staged_files": staged_files,
        "unstaged_files": unstaged_files,
        "untracked_files": untracked_files,
        "touched_files": touched,
    }


def _list_or_placeholder(items: list[str], placeholder: str) -> list[str]:
    """Return list or a single placeholder item."""
    return items if items else [placeholder]


def _compute_hygiene_action(
    context_percent: float | None, message_count: int | None
) -> tuple[str, list[str]]:
    """
    Decide recommended action from context pressure.

    Heuristics:
    - >= 50% context OR >= 35 messages: compact after checkpoint
    - >= 80% context OR >= 55 messages: compact immediately, then clear if switching task
    """
    pct = context_percent if context_percent is not None else 0.0
    msg = message_count if message_count is not None else 0

    if pct >= 80 or msg >= 55:
        return (
            "checkpoint_then_compact_immediately",
            [
                "Write checkpoint file",
                "Run /compact now",
                "If next task is unrelated, run /clear after compact",
            ],
        )

    if pct >= 50 or msg >= 35:
        return (
            "checkpoint_then_compact",
            [
                "Write checkpoint file",
                "Run /compact at the end of this logical chunk",
            ],
        )

    if pct >= 35 or msg >= 25:
        return (
            "prepare_checkpoint",
            [
                "Prepare checkpoint notes now",
                "Run /context every few turns",
                "Compact once context reaches ~50%",
            ],
        )

    return (
        "continue",
        [
            "Keep working in the current session",
            "Use one chat window per task",
        ],
    )


def _restart_prompt(
    checkpoint_path: Path,
    task: str,
    next_steps: list[str],
    touched_files: list[str],
) -> str:
    """Generate restart prompt for a fresh session."""
    file_lines = touched_files[:10]
    files_block = "\n".join(f"- {path}" for path in file_lines) or "- (none)"
    next_block = "\n".join(f"- {step}" for step in next_steps[:6]) or "- (none)"

    return (
        "Continue this task from the saved checkpoint.\n"
        f"1) Read `{checkpoint_path}`.\n"
        f"2) Goal: {task or '(fill task objective)'}.\n"
        "3) Prioritize these next steps:\n"
        f"{next_block}\n"
        "4) Start from these touched files:\n"
        f"{files_block}"
    )


def _to_markdown(
    generated_at: str,
    task: str,
    done: list[str],
    next_steps: list[str],
    decisions: list[str],
    risks: list[str],
    snapshot: dict,
    hygiene_action: str,
    hygiene_steps: list[str],
    restart_prompt: str,
) -> str:
    """Build checkpoint markdown content."""
    lines: list[str] = [
        "# Session Checkpoint",
        "",
        f"- Generated: {generated_at}",
        f"- Branch: {snapshot['branch']}",
        f"- Recommended action: `{hygiene_action}`",
        "",
        "## Objective",
        "",
        task or "(fill objective)",
        "",
        "## Completed",
        "",
    ]

    for item in _list_or_placeholder(done, "(fill completed work)"):
        lines.append(f"- {item}")

    lines.extend(["", "## Next Steps", ""])
    for item in _list_or_placeholder(next_steps, "(fill next step)"):
        lines.append(f"- {item}")

    lines.extend(["", "## Decisions", ""])
    for item in _list_or_placeholder(decisions, "(fill key decision)"):
        lines.append(f"- {item}")

    lines.extend(["", "## Risks / Open Questions", ""])
    for item in _list_or_placeholder(risks, "(fill risk or open question)"):
        lines.append(f"- {item}")

    lines.extend(["", "## Git Snapshot", ""])
    lines.append(f"- Staged files: {len(snapshot['staged_files'])}")
    lines.append(f"- Unstaged files: {len(snapshot['unstaged_files'])}")
    lines.append(f"- Untracked files: {len(snapshot['untracked_files'])}")
    lines.append("")
    lines.append("### Touched Files")
    lines.append("")
    for path in _list_or_placeholder(snapshot["touched_files"], "(none detected)"):
        lines.append(f"- {path}")

    lines.extend(["", "## Token Hygiene", ""])
    for step in hygiene_steps:
        lines.append(f"- {step}")

    lines.extend(["", "## Restart Prompt", "", "```text", restart_prompt, "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a checkpoint file before compacting/clearing context"
    )
    parser.add_argument(
        "--project",
        "-p",
        default=".",
        help="Project root for git snapshot (default: current directory)",
    )
    parser.add_argument(
        "--task",
        "-t",
        default="",
        help="Short task objective for this session",
    )
    parser.add_argument(
        "--done",
        action="append",
        default=[],
        help="Completed item (repeatable)",
    )
    parser.add_argument(
        "--next",
        dest="next_steps",
        action="append",
        default=[],
        help="Next step item (repeatable)",
    )
    parser.add_argument(
        "--decision",
        action="append",
        default=[],
        help="Key decision made (repeatable)",
    )
    parser.add_argument(
        "--risk",
        action="append",
        default=[],
        help="Risk or open question (repeatable)",
    )
    parser.add_argument(
        "--context-percent",
        type=float,
        help="Current context usage percentage from /context",
    )
    parser.add_argument(
        "--message-count",
        type=int,
        help="Approximate messages in current chat",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=".claude/checkpoints/latest.md",
        help="Output checkpoint file",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print checkpoint markdown instead of writing file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON summary after writing",
    )

    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (project_root / output_path).resolve()

    generated_at = datetime.now(timezone.utc).isoformat()
    snapshot = _git_snapshot(project_root)
    action, hygiene_steps = _compute_hygiene_action(
        args.context_percent, args.message_count
    )

    restart_prompt = _restart_prompt(
        output_path, args.task, args.next_steps, snapshot["touched_files"]
    )

    markdown = _to_markdown(
        generated_at=generated_at,
        task=args.task,
        done=args.done,
        next_steps=args.next_steps,
        decisions=args.decision,
        risks=args.risk,
        snapshot=snapshot,
        hygiene_action=action,
        hygiene_steps=hygiene_steps,
        restart_prompt=restart_prompt,
    )

    if args.print_only:
        print(markdown)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)
        print(f"Checkpoint saved: {output_path}")
        print(f"Recommended action: {action}")

    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": generated_at,
                    "checkpoint_file": str(output_path),
                    "project_root": str(project_root),
                    "recommended_action": action,
                    "next_hygiene_steps": hygiene_steps,
                    "branch": snapshot["branch"],
                    "touched_files": snapshot["touched_files"],
                    "touched_file_count": len(snapshot["touched_files"]),
                },
                indent=2,
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
