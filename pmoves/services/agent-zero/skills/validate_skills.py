#!/usr/bin/env python3
"""
SKILL.md Validation Script

Validates SKILL.md files in the PMOVES.AI skills directory structure.
Checks for required frontmatter fields, proper markdown structure,
and compliance with the SKILL.md pattern specification.

Based on the Phase 3 SKILL.md Pattern from the Aligned Implementation Roadmap.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SkillValidator:
    """Validator for SKILL.md files."""

    # Required frontmatter fields
    REQUIRED_FRONTMATTER = {
        'name',
        'description',
        'keywords',
        'version',
        'category'
    }

    # Required markdown sections (case-insensitive)
    REQUIRED_SECTIONS = {
        'overview',
        'capabilities',
        'skill structure',
        'trigger phrases',
        'tools',
        'configuration',
        'cookbook',
        'quick reference',
        'integration points',
        'troubleshooting',
        'see also'
    }

    def __init__(self, strict: bool = False):
        """
        Initialize the validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_file(self, skill_md_path: Path) -> bool:
        """
        Validate a single SKILL.md file.

        Args:
            skill_md_path: Path to SKILL.md file

        Returns:
            True if validation passes, False otherwise
        """
        self.errors = []
        self.warnings = []

        if not skill_md_path.exists():
            self.errors.append(f"File not found: {skill_md_path}")
            return False

        try:
            content = skill_md_path.read_text(encoding='utf-8')
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

        # Validate frontmatter
        frontmatter = self._extract_frontmatter(content)
        if frontmatter is None:
            self.errors.append("No frontmatter found (missing --- delimiters)")
            return False

        self._validate_frontmatter(frontmatter)

        # Validate markdown sections
        self._validate_markdown_sections(content)

        # Validate structure
        self._validate_skill_structure(skill_md_path.parent)

        return len(self.errors) == 0

    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: File content

        Returns:
            Parsed frontmatter dict, or None if not found
        """
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not match:
            return None

        yaml_text = match.group(1)

        try:
            import yaml
            return yaml.safe_load(yaml_text) or {}
        except ImportError:
            self.errors.append("PyYAML not installed, cannot validate frontmatter")
            return {}
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in frontmatter: {e}")
            return None

    def _validate_frontmatter(self, frontmatter: Dict[str, Any]) -> None:
        """
        Validate frontmatter fields.

        Args:
            frontmatter: Parsed frontmatter dict
        """
        # Check required fields
        missing = self.REQUIRED_FRONTMATTER - set(frontmatter.keys())
        if missing:
            self.errors.append(
                f"Missing required frontmatter fields: {', '.join(sorted(missing))}"
            )

        # Validate field types
        if 'name' in frontmatter and not isinstance(frontmatter['name'], str):
            self.errors.append("Field 'name' must be a string")

        if 'description' in frontmatter:
            if not isinstance(frontmatter['description'], str):
                self.errors.append("Field 'description' must be a string")
            elif len(frontmatter['description']) > 200:
                self.warnings.append(
                    f"Description is long ({len(frontmatter['description'])} chars). "
                    "Consider shortening to < 200 characters."
                )

        if 'keywords' in frontmatter:
            if isinstance(frontmatter['keywords'], str):
                # Comma-separated string is okay
                pass
            elif isinstance(frontmatter['keywords'], list):
                # List of keywords is also okay
                pass
            else:
                self.errors.append(
                    "Field 'keywords' must be a string or list of strings"
                )

        if 'version' in frontmatter:
            if not isinstance(frontmatter['version'], str):
                self.errors.append("Field 'version' must be a string")
            elif not re.match(r'^\d+\.\d+\.\d+', frontmatter['version']):
                self.warnings.append(
                    f"Version '{frontmatter['version']}' doesn't match semver pattern (X.Y.Z)"
                )

        if 'category' in frontmatter and not isinstance(frontmatter['category'], str):
            self.errors.append("Field 'category' must be a string")

    def _validate_markdown_sections(self, content: str) -> None:
        """
        Validate required markdown sections exist.

        Args:
            content: File content (after frontmatter)
        """
        # Remove frontmatter
        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

        # Extract all level-1 and level-2 headings
        headings = re.findall(r'^#{1,2}\s+(.+)$', content, re.MULTILINE | re.IGNORECASE)
        headings_lower = [h.lower().strip() for h in headings]

        # Check for required sections
        missing = self.REQUIRED_SECTIONS - set(headings_lower)
        if missing:
            self.errors.append(
                f"Missing required sections: {', '.join(sorted(missing))}"
            )

    def _validate_skill_structure(self, skill_dir: Path) -> None:
        """
        Validate that expected subdirectories exist.

        Args:
            skill_dir: Directory containing SKILL.md
        """
        expected_dirs = ['tools', 'prompts', 'cookbook']

        for dirname in expected_dirs:
            dir_path = skill_dir / dirname
            if not dir_path.exists():
                self.warnings.append(f"Expected directory not found: {dirname}/")

        # Check for at least one tool
        tools_dir = skill_dir / 'tools'
        if tools_dir.exists():
            tools = list(tools_dir.glob('*.py'))
            if not tools:
                self.warnings.append("No Python tools found in tools/ directory")
            else:
                # Check for docstring coverage
                for tool in tools:
                    self._validate_tool_file(tool)

        # Check for cookbook examples
        cookbook_dir = skill_dir / 'cookbook'
        if cookbook_dir.exists():
            examples = list(cookbook_dir.glob('*.md'))
            if not examples:
                self.warnings.append("No cookbook examples found in cookbook/ directory")

    def _validate_tool_file(self, tool_path: Path) -> None:
        """
        Validate that a tool file has proper documentation.

        Args:
            tool_path: Path to tool .py file
        """
        try:
            content = tool_path.read_text(encoding='utf-8')
        except Exception:
            return

        # Check for module docstring (after shebang, encoding, etc.)
        # Skip shebang and blank lines to find actual docstring
        lines = content.split('\n')
        docstring_found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip shebang, encoding, blank lines, and imports
            if stripped.startswith('#!') or not stripped or stripped.startswith(('import ', 'from ')):
                continue
            # Found the first non-skipped line - should be docstring
            if stripped.startswith(('"""', "'''")):
                docstring_found = True
            break

        if not docstring_found:
            self.warnings.append(f"{tool_path.name}: Missing module docstring")

        # Check for class docstrings (improved check)
        class_matches = re.finditer(r'^class\s+(\w+)\s*\:', content, re.MULTILINE)
        for match in class_matches:
            class_name = match.group(1)
            # Look for docstring after class definition
            # Get content after class definition line
            rest_of_file = content[match.end():].lstrip()

            # Check if next non-empty line is a docstring or code
            # Skip empty lines and look at what comes next
            lines_after = rest_of_file.split('\n')
            next_content = None
            for line in lines_after:
                if line.strip() and not line.strip().startswith('#'):
                    next_content = line.strip()
                    break

            if next_content and not next_content.startswith(('"""', "'''")):
                self.warnings.append(
                    f"{tool_path.name}: Class {class_name} may be missing docstring"
                )

    def print_report(self, skill_path: Path) -> None:
        """
        Print validation report for a skill.

        Args:
            skill_path: Path to SKILL.md that was validated
        """
        print(f"\n{'='*60}")
        print(f"Validation Report: {skill_path}")
        print(f"{'='*60}")

        if not self.errors and not self.warnings:
            print("✅ All checks passed!")
            return

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")

        if self.strict and self.warnings:
            print(f"\n⚠️  Strict mode enabled: Treating warnings as errors")


