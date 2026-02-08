# Benchmark Protocol

Use this protocol to measure whether `savethetokens` helps or hurts on real Claude Code tasks.

## 1) Use matched A/B runs (hard requirement)

- Use the exact same task prompt for both runs.
- Start both runs in fresh sessions.
- Keep model and environment identical.
- Use one run without skill, one run with skill.
- Keep completion target identical (same acceptance criteria and stop condition).

## 2) Keep runs comparable (anti-drift)

- Do not add extra instructions in only one variant.
- Do not change scope mid-run.
- Keep output style comparable (no extra giant tables in only one run).
- Stop when both variants deliver equivalent task completion.

## 3) Enforce behavior controls during both runs

- Use phase-level progress updates only (no per-file narration).
- Do not paste long command output unless explicitly requested.
- Do not rerun identical commands unless code/input changed.
- If retries are needed, batch fixes before re-running tests/build.
- Run `/context` periodically. If usage is high, compact consistently in both runs:
  - checkpoint first
  - then `/compact` around `>= 50%` usage or `messages >= 60k`

## 4) Capture milestone snapshots (not only final)

- Capture `/context` at the same milestones for both variants:
  - `M1`: after scaffold/setup
  - `M2`: after first full test run
  - `M3`: near final completion
- Save raw snapshots as:
  - `control_M1.txt`, `control_M2.txt`, `control_M3.txt`
  - `skill_M1.txt`, `skill_M2.txt`, `skill_M3.txt`

## 5) Compute regression report (final + milestone spot checks)

```bash
# Final milestone comparison (M3)
python ~/.claude/skills/savethetokens/scripts/context_snapshot_diff.py \
  --before-file control_M3.txt \
  --after-file skill_M3.txt \
  --max-total-growth-pct 5 \
  --max-messages-growth-pct 5 \
  --strict
```

Outputs:

- `docs/context_snapshot_diff.json`
- `docs/CONTEXT_SNAPSHOT_DIFF.md`

Repeat the same command for M1 and M2 as spot checks.

## 6) Interpret results

- If `messages` grows significantly while `skills` is almost unchanged, the issue is execution verbosity, not skill-load overhead.
- Treat message-token growth on matched tasks as a regression.
- Do not make public savings claims unless strict evidence gates pass.

## 7) Fix loop if regression appears

- Enforce Lean Mode + message budget rules.
- Reduce progress narration frequency and length.
- Avoid repeated identical commands without code/input changes.
- Use checkpoint + `/compact` at consistent thresholds in both variants.
- Re-run matched A/B until regression clears.
