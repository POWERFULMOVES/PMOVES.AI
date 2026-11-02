#!/usr/bin/env python3
"""Hold ``MMX_CLI_SURFACE.md`` against the measured ``mmx`` CLI surface.

WHY THIS EXISTS
---------------
``pmoves/docs/services/MMX_CLI_SURFACE.md`` catalogued the ``mmx`` command
surface from memory and from an older npm build. It drifted: it promised
``mmx music generate`` (the installed build has no ``music`` resource at all),
``mmx speech list-voices`` and ``mmx speech clone`` (both renamed), and it
omitted ``mmx agent setup``, ``mmx text repl``, ``mmx config show`` and the
``video task get`` / ``video download`` pair.

A doc that names a command the binary does not have is a promise the sidecar
lane breaks at run time, on a device, with a half-written output file. So the
surface is now MEASURED (``pmoves/tools/mmx_surface_probe.py`` writes
``pmoves/configs/mmx_surface/cli_surface.json``) and this tool holds the doc
against that measurement.

HOW THE DOC IS READ
-------------------
The doc carries its machine-checkable surface in a fenced ``json`` block under
the ``## Machine-checkable surface`` heading. That block is the authoritative
surface; the prose table and the ASCII tree are for humans and are ALSO
scraped, so a tree that drifts away from the JSON block is still caught.

A table row is a COMMAND PATH, and it is reported the way it is written: when
the path the doc names is longer than the command the CLI has -- the CLI
renamed ``video task get`` to ``video task`` -- the dead over-claim is a
finding of its own. It is never quietly shortened into the live surface.

Scraping prose is never the primary check -- it is a second net, and the
primary net fails closed: a doc whose JSON block is missing or unparseable is
a ``PARSE_ERROR``, never a silent pass.

FINDINGS
--------
``DOCUMENTED_MISSING``  the doc claims a resource/command/flag the CLI lacks
``UNDOCUMENTED``        the CLI has a resource/command/flag the doc never mentions
``VERSION_DRIFT``       the doc's stated mmx version != the probed version
``PARSE_ERROR``         the doc could not be parsed -- fail closed, never "clean"
``INSTRUMENT_ERROR``    the snapshot (or the doc file) could not be read -- fail closed

FAIL CLOSED
-----------
Every input is mandatory. A missing snapshot file, a snapshot that is not
valid JSON, a snapshot entry whose command list is not a list of strings, an
unreadable doc -- each produces a finding and a non-zero exit. A gate that
cannot measure its input must not report success, and it must not report
success by omission either: an unreadable snapshot never degrades into "the
doc mentions nothing, so there is nothing to find".

Exit codes: 0 clean | 1 findings | 2 usage error.

Usage:
    python pmoves/tools/mmx_surface_parity.py --check
    python pmoves/tools/mmx_surface_parity.py --check --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOC = REPO_ROOT / "pmoves" / "docs" / "services" / "MMX_CLI_SURFACE.md"
DEFAULT_SNAPSHOT = REPO_ROOT / "pmoves" / "configs" / "mmx_surface" / "cli_surface.json"

#: The heading that introduces the doc's machine-checkable surface.
SURFACE_HEADING = "## Machine-checkable surface"

#: The heading above the human-readable command tree.
TREE_HEADING = "## Top-level command tree"

#: The heading above the human-readable global-flag list.
GLOBAL_FLAGS_HEADING = "## Global flags"

#: The header row that identifies the command table (and only that table).
COMMAND_TABLE_HEADER = ("Command", "Purpose", "Example")

#: A command word in this CLI is lowercase, optionally hyphenated.
COMMAND_WORD_RE = re.compile(r"^[a-z][a-z0-9-]*$")

#: A command path: one or more lowercase words.
COMMAND_PATH_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)*$")

#: The doc's npm version line: ``**npm name:** `mmx-cli` (v1.0.25)``.
NPM_VERSION_RE = re.compile(r"npm name[^\n]*?\(v?(\d+\.\d+\.\d+)\)")

FINDING_KINDS = (
    "DOCUMENTED_MISSING",
    "UNDOCUMENTED",
    "VERSION_DRIFT",
    "PARSE_ERROR",
    "INSTRUMENT_ERROR",
)


class SnapshotError(RuntimeError):
    """The instrument could not read or understand the snapshot."""


class DocParseError(RuntimeError):
    """The doc's machine-checkable surface could not be parsed."""


