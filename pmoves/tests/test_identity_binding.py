"""The binding between the PMOVES identity vocabulary and Spynel's prefix slots.

`pmoves/docs/AGENTS/IDENTITY_BINDING.md` says one load-bearing thing: the Spynel
`harness.*_agent_prefix` slots declare NO identity. They are harness-native
command prefixes (`/goal`, `/ultrathink`) that Spynel joins to the prompt, so
the PMOVES vocabulary is the only surface that declares who an agent is.

The drift this exists to stop is a reader taking the slot name at face value and
filling `developer_agent_prefix` with a register identity -- say `SPARK-CLAUDE`.
That string would be injected into the PROMPT, never into the register, and no
existing gate would see it: `test_identity_lineage.py` reads the register, and
the register would be unchanged.

DELIBERATELY NARROW. `identity_vocabulary.yaml` is append-only by design
(`pmoves/config/identity_vocabulary.yaml:37-40`), so nothing here may key on the
vocabulary's CONTENTS or SIZE -- a test that did would fail on the next
legitimate append. It asserts only what the doc claims, and
`test_appending_an_identity_does_not_break_the_binding` proves that by running
the same assertions against a vocabulary with an extra identity in it.

Static: reads two files and resolves strings. No Spynel process, no network.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / ".spynel" / "config.yaml"
BINDING_DOC = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "IDENTITY_BINDING.md"
VOCABULARY = REPO_ROOT / "pmoves" / "config" / "identity_vocabulary.yaml"

# A slot counts as DOCUMENTED only from its row in the doc's slot table, which
# pairs the name with the `.spynel/config.yaml` line that defines it. Matching
# the bare name anywhere in the prose would count the paragraph that records
# `notification_agent_prefix` as deliberately ABSENT as if it documented a
# present slot -- inverting the check.
DOCUMENTED_SLOT = re.compile(
    r"^\|\s*`([a-z]+_agent_prefix)`\s*\|\s*`\.spynel/config\.yaml:", re.MULTILINE
)
ABSENT_SLOT = "notification_agent_prefix"


def _module():
    path = REPO_ROOT / "pmoves" / "tools" / "identity_lineage.py"
    spec = importlib.util.spec_from_file_location("identity_lineage", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["identity_lineage"] = module
    spec.loader.exec_module(module)
    return module


il = _module()


def _harness() -> dict:
    """The `harness:` mapping, or skip.

    `.spynel/config.yaml` is private per-workspace state and is not tracked, so
    it is absent in CI and on a fresh clone. Skipping is correct there: the
    binding cannot drift on a node that has no Spynel config.
    """
    if not CONFIG.exists():
        pytest.skip(f"{CONFIG} absent -- no Spynel config on this node")
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    harness = doc.get("harness")
    if not isinstance(harness, dict):
        pytest.skip(f"{CONFIG} has no `harness:` mapping")
    return harness


def _configured_slots(harness: dict) -> set[str]:
    return {k for k in harness if k.endswith("_agent_prefix")}


def _documented_slots() -> set[str]:
    return set(DOCUMENTED_SLOT.findall(BINDING_DOC.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def test_the_binding_doc_lists_exactly_the_configured_prefix_slots():
    """A slot the doc does not name is a slot nobody decided the meaning of.

    This is the one that fires when `notification_agent_prefix` is finally
    added: the doc records its absence as a deliberate asymmetry, so adding it
    must be accompanied by a decision written down, not a silent config edit.
    """
    configured = _configured_slots(_harness())
    documented = _documented_slots()
    assert configured == documented, (
        f"{CONFIG} and {BINDING_DOC.name} disagree on the prefix slots.\n"
        f"  configured but undocumented: {sorted(configured - documented)}\n"
        f"  documented but unconfigured: {sorted(documented - configured)}"
    )


def test_the_doc_still_records_the_absent_notification_slot():
    """The asymmetry is a recorded decision; deleting the note is drift too."""
    text = BINDING_DOC.read_text(encoding="utf-8")
    assert ABSENT_SLOT in text, (
        f"{BINDING_DOC.name} no longer names {ABSENT_SLOT}. Five roles exist "
        "under .spynel/instructions/ and four prefix slots are configured; "
        "that gap is recorded on purpose."
    )
    assert ABSENT_SLOT not in _configured_slots(_harness()), (
        f"{ABSENT_SLOT} is now configured -- give it a row in the slot table "
        f"of {BINDING_DOC.name} and update the asymmetry note."
    )


def test_no_prefix_slot_holds_a_register_identity():
    """The binding itself: a prefix slot is a command, never an identity."""
    _assert_slots_carry_no_identity(_harness())


def test_appending_an_identity_does_not_break_the_binding(tmp_path, monkeypatch):
    """Proof the assertion above is append-safe, not merely narrow-looking.

    Runs the real assertion against a vocabulary carrying one identity more
    than the live file. If the gate were keyed on vocabulary contents or size
    this would fail, which is precisely the failure mode the docstring warns
    about.
    """
    doc = yaml.safe_load(VOCABULARY.read_text(encoding="utf-8")) or {}
    doc.setdefault("identities", []).append(
        {"canonical": "append-probe-identity", "aliases": ["APPEND-PROBE-IDENTITY"]}
    )
    widened = tmp_path / "identity_vocabulary.yaml"
    widened.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setenv("PMOVES_IDENTITY_VOCABULARY", str(widened))

    vocab = il.load_vocabulary()
    assert il.canonical_identity("APPEND-PROBE-IDENTITY", vocab) == "append-probe-identity"
    _assert_slots_carry_no_identity(_harness(), vocab=vocab)


def _assert_slots_carry_no_identity(harness: dict, vocab=None) -> None:
    vocab = vocab if vocab is not None else il.load_vocabulary()
    offenders = {}
    for slot in sorted(_configured_slots(harness)):
        value = str(harness.get(slot) or "").strip()
        if not value:
            continue  # the documented empty-slot default: no identity injected
        resolved = il.canonical_identity(value, vocab)
        if resolved is not None:
            offenders[slot] = (value, resolved)
    assert not offenders, (
        "a Spynel prefix slot holds a register identity. Per "
        f"{BINDING_DOC.name}, a prefix is a harness-native command joined to "
        "the PROMPT; an identity placed here never reaches the claim register "
        "and no lineage gate can see it. Use OWNER= on `make -C pmoves "
        "register-claim` instead.\n"
        + "\n".join(
            f"  {slot}: {value!r} resolves to identity {resolved!r}"
            for slot, (value, resolved) in offenders.items()
        )
    )
