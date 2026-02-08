#!/usr/bin/env python3
"""
Tiered Context Architecture - Classify and optimize context into 3 tiers.

Based on the principle: Load less, get more relevant responses.

Tier 1: Critical Context (<800 tokens) - ALWAYS loaded
    - Project name and purpose
    - Critical "never do this" rules
    - Quick start commands
    - Emergency troubleshooting

Tier 2: Contextual (500-1,500 tokens) - Loaded ON DEMAND
    - Component-specific docs
    - API references
    - Deployment guides
    - Testing patterns

Tier 3: Reference (0 tokens) - LINKED, never loaded
    - Complete API specs
    - Historical change logs
    - Detailed troubleshooting
    - Generated documentation
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TieredUnit:
    """A context unit with tier classification."""
    id: str
    content: str
    tokens: int
    tier: int  # 1, 2, or 3
    category: str
    load_condition: str  # "always", "on_demand", "never"
    relevance_keywords: list[str] = field(default_factory=list)


class TieredContextClassifier:
    """Classifies context units into 3 tiers for optimal loading."""
    
    # Token budgets per tier
    TIER_BUDGETS = {
        1: 800,    # Critical - always loaded
        2: 1500,   # Contextual - on demand
        3: 0       # Reference - linked only
    }
    
    # Patterns that indicate Tier 1 (Critical)
    TIER_1_PATTERNS = [
        r"critical\s*rules?",
        r"never\s+do",
        r"don'?t\s+ever",
        r"important\s*:",
        r"⚠️|🚨|❌",
        r"quick\s*start",
        r"getting\s*started",
        r"emergency",
        r"troubleshoot",
        r"common\s*issues?",
        r"overview",
        r"purpose",
    ]
    
    # Patterns that indicate Tier 2 (Contextual/On-Demand)
    TIER_2_PATTERNS = [
        r"api\s*(reference|docs|endpoints)",
        r"database\s*(schema|docs)",
        r"deployment\s*(guide|docs)",
        r"testing\s*(guide|patterns)",
        r"configuration",
        r"architecture",
        r"components?",
        r"modules?",
    ]
    
    # Patterns that indicate Tier 3 (Reference/Never Load)
    TIER_3_PATTERNS = [
        r"changelog",
        r"history",
        r"generated\s*docs?",
        r"complete\s*(api|reference)",
        r"full\s*(documentation|specs?)",
        r"detailed\s*troubleshooting",
        r"appendix",
        r"legacy",
    ]
    
    # File types by tier
    FILE_TIER_MAPPING = {
        1: ["CLAUDE.md", "README.md", "QUICK_REF.md"],
        2: ["API.md", "DATABASE.md", "TESTING.md", "DEPLOYMENT.md", "ARCHITECTURE.md"],
        3: ["CHANGELOG.md", "HISTORY.md", "docs/troubleshooting/", "generated/"]
    }
    
    def __init__(self):
        self.tier_1_patterns = [re.compile(p, re.IGNORECASE) for p in self.TIER_1_PATTERNS]
        self.tier_2_patterns = [re.compile(p, re.IGNORECASE) for p in self.TIER_2_PATTERNS]
        self.tier_3_patterns = [re.compile(p, re.IGNORECASE) for p in self.TIER_3_PATTERNS]
    
    def classify_content(self, content: str, filename: str = "") -> int:
        """
        Classify content into a tier (1, 2, or 3).
        
        Args:
            content: The text content to classify
            filename: Optional filename for context
            
        Returns:
            Tier number (1, 2, or 3)
        """
        # Check filename first
        filename_lower = filename.lower()
        for tier, files in self.FILE_TIER_MAPPING.items():
            for pattern in files:
                if pattern.lower() in filename_lower:
                    return tier
        
        # Score based on content patterns
        tier_1_score = sum(1 for p in self.tier_1_patterns if p.search(content))
        tier_2_score = sum(1 for p in self.tier_2_patterns if p.search(content))
        tier_3_score = sum(1 for p in self.tier_3_patterns if p.search(content))
        
        # Determine tier
        if tier_1_score > tier_2_score and tier_1_score > tier_3_score:
            return 1
        elif tier_3_score > tier_2_score:
            return 3
        elif tier_2_score > 0:
            return 2
        else:
            # Default to tier 2 for unknown content
            return 2
    
    def classify_units(self, units: list[dict]) -> dict:
        """
        Classify a list of context units into tiers.
        
        Args:
            units: List of context unit dicts
            
        Returns:
            Classification result with tiered units
        """
        tiered = {1: [], 2: [], 3: []}
        tier_tokens = {1: 0, 2: 0, 3: 0}
        
        for unit in units:
            content = unit.get("content", "")
            filename = unit.get("path", unit.get("id", ""))
            tokens = unit.get("tokens", len(content) // 4)
            
            tier = self.classify_content(content, filename)
            
            tiered_unit = {
                **unit,
                "tier": tier,
                "load_condition": self._get_load_condition(tier),
                "tokens": tokens
            }
            
            tiered[tier].append(tiered_unit)
            tier_tokens[tier] += tokens
        
        # Calculate optimization potential
        current_total = sum(tier_tokens.values())
        optimized_total = tier_tokens[1]  # Only Tier 1 always loaded
        savings = current_total - optimized_total
        
        return {
            "tiers": {
                "tier_1_critical": {
                    "units": tiered[1],
                    "token_count": tier_tokens[1],
                    "budget": self.TIER_BUDGETS[1],
                    "over_budget": tier_tokens[1] > self.TIER_BUDGETS[1],
                    "load_condition": "always"
                },
                "tier_2_contextual": {
                    "units": tiered[2],
                    "token_count": tier_tokens[2],
                    "budget": self.TIER_BUDGETS[2],
                    "load_condition": "on_demand"
                },
                "tier_3_reference": {
                    "units": tiered[3],
                    "token_count": tier_tokens[3],
                    "budget": self.TIER_BUDGETS[3],
                    "load_condition": "never_load_link_only"
                }
            },
            "optimization": {
                "current_startup_tokens": current_total,
                "optimized_startup_tokens": tier_tokens[1],
                "tokens_saved_per_session": savings,
                "reduction_percentage": round(savings / current_total * 100, 1) if current_total > 0 else 0
            },
            "recommendations": self._generate_recommendations(tiered, tier_tokens)
        }
    
    def _get_load_condition(self, tier: int) -> str:
        """Get load condition for a tier."""
        return {
            1: "always",
            2: "on_demand",
            3: "never_load_link_only"
        }.get(tier, "on_demand")
    
    def _generate_recommendations(self, tiered: dict, tier_tokens: dict) -> list[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Tier 1 over budget
        if tier_tokens[1] > self.TIER_BUDGETS[1]:
            over = tier_tokens[1] - self.TIER_BUDGETS[1]
            recommendations.append(
                f"⚠️ Tier 1 is {over} tokens over budget ({tier_tokens[1]}/{self.TIER_BUDGETS[1]}). "
                f"Move detailed content to Tier 2 docs and link to them."
            )
        
        # Large Tier 2 items that could be Tier 3
        for unit in tiered[2]:
            if unit.get("tokens", 0) > 1000:
                recommendations.append(
                    f"📄 '{unit.get('id', 'unknown')}' has {unit['tokens']} tokens. "
                    f"Consider moving to Tier 3 (reference) and linking."
                )
        
        # Suggest creating QUICK_REF.md if not present
        has_quick_ref = any("quick_ref" in u.get("id", "").lower() for u in tiered[1])
        if not has_quick_ref:
            recommendations.append(
                "💡 Create a QUICK_REF.md for common commands and troubleshooting. "
                "This saves ~200 tokens per common query."
            )
        
        # Suggest session hooks
        recommendations.append(
            "🚀 Implement session-start hooks to show project status and guide to relevant docs. "
            "Use: python scripts/session_hook_generator.py --project ."
        )
        
        return recommendations
    
    def optimize_claude_md(self, content: str) -> dict:
        """
        Analyze and optimize a CLAUDE.md file.
        
        Args:
            content: CLAUDE.md content
            
        Returns:
            Optimization analysis and recommendations
        """
        lines = content.split("\n")
        total_lines = len(lines)
        
        # Estimate tokens
        words = len(content.split())
        estimated_tokens = int(words * 0.75)
        
        # Analyze first 200 lines (critical zone)
        first_200 = "\n".join(lines[:200])
        first_200_words = len(first_200.split())
        first_200_tokens = int(first_200_words * 0.75)
        
        # Check for critical sections in first 200 lines
        has_overview = bool(re.search(r"##?\s*(overview|about|purpose)", first_200, re.I))
        has_quick_start = bool(re.search(r"##?\s*quick\s*start", first_200, re.I))
        has_critical_rules = bool(re.search(r"##?\s*(critical|important)\s*rules?", first_200, re.I))
        has_troubleshooting = bool(re.search(r"##?\s*troubleshoot", first_200, re.I))
        
        # Find sections that should be moved out
        verbose_sections = []
        current_section = None
        section_start = 0
        section_content = []
        
        for i, line in enumerate(lines):
            if line.startswith("## "):
                if current_section and len(section_content) > 50:
                    verbose_sections.append({
                        "name": current_section,
                        "start_line": section_start,
                        "lines": len(section_content),
                        "estimated_tokens": int(len(" ".join(section_content).split()) * 0.75)
                    })
                current_section = line[3:].strip()
                section_start = i
                section_content = []
            else:
                section_content.append(line)
        
        # Score the file
        score = 100
        issues = []
        
        if estimated_tokens > 2000:
            score -= 30
            issues.append(f"File has {estimated_tokens} tokens (target: <2000)")
        
        if first_200_tokens > 1000:
            score -= 20
            issues.append(f"First 200 lines have {first_200_tokens} tokens (target: <800)")
        
        if not has_overview:
            score -= 10
            issues.append("Missing overview section in first 200 lines")
        
        if not has_quick_start:
            score -= 10
            issues.append("Missing quick start section in first 200 lines")
        
        if not has_critical_rules:
            score -= 15
            issues.append("Missing critical rules section in first 200 lines")
        
        if not has_troubleshooting:
            score -= 5
            issues.append("Missing troubleshooting table in first 200 lines")
        
        # Generate optimized structure suggestion
        optimized_structure = self._generate_optimized_structure()
        
        return {
            "current_stats": {
                "total_lines": total_lines,
                "total_tokens": estimated_tokens,
                "first_200_lines_tokens": first_200_tokens
            },
            "critical_sections": {
                "has_overview": has_overview,
                "has_quick_start": has_quick_start,
                "has_critical_rules": has_critical_rules,
                "has_troubleshooting": has_troubleshooting
            },
            "verbose_sections": verbose_sections,
            "optimization_score": max(0, score),
            "issues": issues,
            "optimized_structure": optimized_structure,
            "potential_savings": {
                "tokens_if_optimized": min(800, first_200_tokens),
                "savings_per_session": max(0, estimated_tokens - 800),
                "monthly_savings_estimate": f"${max(0, (estimated_tokens - 800) * 0.00003 * 100 * 30):.2f}"
            }
        }
    
    def _generate_optimized_structure(self) -> str:
        """Generate recommended CLAUDE.md structure."""
        return '''# Project Name

## 🎯 Overview (50 words max)
Brief description. Tech stack summary.
**Docs:** See `docs/INDEX.md` for navigation

## 🚨 Critical Rules
1. **Never commit secrets** - Use `.env.local`
2. **Run tests before commit** - `npm test`
3. **Never force push to main** - Create PR
4. **Check migrations** - Review before deploy

## 🚀 Quick Start
**Install:** `npm install && docker-compose up -d`
**Dev:** `npm run dev` (localhost:3000)
**Test:** `npm test`
**Build:** `npm run build`

## 🐛 Troubleshooting
| Issue | Fix |
|-------|-----|
| DB connection error | `docker-compose up -d` |
| Port in use | `lsof -ti:3000 | xargs kill` |
| Type errors | `npm run type-check` |

**Full guide:** `docs/TROUBLESHOOTING.md`

## 📂 Key Files
- `src/` - Source code
- `docs/` - Documentation
- `tests/` - Test files

## 📞 Where to Find More
- **API:** `docs/API.md`
- **Database:** `docs/DATABASE.md`
- **Deployment:** `docs/DEPLOYMENT.md`
'''


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Tiered context classification")
    parser.add_argument("--input", "-f", help="Input JSON file with context units")
    parser.add_argument("--claude-md", "-c", help="Path to CLAUDE.md to analyze")
    parser.add_argument("--output", "-o", help="Output file")
    
    args = parser.parse_args()
    
    classifier = TieredContextClassifier()
    
    if args.claude_md:
        # Analyze CLAUDE.md
        with open(args.claude_md) as f:
            content = f.read()
        result = classifier.optimize_claude_md(content)
    elif args.input:
        # Classify context units
        with open(args.input) as f:
            data = json.load(f)
        units = data.get("context_units", data)
        result = classifier.classify_units(units)
    else:
        # Demo
        result = classifier.classify_units([
            {"id": "CLAUDE.md", "content": "# Project\n## Critical Rules\nNever commit secrets", "tokens": 500},
            {"id": "docs/API.md", "content": "# API Reference\nGET /users", "tokens": 1200},
            {"id": "docs/CHANGELOG.md", "content": "# Changelog\n## v1.0.0", "tokens": 800},
        ])
    
    output = json.dumps(result, indent=2)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
