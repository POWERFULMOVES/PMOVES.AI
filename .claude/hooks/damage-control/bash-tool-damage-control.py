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

# Known Roads + proportionate path resolution live beside this script.
sys.path.insert(0, str(Path(__file__).parent))
import path_scope  # noqa: E402
from known_roads import (  # noqa: E402
    active_grant_verified,
    evaluate_known_road,
    known_road_hint,
    record_use,
    set_hook_input,
)


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


# ----------------------------------------------------------------------------
# PATH REGEX WITH DEPTH (gitignore-like), used BESIDE glob_to_regex, never
# instead of it.
# ----------------------------------------------------------------------------
# glob_to_regex maps `*` to `[^\s/]*`, and the verb-adjacent templates below
# (`>\s*{path}`, `>>\s*{path}`, `cp ... \s+{path}`) put the path IMMEDIATELY
# after the verb. Together that meant a protected name was matched only as the
# FIRST path component. Measured on origin/main 2026-09-23: none of the 17 glob
# readOnly entries matched `a/b/<name>`, `**/Dockerfile` reached exactly one
# level, and literal entries had the same shape -- `cp x <abs repo>/pmoves/
# contracts/schemas/z.schema.json` and `echo x > ./pmoves/services/s/config/a`
# exited 0, as did every prefixed write of the Known Road grant file.
#
# The semantics here are gitignore's, adapted to command text:
#   *   one path segment          **  any number of segments (incl. zero)
#   a pattern with no slash matches the BASENAME at any depth
#   a relative pattern with a slash matches at any depth too -- the guard cannot
#     know the command's working directory, and an absolute path into the repo
#     must match, so this mirrors path_scope.token_matches_entry
#   the match must END at a path boundary, so `Dockerfile` does not reach
#     `Dockerfile_notes.txt` and `*.lock` does not reach `x.lock.md`
#   an optional opening quote is accepted: `> "a/b/poetry.lock"` is the same write
#
# MONOTONIC BY CONSTRUCTION: check_path_patterns tries the ORIGINAL regex first
# and this one only in addition, so nothing the original matched stops matching.
# The end anchor therefore narrows only what THIS regex adds. That is also why
# the original's unanchored over-match (`Dockerfile` reaching `Dockerfilex` as a
# bare first component) is left alone: removing it would let through commands
# the guard refuses today, and that is a separate, adjudicated change.
_SEG_CHAR = r"[^\s/'\"<>|;&()`]"        # one character inside a path segment
_ANY_PATH_CHAR = r"[^\s'\"<>|;&()`]"    # one character of a path, `/` included
_PATH_END = r"(?=$|[/\s'\"<>|;&()`])"   # the match stops at a component boundary
_DIR_END = r"(?:/|(?=$|[\s'\"<>|;&()`]))"
_OPT_QUOTE = r"['\"]?"
_ANY_PREFIX = r"(?:" + _ANY_PATH_CHAR + r"*/)?"


def _is_anchored_entry(path: str) -> bool:
    return path.startswith("/") or path.startswith("~")


def _glob_body_regex(glob_pattern: str) -> str:
    """The body of a glob with gitignore segment semantics (no prefix, no end)."""
    out = ""
    i = 0
    n = len(glob_pattern)
    while i < n:
        ch = glob_pattern[i]
        if glob_pattern.startswith("**/", i):
            out += r"(?:" + _ANY_PATH_CHAR + r"*/)?"
            i += 3
            continue
        if glob_pattern.startswith("**", i):
            out += _ANY_PATH_CHAR + "*"
            i += 2
            continue
        if ch == "*":
            out += _SEG_CHAR + "*"
        elif ch == "?":
            out += _SEG_CHAR
        else:
            out += re.escape(ch)
        i += 1
    return out


def path_depth_regex(path: str) -> str:
    """Regex for `path` as a command TARGET at any depth -- see the block above.

    Only ever used as an ADDITIONAL alternative to the original matcher.
    """
    is_dir = path.endswith("/") and len(path) > 1
    core = path[:-1] if is_dir else path
    if is_glob_pattern(core):
        body = _glob_body_regex(core)
    else:
        body = re.escape(core)
    if _is_anchored_entry(path):
        prefix = ""
    elif core.startswith("**/"):
        prefix = ""                       # the body already reaches any depth
    else:
        prefix = _ANY_PREFIX
    return _OPT_QUOTE + prefix + body + (_DIR_END if is_dir else _PATH_END)


