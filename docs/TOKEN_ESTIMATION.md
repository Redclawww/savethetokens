# Token Estimation

Accurate token estimation is critical for context governance. The Context Governor uses multiple estimation methods.

## Estimation Methods

### 1. Tiktoken (Recommended)

Uses OpenAI's tiktoken library for accurate counts:

```python
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-4")
tokens = len(encoder.encode(text))
```

**Supported models**:

- GPT-4, GPT-4o, GPT-4o-mini: `cl100k_base`
- GPT-3.5: `cl100k_base`
- Claude models: `cl100k_base` (approximation)

### 2. Character-Based Fallback

When tiktoken unavailable:

```python
# Approximate: 4 characters per token
tokens = len(text) // 4
```

This is less accurate but works everywhere.

### 3. Model-Specific Adjustments

Different models tokenize differently:

| Model Family | Adjustment      |
| ------------ | --------------- |
| GPT-4/Claude | 1.0x (baseline) |
| Older models | 1.1x-1.2x       |

## Token Counting in Practice

### For Files

```python
def count_file_tokens(filepath, encoder):
    with open(filepath) as f:
        content = f.read()
    return len(encoder.encode(content))
```

### For Messages

```python
def count_message_tokens(message, encoder):
    # Account for message overhead
    overhead = 4  # role, name, etc.
    content_tokens = len(encoder.encode(message["content"]))
    return overhead + content_tokens
```

### For Conversations

```python
def count_conversation_tokens(messages, encoder):
    total = 3  # conversation overhead
    for msg in messages:
        total += count_message_tokens(msg, encoder)
    return total
```

## Token Budgets

### Recommended Allocations

For an 8K budget:

| Component        | Tokens | Percentage |
| ---------------- | ------ | ---------- |
| System prompt    | 500    | 6%         |
| Context          | 5500   | 69%        |
| User message     | 500    | 6%         |
| Response reserve | 1500   | 19%        |

### Safety Margins

Always reserve tokens for:

- Response generation (20-30%)
- Unexpected overhead (5%)
- Buffer (5%)

```python
usable_budget = total_budget * 0.70  # 70% for context
```

## Context Window Reference

| Model           | Context Window | Safe Budget |
| --------------- | -------------- | ----------- |
| claude-3-opus   | 200K           | 140K        |
| claude-3-sonnet | 200K           | 140K        |
| claude-3-haiku  | 200K           | 140K        |
| gpt-4o          | 128K           | 90K         |
| gpt-4o-mini     | 128K           | 90K         |

## Caching

Token counts are cached to avoid recomputation:

```python
cache = {}

def estimate_cached(text, model_id):
    key = hash(text)
    if key not in cache:
        cache[key] = estimate_tokens(text, model_id)
    return cache[key]
```

## Usage in Scripts

Run token estimation:

```bash
python scripts/analyze.py --count-tokens
```

Output:

```json
{
  "units": [
    { "id": "file1", "path": "auth.py", "tokens": 1250 },
    { "id": "file2", "path": "utils.py", "tokens": 3400 }
  ],
  "total_tokens": 4650,
  "estimation_method": "tiktoken",
  "model": "gpt-4"
}
```

## Best Practices

1. **Use tiktoken when available** - Most accurate
2. **Cache aggressively** - Token counting is expensive
3. **Reserve response budget** - Don't use 100% of context
4. **Validate after pruning** - Ensure result fits budget
5. **Account for overhead** - Messages have formatting tokens
