# Strict Benchmark Prompt (Claude Code)

Use this at the start of BOTH benchmark runs (control and with-skill).
Paste exactly, then append your task prompt.

```text
Benchmark mode enabled. Follow these hard rules for this run:

1) Scope and completion
- Keep scope exactly equal to the provided task.
- Do not add extra features, extra docs, or extra report sections unless asked.
- Stop when acceptance criteria are met; do not continue with optional polish.

2) Communication budget
- Use phase-level updates only (setup, implement, validate, finish).
- Do not narrate every file write.
- Summarize command output in 1-3 lines unless I ask for full output.
- Do not produce long tables in the final response.

3) Retry discipline
- Do not rerun the same command unless code/input changed.
- If a check fails, batch fixes before rerunning.

4) Context discipline
- Run /context at matched milestones:
  M1 after scaffold/setup
  M2 after first full test run
  M3 near final completion
- If context >= 50% OR message tokens >= 60k:
  - create checkpoint summary (done/next/files)
  - run /compact
- Use the same compact policy in both benchmark variants.

5) Deliverable format
- Final response must include only:
  - changed files
  - test/build summary
  - blockers/risks
- Keep final response concise.

Important: optimize for correctness first, then token discipline. If there is a tradeoff, state it explicitly.
```

## Run Notes

- Use the same model and environment for both variants.
- Use identical task prompt and stop criteria.
- Compare snapshots with:

```bash
python ~/.claude/skills/savethetokens/scripts/context_snapshot_diff.py \
  --before-file control_M3.txt \
  --after-file skill_M3.txt \
  --max-total-growth-pct 5 \
  --max-messages-growth-pct 5 \
  --strict
```
