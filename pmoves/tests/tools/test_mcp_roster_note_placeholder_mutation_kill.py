"""Mutation-kill harness: the fleet-roster malformed-reference ratchet must say no.

The companion harness for
``pmoves/tests/tools/test_mcp_roster_note_placeholder_ratchet.py``.

Why this exists
---------------
A ratchet that can only pass is decoration. This harness proves the ratchet
is LOAD-BEARING by restoring the exact defect it was written for and showing
that the named test FAILS when it comes back.

How it works (house convention, lesson #12 from
``test_gap_ratchet_LEARNINGS.md``): a mutation-kill must INVOKE the assertion
the ratchet uses, never restate it. So this harness does not re-implement the
checks. It:

1. copies the REAL fleet roster (and, for one mutation, the real inventory)
   into a tmp dir,
2. MUTATES the copy -- restoring the defect, or changing the contract the
   ratchet asserts against,
3. repoints the ratchet's OWN module-level constants at the mutated copy,
4. calls the ratchet's OWN test functions and asserts they RAISE with the
   SPECIFIC expected message -- not merely that "something" raised.

The mutated copy is what makes the mutation honest: the ratchet reads
whatever file it is pointed at, so pointing it at a roster with the note back
inside `env` is exactly the state that must be rejected.

The mutations
-------------
M1  The note is moved BACK into `env`, `${...}` and all.
    This is the ORIGINAL defect, restored byte-for-byte from the shape that
    shipped. Kills ``test_no_env_value_carries_a_malformed_reference`` and
    ``test_the_nats_fleet_server_is_not_degraded_by_its_own_documentation``.

M2  The note is moved into `env` and its malformed `${...}` is rewritten to a
    WELL-FORMED `${NATS_CREDS}`.
    This kills ``test_no_documentation_key_sits_inside_an_env_block`` while
    ``test_no_env_value_carries_a_malformed_reference`` STILL PASSES -- which
    is the point. It proves the two rules are INDEPENDENT: the malformed-
    reference rule is not simply re-detecting "a note is in env", and the
    documentation-placement rule is not merely a special case of it.

M3  The note is DELETED.
    Kills ``test_the_nats_creds_documentation_is_still_present_and_intact``
    and ``test_a_merge_regeneration_preserves_the_server_documentation``. The
    note is the only record of the CORE-account transport-trust gate, the
    payload-provenance gate and the `_nats_creds()` fallback rule; a fix
    that made the finding disappear by deleting the documentation would be a
    regression, and this is the mutation that proves the ratchet can tell
    the difference.

M4  The INVENTORY changes under the roster.
    Kills ``test_the_fleet_roster_still_agrees_with_its_generator``. The
    roster is generated from the inventory and merged over the tracked file,
    so a change to the source that the roster does not reflect is drift.

M5  An UNBALANCED reference (``${BROKEN``) lands in a config value.
    Kills ``test_no_env_value_carries_a_malformed_reference``. Codex finding
    4631230891: the filter used to require a CLOSING brace, so an unbalanced
    reference was discarded -- and the normalizer still degrades the server,
    because it records the literal text it could not close. The hole left the
    malformed-reference class half-unprotected.

M6  The INVENTORY gains a server the roster does not carry.
    Kills ``test_the_fleet_roster_still_agrees_with_its_generator``. Codex
    finding 4631230905: the absence branch used to `continue`, so a whole
    missing server was invisible -- a field-by-field comparison has nothing
    to compare when the entry is not there at all.

M7  A server recorded as deliberately absent BECOMES rostered.
    Kills ``test_the_fleet_roster_still_agrees_with_its_generator``. The
    other direction of the absence record: without it, the record of
    measured reasons could go stale and keep claiming a server is missing
    when it is not. The roster entry is inserted VERBATIM from the
    generator, so the only thing that can fail is the stale record.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHET_MODULE = "pmoves.tests.tools.test_mcp_roster_note_placeholder_ratchet"

# The key the documentation lives under, and the server that carries it.
DOC_KEY = "_NATS_CREDS_NOTE"
TARGET_SERVER = "pmoves-nats-fleet"

# The malformed reference the original note quoted. It is unsatisfiable by
# construction: there is no environment variable named `...`.
MALFORMED = "${...}"

# A well-formed reference to a real variable. Unresolved, but not malformed.
WELL_FORMED = "${NATS_CREDS}"

# An UNBALANCED reference: it opens a placeholder and never closes it, so no
# environment variable can ever satisfy it. The normalizer records the literal
# text it could not close.
UNBALANCED = "${BROKEN"

# The key used by the M6 mutation: a server the inventory declares and the
# tracked roster does not carry.
ABSENT_PROBE_KEY = "natsnote-absent-probe"

# One of the servers recorded in GENERATED_NOT_ROSTERED as deliberately
# absent. M7 rosters it, so the absence record must notice.
RECORDED_ABSENT_SERVER = "flute-voice-mcp"


def _load_ratchet():
    """Import the ratchet module fresh, with its constants reset.

    `importlib.reload` matters here: the harness repoints `ROSTER_PATH` and
    `INVENTORY_PATH` at mutated copies, and without a reload the next test
    would copy the ALREADY-MUTATED file and mutate it again -- so the
    "mutation setup failed" error would mask the real assertion.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    importlib.invalidate_caches()
    module = importlib.import_module(RATCHET_MODULE)
    return importlib.reload(module)


