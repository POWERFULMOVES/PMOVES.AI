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
    active_grant,
    evaluate_known_road,
    known_road_hint,
    record_use,
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


def check_opaque_write_verbs(
    command: str, config: Dict[str, Any]
) -> Tuple[bool, bool, str]:
    """Last gate: a verb that can write a path the command never spells.

    Runs AFTER every path rule and only on the fall-through, so it can turn an
    allow into an `ask` and nothing else. It cannot relax a single existing
    block -- every one of them has already returned by the time this is reached.

    A provable Known Road grant allows and RECORDS. `active_grant()` asserts less
    than `evaluate_known_road()` -- it says a grant is open, not that it covers
    this file -- which is the honest reading here, because there is no file to
    check the domain predicate against. That weaker assertion is acceptable only
    because this gate never sees a NAMED protected path: any command that named
    one was decided above.
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
        domain, reason, provable = active_grant()
        if provable:
            record_use(
                "Bash(opaque-verb)", f"<opaque-verb:{verb}>", domain, reason,
                note=f"{verb} — target not derivable from command text",
            )
            return False, False, ""
        return False, True, (
            f"OPAQUE WRITE: `{verb}` {why}. The damage-control guard matches "
            "command TEXT, so it cannot tell whether this touches a protected "
            "path — no path rule applies to a target the command never names. "
            "Approve only if you know what it writes. Any protected path it does "
            "change will be reported afterwards by the PostToolUse effect check."
        )
    return False, False, ""


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
                if re.search(glob_regex, command, re.IGNORECASE):
                    # Check if command targets a template file
                    if any(suffix in command.lower() for suffix in template_suffixes):
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
            if re.search(bounded_expanded, command) or re.search(bounded_original, command):
                # Check if command targets a template file
                if any(suffix in command.lower() for suffix in template_suffixes):
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
