#!/usr/bin/env python3
"""
Context Relevance Scorer - Score context relevance to current task.

Implements the article's relevance scoring system:
- High relevance: Currently working on (from git diff)
- Medium relevance: Related files/imports
- Low relevance: Project-wide but not directly related
- Zero relevance: Irrelevant content (should be filtered)
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelevanceScore:
    """Relevance score with explanation."""
    score: float  # 0.0 to 1.0
    category: str  # "high", "medium", "low", "zero"
    reason: str
    file_path: Optional[str] = None


@dataclass
class WorkContext:
    """Current work context detected from various signals."""
    changed_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    recent_branches: list[str] = field(default_factory=list)
    current_branch: str = ""
    active_modules: list[str] = field(default_factory=list)
    detected_intent: str = "general"  # coding, debugging, testing, docs, etc.


class ContextRelevanceScorer:
    """Scores context relevance based on current work context."""
    
    # File type relevance weights
    FILE_WEIGHTS = {
        ".md": 0.3,  # Docs are generally lower unless directly relevant
        ".json": 0.4,
        ".yaml": 0.4,
        ".yml": 0.4,
        ".ts": 0.8,
        ".tsx": 0.8,
        ".js": 0.8,
        ".jsx": 0.8,
        ".py": 0.8,
        ".java": 0.8,
        ".go": 0.8,
        ".rs": 0.8,
        ".css": 0.5,
        ".scss": 0.5,
        ".html": 0.5,
        ".sql": 0.6,
        ".prisma": 0.7,
    }
    
    # Content patterns and their base relevance
    CONTENT_PATTERNS = {
        r"\b(error|exception|failed|crash)\b": ("debugging", 0.9),
        r"\b(test|spec|describe)\b|it\(": ("testing", 0.8),
        r"\b(TODO|FIXME|HACK)\b": ("improvement", 0.7),
        r"\b(import|require)\b|from\s+['\"]": ("dependency", 0.6),
        r"\b(function|class|def|const|let|var)\b": ("definition", 0.7),
    }
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize scorer.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._work_context: Optional[WorkContext] = None
    
    def get_work_context(self) -> WorkContext:
        """Detect current work context from git and environment."""
        if self._work_context:
            return self._work_context
        
        context = WorkContext()
        
        try:
            # Get changed files (not staged)
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                context.changed_files = [
                    f.strip() for f in result.stdout.strip().split("\n") 
                    if f.strip()
                ]
            
            # Get staged files
            result = subprocess.run(
                ["git", "diff", "--staged", "--name-only"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                context.staged_files = [
                    f.strip() for f in result.stdout.strip().split("\n") 
                    if f.strip()
                ]
            
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                context.current_branch = result.stdout.strip()
            
            # Get recent branches (last 5)
            result = subprocess.run(
                ["git", "branch", "--sort=-committerdate", "--format=%(refname:short)"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                branches = result.stdout.strip().split("\n")[:5]
                context.recent_branches = [b.strip() for b in branches if b.strip()]
            
        except FileNotFoundError:
            # Git not available
            pass
        
        # Detect active modules from changed files
        for f in context.changed_files + context.staged_files:
            parts = f.split("/")
            if len(parts) > 1:
                module = parts[0]
                if module not in context.active_modules:
                    context.active_modules.append(module)
        
        # Detect intent from branch name
        branch = context.current_branch.lower()
        if any(x in branch for x in ["fix", "bug", "hotfix"]):
            context.detected_intent = "debugging"
        elif any(x in branch for x in ["test", "spec"]):
            context.detected_intent = "testing"
        elif any(x in branch for x in ["feat", "feature", "add"]):
            context.detected_intent = "coding"
        elif any(x in branch for x in ["doc", "readme"]):
            context.detected_intent = "documentation"
        elif any(x in branch for x in ["refactor", "cleanup"]):
            context.detected_intent = "refactoring"
        else:
            context.detected_intent = "general"
        
        self._work_context = context
        return context
    
    def score_file(self, file_path: str) -> RelevanceScore:
        """
        Score relevance of a file to current work context.
        
        Args:
            file_path: Path to file (relative to project root)
            
        Returns:
            RelevanceScore with score, category, and reason
        """
        context = self.get_work_context()
        path = Path(file_path)
        
        # Check if file is currently being worked on (highest relevance)
        if file_path in context.changed_files:
            return RelevanceScore(
                score=1.0,
                category="high",
                reason="Currently modified (in git diff)",
                file_path=file_path
            )
        
        if file_path in context.staged_files:
            return RelevanceScore(
                score=0.95,
                category="high", 
                reason="Staged for commit",
                file_path=file_path
            )
        
        # Check if file is in an active module
        for module in context.active_modules:
            if file_path.startswith(module + "/"):
                return RelevanceScore(
                    score=0.8,
                    category="high",
                    reason=f"In active module: {module}",
                    file_path=file_path
                )
        
        # Get base weight from file type
        suffix = path.suffix.lower()
        base_weight = self.FILE_WEIGHTS.get(suffix, 0.5)
        
        # Check if file might be related to changed files (same directory)
        for changed in context.changed_files:
            changed_path = Path(changed)
            if path.parent == changed_path.parent:
                return RelevanceScore(
                    score=0.7,
                    category="medium",
                    reason=f"Same directory as modified file: {changed}",
                    file_path=file_path
                )
        
        # Check imports/dependencies (if we can read the file)
        full_path = self.project_root / file_path
        if full_path.exists() and full_path.stat().st_size < 100000:
            try:
                content = full_path.read_text()
                # Check if this file imports any changed files
                for changed in context.changed_files:
                    changed_name = Path(changed).stem
                    if changed_name in content:
                        return RelevanceScore(
                            score=0.65,
                            category="medium",
                            reason=f"Likely imports: {changed}",
                            file_path=file_path
                        )
            except (OSError, UnicodeDecodeError):
                pass
        
        # Apply intent-based adjustments
        intent = context.detected_intent
        if intent == "testing" and ("test" in file_path.lower() or "spec" in file_path.lower()):
            return RelevanceScore(
                score=0.75,
                category="medium",
                reason="Test file relevant to testing intent",
                file_path=file_path
            )
        
        if intent == "documentation" and suffix == ".md":
            return RelevanceScore(
                score=0.7,
                category="medium",
                reason="Documentation file relevant to docs intent",
                file_path=file_path
            )
        
        # Default: low relevance based on file type
        return RelevanceScore(
            score=base_weight * 0.5,
            category="low",
            reason="Project file, not directly related to current work",
            file_path=file_path
        )
    
    def score_content(self, content: str, file_path: Optional[str] = None) -> RelevanceScore:
        """
        Score relevance of content block to current work context.
        
        Args:
            content: Text content to score
            file_path: Optional source file path
            
        Returns:
            RelevanceScore with score, category, and reason
        """
        context = self.get_work_context()
        
        # Check for references to changed files
        for changed in context.changed_files:
            if changed in content or Path(changed).stem in content:
                return RelevanceScore(
                    score=0.9,
                    category="high",
                    reason=f"References changed file: {changed}",
                    file_path=file_path
                )
        
        # Check content patterns
        for pattern, (intent_type, base_score) in self.CONTENT_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                # Boost if matches current intent
                if intent_type == context.detected_intent:
                    return RelevanceScore(
                        score=min(base_score * 1.2, 1.0),
                        category="high",
                        reason=f"Matches current intent: {intent_type}",
                        file_path=file_path
                    )
                return RelevanceScore(
                    score=base_score * 0.8,
                    category="medium",
                    reason=f"Contains {intent_type} content",
                    file_path=file_path
                )
        
        # Default: low relevance
        return RelevanceScore(
            score=0.3,
            category="low",
            reason="Generic content, no specific relevance signals",
            file_path=file_path
        )
    
    def filter_by_relevance(
        self,
        items: list[dict],
        min_score: float = 0.3,
        max_items: Optional[int] = None
    ) -> list[dict]:
        """
        Filter and sort items by relevance score.
        
        Args:
            items: List of items with 'content' and optionally 'file_path'
            min_score: Minimum relevance score to include
            max_items: Maximum items to return
            
        Returns:
            Filtered and sorted items with relevance scores added
        """
        scored_items = []
        
        for item in items:
            if "file_path" in item or "path" in item:
                file_path = item.get("file_path") or item.get("path")
                score = self.score_file(file_path)
            elif "content" in item:
                score = self.score_content(item["content"])
            else:
                continue
            
            if score.score >= min_score:
                scored_item = {
                    **item,
                    "relevance": {
                        "score": score.score,
                        "category": score.category,
                        "reason": score.reason
                    }
                }
                scored_items.append(scored_item)
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x["relevance"]["score"], reverse=True)
        
        if max_items:
            scored_items = scored_items[:max_items]
        
        return scored_items
    
    def analyze_context_waste(self, context_items: list[dict]) -> dict:
        """
        Analyze how much context might be wasted on low-relevance items.
        
        Args:
            context_items: List of context items with 'content' and 'tokens'
            
        Returns:
            Analysis of context waste
        """
        total_tokens = 0
        waste_by_category = {
            "high": {"tokens": 0, "count": 0},
            "medium": {"tokens": 0, "count": 0},
            "low": {"tokens": 0, "count": 0},
            "zero": {"tokens": 0, "count": 0}
        }
        
        for item in context_items:
            tokens = item.get("tokens", len(item.get("content", "")) // 4)
            total_tokens += tokens
            
            if "file_path" in item or "path" in item:
                file_path = item.get("file_path") or item.get("path")
                score = self.score_file(file_path)
            elif "content" in item:
                score = self.score_content(item["content"])
            else:
                score = RelevanceScore(0.0, "zero", "No content")
            
            category = score.category
            waste_by_category[category]["tokens"] += tokens
            waste_by_category[category]["count"] += 1
        
        # Calculate waste (low + zero relevance items)
        wasted_tokens = (
            waste_by_category["low"]["tokens"] + 
            waste_by_category["zero"]["tokens"]
        )
        
        waste_percentage = (wasted_tokens / total_tokens * 100) if total_tokens > 0 else 0
        
        return {
            "total_tokens": total_tokens,
            "wasted_tokens": wasted_tokens,
            "waste_percentage": round(waste_percentage, 1),
            "by_category": waste_by_category,
            "recommendation": self._get_waste_recommendation(waste_percentage)
        }
    
    def _get_waste_recommendation(self, waste_percentage: float) -> str:
        """Get recommendation based on waste percentage."""
        if waste_percentage < 10:
            return "✅ Excellent! Context is highly relevant."
        elif waste_percentage < 25:
            return "👍 Good. Minor optimization possible."
        elif waste_percentage < 40:
            return "⚠️ Moderate waste. Consider filtering low-relevance items."
        else:
            return "🚨 High waste! Filter aggressively to reduce costs."


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Score context relevance")
    parser.add_argument("--project", "-p", help="Project root directory")
    parser.add_argument("--file", "-f", help="Score specific file")
    parser.add_argument("--analyze", "-a", action="store_true", help="Analyze work context")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    scorer = ContextRelevanceScorer(args.project)
    
    if args.analyze:
        context = scorer.get_work_context()
        if args.json:
            print(json.dumps({
                "changed_files": context.changed_files,
                "staged_files": context.staged_files,
                "current_branch": context.current_branch,
                "active_modules": context.active_modules,
                "detected_intent": context.detected_intent
            }, indent=2))
        else:
            print("📊 Current Work Context")
            print(f"  Branch: {context.current_branch}")
            print(f"  Intent: {context.detected_intent}")
            print(f"  Changed files: {len(context.changed_files)}")
            for f in context.changed_files[:5]:
                print(f"    - {f}")
            print(f"  Active modules: {', '.join(context.active_modules) or 'none'}")
    
    elif args.file:
        score = scorer.score_file(args.file)
        if args.json:
            print(json.dumps({
                "file": args.file,
                "score": score.score,
                "category": score.category,
                "reason": score.reason
            }, indent=2))
        else:
            emoji = {"high": "🟢", "medium": "🟡", "low": "🟠", "zero": "🔴"}
            print(f"{emoji[score.category]} {score.category.upper()}: {score.score:.2f}")
            print(f"   {score.reason}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
