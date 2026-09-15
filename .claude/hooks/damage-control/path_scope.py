"""Proportionate path resolution for the Bash damage-control guard.

WHY THIS EXISTS
---------------
Every pattern in bash-tool-damage-control.py matches COMMAND TEXT. A template
like `\\bch<verb>\\s+.*{path}` lets the verb and the protected name sit
arbitrarily far apart in the string, and a bare directory entry such as the
interpreter-environment dir matches that name ANYWHERE on the host -- not just
inside this repository. Two refusals of legitimate work were observed:

  1. a host-level interpreter environment rebuilt OUTSIDE the repo was refused
     because the command text contained a bare directory name that patterns.yaml
     lists without any repository scope;
  2. a claim-register note was refused because the note QUOTED the literal
     strings it was documenting -- the matcher reads text, not intent.

WHAT THIS MODULE DOES
---------------------
The regex stage stays exactly as it is and becomes CANDIDATE DETECTION. This
module supplies a confirmation stage that runs after it.

The confirmation stage is MONOTONIC: it can only turn a candidate block into an
allow, never the reverse. No command that the guard previously permitted can
become blocked by anything here. It drops a candidate in exactly two cases:

  1. NO token in the command resolves to a path that the entry covers -- the
     regex matched prose only;
  2. the entry is repo-scoped (patterns.yaml: repoScopedPaths) and the matching
     token resolves OUTSIDE this repository.

Everywhere else it FAILS CLOSED: if the command cannot be lexed, or a token
cannot be resolved, the candidate is kept and the guard still refuses.

HOW MATCHING WORKS
------------------
Entries and tokens are both split into path COMPONENTS and compared
component-wise with fnmatch. A sentence is a single component, so prose that
merely contains a protected name does not match. An absolute entry splits to a
leading empty component, which anchors it to the start of the token -- so a
sentence mentioning a system directory does not match either.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shlex
from typing import Callable, List, Optional, Sequence, Tuple

# Shell operators that shlex(punctuation_chars=True) emits as their own tokens.
_OPERATORS = {
    "&&", "||", "|", ";", ";;", "&", "(", ")", "{", "}",
    "<", "<<", "<<<", ">", ">>", ">|", "2>", "2>>", "!",
}

# Characters that separate a path from surrounding syntax inside one lexed token
# (--out=a/b, f(a/b), [a/b], a/b;c). Whitespace is deliberately NOT included:
# splitting on spaces would turn a prose sentence back into bare words and
# reintroduce the exact false positive this module removes.
_SUBSPLIT = re.compile(r"[=,()\[\]{};&|<>`$*?!\t'\"]+")

# Characters that mark a token as a CODE FRAGMENT rather than a path. Every one of
# them is in _SUBSPLIT, so whenever a token contains one, a cleaner sub-token
# covering the same text is guaranteed to be in the list too. That guarantee is
# what makes it safe to exclude fragments from the repo-scoping decision.
_CODE_CHARS = set("=,()[]{};&|<>`$*?!\t'\"")

# Bodies of quoted string literals. The interpreter-write patterns in the guard
# require the path inside quotes, and a lexed token for embedded code keeps the
# surrounding syntax attached, so quoted bodies are harvested separately.
#
# TWO INDEPENDENT SCANS, NOT ONE ALTERNATION. A single `'..'|".."` alternation
# let an outer double-quoted argument swallow the inner literal whole, so the
# real target inside `-c "io.open('P','w')"` never surfaced as a token and five
# interpreter-write blocks in the existing suite silently stopped firing. Each
# quote style is scanned over the same text independently, then one more level
# down, so a nested literal is reached from either direction.
_SINGLE_QUOTED = re.compile(r"'([^']*)'")
_DOUBLE_QUOTED = re.compile(r'"([^"]*)"')
_QUOTE_DEPTH = 2


def repo_root() -> str:
    """Absolute path of the repository this guard protects."""
    return os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _fwd(path: str) -> str:
    return path.replace("\\", "/")


def command_tokens(command: str) -> Optional[List[str]]:
    """Lex `command` into candidate path tokens.

    Returns None when the command cannot be lexed (unbalanced quotes, etc.).
    The caller MUST treat None as undecidable and keep the candidate block.
    """
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        # A '#' inside a command is not a comment for our purposes. Leaving the
        # default commenters set would silently DISCARD the rest of the command,
        # which would lose real targets -- a fail-open direction.
        lex.commenters = ""
        lexed = list(lex)
    except ValueError:
        return None

    out: List[str] = []

    def add(raw: str) -> None:
        raw = raw.strip()
        if not raw or raw in _OPERATORS:
            return
        out.append(raw)
        for piece in _SUBSPLIT.split(raw):
            if not piece or piece == raw:
                continue
            out.append(piece)
            # A piece lexed out of embedded code can keep its literal quotes
            # (posix shlex leaves single quotes intact inside a double-quoted
            # argument). Stripping them is block-preserving: it can only ADD a
            # candidate token, never remove one.
            bare = piece.strip("'\"")
            if bare and bare != piece:
                out.append(bare)

    for tok in lexed:
        add(tok.lstrip("<>"))

    for body in _quoted_bodies(command):
        add(body)

    return out


def _quoted_bodies(text: str) -> List[str]:
    """Bodies of quoted literals in `text`, descending _QUOTE_DEPTH levels."""
    found: List[str] = []
    frontier = [text]
    for _ in range(_QUOTE_DEPTH):
        nxt: List[str] = []
        for chunk in frontier:
            for body in _SINGLE_QUOTED.findall(chunk) + _DOUBLE_QUOTED.findall(chunk):
                if body:
                    found.append(body)
                    nxt.append(body)
        if not nxt:
            break
        frontier = nxt
    return found


def _components(path: str) -> List[str]:
    """Path components of `path`, lowercased, with '~' expanded and '.' dropped.

    The leading empty component of an absolute path is PRESERVED: it is what
    anchors an absolute entry to the start of a token.
    """
    expanded = _fwd(os.path.expanduser(path))
    parts = expanded.lower().split("/")
    # Drop '.' and interior empties from '//', but keep a leading '' (absolute).
    cleaned: List[str] = []
    for i, part in enumerate(parts):
        if i == 0 and part == "":
            cleaned.append("")
            continue
        if part in ("", "."):
            continue
        cleaned.append(part)
    return cleaned


def entry_components(entry: str) -> List[str]:
    """Components of a patterns.yaml entry. A tilde entry is expanded first, so
    it anchors like any other absolute entry."""
    return _components(entry)


def _window_match(tcomp: List[str], start: int, ecomp: Sequence[str]) -> bool:
    """Match entry components against token components from `start`.

    A '**' component matches ZERO OR MORE token components. Requiring it to match
    exactly one silently unblocked four operations on `./Dockerfile` against the
    entry `**/Dockerfile`: the token normalizes to a single component, the entry
    carried two, and the length check rejected it before any comparison ran. A
    differential sweep against the previous guard caught it; nothing in the
    hand-written suite did, because no case combined a '**' entry with a './'
    prefix. Zero-or-more is also what the glob means.
    """
    if not ecomp:
        return True
    if ecomp[0] == "**":
        rest = ecomp[1:]
        for skip in range(len(tcomp) - start + 1):
            if _window_match(tcomp, start + skip, rest):
                return True
        return False
    if start >= len(tcomp):
        return False
    if not fnmatch.fnmatch(tcomp[start], ecomp[0]):
        return False
    return _window_match(tcomp, start + 1, ecomp[1:])


def token_matches_entry(token: str, entry: str) -> bool:
    """True when `token` names a path that the protected `entry` covers.

    Component-wise fnmatch over a window that may start anywhere in the token, so
    a relative entry matches at any depth. An absolute entry's leading empty
    component can only match the token's own leading empty component, which
    anchors it to the start -- that is what keeps a sentence mentioning a system
    directory from matching.
    """
    tcomp = _components(token)
    ecomp = entry_components(entry)
    if not tcomp or not ecomp:
        return False
    return any(_window_match(tcomp, start, ecomp) for start in range(len(tcomp) + 1))


def resolve(token: str) -> Tuple[str, bool]:
    """(absolute normalized token, is_inside_repo).

    A relative token resolves against the repository root, which is the Bash
    tool's working directory. That is the conservative reading: a relative token
    stays in scope even if the command changed directory first.

    QUOTES ARE STRIPPED FIRST. A token lexed out of embedded code can keep its
    literal quotes, and a leading quote stops '~' from expanding -- so a host path
    like '~/.cache/go-build' resolved as a RELATIVE path, landed inside the repo,
    and defeated repo scoping. Measured: clearing that host cache was refused as
    "read-only path build/", naming a repo directory it never touched. Stripping
    can only yield the true path, so it cannot lose a block.
    """
    token = token.strip("'\"")
    expanded = os.path.expanduser(token)
    if os.path.isabs(expanded):
        absolute = os.path.normpath(expanded)
    else:
        absolute = os.path.normpath(os.path.join(repo_root(), expanded))
    absolute = _fwd(absolute)
    root = _fwd(repo_root()).rstrip("/")
    inside = absolute == root or absolute.startswith(root + "/")
    return absolute, inside


def confirm(
    tokens: Optional[Sequence[str]],
    entry: str,
    repo_scoped: Sequence[str],
    legacy_match: Optional[Callable[[str, str], bool]] = None,
) -> Tuple[bool, List[str]]:
    """Confirm a regex candidate against resolved paths.

    Returns (keep_block, matching_absolute_paths).

      keep_block=True   the command really does target a path the entry covers
                        (or the command could not be decided -- fail closed)
      keep_block=False  the regex matched prose only, or the entry is repo-scoped
                        and every matching token lies outside the repository

    `legacy_match(token, entry)` is the guard's ORIGINAL matcher, applied to one
    token instead of to the whole command. It is passed in rather than reproduced
    here so it cannot drift from the matcher actually in force. Its role is to
    make this stage provably monotonic: a token the original rules matched keeps
    its block even if the component matcher is stricter, so the ONLY blocks that
    can be dropped are the two sanctioned classes. It was not optional -- without
    it, four operations on './Dockerfile.z' stopped being refused, because the
    original glob regex was unanchored and matched a prefix of the filename while
    component matching correctly did not.
    """
    if tokens is None:
        # Undecidable: the command could not be lexed. Keep the refusal.
        return True, []

    is_repo_scoped = entry in set(repo_scoped)
    matched: List[str] = []
    saw_token_match = False
    saw_path_like = False

    for token in tokens:
        hit = token_matches_entry(token, entry)
        if not hit and legacy_match is not None:
            hit = legacy_match(token, entry)
        if not hit:
            continue
        saw_token_match = True

        # A CODE FRAGMENT must not decide repo scoping. A quoted argument such as
        # open('<host-cache-dir>/x' has no whitespace, so it reached here as a
        # "path"; it is not absolute, so it resolved against the repo root, landed
        # INSIDE the repo, and kept a block on a host cache directory the command
        # never touched -- reported against an unrelated repo build directory. Its
        # cleaner sub-token is guaranteed present (every _CODE_CHARS member is a
        # _SUBSPLIT separator), so skipping the fragment loses nothing; and if ONLY
        # fragments matched, we fail closed below.
        if _CODE_CHARS & set(token):
            continue
        saw_path_like = True

        absolute, inside = resolve(token)
        if is_repo_scoped and not inside:
            continue
        matched.append(absolute)

    if not saw_token_match:
        # Case 1: prose only -- no token in this command names such a path.
        return False, []
    if not saw_path_like:
        # Undecidable: every match was a code fragment. Keep the refusal.
        return True, []
    if not matched:
        # Case 2: repo-scoped entry, every match resolves outside the repository.
        return False, []
    return True, matched
