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

    `expand()` records an unresolvable but well-formed reference under its
    NAME (`NATS_CREDS`) and a malformed one under its LITERAL TEXT
    (`${...}`). So with an EMPTY environment, a recorded miss that still
    looks like a reference is malformed, and one that does not is a real
    variable the operator has not set. This uses the tool's own parser rather
    than a second regex, so the two cannot disagree.
    """
    missing: list[str] = []
    mrn.expand(value, {}, missing)
    return [m for m in missing if m.startswith("${") and m.endswith("}")]


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
    """
    inventory = gen.load_inventory(INVENTORY_PATH)
    generated = gen.generate_for_client(
        "claude", inventory=inventory, endpoint="fleet", allow_os_environ=False
    )
    tracked = _servers(_load_roster())
    drift: list[str] = []
    for key, gen_entry in _servers(generated).items():
        tracked_entry = tracked.get(key)
        if not isinstance(gen_entry, dict) or not isinstance(tracked_entry, dict):
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
