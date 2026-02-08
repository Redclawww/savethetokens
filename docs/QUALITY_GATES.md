# Quality Gates

Run these gates before finalizing any coding task while using `savethetokens`.

## A) Scope Gate (required)

- Confirm the delivered changes match the explicit user request.
- Remove/avoid unrelated extras (new pages, infra, benchmarks, docs) unless requested.

## B) Correctness Gates (required for backend/API work)

- Authorization gate: protected resources enforce membership/role checks.
- Concurrency gate: optimistic locking updates use atomic `WHERE id=? AND version=?`.
- Validation gate: user inputs fail with 4xx + clear error shape (not generic 500).
- Data integrity gate: cross-entity constraints are enforced (same project, FK expectations).

## C) Code Thoroughness Gate (required for all code tasks)

Token savings must come from message efficiency — never from skipping these checks:

- **Strict config**: strictest compiler/linter mode enabled. Zero `any`, `@ts-ignore`, `@ts-nocheck`.
- **Test coverage**: every touched function has tests (happy path + error path minimum).
- **Safety limits**: runtime loops, recursion, and unbounded input have explicit guards (max steps, depth, timeout).
- **Error quality**: errors carry location info and actionable messages. No silent swallowing.
- **Input validation**: validate at system boundaries (user input, API responses, file I/O).
- **Security**: no injection vectors, no hardcoded secrets, parameterized queries.
- **Build passes**: type-check/compile/build runs clean before declaring done.

## D) Frontend Reliability Gates (required for frontend work)

- Build/type gate: run a compile check or Next build when possible.
- Test gate: run relevant tests for changed components/hooks.
- Config gate: no known warning-level misconfigurations in test/build configs.

## E) Evidence Gate (required when claiming token savings)

- Use matched before/after tasks (same intent and similar complexity).
- Use fresh sessions for both variants.
- Report absolute numbers and percentages.
- Do not claim improvements unless evidence is measured.
- Run `scripts/context_snapshot_diff.py` for quick A/B sanity checks.
- For public claims, require strict telemetry gates:
  - `intent_balanced_coverage`
  - `overall_ci_excludes_zero`
  - `overall_p_value_significant`
  - `optimized_quality_preserved_at_least_95pct`

## F) Final Output Gate (always)

- List what was verified.
- List what could not be verified and why.
- Separate measured facts from assumptions/inference.

## G) Message Efficiency Gate (required for Claude Code sessions)

- Avoid verbose step-by-step narration unless explicitly requested.
- Avoid repeated identical commands with no new input/code changes.
- Summarize command output; include full output only when user asks.
- For matched A/B tasks, treat increased message tokens as a regression signal.

## H) Benchmark Discipline Gate (required for token A/B claims)

- Control and skill variants must use the same prompt, model, environment, and stop criteria.
- Capture `/context` at matched milestones (M1 setup, M2 first full test run, M3 final).
- Use consistent compact policy in both variants (checkpoint first; compact around >=50% or messages >=60k).
- Reject claims if runs are not behavior-matched (scope drift, verbosity drift, retry-pattern drift).

## I) Advanced Automation Safety Gate (required when using advanced features)

- Compact automation must be advisory-first; do not auto-run `/clear` without explicit opt-in.
- Tool filtering must support fail-open behavior for low-confidence scenarios.
- Skill selection must be confidence-gated; low-confidence results are recommendations only.
- Memory retrieval injected into prompts must enforce strict size caps (for example max chars).
