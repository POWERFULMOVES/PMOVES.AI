#!/usr/bin/env python3
"""
Deterministic Security Hooks for Agent Zero

Validates commands against patterns.yaml before execution.
Based on PMOVES-BoTZ security constitution.
"""

import re
import yaml
from pathlib import Path
from typing import Optional, Tuple

PATTERNS_PATH = Path(__file__).parent.parent / "patterns.yaml"


class DeterministicHook:
    """Pre-execution validation using regex patterns."""

    def __init__(self, patterns_path: Path = PATTERNS_PATH):
        self.patterns_path = patterns_path
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict:
        """Load security patterns from YAML."""
        if not self.patterns_path.exists():
            return {"blocked_commands": [], "protected_paths": {}}

        with open(self.patterns_path) as f:
            return yaml.safe_load(f)

    def check_command(self, command: str, file_path: str = None) -> Tuple[bool, str]:
        """
        Check if command is safe to execute.

        Returns:
            (allowed, reason) tuple
        """
        # Check blocked commands
        for rule in self.patterns.get("global_protection", {}).get("blocked_commands", []):
            pattern = rule["pattern"]
            flags = re.IGNORECASE if rule.get("case_insensitive", False) else 0

            if re.search(pattern, command, flags):
                return False, f"BLOCKED: {rule['reason']}"

        # Check protected paths
        if file_path:
            if self._is_protected(file_path, "zero_access"):
                return False, f"BLOCKED: Cannot access protected path: {file_path}"

        return True, "OK"

    def _is_protected(self, path: str, protection_level: str) -> bool:
        """Check if path has the given protection level."""
        protected = self.patterns.get("global_protection", {}).get("protected_paths", {}).get(protection_level, [])
        for pattern in protected:
            if Path(path).match(pattern):
                return True
        return False


def pre_command_check(command: str, file_path: str = None) -> bool:
    """
    Hook entry point for pre-execution validation.

    Raises:
        PermissionError: If command is blocked
    """
    hook = DeterministicHook()
    allowed, reason = hook.check_command(command, file_path)

    if not allowed:
        raise PermissionError(reason)

    return True


if __name__ == "__main__":
    # Test the hook
    import sys

    test_cases = [
        ("rm -rf /", None),
        ("git push --force", None),
        ("echo 'hello'", None),
        ("cat .env", ".env"),
        ("ls -la", None),
    ]

    hook = DeterministicHook()

    print("Testing DeterministicHook:")
    print("-" * 60)

    for cmd, path in test_cases:
        allowed, reason = hook.check_command(cmd, path)
        status = "✓ ALLOW" if allowed else "✗ BLOCK"
        print(f"{status}: {cmd}")
        if not allowed:
            print(f"  Reason: {reason}")
        print()

    sys.exit(0)
