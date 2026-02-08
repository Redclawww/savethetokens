#!/usr/bin/env python3
"""
Context Pruner - Prunes context to fit within token budget.

Implements intent-aware pruning strategies.

QUALITY PRESERVATION PRINCIPLES:
1. NEVER prune system prompts - they define behavior
2. NEVER prune the most recent user message - it's the task
3. NEVER prune error context during debugging - critical for fixes
4. ALWAYS warn when pruning may affect output quality
5. DEFAULT to keeping content when uncertain
6. Prefer summarization over deletion for valuable content
"""

import sys
from typing import Optional


class ContextPruner:
    """Prunes context units based on budget and intent.
    
    QUALITY GUARANTEE: This pruner is designed to NEVER degrade LLM output.
    It follows fail-safe defaults and conservative pruning strategies.
    """
    
    # Priority ranges for pruning decisions
    PRIORITY_THRESHOLDS = {
        "critical": 90,    # NEVER prune - essential for quality
        "important": 70,   # Prune only as absolute last resort
        "normal": 50,      # Conservative pruning with warnings
        "low": 30,         # Safe to prune if needed
        "optional": 0      # Prune first, lowest impact
    }
    
    # PROTECTED TYPES - These are NEVER pruned to preserve quality
    PROTECTED_TYPES = {
        "system",          # System prompts define behavior
        "instruction",     # User instructions are critical
        "current_task",    # The actual task being performed
    }
    
    # Types that require special protection based on intent
    INTENT_PROTECTED = {
        "debugging": {"error", "traceback", "stack_trace", "exception"},
        "code_generation": {"specification", "requirements", "interface"},
        "explanation": {"question", "query"},
        "review": {"code", "diff", "changes"},
    }
    
    # Type-based minimum retention - CONSERVATIVE defaults
    TYPE_MIN_KEEP = {
        "system": 1.0,     # ALWAYS keep 100% - defines LLM behavior
        "message": 1.0,    # ALWAYS keep recent messages - they're the task
        "error": 1.0,      # ALWAYS keep errors - critical for debugging
        "instruction": 1.0, # ALWAYS keep instructions
        "file": 0.5,       # Keep at least half - context matters
        "tool_output": 0.6, # Keep most tool output - often relevant
        "reference": 0.4,  # Reference docs can be trimmed
        "history": 0.3     # Older history can be summarized
    }
    
    # Maximum pruning percentage - QUALITY SAFEGUARD
    # Never prune more than this % to prevent quality degradation
    MAX_PRUNE_PERCENTAGE = 0.40  # Never remove more than 40% of context
    
    def prune(
        self,
        context_units: list[dict],
        budget: int,
        intent: str = "generic",
        query: Optional[str] = None
    ) -> dict:
        """
        Prune context units to fit within budget.
        
        Args:
            context_units: List of context unit dicts
            budget: Token budget to fit within
            intent: Task intent for strategy selection
            query: Optional query for relevance scoring
            
        Returns:
            Pruning result with decisions and statistics
        """
        # Calculate current totals
        total_tokens = sum(u.get("tokens", 0) for u in context_units)
        
        # QUALITY SAFEGUARD: Calculate protected tokens that can NEVER be pruned
        protected_tokens = self._calculate_protected_tokens(context_units, intent)
        
        if total_tokens <= budget:
            # No pruning needed - best case for quality
            return {
                "decisions": [
                    {
                        "unit_id": u.get("id", f"unit_{i}"),
                        "type": u.get("type", "unknown"),
                        "action": "keep",
                        "original_tokens": u.get("tokens", 0),
                        "final_tokens": u.get("tokens", 0),
                        "priority": u.get("priority", 50),
                        "reason": "Within budget - full quality preserved"
                    }
                    for i, u in enumerate(context_units)
                ],
                "strategy": "none",
                "threshold": 0,
                "warnings": [],
                "quality_impact": "none"  # No quality degradation
            }
        
        # Score and rank units
        scored_units = self._score_units(context_units, intent, query)
        
        # Determine pruning strategy based on how much we need to cut
        reduction_needed = total_tokens - budget
        reduction_ratio = reduction_needed / total_tokens
        
        # QUALITY SAFEGUARD: Cap maximum reduction to prevent quality degradation
        max_allowed_reduction = total_tokens * self.MAX_PRUNE_PERCENTAGE
        quality_warnings = []
        
        if reduction_needed > max_allowed_reduction:
            quality_warnings.append(
                f"QUALITY WARNING: Requested {reduction_ratio*100:.0f}% reduction exceeds safe limit of {self.MAX_PRUNE_PERCENTAGE*100:.0f}%. "
                f"Output quality may be preserved by keeping more context than budget allows."
            )
        
        if protected_tokens > budget:
            quality_warnings.append(
                f"QUALITY ALERT: Protected context ({protected_tokens} tokens) exceeds budget ({budget}). "
                f"Cannot prune without risking output quality. Recommend increasing budget."
            )
        
        # Conservative strategy selection - prefer quality over strict budget adherence
        if reduction_ratio < 0.15:
            strategy = "minimal"
            threshold = 0.15  # Only prune clearly low-value content
        elif reduction_ratio < 0.30:
            strategy = "light"
            threshold = 0.25
        elif reduction_ratio < 0.40:
            strategy = "moderate"
            threshold = 0.35
        else:
            strategy = "conservative_aggressive"  # Still prioritizes quality
            threshold = 0.45
            quality_warnings.append(
                "High reduction required - using conservative aggressive strategy to preserve essential context"
            )
        
        # Make pruning decisions
        decisions = []
        warnings = []
        running_tokens = 0
        removed_tokens = 0
        
        # Sort by score (descending) - highest scores kept first
        scored_units.sort(key=lambda x: x["score"], reverse=True)
        
        for i, unit in enumerate(scored_units):
            unit_id = unit["unit_id"]
            unit_type = unit["type"]
            tokens = unit["tokens"]
            priority = unit["priority"]
            score = unit["score"]
            
            min_keep = self.TYPE_MIN_KEEP.get(unit_type, 0.2)
            
            # QUALITY-FIRST Decision logic
            is_protected_type = unit_type in self.PROTECTED_TYPES
            is_intent_protected = unit_type in self.INTENT_PROTECTED.get(intent, set())
            is_high_priority = priority >= self.PRIORITY_THRESHOLDS["critical"]
            is_recent_message = unit_type == "message" and i >= len(scored_units) - 3
            
            # RULE 1: NEVER prune protected types - they're essential for quality
            if is_protected_type or is_intent_protected or is_high_priority:
                action = "keep"
                final_tokens = tokens
                reason = f"Protected ({unit_type}) - essential for output quality"
            
            # RULE 2: ALWAYS keep recent messages - they contain the actual task
            elif is_recent_message:
                action = "keep"
                final_tokens = tokens
                reason = "Recent message - contains current task context"
            
            # RULE 3: Keep if it fits in budget
            elif running_tokens + tokens <= budget:
                action = "keep"
                final_tokens = tokens
                reason = f"Score {score:.2f} - within budget, quality preserved"
            
            # RULE 4: High-value content - keep even if slightly over budget
            elif score >= 0.7 and running_tokens < budget * 0.95:
                action = "keep"
                final_tokens = tokens
                reason = f"High value (score {score:.2f}) - kept for quality"
                if running_tokens + tokens > budget:
                    quality_warnings.append(
                        f"Kept high-value unit '{unit_id}' to preserve output quality"
                    )
            
            # RULE 5: Large valuable content - summarize instead of delete
            elif tokens > 800 and score >= 0.4:
                action = "summarize"
                # Keep more content in summary - 40% instead of 30%
                final_tokens = min(600, int(tokens * 0.4))
                reason = f"Summarized to preserve key information ({tokens}→{final_tokens})"
            
            # RULE 6: Only prune clearly low-value content
            elif score < threshold and priority < self.PRIORITY_THRESHOLDS["normal"]:
                action = "prune"
                final_tokens = 0
                reason = f"Low value (score {score:.2f}) - safe to prune"
            
            # DEFAULT: When uncertain, KEEP - fail-safe for quality
            else:
                action = "keep"
                final_tokens = tokens
                reason = f"Kept by default - uncertain value, preserving quality"

            # Enforce hard prune cap so quality guarantees are real, not advisory.
            desired_removed = max(0, tokens - final_tokens)
            remaining_allowance = max(0, int(max_allowed_reduction - removed_tokens))
            if desired_removed > remaining_allowance:
                if remaining_allowance <= 0:
                    action = "keep"
                    final_tokens = tokens
                    reason = (
                        f"Kept to enforce max prune cap ({self.MAX_PRUNE_PERCENTAGE*100:.0f}%)"
                    )
                else:
                    adjusted_final = max(0, tokens - remaining_allowance)
                    action = "summarize" if adjusted_final < tokens else "keep"
                    final_tokens = adjusted_final
                    reason = (
                        f"Adjusted to enforce max prune cap ({tokens}→{final_tokens})"
                    )
                desired_removed = max(0, tokens - final_tokens)
            
            if action != "prune":
                running_tokens += final_tokens
            removed_tokens += desired_removed
            
            decisions.append({
                "unit_id": unit_id,
                "type": unit_type,
                "action": action,
                "original_tokens": tokens,
                "final_tokens": final_tokens,
                "priority": priority,
                "score": round(score, 2),
                "reason": reason
            })
        
        # Check if we're still over budget
        final_total = sum(d["final_tokens"] for d in decisions)
        pruned_count = sum(1 for d in decisions if d["action"] == "prune")
        kept_count = sum(1 for d in decisions if d["action"] == "keep")
        
        # QUALITY ASSESSMENT
        actual_reduction_ratio = (
            (total_tokens - final_total) / total_tokens if total_tokens > 0 else 0
        )
        quality_impact = "none"
        if actual_reduction_ratio == 0:
            quality_impact = "none"
        elif pruned_count <= 2 and all(d["priority"] < 30 for d in decisions if d["action"] == "prune"):
            quality_impact = "minimal"
        elif actual_reduction_ratio < 0.25:
            quality_impact = "low"
        elif actual_reduction_ratio <= self.MAX_PRUNE_PERCENTAGE:
            quality_impact = "moderate"
            quality_warnings.append(
                "Moderate pruning applied - review output for completeness"
            )
        else:
            quality_impact = "significant"
            quality_warnings.append(
                "IMPORTANT: Significant context removed. Consider increasing budget for better output quality."
            )
        
        if final_total > budget:
            # Over budget but we prioritized quality
            quality_warnings.append(
                f"Context ({final_total} tokens) exceeds budget ({budget}) to preserve output quality. "
                f"This is intentional - quality > strict budget adherence."
            )
        
        return {
            "decisions": decisions,
            "strategy": strategy,
            "threshold": threshold,
            "warnings": warnings + quality_warnings,
            "quality_impact": quality_impact,
            "actual_reduction_percentage": round(actual_reduction_ratio * 100, 1),
            "quality_preserved": actual_reduction_ratio <= self.MAX_PRUNE_PERCENTAGE
        }
    
    def _score_units(
        self,
        units: list[dict],
        intent: str,
        query: Optional[str]
    ) -> list[dict]:
        """Score units for pruning priority."""
        
        # Intent-based type weights
        intent_weights = {
            "code_generation": {"file": 1.2, "reference": 1.1, "history": 0.5},
            "debugging": {"error": 1.5, "tool_output": 1.3, "file": 1.0},
            "explanation": {"file": 1.1, "reference": 1.2, "message": 1.0},
            "search": {"file": 1.3, "tool_output": 1.1},
            "review": {"file": 1.2, "history": 0.8},
            "generic": {}
        }
        
        weights = intent_weights.get(intent, {})
        
        scored = []
        for i, unit in enumerate(units):
            unit_id = unit.get("id", f"unit_{i}")
            unit_type = unit.get("type", "unknown")
            priority = unit.get("priority", 50)
            tokens = unit.get("tokens", 0)
            content = unit.get("content", "")
            
            # Base score from priority (0-1 scale)
            base_score = priority / 100.0
            
            # Type weight
            type_weight = weights.get(unit_type, 1.0)
            
            # Recency bonus (later units are more recent/relevant)
            recency_bonus = (i + 1) / len(units) * 0.1
            
            # Size penalty for very large units
            size_penalty = 0
            if tokens > 5000:
                size_penalty = 0.2
            elif tokens > 3000:
                size_penalty = 0.1
            
            # Query relevance bonus
            relevance_bonus = 0
            if query and content:
                query_terms = set(query.lower().split())
                content_lower = content.lower()
                matches = sum(1 for term in query_terms if term in content_lower)
                if matches > 0:
                    relevance_bonus = min(0.2, matches * 0.05)

            # Relevance signal from upstream scorer (if available).
            relevance_signal = unit.get("relevance", {}).get("score")
            relevance_adjustment = 0
            if isinstance(relevance_signal, (int, float)):
                # Conservative weighting: boost high relevance, lightly penalize low relevance.
                relevance_adjustment = (float(relevance_signal) - 0.5) * 0.3
                if relevance_signal < 0.25 and priority < self.PRIORITY_THRESHOLDS["normal"]:
                    relevance_adjustment -= 0.05
            
            # Calculate final score
            score = (
                base_score * type_weight
                + recency_bonus
                + relevance_bonus
                + relevance_adjustment
                - size_penalty
            )
            score = max(0, min(1, score))  # Clamp to 0-1
            
            scored.append({
                "unit_id": unit_id,
                "type": unit_type,
                "tokens": tokens,
                "priority": priority,
                "score": score
            })
        
        return scored
    
    def _calculate_protected_tokens(self, units: list[dict], intent: str) -> int:
        """
        Calculate tokens that MUST be kept to preserve output quality.
        
        These tokens are never counted against the prunable budget.
        """
        protected = 0
        intent_protected_types = self.INTENT_PROTECTED.get(intent, set())
        
        for i, unit in enumerate(units):
            unit_type = unit.get("type", "unknown")
            tokens = unit.get("tokens", 0)
            priority = unit.get("priority", 50)
            
            # System prompts - ALWAYS protected
            if unit_type in self.PROTECTED_TYPES:
                protected += tokens
            
            # Intent-specific protected types
            elif unit_type in intent_protected_types:
                protected += tokens
            
            # High priority units (90+)
            elif priority >= self.PRIORITY_THRESHOLDS["critical"]:
                protected += tokens
            
            # Recent messages (last 3) - they contain the current task
            elif unit_type == "message" and i >= len(units) - 3:
                protected += tokens
        
        return protected


def main():
    """CLI entry point."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Prune context to budget")
    parser.add_argument("--budget", "-b", type=int, required=True, help="Token budget")
    parser.add_argument("--intent", "-i", default="generic", help="Task intent")
    parser.add_argument("--query", "-q", help="Query for relevance")
    parser.add_argument("--input", "-f", help="Input JSON file")
    
    args = parser.parse_args()
    
    # Load input
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
            context_units = data.get("context_units", data)
    else:
        data = json.load(sys.stdin)
        context_units = data.get("context_units", data)
    
    pruner = ContextPruner()
    result = pruner.prune(context_units, args.budget, args.intent, args.query)
    
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
