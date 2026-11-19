"""The fleet MCP roster must not carry a malformed reference in a config value.

WHAT THIS CATCHES
-----------------
`.claude/mcp.json` is the FLEET roster: `deploy/provision/claude-pmoves.sh`
reads it from `origin/main` on EVERY node and hands it to Claude Code after
running it through `pmoves/tools/mcp_roster_normalize.py`.

That normalizer's P4/P5 passes expand `${VAR}` in every `url`, `headers` and
`env` value, and RECORD what would not expand. A recorded miss is a verdict
against the server: the server is announced as degraded in the durable
`_pmoves_roster_verdicts` block.

THE DEFECT THIS EXISTED FOR (measured 2026-11-19). The `pmoves-nats-fleet`
entry carried its documentation as an `env` key:

    "env": {
      "NATS_URL": "${NATS_URL}",
      "NATS_CREDS": "${NATS_CREDS:-}",
      "_NATS_CREDS_NOTE": "... rejects an empty value AND an unresolved
                            \"${...}\" placeholder ..."
    }

The note QUOTES the literal text `${...}`. `expand()` parses that as a
variable reference whose name is `...`, which fails the `_IDENT` check, so it
is recorded as a MALFORMED reference and the server is degraded -- always, in
every launch, on every node, whatever the operator's environment says. The
cross-node NATS bridge (the SPARK cascade dispatch path) was therefore
permanently degraded by its own documentation.

MEASURED, with the LIVE normalizer, both operator environments:

    creds SET    -> degraded: pmoves-nats-fleet: ['${...}']
    creds UNSET  -> degraded: pmoves-nats-fleet: ['${...}', 'NATS_CREDS']

Every OTHER degraded entry in that roster names a REAL env var the operator
can set (`HOSTINGER_API_KEY`, `TAILSCALE_API_KEY`, ...). `pmoves-nats-fleet`
was the only one degraded by PROSE. No amount of configuration could clear it:
the only thing that clears it is not quoting a placeholder in a config value.

WHY A MALFORMED REFERENCE IS THE RIGHT INVARIANT (not "the nats entry").
A reference to a real variable may legitimately be unresolved -- that is the
operator's credential to provide, and the verdict is exactly right. A
MALFORMED reference can never resolve: there is no environment variable whose
name is `...`. So a malformed reference in a config value is a permanent
defect by construction, and asserting on it catches the whole class rather
than one instance of it.

WHY DOCUMENTATION MUST NOT LIVE IN `env` (the house convention).
`deploy/provision/claude-pmoves.sh` says it explicitly, in the comment that
explains why its own raw-roster gate excludes `_`-prefixed lines:

    FALSE POSITIVE, prose. `.claude/mcp.json`'s `_note` quotes the docs
    verbatim -- "uses the unexpanded ${VAR} text as-is". Claude Code reads
    `mcpServers`; `_`-prefixed keys are documentation.

Fourteen entries in the fleet roster already carry their documentation as a
SERVER-LEVEL `_`-prefixed key (`_note`, `_purpose`, `_setup`, `_disabled`).
The `pmoves-nats-fleet` note was the only one inside an `env` block -- which
also means it was being injected into the MCP server's real environment as a
700-character string, and scanned for references that were never meant to be
references.

WHAT THE FIX WAS
----------------
Lift the note out of `env` to a server-level `_`-prefixed key. Nothing about
the server's actual configuration changes: the MCP never read the note
(`git grep _NATS_CREDS_NOTE` returns exactly one hit -- the roster itself).
The note's TEXT is preserved verbatim, because the text is the documentation
of the placeholder semantics and is worth keeping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import pytest

from pmoves.tools import mcp_config_generator as gen
from pmoves.tools import mcp_roster_normalize as mrn

REPO_ROOT = Path(__file__).resolve().parents[3]

# The tracked FLEET roster. Mutable at module level so the mutation harness can
# repoint the ratchet at a mutated copy (the house convention: the ratchet
# reads whatever it is pointed at, so pointing it at a broken copy is exactly
# the state that must be rejected).
ROSTER_PATH = REPO_ROOT / ".claude" / "mcp.json"

# The inventory the roster is derived from.
INVENTORY_PATH = REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json"

# The server whose documentation was in the wrong place.
TARGET_SERVER = "pmoves-nats-fleet"

# The documentation key, and the env var it documents.
DOC_KEY = "_NATS_CREDS_NOTE"
DOCUMENTED_VAR = "NATS_CREDS"

# The fields the normalizer expands. `_DROP_FIELDS` + `_WARN_FIELDS` are the
# tool's own constants -- read from the tool, never restated here, so this
# ratchet cannot drift from the component it constrains.
SCANNED_FIELDS = tuple(mrn._DROP_FIELDS) + tuple(mrn._WARN_FIELDS)

# Servers the inventory declares for the `claude` client that the FLEET roster
# deliberately does NOT carry, each with the MEASURED reason.
#
# WHY THIS LIST IS NOT OPTIONAL. MEASURED 2026-11-19 with the LIVE generator
# at client `claude`, endpoint `fleet`, `allow_os_environ=False`:
#
#   * the inventory declares 19 server entries in total;
#   * the generator EMITS 14 of them for this client;
#   * the tracked roster carries 21 servers.
#
# Of the 14 generated, exactly THREE are not rostered -- and the reason
# differs per server, so the difference has to be WRITTEN DOWN, not skipped.
# The roster's other 10 servers are the opposite direction: they are in the
# roster but are not described by the inventory at all (hand-added), so they
# are not absences and are not listed here.
#
# The previous version of this test skipped an absent server in silence, which
# meant an inventory addition (the generator would emit it) or an accidental
# deletion from the roster was invisible: the test passed while the fleet was
# missing a whole server. Codex finding 4631230905 on this file.
#
# The reasons, measured:
#
#   e2b-danger-room   A stdio server whose command runs
#                     `node ./pmoves-e2b-mcp-server/packages/js/build/index.js`.
#                     MEASURED: the e2b submodule's tree at `e19e1ac7d` has NO
#                     `packages/js/build` entry at all (only `src/`,
#                     `package.json`, `tsconfig.json`), and NO file in
#                     `pmoves/mk`, `pmoves/Makefile`, `deploy/`,
#                     `pmoves/tools` or `pmoves/scripts` performs the
#                     `npm run build` that produces it. The entry would
#                     therefore launch and exit with MODULE_NOT_FOUND on every
#                     node -- a permanently failed MCP server in every session.
#
#   flute-voice       The SSE surface of the flute-gateway. On the fleet
#                     endpoint the inventory resolves it to
#                     `http://${TS_Z890}:8055/sse`, so it is only reachable
#                     where that tailnet name resolves, and it needs
#                     `FLUTE_API_KEY` (present in `pmoves/env.shared.example`).
#
#   flute-voice-mcp   The streamable-http twin of the same gateway at the same
#                     host, with the same `FLUTE_API_KEY` dependency.
#
# A NEW absence must fail this ratchet; a server that BECOMES rostered must
# fail it too, so this record cannot silently go stale.
GENERATED_NOT_ROSTERED: Dict[str, str] = {
    "e2b-danger-room": (
        "stdio server whose command runs node ./pmoves-e2b-mcp-server/packages/js/"
        "build/index.js; the e2b submodule's tree has no packages/js/build entry and "
        "no file in pmoves/mk, pmoves/Makefile, deploy/, pmoves/tools or "
        "pmoves/scripts performs the npm run build that produces it, so the entry "
        "would launch and fail on every node"
    ),
    "flute-voice": (
        "SSE surface of the flute-gateway; on the fleet endpoint the inventory "
        "resolves it to http://${TS_Z890}:8055/sse, so it is reachable only where "
        "that tailnet name resolves, and it needs FLUTE_API_KEY"
    ),
    "flute-voice-mcp": (
        "streamable-http twin of the flute-gateway at the same host, with the same "
        "FLUTE_API_KEY dependency"
    ),
}


def _load_roster(path: Path | None = None) -> Dict[str, Any]:
    return json.loads((path or ROSTER_PATH).read_text(encoding="utf-8"))


def _servers(roster: Mapping[str, Any]) -> Dict[str, Any]:
    servers = roster.get("mcpServers")
    return servers if isinstance(servers, dict) else {}


def _scannable_values(entry: Mapping[str, Any]) -> Iterable[tuple[str, str, str]]:
    """Yield ``(field, key, value)`` for every value the normalizer expands."""
    for field in SCANNED_FIELDS:
        block = entry.get(field)
        if isinstance(block, str):
            yield field, "<value>", block
        elif isinstance(block, dict):
            for key, value in block.items():
                if isinstance(value, str):
                    yield field, key, value


def _malformed_references(value: str) -> list[str]:
    """References that can NEVER resolve, found with the tool's own `expand`.

    `expand()` records three kinds of miss, and the RECORDING is what tells
    them apart:

      * an unresolvable but well-formed reference, under its NAME
        (`NATS_CREDS`) -- a real variable the operator has not set;
      * a malformed one, under its LITERAL TEXT (`${...}`) -- the name is not
        an identifier, so no variable can ever have it;
      * an UNBALANCED one (`${BROKEN`), under the literal text it could not
        close.

    So the discriminator is "does the recorded miss still look like a
    REFERENCE?", i.e. does it start with `${`. A well-formed miss is a bare
    name and never starts with `${`; every malformed miss does, whether or
    not it has a closing brace. Requiring the closing brace here would drop
    the unbalanced case -- and an unbalanced reference is exactly as
    unsatisfiable as a malformed one, so it would leave a hole in the class
    this ratchet exists to close.

    This uses the tool's own parser rather than a second regex, so the two
    cannot disagree.
    """
    missing: list[str] = []
    mrn.expand(value, {}, missing)
    return [m for m in missing if m.startswith("${")]


def test_no_env_value_carries_a_malformed_reference() -> None:
    """No config value may quote a reference that can never resolve.

    A well-formed `${VAR}` may be unresolved -- that is a missing credential
    and the verdict is right. A MALFORMED reference is unsatisfiable by
    construction, so it is a permanent defect.
    """
    offenders: list[str] = []
    for name, entry in _servers(_load_roster()).items():
        if not isinstance(entry, dict):
            continue
        for field, key, value in _scannable_values(entry):
            malformed = _malformed_references(value)
            if malformed:
                offenders.append(f"{name}.{field}.{key} -> {malformed}")
    assert not offenders, (
        "the fleet roster carries reference(s) that can never resolve, so the "
        "normalizer degrades those servers permanently -- on every node, in "
        "every launch, whatever the operator's environment says:\n  "
        + "\n  ".join(offenders)
        + "\nA malformed reference is unsatisfiable by construction (there is "
        "no environment variable named `...`), so no configuration clears it. "
        "Documentation that quotes a placeholder belongs in a server-level "
        "`_`-prefixed key, which the normalizer never scans."
    )


def test_no_documentation_key_sits_inside_an_env_block() -> None:
    """`env` carries configuration; documentation belongs at server level.

    The normalizer expands every `env` value, so a note placed there is both
    scanned for references that were never references AND injected into the
    MCP server's real environment.
    """
    offenders: list[str] = []
    for name, entry in _servers(_load_roster()).items():
        if not isinstance(entry, dict):
            continue
        env = entry.get("env")
        if isinstance(env, dict):
            docs = sorted(k for k in env if k.startswith("_"))
            if docs:
                offenders.append(f"{name}.env -> {docs}")
    assert not offenders, (
        "documentation keys found inside an `env` block:\n  "
        + "\n  ".join(offenders)
        + "\n`env` is configuration and is expanded by the normalizer; a "
        "server-level `_`-prefixed key is documentation and is not (see "
        "deploy/provision/claude-pmoves.sh on why `_`-prefixed keys are "
        "excluded from the raw-roster gate for exactly this reason)."
    )


@pytest.mark.parametrize(
    "environ",
    [
        pytest.param(
            {
                "NATS_URL": "nats://fleet:KVM4-2",
                "NATS_CREDS": "/vault/core.creds",
            },
            id="creds-set",
        ),
        pytest.param(
            {"NATS_URL": "nats://fleet:KVM4-2"},
            id="creds-unset",
        ),
    ],
)
def test_the_nats_fleet_server_is_not_degraded_by_its_own_documentation(
    environ: Mapping[str, str],
) -> None:
    """The NATS bridge must not be degraded by a string that describes it.

    Both operator environments are covered, because the defect differed
    between them: with the `.creds` materialised the note still produced a
    malformed reference, and with it absent it ALSO named `NATS_CREDS`,
    which the operator cannot fix because the roster's own `NATS_CREDS`
    entry resolves that variable correctly.
    """
    roster = _load_roster()
    _, dropped, degraded = mrn.normalize(roster, str(REPO_ROOT), dict(environ))
    degraded_map = dict(degraded)
    assert TARGET_SERVER not in degraded_map, (
        f"{TARGET_SERVER} is degraded by {degraded_map.get(TARGET_SERVER)!r} "
        f"with environment {sorted(environ)}. The cross-node NATS bridge is "
        "the SPARK cascade dispatch path; a permanent degrade means the "
        "signal path looks broken on every node in every session."
    )
    assert TARGET_SERVER not in dict(dropped), (
        f"{TARGET_SERVER} was DROPPED with environment {sorted(environ)}: "
        f"{dict(dropped).get(TARGET_SERVER)!r}"
    )


def test_the_nats_creds_documentation_is_still_present_and_intact() -> None:
    """The fix must MOVE the note, not delete it.

    The obvious way to make the malformed-reference finding disappear is to
    drop the note. That would be a worse outcome than the defect: the note is
    the only record of the CORE-account transport-trust and payload-provenance
    gates, and of the `_nats_creds()` fallback rule it describes. This test
    is what stops the ratchet from being satisfiable by deletion.
    """
    entry = _servers(_load_roster()).get(TARGET_SERVER)
    assert isinstance(entry, dict), f"{TARGET_SERVER} is missing from the roster"
    assert DOC_KEY in entry, (
        f"{TARGET_SERVER}.{DOC_KEY} is gone from the roster. The note "
        "documents the CORE-account transport-trust gate, the "
        "payload-provenance gate and the `_nats_creds()` fallback rule; it "
        "belongs at server level, not deleted."
    )
    note = entry[DOC_KEY]
    assert isinstance(note, str) and note.strip(), (
        f"{TARGET_SERVER}.{DOC_KEY} is empty"
    )
    for phrase in (DOCUMENTED_VAR, "transport-trust gate", "payload-provenance gate"):
        assert phrase in note, (
            f"{TARGET_SERVER}.{DOC_KEY} no longer mentions {phrase!r}; the note "
            "was truncated rather than moved."
        )


def test_the_fleet_roster_still_agrees_with_its_generator() -> None:
    """Every field the generator describes must still match the tracked file.

    `.claude/mcp.json` is produced by `mcp_config_generator` and merged over
    the tracked file, so the tracked entry may carry hand-added keys the
    inventory does not describe -- but every key the generator DOES describe
    must hold the same value, or the roster has drifted from its source.

    A server the generator describes and the roster does NOT carry is the
    OTHER direction, and it is the more dangerous one: it is invisible to a
    field-by-field comparison, because there is no field to compare. It means
    the deployed fleet is missing an entire inventory-defined server.

    The three measured exceptions are recorded in `GENERATED_NOT_ROSTERED`,
    and this test holds that record to BOTH directions:

      * a NEW absence fails -- the inventory moved on and the roster did not;
      * a recorded absence that BECOMES rostered also fails -- otherwise the
        record of measured reasons goes stale and keeps claiming a server is
        missing when it is not.
    """
    inventory = gen.load_inventory(INVENTORY_PATH)
    generated = gen.generate_for_client(
        "claude", inventory=inventory, endpoint="fleet", allow_os_environ=False
    )
    tracked = _servers(_load_roster())
    drift: list[str] = []
    absent: list[str] = []
    for key, gen_entry in _servers(generated).items():
        tracked_entry = tracked.get(key)
        if not isinstance(gen_entry, dict):
            continue
        if not isinstance(tracked_entry, dict):
            # NOT a `continue`. An absent server is a drift of its own, and
            # skipping it is how a whole server goes missing unnoticed.
            absent.append(key)
            continue
        for field, value in gen_entry.items():
            if field == "env" and isinstance(value, dict):
                actual = tracked_entry.get("env")
                if not isinstance(actual, dict):
                    drift.append(f"{key}.env missing")
                    continue
                for env_key, env_value in value.items():
                    if actual.get(env_key) != env_value:
                        drift.append(
                            f"{key}.env.{env_key}: tracked {actual.get(env_key)!r} "
                            f"!= generated {env_value!r}"
                        )
                continue
            if tracked_entry.get(field) != value:
                drift.append(
                    f"{key}.{field}: tracked {tracked_entry.get(field)!r} "
                    f"!= generated {value!r}"
                )

    undocumented = sorted(set(absent) - set(GENERATED_NOT_ROSTERED))
    assert not undocumented, (
        "the fleet roster is MISSING a server the inventory declares:\n  "
        + "\n  ".join(
            f"{key} -- no recorded reason; add the measured reason to "
            f"GENERATED_NOT_ROSTERED in this file, or roster the server"
            for key in undocumented
        )
        + "\nThe generator emits these servers for the `claude` client, so the "
        "inventory has moved on and the tracked roster has not. A missing "
        "server is invisible to the field-by-field check below: there is no "
        "field to compare."
    )

    resolved = sorted(set(GENERATED_NOT_ROSTERED) - set(absent))
    assert not resolved, (
        "these servers are recorded in GENERATED_NOT_ROSTERED as deliberately "
        "absent from the fleet roster, but they are now rostered:\n  "
        + "\n  ".join(resolved)
        + "\nThe record of measured reasons has gone stale. Remove them from "
        "GENERATED_NOT_ROSTERED and update the measurement note above with "
        "the current numbers."
    )

    assert not drift, (
        "the tracked fleet roster has drifted from the inventory it is "
        "generated from:\n  " + "\n  ".join(drift) + "\nRegenerate with "
        "`python -m pmoves.tools.mcp_config_generator --client claude`."
    )


def test_a_merge_regeneration_preserves_the_server_documentation() -> None:
    """Regenerating the roster must not silently delete the note.

    The merge overlays the generated fields onto the tracked file and keeps
    the tracked file's own keys. That is the property this fix depends on:
    the note lives in a tracked-file key the generator does not describe, so
    it survives. If a future generator stopped preserving unknown keys, the
    documentation would vanish with no signal.
    """
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "mcp.json"
        shutil.copy(ROSTER_PATH, scratch)
        inventory = gen.load_inventory(INVENTORY_PATH)
        gen.write_client_config(
            "claude",
            scratch,
            merge=True,
            inventory=inventory,
            endpoint="fleet",
            allow_os_environ=False,
        )
        merged = json.loads(scratch.read_text(encoding="utf-8"))
    entry = _servers(merged).get(TARGET_SERVER)
    assert isinstance(entry, dict), f"{TARGET_SERVER} vanished from the merged roster"
    assert DOC_KEY in entry, (
        f"a merge regeneration dropped {TARGET_SERVER}.{DOC_KEY}. The merge "
        "path overlays the generated fields and keeps the tracked file's own "
        "keys; if that changes, the documentation is lost silently."
    )
