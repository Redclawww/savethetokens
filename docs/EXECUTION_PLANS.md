# Execution Plans

The Context Governor produces **execution plans** - structured recommendations for how to execute an LLM task with optimized context.

## Plan Structure

An execution plan is a JSON document with the following structure:

```json
{
  "plan_id": "uuid-string",
  "created_at": "2025-02-02T12:00:00Z",
  "version": "1.0",

  "input_summary": {
    "total_units": 15,
    "total_tokens": 45000,
    "units_by_type": {
      "file": 8,
      "message": 5,
      "tool_result": 2
    }
  },

  "constraints": {
    "token_budget": 8000,
    "target_model": "claude-3-sonnet",
    "intent": "code_generation"
  },

  "experiment": {
    "enabled": true,
    "id": "claude-launch-v1",
    "variant": "optimized",
    "assignment_key": "TICKET-123"
  },

  "recommendations": {
    "model": {
      "recommended": "claude-3-sonnet",
      "reason": "Sufficient for code generation, cost-optimized",
      "alternatives": ["claude-3-opus"]
    },
    "budget_allocation": {
      "system_prompt": 500,
      "context": 6500,
      "response_reserve": 1000
    }
  },

  "optimized_context": [
    {
      "id": "file_auth_py",
      "type": "file",
      "action": "keep",
      "tokens": 1200,
      "priority": 95,
      "reason": "Directly relevant to task"
    },
    {
      "id": "file_utils_py",
      "type": "file",
      "action": "summarize",
      "original_tokens": 3000,
      "tokens": 400,
      "reason": "Supporting context, summarized"
    },
    {
      "id": "old_message_1",
      "type": "message",
      "action": "prune",
      "original_tokens": 500,
      "tokens": 0,
      "reason": "Low relevance to current task"
    }
  ],

  "statistics": {
    "tokens_saved": 37000,
    "reduction_percentage": 82.2,
    "units_kept": 8,
    "units_summarized": 3,
    "units_pruned": 4
  },

  "savings_breakdown": {
    "baseline_tokens": 45000,
    "after_filter_tokens": 18000,
    "after_pruning_tokens": 8000,
    "package_filtering": {
      "tokens_saved": 27000,
      "percentage_of_baseline": 60.0
    },
    "pruning_and_summarization": {
      "tokens_saved": 10000,
      "percentage_of_baseline": 22.2,
      "percentage_of_post_filter": 55.6
    },
    "overall": {
      "tokens_saved": 37000,
      "percentage_of_baseline": 82.2
    }
  },

  "session_hygiene": {
    "message_count_estimate": 32,
    "input_context_utilization_pct": 58.1,
    "optimized_context_utilization_pct": 34.7,
    "recommended_action": "checkpoint_then_compact",
    "playbook": [
      "Create a short checkpoint before ending this task chunk",
      "Run /compact around this point instead of waiting for hard limits"
    ]
  },

  "warnings": [],

  "explainability": {
    "strategy_used": "intent_aware",
    "intent_confidence": 0.92,
    "pruning_threshold": 0.3
  }
}
```

## Using Execution Plans

### For Manual Review

The plan is human-readable. Review the `optimized_context` array to see:

- Which items are kept and why
- Which items are summarized
- Which items are pruned
- Token allocation per item

### For Orchestrators

Agent orchestrators can consume the plan programmatically:

```python
import json

with open("execution_plan.json") as f:
    plan = json.load(f)

# Get recommended model
model = plan["recommendations"]["model"]["recommended"]

# Build optimized context
context = []
for item in plan["optimized_context"]:
    if item["action"] in ["keep", "summarize"]:
        # Load the item content
        context.append(load_item(item["id"]))
```

### For Claude Code

When using with Claude Code, the plan informs context assembly:

1. Run the governor to generate a plan
2. Review the pruning decisions
3. Assemble context following the plan
4. Make your LLM call with optimized context

## Plan Actions

Each context unit receives one of these actions:

| Action      | Description                |
| ----------- | -------------------------- |
| `keep`      | Include unchanged          |
| `summarize` | Include summarized version |
| `truncate`  | Include truncated version  |
| `prune`     | Exclude entirely           |

## Session Hygiene Actions

Execution plans now include a `session_hygiene.recommended_action` field:

| Action                                  | Meaning |
| --------------------------------------- | ------- |
| `continue`                              | Session pressure is low. Keep working on same task. |
| `prepare_checkpoint`                    | Pressure rising. Prepare checkpoint bullets now. |
| `checkpoint_then_compact`               | Save checkpoint and compact around this point. |
| `checkpoint_then_compact_immediately`   | Compact now; consider fresh session for unrelated follow-up work. |

## Validation

Plans include validation information:

```json
{
  "validation": {
    "total_tokens": 7800,
    "within_budget": true,
    "budget_remaining": 200
  }
}
```

Always verify `within_budget: true` before using the plan.
