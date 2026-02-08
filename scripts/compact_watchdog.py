#!/usr/bin/env python3
"""
Compact watchdog for Claude Code /context snapshots.

This script is intentionally conservative:
- Recommends actions; does not execute slash commands.
- Never emits /clear unless explicitly allowed.
- Can require an existing checkpoint before command emission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from context_snapshot_diff import parse_snapshot


def decide_action(
    used_pct: float | None,
    message_tokens: int | None,
    *,
    warn_pct: float,
    compact_pct: float,
    clear_pct: float,
    compact_message_tokens: int,
    allow_clear: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if used_pct is None and message_tokens is None:
        return ("insufficient_data", ["Could not parse usage metrics from /context snapshot"])

    if used_pct is not None:
        reasons.append(f"context_used_pct={used_pct:.1f}%")
    if message_tokens is not None:
        reasons.append(f"messages_tokens={message_tokens}")

    if (
        allow_clear
        and used_pct is not None
        and used_pct >= clear_pct
    ):
        return ("checkpoint_then_clear", reasons + ["High context pressure above clear threshold"])

    if (
        (used_pct is not None and used_pct >= compact_pct)
        or (message_tokens is not None and message_tokens >= compact_message_tokens)
    ):
        return ("checkpoint_then_compact", reasons + ["Context pressure above compact threshold"])

    if used_pct is not None and used_pct >= warn_pct:
        return ("monitor", reasons + ["Near compact threshold; prepare checkpoint"])

    return ("continue", reasons + ["Context pressure is acceptable"])


def command_for_action(action: str) -> str | None:
    mapping = {
        "checkpoint_then_compact": "/compact",
        "checkpoint_then_clear": "/clear",
    }
    return mapping.get(action)


def main() -> int:
    parser = argparse.ArgumentParser(description="Advise safe /compact or /clear actions")
    parser.add_argument("--context-file", required=True, help="Path to raw /context output text")
    parser.add_argument("--warn-pct", type=float, default=50.0, help="Warn threshold (default: 50)")
    parser.add_argument("--compact-pct", type=float, default=65.0, help="Compact threshold (default: 65)")
    parser.add_argument("--clear-pct", type=float, default=85.0, help="Clear threshold (default: 85)")
    parser.add_argument(
        "--compact-message-tokens",
        type=int,
        default=60000,
        help="Compact when message bucket exceeds this token count (default: 60000)",
    )
    parser.add_argument(
        "--allow-clear",
        action="store_true",
        help="Allow /clear recommendation when thresholds are exceeded",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=".claude/checkpoints/latest.md",
        help="Checkpoint file path required before command emission",
    )
    parser.add_argument(
        "--require-checkpoint",
        action="store_true",
        help="Require checkpoint file before emitting command",
    )
    parser.add_argument(
        "--emit-command-file",
        help="Write recommended slash command (/compact or /clear) to this file",
    )
    parser.add_argument(
        "--output-json",
        default="docs/compact_watchdog_report.json",
        help="Write machine-readable watchdog report to JSON",
    )

    args = parser.parse_args()

    context_text = Path(args.context_file).read_text(encoding="utf-8")
    snapshot = parse_snapshot(context_text)

    action, reasons = decide_action(
        snapshot.total_used_pct,
        snapshot.messages,
        warn_pct=args.warn_pct,
        compact_pct=args.compact_pct,
        clear_pct=args.clear_pct,
        compact_message_tokens=args.compact_message_tokens,
        allow_clear=args.allow_clear,
    )

    checkpoint_path = Path(args.checkpoint_file)
    checkpoint_exists = checkpoint_path.exists()
    command = command_for_action(action)
    command_emitted = False
    emit_reason = None

    if args.emit_command_file and command:
        if args.require_checkpoint and not checkpoint_exists:
            emit_reason = (
                "Command emission blocked because checkpoint is required but missing. "
                f"Expected: {checkpoint_path}"
            )
        elif command == "/clear" and not args.allow_clear:
            emit_reason = "Command emission blocked because /clear is disabled by default"
        else:
            out_path = Path(args.emit_command_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(f"{command}\n", encoding="utf-8")
            command_emitted = True
            emit_reason = f"Emitted command to {out_path}"

    report = {
        "action": action,
        "reasons": reasons,
        "recommended_command": command,
        "checkpoint_required": args.require_checkpoint,
        "checkpoint_file": str(checkpoint_path),
        "checkpoint_exists": checkpoint_exists,
        "command_emitted": command_emitted,
        "emission_note": emit_reason,
        "thresholds": {
            "warn_pct": args.warn_pct,
            "compact_pct": args.compact_pct,
            "clear_pct": args.clear_pct,
            "compact_message_tokens": args.compact_message_tokens,
        },
        "snapshot": snapshot.to_dict(),
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Action: {action}")
    print("Reasons:")
    for reason in reasons:
        print(f"- {reason}")
    if command:
        print(f"Recommended command: {command}")
    if emit_reason:
        print(emit_reason)
    print(f"Wrote report: {output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