def _mutated_roster(tmp_path: Path, mutate) -> Path:
    """Copy the real roster and apply *mutate* to the parsed server entry.

    The copy is the real tracked file, so the mutation is applied to the
    artefact the ratchet actually reads.
    """
    ratchet = _load_ratchet()
    dest = tmp_path / "mcp.json"
    shutil.copy(ratchet.ROSTER_PATH, dest)
    raw = json.loads(dest.read_text(encoding="utf-8"))
    mutate(raw["mcpServers"][TARGET_SERVER])
    dest.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return dest


def _mutated_roster_raw(tmp_path: Path, mutate) -> Path:
    """Copy the real roster and apply *mutate* to the WHOLE roster document.

    Some mutations are not about one server's fields -- adding a server to the
    roster, for instance -- so they need the top-level document.
    """
    ratchet = _load_ratchet()
    dest = tmp_path / "mcp.json"
    shutil.copy(ratchet.ROSTER_PATH, dest)
    raw = json.loads(dest.read_text(encoding="utf-8"))
    mutate(raw)
    dest.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return dest


def _move_note_into_env(server: Dict[str, Any], note_value: str) -> None:
    """Move the documentation back inside `env`, optionally reworded."""
    note = server.pop(DOC_KEY)
    server["env"][DOC_KEY] = note_value if note_value is not None else note


def test_mutation_note_back_inside_env_is_killed(tmp_path: Path) -> None:
    """Restoring the ORIGINAL defect MUST make the ratchet fail.

    This is the exact shape that shipped: the documentation quoted the
    literal `${...}` from inside an `env` block.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_roster(tmp_path, lambda s: _move_note_into_env(s, None))
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_no_env_value_carries_a_malformed_reference()
    assert "can never resolve" in str(excinfo.value), (
        "the ratchet raised, but not with the malformed-reference message -- "
        f"the assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_note_back_inside_env_restores_the_permanent_degrade(
    tmp_path: Path,
) -> None:
    """The behavioural test MUST fail when the defect comes back.

    The malformed-reference test above is a structural check. This one runs
    the LIVE normalizer and asserts the server is not degraded -- so it is
    the test that would have caught the operator-visible symptom (the NATS
    bridge degraded on every node, in every session).
    """
    ratchet = _load_ratchet()
    mutated = _mutated_roster(tmp_path, lambda s: _move_note_into_env(s, None))
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_the_nats_fleet_server_is_not_degraded_by_its_own_documentation(
            {"NATS_URL": "nats://fleet:KVM4-2", "NATS_CREDS": "/vault/core.creds"}
        )
    assert "is degraded by" in str(excinfo.value), (
        "the ratchet raised, but not with the degrade message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_documentation_key_inside_env_is_killed(tmp_path: Path) -> None:
    """A note in `env` MUST fail the placement rule -- even when it is
    well-formed.

    The note here quotes a REAL variable rather than the malformed `${...}`,
    so the malformed-reference rule has nothing to say. That isolates the
    two rules: the placement rule must still fire, and the malformed-
    reference rule must still PASS. If either changed shape, the harness
    would be asserting a rule the ratchet does not have.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_roster(
        tmp_path, lambda s: _move_note_into_env(s, f"a note about {WELL_FORMED}")
    )
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_no_documentation_key_sits_inside_an_env_block()
    assert "documentation keys found inside an `env` block" in str(excinfo.value), (
        "the ratchet raised, but not with the documentation-placement message "
        f"-- the assertion that should have fired changed shape: {excinfo.value!r}"
    )

    # The malformed-reference rule must NOT fire for a well-formed reference.
    # If it did, the two rules would be the same rule wearing two names.
    ratchet.test_no_env_value_carries_a_malformed_reference()


