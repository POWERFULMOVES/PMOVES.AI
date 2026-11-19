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
  * the roster rows the section publishes must match the roster the gate
    actually reads (``.claude/mcp.json``), field by field and var by var;
  * the DROPPED / DEGRADED verdict the section publishes must be the verdict
    the LIVE gate produces -- derived by calling
    ``pmoves.tools.mcp_roster_normalize.normalize()`` with an empty
    environment, not by re-typing the rule;
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
# do not start with one of these prefixes and are therefore never matched.
#
# The lookbehind matters: a HOST path such as
# `~/.claude/plugins/cache/.../hooks.json` CONTAINS `.claude/`, and without
# the guard the extractor would read it as a repo path and demand a file
# that is not in this repository. A repo path is never preceded by `~` or `/`.
_REPO_PATH = re.compile(
    r"(?<![~/])"
    r"(?:pmoves|deploy|\.claude|docs|scripts|website)/"
    r"[A-Za-z0-9_./\-]*(?:\{[A-Za-z0-9_,]+\})?"
)

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
    """`a/{x,y}.b` -> ['a/x.b', 'a/y.b']."""
    match = re.search(r"\{([^{}]*)\}", path)
    if not match:
        return [path]
    head, tail = path[: match.start()], path[match.end() :]
    out: List[str] = []
    for alternative in match.group(1).split(","):
        out.extend(_expand_braces(head + alternative + tail))
    return out


def _named_paths() -> List[str]:
    """Every repo-relative path the section names, brace-expanded.

    Directory references (trailing `/`) are skipped: the section names a
    scratch directory that only exists while a test is running.
    """
    found: Set[str] = set()
    for raw in _REPO_PATH.findall(_section_text()):
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


def _live_verdict(server: str, field: str, var: str) -> str:
    """What the LIVE roster gate does when *var* is unset for *server*.

    DROPPED, DEGRADED, or CLEAN -- derived by running the real normalizer
    over the real roster entry with an empty environment.
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
    _out, dropped, degraded = roster_norm.normalize(payload, str(REPO_ROOT), {}, None)
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


def test_every_required_roster_var_of_a_named_server_is_listed() -> None:
    """A server named in the table must have ALL its required vars listed.

    The failure this catches is the half-row: the roster gains a bare
    reference for a server the section already covers, and the section keeps
    describing the old set. The operator then fixes the wrong variable.
    """
    rows = _roster_rows()
    roster = _roster()
    listed: Dict[str, Set[str]] = {}
    for server, var, _field, _verdict in rows:
        listed.setdefault(server, set()).add(var)
    problems: List[str] = []
    for server, named in sorted(listed.items()):
        if server not in roster:
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
    assert not problems, "\n".join(problems)


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
    named = sorted(
        set(re.findall(r"([A-Za-z0-9\-]+)\.\{sh,ps1,cmd\}", _section_text()))
    )
    assert named == hand, (
        "the section's hand-written launcher set does not match the "
        f"generator's: section={named} generator={hand}"
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
