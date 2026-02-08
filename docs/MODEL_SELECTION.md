# Model Selection

The Context Governor recommends optimal models based on task requirements, context size, and cost considerations.

## Model Capability Matrix

| Model           | Context Window | Tier     | Best For                         |
| --------------- | -------------- | -------- | -------------------------------- |
| claude-3-opus   | 200K           | premium  | Complex reasoning, nuanced tasks |
| claude-3-sonnet | 200K           | standard | Balanced performance/cost        |
| claude-3-haiku  | 200K           | economy  | Fast, simple tasks               |
| gpt-4o          | 128K           | premium  | Multi-modal, complex tasks       |
| gpt-4o-mini     | 128K           | economy  | Simple tasks, high volume        |

## Selection Algorithm

### Step 1: Check Context Fit

```
if total_tokens > model.context_window:
    → Upgrade to larger model OR prune context
```

### Step 2: Match Capabilities to Intent

| Intent          | Minimum Tier | Recommended  |
| --------------- | ------------ | ------------ |
| code_generation | standard     | sonnet       |
| debugging       | standard     | sonnet       |
| explanation     | economy      | haiku/sonnet |
| search          | economy      | haiku        |
| planning        | standard     | sonnet       |
| review          | standard     | sonnet       |

### Step 3: Apply Cost Preference

If `prefer_cost_savings` is enabled:

- Try to downgrade while maintaining capability requirements
- Calculate estimated savings

### Step 4: Generate Recommendation

```json
{
  "recommended_model": "claude-3-sonnet",
  "original_model": "claude-3-opus",
  "reason": "Task requirements met by sonnet, 80% cost savings",
  "capability_match": true,
  "cost_savings_estimate": 0.8
}
```

## Intent-Capability Mapping

### Code Generation

- **Required**: Strong coding ability
- **Recommended**: claude-3-sonnet, gpt-4o
- **Acceptable**: claude-3-haiku (simple tasks)

### Debugging

- **Required**: Code understanding, reasoning
- **Recommended**: claude-3-sonnet
- **Upgrade to**: claude-3-opus (complex bugs)

### Explanation

- **Required**: Clear communication
- **Recommended**: claude-3-haiku, claude-3-sonnet
- **Notes**: Lower tier often sufficient

### Complex Reasoning

- **Required**: Advanced reasoning
- **Recommended**: claude-3-opus
- **Notes**: Don't downgrade for cost

## Configuration

Override model selection behavior:

```json
{
  "model_selection": {
    "enabled": true,
    "prefer_cost_savings": true,
    "capability_threshold": 0.8,
    "allowed_models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "default_model": "claude-3-sonnet"
  }
}
```

## Cost Estimation

Approximate costs per 1K tokens (input):

| Model           | Cost/1K  |
| --------------- | -------- |
| claude-3-opus   | $0.015   |
| claude-3-sonnet | $0.003   |
| claude-3-haiku  | $0.00025 |

Cost savings calculation:

```
savings = 1 - (recommended_cost / original_cost)
```

## Usage in Plans

The execution plan includes model recommendations:

```json
{
  "recommendations": {
    "model": {
      "recommended": "claude-3-sonnet",
      "original": "claude-3-opus",
      "reason": "Task complexity allows standard tier",
      "cost_savings_estimate": 0.8,
      "alternatives": ["claude-3-opus"],
      "warnings": []
    }
  }
}
```

## Manual Override

Force a specific model:

```bash
python scripts/plan.py --budget 8000 --model claude-3-opus
```

This skips automatic selection but still validates context fits.
