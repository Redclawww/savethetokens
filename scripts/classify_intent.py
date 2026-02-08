#!/usr/bin/env python3
"""
Intent Classifier - Classifies task intent from context.

Determines the type of task being performed to guide pruning strategy.
"""

import re
from typing import Optional


class IntentClassifier:
    """Classifies task intent from context and queries."""
    
    INTENTS = {
        "code_generation": {
            "keywords": ["implement", "create", "build", "write", "generate", "add", "new"],
            "patterns": [r"implement\s+\w+", r"create\s+a\s+\w+", r"write\s+code"],
            "description": "Creating new code or features"
        },
        "debugging": {
            "keywords": ["error", "bug", "fix", "issue", "broken", "crash", "fail", "debug"],
            "patterns": [r"error\s*:", r"traceback", r"exception", r"why\s+.*\s+not\s+working"],
            "description": "Debugging and error resolution"
        },
        "explanation": {
            "keywords": ["explain", "what", "how", "why", "understand", "describe", "tell"],
            "patterns": [r"what\s+is\s+\w+", r"how\s+does\s+\w+", r"explain\s+\w+"],
            "description": "Understanding and explanation"
        },
        "search": {
            "keywords": ["find", "search", "locate", "where", "grep", "look"],
            "patterns": [r"find\s+\w+", r"where\s+is\s+\w+", r"search\s+for"],
            "description": "Finding code or information"
        },
        "planning": {
            "keywords": ["plan", "design", "architect", "structure", "organize", "approach"],
            "patterns": [r"how\s+should\s+i", r"best\s+approach", r"plan\s+to"],
            "description": "Planning and design"
        },
        "review": {
            "keywords": ["review", "check", "audit", "analyze", "improve", "refactor"],
            "patterns": [r"review\s+\w+", r"check\s+\w+", r"improve\s+\w+"],
            "description": "Code review and improvement"
        },
        "generic": {
            "keywords": [],
            "patterns": [],
            "description": "General task"
        }
    }
    
    # Priority strategies for each intent
    INTENT_STRATEGIES = {
        "code_generation": ["file", "reference", "system"],
        "debugging": ["error", "message", "file", "tool_output"],
        "explanation": ["file", "reference", "message"],
        "search": ["file", "reference", "tool_output"],
        "planning": ["message", "system", "reference"],
        "review": ["file", "message", "history"],
        "generic": ["message", "file", "system"]
    }
    
    def classify(self, content: str, query: Optional[str] = None) -> dict:
        """
        Classify the intent of the given context.
        
        Args:
            content: Combined context content
            query: Optional explicit query/request
            
        Returns:
            Classification result with intent and confidence
        """
        text_to_analyze = (query or "") + " " + content[:5000]  # Limit analysis scope
        text_lower = text_to_analyze.lower()
        
        scores = {}
        
        for intent, config in self.INTENTS.items():
            if intent == "generic":
                continue
            
            score = 0
            
            # Keyword matching
            for keyword in config["keywords"]:
                if keyword in text_lower:
                    score += 1.0
            
            # Pattern matching
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower):
                    score += 2.0
            
            scores[intent] = score
        
        # Determine winner
        if not scores or max(scores.values()) == 0:
            return {
                "intent": "generic",
                "confidence": 0.5,
                "scores": scores,
                "strategy": self.INTENT_STRATEGIES["generic"]
            }
        
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        total_score = sum(scores.values())
        
        confidence = min(0.95, best_score / max(5, total_score) + 0.3)
        
        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "scores": scores,
            "strategy": self.INTENT_STRATEGIES[best_intent]
        }
    
    def get_priority_weights(self, intent: str) -> dict[str, float]:
        """
        Get priority weights for context types based on intent.
        
        Args:
            intent: The classified intent
            
        Returns:
            Dict mapping context types to weight multipliers
        """
        base_weights = {
            "system": 1.0,
            "message": 1.0,
            "file": 0.8,
            "error": 0.7,
            "tool_output": 0.7,
            "reference": 0.5,
            "history": 0.3
        }
        
        # Intent-specific boosts
        boosts = {
            "code_generation": {"file": 1.3, "reference": 1.2},
            "debugging": {"error": 1.5, "tool_output": 1.3, "file": 1.1},
            "explanation": {"file": 1.2, "reference": 1.3},
            "search": {"file": 1.4, "tool_output": 1.2},
            "planning": {"reference": 1.3, "history": 0.5},
            "review": {"file": 1.3, "history": 1.1},
            "generic": {}
        }
        
        intent_boosts = boosts.get(intent, {})
        
        return {
            ctx_type: base_weights.get(ctx_type, 0.5) * intent_boosts.get(ctx_type, 1.0)
            for ctx_type in base_weights
        }


def main():
    """CLI entry point."""
    import argparse
    import json
    import sys
    
    parser = argparse.ArgumentParser(description="Classify task intent")
    parser.add_argument("--query", "-q", help="Query/request text")
    parser.add_argument("--input", "-f", help="Input file with context")
    
    args = parser.parse_args()
    
    classifier = IntentClassifier()
    
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
        content = " ".join(u.get("content", "") for u in data.get("context_units", [data]))
    else:
        content = sys.stdin.read() if not sys.stdin.isatty() else ""
    
    result = classifier.classify(content, args.query)
    print(json.dumps(result, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
