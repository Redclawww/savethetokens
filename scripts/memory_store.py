#!/usr/bin/env python3
"""
Lightweight external memory store for savethetokens.

Design goals:
- Keep memory outside chat context.
- Retrieve only high-signal notes with strict size caps.
- Fail safe: bounded outputs, explicit opt-in for deletions.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import overlap_score


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryNote:
    id: str
    created_at: str
    task: str
    note: str
    tags: list[str]
    priority: int

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "task": self.task,
            "note": self.note,
            "tags": self.tags,
            "priority": self.priority,
        }


def load_notes(path: Path) -> list[MemoryNote]:
    if not path.exists():
        return []
    notes: list[MemoryNote] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        notes.append(
            MemoryNote(
                id=str(obj["id"]),
                created_at=str(obj["created_at"]),
                task=str(obj.get("task", "")),
                note=str(obj.get("note", "")),
                tags=list(obj.get("tags", [])),
                priority=int(obj.get("priority", 1)),
            )
        )
    return notes


def save_notes(path: Path, notes: list[MemoryNote]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for note in notes:
            f.write(json.dumps(note.to_json(), ensure_ascii=True) + "\n")


def format_prompt_memory(notes: list[MemoryNote], max_chars: int) -> str:
    lines = ["Relevant memory notes:"]
    budget = max_chars
    for note in notes:
        text = f"- [{note.id}] task={note.task} tags={','.join(note.tags)} note={note.note}"
        if len(text) + 1 > budget:
            break
        lines.append(text)
        budget -= len(text) + 1
    return "\n".join(lines)


def cmd_add(args: argparse.Namespace) -> int:
    path = Path(args.store).expanduser()
    notes = load_notes(path)
    next_id = str(len(notes) + 1)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    note = MemoryNote(
        id=next_id,
        created_at=utc_now(),
        task=args.task.strip(),
        note=args.note.strip(),
        tags=tags,
        priority=max(1, min(5, args.priority)),
    )
    notes.append(note)
    save_notes(path, notes)
    print(f"Added note id={note.id}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    path = Path(args.store).expanduser()
    notes = load_notes(path)
    ranked = []
    for note in notes:
        searchable = " ".join([note.task, note.note, " ".join(note.tags)])
        score = overlap_score(args.query, searchable) * (1 + (note.priority - 1) * 0.1)
        ranked.append((score, note))
    ranked.sort(key=lambda x: x[0], reverse=True)

    top = [n for s, n in ranked if s > 0][: args.top_k]
    report = {
        "query": args.query,
        "store": str(path),
        "total_notes": len(notes),
        "returned": len(top),
        "results": [
            {
                "id": n.id,
                "task": n.task,
                "tags": n.tags,
                "priority": n.priority,
                "created_at": n.created_at,
            }
            for n in top
        ],
    }

    if args.for_prompt:
        prompt_text = format_prompt_memory(top, max_chars=args.max_chars)
        print(prompt_text)
    else:
        print(json.dumps(report, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    path = Path(args.store).expanduser()
    notes = load_notes(path)
    show = notes[-args.limit :] if args.limit > 0 else notes
    print(
        json.dumps(
            [n.to_json() for n in show],
            indent=2,
        )
    )
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    path = Path(args.store).expanduser()
    notes = load_notes(path)
    if args.keep_last <= 0:
        raise ValueError("--keep-last must be > 0")
    pruned = notes[-args.keep_last :]
    removed = len(notes) - len(pruned)
    if not args.yes:
        print(
            "Refusing to prune without --yes. "
            f"Would remove {removed} notes and keep {len(pruned)}."
        )
        return 1
    save_notes(path, pruned)
    print(f"Pruned store: removed {removed}, kept {len(pruned)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External memory store for savethetokens")
    parser.add_argument(
        "--store",
        default="~/.claude/savethetokens/memory.jsonl",
        help="Memory JSONL file path",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add memory note")
    add.add_argument("--task", required=True, help="Task identifier/title")
    add.add_argument("--note", required=True, help="Memory note content")
    add.add_argument("--tags", default="", help="Comma-separated tags")
    add.add_argument("--priority", type=int, default=3, help="Priority 1-5")
    add.set_defaults(func=cmd_add)

    search = sub.add_parser("search", help="Search relevant memory notes")
    search.add_argument("--query", required=True, help="Current task query")
    search.add_argument("--top-k", type=int, default=5, help="Max notes to return")
    search.add_argument(
        "--for-prompt",
        action="store_true",
        help="Print compact prompt-ready bullets",
    )
    search.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Max character budget for --for-prompt output",
    )
    search.set_defaults(func=cmd_search)

    ls = sub.add_parser("list", help="List memory notes")
    ls.add_argument("--limit", type=int, default=50, help="Show last N notes")
    ls.set_defaults(func=cmd_list)

    prune = sub.add_parser("prune", help="Prune old notes")
    prune.add_argument("--keep-last", type=int, default=500, help="Keep last N notes")
    prune.add_argument("--yes", action="store_true", help="Confirm prune")
    prune.set_defaults(func=cmd_prune)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
