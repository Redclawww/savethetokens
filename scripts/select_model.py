#!/usr/bin/env python3
"""
Model Selector - Recommends optimal model based on task requirements.

Considers capabilities, cost, and context window requirements.
"""

import json
import sys


class ModelSelector:
    """Selects optimal model for task requirements."""
    
    # Model catalog with capabilities
    MODELS = {
        # Claude 4 family (Anthropic latest)
        "claude-sonnet-4": {
            "context_window": 200000,
            "max_output": 64000,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
            "capabilities": {
                "code_generation": 0.95,
                "debugging": 0.95,
                "explanation": 0.95,
                "search": 0.80,
                "planning": 0.95,
                "review": 0.95,
                "generic": 0.90
            },
            "tier": "standard"
        },
        "claude-opus-4": {
            "context_window": 200000,
            "max_output": 32000,
            "cost_per_1k_input": 0.015,
            "cost_per_1k_output": 0.075,
            "capabilities": {
                "code_generation": 1.0,
                "debugging": 1.0,
                "explanation": 1.0,
                "search": 0.85,
                "planning": 1.0,
                "review": 1.0,
                "generic": 0.95
            },
            "tier": "premium"
        },
        # Claude 3.5 family
        "claude-3-5-sonnet": {
            "context_window": 200000,
            "max_output": 8192,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
            "capabilities": {
                "code_generation": 0.95,
                "debugging": 0.95,
                "explanation": 0.90,
                "search": 0.75,
                "planning": 0.90,
                "review": 0.90,
                "generic": 0.85
            },
            "tier": "standard"
        },
        # Claude 3 family
        "claude-3-sonnet": {
            "context_window": 200000,
            "max_output": 4096,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
            "capabilities": {
                "code_generation": 0.85,
                "debugging": 0.85,
                "explanation": 0.85,
                "search": 0.70,
                "planning": 0.80,
                "review": 0.80,
                "generic": 0.80
            },
            "tier": "standard"
        },
        "claude-3-haiku": {
            "context_window": 200000,
            "max_output": 4096,
            "cost_per_1k_input": 0.00025,
            "cost_per_1k_output": 0.00125,
            "capabilities": {
                "code_generation": 0.70,
                "debugging": 0.65,
                "explanation": 0.75,
                "search": 0.80,
                "planning": 0.60,
                "review": 0.65,
                "generic": 0.70
            },
            "tier": "economy"
        },
        "claude-3-opus": {
            "context_window": 200000,
            "max_output": 4096,
            "cost_per_1k_input": 0.015,
            "cost_per_1k_output": 0.075,
            "capabilities": {
                "code_generation": 0.95,
                "debugging": 0.95,
                "explanation": 0.95,
                "search": 0.80,
                "planning": 0.95,
                "review": 0.95,
                "generic": 0.90
            },
            "tier": "premium"
        }
    }
    
    # Intent complexity mapping
    INTENT_COMPLEXITY = {
        "code_generation": "high",
        "debugging": "high",
        "explanation": "medium",
        "search": "low",
        "planning": "high",
        "review": "medium",
        "generic": "medium"
    }
    
    def select(
        self,
        requested_model: str,
        intent: str,
        context_tokens: int,
        prefer_cost_savings: bool = True
    ) -> dict:
        """
        Select optimal model for the task.
        
        Args:
            requested_model: User's requested model
            intent: Task intent
            context_tokens: Expected context size
            prefer_cost_savings: Whether to optimize for cost
            
        Returns:
            Model recommendation dict
        """
        # Normalize model name
        requested = self._normalize_model(requested_model)
        requested_info = self.MODELS.get(requested, self.MODELS["claude-3-sonnet"])
        
        # Check if requested model fits
        if context_tokens > requested_info["context_window"] * 0.8:
            # Need larger context window
            alternatives = self._find_larger_context_models(context_tokens)
            if alternatives:
                return {
                    "recommended_model": alternatives[0],
                    "original_model": requested_model,
                    "reason": f"Context size ({context_tokens}) exceeds {requested_model} effective limit",
                    "alternatives": alternatives[1:3],
                    "cost_savings_estimate": None
                }
        
        # Get task complexity
        complexity = self.INTENT_COMPLEXITY.get(intent, "medium")
        required_capability = requested_info["capabilities"].get(intent, 0.7)
        
        # If cost savings preferred, check for cheaper alternatives
        if prefer_cost_savings:
            cheaper = self._find_cheaper_alternative(
                requested, intent, context_tokens, required_capability * 0.9
            )
            if cheaper and cheaper != requested:
                savings = self._estimate_savings(
                    requested_info, self.MODELS[cheaper], context_tokens
                )
                return {
                    "recommended_model": cheaper,
                    "original_model": requested_model,
                    "reason": f"Cost optimization: {cheaper} sufficient for {intent}",
                    "cost_savings_estimate": f"{savings:.1f}%",
                    "alternatives": [requested]
                }
        
        # For high complexity, consider upgrading
        if complexity == "high" and requested_info["tier"] == "economy":
            upgraded = self._find_upgraded_model(requested, intent)
            if upgraded:
                return {
                    "recommended_model": upgraded,
                    "original_model": requested_model,
                    "reason": f"Task complexity ({intent}) may benefit from {upgraded}",
                    "alternatives": [requested],
                    "cost_savings_estimate": None
                }
        
        # Keep original model
        return {
            "recommended_model": requested_model,
            "original_model": requested_model,
            "reason": f"Requested model suitable for {intent}",
            "alternatives": [],
            "cost_savings_estimate": None
        }
    
    def _normalize_model(self, model: str) -> str:
        """Normalize model name to catalog key."""
        model_lower = model.lower().replace("-", " ").replace("_", " ")
        
        mappings = {
            "sonnet": "claude-3-sonnet",
            "haiku": "claude-3-haiku",
            "opus": "claude-3-opus",
            "claude 3 sonnet": "claude-3-sonnet",
            "claude 3 haiku": "claude-3-haiku",
            "claude 3 opus": "claude-3-opus",
            "claude 3.5 sonnet": "claude-3-5-sonnet",
            "claude sonnet 4": "claude-sonnet-4",
            "claude opus 4": "claude-opus-4",
        }
        
        for key, value in mappings.items():
            if key in model_lower:
                return value
        
        # Try direct match
        normalized = model.lower().replace(" ", "-")
        if normalized in self.MODELS:
            return normalized
        
        return "claude-3-sonnet"  # Default
    
    def _find_larger_context_models(self, min_context: int) -> list[str]:
        """Find models with sufficient context window."""
        suitable = []
        for name, info in self.MODELS.items():
            if info["context_window"] >= min_context * 1.2:
                suitable.append((name, info["cost_per_1k_input"]))
        
        suitable.sort(key=lambda x: x[1])  # Sort by cost
        return [m[0] for m in suitable]
    
    def _find_cheaper_alternative(
        self, current: str, intent: str, tokens: int, min_capability: float
    ) -> str | None:
        """Find cheaper model that meets requirements."""
        current_info = self.MODELS.get(current)
        if not current_info:
            return None
        
        current_cost = current_info["cost_per_1k_input"]
        
        candidates = []
        for name, info in self.MODELS.items():
            if name == current:
                continue
            
            # Check capability
            capability = info["capabilities"].get(intent, 0.5)
            if capability < min_capability:
                continue
            
            # Check context fits
            if info["context_window"] < tokens * 1.1:
                continue
            
            # Check if cheaper
            if info["cost_per_1k_input"] >= current_cost:
                continue
            
            candidates.append((name, info["cost_per_1k_input"], capability))
        
        if not candidates:
            return None
        
        # Best capability among cheaper options
        candidates.sort(key=lambda x: (-x[2], x[1]))
        return candidates[0][0]
    
    def _find_upgraded_model(self, current: str, intent: str) -> str | None:
        """Find better model for complex tasks."""
        current_info = self.MODELS.get(current)
        if not current_info:
            return None
        
        current_capability = current_info["capabilities"].get(intent, 0.5)
        
        for name, info in self.MODELS.items():
            if name == current:
                continue
            
            capability = info["capabilities"].get(intent, 0.5)
            if capability > current_capability + 0.15:
                # Significant improvement
                return name
        
        return None
    
    def _estimate_savings(self, original: dict, recommended: dict, tokens: int) -> float:
        """Estimate cost savings percentage."""
        orig_cost = original["cost_per_1k_input"] * tokens / 1000
        rec_cost = recommended["cost_per_1k_input"] * tokens / 1000
        
        if orig_cost == 0:
            return 0
        
        return (orig_cost - rec_cost) / orig_cost * 100


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Select optimal model")
    parser.add_argument("--model", "-m", default="claude-3-sonnet", help="Requested model")
    parser.add_argument("--intent", "-i", default="generic", help="Task intent")
    parser.add_argument("--tokens", "-t", type=int, default=4000, help="Context tokens")
    parser.add_argument("--no-cost-optimize", action="store_true", help="Disable cost optimization")
    
    args = parser.parse_args()
    
    selector = ModelSelector()
    result = selector.select(
        args.model,
        args.intent,
        args.tokens,
        not args.no_cost_optimize
    )
    
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
