# Session Playbook

Practical workflow to reduce token usage without losing task continuity.

## 1) Start Narrow

- Define one objective per session.
- Load only files needed for that objective.
- For command execution that needs no reasoning, use `! <command>` directly.

Example:

```text
! rg "AuthMiddleware" src/
! npm test -- auth
```

## 2) Work in Chunks

- Split large requests into small, finishable chunks.
- After each chunk, checkpoint progress and decide whether to compact.

## 3) Compact Proactively

- Run `/context` periodically.
- Compact around 50% context usage (or roughly 35-50 messages).
- Do not wait for near-limit sessions.

## 4) Checkpoint Before Compact/Clear

Use:

```bash
python scripts/session_checkpoint.py \
  --task "Implement auth middleware" \
  --done "Added middleware skeleton" \
  --next "Wire middleware in router" \
  --context-percent 54 \
  --message-count 38
```

This writes `.claude/checkpoints/latest.md` with:

- objective
- completed work
- next steps
- decisions and risks
- touched files
- restart prompt

## 5) Reset for Unrelated Work

- If the next task is unrelated, start a fresh chat/session.
- Keep checkpoints and git state so context can be restored quickly when needed.

## 6) Keep Instruction Files Lean

- Keep high-level rules in `CLAUDE.md`.
- Move deep reference material into `docs/*.md`.
- Link to references instead of embedding long sections inline.

## 7) Run Quality Gates Before Final Output

- For code changes, run through `docs/QUALITY_GATES.md`.
- Prefer failing fast on auth/concurrency/validation issues over shipping quickly.
- If a check cannot be run in the environment, state that explicitly in the final response.

## 8) Validate Token Claims With Matched A/B

- Use `docs/BENCHMARK_PROTOCOL.md` for fair control vs optimized runs.
- Treat message-token growth as a regression until fixed.

## 9) Use Advanced Automation Conservatively

- See `docs/ADVANCED_AUTOMATION.md` for safe rollout patterns.
- Enable one advanced feature at a time, then re-measure via matched A/B.
