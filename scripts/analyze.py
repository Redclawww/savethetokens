#!/usr/bin/env python3
"""
Context Analyzer - Analyzes context structure and quality.

Scans provided context units and generates analysis report.
Automatically filters out package directories (node_modules, __pycache__, etc.)
"""

import json
import sys
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Import path filter for automatic package exclusion
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from path_filter import PathFilter


@dataclass
class ContextUnit:
    """Represents a unit of context."""
    id: str
    type: str
    content: str
    priority: int = 50
    tokens: int = 0
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ContextAnalyzer:
    """Analyzes context for optimization opportunities.
    
    Automatically filters out package/dependency directories to prevent
    node_modules, __pycache__, vendor, etc. from bloating context.
    """
    
    CONTEXT_TYPES = {
        "system": {"base_priority": 100, "min_keep_ratio": 1.0},
        "message": {"base_priority": 90, "min_keep_ratio": 0.9},
        "error": {"base_priority": 85, "min_keep_ratio": 0.8},
        "file": {"base_priority": 50, "min_keep_ratio": 0.2},
        "reference": {"base_priority": 40, "min_keep_ratio": 0.1},
        "history": {"base_priority": 30, "min_keep_ratio": 0.1},
        "tool_output": {"base_priority": 60, "min_keep_ratio": 0.3},
        "unknown": {"base_priority": 50, "min_keep_ratio": 0.2}
    }
    
    def __init__(self, auto_filter: bool = True):
        """
        Initialize analyzer.
        
        Args:
            auto_filter: Whether to automatically filter package directories
        """
        self.units: list[ContextUnit] = []
        self.path_filter = PathFilter() if auto_filter else None
        self.filtered_units: list[dict] = []
    
    def analyze(self, context_units: list[dict]) -> dict:
        """
        Analyze context units and return analysis report.
        
        Args:
            context_units: List of context unit dicts
            
        Returns:
            Analysis report dict
        """
        self.units = []
        self.filtered_units = []
        
        # Filter out package directories first
        if self.path_filter:
            context_units, self.filtered_units = self.path_filter.filter_context_units(
                context_units
            )
        
        # Parse units
        for unit_data in context_units:
            unit = ContextUnit(
                id=unit_data.get("id", f"unit_{len(self.units)}"),
                type=unit_data.get("type", "unknown"),
                content=unit_data.get("content", ""),
                priority=unit_data.get("priority", 50),
                tokens=unit_data.get("tokens", 0),
                metadata=unit_data.get("metadata", {})
            )
            self.units.append(unit)
        
        # Run analysis
        return {
            "summary": self._generate_summary(),
            "units": self._analyze_units(),
            "duplicates": self._find_duplicates(),
            "type_distribution": self._get_type_distribution(),
            "optimization_opportunities": self._find_opportunities(),
            "filtered_packages": {
                "count": len(self.filtered_units),
                "units": self.filtered_units[:10],  # Show first 10
                "message": f"Automatically filtered {len(self.filtered_units)} package/dependency files"
                           if self.filtered_units else "No package files filtered"
            }
        }
    
    def _generate_summary(self) -> dict:
        """Generate summary statistics."""
        total_tokens = sum(u.tokens for u in self.units)
        total_content_length = sum(len(u.content) for u in self.units)
        
        return {
            "total_units": len(self.units),
            "total_tokens": total_tokens,
            "total_content_length": total_content_length,
            "avg_tokens_per_unit": total_tokens // len(self.units) if self.units else 0,
            "avg_priority": sum(u.priority for u in self.units) // len(self.units) if self.units else 0
        }
    
    def _analyze_units(self) -> list[dict]:
        """Analyze individual units."""
        results = []
        
        for unit in self.units:
            type_config = self.CONTEXT_TYPES.get(unit.type, self.CONTEXT_TYPES["unknown"])
            
            # Detect potential issues
            issues = []
            if unit.tokens > 4000:
                issues.append("very_large")
            if unit.tokens == 0 and unit.content:
                issues.append("missing_token_count")
            if not unit.content.strip():
                issues.append("empty_content")
            if unit.priority < type_config["base_priority"] - 20:
                issues.append("low_priority_for_type")
            
            results.append({
                "id": unit.id,
                "type": unit.type,
                "tokens": unit.tokens,
                "priority": unit.priority,
                "content_length": len(unit.content),
                "base_priority": type_config["base_priority"],
                "min_keep_ratio": type_config["min_keep_ratio"],
                "issues": issues
            })
        
        return results
    
    def _find_duplicates(self) -> list[dict]:
        """Find duplicate or near-duplicate content."""
        duplicates = []
        seen_hashes = {}
        
        for unit in self.units:
            # Hash first 500 chars + length as a simple similarity check
            content_key = hashlib.md5(
                (unit.content[:500] + str(len(unit.content))).encode()
            ).hexdigest()[:8]
            
            if content_key in seen_hashes:
                duplicates.append({
                    "unit_id": unit.id,
                    "duplicate_of": seen_hashes[content_key],
                    "savings_tokens": unit.tokens
                })
            else:
                seen_hashes[content_key] = unit.id
        
        return duplicates
    
    def _get_type_distribution(self) -> dict:
        """Get distribution of context types."""
        distribution = {}
        
        for unit in self.units:
            if unit.type not in distribution:
                distribution[unit.type] = {"count": 0, "tokens": 0}
            distribution[unit.type]["count"] += 1
            distribution[unit.type]["tokens"] += unit.tokens
        
        return distribution
    
    def _find_opportunities(self) -> list[dict]:
        """Find optimization opportunities."""
        opportunities = []
        
        # Check for large units that could be summarized
        for unit in self.units:
            if unit.type == "file" and unit.tokens > 2000:
                opportunities.append({
                    "unit_id": unit.id,
                    "opportunity": "summarize_large_file",
                    "potential_savings": unit.tokens - 500,
                    "description": f"File {unit.id} has {unit.tokens} tokens, consider summarizing"
                })
            elif unit.type == "history" and unit.tokens > 1000:
                opportunities.append({
                    "unit_id": unit.id,
                    "opportunity": "truncate_history",
                    "potential_savings": unit.tokens - 300,
                    "description": f"History {unit.id} has {unit.tokens} tokens, consider truncating older entries"
                })
        
        # Check for low-priority units consuming significant tokens
        low_priority_tokens = sum(u.tokens for u in self.units if u.priority < 30)
        if low_priority_tokens > 1000:
            opportunities.append({
                "opportunity": "prune_low_priority",
                "potential_savings": low_priority_tokens,
                "description": f"{low_priority_tokens} tokens in low-priority units could be pruned"
            })
        
        return opportunities


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze context structure")
    parser.add_argument("--input", "-f", help="Input JSON file")
    parser.add_argument("--output", "-o", default="-", help="Output file (- for stdout)")
    
    args = parser.parse_args()
    
    # Load input
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
            context_units = data.get("context_units", data)
    else:
        # Read from stdin
        data = json.load(sys.stdin)
        context_units = data.get("context_units", data)
    
    # Analyze
    analyzer = ContextAnalyzer()
    result = analyzer.analyze(context_units)
    
    # Output
    output = json.dumps(result, indent=2)
    if args.output == "-":
        print(output)
    else:
        with open(args.output, "w") as f:
            f.write(output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
