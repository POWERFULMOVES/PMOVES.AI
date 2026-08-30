# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
Claude Code Edit Tool Damage Control
=====================================

Blocks edits to protected files via PreToolUse hook on Edit tool.
Loads zeroAccessPaths and readOnlyPaths from patterns.yaml.

Exit codes:
  0 = Allow edit
  2 = Block edit (stderr fed back to Claude)
"""

import json
import sys
import os
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import yaml

# Known Roads — contextualized, provable bypass for readOnlyPath domains.
sys.path.insert(0, str(Path(__file__).parent))
from known_roads import evaluate_known_road, known_road_hint  # noqa: E402


def is_glob_pattern(pattern: str) -> bool:
    """Check if pattern contains glob wildcards."""
    return '*' in pattern or '?' in pattern or '[' in pattern


def match_path(file_path: str, pattern: str) -> bool:
    """Match file path against pattern, supporting both prefix and glob matching.

    Handles Windows absolute paths vs relative patterns by resolving against
    CLAUDE_PROJECT_DIR and normalizing path separators.
    """
    # Resolve relative patterns against project dir for Windows absolute path matching
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir and not os.path.isabs(pattern) and not pattern.startswith("~"):
        abs_pattern = os.path.join(project_dir, pattern)
    else:
        abs_pattern = pattern

    expanded_pattern = os.path.expanduser(abs_pattern)
    normalized = os.path.normpath(file_path)
    expanded_normalized = os.path.expanduser(normalized)

    # Normalize separators for cross-platform comparison
    norm_fwd = expanded_normalized.replace("\\", "/").lower()
    pat_fwd = expanded_pattern.replace("\\", "/").lower()
    raw_pat_fwd = pattern.replace("\\", "/").lower()

    if is_glob_pattern(pattern):
        basename_lower = os.path.basename(expanded_normalized).lower()
        pattern_basename = os.path.basename(pattern).lower()

        # Match basename against filename portion (e.g., *.pem, .env*, docker-compose*.yml)
        if fnmatch.fnmatch(basename_lower, pattern_basename):
            # If pattern has a directory prefix, verify the directory matches too
            pattern_dir = os.path.dirname(raw_pat_fwd)
            if not pattern_dir or pattern_dir in norm_fwd:
                return True

        # Full path glob match (resolved against project dir)
        if fnmatch.fnmatch(norm_fwd, pat_fwd):
            return True
        return False
    else:
        # Prefix matching with normalized separators (resolved path)
        if norm_fwd.startswith(pat_fwd) or norm_fwd == pat_fwd.rstrip("/"):
            return True
        # Suffix matching for relative patterns (e.g., "pmoves/env.shared" in "/full/path/pmoves/env.shared")
        if not os.path.isabs(pattern) and not pattern.startswith("~") and raw_pat_fwd in norm_fwd:
            return True
        return False


def get_config_path() -> Path:
    """Get path to patterns.yaml, checking multiple locations."""
    # 1. Check project hooks directory (installed location)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        project_config = Path(project_dir) / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
        if project_config.exists():
            return project_config

    # 2. Check script's own directory (installed location)
    script_dir = Path(__file__).parent
    local_config = script_dir / "patterns.yaml"
    if local_config.exists():
        return local_config

    # 3. Check skill root directory (development location)
    skill_root = script_dir.parent.parent / "patterns.yaml"
    if skill_root.exists():
        return skill_root

    return local_config  # Default, even if it doesn't exist


def load_config() -> Dict[str, Any]:
    """Load config from YAML."""
    config_path = get_config_path()

    if not config_path.exists():
        return {"zeroAccessPaths": [], "readOnlyPaths": []}

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    return config


TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".defaults")


def _dir_prefix_match(normalized_fwd: str, pattern: str) -> bool:
    """True when `pattern` names a DIRECTORY prefix of the path.

    chitSafePaths carries directory entries written with a trailing separator.
    match_path handles file and glob patterns; this covers the directory form,
    anchored to a path boundary so "a/b/" cannot match "xa/b-c/".
    """
    pat = pattern.replace("\\", "/")
    if not pat.endswith("/"):
        return False
    return normalized_fwd.startswith(pat) or ("/" + pat) in ("/" + normalized_fwd)


def check_path(file_path: str, config: Dict[str, Any]) -> Tuple[bool, str, bool]:
    """Check if file_path is blocked. Returns (blocked, reason, is_template).

    ORDER MATTERS AND IS DELIBERATE: zero-access is decided FIRST.

    chitSafePaths used to run ahead of everything, so a safe-list entry could
    open a path the config declares zero-access. That was not theoretical: a
    chitSafePaths directory entry is a prefix of a zeroAccessPaths glob under
    the same tree, and every file the glob protects was editable through it.
    A safe-list may relax read-only; it must never reach a file the config says
    has no access at all.
    """
    normalized_fwd = os.path.normpath(file_path).replace("\\", "/")

    # 1. Zero-access wins over every bypass, including chitSafePaths.
    for zero_path in config.get("zeroAccessPaths", []):
        if match_path(file_path, zero_path):
            basename = os.path.basename(file_path).lower()
            if any(basename.endswith(suffix) for suffix in TEMPLATE_SUFFIXES):
                return True, f"zero-access path {zero_path}", True
            return True, f"zero-access path {zero_path} (no operations allowed)", False

    # 2. CHIT safe paths — CGP archives and CHIT data dirs bypass read-only.
    #    match_path, not a bare `in`: substring matching made every entry an
    #    unanchored wildcard, so a bare filename entry also matched that name
    #    with any suffix appended, and any path merely containing those bytes.
    for safe_pat in config.get("chitSafePaths", []):
        if match_path(file_path, safe_pat) or _dir_prefix_match(normalized_fwd, safe_pat):
            return False, "", False

    # Known Road — contextualized, provable bypass (see known_roads.py / PATTERNS.md).
    kr_allowed, kr_detail = evaluate_known_road("Edit", file_path, normalized_fwd)
    if kr_allowed:
        return False, "", False
    if kr_detail:
        # File is in a Known Road domain but the road is invalid — block with detail.
        return True, kr_detail, False

    # Check read-only paths (edits not allowed)
    for readonly in config.get("readOnlyPaths", []):
        if match_path(file_path, readonly):
            return True, f"read-only path {readonly}", False

    return False, "", False


def main() -> None:
    config = load_config()

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only check Edit tool
    if tool_name != "Edit":
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check if file is blocked
    blocked, reason, is_template = check_path(file_path, config)
    if blocked:
        if is_template:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        f"ENV TEMPLATE: This file matches {reason} but appears to be a template file. "
                        f"In production, env files populate from the secrets pipeline (make -C pmoves secrets-funnel). "
                        f"Template files should update from source. "
                        f"Approve this edit only if you are intentionally modifying the template (e.g., security remediation)."
                    )
                }
            }
            print(json.dumps(output))
            sys.exit(0)
        else:
            hint = "" if "Known Road" in reason else known_road_hint(
                os.path.normpath(file_path).replace("\\", "/"))
            print(f"SECURITY: Blocked edit to {reason}: {file_path}{hint}", file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
