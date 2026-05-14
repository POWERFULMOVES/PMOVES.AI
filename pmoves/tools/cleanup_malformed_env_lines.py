#!/usr/bin/env python3
"""Remove malformed lines from env.shared that don't match KEY=VALUE format.

This script cleans up orphaned fragments (like base64 strings with = padding)
that break Docker Compose env file parsing. It only removes lines that:
1. Don't match the KEY=VALUE pattern
2. Don't start with # (comments)
3. Aren't blank lines

The validation is strict: keys must be UPPERCASE with only [A-Z0-9_] characters.
"""

from pathlib import Path
import sys

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

ENV_FILE = Path(__file__).resolve().parents[1] / "env.shared"


def is_valid_key_value_line(line: str) -> bool:
    """Check if a line matches valid KEY=VALUE format."""
    line = line.strip()

    # Skip blank lines and comments
    if not line or line.startswith("#"):
        return True  # These are valid, keep them

    # Must have = as separator
    if "=" not in line:
        return False  # Invalid, no = sign

    parts = line.split("=", 1)
    if len(parts) != 2:
        return False  # Invalid, malformed split

    key, _value = parts
    key = key.strip()

    # Key must be non-empty
    if not key:
        return False

    # Key format: uppercase alphanumeric, underscores, and colons allowed
    # (A0_SET_ namespace uses colons, _ is used for special env vars)
    # But reject base64 fragments that look like "abcd1234==" or contain +/
    if not key.isupper():
        return False

    # Allow alphanumeric, underscore, colon
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:")
    if not all(c in allowed_chars for c in key):
        return False

    # Reject if key looks like base64 (has + or /, or ends with == padding)
    # This catches lines like "t2+5bsdL/...==ABC=" that split incorrectly
    if any(c in key for c in '+/'):
        return False

    return True  # Valid KEY=VALUE line


def cleanup_env_file():
    """Remove malformed lines from env.shared."""

    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found")
        return 1

    # Read the file
    text = ENV_FILE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # Filter out malformed lines
    cleaned_lines = []
    removed_count = 0

    for i, line in enumerate(lines, 1):
        if is_valid_key_value_line(line):
            cleaned_lines.append(line)
        else:
            # Show what we're removing
            preview = line.strip()[:60]
            if len(preview) == 60:
                preview += "..."
            print(f"Removing line {i}: {preview}")
            removed_count += 1

    # Write back
    ENV_FILE.write_text("".join(cleaned_lines), encoding="utf-8")

    if removed_count > 0:
        print(f"\n[OK] Removed {removed_count} malformed line(s) from {ENV_FILE}")
        print("     These lines didn't match KEY=VALUE format and would break Docker Compose parsing")
    else:
        print("[OK] No malformed lines found - file is clean")

    return 0


if __name__ == "__main__":
    sys.exit(cleanup_env_file())