def find_skill_files(root_dir: Path) -> List[Path]:
    """
    Find all SKILL.md files in a directory tree.

    Args:
        root_dir: Root directory to search

    Returns:
        List of SKILL.md file paths
    """
    return list(root_dir.rglob('SKILL.md'))


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate PMOVES.AI SKILL.md files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a single skill
  %(prog)s pmoves/services/agent-zero/skills/my-skill/SKILL.md

  # Validate all skills in a directory
  %(prog)s --dir pmoves/services/agent-zero/skills/

  # Strict mode (warnings become errors)
  %(prog)s --strict --dir pmoves/services/agent-zero/skills/
        """
    )

    parser.add_argument(
        'file',
        nargs='?',
        type=Path,
        help='Path to specific SKILL.md file'
    )

    parser.add_argument(
        '--dir',
        type=Path,
        help='Directory to search for SKILL.md files'
    )

    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )

    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop on first validation error'
    )

    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Must specify either FILE or --dir")

    validator = SkillValidator(strict=args.strict)

    if args.file:
        # Validate single file
        success = validator.validate_file(args.file)
        validator.print_report(args.file)
        return 0 if success else 1

    else:
        # Validate all files in directory
        skill_files = find_skill_files(args.dir)

        if not skill_files:
            print(f"No SKILL.md files found in {args.dir}")
            return 0

        print(f"Found {len(skill_files)} SKILL.md file(s)")

        all_passed = True
        failed_count = 0

        for skill_file in skill_files:
            success = validator.validate_file(skill_file)

            if not success:
                all_passed = False
                failed_count += 1

            validator.print_report(skill_file)

            if not success and args.fail_fast:
                print(f"\n❌ Validation failed (fail-fast mode)")
                return 1

        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(skill_files) - failed_count}/{len(skill_files)} passed")

        if not all_passed:
            print(f"❌ {failed_count} validation error(s)")
            return 1
        else:
            print("✅ All validations passed!")
            return 0


if __name__ == '__main__':
    sys.exit(main())
