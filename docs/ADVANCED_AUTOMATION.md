# Advanced Automation (Safe Defaults)

This page covers optional advanced features. Use these only after baseline quality gates pass.

## 1) Compact Watchdog (advisory)

Purpose:
- Recommend `/compact` or `/clear` from a raw `/context` snapshot.
- Keep automation safe: recommendations only, no command execution.

Command:

```bash
python ~/.claude/skills/savethetokens/scripts/compact_watchdog.py \
  --context-file context_snapshot.txt \
  --require-checkpoint \
  --emit-command-file .claude/next_slash_command.txt
```

Safety:
- `/clear` is blocked unless `--allow-clear` is provided.
- Command emission can require an existing checkpoint file.

## 2) Dynamic Tool Filtering (fail-open)

Purpose:
- Rank likely-relevant tools for a task and reduce prompt clutter.

Command:

```bash
python ~/.claude/skills/savethetokens/scripts/tool_filter.py \
  --input tools.json \
  --query "debug flaky auth test" \
  --fail-open
```

Safety:
- Required tools are always retained.
- With low confidence, `--fail-open` keeps all tools to avoid false negatives.

## 3) Semantic Skill Selection (recommendation only)

Purpose:
- Rank relevant skills by query from installed skill metadata.

Command:

```bash
python ~/.claude/skills/savethetokens/scripts/skill_selector.py \
  --query "optimize remotion render performance"
```

Safety:
- Output includes `auto_activation_safe`.
- If confidence is low, treat output as suggestions only.

## 4) External Memory Store (bounded retrieval)

Purpose:
- Persist long-term notes outside chat context.
- Retrieve only compact, high-signal memory snippets.

Commands:

```bash
# Add note
python ~/.claude/skills/savethetokens/scripts/memory_store.py add \
  --task "bench-compiler-ab" \
  --note "Regression likely caused by verbose progress output." \
  --tags benchmark,messages,regression \
  --priority 4

# Retrieve prompt-ready bullets (bounded by max chars)
python ~/.claude/skills/savethetokens/scripts/memory_store.py search \
  --query "why did with-skill run use more tokens" \
  --for-prompt \
  --top-k 5 \
  --max-chars 1200
```

Safety:
- Retrieval output is bounded by `--max-chars`.
- Pruning requires explicit `--yes`.

## Rollout Guidance

1. Enable one advanced feature at a time.
2. Run matched A/B tests from `docs/BENCHMARK_PROTOCOL.md`.
3. If message tokens increase, treat as regression and rollback.
