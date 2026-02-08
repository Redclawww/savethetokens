# Pruning Strategies

The Context Governor uses different pruning strategies based on task intent. Each strategy optimizes which context to keep, summarize, or prune.

## Strategy Selection

Strategies are selected based on classified intent:

| Intent            | Strategy        | Preserves                      |
| ----------------- | --------------- | ------------------------------ |
| `code_generation` | Code-First      | Files, snippets, examples      |
| `debugging`       | Error-First     | Errors, traces, recent changes |
| `explanation`     | Context-Rich    | Documentation, history         |
| `search`          | Relevance-First | Search results, ranked items   |
| `planning`        | Goal-First      | Requirements, constraints      |
| `review`          | Diff-First      | Changes, comments, standards   |
| `generic`         | Balanced        | Mixed priority                 |

## Strategy Details

### Code-First (code_generation)

**Goal**: Maximize code context for generation tasks.

**Preserves**:

- Source files (highest priority)
- Code snippets
- Function signatures
- Examples and patterns

**Prunes aggressively**:

- Old conversation messages
- Documentation (unless directly referenced)
- General explanations

**Weights**:

```
files: 1.0
snippets: 0.9
messages: 0.5
documentation: 0.4
```

### Error-First (debugging)

**Goal**: Maximize error context for debugging.

**Preserves**:

- Error messages and stack traces
- Recent file changes
- Related code context
- Previous debugging attempts

**Prunes aggressively**:

- Unrelated files
- Old conversation history
- General documentation

**Weights**:

```
errors: 1.0
tool_results: 0.9
recent_files: 0.8
messages: 0.6
```

### Context-Rich (explanation)

**Goal**: Preserve broad context for explanations.

**Preserves**:

- Documentation
- Conversation history
- Related concepts
- Examples

**Balances**:

- All context types fairly
- Recency weighted moderately

**Weights**:

```
documentation: 1.0
messages: 0.8
files: 0.7
examples: 0.9
```

### Relevance-First (search)

**Goal**: Prioritize by relevance score.

**Preserves**:

- Search results with high relevance
- Query-related content
- Contextual matches

**Uses**:

- TF-IDF scoring
- Query term matching
- Semantic similarity (if available)

**Weights**:

```
relevance_score: 0.6
priority: 0.2
recency: 0.2
```

### Goal-First (planning)

**Goal**: Preserve planning context.

**Preserves**:

- Requirements and constraints
- Goals and objectives
- Previous plans
- Decision history

**Prunes**:

- Implementation details
- Code files (unless architectural)
- Low-level documentation

### Diff-First (review)

**Goal**: Focus on changes and standards.

**Preserves**:

- Diffs and changes
- Code standards
- Review comments
- Previous feedback

**Prunes**:

- Unchanged code
- Unrelated context
- Old discussions

## Custom Weights

Override default weights in the configuration:

```json
{
  "pruning": {
    "strategy": "hybrid",
    "weights": {
      "priority": 0.4,
      "relevance": 0.4,
      "recency": 0.2
    },
    "type_weights": {
      "file": 1.0,
      "message": 0.7,
      "tool_result": 0.8
    }
  }
}
```

## Scoring Formula

Combined score for each context unit:

```
score = (priority_weight × normalized_priority) +
        (relevance_weight × relevance_score) +
        (recency_weight × recency_score) +
        (type_bonus if type in preserved_types else 0)
```

Units are sorted by score and included until budget is exhausted.

## Summarization Triggers

When a unit is valuable but too large:

1. Score exceeds keep threshold
2. Adding it would exceed budget
3. Summarization is enabled
4. Summarized version fits in remaining budget

The summarized version preserves key information in fewer tokens.
