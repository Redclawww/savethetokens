#!/usr/bin/env python3
"""
Path Filter - Filters out package directories and dependency files.

Automatically excludes directories that bloat context without adding value:
- node_modules (JavaScript)
- __pycache__, .venv, venv (Python)
- vendor (Go, PHP)
- target (Rust, Java)
- .git (version control)
- build/dist outputs
"""

import os
import re
from pathlib import Path
from typing import Optional


class PathFilter:
    """Filters paths to exclude package/dependency directories."""
    
    # Directories to ALWAYS ignore - these bloat context with no value
    IGNORED_DIRECTORIES = {
        # JavaScript/Node.js
        "node_modules",
        "bower_components",
        ".npm",
        ".yarn",
        ".pnpm-store",
        
        # Python
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "virtualenv",
        ".eggs",
        "*.egg-info",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        
        # Java/Kotlin/Scala
        "target",
        ".gradle",
        ".m2",
        "build",
        
        # Rust
        "target",
        
        # Go
        "vendor",
        
        # .NET/C#
        "bin",
        "obj",
        "packages",
        
        # Ruby
        "vendor/bundle",
        ".bundle",
        
        # PHP
        "vendor",
        
        # General build outputs
        "dist",
        "out",
        "output",
        ".build",
        "_build",
        
        # IDE/Editor
        ".idea",
        ".vscode",
        ".vs",
        "*.swp",
        "*.swo",
        
        # Version control
        ".git",
        ".svn",
        ".hg",
        
        # OS files
        ".DS_Store",
        "Thumbs.db",
        
        # Coverage/test artifacts
        "coverage",
        ".coverage",
        "htmlcov",
        ".nyc_output",
        
        # Logs
        "logs",
        "*.log",
        
        # Temporary files
        "tmp",
        "temp",
        ".tmp",
        ".temp",
        ".cache",
    }
    
    # File patterns to ignore (regex)
    IGNORED_FILE_PATTERNS = [
        r"\.min\.js$",           # Minified JS
        r"\.min\.css$",          # Minified CSS
        r"\.bundle\.js$",        # Bundled JS
        r"\.map$",               # Source maps
        r"\.lock$",              # Lock files (package-lock, yarn.lock, etc.)
        r"package-lock\.json$",  # npm lock
        r"yarn\.lock$",          # yarn lock
        r"pnpm-lock\.yaml$",     # pnpm lock
        r"Gemfile\.lock$",       # Ruby lock
        r"Cargo\.lock$",         # Rust lock
        r"poetry\.lock$",        # Python poetry lock
        r"composer\.lock$",      # PHP lock
        r"\.pyc$",               # Python compiled
        r"\.pyo$",               # Python optimized
        r"\.class$",             # Java compiled
        r"\.o$",                 # C/C++ object files
        r"\.so$",                # Shared objects
        r"\.dll$",               # Windows DLLs
        r"\.exe$",               # Windows executables
        r"\.bin$",               # Binary files
        r"\.wasm$",              # WebAssembly
    ]
    
    # Maximum file size to include (in bytes) - 100KB
    MAX_FILE_SIZE = 100 * 1024
    
    def __init__(self, custom_ignores: Optional[list[str]] = None):
        """
        Initialize path filter.
        
        Args:
            custom_ignores: Additional patterns to ignore
        """
        self.ignored_dirs = self.IGNORED_DIRECTORIES.copy()
        self.ignored_patterns = [re.compile(p) for p in self.IGNORED_FILE_PATTERNS]
        
        if custom_ignores:
            for pattern in custom_ignores:
                if pattern.endswith("/"):
                    self.ignored_dirs.add(pattern.rstrip("/"))
                else:
                    self.ignored_patterns.append(re.compile(pattern))
    
    def should_ignore(self, path: str | Path) -> tuple[bool, str]:
        """
        Check if a path should be ignored.
        
        Args:
            path: File or directory path
            
        Returns:
            Tuple of (should_ignore, reason)
        """
        path = Path(path)
        
        # Check each part of the path for ignored directories
        for part in path.parts:
            if part in self.ignored_dirs:
                return True, f"Ignored directory: {part}"
            # Handle glob patterns like *.egg-info
            for ignored in self.ignored_dirs:
                if "*" in ignored:
                    pattern = ignored.replace("*", ".*")
                    if re.match(pattern, part):
                        return True, f"Matches ignored pattern: {ignored}"
        
        # Check file patterns
        filename = path.name
        for pattern in self.ignored_patterns:
            if pattern.search(filename):
                return True, f"Matches ignored file pattern"
        
        # Check file size if it's a file
        if path.is_file():
            try:
                size = path.stat().st_size
                if size > self.MAX_FILE_SIZE:
                    return True, f"File too large: {size / 1024:.1f}KB > {self.MAX_FILE_SIZE / 1024:.1f}KB"
            except OSError:
                pass
        
        return False, ""
    
    def filter_paths(self, paths: list[str]) -> tuple[list[str], list[dict]]:
        """
        Filter a list of paths, removing ignored ones.
        
        Args:
            paths: List of file paths
            
        Returns:
            Tuple of (kept_paths, filtered_info)
        """
        kept = []
        filtered = []
        
        for path in paths:
            should_ignore, reason = self.should_ignore(path)
            if should_ignore:
                filtered.append({"path": path, "reason": reason})
            else:
                kept.append(path)
        
        return kept, filtered
    
    def filter_context_units(self, units: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Filter context units, removing those from ignored paths.
        
        Args:
            units: List of context unit dicts
            
        Returns:
            Tuple of (kept_units, filtered_units)
        """
        kept = []
        filtered = []
        
        for unit in units:
            # Check if unit has a path/file reference
            path = unit.get("path") or unit.get("file") or unit.get("id", "")
            
            # Skip non-file units (messages, system prompts, etc.)
            if unit.get("type") in ("system", "message", "instruction", "error"):
                kept.append(unit)
                continue
            
            should_ignore, reason = self.should_ignore(path)
            if should_ignore:
                filtered.append({
                    **unit,
                    "filtered_reason": reason
                })
            else:
                kept.append(unit)
        
        return kept, filtered
    
    def scan_directory(
        self, 
        root: str | Path, 
        extensions: Optional[list[str]] = None
    ) -> list[str]:
        """
        Scan a directory for files, automatically filtering ignored paths.
        
        Args:
            root: Root directory to scan
            extensions: Optional list of extensions to include (e.g., ['.py', '.js'])
            
        Returns:
            List of file paths (relative to root)
        """
        root = Path(root)
        files = []
        
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            
            # Check extensions
            if extensions and path.suffix.lower() not in extensions:
                continue
            
            # Check if should ignore
            should_ignore, _ = self.should_ignore(path)
            if not should_ignore:
                files.append(str(path.relative_to(root)))
        
        return files
    
    @classmethod
    def get_gitignore_patterns(cls, root: str | Path) -> list[str]:
        """
        Read patterns from .gitignore file.
        
        Args:
            root: Project root directory
            
        Returns:
            List of gitignore patterns
        """
        gitignore = Path(root) / ".gitignore"
        patterns = []
        
        if gitignore.exists():
            try:
                with open(gitignore) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except OSError:
                pass
        
        return patterns


def main():
    """CLI entry point."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Filter paths for context optimization")
    parser.add_argument("--scan", "-s", help="Directory to scan")
    parser.add_argument("--check", "-c", help="Check if a path should be ignored")
    parser.add_argument("--extensions", "-e", nargs="+", help="File extensions to include")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    filter = PathFilter()
    
    if args.check:
        should_ignore, reason = filter.should_ignore(args.check)
        if args.json:
            print(json.dumps({
                "path": args.check,
                "ignored": should_ignore,
                "reason": reason
            }))
        else:
            if should_ignore:
                print(f"IGNORE: {args.check} ({reason})")
            else:
                print(f"KEEP: {args.check}")
    
    elif args.scan:
        extensions = args.extensions
        if extensions:
            extensions = [e if e.startswith(".") else f".{e}" for e in extensions]
        
        files = filter.scan_directory(args.scan, extensions)
        
        if args.json:
            print(json.dumps({"files": files, "count": len(files)}))
        else:
            for f in files:
                print(f)
            print(f"\nTotal: {len(files)} files")
    
    else:
        # Read paths from stdin
        import sys
        paths = [line.strip() for line in sys.stdin if line.strip()]
        kept, filtered = filter.filter_paths(paths)
        
        if args.json:
            print(json.dumps({
                "kept": kept,
                "filtered": filtered,
                "kept_count": len(kept),
                "filtered_count": len(filtered)
            }))
        else:
            print("Kept files:")
            for p in kept:
                print(f"  {p}")
            print(f"\nFiltered out {len(filtered)} files")


if __name__ == "__main__":
    main()