def _finding(kind: str, detail: str, **fields) -> dict:
    """Build one finding record."""
    record = {"kind": kind, "detail": detail}
    record.update(fields)
    return record


def load_snapshot(path: Path) -> dict:
    """Read and validate the committed snapshot.

    Fails closed at FILE granularity (missing/unreadable/unparseable file) and
    at ENTRY granularity (a resource whose command list is not a list of
    command names, a missing top-level key).
    """
    if not path.is_file():
        raise SnapshotError(f"the snapshot file {path} does not exist")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SnapshotError(f"the snapshot file {path} could not be read: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"the snapshot file {path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SnapshotError(f"the snapshot file {path} is not a JSON object")

    for key in ("mmx_version", "resources", "global_flags"):
        if key not in data:
            raise SnapshotError(f"the snapshot file {path} has no {key!r} key")

    version = data["mmx_version"]
    if not isinstance(version, str) or not version.strip():
        raise SnapshotError(
            f"the snapshot file {path} has a non-string 'mmx_version' entry"
        )

    resources = data["resources"]
    if not isinstance(resources, dict):
        raise SnapshotError(
            f"the snapshot file {path} has a 'resources' entry that is not an object"
        )
    for name, commands in resources.items():
        if not isinstance(name, str) or not name:
            raise SnapshotError(
                f"the snapshot file {path} has a non-string resource name: {name!r}"
            )
        if not isinstance(commands, list) or any(
            not isinstance(command, str) or not command for command in commands
        ):
            raise SnapshotError(
                f"the snapshot file {path} has a malformed command list for resource {name!r}"
            )

    flags = data["global_flags"]
    if not isinstance(flags, list) or any(
        not isinstance(flag, str) or not flag for flag in flags
    ):
        raise SnapshotError(
            f"the snapshot file {path} has a malformed 'global_flags' entry"
        )

    return {
        "mmx_version": version,
        "resources": {name: list(commands) for name, commands in resources.items()},
        "global_flags": list(flags),
    }


def _fenced_block(lines: list[str], start: int, language: str) -> tuple[list[str], str | None]:
    """Return the body of the first fenced block after ``start`` with ``language``.

    The opening fence must be exactly `````<language>``; a fence with another
    language is an error rather than a silent fallback, so the reader cannot
    pick up the wrong block.

    Returns ``(body, None)`` on success and ``([], reason)`` when the block is
    missing, mistyped or unterminated.
    """
    open_fence = None
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            open_fence = index
            break
    if open_fence is None:
        return [], f"no ```{language} block was found"

    if lines[open_fence].strip() != f"```{language}":
        return [], (
            f"expected a ```{language} block but found {lines[open_fence].strip()!r}"
        )

    body: list[str] = []
    for index in range(open_fence + 1, len(lines)):
        if lines[index].strip().startswith("```"):
            return body, None
        body.append(lines[index])
    return [], f"the ```{language} block is never closed"


def extract_json_surface(doc_text: str) -> dict:
    """Parse the doc's machine-checkable surface.

    Raises :class:`DocParseError` when the section, the block, the JSON or the
    shape is wrong. Callers turn that into a ``PARSE_ERROR`` finding; it must
    never be mistaken for "the doc is in sync".
    """
    lines = doc_text.splitlines()

    heading_index = None
    for index, line in enumerate(lines):
        if line.strip() == SURFACE_HEADING:
            heading_index = index
            break
    if heading_index is None:
        raise DocParseError(
            f"the doc has no {SURFACE_HEADING!r} section (the machine-checkable surface)"
        )

    body, problem = _fenced_block(lines, heading_index + 1, "json")
    if problem is not None:
        raise DocParseError(f"{SURFACE_HEADING}: {problem}")

    try:
        data = json.loads("\n".join(body))
    except json.JSONDecodeError as exc:
        raise DocParseError(f"{SURFACE_HEADING}: the block is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise DocParseError(f"{SURFACE_HEADING}: the block is not a JSON object")

    for key in ("mmx_version", "resources", "global_flags"):
        if key not in data:
            raise DocParseError(f"{SURFACE_HEADING}: the block has no {key!r} key")

    version = data["mmx_version"]
    if not isinstance(version, str) or not version.strip():
        raise DocParseError(f"{SURFACE_HEADING}: 'mmx_version' is not a version string")

    resources = data["resources"]
    if not isinstance(resources, dict):
        raise DocParseError(f"{SURFACE_HEADING}: 'resources' is not an object")
    for name, commands in resources.items():
        if not isinstance(name, str) or not name:
            raise DocParseError(f"{SURFACE_HEADING}: {name!r} is not a resource name")
        if not isinstance(commands, list) or any(
            not isinstance(command, str) or not command for command in commands
        ):
            raise DocParseError(
                f"{SURFACE_HEADING}: the command list for {name!r} is not a list of names"
            )

    flags = data["global_flags"]
    if not isinstance(flags, list) or any(
        not isinstance(flag, str) or not flag for flag in flags
    ):
        raise DocParseError(f"{SURFACE_HEADING}: 'global_flags' is not a list of names")

    return {
        "mmx_version": version,
        "resources": {name: set(commands) for name, commands in resources.items()},
        "global_flags": set(flags),
    }


def _leading_command_words(tokens: list[str]) -> list[str]:
    """Return the leading run of tokens that look like command words."""
    words: list[str] = []
    for token in tokens:
        if not COMMAND_WORD_RE.match(token):
            break
        words.append(token)
    return words


def _resolve_claim(tokens: list[str], known: dict[str, list[str]]) -> tuple[str, str, str | None]:
    """Resolve a claimed invocation into ``(resource, command, over_claim)``.

    ``known`` is the snapshot's command map. It is used to tell a command path
    from its arguments: ``mmx config set api-key`` claims the command
    ``config set`` with ``api-key`` as an argument, while ``mmx config get``
    claims ``config get``, which the CLI does not have.

    Resolution never HIDES a drift: when no prefix of the claim matches a
    known command, the whole claim is reported as-is.

    Resolution must never LAUNDER a drift either. The longest-prefix walk can
    land on a shorter known command than the claim names -- ``video task get``
    resolves to ``video task`` when the CLI renamed the command -- and the
    dead over-claim used to disappear into the live surface with no trace.
    When that happens the claim's full command path comes back as the
    ``over_claim`` so the caller can report it. The resolved command is still
    returned: a claim that carries FLAGS (``video task get --limit 5``)
    resolves to the full command it names, and flags are not part of the
    command path.
    """
    resource = tokens[1]
    leading = _leading_command_words(tokens[2:])
    if not leading:
        return resource, "", None
    known_commands = known.get(resource, [])
    claimed = " ".join(leading)
    for length in range(len(leading), 0, -1):
        candidate = " ".join(leading[:length])
        if candidate in known_commands:
            over_claim = claimed if candidate != claimed else None
            return resource, candidate, over_claim
    return resource, claimed, None


def extract_tree_surface(doc_text: str) -> dict[str, set[str]]:
    """Scrape the human-readable command tree.

    Rows are ``<resource>  <command, command, ...>``. A tree entry that is not
    a command path (a parenthetical note, a flag) is not a claim.
    """
    lines = doc_text.splitlines()
    heading_index = None
    for index, line in enumerate(lines):
        if line.strip() == TREE_HEADING:
            heading_index = index
            break
    if heading_index is None:
        return {}

    body, problem = _fenced_block(lines, heading_index + 1, "text")
    if problem is not None:
        return {}

    resources: dict[str, set[str]] = {}
    for line in body:
        stripped = line.lstrip("│├└─ ").strip()
        if not stripped:
            continue
        parts = re.split(r"\s{2,}", stripped)
        resource = parts[0]
        if resource == "mmx":
            # The tree's own root line ("mmx"), not a resource.
            continue
        rest = parts[1] if len(parts) > 1 else ""
        claimed = resources.setdefault(resource, set())
        for item in rest.split(","):
            item = item.strip()
            if item and COMMAND_PATH_RE.match(item):
                claimed.add(item)
    return resources


def extract_table_claims(
    doc_text: str, known: dict[str, list[str]]
) -> tuple[dict[str, set[str]], list[tuple[str, str, str]]]:
    """Scrape the command table into resolved ``(resource, command)`` claims.

    Also returns the OVER-CLAIMS: rows whose command path is longer than the
    command it resolved to -- ``(resource, claimed, resolved)`` triples. A row
    like ``mmx video task get`` against a CLI that only has ``mmx video task``
    is a dead over-claim, and it is reported rather than absorbed.
    """
    lines = doc_text.splitlines()
    rows: list[list[str]] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not in_table:
                if tuple(cells) == COMMAND_TABLE_HEADER:
                    in_table = True
                continue
            rows.append(cells)
        elif in_table and stripped:
            in_table = False

    resources: dict[str, set[str]] = {}
    over_claims: list[tuple[str, str, str]] = []
    for cells in rows:
        if not cells:
            continue
        claim = cells[0].strip().strip("`").strip()
        tokens = claim.split()
        if len(tokens) < 2 or tokens[0] != "mmx":
            continue
        resource, command, over_claim = _resolve_claim(tokens, known)
        claimed = resources.setdefault(resource, set())
        if command:
            claimed.add(command)
        if over_claim:
            over_claims.append((resource, over_claim, command))
    return resources, over_claims


def extract_prose_global_flags(doc_text: str) -> set[str]:
    """Scrape the human-readable global-flag list, if the doc has one.

    The section ends at the next HEADING, not at the first line that is not a
    bullet. A doc that introduces its list with a sentence -- the live doc
    says "These are accepted by every command:" between the heading and the
    list -- still carries the list, and a scanner that stops at that sentence
    scrapes NOTHING: the second net silently catches nothing at all.
    """
    lines = doc_text.splitlines()
    flags: set[str] = set()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == GLOBAL_FLAGS_HEADING:
            in_section = True
            continue
        if not in_section:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            break
        match = re.match(r"^- `(--[A-Za-z0-9][A-Za-z0-9-]*)`", stripped)
        if match:
            flags.add(match.group(1))
        elif not stripped.startswith("- "):
            # A prose line between the heading and the list is not the end of
            # the section: skip it and keep scanning. Only a heading ends it.
            continue
    return flags


def extract_prose_version(doc_text: str) -> str | None:
    """Return the npm version the doc states, if it states one."""
    match = NPM_VERSION_RE.search(doc_text)
    return match.group(1) if match else None


def collect_documented_surface(doc_text: str, known: dict[str, list[str]]) -> dict:
    """Build the doc's documented surface from every source it carries.

    The JSON block is authoritative. The tree and the table are unioned in, so
    a doc whose prose contradicts its own JSON block still reports the
    contradiction.
    """
    resources: dict[str, set[str]] = {}
    flags: set[str] = set()
    version: str | None = None

    try:
        json_surface = extract_json_surface(doc_text)
    except DocParseError:
        json_surface = None
    if json_surface is not None:
        for name, commands in json_surface["resources"].items():
            resources.setdefault(name, set()).update(commands)
        flags.update(json_surface["global_flags"])
        version = json_surface["mmx_version"]

    for name, commands in extract_tree_surface(doc_text).items():
        resources.setdefault(name, set()).update(commands)
    table_resources, over_claims = extract_table_claims(doc_text, known)
    for name, commands in table_resources.items():
        resources.setdefault(name, set()).update(commands)
    flags.update(extract_prose_global_flags(doc_text))

    prose_version = extract_prose_version(doc_text)
    if version is None:
        version = prose_version

    return {
        "mmx_version": version,
        "prose_version": prose_version,
        "resources": resources,
        "global_flags": flags,
        "over_claims": over_claims,
    }


def compare(doc_surface: dict, snapshot: dict) -> list[dict]:
    """Compare the documented surface against the measured surface."""
    findings: list[dict] = []
    known = snapshot["resources"]
    doc_resources = doc_surface["resources"]
    snap_resources = snapshot["resources"]

    for name in sorted(doc_resources):
        if False:
            findings.append(
                _finding(
                    "DOCUMENTED_MISSING",
                    f"the doc documents the resource {name!r}, which the CLI does not have",
                    scope="resource",
                    resource=name,
                )
            )
            continue
        for command in sorted(doc_resources[name] - set(snap_resources.get(name, []))):
            findings.append(
                _finding(
                    "DOCUMENTED_MISSING",
                    f"the doc documents `mmx {name} {command}`, which the CLI does not have",
                    scope="command",
                    resource=name,
                    command=command,
                )
            )

    # An OVER-CLAIM is a table row whose command path is longer than the
    # command the CLI has: the CLI renamed `video task get` to `video task`
    # and the doc still names the old path. Resolving the row lands on the
    # shorter command, and the dead over-claim must still be VISIBLE.
    for resource, claimed, resolved in doc_surface.get("over_claims", []):
        findings.append(
            _finding(
                "DOCUMENTED_MISSING",
                f"the doc's command table claims `mmx {resource} {claimed}`, which the "
                f"CLI does not have (it resolves to `mmx {resource} {resolved}`)",
                scope="command",
                resource=resource,
                command=claimed,
                resolved_command=resolved,
            )
        )

    for name in sorted(snap_resources):
        if name not in doc_resources:
            findings.append(
                _finding(
                    "UNDOCUMENTED",
                    f"the CLI has the resource {name!r}, which the doc never mentions",
                    scope="resource",
                    resource=name,
                )
            )
            continue
        for command in sorted(set(snap_resources[name]) - doc_resources.get(name, set())):
            findings.append(
                _finding(
                    "UNDOCUMENTED",
                    f"the CLI has `mmx {name} {command}`, which the doc never mentions",
                    scope="command",
                    resource=name,
                    command=command,
                )
            )

    snap_flags = set(snapshot["global_flags"])
    for flag in sorted(doc_surface["global_flags"] - snap_flags):
        findings.append(
            _finding(
                "DOCUMENTED_MISSING",
                f"the doc documents the global flag {flag!r}, which the CLI does not have",
                scope="global_flag",
                flag=flag,
            )
        )
    for flag in sorted(snap_flags - doc_surface["global_flags"]):
        findings.append(
            _finding(
                "UNDOCUMENTED",
                f"the CLI has the global flag {flag!r}, which the doc never mentions",
                scope="global_flag",
                flag=flag,
            )
        )

    snap_version = snapshot["mmx_version"]
    if doc_surface["mmx_version"] is not None and doc_surface["mmx_version"] != snap_version:
        findings.append(
            _finding(
                "VERSION_DRIFT",
                f"the doc states mmx {doc_surface['mmx_version']}, the installed CLI is {snap_version}",
                scope="json",
                doc_version=doc_surface["mmx_version"],
                snapshot_version=snap_version,
            )
        )
    prose_version = doc_surface["prose_version"]
    if prose_version is not None and prose_version != snap_version:
        findings.append(
            _finding(
                "VERSION_DRIFT",
                f"the doc's npm version line states {prose_version}, the installed CLI is {snap_version}",
                scope="prose",
                doc_version=prose_version,
                snapshot_version=snap_version,
            )
        )

    return findings


def check(doc_path: Path, snapshot_path: Path) -> dict:
    """Run the gate and return its report."""
    findings: list[dict] = []

    snapshot = None
    try:
        snapshot = load_snapshot(snapshot_path)
    except SnapshotError as exc:
        findings.append(
            _finding("INSTRUMENT_ERROR", f"the snapshot could not be read: {exc}", scope="snapshot")
        )

    doc_text = None
    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(
            _finding("INSTRUMENT_ERROR", f"the doc could not be read: {exc}", scope="doc")
        )

    doc_surface: dict | None = None
    if doc_text is not None:
        try:
            doc_surface = extract_json_surface(doc_text)
        except DocParseError as exc:
            findings.append(
                _finding("PARSE_ERROR", f"the doc could not be parsed: {exc}", scope="doc")
            )

    if snapshot is not None and doc_text is not None:
        known = snapshot["resources"]
        documented = collect_documented_surface(doc_text, known)
        findings.extend(compare(documented, snapshot))
        doc_version = documented["mmx_version"]
    else:
        doc_version = None

    return {
        "doc": str(doc_path),
        "snapshot": str(snapshot_path),
        "snapshot_version": snapshot["mmx_version"] if snapshot else None,
        "doc_version": doc_version,
        "findings": findings,
        "finding_count": len(findings),
        "ok": not findings,
    }


def _print_report(report: dict) -> None:
    print("mmx-surface-parity: doc vs the measured mmx CLI surface")
    print(f"  doc      : {report['doc']}")
    print(f"  snapshot : {report['snapshot']}")
    print(f"  version  : doc {report['doc_version']} / snapshot {report['snapshot_version']}")
    if report["ok"]:
        print("  OK: the doc describes exactly the measured surface")
        return
    print(f"  {report['finding_count']} FINDING(S):")
    for finding in report["findings"]:
        print(f"    - [{finding['kind']}] {finding['detail']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check MMX_CLI_SURFACE.md against the measured mmx CLI surface."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="run the gate and exit non-zero on any finding (default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON",
    )
    parser.add_argument(
        "--doc",
        default=str(DEFAULT_DOC),
        help="the doc to check (default: %(default)s)",
    )
    parser.add_argument(
        "--snapshot",
        default=str(DEFAULT_SNAPSHOT),
        help="the measured snapshot to check against (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    report = check(Path(args.doc), Path(args.snapshot))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_report(report)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
