# savethetokens

Claude Code skill to reduce token burn with proactive compacting, context pruning, and session hygiene.

## What it does

**savethetokens** is a Claude Code skill that helps you spend fewer tokens per task by:

- Generating budget-aware execution plans
- Proactive compacting before you hit context limits
- Checkpoint files so no work is lost on `/compact` or `/clear`
- Tiered docs — only load details when needed
- Relevance-based context pruning (max 40%, never prunes system prompts or errors)
- Cost/ROI tracking across developers
- A/B telemetry for measuring real savings

Includes 25 Python scripts and 13 reference docs.

## Install

```bash
npx skills add Redclawww/save-the-tokens -g
```

This installs the skill globally and symlinks it to Claude Code (and 30+ other agents). No extra setup needed.

## Uninstall

```bash
npx skills remove savethetokens -g
```

## Prerequisites

- **Python** >= 3.8 (for the skill scripts)

## Quick start

Once installed, use these commands from Claude Code or your terminal:

```bash
# Generate an execution plan with a token budget
python ~/.claude/skills/savethetokens/scripts/govern.py --budget 8000

# Create a checkpoint before compact/clear
python ~/.claude/skills/savethetokens/scripts/session_checkpoint.py \
  --task "implement auth" \
  --done "added JWT middleware" \
  --next "write tests" \
  --context-percent 52

# Optimize your CLAUDE.md
python ~/.claude/skills/savethetokens/scripts/claude_md_optimizer.py --analyze

# Calculate cost savings across a team
python ~/.claude/skills/savethetokens/scripts/cost_calculator.py --developers 5

# Run launch-readiness benchmark
python ~/.claude/skills/savethetokens/scripts/launch_readiness.py
```

## Docs

After install, detailed documentation is available in the skill's `docs/` directory:

- `SESSION_PLAYBOOK.md` — Compact/reset workflow
- `QUALITY_GATES.md` — Code-quality and claim-quality gates
- `BENCHMARK_PROTOCOL.md` — Matched A/B testing process
- `PRUNING_STRATEGIES.md` — How pruning works
- `TOKEN_ESTIMATION.md` — Token counting methods
- `ADVANCED_AUTOMATION.md` — Optional advanced features
- And more

## License

MIT