def _is_depth_adjacent(template: str) -> bool:
    """Does {path} follow something OTHER than an unbounded `.*` / `[^'"]*`?

    Those two already absorb a directory prefix, so the depth regex adds nothing
    there -- and inside the interpreter templates it would stack a second greedy
    path scan onto `[^'"]*`, which is the super-linear shape that once stalled
    every Bash call for 22 s (see INTERPRETER WRITE PATTERNS).
    """
    before = template.split("{path}", 1)[0]
    return not (before.endswith(".*") or before.endswith("[^'\\\"]*")
                or before.endswith("[^'\"]*"))


# ============================================================================
# OPERATION PATTERNS - Edit these to customize what operations are blocked
# ============================================================================
# {path} will be replaced with the escaped path at runtime
#
# ADJACENCY. A template whose {path} follows an unbounded `.*` already reaches
# any depth, because `.*` absorbs the directory prefix. A template whose {path}
# follows `\s*` / `\s+` / `=` does not, so check_path_patterns ALSO tries the
# depth regex (path_depth_regex) in those templates -- see _is_depth_adjacent.

# A `tee` append flag as a whole TOKEN: -a, -ai, -ia, --append. The first
# revision used the lookahead `(?!.*-a)`, which rejected the write template for
# any command containing the two bytes "-a" ANYWHERE after tee -- `x-api.json`,
# `road-active` -- and the append template then needed "-a" BEFORE the path, so
# `tee pmoves/contracts/schemas/x-api.schema.json` matched neither and exited 0.
_TEE_APPEND_FLAG = r"(?:-[A-Za-z]*a[A-Za-z]*|--append)(?=\s|$)"
# The arguments of ONE simple command: a separator ends them.
_ARGS = r"[^\n;&|]*"
# Command position for verbs whose name is also an ordinary word (install, ln).
_CMD_POS = r"(?:^|[\n;&|(`]\s*|\$\(\s*|\bsudo\s+|\bxargs\s+(?:-\S+\s+)*)"
# End of the simple command, so {path} is the LAST operand (the destination).
_LAST_OPERAND = r"\s*(?=$|[\n;&|)`])"

# Operations blocked for READ-ONLY paths (all modifications)
WRITE_PATTERNS = [
    (r'>\|?\s*{path}', "write"),
    (r'\btee\s+(?!(?:' + _ARGS + r'\s)?' + _TEE_APPEND_FLAG + r').*{path}', "write"),
    # touch creates or re-stamps every operand.
    (r'\btouch\s+(?:' + _ARGS + r'\s)?{path}', "touch"),
    # dd writes exactly the file named by of=.
    (r'\bdd\s+' + _ARGS + r'\bof={path}', "write"),
    # ln and install write their LAST operand; earlier operands are sources, and
    # a bare `ln -s /usr/bin/python3` (one operand) links INTO the cwd.
    # The flag star is POSSESSIVE (`*+`, Py3.11+): on a non-match the plain star
    # gave back one `-x ` token at a time and retried the whole {path} tail per
    # token -- `ln -s -s ...` x1500 measured 5.3s in a BLOCKING PreToolUse hook
    # (G5). Possessive refuses to give back; a true match never needed it to,
    # because a protected path is never itself a flag token.
    (_CMD_POS + r'ln\s+(?:-\S+\s+)*+\S+\s+(?:' + _ARGS + r'\s)?{path}' + _LAST_OPERAND, "link"),
    (_CMD_POS + r'install\s+(?:-\S+\s+)*+\S+\s+(?:' + _ARGS + r'\s)?{path}' + _LAST_OPERAND, "install"),
    # A write target computed by command substitution hides the real path from
    # the plain template: `echo x > "$(cat 'a/b/poetry.lock')"` writes wherever
    # that file says. Fail closed -- a substitution in the target position that
    # mentions a protected path blocks, resolvable or not. `[^;&|>]*` cannot
    # cross a separator, so a substitution in a LATER command (after ; & |) is
    # not smuggled in. Cost: the rare redirect-first form
    # `echo > notes.md "$(cat poetry.lock)"` blocks too; that is the fail-closed
    # direction this guard is built to err in.
    (r'>\|?\s*[^;&|>]*(?:\$\(|`)[^)`]*{path}', "write"),
]

APPEND_PATTERNS = [
    (r'>>\s*{path}', "append"),
    (r'\btee\s+(?:' + _ARGS + r'\s)?' + _TEE_APPEND_FLAG + r'.*{path}', "append"),
    # Substitution-hiding an append target -- see the matching write template.
    (r'>>\s*[^;&|>]*(?:\$\(|`)[^)`]*{path}', "append"),
]

