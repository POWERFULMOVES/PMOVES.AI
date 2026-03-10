"""Shared fixtures and utilities for smoke tests.

Provides cross-platform alternatives to subprocess grep calls,
so smoke tests work on Windows, macOS, and Linux.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PMOVES_DIR = PROJECT_ROOT / "pmoves"


def grep_file(
    file_path: Path,
    pattern: str,
    *,
    fixed: bool = False,
) -> List[str]:
    """Return lines matching pattern in file (cross-platform grep replacement).

    Args:
        file_path: Path to the file to search.
        pattern: Regex pattern (or literal string if fixed=True).
        fixed: If True, match literal substring instead of regex.

    Returns:
        List of matching lines (stripped of trailing newline).
    """
    if not file_path.exists():
        return []
    content = file_path.read_text(errors="replace")
    if fixed:
        return [line for line in content.splitlines() if pattern in line]
    regex = re.compile(pattern)
    return [line for line in content.splitlines() if regex.search(line)]


def grep_count(file_path: Path, pattern: str, *, fixed: bool = False) -> int:
    """Count matching lines (replaces grep -c)."""
    return len(grep_file(file_path, pattern, fixed=fixed))


def grep_context(
    file_path: Path,
    pattern: str,
    *,
    before: int = 0,
    after: int = 0,
) -> str:
    """Return lines around matches with context (replaces grep -B/-A).

    Returns concatenated matching regions as a single string.
    """
    if not file_path.exists():
        return ""
    lines = file_path.read_text(errors="replace").splitlines()
    result_lines: list[str] = []
    seen: set[int] = set()
    regex = re.compile(pattern)

    for i, line in enumerate(lines):
        if regex.search(line):
            start = max(0, i - before)
            end = min(len(lines), i + after + 1)
            for j in range(start, end):
                if j not in seen:
                    result_lines.append(lines[j])
                    seen.add(j)

    return "\n".join(result_lines)


def grep_numbered(
    file_path: Path,
    pattern: str,
    *,
    fixed: bool = False,
) -> List[str]:
    """Return matching lines prefixed with line numbers (replaces grep -n).

    Format: '42:line content here'
    """
    if not file_path.exists():
        return []
    content = file_path.read_text(errors="replace")
    results = []
    if fixed:
        for i, line in enumerate(content.splitlines(), 1):
            if pattern in line:
                results.append(f"{i}:{line}")
    else:
        regex = re.compile(pattern)
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                results.append(f"{i}:{line}")
    return results
