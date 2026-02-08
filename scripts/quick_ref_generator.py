#!/usr/bin/env python3
"""
Quick Reference Generator - Creates QUICK_REF.md cheat sheets

Generates one-page reference cards with:
- Essential commands (copy-paste ready)
- Common troubleshooting (instant fixes)
- Critical rules (never do this)
- Tech stack overview
- Quick links to detailed docs
"""

import json
import sys
from pathlib import Path
from typing import Optional


class QuickReferenceGenerator:
    """Generates optimized QUICK_REF.md documentation."""
    
    # Common project patterns
    TECH_STACKS = {
        "mern": {
            "name": "MERN Stack",
            "layers": {
                "Frontend": "React + TypeScript",
                "Backend": "Express.js + Node.js",
                "Database": "MongoDB",
                "Cache": "Redis (optional)"
            }
        },
        "django": {
            "name": "Django",
            "layers": {
                "Backend": "Django + Python",
                "Database": "PostgreSQL",
                "Cache": "Redis",
                "Queue": "Celery"
            }
        },
        "rails": {
            "name": "Ruby on Rails",
            "layers": {
                "Backend": "Rails + Ruby",
                "Database": "PostgreSQL",
                "Cache": "Redis",
                "Jobs": "Sidekiq"
            }
        }
    }
    
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self.project_name = self.project_root.name
    
    def generate(
        self,
        commands: Optional[dict] = None,
        issues: Optional[list[dict]] = None,
        rules: Optional[list[str]] = None,
        tech_stack: Optional[dict] = None
    ) -> str:
        """
        Generate QUICK_REF.md content.
        
        Args:
            commands: Dict of command categories and their commands
            issues: List of common issues with fixes
            rules: List of critical rules
            tech_stack: Tech stack layers
            
        Returns:
            QUICK_REF.md markdown content
        """
        sections = []
        
        # Header
        sections.append(f"# Quick Reference - {self.project_name}")
        sections.append("")
        sections.append("One-page cheat sheet for common tasks and fixes.")
        sections.append("")
        sections.append("---")
        sections.append("")
        
        # Essential Commands
        if commands:
            sections.append("## Essential Commands")
            sections.append("")
            sections.append("```bash")
            
            for category, cmds in commands.items():
                sections.append(f"# {category}")
                for cmd_name, cmd in cmds.items():
                    sections.append(f"{cmd:<40}# {cmd_name}")
                sections.append("")
            
            sections.append("```")
            sections.append("")
        else:
            # Default template
            sections.extend([
                "## Essential Commands",
                "",
                "```bash",
                "# Development",
                "[dev-command]                           # Start dev server",
                "[test-command]                          # Run tests",
                "[build-command]                         # Build for production",
                "",
                "# Database",
                "[db-start-command]                      # Start database",
                "[db-migrate-command]                    # Run migrations",
                "[db-gui-command]                        # Open DB GUI",
                "",
                "# Docker",
                "docker-compose up -d                    # Start services",
                "docker-compose down                     # Stop services",
                "docker-compose logs -f                  # View logs",
                "```",
                ""
            ])
        
        # Common Issues
        sections.append("## Common Issues & Fixes")
        sections.append("")
        sections.append("| Problem | Solution |")
        sections.append("|---------|----------|")
        
        if issues:
            for issue in issues:
                problem = issue.get("problem", "")
                solution = issue.get("solution", "")
                sections.append(f"| {problem} | `{solution}` |")
        else:
            # Default template
            sections.extend([
                "| Port already in use | `lsof -ti:[PORT] | xargs kill -9` |",
                "| Database not connecting | `docker-compose up -d` |",
                "| Tests failing | `[test-command] --verbose` |",
                "| Type errors | `[type-check-command]` |",
                "| Slow performance | Check docs/PERFORMANCE.md |"
            ])
        
        sections.append("")
        sections.append("**Full troubleshooting:** `docs/TROUBLESHOOTING.md`")
        sections.append("")
        
        # Critical Rules
        sections.append("## Critical Rules")
        sections.append("")
        
        if rules:
            for rule in rules:
                sections.append(f"- {rule}")
        else:
            sections.extend([
                "- ✅ **DO** run tests before committing",
                "- ✅ **DO** use TypeScript strict mode",
                "- ✅ **DO** review migrations before deploy",
                "- ❌ **DON'T** commit secrets (.env.local)",
                "- ❌ **DON'T** force push to main",
                "- ❌ **DON'T** skip code review"
            ])
        
        sections.append("")
        
        # Tech Stack
        sections.append("## Tech Stack")
        sections.append("")
        sections.append("| Layer | Technology |")
        sections.append("|-------|------------|")
        
        if tech_stack:
            for layer, tech in tech_stack.items():
                sections.append(f"| {layer} | {tech} |")
        else:
            sections.extend([
                "| Frontend | [framework] |",
                "| Backend | [framework] |",
                "| Database | [database] |",
                "| Cache | [cache] |"
            ])
        
        sections.append("")
        
        # Project Structure
        sections.append("## Project Structure")
        sections.append("")
        sections.append("```")
        sections.append(self._generate_structure_tree())
        sections.append("```")
        sections.append("")
        
        # Links
        sections.append("## Documentation Links")
        sections.append("")
        sections.append("- 📖 [Full Documentation](docs/INDEX.md)")
        sections.append("- 🔌 [API Reference](docs/API.md)")
        sections.append("- 🗄️ [Database Schema](docs/DATABASE.md)")
        sections.append("- 🧪 [Testing Guide](docs/TESTING.md)")
        sections.append("- 🚀 [Deployment](docs/DEPLOYMENT.md)")
        sections.append("")
        
        # Footer
        sections.append("---")
        sections.append("")
        sections.append("**💡 Tip:** Keep this file under 200 lines for instant loading.")
        sections.append("")
        
        return "\n".join(sections)
    
    def _generate_structure_tree(self) -> str:
        """Generate basic project structure tree."""
        # Check what exists
        structure = [f"{self.project_name}/"]
        
        common_dirs = [
            ("src/", "Source code"),
            ("tests/", "Test files"),
            ("docs/", "Documentation"),
            ("config/", "Configuration"),
            ("scripts/", "Utility scripts"),
            (".github/", "CI/CD workflows")
        ]
        
        for dir_name, description in common_dirs:
            if (self.project_root / dir_name.rstrip("/")).exists():
                structure.append(f"├── {dir_name:<20} # {description}")
        
        # Common files
        common_files = [
            ("package.json", "Node.js dependencies"),
            ("requirements.txt", "Python dependencies"),
            ("Cargo.toml", "Rust dependencies"),
            ("go.mod", "Go dependencies"),
            ("docker-compose.yml", "Docker services"),
            ("README.md", "Project overview")
        ]
        
        for file_name, description in common_files:
            if (self.project_root / file_name).exists():
                structure.append(f"├── {file_name:<20} # {description}")
        
        return "\n".join(structure)
    
    def detect_commands(self) -> dict:
        """
        Auto-detect commands from project files.
        
        Returns:
            Dict of categorized commands
        """
        commands = {}
        
        # Check package.json (Node.js)
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                import json as json_module
                data = json_module.loads(package_json.read_text())
                scripts = data.get("scripts", {})
                
                if scripts:
                    commands["Development"] = {}
                    for script_name in ["dev", "start", "build", "test"]:
                        if script_name in scripts:
                            commands["Development"][script_name.title()] = f"npm run {script_name}"
            except:
                pass
        
        # Check for Docker
        if (self.project_root / "docker-compose.yml").exists():
            commands["Docker"] = {
                "Start services": "docker-compose up -d",
                "Stop services": "docker-compose down",
                "View logs": "docker-compose logs -f"
            }
        
        # Check for Python
        if (self.project_root / "manage.py").exists():  # Django
            commands["Development"] = {
                "Dev server": "python manage.py runserver",
                "Migrations": "python manage.py migrate",
                "Shell": "python manage.py shell"
            }
        elif (self.project_root / "requirements.txt").exists():
            commands["Python"] = {
                "Install deps": "pip install -r requirements.txt",
                "Run tests": "pytest"
            }
        
        return commands
    
    def create_file(self, output_dir: Optional[str | Path] = None) -> Path:
        """
        Create QUICK_REF.md file.
        
        Args:
            output_dir: Directory for docs/ (defaults to project root)
            
        Returns:
            Path to created file
        """
        if output_dir is None:
            output_dir = self.project_root
        
        docs_dir = Path(output_dir) / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        quick_ref = docs_dir / "QUICK_REF.md"
        
        # Detect commands if possible
        commands = self.detect_commands()
        
        content = self.generate(commands=commands if commands else None)
        quick_ref.write_text(content)
        
        return quick_ref


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate QUICK_REF.md cheat sheets"
    )
    parser.add_argument(
        "--project", "-p",
        default=".",
        help="Project root directory (default: current)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory (default: project/docs/)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print content without creating file"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Auto-detect commands from project files"
    )
    
    args = parser.parse_args()
    
    generator = QuickReferenceGenerator(args.project)
    
    if args.detect:
        # Show detected commands
        commands = generator.detect_commands()
        print("Detected commands:")
        print(json.dumps(commands, indent=2))
        return 0
    
    if args.dry_run:
        content = generator.generate()
        print(content)
    else:
        quick_ref = generator.create_file(args.output)
        print(f"✅ Created QUICK_REF.md: {quick_ref}")
        print(f"\n💡 Customize the template with your project specifics:")
        print(f"   - Add your most-used commands")
        print(f"   - List your common issues")
        print(f"   - Document critical rules")
        print(f"\nTarget: Keep under 200 lines for instant loading")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
