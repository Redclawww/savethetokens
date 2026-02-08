# Lean Session Prompt

Use this at the start of a Claude Code task when you want strict token discipline.

```text
/savethetokens
Use Lean Mode and strict message budget:
- keep updates phase-level only
- do not paste long command outputs
- do not repeat identical commands without code/input changes
- batch edits before reporting
- final response must include only: changed files, test summary, risks/blockers
```

For measurement runs, use `docs/STRICT_BENCHMARK_PROMPT.md` and pair it with `docs/BENCHMARK_PROTOCOL.md`.
