#!/usr/bin/env python3
"""
CLAUDE.md Optimizer - Analyzes and optimizes CLAUDE.md files

Implements tiered documentation approach:
- Tier 1 (Critical): First 200 lines, <800 tokens - always loaded
- Tier 2 (Contextual): Referenced docs - loaded on demand  
- Tier 3 (Reference): Linked only - never loaded

Based on best practices from context optimization research.
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from estimate_tokens import TokenEstimator


@dataclass
class DocumentAnalysis:
    """Analysis results for a documentation file."""
    total_lines: int
    total_tokens: int
    first_200_lines_tokens: int
    sections: list[dict]
    issues: list[dict]
    recommendations: list[str]
    optimization_potential: int  # Estimated token savings


class CLAUDEMdOptimizer:
    """Optimizes CLAUDE.md files for efficient context usage."""
    
    # Recommended token budgets
    TARGET_FIRST_200_TOKENS = 800
    MAX_FIRST_200_TOKENS = 1000
    
    # Section patterns that can be moved to separate docs
    MOVEABLE_SECTIONS = {
        "API": "docs/API.md",
        "Database": "docs/DATABASE.md",
        "Testing": "docs/TESTING.md",
        "Deployment": "docs/DEPLOYMENT.md",
        "Architecture": "docs/ARCHITECTURE.md",
        "Troubleshooting": "docs/TROUBLESHOOTING.md"
    }
    
    def __init__(self):
        self.estimator = TokenEstimator()
    
    def analyze(self, claude_md_path: str | Path) -> DocumentAnalysis:
        """
        Analyze CLAUDE.md file and identify optimization opportunities.
        
        Args:
            claude_md_path: Path to CLAUDE.md file
            
        Returns:
            Detailed analysis with recommendations
        """
        path = Path(claude_md_path)
        
        if not path.exists():
            raise FileNotFoundError(f"CLAUDE.md not found: {path}")
        
        content = path.read_text()
        lines = content.split("\n")
        
        # Analyze full document
        total_tokens = self.estimator.estimate(content, "markdown")
        
        # Analyze first 200 lines
        first_200 = "\n".join(lines[:200])
        first_200_tokens = self.estimator.estimate(first_200, "markdown")
        
        # Extract sections
        sections = self._extract_sections(lines)
        
        # Identify issues
        issues = []
        recommendations = []
        
        # Check first 200 lines token budget
        if first_200_tokens > self.MAX_FIRST_200_TOKENS:
            issues.append({
                "severity": "high",
                "issue": f"First 200 lines exceed recommended budget",
                "current": first_200_tokens,
                "target": self.TARGET_FIRST_200_TOKENS,
                "excess": first_200_tokens - self.TARGET_FIRST_200_TOKENS
            })
            recommendations.append(
                f"Reduce first 200 lines by {first_200_tokens - self.TARGET_FIRST_200_TOKENS} tokens"
            )
        
        # Check for moveable sections in first 200 lines
        for section in sections:
            if section["start_line"] < 200:
                for keyword, target_file in self.MOVEABLE_SECTIONS.items():
                    if keyword.lower() in section["title"].lower():
                        if section["tokens"] > 200:
                            issues.append({
                                "severity": "medium",
                                "issue": f"Large {keyword} section in first 200 lines",
                                "section": section["title"],
                                "tokens": section["tokens"],
                                "suggestion": f"Move to {target_file}"
                            })
                            recommendations.append(
                                f"Move '{section['title']}' section to {target_file}"
                            )
        
        # Check for duplicate content
        if self._has_duplicate_troubleshooting(content):
            issues.append({
                "severity": "low",
                "issue": "Duplicate troubleshooting content detected",
                "suggestion": "Consolidate into docs/TROUBLESHOOTING.md"
            })
            recommendations.append("Create centralized docs/TROUBLESHOOTING.md")
        
        # Check for missing quick reference
        if not self._has_quick_reference(content):
            recommendations.append("Add quick reference section (commands, issues)")
        
        # Calculate optimization potential
        optimization_potential = 0
        for issue in issues:
            if "excess" in issue:
                optimization_potential += issue["excess"]
            elif "tokens" in issue and issue["tokens"] > 200:
                optimization_potential += issue["tokens"] - 50  # Keep summary
        
        return DocumentAnalysis(
            total_lines=len(lines),
            total_tokens=total_tokens,
            first_200_lines_tokens=first_200_tokens,
            sections=sections,
            issues=issues,
            recommendations=recommendations,
            optimization_potential=optimization_potential
        )
    
    def _extract_sections(self, lines: list[str]) -> list[dict]:
        """Extract markdown sections from lines."""
        sections = []
        current_section = None
        
        for i, line in enumerate(lines):
            # Match markdown headers (## or ###)
            if line.startswith("##"):
                # Save previous section
                if current_section:
                    content = "\n".join(lines[current_section["start_line"]:i])
                    current_section["tokens"] = self.estimator.estimate(content, "markdown")
                    current_section["end_line"] = i - 1
                    sections.append(current_section)
                
                # Start new section
                level = len(re.match(r"^#+", line).group())
                title = line.lstrip("#").strip()
                current_section = {
                    "title": title,
                    "level": level,
                    "start_line": i,
                    "end_line": None,
                    "tokens": 0
                }
        
        # Add last section
        if current_section:
            content = "\n".join(lines[current_section["start_line"]:])
            current_section["tokens"] = self.estimator.estimate(content, "markdown")
            current_section["end_line"] = len(lines) - 1
            sections.append(current_section)
        
        return sections
    
    def _has_duplicate_troubleshooting(self, content: str) -> bool:
        """Check if troubleshooting info appears multiple times."""
        troubleshooting_patterns = [
            r"docker-compose up",
            r"database.*connection.*error",
            r"port.*already.*in.*use"
        ]
        
        matches = 0
        for pattern in troubleshooting_patterns:
            if len(re.findall(pattern, content, re.IGNORECASE)) > 1:
                matches += 1
        
        return matches >= 2
    
    def _has_quick_reference(self, content: str) -> bool:
        """Check if document has a quick reference section."""
        return bool(re.search(r"##.*quick.*ref", content, re.IGNORECASE))
    
    def generate_optimized_version(self, claude_md_path: str | Path) -> str:
        """
        Generate optimized version of CLAUDE.md.
        
        Returns:
            Optimized content
        """
        path = Path(claude_md_path)
        content = path.read_text()
        lines = content.split("\n")
        
        analysis = self.analyze(path)
        
        # Build optimized version
        optimized = []
        
        # Add optimization header
        optimized.extend([
            "# Project Name",
            "",
            "## 🎯 Overview (50 words max)",
            "[Project description - keep it under 50 words]",
            "",
            "## 🚨 Critical Rules",
            "1. ✅ Run tests before commit",
            "2. ❌ Never commit secrets",
            "3. ❌ Never force push to main",
            "4. ✅ Review migrations before deploy",
            "",
            "## 🚀 Quick Start",
            "**Install:** [install command]",
            "**Dev:** [dev command]",
            "**Test:** [test command]",
            "",
            "## 🐛 Common Issues",
            "| Issue | Fix |",
            "|-------|-----|",
            "| Database error | `docker-compose up -d` |",
            "| Port in use | `lsof -ti:3000 | xargs kill -9` |",
            "",
            "**Full troubleshooting:** `docs/TROUBLESHOOTING.md`",
            "",
            "## 📚 Documentation",
            "- **Quick Reference:** `docs/QUICK_REF.md` (one-page cheat sheet)",
            "- **API:** `docs/API.md`",
            "- **Database:** `docs/DATABASE.md`",
            "- **Testing:** `docs/TESTING.md`",
            "- **Deployment:** `docs/DEPLOYMENT.md`",
            "",
            "## 📂 Project Structure",
            "[Brief structure overview - 10 lines max]",
            "",
            "---",
            "",
            "# Detailed Documentation (Below Line 200)",
            "[Original detailed content - only loaded when specifically requested]",
            ""
        ])
        
        # Add original content after marker
        optimized.extend(lines)
        
        return "\n".join(optimized)
    
    def calculate_cost_savings(
        self,
        current_tokens: int,
        optimized_tokens: int,
        sessions_per_day: int = 20,
        developers: int = 1,
        cost_per_1k_tokens: float = 0.003
    ) -> dict:
        """
        Calculate cost savings from optimization.
        
        Returns:
            Cost analysis with savings
        """
        tokens_saved_per_session = current_tokens - optimized_tokens
        sessions_per_month = sessions_per_day * developers * 22  # 22 work days
        
        current_cost_per_session = (current_tokens / 1000) * cost_per_1k_tokens
        optimized_cost_per_session = (optimized_tokens / 1000) * cost_per_1k_tokens
        
        monthly_current = current_cost_per_session * sessions_per_month
        monthly_optimized = optimized_cost_per_session * sessions_per_month
        monthly_savings = monthly_current - monthly_optimized
        
        return {
            "tokens_saved_per_session": tokens_saved_per_session,
            "reduction_percentage": (tokens_saved_per_session / current_tokens * 100)
                                   if current_tokens > 0 else 0,
            "cost_per_session": {
                "current": round(current_cost_per_session, 4),
                "optimized": round(optimized_cost_per_session, 4),
                "savings": round(current_cost_per_session - optimized_cost_per_session, 4)
            },
            "monthly_cost": {
                "current": round(monthly_current, 2),
                "optimized": round(monthly_optimized, 2),
                "savings": round(monthly_savings, 2)
            },
            "annual_savings": round(monthly_savings * 12, 2)
        }


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze and optimize CLAUDE.md files"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="CLAUDE.md",
        help="Path to CLAUDE.md (default: ./CLAUDE.md)"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze current file"
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Generate optimized version"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for optimized version"
    )
    parser.add_argument(
        "--cost",
        action="store_true",
        help="Calculate cost savings"
    )
    parser.add_argument(
        "--sessions-per-day",
        type=int,
        default=20,
        help="Sessions per developer per day (default: 20)"
    )
    parser.add_argument(
        "--developers",
        type=int,
        default=1,
        help="Number of developers (default: 1)"
    )
    
    args = parser.parse_args()
    
    optimizer = CLAUDEMdOptimizer()
    
    try:
        if args.analyze or (not args.optimize and not args.cost):
            # Analyze
            analysis = optimizer.analyze(args.file)
            
            print(f"📊 CLAUDE.md Analysis: {args.file}")
            print("=" * 60)
            print(f"Total lines: {analysis.total_lines}")
            print(f"Total tokens: {analysis.total_tokens}")
            print(f"First 200 lines: {analysis.first_200_lines_tokens} tokens")
            print(f"Target: {optimizer.TARGET_FIRST_200_TOKENS} tokens")
            
            if analysis.first_200_lines_tokens > optimizer.TARGET_FIRST_200_TOKENS:
                excess = analysis.first_200_lines_tokens - optimizer.TARGET_FIRST_200_TOKENS
                print(f"⚠️  Excess: {excess} tokens ({excess/analysis.first_200_lines_tokens*100:.1f}%)")
            else:
                print("✅ Within target budget")
            
            print(f"\n📑 Sections: {len(analysis.sections)}")
            for section in analysis.sections[:10]:
                status = "📍" if section["start_line"] < 200 else "📄"
                print(f"  {status} {section['title']}: {section['tokens']} tokens (lines {section['start_line']}-{section['end_line']})")
            
            if len(analysis.sections) > 10:
                print(f"  ... and {len(analysis.sections) - 10} more sections")
            
            if analysis.issues:
                print(f"\n⚠️  Issues Found: {len(analysis.issues)}")
                for issue in analysis.issues:
                    print(f"  [{issue['severity'].upper()}] {issue['issue']}")
                    if "suggestion" in issue:
                        print(f"     → {issue['suggestion']}")
            
            if analysis.recommendations:
                print(f"\n💡 Recommendations:")
                for rec in analysis.recommendations:
                    print(f"  • {rec}")
            
            if analysis.optimization_potential > 0:
                print(f"\n✨ Optimization Potential: {analysis.optimization_potential} tokens")
                print(f"   ({analysis.optimization_potential/analysis.total_tokens*100:.1f}% reduction possible)")
        
        if args.optimize:
            # Generate optimized version
            optimized = optimizer.generate_optimized_version(args.file)
            
            if args.output:
                Path(args.output).write_text(optimized)
                print(f"✅ Optimized version saved to: {args.output}")
            else:
                print(optimized)
        
        if args.cost:
            # Calculate cost savings
            analysis = optimizer.analyze(args.file)
            optimized_tokens = max(
                optimizer.TARGET_FIRST_200_TOKENS,
                analysis.first_200_lines_tokens - analysis.optimization_potential
            )
            
            savings = optimizer.calculate_cost_savings(
                analysis.first_200_lines_tokens,
                optimized_tokens,
                args.sessions_per_day,
                args.developers
            )
            
            print(f"\n💰 Cost Analysis")
            print("=" * 60)
            print(f"Sessions/day per developer: {args.sessions_per_day}")
            print(f"Developers: {args.developers}")
            print(f"Tokens saved per session: {savings['tokens_saved_per_session']}")
            print(f"Reduction: {savings['reduction_percentage']:.1f}%")
            print(f"\nCost per session:")
            print(f"  Current: ${savings['cost_per_session']['current']}")
            print(f"  Optimized: ${savings['cost_per_session']['optimized']}")
            print(f"  Savings: ${savings['cost_per_session']['savings']}")
            print(f"\nMonthly cost:")
            print(f"  Current: ${savings['monthly_cost']['current']}")
            print(f"  Optimized: ${savings['monthly_cost']['optimized']}")
            print(f"  Savings: ${savings['monthly_cost']['savings']}")
            print(f"\n📈 Annual savings: ${savings['annual_savings']}")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
