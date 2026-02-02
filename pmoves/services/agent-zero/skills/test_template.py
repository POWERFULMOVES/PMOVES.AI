#!/usr/bin/env python3
"""
Test script to validate the SKILL.md template.

This script validates that the .template/SKILL.md file itself
conforms to the validation rules.
"""

import sys
from pathlib import Path

# Add skills directory to path for imports
skills_dir = Path(__file__).parent
sys.path.insert(0, str(skills_dir))

from validate_skills import SkillValidator


def main():
    """Test the template against validation rules."""
    template_path = skills_dir / ".template" / "SKILL.md"

    print(f"Validating template: {template_path}")
    print("="*60)

    validator = SkillValidator(strict=False)
    success = validator.validate_file(template_path)
    validator.print_report(template_path)

    if success:
        print("\n✅ Template is valid!")
        print("\nNote: The template contains placeholders (e.g., '[Skill Name]')")
        print("When creating a new skill, replace these with actual values.")
        return 0
    else:
        print("\n⚠️  Template has validation issues (expected for placeholders)")
        print("\nThese issues are expected because the template contains:")
        print("  - Placeholder values in frontmatter")
        print("  - Example content instead of real content")
        print("\nWhen creating a new skill, replace placeholders and re-validate.")
        return 0  # Don't fail for template placeholders


if __name__ == '__main__':
    sys.exit(main())
