# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
Claude Code Security Firewall - Python/UV Implementation
=========================================================

Blocks dangerous commands before execution via PreToolUse hook.
Loads patterns from patterns.yaml for easy customization.

Exit codes:
  0 = Allow command (or JSON output with permissionDecision)
  2 = Block command (stderr fed back to Claude)

JSON output for ask patterns:
  {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "..."}}
"""

import json
import sys
import re
import os
import fnmatch
from pathlib import Path
from typing import Tuple, List, Dict, Any

import yaml


def is_glob_pattern(pattern: str) -> bool:
    """Check if pattern contains glob wildcards."""
    return '*' in pattern or '?' in pattern or '[' in pattern


def glob_to_regex(glob_pattern: str) -> str:
    """Convert a glob pattern to a regex pattern for matching in commands."""
    # Escape special regex chars except * and ?
    result = ""
    for char in glob_pattern:
        if char == '*':
            result += r'[^\s/]*'  # Match any chars except whitespace and path sep
        elif char == '?':
            result += r'[^\s/]'   # Match single char except whitespace and path sep
        elif char in r'\.^$+{}[]|()':
            result += '\\' + char
        else:
            result += char
    return result

# ============================================================================
# OPERATION PATTERNS - Edit these to customize what operations are blocked
# ============================================================================
# {path} will be replaced with the escaped path at runtime

# Operations blocked for READ-ONLY paths (all modifications)
WRITE_PATTERNS = [
    (r'>\s*{path}', "write"),
    (r'\btee\s+(?!.*-a).*{path}', "write"),
]

APPEND_PATTERNS = [
    (r'>>\s*{path}', "append"),
    (r'\btee\s+-a\s+.*{path}', "append"),
    (r'\btee\s+.*-a.*{path}', "append"),
]

EDIT_PATTERNS = [
    (r'\bsed\s+-i.*{path}', "edit"),
    (r'\bperl\s+-[^\s]*i.*{path}', "edit"),
    (r'\bawk\s+-i\s+inplace.*{path}', "edit"),
]

MOVE_COPY_PATTERNS = [
    (r'\bmv\s+.*\s+{path}', "move"),
    (r'\bcp\s+.*\s+{path}', "copy"),
]

DELETE_PATTERNS = [
    # `git rm` is a reversible git-index removal, not a filesystem delete —
    # exclude it (mirrors the docker/podman/git exclusion in patterns.yaml).
    (r'(?<!git\s)\brm\s+.*{path}', "delete"),
    (r'\bunlink\s+.*{path}', "delete"),
    (r'\brmdir\s+.*{path}', "delete"),
    (r'\bshred\s+.*{path}', "delete"),
]

PERMISSION_PATTERNS = [
    (r'\bchmod\s+.*{path}', "chmod"),
    (r'\bchown\s+.*{path}', "chown"),
    (r'\bchgrp\s+.*{path}', "chgrp"),
]

TRUNCATE_PATTERNS = [
    (r'\btruncate\s+.*{path}', "truncate"),
    (r':\s*>\s*{path}', "truncate"),
]

# Combined patterns for read-only paths (block ALL modifications)
# ---------------------------------------------------------------------------
# INTERPRETER WRITE PATTERNS
# ---------------------------------------------------------------------------
# Every other pattern keys on a SHELL verb (>, tee, sed -i, cp, mv, truncate).
# An interpreter uses none of them, so `python - <<'PY'` + pathlib.write_text()
# matched nothing and readOnlyPaths were writable from Bash while Edit/Write
# were correctly blocked.
#
# THE PATH MUST BE QUOTED AND BOUND TO THE WRITE. An earlier revision asserted
# 'an interpreter runs' AND 'a write verb appears' independently, then only
# required the path to occur somewhere in the command. That was wrong three ways:
#
#   * readOnlyPaths includes /usr/, /bin/, build/, .venv/, node_modules/, so
#     `/usr/bin/python3 -c "...write_text('a.txt')..."` was BLOCKED on /usr/,
#     and `source .venv/bin/activate && python -c "open('out.txt','w')"` on /bin/.
#   * reading a protected file and writing elsewhere was blocked, contradicting
#     the read-only contract -- the canonical regenerate-a-doc script.
#   * unanchored [\s\S]* re-scanned from every offset, x56 paths x2 forms, in a
#     BLOCKING PreToolUse hook: a 5 KB heredoc stalled every Bash call 22s.
#
# Requiring the path inside a quoted string fixes the first: /usr/ and .venv/
# appear as bare command fragments, a real target is always a literal. Binding
# it to the write operation fixes the second: `Path('P').read_text()` has a READ
# verb after the path. Dropping the lookaheads and the leading wildcard fixes
# the third -- re.search already scans, so these stay linear.
#
# RESIDUAL GAP, stated not papered over: indirection is still out of reach.
#   p = Path(x); p.write_text(...)      variable holds the path
#   for f in <paths>; do perl -i ... "$f"; done
# No regex over command text can expand those. Closing them needs
# interpretation, not pattern matching.

# Methods invoked ON a path object: Path('P').write_text(...)
_PATH_WRITE_METHODS = (
    r"(?:write_text|write_bytes|unlink|touch|mkdir|rename|replace|truncate|"
    r"chmod|rmdir|write|writelines|open)"
)
# Functions taking the path as an ARGUMENT: shutil.copy(src, 'P')
_WRITE_FUNCS = (
    r"(?:writeFileSync|appendFileSync|createWriteStream|"
    r"shutil\.(?:copy|copy2|copyfile|copytree|move|rmtree)|"
    r"os\.(?:remove|unlink|truncate|rename|replace|rmdir|removedirs|makedirs|mkdir)|"
    r"fs\.(?:writeFile|writeFileSync|appendFile|rm|rmSync|unlink|rename|truncate|mkdir))"
)
# PowerShell is invocable from the Bash tool on this Windows-primary fleet and
# uses -Path rather than call parens.
_PS_WRITE = r"(?:Set-Content|Out-File|Add-Content|Remove-Item|New-Item|Clear-Content)"

# A COMPLETE quoted string containing the protected path. Requiring the quotes
# is what keeps /usr/, /bin/, build/ and .venv/ from matching: those appear as
# bare command fragments, never as string literals.
_Q_OPEN = r"['\"][^'\"]*{path}[^'\"]*['\"]"

INTERPRETER_WRITE_PATTERNS = [
    # Path('P').write_text(...)  -- quoted path, write method applied to it
    (_Q_OPEN + r"\s*\)\s*\.\s*" + _PATH_WRITE_METHODS,
     "interpreter write"),
    # open('P', 'w'|'a'|'x')
    (_Q_OPEN + r"\s*,\s*['\"][wax]",
     "interpreter write"),
    # writeFileSync('P', ...) / shutil.copy(src, 'P') / os.remove('P')
    (_WRITE_FUNCS + r"\s*\([^)]{0,200}" + _Q_OPEN,
     "interpreter write"),
    # Set-Content -Path 'P'
    (_PS_WRITE + r"[^\n]{0,120}" + _Q_OPEN,
     "interpreter write"),
]

# noDeletePaths need the destructive subset — the earlier revision extended only
# READ_ONLY_BLOCKED, leaving `python -c "os.remove('CLAUDE.md')"` allowed.
_DELETE_METHODS = r"(?:unlink|rmdir|remove)"
_DELETE_FUNCS = (
    r"(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir|removedirs)|"
    r"fs\.(?:rm|rmSync|unlink|rmdir))"
)
INTERPRETER_DELETE_PATTERNS = [
    (_Q_OPEN + r"\s*\)\s*\.\s*" + _DELETE_METHODS, "interpreter delete"),
    (_DELETE_FUNCS + r"\s*\([^)]{0,200}" + _Q_OPEN, "interpreter delete"),
    (r"(?:Remove-Item|Clear-Content)[^\n]{0,120}" + _Q_OPEN, "interpreter delete"),
]

READ_ONLY_BLOCKED = (
    INTERPRETER_WRITE_PATTERNS +
    WRITE_PATTERNS +
    APPEND_PATTERNS +
    EDIT_PATTERNS +
    MOVE_COPY_PATTERNS +
    DELETE_PATTERNS +
    PERMISSION_PATTERNS +
    TRUNCATE_PATTERNS
)

# Patterns for no-delete paths (block ONLY delete operations)
# Includes the interpreter delete subset: the first revision extended only
# READ_ONLY_BLOCKED, so `python -c "os.remove('CLAUDE.md')"` stayed allowed
# against every noDeletePath (.git/, .github/, pmoves/services/, LICENSE).
NO_DELETE_BLOCKED = DELETE_PATTERNS + INTERPRETER_DELETE_PATTERNS

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

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
    """Load patterns from YAML config file. Fails closed on any error."""
    config_path = get_config_path()

    if not config_path.exists():
        print(f"SECURITY: Config not found at {config_path} — blocking all commands (fail-closed)", file=sys.stderr)
        sys.exit(2)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"SECURITY: Failed to parse {config_path}: {e} — blocking all commands (fail-closed)", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"SECURITY: Failed to read {config_path}: {e} — blocking all commands (fail-closed)", file=sys.stderr)
        sys.exit(2)

    if not isinstance(config, dict):
        print(f"SECURITY: Config at {config_path} is not a dict — blocking all commands (fail-closed)", file=sys.stderr)
        sys.exit(2)

    if "bashToolPatterns" not in config:
        print("SECURITY: Config missing 'bashToolPatterns' key — blocking all commands (fail-closed)", file=sys.stderr)
        sys.exit(2)

    return config


# ============================================================================
# PATH CHECKING
# ============================================================================

def _escape_path(path: str) -> str:
    """Escape a protected path, making a directory's trailing slash OPTIONAL.

    Configured directory paths end with "/" (".claude/context/", "pmoves/tools/")
    and re.escape() kept that slash mandatory. Omitting one character therefore
    walked straight past the guard: a recursive delete of "pmoves/tools/" was
    blocked, while the identical delete of "pmoves/tools" was ALLOWED. Same
    directory, same destruction, one character apart.

    This applied to EVERY pattern class -- delete, write, move, truncate, and the
    interpreter patterns alike -- because they all interpolate {path}. Fixing it
    here fixes all of them at once.

    The trailing group is (?:/|(?![A-Za-z0-9._-])) rather than a bare optional
    slash, which would also match "pmoves/toolsmith", and rather than \b, which
    once the separator is optional. Requiring either a separator or a word
    boundary keeps the match on a whole path component.
    """
    if path.endswith("/") and len(path) > 1:
        return re.escape(path[:-1]) + r"(?:/|(?![A-Za-z0-9._-]))"
    return re.escape(path)


def check_path_patterns(command: str, path: str, patterns: List[Tuple[str, str]], path_type: str) -> Tuple[bool, str]:
    """Check command against a list of patterns for a specific path.

    Supports both:
    - Literal paths: ~/.bashrc, /etc/hosts (prefix matching)
    - Glob patterns: *.lock, *.md, src/* (glob matching)
    """
    if is_glob_pattern(path):
        # Glob pattern - convert to regex for command matching
        glob_regex = glob_to_regex(path)
        for pattern_template, operation in patterns:
            # For glob patterns, we check if the operation + glob appears in command
            # e.g., "rm *.lock" should match DELETE_PATTERNS with *.lock
            try:
                # SUBSTITUTE into {path}; do not strip it and append.
                #
                # Stripping worked only because every SHELL template ends in {path},
                # so prefix+glob happened to reconstruct them. The INTERPRETER templates
                # carry {path} in the MIDDLE, and stripping collapsed the quote-binding
                # to a bare quoted-string match with the glob tacked on the end -- which
                # no longer ties the path to the write. Every readOnlyPath expressed as a
                # glob (12 of 57) was therefore unprotected against interpreter writes,
                # while literal paths were protected. Measured: an interpreter write to a
                # glob-matched read-only path was ALLOWED; the same form against a literal
                # read-only path was BLOCKED.
                #
                # Substitution reconstructs the shell templates identically (placeholder is
                # last, so you get prefix+glob) and fixes the interpreter ones.
                # glob_to_regex emits no anchors, so it is safe to embed mid-pattern.
                filled = pattern_template.replace('{path}', glob_regex)
                if filled and re.search(filled, command, re.IGNORECASE):
                    return True, f"Blocked: {operation} operation on {path_type} {path}"
            except re.error as e:
                print(f"WARNING: Invalid regex for glob path pattern ({operation}, {path}): {e}", file=sys.stderr)
                continue
    else:
        # Original literal path matching (prefix-based)
        expanded = os.path.expanduser(path)
        escaped_expanded = _escape_path(expanded)
        escaped_original = _escape_path(path)

        for pattern_template, operation in patterns:
            # Check both expanded path (/Users/x/.ssh/) and original tilde form (~/.ssh/)
            pattern_expanded = pattern_template.replace("{path}", escaped_expanded)
            pattern_original = pattern_template.replace("{path}", escaped_original)
            try:
                if re.search(pattern_expanded, command) or re.search(pattern_original, command):
                    return True, f"Blocked: {operation} operation on {path_type} {path}"
            except re.error as e:
                print(f"WARNING: Invalid regex for literal path pattern ({operation}, {path}): {e}", file=sys.stderr)
                continue

    return False, ""


def check_command(command: str, config: Dict[str, Any]) -> Tuple[bool, bool, str]:
    """Check if command should be blocked or requires confirmation.

    Returns: (blocked, ask, reason)
      - blocked=True, ask=False: Block the command
      - blocked=False, ask=True: Show confirmation dialog
      - blocked=False, ask=False: Allow the command
    """
    patterns = config.get("bashToolPatterns", [])
    zero_access_paths = config.get("zeroAccessPaths", [])
    read_only_paths = config.get("readOnlyPaths", [])
    no_delete_paths = config.get("noDeletePaths", [])

    # 1. Check against patterns from YAML (may block or ask)
    for item in patterns:
        pattern = item.get("pattern", "")
        reason = item.get("reason", "Blocked by pattern")
        should_ask = item.get("ask", False)

        try:
            if re.search(pattern, command, re.IGNORECASE):
                if should_ask:
                    return False, True, reason  # Ask for confirmation
                else:
                    return True, False, f"Blocked: {reason}"  # Block
        except re.error as e:
            print(f"WARNING: Invalid regex in bashToolPatterns: {pattern!r} — {e}", file=sys.stderr)
            continue

    # CHIT bypass: CHIT tool commands can access env files they need to encode/rotate.
    # Destructive patterns (rm, DROP, git push --force) still apply — checked above.
    chit_bypass = config.get("chitBypassPatterns", [])
    is_chit_op = False
    for pat in chit_bypass:
        if pat:
            try:
                if re.search(pat, command, re.IGNORECASE):
                    is_chit_op = True
                    break
            except re.error as e:
                print(f"WARNING: Invalid regex in chitBypassPatterns: {pat!r} — {e}", file=sys.stderr)
                continue
    if is_chit_op:
        return False, False, ""

    # Template suffixes that should trigger ask instead of block
    template_suffixes = (".example", ".sample", ".template", ".defaults")

    # 2. Check for ANY access to zero-access paths (including reads)
    #
    # Token-boundary rule: for file/identifier patterns (no trailing '/'),
    # append (?!\w) so ".env" does not substring-match inside "os.environ".
    # For directory-prefix patterns (ending with '/'), the '/' is itself a
    # boundary — the match is meant to fire on ANY file inside the directory
    # (e.g., "~/.ssh/id_rsa"), so we must NOT append (?!\w) there.
    for zero_path in zero_access_paths:
        is_dir_prefix = zero_path.endswith('/')
        token_boundary = '' if is_dir_prefix else r'(?!\w)'
        if is_glob_pattern(zero_path):
            # Convert glob to regex for command matching.
            glob_regex = glob_to_regex(zero_path) + token_boundary
            try:
                if re.search(glob_regex, command, re.IGNORECASE):
                    # Check if command targets a template file
                    if any(suffix in command.lower() for suffix in template_suffixes):
                        return False, True, (
                            f"ENV TEMPLATE: Command matches zero-access pattern {zero_path} but targets a template file. "
                            f"In production, env files populate from the secrets pipeline (make -C pmoves secrets-funnel). "
                            f"Template files should update from source. "
                            f"Approve only if intentionally modifying templates (e.g., security remediation)."
                        )
                    return True, False, f"Blocked: zero-access pattern {zero_path} (no operations allowed)"
            except re.error as e:
                print(f"WARNING: Invalid regex for zero-access glob {zero_path}: {e}", file=sys.stderr)
                continue
        else:
            # Original literal path matching
            expanded = os.path.expanduser(zero_path)
            escaped_expanded = re.escape(expanded)
            escaped_original = re.escape(zero_path)

            # Check both expanded path (/Users/x/.ssh/) and original tilde form (~/.ssh/).
            # For non-directory literals (e.g. ".env"), append (?!\w) so the literal
            # cannot substring-match inside a longer identifier like "os.environ".
            # Directory prefixes (ending with '/') intentionally skip the boundary —
            # they match anything in the directory, including word-char filenames.
            bounded_expanded = escaped_expanded + token_boundary
            bounded_original = escaped_original + token_boundary
            if re.search(bounded_expanded, command) or re.search(bounded_original, command):
                # Check if command targets a template file
                if any(suffix in command.lower() for suffix in template_suffixes):
                    return False, True, (
                        f"ENV TEMPLATE: Command matches zero-access path {zero_path} but targets a template file. "
                        f"In production, env files populate from the secrets pipeline (make -C pmoves secrets-funnel). "
                        f"Template files should update from source. "
                        f"Approve only if intentionally modifying templates (e.g., security remediation)."
                    )
                return True, False, f"Blocked: zero-access path {zero_path} (no operations allowed)"

    # 2b. Bash delete allowlist — explicit, whole-command-anchored exceptions to the
    # read-only / no-delete blocks below (e.g. clearing git's own orphaned lockfiles).
    # Deliberately placed AFTER the destructive-pattern block (step 1: rm -rf / rm -f
    # are already blocked) and AFTER zero-access (step 2, never bypassed), so an
    # allowlisted command cannot smuggle anything dangerous past those gates. Each
    # pattern is anchored to the whole command in patterns.yaml, so no chaining.
    for item in config.get("bashDeleteAllowlist", []):
        pat = item.get("pattern", "")
        if not pat:
            continue
        try:
            if re.search(pat, command):
                return False, False, ""  # explicitly allowed (see patterns.yaml: reason)
        except re.error as e:
            print(f"WARNING: Invalid regex in bashDeleteAllowlist: {pat!r} — {e}", file=sys.stderr)
            continue

    # 3. Check for modifications to read-only paths (reads allowed)
    for readonly in read_only_paths:
        blocked, reason = check_path_patterns(command, readonly, READ_ONLY_BLOCKED, "read-only path")
        if blocked:
            return True, False, reason

    # 4. Check for deletions on no-delete paths (read/write/edit allowed)
    for no_delete in no_delete_paths:
        blocked, reason = check_path_patterns(command, no_delete, NO_DELETE_BLOCKED, "no-delete path")
        if blocked:
            return True, False, reason

    return False, False, ""


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    config = load_config()

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only check Bash commands
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Check the command
    is_blocked, should_ask, reason = check_command(command, config)

    if is_blocked:
        print(f"SECURITY: {reason}", file=sys.stderr)
        print(f"Command: {command[:100]}{'...' if len(command) > 100 else ''}", file=sys.stderr)
        sys.exit(2)
    elif should_ask:
        # Output JSON to trigger confirmation dialog
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
