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
from typing import List, Optional, Sequence, Tuple

# Shell operators that shlex(punctuation_chars=True) emits as their own tokens.
_OPERATORS = {
    "&&", "||", "|", ";", ";;", "&", "(", ")", "{", "}",
    "<", "<<", "<<<", ">", ">>", ">|", "2>", "2>>", "!",
}

# Characters that separate a path from surrounding syntax inside one lexed token
# (--out=a/b, f(a/b), [a/b], a/b;c). Whitespace is deliberately NOT included:
# splitting on spaces would turn a prose sentence back into bare words and
# reintroduce the exact false positive this module removes.
_SUBSPLIT = re.compile(r"[=,()\[\]{};&|<>`$*?!\t]+")

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


def token_matches_entry(token: str, entry: str) -> bool:
    """True when `token` names a path that the protected `entry` covers.

    Component-wise fnmatch over a contiguous window. Handles literal entries,
    basename globs, directory-prefix entries and multi-segment globs uniformly.
    """
    tcomp = _components(token)
    ecomp = entry_components(entry)
    if not tcomp or not ecomp:
        return False
    if len(ecomp) > len(tcomp):
        return False
    for start in range(len(tcomp) - len(ecomp) + 1):
        if all(
            fnmatch.fnmatch(tcomp[start + off], ecomp[off])
            for off in range(len(ecomp))
        ):
            return True
    return False


def resolve(token: str) -> Tuple[str, bool]:
    """(absolute normalized token, is_inside_repo).

    A relative token resolves against the repository root, which is the Bash
    tool's working directory. That is the conservative reading: a relative token
    stays in scope even if the command changed directory first.
    """
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
) -> Tuple[bool, List[str]]:
    """Confirm a regex candidate against resolved paths.

    Returns (keep_block, matching_absolute_paths).

      keep_block=True   the command really does target a path the entry covers
                        (or the command could not be decided -- fail closed)
      keep_block=False  the regex matched prose only, or the entry is repo-scoped
                        and every matching token lies outside the repository
    """
    if tokens is None:
        # Undecidable: the command could not be lexed. Keep the refusal.
        return True, []

    is_repo_scoped = entry in set(repo_scoped)
    matched: List[str] = []
    saw_token_match = False

    for token in tokens:
        if not token_matches_entry(token, entry):
            continue
        saw_token_match = True
        absolute, inside = resolve(token)
        if is_repo_scoped and not inside:
            continue
        matched.append(absolute)

    if not saw_token_match:
        # Case 1: prose only -- no token in this command names such a path.
        return False, []
    if not matched:
        # Case 2: repo-scoped entry, every match resolves outside the repository.
        return False, []
    return True, matched
