"""Ratchet: the always-loaded Windows-host-quirks section must not drift back
into false claims.

THE DEFECT CLASS
----------------
``.claude/BOOTSTRAP.md`` is ALWAYS loaded -- every agent on every node reads it
before it reads anything else. A false claim in it is therefore not a stale
doc: it is a wrong instruction that every cold start acts on. This section
landed in 2026-09 and already carried four claims that `main` had moved past
by the time it was landed (a stale plugin version, a stale env-var name, a
verdict that was the wrong verdict for a field, and a file path that was the
wrong file).

THE RULE THIS RATCHET ENFORCES
-------------------------------
Every expectation here is DERIVED FROM THE LIVE SOURCE OF TRUTH, never from a
literal written next to the assertion:

  * the launcher paths the section names must exist ON DISK;
  * every repository directory must be covered by the path extractor, so a
    named path can never slip past the existence check;
  * the roster rows the section publishes must match the roster the gate
    actually reads (``.claude/mcp.json``), field by field and var by var;
  * the DROPPED / DEGRADED verdict the section publishes must be the verdict
    the LIVE gate produces -- derived by calling
    ``pmoves.tools.mcp_roster_normalize.normalize()`` with an empty
    environment, not by re-typing the rule;
  * the section's description of the gate must match what the gate DOES on
    each path -- a degraded header is KEPT, and only a normalizer failure
    is fail-closed;
  * every roster server that yields findings must be covered by the table
    or by the footnote that names the servers the table does not cover;
  * a rule the section cites must still be IN the file it cites it from;
  * the always-loaded file must stay within the character budget its
    sibling doc publishes -- read FROM that doc, so the two cannot drift;
  * the launchers the section calls hand-written must be exactly the launchers
    the LIVE generator marks ``managed="hand"``, and the default plan must
    exclude them while ``--include-hand`` must include them;
  * every generator flag the section names must be a REAL option of the
    generator's own argument parser.

A test that re-types the section's own expression would prove nothing. Each
check below asks the SOURCE whether the SECTION is still true.

Run it directly:

    python -m pytest pmoves/tests/tools/test_bootstrap_windows_host_quirks_ratchet.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It reads the
tree and calls the roster normalizer in-process.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]

# `pmoves.tools` is a package; `pmoves_launcher_generator` is a flat module in
# pmoves/tools/. Both import paths are needed.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))

import pmoves_launcher_generator as gen  # noqa: E402
from pmoves.tools import mcp_roster_normalize as roster_norm  # noqa: E402

BOOTSTRAP = REPO_ROOT / ".claude" / "BOOTSTRAP.md"
ROSTER = REPO_ROOT / ".claude" / "mcp.json"
CLAUDE_DOC = REPO_ROOT / ".claude" / "CLAUDE.md"
LAUNCHER = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh"

SECTION_HEADING = "## Windows host quirks (POWERFULMOVES / 5090)"

# The three fields the roster gate expands. A reference in `url` DROPs the
# server; one in `headers` or `env` DEGRADES it. The split is the LIVE
# normalizer's -- this list only says WHERE to look.
GATE_FIELDS = ("url", "headers", "env")

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# A `${...}` span. The roster has no NESTED default (${A:-${B}}), so a
# non-greedy body is enough -- and the normalizer records a malformed body
# (`${...}`) as a finding under its own literal text, which the `_IDENT`
# filter below discards because it is not a variable name.
_REF = re.compile(r"\$\{([^{}]*)\}")

# Repo-relative paths the section may name. Host paths (C:/..., ~/.claude/...)
# do not start with one of the top-level directories below and are therefore
# never matched.
#
# The lookbehind matters: a HOST path such as
# `~/.claude/plugins/cache/.../hooks.json` CONTAINS `.claude/`, and without
# the guard the extractor would read it as a repo path and demand a file
# that is not in this repository. A repo path is never preceded by `~` or `/`.
#
# THE PREFIX LIST IS DERIVED FROM THE TREE, NOT HAND-WRITTEN.
#
# It used to be the literal `(?:pmoves|deploy|\.claude|docs|scripts|website)`.
# Measured 2026-11-19 against this section: THREE of those SIX prefixes
# matched nothing at all (`docs` 0, `scripts` 0, `website` 0) -- decorative
# prefixes, which are promises the extractor does not keep, and a hardcoded
# list is exactly the "literal written next to the assertion" this file's
# own docstring forbids. The list is now read from the repository's own
# top-level directories, so every prefix is a REAL directory and a path
# under any of them is extracted, and then gated by the existence check.
_PATH_TAIL = r"[A-Za-z0-9_./\-]*(?:\{[A-Za-z0-9_, \t]+\})?"


@lru_cache(maxsize=1)
def _top_level_dirs() -> Tuple[str, ...]:
    """The repository's own top-level DIRECTORIES, from the tree.

    Longest first, so `pmoves_voice_router` is not shadowed by `pmoves`.
    Names with characters outside `[A-Za-z0-9_.-]` are skipped: they are
    prose, not paths, and a directory called "AI Agent Integration and Best
    Practices.md" is not something a section should be able to name.
    """
    proc = subprocess.run(
        ["git", "ls-tree", "-d", "--name-only", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, (
        "git ls-tree failed in " + str(REPO_ROOT) + ": " + proc.stderr.strip()
    )
    names = {
        line.strip()
        for line in proc.stdout.splitlines()
        if re.fullmatch(r"[A-Za-z0-9_.\-]+", line.strip())
    }
    assert names, "the repository has no top-level directories"
    return tuple(sorted(names, key=lambda n: (-len(n), n)))


@lru_cache(maxsize=1)
def _repo_path_pattern() -> "re.Pattern[str]":
    """The extractor: a repo path is a REAL top-level directory plus a tail."""
    alternation = "|".join(re.escape(name) for name in _top_level_dirs())
    return re.compile(r"(?<![~/])(?:" + alternation + r")/" + _PATH_TAIL)

# The published roster table. The header row is matched too, so a renamed
# table is a loud failure rather than a silently-empty parse.
_TABLE_HEADER = re.compile(
    r"^\|\s*server\s*\|\s*env var\s*\|\s*roster field\s*\|\s*verdict when unset\s*\|",
    re.IGNORECASE,
)

_TABLE_ROW = re.compile(
    r"^\|\s*`(?P<server>[A-Za-z0-9._-]+)`\s*\|\s*`(?P<var>[A-Za-z_][A-Za-z0-9_]*)`\s*"
    r"\|\s*`(?P<field>url|headers|env)`\s*\|\s*(?P<verdict>DROPPED|DEGRADED)\s*\|"
)


# ---------------------------------------------------------------------------
# The section under test
# ---------------------------------------------------------------------------
def _section_text() -> str:
    """The text of the Windows-host-quirks section, verbatim.

    A missing heading is a loud failure: the ratchet must not pass by
    reading an empty section.
    """
    lines = BOOTSTRAP.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == SECTION_HEADING:
            start = index
            break
    assert start is not None, (
        f"{SECTION_HEADING!r} is not in {BOOTSTRAP.relative_to(REPO_ROOT)}"
    )
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _expand_braces(path: str) -> List[str]:
    """`a/{x,y}.b` -> ['a/x.b', 'a/y.b'].

    Whitespace inside the braces is dropped: `{sh, ps1, cmd}` is the same
    path as `{sh,ps1,cmd}`, and the spacey spelling is valid in every shell
    an operator might type it into.
    """
    match = re.search(r"\{([^{}]*)\}", path)
    if not match:
        return [path]
    head, tail = path[: match.start()], path[match.end() :]
    out: List[str] = []
    for alternative in match.group(1).split(","):
        out.extend(_expand_braces(head + alternative.strip() + tail))
    return out


def _named_path_tokens(text: str | None = None) -> List[str]:
    """The raw path tokens the extractor matched, before brace expansion.

    Split out from :func:`_named_paths` so a caller can compare the section's
    paths against the extractor's own output token for token.
    """
    if text is None:
        text = _section_text()
    return sorted(set(_repo_path_pattern().findall(text)))


def _named_paths(text: str | None = None) -> List[str]:
    """Every repo-relative path the section names, brace-expanded.

    Directory references (trailing `/`) are skipped: the section names a
    scratch directory that only exists while a test is running.
    """
    found: Set[str] = set()
    for raw in _named_path_tokens(text):
        for expanded in _expand_braces(raw):
            if expanded.endswith("/"):
                continue
            found.add(expanded)
    return sorted(found)


def _git_ignored(paths: Iterable[str]) -> Set[str]:
    """The subset of *paths* the repository's ignore rules exclude.

    A path the repo does not track cannot be checked for existence (the live
    `pmoves/env.shared` is gitignored and absent from a fresh clone). A path
    the repo DOES track must exist.
    """
    candidates = list(paths)
    if not candidates:
        return set()
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input="\n".join(candidates) + "\n",
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# The roster the gate reads
# ---------------------------------------------------------------------------
def _roster() -> Dict[str, dict]:
    data = json.loads(ROSTER.read_text(encoding="utf-8"))
    return data.get("mcpServers") or {}


def _normalizer_requires(body: str) -> bool:
    """Does the LIVE normalizer treat `${body}` as a missing variable?

    Derived from the implementation, not from a reading of it: a body with a
    `:-` default renders its default and records nothing; a bare body records
    a miss.
    """
    missing: List[str] = []
    roster_norm.expand("${" + body + "}", {}, missing)
    return bool(missing)


def _reference_name(body: str) -> str:
    """The variable name a `${body}` refers to ("" when it is malformed)."""
    name = body.split(":-", 1)[0].strip() if ":-" in body else body.strip()
    return name if _IDENT.match(name) else ""


def _field_references(cfg: dict) -> Dict[str, Dict[str, bool]]:
    """{field: {var: is_required}} for one roster server.

    A variable is required if ANY occurrence of it in that field is a bare
    reference. `pmoves-nats-fleet` proves why the "any" matters: it carries
    the DEFAULTED form `${NATS_CREDS:-}` as the value, and the BARE form
    `${NATS_CREDS}` inside a sibling `_`-prefixed note. The default alone
    would not be a finding; the bare reference is.
    """
    out: Dict[str, Dict[str, bool]] = {field: {} for field in GATE_FIELDS}

    def record(field: str, value: str) -> None:
        for match in _REF.finditer(value):
            name = _reference_name(match.group(1))
            if not name:
                continue
            required = _normalizer_requires(match.group(1))
            out[field][name] = out[field].get(name, False) or required

    url = cfg.get("url")
    if isinstance(url, str):
        record("url", url)
    for field in ("headers", "env"):
        block = cfg.get(field)
        if isinstance(block, dict):
            for value in block.values():
                if isinstance(value, str):
                    record(field, value)
    return out


def _neutralise(text: str, keep: str) -> str:
    """Replace every reference whose name is not *keep* with a literal.

    This isolates one variable so the live gate's verdict for THAT variable
    can be observed, without the other variables' findings masking it.
    """
    def repl(match: "re.Match[str]") -> str:
        name = _reference_name(match.group(1))
        return match.group(0) if name == keep else "resolved"

    return _REF.sub(repl, text)


def _live_normalized(
    server: str, field: str, var: str
) -> Tuple[List[Tuple[str, List[str]]], List[Tuple[str, List[str]]], dict]:
    """(dropped, degraded, kept_config) from the LIVE roster gate.

    Only *var* is left unresolved; every other reference in the entry is
    replaced by a literal so it cannot mask *var*'s own verdict.
    """
    cfg = copy.deepcopy(_roster()[server])
    url = cfg.get("url")
    if isinstance(url, str):
        cfg["url"] = _neutralise(url, var)
    for block_field in ("headers", "env"):
        block = cfg.get(block_field)
        if isinstance(block, dict):
            for key, value in list(block.items()):
                if isinstance(value, str):
                    block[key] = _neutralise(value, var)
    payload = {"mcpServers": {server: cfg}}
    out, dropped, degraded = roster_norm.normalize(payload, str(REPO_ROOT), {}, None)
    kept = (out.get("mcpServers") or {}).get(server)
    return dropped, degraded, kept if isinstance(kept, dict) else {}


def _live_verdict(server: str, field: str, var: str) -> str:
    """What the LIVE roster gate does when *var* is unset for *server*.

    DROPPED, DEGRADED, or CLEAN -- derived by running the real normalizer
    over the real roster entry with an empty environment.
    """
    dropped, degraded, _kept = _live_normalized(server, field, var)
    if dropped:
        return "DROPPED"
    if degraded:
        return "DEGRADED"
    return "CLEAN"


def _roster_rows() -> List[Tuple[str, str, str, str]]:
    """The published roster table, as (server, var, field, verdict) tuples.

    A table row the parser cannot read is a FAILURE, not a skipped row --
    otherwise an edited row would silently stop being checked.
    """
    lines = _section_text().splitlines()
    header = None
    for index, line in enumerate(lines):
        if _TABLE_HEADER.match(line):
            header = index
            break
    assert header is not None, (
        "the section publishes no roster table "
        "(| server | env var | roster field | verdict when unset |)"
    )
    rows: List[Tuple[str, str, str, str]] = []
    for line in lines[header + 1 :]:
        if not line.strip().startswith("|"):
            break
        if set(line.strip()) <= set("|-: "):
            continue
        match = _TABLE_ROW.match(line)
        assert match is not None, (
            f"roster table row is not readable by the ratchet: {line!r}"
        )
        rows.append(
            (
                match.group("server"),
                match.group("var"),
                match.group("field"),
                match.group("verdict"),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# The gate table: what the roster gate ACTUALLY does on each path
# ---------------------------------------------------------------------------
_GATE_HEADER = re.compile(
    r"^\|\s*path\s*\|\s*an unset credential in\s*`headers`\s*or\s*`env`\s*\|"
    r"\s*the session starts\?\s*\|",
    re.IGNORECASE,
)

_GATE_ROW = re.compile(
    r"^\|\s*(?P<path>[^|]+?)\s*\|\s*(?P<effect>[^|]+?)\s*\|\s*(?P<starts>YES|NO)\s*\|"
)


def _gate_rows() -> List[Tuple[str, str, str]]:
    """The published gate table, as (path, effect, session_starts) tuples."""
    lines = _section_text().splitlines()
    header = None
    for index, line in enumerate(lines):
        if _GATE_HEADER.match(line):
            header = index
            break
    assert header is not None, (
        "the section publishes no gate table "
        "(| path | an unset credential in `headers` or `env` | the session starts? |)"
    )
    rows: List[Tuple[str, str, str]] = []
    for line in lines[header + 1 :]:
        if not line.strip().startswith("|"):
            break
        if set(line.strip()) <= set("|-: "):
            continue
        match = _GATE_ROW.match(line)
        assert match is not None, (
            f"gate table row is not readable by the ratchet: {line!r}"
        )
        rows.append(
            (match.group("path"), match.group("effect"), match.group("starts"))
        )
    assert rows, "the section's gate table has no rows"
    return rows


# ---------------------------------------------------------------------------
# The roster footnote: the servers the section says ALSO flag
# ---------------------------------------------------------------------------
_FOOTNOTE_ANCHOR = "The roster yields findings for more servers than these"
_FOOTNOTE_ROWCOUNT = re.compile(r"than these\s+(\d+)\s+rows")


def _footnote_line() -> str:
    """The line that names the roster servers the table does not cover."""
    for line in _section_text().splitlines():
        if line.lstrip().startswith("- ") and _FOOTNOTE_ANCHOR in line:
            return line
    raise AssertionError(
        "the section has no footnote naming the roster servers the table "
        "does not cover"
    )


def _footnote_servers() -> List[str]:
    """The roster servers the footnote names, in the order it names them."""
    return re.findall(r"`([A-Za-z0-9._\-]+)`", _footnote_line())


def _footnote_row_count() -> int:
    """The number of table rows the footnote claims it is a superset of."""
    match = _FOOTNOTE_ROWCOUNT.search(_footnote_line())
    assert match is not None, (
        "the footnote does not state how many table rows it is a superset of"
    )
    return int(match.group(1))


# ---------------------------------------------------------------------------
# The documented size budget, read FROM the sibling doc that states it
# ---------------------------------------------------------------------------
_BUDGET = re.compile(r"≤(\d+)(k?)\s*chars")


def _documented_budget() -> int:
    """The character budget `.claude/CLAUDE.md` states for BOOTSTRAP.md.

    Read from the doc rather than written next to the assertion, so the
    published number and the gate cannot drift apart.
    """
    doc = CLAUDE_DOC.read_text(encoding="utf-8")
    found = {
        int(digits) * (1000 if unit else 1) for digits, unit in _BUDGET.findall(doc)
    }
    assert found, (
        f"{CLAUDE_DOC.relative_to(REPO_ROOT)} states no character budget for "
        f"{BOOTSTRAP.relative_to(REPO_ROOT)}"
    )
    assert len(found) == 1, (
        f"{CLAUDE_DOC.relative_to(REPO_ROOT)} states more than one character "
        f"budget for {BOOTSTRAP.relative_to(REPO_ROOT)}: {sorted(found)}"
    )
    return found.pop()


# ---------------------------------------------------------------------------
# The launchers the section calls hand-written
# ---------------------------------------------------------------------------
# The brace set is matched with the SPACES tolerated: `{sh, ps1, cmd}` is the
# same path as `{sh,ps1,cmd}` and is what half the shells accept. A pattern
# that matched only one spelling extracted NOTHING from the other, and the
# comparison then failed with "the section forgot everything" -- a diagnosis
# that lies about the cause.
_LAUNCHER_SET = re.compile(r"([A-Za-z0-9\-]+)\.\{[ \t]*sh[ \t]*,[ \t]*ps1[ \t]*,[ \t]*cmd[ \t]*\}")


def _launcher_names(text: str | None = None) -> List[str]:
    """The launcher names the section calls hand-written, in sorted order."""
    if text is None:
        text = _section_text()
    return sorted(set(_LAUNCHER_SET.findall(text)))


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def test_every_repo_path_the_section_names_exists() -> None:
    """Every repo-relative path the section names must exist on disk.

    The stranded draft named a path that did not exist (`claude-pmoves.sh`
    under a directory that was not there) and, in the plugin subsection, named
    a FILE that is not where the plugin actually lives.
    """
    named = _named_paths()
    assert named, "the section names no repo-relative path at all"
    ignored = _git_ignored(named)
    missing = [
        path
        for path in named
        if path not in ignored and not (REPO_ROOT / path).exists()
    ]
    assert not missing, (
        "the section names paths that do not exist: "
        + ", ".join(missing)
        + " -- re-derive them against the tree before naming them"
    )


def test_the_roster_table_matches_the_live_roster_and_the_live_gate() -> None:
    """Each published row must be true of the LIVE roster and the LIVE gate.

    Three independent questions per row:
      1. does the roster read that variable at all?
      2. does it read it in the FIELD the section names?
      3. is the verdict the section publishes the verdict the gate produces?
    """
    rows = _roster_rows()
    assert rows, "the section publishes no roster table rows"
    roster = _roster()
    problems: List[str] = []
    for server, var, field, verdict in rows:
        if server not in roster:
            problems.append(
                f"{server}: not a server in {ROSTER.relative_to(REPO_ROOT)}"
            )
            continue
        references = _field_references(roster[server])
        read_in = {f for f in GATE_FIELDS if var in references[f]}
        if not read_in:
            problems.append(
                f"{server}/{var}: the roster does not read {var} in "
                f"{'/'.join(GATE_FIELDS)}"
            )
            continue
        if field not in read_in:
            problems.append(
                f"{server}/{var}: the roster reads it in {sorted(read_in)}, "
                f"not in {field}"
            )
            continue
        if not references[field][var]:
            problems.append(
                f"{server}/{var}: the {field} reference is DEFAULTED, so an "
                "unset value is not a finding and there is nothing to WARN about"
            )
            continue
        live = _live_verdict(server, field, var)
        if live != verdict:
            problems.append(
                f"{server}/{var}: the section says {verdict}, the live gate "
                f"says {live}"
            )
    assert not problems, "\n".join(problems)


def test_every_required_roster_var_of_every_roster_server_is_covered() -> None:
    """EVERY roster server that yields findings must be covered by the section.

    Coverage has exactly two shapes, and a server must have one of them:

      * it is a row (or rows) in the published table, and the table lists
        EVERY variable the roster requires of it -- the half-row failure
        this test was first written for: the roster gains a bare reference
        for a server the section already covers, the section keeps
        describing the old set, and the operator fixes the wrong variable;
      * it is named in the footnote's parenthetical list, which is where the
        section says "these others flag too".

    A server in NEITHER is a finding the operator is never told about. The
    old version of this test only swept the servers the TABLE names, so a
    bare `${CLOUDFLARE_ACCOUNT_ID}` added to the `cloudflare` entry -- one of
    the seven the footnote mentions -- landed outside the gate entirely.
    """
    rows = _roster_rows()
    roster = _roster()
    listed: Dict[str, Set[str]] = {}
    for server, var, _field, _verdict in rows:
        listed.setdefault(server, set()).add(var)
    footnote = set(_footnote_servers())
    problems: List[str] = []

    for server, named in sorted(listed.items()):
        if server not in roster:
            problems.append(
                f"{server}: not a server in {ROSTER.relative_to(REPO_ROOT)}"
            )
            continue
        required: Set[str] = set()
        for names in _field_references(roster[server]).values():
            required |= {name for name, is_required in names.items() if is_required}
        unlisted = required - named
        if unlisted:
            problems.append(
                f"{server}: the roster also requires {sorted(unlisted)}, "
                "which the table does not list"
            )

    # The FULL roster, not just the servers the table names.
    for server in sorted(roster):
        if server.startswith("_") or not isinstance(roster[server], dict):
            continue
        required: Set[str] = set()
        for names in _field_references(roster[server]).values():
            required |= {name for name, is_required in names.items() if is_required}
        if not required:
            continue
        if server in listed or server in footnote:
            continue
        problems.append(
            f"{server}: the roster requires {sorted(required)} and the "
            "section covers it in neither the table nor the footnote"
        )

    # The footnote must name only servers the roster actually has.
    for server in sorted(footnote):
        if server not in roster:
            problems.append(
                f"{server}: the footnote names it as a roster server, but it "
                f"is not in {ROSTER.relative_to(REPO_ROOT)}"
            )

    assert not problems, "\n".join(problems)


def test_the_footnote_states_how_many_rows_it_is_a_superset_of() -> None:
    """The footnote's row count must be the table's real row count.

    "more servers than these 9 rows" is a claim about the table, and a claim
    in an always-loaded doc is a claim somebody has to keep true.
    """
    stated = _footnote_row_count()
    actual = len(_roster_rows())
    assert stated == actual, (
        f"the footnote says it covers servers beyond {stated} table rows, but "
        f"the table has {actual}"
    )


def test_the_section_names_exactly_the_hand_written_launchers() -> None:
    """The launchers the section calls hand-written must be exactly the ones
    the LIVE generator marks `managed="hand"` -- in BOTH directions.

    Naming a generator-managed launcher as hand-written sends an operator to
    edit a file the next regen overwrites. Failing to name a hand-written one
    sends them to edit a file that was never generated.
    """
    tools = gen.load_cli_tools(REPO_ROOT)
    hand = sorted(tool.name for tool in tools if tool.managed == "hand")
    assert hand, "the generator marks no launcher as hand-managed"
    named = _launcher_names()
    assert named == hand, (
        "the section's hand-written launcher set does not match the "
        f"generator's: section={named} generator={hand}"
    )


def test_the_launcher_extraction_tolerates_both_brace_spellings() -> None:
    """`a.{sh,ps1,cmd}` and `a.{sh, ps1, cmd}` are the SAME path.

    The extractor used to match exactly one spelling, so the equally valid
    spacey form extracted NOTHING -- and the comparison then failed with
    "the section forgot everything", a diagnosis that lies about the cause.
    The failure was caught; the DIAGNOSIS was the defect.
    """
    tight = _launcher_names("`claude-pmoves.{sh,ps1,cmd}`")
    loose = _launcher_names("`claude-pmoves.{sh, ps1, cmd}`")
    assert tight == ["claude-pmoves"], (
        f"the tight brace spelling did not extract: {tight}"
    )
    assert loose == tight, (
        "the spacey brace spelling extracts differently from the tight one: "
        f"loose={loose} tight={tight} -- content drift, not prose punctuation, "
        "must be what trips the comparison"
    )


def test_the_default_plan_excludes_the_hand_written_launchers() -> None:
    """The generator's DEFAULT plan must not contain them; `--include-hand` must.

    This is the live half of the claim the section makes about the generator:
    the exclusion is a property of the generator, so it is checked against
    the generator, not against the section.
    """
    tools = gen.load_cli_tools(REPO_ROOT)
    hand = sorted(tool.name for tool in tools if tool.managed == "hand")
    default = {f.relpath for f in gen.build_plan(REPO_ROOT, include_hand=False).files}
    with_hand = {f.relpath for f in gen.build_plan(REPO_ROOT, include_hand=True).files}
    for name in hand:
        for extension in (".sh", ".ps1", ".cmd"):
            relpath = f"deploy/provision/{name}{extension}"
            assert relpath not in default, (
                f"{relpath} is in the generator's DEFAULT plan -- it is not "
                "hand-written after all"
            )
            assert relpath in with_hand, (
                f"{relpath} is not in the --include-hand plan -- the "
                "generator's hand-exclusion has changed shape"
            )


def test_every_generator_flag_the_section_names_is_a_real_flag() -> None:
    """Every `--flag` the section attributes to the generator must be a REAL
    option of the generator's own parser.

    Scoped to the lines that mention the generator, so a flag belonging to
    some other tool is not dragged into this check.
    """
    real = {
        option
        for action in gen._parser()._actions
        for option in action.option_strings
    }
    assert real, "the generator's parser exposes no options at all"
    generator_lines = [
        line for line in _section_text().splitlines() if "generator" in line
    ]
    named = set()
    for line in generator_lines:
        named |= set(re.findall(r"--[A-Za-z][A-Za-z0-9\-]*", line))
    unknown = sorted(named - real)
    assert not unknown, (
        "the section names generator flags that do not exist: "
        + ", ".join(unknown)
        + f" -- the generator's real options are {sorted(real)}"
    )


def test_every_repository_directory_is_covered_by_the_path_extractor() -> None:
    """The extractor's prefix list must be the repository's own directories.

    It used to be a hand-written literal,
    `(?:pmoves|deploy|\\.claude|docs|scripts|website)`, and MEASURED 2026-11-19
    against this section THREE of those SIX prefixes matched nothing at all
    (`docs` 0, `scripts` 0, `website` 0). A decorative prefix is a promise
    the extractor does not keep, and a hardcoded list is exactly the "literal
    written next to the assertion" this file's own docstring forbids.

    Deriving the list from the tree means every prefix is a REAL directory,
    so a path under any of them is extracted and then gated by the existence
    check -- an invented `website/whatever.txt` is caught rather than waved
    through.
    """
    dirs = _top_level_dirs()
    assert dirs, "the repository has no top-level directories"
    uncovered = [
        name
        for name in dirs
        if f"{name}/probe-file.txt" not in _named_path_tokens(
            f"{name}/probe-file.txt"
        )
    ]
    assert not uncovered, (
        "the path extractor does not cover these top-level directories: "
        + ", ".join(uncovered)
    )
    assert _named_path_tokens(), "the section names no repo-relative path at all"


def test_the_fail_closed_claim_matches_the_live_gate() -> None:
    """The section's gate table must say what the LIVE gate actually does.

    Two independent sources, both read from the tree:

      * the normalizer: an unset credential in `headers`/`env` leaves the
        server KEPT and DEGRADED, and the LITERAL `${...}` survives in the
        value -- so the placeholder reaches the wire and the session starts;
      * the launcher: the REFUSAL lives in the normalizer-FAILURE branch
        (its own comment says the block is reached only when the
        normalizer could not run), so the session is blocked only there.

    The section used to claim the gate "stops a literal `${...}` from
    leaking into an MCP header". That was FALSE in the ordinary
    missing-token case, and it is an always-loaded document: a false claim
    here is a wrong instruction every cold start acts on.
    """
    rows = _roster_rows()
    header_rows = [row for row in rows if row[2] == "headers"]
    assert header_rows, (
        "the table publishes no `headers` row, so there is no live case to "
        "derive the gate's behaviour from"
    )
    server, var, _field, _verdict = header_rows[0]

    dropped, degraded, kept = _live_normalized(server, "headers", var)

    # -- LIVE 1: the normalizer KEEPS the server, DEGRADES it, and leaves
    #    the literal placeholder in the header.
    assert not dropped, (
        f"{server}: the live normalizer DROPPED it for an unset {var}, so "
        "the section's DEGRADED-and-KEPT claim is not what the gate does"
    )
    assert any(var in names for _srv, names in degraded), (
        f"{server}: the live normalizer did not record {var} as a finding"
    )
    kept_headers = json.dumps((kept or {}).get("headers") or {})
    assert "${" + var + "}" in kept_headers, (
        f"{server}: the live normalizer did not leave the literal "
        f"${{{var}}} in the header it kept: {kept_headers}"
    )

    # -- LIVE 2: the launcher refuses only in the normalizer-FAILURE path.
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "PMOVES_ALLOW_RAW_ROSTER" in launcher, (
        f"{LAUNCHER.relative_to(REPO_ROOT)} no longer carries the "
        "PMOVES_ALLOW_RAW_ROSTER override"
    )
    assert "Refusing to start" in launcher, (
        f"{LAUNCHER.relative_to(REPO_ROOT)} no longer refuses to start a "
        "session whose credentials are placeholders"
    )

    # -- The section must agree with both.
    gate = _gate_rows()
    starts = [row for row in gate if row[2] == "YES"]
    blocked = [row for row in gate if row[2] == "NO"]
    assert len(starts) == 1 and len(blocked) == 1, (
        "the gate table must publish exactly one row where the session "
        f"starts and one where it does not: {gate}"
    )
    effect = starts[0][1].lower()
    assert "kept" in effect and "degraded" in effect, (
        "the row that says the session STARTS must describe a server that "
        "is KEPT and DEGRADED, which is what the live normalizer does: "
        f"{starts[0][1]!r}"
    )
    assert "literal" in effect, (
        "the row that says the session STARTS must say that the literal "
        f"`${{...}}` survives into the header: {starts[0][1]!r}"
    )
    assert "raw roster" in blocked[0][1].lower(), (
        "the row that says the session is BLOCKED must describe the raw "
        f"roster the launcher refuses: {blocked[0][1]!r}"
    )

    # -- And the retracted wording must not come back.
    section = _section_text()
    for phrase in ("stops a literal", "from leaking into an MCP header"):
        assert phrase not in section, (
            f"the section still claims the gate {phrase!r} -- the live gate "
            "is fail-OPEN on a degraded header"
        )


# The SUBJECT of the rule the section attributes to a cited YAML file: the
# capitalised word the line uses to name what the rule is about ("blocks
# real Tailscale IPs"). Derived from the section rather than written here,
# so a reword that no longer matches this shape fails LOUDLY instead of
# silently dropping the content check.
_RULE_SUBJECT = re.compile(r"\b([A-Z][A-Za-z\-]+)\s+IPs\b")
_CITED_COMMAND = re.compile(r"make -C [A-Za-z0-9_./\-]+ [A-Za-z0-9_\-]+")


def test_every_rule_the_section_cites_is_still_in_the_file_it_cites() -> None:
    """A citation must point at a rule that still EXISTS.

    The path-existence ratchet only proves the FILE is there. A file can be
    renamed, or the rule inside it deleted, and the always-loaded section
    would keep sending the operator to a justification the tree no longer
    has -- the exact rot this lane exists to eliminate, hiding behind a
    path-exists check.

    The section cites `.claude/hooks/damage-control/patterns.yaml` for the
    Tailscale-IP rule and for the `make -C pmoves fleet-status` remedy, so
    the file must still carry BOTH: the subject it names, and the command it
    attributes to it.
    """
    section = _section_text()
    cited: List[Tuple[str, str]] = []
    for line in section.splitlines():
        for path in _named_path_tokens(line):
            if path.endswith((".yaml", ".yml")):
                cited.append((path, line))
    assert cited, "the section cites no YAML file to check the content of"
    problems: List[str] = []
    for path, line in cited:
        target = REPO_ROOT / path
        assert target.is_file(), f"{path} does not exist"
        text = target.read_text(encoding="utf-8")
        commands = _CITED_COMMAND.findall(line)
        assert commands, (
            f"the section cites {path} but attributes no command to it, so "
            "the citation cannot be content-checked -- reword it so the rule "
            "it names is visible"
        )
        for command in commands:
            if command not in text:
                problems.append(
                    f"{path}: the section attributes {command!r} to it, but "
                    "the file no longer contains that command"
                )
        subjects = _RULE_SUBJECT.findall(line)
        assert subjects, (
            f"the section cites {path} but names no rule subject in the "
            "shape this check derives -- reword it so the rule it names is "
            "visible"
        )
        for subject in subjects:
            if subject not in text:
                problems.append(
                    f"{path}: the section says it blocks {subject} IPs, but "
                    f"the file no longer mentions {subject}"
                )
    assert not problems, "\n".join(problems)


def test_the_bootstrap_stays_within_its_documented_budget() -> None:
    """The always-loaded file must stay within the budget the sibling states.

    `.claude/CLAUDE.md` used to say "the flat foundation (≤5k chars)" while
    the file was 14,599 chars -- a contract that was 2.9x over and never
    gated, so the number was fiction. The budget is now READ from that doc,
    so the published number and the gate cannot drift apart, and the file
    cannot grow without a deliberate, published decision.
    """
    budget = _documented_budget()
    size = len(BOOTSTRAP.read_text(encoding="utf-8"))
    assert size <= budget, (
        f"{BOOTSTRAP.relative_to(REPO_ROOT)} is {size} chars, over the "
        f"{budget}-char budget {CLAUDE_DOC.relative_to(REPO_ROOT)} states -- "
        "cut the file or raise the published budget, deliberately"
    )
