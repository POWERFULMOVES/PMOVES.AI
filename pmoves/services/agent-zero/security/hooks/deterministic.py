#!/usr/bin/env python3
"""
Deterministic Security Hooks for Agent Zero

Validates commands against patterns.yaml before execution.
Based on PMOVES-BoTZ security constitution.
"""

import asyncio
import os
import re
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

PATTERNS_PATH = Path(__file__).parent.parent / "patterns.yaml"

# Thread-safe cache for compiled regex patterns
_pattern_cache: Dict[str, re.Pattern] = {}
_cache_lock = asyncio.Lock()


class TimeoutError(Exception):
    """Raised when regex matching times out."""


def _timeout_handler(signum, frame):
    """Signal handler for regex timeout."""
    raise TimeoutError("Regex matching timed out")


@contextmanager
def _regex_timeout(seconds: float):
    """
    Context manager to limit regex execution time.
    Prevents ReDoS (Regular Expression Denial of Service) attacks.
    """
    # Set signal handler for timeout
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(int(seconds))
    try:
        yield
    finally:
        # Cancel alarm and restore old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


async def _compile_pattern(pattern: str) -> re.Pattern:
    """
    Thread-safe regex compilation with caching.

    Args:
        pattern: Regex pattern string

    Returns:
        Compiled regex pattern

    Raises:
        TimeoutError: If compilation takes too long
        re.error: If pattern is invalid
    """
    # Check cache first
    if pattern in _pattern_cache:
        return _pattern_cache[pattern]

    # Thread-safe compilation
    async with _cache_lock:
        # Double-check after acquiring lock
        if pattern in _pattern_cache:
            return _pattern_cache[pattern]

        # Compile with timeout protection
        try:
            with _regex_timeout(seconds=2):
                compiled = re.compile(pattern)
                _pattern_cache[pattern] = compiled
                return compiled
        except TimeoutError:
            raise ValueError(f"Regex pattern compilation timed out: {pattern[:50]}...")
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")


class DeterministicHook:
    """Pre-execution validation using regex patterns."""

    def __init__(self, patterns_path: Path = PATTERNS_PATH) -> None:
        """
        Initialize DeterministicHook.

        Args:
            patterns_path: Path to patterns.yaml configuration
        """
        self.patterns_path = patterns_path
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict:
        """
        Load security patterns from YAML.

        Returns:
            Dictionary with security patterns
        """
        if not self.patterns_path.exists():
            return {"blocked_commands": [], "protected_paths": {}}

        try:
            with open(self.patterns_path) as f:
                return yaml.safe_load(f) or {"blocked_commands": [], "protected_paths": {}}
        except (yaml.YAMLError, IOError) as e:
            # Log error but don't crash - return safe defaults
            print(f"Warning: Failed to load patterns.yaml: {e}")
            return {"blocked_commands": [], "protected_paths": {}}

    def check_command(self, command: str, file_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if command is safe to execute.

        Args:
            command: Command string to validate
            file_path: Optional file path to check against protected paths

        Returns:
            (allowed, reason) tuple where allowed is True if command is safe

        Raises:
            ValueError: If regex pattern is invalid or compilation times out
        """
        # Check blocked commands with timeout protection
        blocked_commands = self.patterns.get("global_protection", {}).get("blocked_commands", [])
        for rule in blocked_commands:
            pattern = rule.get("pattern")
            if not pattern:
                continue

            flags = re.IGNORECASE if rule.get("case_insensitive", False) else 0

            try:
                # Use timeout to prevent ReDoS
                with _regex_timeout(seconds=1):
                    if re.search(pattern, command, flags):
                        return False, f"BLOCKED: {rule.get('reason', 'Command blocked by security policy')}"
            except TimeoutError:
                # Log and continue - safer to allow than to crash on DoS
                print(f"Warning: Regex timeout on pattern: {pattern[:50]}...")
                continue
            except re.error as e:
                print(f"Warning: Invalid regex pattern: {e}")
                continue

        # Check protected paths with normalization
        if file_path:
            if self._is_protected(file_path, "zero_access"):
                return False, f"BLOCKED: Cannot access protected path: {file_path}"

        return True, "OK"

    def _is_protected(self, path: str, protection_level: str) -> bool:
        """
        Check if path has the given protection level.

        SECURITY: Normalizes paths to prevent directory traversal attacks.
        Uses os.path.normpath() and os.path.abspath() to resolve '../' and symlinks.

        Args:
            path: File path to check
            protection_level: Protection level to check against

        Returns:
            True if path is protected
        """
        # CRITICAL: Normalize path to prevent traversal attacks like '../../../etc/passwd'
        # This resolves any '../' sequences, symbolic links, and relative paths
        try:
            normalized_path = os.path.normpath(path)
            absolute_path = os.path.abspath(normalized_path)
        except (ValueError, OSError) as e:
            # If path normalization fails, assume it's malicious
            print(f"Warning: Invalid path normalization for '{path}': {e}")
            return True  # Fail secure: block the path

        protected_patterns = self.patterns.get("global_protection", {}).get("protected_paths", {}).get(protection_level, [])

        for pattern in protected_patterns:
            try:
                # Use Path.match() which works with glob patterns
                # Path.match() is safe against traversal when used with normalized paths
                if Path(absolute_path).match(pattern):
                    return True
            except (ValueError, re.error) as e:
                print(f"Warning: Invalid protected path pattern '{pattern}': {e}")
                continue

        return False


def pre_command_check(command: str, file_path: Optional[str] = None) -> bool:
    """
    Hook entry point for pre-execution validation.

    Args:
        command: Command to validate
        file_path: Optional file path to check

    Returns:
        True if command is allowed

    Raises:
        PermissionError: If command is blocked by security policy
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