EDIT_PATTERNS = [
    (r'\bsed\s+-i.*{path}', "edit"),
    # -i anywhere in the flags (`sed -E -i`, `sed --in-place`), not only first.
    (r'\bsed[ \t]+(?:[^\s;&|]+[ \t]+)*?(?:-[A-Za-z]*i[A-Za-z.]*|--in-place\S*)[ \t].*{path}', "edit"),
    (r'\bperl\s+-[^\s]*i.*{path}', "edit"),
    # lowercase letters only before the i, so `-Ilib` (include path) is not -i.
    (r'\bperl[ \t]+(?:-\S+[ \t]+)*?-[a-z]*i\S*[ \t].*{path}', "edit"),
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


def _legacy_entry_match(token: str, path: str) -> bool:
    """Does the patterns.yaml entry `path` match this single TOKEN under the
    ORIGINAL matching rules?

    The original rules ran over the WHOLE COMMAND, which is the defect. Running
    the same rules over one resolved token keeps every block whose target is a
    real path, while prose stops matching -- and prose is excluded structurally:
    a path token in these commands never contains whitespace, and a sentence
    always does. A quoted path that genuinely contains a space is still covered,
    by the component matcher in path_scope.

    Deliberately reuses is_glob_pattern / glob_to_regex / _escape_path rather than
    restating them, so this cannot drift from the matcher in force above. An
    uncompilable pattern returns True (undecidable -> keep the refusal).
    """
    if not token or any(ch.isspace() for ch in token):
        return False

    if is_glob_pattern(path):
        try:
            return re.search(glob_to_regex(path), token, re.IGNORECASE) is not None
        except re.error:
            return True

    for escaped in (_escape_path(os.path.expanduser(path)), _escape_path(path)):
        try:
            if re.search(escaped, token):
                return True
        except re.error:
            return True
    return False


def check_path_patterns(
    command: str,
    path: str,
    patterns: List[Tuple[str, str]],
    path_type: str,
    tokens=None,
    repo_scoped: Tuple[str, ...] = (),
) -> Tuple[bool, str]:
    """Check command against a list of patterns for a specific path.

    Supports both:
    - Literal paths: ~/.bashrc, /etc/hosts (prefix matching)
    - Glob patterns: *.lock, *.md, src/* (glob matching)

    PROPORTIONALITY: the regex above is CANDIDATE DETECTION only. Every template
    bridges the verb and the path with `.*`, so a sentence that merely NAMES a
    protected directory matched, and a bare directory entry matched that name
    anywhere on the host rather than inside this repository. Both refused real
    work (see path_scope.py for the two observed cases).

    A candidate is therefore confirmed against RESOLVED PATHS via
    path_scope.confirm(), which is monotonic -- it can only turn a block into an
    allow, never the reverse -- and fails CLOSED when the command cannot be
    lexed. `tokens` is computed once per command by the caller; passing None
    recomputes it here so the older 4-argument call sites keep working.
    """
    if tokens is None:
        tokens = path_scope.command_tokens(command)

    def _verdict(operation: str) -> Tuple[bool, str]:
        keep, _hits = path_scope.confirm(tokens, path, repo_scoped, _legacy_entry_match)
        if not keep:
            # The regex matched prose, or every resolved match for this
            # repo-scoped entry lies outside the repository. Entry inapplicable.
            return False, ""
        return True, f"Blocked: {operation} operation on {path_type} {path}"

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
                    return _verdict(operation)
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
                    return _verdict(operation)
            except re.error as e:
                print(f"WARNING: Invalid regex for literal path pattern ({operation}, {path}): {e}", file=sys.stderr)
                continue

    # Depth: in a verb-ADJACENT template the original regex matches the protected
    # name only as the first path component. Try the depth regex there too --
    # AFTER the original, and only in addition to it, so this can only add
    # matches. See path_depth_regex.
    depth_regex = path_depth_regex(path)
    depth_flags = re.IGNORECASE if is_glob_pattern(path) else 0
    for pattern_template, operation in patterns:
        if not _is_depth_adjacent(pattern_template):
            continue
        filled = pattern_template.replace("{path}", depth_regex)
        try:
            if re.search(filled, command, depth_flags):
                return _verdict(operation)
        except re.error as e:
            print(f"WARNING: Invalid depth regex ({operation}, {path}): {e}", file=sys.stderr)
            continue

    return False, ""


# The zero-access class is the one refusal with NO road, and saying so is the whole
# point of this string. The other three block classes each name an alternative now
# -- command-shape via `alternative:` / `cacheRoads`, read-only and no-delete via
# the Known Road hint -- so an agent that meets a bare "no operations allowed"
# cannot tell "no road exists" from "a road exists and I have not found it yet",
# and probes spellings until it gives up. That probing is the cost this change
# removes, and here it is removed by stating the absence outright.
#
# MESSAGE TEXT ONLY. Appended to a `return True, False, ...` whose verdict is
# already decided. Nothing here is consulted on the allow path, and nothing here
# can open anything -- least of all this class, which is precisely what it says.
#
# That no grant applies is a property of the code ORDER, not a policy note: both
# zero-access returns are reached before Known Roads is consulted at all.
_ZERO_ACCESS_NOTE = (
    " | THERE IS NO ROAD HERE, by design: this gate runs BEFORE Known Roads, so no "
    "KNOWN_ROAD grant can open this class -- do not spend turns looking for one. "
    "Sanctioned routes for the legitimate intents behind this shape: tier and "
    "environment files are GENERATED, so change the source and re-run "
    "`make -C pmoves secrets-funnel` instead of editing the file; to learn what a "
    "path is protected as WITHOUT tripping this gate, run "
    "`python3 .claude/skills/known-roads/roads.py check <path>`, or "
    "`... roads.py protected` for the whole class list. If the work genuinely needs "
    "the secret itself, escalate to the operator with the exact path and the reason "
    "-- that is the route, not a workaround."
)


def _cache_roads(command: str, config: Dict[str, Any]) -> str:
    """Vendor cache commands for any tool cache this command names.

    Returns "" when none apply. Message text only -- see _pattern_route().
    """
    hits = []
    for item in config.get("cacheRoads", []) or []:
        match = item.get("match", "")
        cmd = item.get("command", "")
        if match and cmd and match.lower() in command.lower():
            if cmd not in hits:
                hits.append(cmd)
    if not hits:
        return ""
    return " | CACHE ROADS for what this command names: " + "; ".join(hits)


def _pattern_route(item: Dict[str, Any], command: str, config: Dict[str, Any]) -> str:
    """The sanctioned alternative for a command-shape block, if one is declared.

    A guard that teaches only by refusal spends the fleet's discovery budget on its
    own configuration. The observed case: clearing regenerable tool caches with a
    recursive removal, on a host at 100 percent disk, was refused -- correctly --
    and named no alternative, so the route was discoverable only by guessing.

    MESSAGE TEXT ONLY. This runs AFTER a block has been decided and appends to the
    reason. It cannot allow anything, cannot change a verdict, and is never
    consulted on the allow path. Declared per-entry as `alternative:` in
    patterns.yaml so the route set is enumerable rather than folded into prose.
    """
    route = (item.get("alternative") or "").strip()
    suffix = _cache_roads(command, config)
    if route:
        return " | " + route + suffix
    return suffix


def _known_road_verdict(paths: List[str]) -> Tuple[bool, str, str]:
    """Evaluate Known Roads for the resolved paths a block matched.

    Returns (allowed, invalid_detail, hint):
      (True,  "",     "")     an active, provable grant covers one of these paths
                              -- recorded to known-roads.jsonl by known_roads.py
      (False, detail, "")     a path IS in the declared domain but the grant is
                              not provable -- refuse, surfacing `detail`
      (False, "",     hint)   no grant active; `hint` names the sanctioned road
                              when one exists for this path ("" when none does)

    This is the same mechanism the Edit and Write guards already consult. Before
    this, Bash blocked and then abandoned: it never named the road, so the
    protected set was discoverable only by tripping it. A road that the tool
    naming it cannot actually take is not guidance.

    It cannot open anything the destructive-pattern gate or the zero-access gate
    already refused: both run EARLIER in check_command and return before here.
    """
    hint = ""
    for absolute in paths:
        allowed, detail = evaluate_known_road("Bash", absolute, absolute)
        if allowed:
            return True, "", ""
        if detail:
            return False, detail, ""
        if not hint:
            hint = known_road_hint(absolute)
    return False, "", hint


_HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredoc_bodies(command: str) -> str:
    """`command` with the BODY of every heredoc removed, openers kept.

    Only the opaque-verb tripwire uses this. That tripwire has no path text to
    keep a match honest, so it must treat a newline as a command separator --
    and the moment it does, every line of a document being written through a
    heredoc becomes a command position. Writing a note that quotes one of these
    verbs would then prompt on its own prose. Same failure the proportionality
    work fixed for the {path} rules, arriving from the other direction.

    Deliberately NOT applied to any other check: those are all path-bound, and
    removing text can only remove matches. Here it cannot lose a real block --
    the tripwire is the last gate and only ever escalates allow to ask.

    KNOWN HOLE, stated rather than papered over: a heredoc whose body is FED TO A
    SHELL (`bash <<EOF ... EOF`) really does execute its contents, and this
    strips it, so an opaque verb in there is not seen. Distinguishing a heredoc
    that is a document from one that is a script needs to know what consumes it,
    which is interpretation, not lexing. The trade was made knowingly: without
    stripping, writing a note that merely quotes one of these verbs prompts on
    its own prose, every time, and a gate that cries wolf on documentation gets
    switched off. The executed case is covered where it is actually decidable --
    by effect, in effect_check.py.
    """
    out = []
    pos = 0
    while True:
        match = _HEREDOC_OPEN.search(command, pos)
        if not match:
            out.append(command[pos:])
            return "".join(out)
        newline = command.find("\n", match.end())
        if newline == -1:                       # opener with no body in view
            out.append(command[pos:])
            return "".join(out)
        out.append(command[pos:newline + 1])
        terminator = match.group(2)
        rest = command[newline + 1:]
        offset = None
        cursor = 0
        for line in rest.split("\n"):
            if line.strip() == terminator:
                offset = cursor + len(line)
                break
            cursor += len(line) + 1
        if offset is None:                      # unterminated: nothing follows
            return "".join(out)
        pos = newline + 1 + offset


# ----------------------------------------------------------------------------
# GRANT STATE: the files that AUTHORIZE this guard's own bypasses
# ----------------------------------------------------------------------------
# `.known-road-active` opens a readOnly domain; `.grant-state-cache.json` (PR
# #3174) decides whether a pr:/issue: grant is still LIVE, so a forged entry
# revives a dead grant. An agent that can write either can authorize itself,
# which defeats the half of the Known Roads model that says a HUMAN authorizes.
#
# Measured on origin/main 2026-09-23: the Bash guard refused only the bare file
# name. Every prefixed form -- `.claude/hooks/damage-control/<grant>`, `./`, an
# absolute path -- and `touch`, `tee`, `cp`, `ln`, `install`, `dd of=` exited 0.
# Both files are git-ignored, so the PostToolUse effect check cannot see a write
# to them either: PreToolUse is the only line, and it was open.
#
# WHY A NAME RULE AND NOT MORE VERB TEMPLATES. Every other rule here keys on a
# write verb and then looks for the path. For these two files the question is
# the reverse: is there ANY way this command writes them? A verb list answers
# that with "the verbs someone thought of" -- this repo has shipped that shape
# repeatedly. So the rule keys on the NAME, anywhere in the command, and the
# only exemption is a closed list of pure reads, whole-command anchored:
#
#   refused  any command that names either file (or a stem of one, so
#            `.known-road-$(echo active)` and `.known-road-act*` are caught),
#            whatever the verb, prefix, quoting or redirection
#   allowed  cat / head / tail / ls / stat / wc / file / test / [ / grep, on ONE
#            line, with no redirection, pipe, chaining, substitution or
#            expansion character anywhere in the command
#
# The read exemption only lets a command past THIS rule; every later rule still
# runs on it. A git-commit heredoc is masked first, as for every path rule, so a
# commit message may name these files.
#
# Runs FIRST in check_command, before the command-shape patterns: one of those
# returns `ask`, and an operator approving an unrelated prompt must not approve a
# self-grant riding in the same command. A pure block, so running it first can
# only refuse more.
#
# RESIDUAL, stated not papered over: a name assembled so that NO stem survives
# (quote-splitting inside every stem, variable concatenation, an interpreter
# building the string), a script file that is then executed, and an opaque verb
# writing the whole directory (rsync, tar -x) are not text-visible. The opaque
# verbs still `ask`; the rest needs interpretation, not matching.
_GRANT_STATE_NAME = re.compile(r"known-road-|road-active|grant-state-cache", re.IGNORECASE)
_GRANT_STATE_PURE_READ = re.compile(
    r"^[ \t]*(?:cat|head|tail|ls|stat|wc|file|test|\[|grep|egrep|fgrep)"
    r"(?:[ \t]+[^\s;&|<>`$(){}\\]+)*[ \t]*$"
)
_GRANT_STATE_NOTE = (
    "Blocked: this command names the Known Road grant file or the grant-state "
    "cache (.known-road" "-active / .grant-state" "-cache.json). Those files "
    "AUTHORIZE this guard's own bypasses, so no Bash command may write, create, "
    "copy, move, link, truncate or delete them, with any path prefix or verb. A "
    "text matcher cannot prove a command only reads, so the only exemption is a "
    "bare one-line read (cat/head/tail/ls/stat/wc/file/test/grep) with no "
    "redirection, pipe, chaining or expansion. NO KNOWN ROAD OPENS THIS: a grant "
    "cannot authorize writing the grant. To see the active grant: "
    "`python3 .claude/skills/known-roads/roads.py status`. To write prose that "
    "names these files, use the Write/Edit tool (they check the target path, not "
    "the content) or a quoted-heredoc `git commit -F -` message. The grant is "
    "operator-written, out of band."
)


def check_grant_state_files(command: str, path_scan: str) -> Tuple[bool, str]:
    """(blocked, reason) for any Bash command that names the grant state.

    `path_scan` is the command with git-commit heredoc bodies masked. Pure regex
    over text -- no lexing -- so a command that cannot be lexed (unbalanced
    quotes) is still refused rather than failing open.
    """
    if not _GRANT_STATE_NAME.search(path_scan):
        return False, ""
    if "\n" not in command and _GRANT_STATE_PURE_READ.match(command):
        return False, ""
    return True, _GRANT_STATE_NOTE


def check_opaque_write_verbs(
    command: str, config: Dict[str, Any]
) -> Tuple[bool, bool, str]:
    """Last gate: a verb that can write a path the command never spells.

    Runs AFTER every path rule and only on the fall-through, so it can turn an
    allow into an `ask` and nothing else. It cannot relax a single existing
    block -- every one of them has already returned by the time this is reached.

    A KNOWN ROAD GRANT DOES NOT COVER AN OPAQUE WRITE. It used to: a provable
    grant allowed and recorded, on the strength of `active_grant()` -- which
    says SOME grant is open, not that it covers what this command writes. So an
    agent's `tar -x` passed silently under an operator's unrelated `dockerfile:`
    grant (live trail row 2026-09-24T00:24:01Z, recorded as `<opaque-verb:tar
    extract>` -- a row that names no file and therefore proves nothing).

    Why not "allow when the grant's domain covers the targets"? Because the
    targets are exactly what this gate cannot know. A grant is a per-FILE domain
    predicate plus a provable reason (evaluate_known_road); with no file there is
    nothing to evaluate. Deriving targets would mean reading the diff or archive
    here, and that is time-of-check/time-of-use by construction: the same command
    can write the patch it then applies (`cat > x.patch <<EOF ... EOF; git apply
    x.patch`), so what PreToolUse reads is not what runs. The one opaque verb
    whose target IS named -- `dd of=` -- is now decided by the path rules, per
    file, before this gate is reached.

    So a grant changes only the MESSAGE: the operator who opened it is told it
    does not cover this, and asked -- the same verdict as with no grant. After
    an approval, the PostToolUse effect check still records every protected path
    that actually changed against the grant, per file, which is the honest
    record this gate could never produce.
    """
    stripped = strip_heredoc_bodies(command)
    for item in config.get("opaqueWriteVerbs", []) or []:
        pattern = item.get("pattern", "")
        if not pattern:
            continue
        try:
            if not re.search(pattern, stripped):
                continue
            unless = item.get("unless", "")
            if unless and re.search(unless, stripped):
                continue
        except re.error as e:
            print(f"WARNING: Invalid regex in opaqueWriteVerbs ({item.get('verb')}): {e}",
                  file=sys.stderr)
            continue

        verb = item.get("verb", "?")
        why = item.get("reason", "writes targets not named in the command")
        domain, reason, provable, void_detail, state, source = active_grant_verified()
        if provable:
            record_use(
                "Bash(opaque-verb)", f"<opaque-verb:{verb}>", domain, reason,
                note=f"{verb} — target not derivable from command text",
                grant_state=state, grant_source=source,
            )
            return False, False, ""
        # A grant that is present but void (merged PR, aged-out file, cannot be
        # verified) must SAY so here: otherwise the operator sees a generic
        # prompt and approves on the belief that their grant is still covering it.
        void_note = (f" A Known Road grant is present but NOT honoured: {void_detail}."
                     if void_detail else "")
        return False, True, (
            f"OPAQUE WRITE: `{verb}` {why}. The damage-control guard matches "
            "command TEXT, so it cannot tell whether this touches a protected "
            "path — no path rule applies to a target the command never names. "
            "Approve only if you know what it writes. Any protected path it does "
            "change will be reported afterwards by the PostToolUse effect check."
            + void_note
        )
    return False, False, ""


# A quoted heredoc feeding `git commit`: the delimiter quoting is what makes
# the body inert, and `git commit` is what makes it a message rather than code.
# Skip git's global flags (--no-pager, -c) before the subcommand.
#
# ONE branch, not an alternation. The first revision used
#     (?:-[^\s]+\s+|--[^\s]+(?:=[^\s]+)?\s+)*
# and CodeQL flagged it as exponential backtracking, correctly: BOTH branches
# match a token beginning "--", because `-[^\s]+` happily consumes "--foo". An
# ambiguous alternation under `*` lets a FAILING match split the same input two
# ways at every position -- 2^n paths. Reported triggers were repetitions of
# '--' and '!=\t--'.
#
# This matters more here than in ordinary code: the hook is PreToolUse, so it
# runs before EVERY Bash call. A pathological command line would hang the whole
# session, and this file already carries a 22s-stall regression from a different
# runaway pattern (see INTERPRETER WRITE PATTERNS above).
#
# A git flag token is just "-" followed by non-space, so the two branches were
# always the same shape. Collapsing them leaves exactly one way to match any
# token: `-`, then non-space up to the whitespace that ends it. No ambiguity, no
# backtracking. Deliberately a superset of the old pair (it also accepts a bare
# "-"), which is harmless in a prefix-skipper whose next obligation is `commit`.
_GIT_COMMIT_HEREDOC_START = re.compile(
    r"\bgit\s+(?:-\S*\s+)*commit\b[^\n]*?"
    r"<<(-?)\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2[^\n]*\n"
)


def _mask_git_commit_heredocs(command: str) -> str:
    """Blank the BODY of a QUOTED heredoc that feeds `git commit`.

    A commit message is not an operation. Writing

        git commit -F - <<'EOF'
        ... deliberately skipped pmoves/chit/secrets_manifest.yaml ...
        EOF

    tripped the zero-access scan, which -- unlike every other check here --
    matches a bare path ANYWHERE in the command text with no operation verb
    required. That breadth is correct for "no operations allowed" (it is what
    catches `cat`), but it means DESCRIBING a protected path is indistinguishable
    from touching one. The practical cost is perverse: it pushes commit messages
    toward vagueness exactly where precision matters most -- recording why a
    protected file was deliberately excluded.

    WHY THIS IS SAFE, AND WHERE THE LINE IS:
      * Only a QUOTED delimiter (<<'EOF' / <<"EOF") qualifies. With quoting the
        shell performs no $(...), backtick, or parameter expansion, so the body
        cannot execute -- it is literal bytes handed to git. An UNQUOTED <<EOF
        still expands and therefore keeps being scanned in full.
      * Only `git commit` qualifies. `python - <<'PY'` stays scanned, which is
        what INTERPRETER_WRITE_PATTERNS exist for -- masking heredocs generally
        would blow a hole straight through them.

    Masking preserves length and newlines, so every other pattern sees identical
    offsets and line structure; only message characters become spaces.

    RESIDUAL GAP, stated not papered over: `git commit -m "...path..."` is NOT
    covered. Quoting and escaping in an inline argument need a real shell parse,
    not a regex, and a wrong parse here fails open. Use a heredoc when a commit
    message must name a protected path.
    """
    out = command
    for m in _GIT_COMMIT_HEREDOC_START.finditer(command):
        dash, delim = m.group(1), m.group(3)
        body_start = m.end()
        # Match the shell exactly. `<<-EOF` strips leading tabs, so an indented
        # terminator ends it; plain `<<EOF` does NOT, so its terminator must sit
        # at column 0. Accepting indentation for both was wrong in the direction
        # of ending the mask EARLY -- a commit message that quotes a heredoc
        # example (indented EOF inside the prose) resumed scanning mid-message.
        # That failed closed rather than open, but it false-positived precisely
        # the case this function exists to serve.
        indent = r"[ \t]*" if dash else r""
        terminator = re.compile(
            r"^" + indent + re.escape(delim) + r"[ \t]*$", re.MULTILINE
        )
        t = terminator.search(out, body_start)
        body_end = t.start() if t else len(out)
        span = out[body_start:body_end]
        # Length-preserving: keeps offsets stable for the remaining finditer
        # matches, which were computed against the original string.
        masked = "".join("\n" if ch == "\n" else " " for ch in span)
        out = out[:body_start] + masked + out[body_end:]
    return out


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

    # A commit message is not an operation. Mask the body of a QUOTED heredoc that
    # feeds `git commit` before any path scan, so DESCRIBING a protected path does
    # not read as touching one. Placed after the destructive-pattern gate (step 1)
    # and before every path rule, so masking can only narrow what they see.
    path_scan = _mask_git_commit_heredocs(command)

    # 0. The grant state is unwritable from Bash in ANY form -- before every other
    # rule, including the `ask` shapes below. See check_grant_state_files.
    grant_blocked, grant_reason = check_grant_state_files(command, path_scan)
    if grant_blocked:
        return True, False, grant_reason

    # 1. Check against patterns from YAML (may block or ask)
    for item in patterns:
        pattern = item.get("pattern", "")
        reason = item.get("reason", "Blocked by pattern")
        should_ask = item.get("ask", False)

        try:
            if re.search(pattern, command, re.IGNORECASE):
                # The route is appended to BOTH outcomes: an `ask` prompt that names
                # the sanctioned path lets the operator pick it instead of approving
                # the refused shape.
                route = _pattern_route(item, command, config)
                if should_ask:
                    return False, True, reason + route  # Ask for confirmation
                else:
                    return True, False, f"Blocked: {reason}{route}"  # Block
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
                if re.search(glob_regex, path_scan, re.IGNORECASE):
                    # Check if command targets a template file
                    if any(suffix in path_scan.lower() for suffix in template_suffixes):
                        return False, True, (
                            f"ENV TEMPLATE: Command matches zero-access pattern {zero_path} but targets a template file. "
                            f"In production, env files populate from the secrets pipeline (make -C pmoves secrets-funnel). "
                            f"Template files should update from source. "
                            f"Approve only if intentionally modifying templates (e.g., security remediation)."
                        )
                    return True, False, (f"Blocked: zero-access pattern {zero_path} "
                                        f"(no operations allowed){_ZERO_ACCESS_NOTE}")
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
            if re.search(bounded_expanded, path_scan) or re.search(bounded_original, path_scan):
                # Check if command targets a template file
                if any(suffix in path_scan.lower() for suffix in template_suffixes):
                    return False, True, (
                        f"ENV TEMPLATE: Command matches zero-access path {zero_path} but targets a template file. "
                        f"In production, env files populate from the secrets pipeline (make -C pmoves secrets-funnel). "
                        f"Template files should update from source. "
                        f"Approve only if intentionally modifying templates (e.g., security remediation)."
                    )
                return True, False, (f"Blocked: zero-access path {zero_path} "
                                    f"(no operations allowed){_ZERO_ACCESS_NOTE}")

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

    # Resolve the command's path tokens ONCE. ~94 entries follow and the
    # confirmation stage below consults these for every candidate; lexing per
    # entry would re-scan the command 94 times inside a blocking PreToolUse hook.
    tokens = path_scope.command_tokens(command)
    repo_scoped = tuple(config.get("repoScopedPaths", []) or ())

    def _decide(entry: str, reason: str) -> Tuple[bool, bool, str]:
        """Attach the Known Road verdict to a confirmed path block."""
        _keep, hits = path_scope.confirm(tokens, entry, repo_scoped, _legacy_entry_match)
        allowed, detail, hint = _known_road_verdict(hits)
        if allowed:
            return False, False, ""
        if detail:
            return True, False, f"Blocked: {detail}"
        return True, False, reason + hint

    # 3. Check for modifications to read-only paths (reads allowed)
    for readonly in read_only_paths:
        blocked, reason = check_path_patterns(
            command, readonly, READ_ONLY_BLOCKED, "read-only path", tokens, repo_scoped)
        if blocked:
            return _decide(readonly, reason)

    # 4. Check for deletions on no-delete paths (read/write/edit allowed)
    for no_delete in no_delete_paths:
        blocked, reason = check_path_patterns(
            command, no_delete, NO_DELETE_BLOCKED, "no-delete path", tokens, repo_scoped)
        if blocked:
            return _decide(no_delete, reason)

    # 5. LAST: verbs that write paths they never spell. Placed after every path
    # rule on purpose -- it only ever sees commands the rules above allowed, so
    # it is provably incapable of relaxing one of them.
    return check_opaque_write_verbs(command, config)


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
    # Attribution (not authentication) for any Known Road row this call records.
    set_hook_input(input_data)

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
    # Exit 0 or 2 only -- an uncaught exception must never exit open. See fail_closed.py.
    from fail_closed import run_fail_closed  # noqa: E402
    run_fail_closed(main, "PreToolUse")
