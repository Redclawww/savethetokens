# Live Telemetry

Run this after collecting real Claude Code sessions for both `control` and `optimized` variants.

## 1) Record experiment sessions

Use deterministic assignment with a stable ticket/task key:

```bash
python ~/.claude/skills/savethetokens/scripts/govern.py \
  --input context.json \
  --budget 8000 \
  --experiment-id claude-launch-v1 \
  --variant auto \
  --assignment-key TICKET-123
```

When a row is assigned to `control`, governor disables package filtering, relevance/tiered assists, and pruning so the run reflects baseline behavior.

## 2) Generate A/B report

```bash
python ~/.claude/skills/savethetokens/scripts/ab_telemetry.py \
  --experiment-id claude-launch-v1 \
  --days 14 \
  --min-samples 20
```

Default intent-balance requirement:

- Required intents: `code_generation,debugging,planning,review`
- Minimum per intent per variant: `5`

Override when needed:

```bash
python ~/.claude/skills/savethetokens/scripts/ab_telemetry.py \
  --experiment-id claude-launch-v1 \
  --required-intents code_generation,debugging,planning,review \
  --min-samples-per-intent 8
```

Outputs:

- `docs/live_telemetry_report.json`
- `docs/LIVE_TELEMETRY.md` (this file, overwritten with measured results)

## Strict Claim Mode

Use `--strict-claim-mode` in CI or release gates to fail with exit code 2 when
claims are not yet supported by the data. Failing gates and intent shortfalls
are printed to stderr-friendly stdout:

```bash
python ~/.claude/skills/savethetokens/scripts/ab_telemetry.py \
  --experiment-id claude-launch-v1 \
  --strict-claim-mode
```

Example failure output:

```
STRICT CLAIM MODE: claim_ready is FALSE — cannot claim measured savings.
Failing gates (2):
  - intent_balanced_coverage
  - overall_ci_excludes_zero
Intent coverage shortfall (min required per variant: 5):
  code_generation: optimized=6, control=3 [MISSING]
  debugging: optimized=5, control=5 [OK]
  planning: optimized=2, control=1 [MISSING]
  review: optimized=5, control=5 [OK]
```

## JSON to stdout

Use `--json-stdout` to print the full report JSON to stdout (in addition to
writing the file). Useful for piping into `jq` or downstream tooling:

```bash
python ~/.claude/skills/savethetokens/scripts/ab_telemetry.py \
  --experiment-id claude-launch-v1 \
  --json-stdout | jq '.summary.claim_ready'
```

Both flags can be combined:

```bash
python ~/.claude/skills/savethetokens/scripts/ab_telemetry.py \
  --experiment-id claude-launch-v1 \
  --strict-claim-mode \
  --json-stdout
```

## Claim Gates

Public claims should only be made when all are true:

- `min_samples_each_variant`
- `intent_balanced_coverage`
- `optimized_beats_control_on_overall_savings`
- `overall_ci_excludes_zero`
- `overall_p_value_significant`
- `optimized_quality_preserved_at_least_95pct`