def test_mutation_deleted_documentation_is_killed(tmp_path: Path) -> None:
    """Deleting the note MUST fail the ratchet.

    Deleting the documentation is the tempting way to make the malformed
    reference disappear. It would also delete the only record of the
    CORE-account transport-trust gate, the payload-provenance gate and the
    `_nats_creds()` fallback rule. The ratchet must reject that.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_roster(tmp_path, lambda s: s.pop(DOC_KEY))
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_the_nats_creds_documentation_is_still_present_and_intact()
    assert "is not a server-level key" in str(excinfo.value) or (
        "is gone from the roster" in str(excinfo.value)
    ), (
        "the ratchet raised, but not with the missing-documentation message "
        f"-- the assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_deleted_documentation_is_killed_by_the_merge_test(
    tmp_path: Path,
) -> None:
    """The merge test MUST fail when the documentation is gone.

    The merge test is the provenance guard: it asserts that regenerating the
    roster does not silently drop a key the generator does not describe. A
    roster without the note must fail it.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_roster(tmp_path, lambda s: s.pop(DOC_KEY))
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_a_merge_regeneration_preserves_the_server_documentation()
    assert "dropped" in str(excinfo.value), (
        "the ratchet raised, but not with the merge message -- the assertion "
        f"that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_inventory_drift_is_killed(tmp_path: Path) -> None:
    """The inventory changing under the roster MUST be detected.

    `.claude/mcp.json` is generated from `pmoves/config/mcp_inventory.json`
    and merged over the tracked file. If the source changes and the roster
    does not, the roster has drifted from the contract it is derived from --
    which is how a server ends up pointing at an endpoint nobody serves.
    """
    ratchet = _load_ratchet()
    inventory = json.loads(ratchet.INVENTORY_PATH.read_text(encoding="utf-8"))
    for group in inventory["groups"].values():
        for server in group.get("servers", []):
            if server.get("key") == TARGET_SERVER:
                server["env"]["NATS_ROSTER_DRIFT_PROBE"] = "${NATS_ROSTER_DRIFT_PROBE}"
                break
        else:
            continue
        break
    else:
        pytest.fail(f"mutation setup failed: {TARGET_SERVER} is not in the inventory")

    dest = tmp_path / "mcp_inventory.json"
    dest.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    ratchet.INVENTORY_PATH = dest

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_the_fleet_roster_still_agrees_with_its_generator()
    assert "drifted from the inventory" in str(excinfo.value), (
        "the ratchet raised, but not with the drift message -- the assertion "
        f"that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_unbalanced_placeholder_is_killed(tmp_path: Path) -> None:
    """An UNBALANCED reference MUST fail the malformed-reference rule.

    Codex finding 4631230891: the filter used to require a CLOSING brace, so
    `${BROKEN` was discarded and the ratchet passed -- while the normalizer
    still degraded the server, because it records the literal text it could
    not close. An unbalanced reference is exactly as unsatisfiable as a
    malformed one, so the hole left the class half-unprotected.
    """
    ratchet = _load_ratchet()

    def _set_unbalanced(server: Dict[str, Any]) -> None:
        env = server.get("env")
        if not isinstance(env, dict):
            env = {}
            server["env"] = env
        env["NATS_BROKEN_PROBE"] = UNBALANCED

    mutated = _mutated_roster(tmp_path, _set_unbalanced)
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_no_env_value_carries_a_malformed_reference()
    assert "can never resolve" in str(excinfo.value), (
        "the ratchet raised, but not with the malformed-reference message -- "
        f"the assertion that should have fired changed shape: {excinfo.value!r}"
    )
    assert UNBALANCED in str(excinfo.value), (
        "the ratchet fired, but did not name the unbalanced reference -- "
        f"the assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_missing_generated_server_is_killed(tmp_path: Path) -> None:
    """A generated server ABSENT from the roster MUST fail the ratchet.

    Codex finding 4631230905: the absence branch used to `continue`, so an
    inventory addition -- or an accidental deletion from the roster -- was
    invisible. The field-by-field comparison has nothing to compare when the
    entry is not there at all.
    """
    ratchet = _load_ratchet()
    inventory = json.loads(ratchet.INVENTORY_PATH.read_text(encoding="utf-8"))
    placed = False
    for group in inventory["groups"].values():
        for server in group.get("servers", []):
            if server.get("key") == TARGET_SERVER:
                probe = dict(server)
                probe["key"] = ABSENT_PROBE_KEY
                group["servers"].append(probe)
                placed = True
                break
        if placed:
            break
    if not placed:
        pytest.fail(f"mutation setup failed: {TARGET_SERVER} is not in the inventory")

    dest = tmp_path / "mcp_inventory.json"
    dest.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    ratchet.INVENTORY_PATH = dest

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_the_fleet_roster_still_agrees_with_its_generator()
    assert "MISSING a server the inventory declares" in str(excinfo.value), (
        "the ratchet raised, but not with the missing-server message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )
    assert ABSENT_PROBE_KEY in str(excinfo.value), (
        "the ratchet fired, but did not name the missing server -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_stale_absence_record_is_killed(tmp_path: Path) -> None:
    """A recorded absence that BECOMES rostered MUST fail the ratchet.

    The other direction of the absence record. Without it, the record of
    measured reasons could go stale and keep claiming a server is missing
    when it is not -- and a ratchet nobody trusts is decoration.

    The roster entry is inserted VERBATIM from the generator, so the only
    thing that can fail here is the stale record: the field-by-field drift
    check must stay silent.
    """
    from pmoves.tools import mcp_config_generator as gen

    ratchet = _load_ratchet()
    inventory = gen.load_inventory(ratchet.INVENTORY_PATH)
    generated = gen.generate_for_client(
        "claude", inventory=inventory, endpoint="fleet", allow_os_environ=False
    )
    entry = generated.get("mcpServers", {}).get(RECORDED_ABSENT_SERVER)
    if not isinstance(entry, dict):
        pytest.fail(
            "mutation setup failed: the generator does not emit "
            f"{RECORDED_ABSENT_SERVER}"
        )

    def _add_server(raw: Dict[str, Any]) -> None:
        raw["mcpServers"][RECORDED_ABSENT_SERVER] = entry

    mutated = _mutated_roster_raw(tmp_path, _add_server)
    ratchet.ROSTER_PATH = mutated

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_the_fleet_roster_still_agrees_with_its_generator()
    assert "has gone stale" in str(excinfo.value), (
        "the ratchet raised, but not with the stale-record message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )
    assert RECORDED_ABSENT_SERVER in str(excinfo.value), (
        "the ratchet fired, but did not name the server whose record went "
        f"stale -- the assertion that should have fired changed shape: "
        f"{excinfo.value!r}"
    )
