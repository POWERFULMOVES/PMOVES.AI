"""The lineage edges the claim register cannot express, and the gate on them.

331 entries, 49 author strings, ~13 identities. Three distinct repairs have all
been performed by editing history in place, because the ledger has no field for
any of them: attribution correction, key drift, and succession.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _module():
    path = REPO_ROOT / "pmoves" / "tools" / "identity_lineage.py"
    spec = importlib.util.spec_from_file_location("identity_lineage", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["identity_lineage"] = module
    spec.loader.exec_module(module)
    return module


il = _module()


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def test_the_register_is_clean():
    findings = il.verify()
    assert findings == [], "\n".join(findings)


def test_the_gate_fails_on_an_undeclared_author():
    """Proven by running the gate's own detection, not a lookup in isolation."""
    entries = il.register_entries() + [
        ("2026-08-25T23:59:00Z", "CLAIM", "SOME-NEW-AGENT (opus 9)")
    ]
    missing = il.undeclared_authors(entries)
    assert missing == {"SOME-NEW-AGENT (opus 9)": 1}


def test_the_gate_fails_on_a_prose_only_correction(tmp_path, monkeypatch):
    """A `[CORRECTION ...]` with no structured record must be a finding.

    This is the specific thing that let the workaround become house style: the
    annotation looks like a record, so nobody noticed the original author was
    only recoverable from git.
    """
    fake = tmp_path / "register.md"
    fake.write_text(
        "- `2026-01-01T00:00:00Z` CLAIM `4090-CLAUDE` scope: work. "
        "[CORRECTION 2026-01-02: attributed to someone else]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(il, "REGISTER_PATH", fake)
    findings = il.verify()
    assert any("has no record" in f for f in findings), findings


def test_a_succession_without_evidence_is_a_finding():
    """An unevidenced lineage edge is a guess with a schema."""
    vocab = il.load_vocabulary()
    vocab.successions = [{"from": "z890-claude", "to": "5090-claude"}]
    findings = il.verify(vocab)
    assert any("cites no evidence" in f for f in findings), findings


def test_a_succession_to_an_undeclared_identity_is_a_finding():
    vocab = il.load_vocabulary()
    vocab.successions = [
        {"from": "z890-claude", "to": "nobody-claude", "evidence": "x"}
    ]
    findings = il.verify(vocab)
    assert any("nobody-claude" in f for f in findings), findings


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def test_the_parenthetical_does_not_create_a_new_identity():
    """The drift that broke the collision hook (#2734).

    B850 appears under four spellings; two of them did not collide with each
    other, so a lane stayed open for a week. A model or lane in the
    parenthetical must not make a stranger of a known identity.
    """
    for spelling in [
        "B850-CLAUDE (Knuckles)",
        "B850-CLAUDE (Knuckles, opus 4.7 1M)",
        "B850-CLAUDE (Claude Opus 5)",
        "B850-CLAUDE (Opus 5)",
        "B850-CLAUDE (a model that does not exist yet)",
    ]:
        assert il.canonical_identity(spelling) == "b850-claude", spelling


def test_my_own_lane_resolves_across_all_nine_spellings():
    """Recorded because the author of this file is not an observer here --
    4090 has the widest drift of any identity in the register."""
    for spelling in [
        "4090-CLAUDE", "4090-claude (field)", "4090-CLAUDE (opus 4.8)",
        "4090-CLAUDE (Sonnet 4.6)", "4090-CLAUDE (field)",
        "4090-claude (field, voice-binding lane)",
        "4090-CLAUDE (pr-trim, opus-5)",
    ]:
        assert il.canonical_identity(spelling) == "4090-claude", spelling


def test_both_arrow_forms_normalise_to_one_key():
    """The register uses a unicode arrow; anything typed later will use ASCII."""
    assert (il.canonical_identity("Z890→5090-CLAUDE (opus 4.7 1M)")
            == il.canonical_identity("Z890->5090-CLAUDE"))


def test_an_alias_may_name_only_one_identity():
    doc = {"identities": [
        {"canonical": "a", "aliases": ["shared"]},
        {"canonical": "b", "aliases": ["shared"]},
    ]}
    path = REPO_ROOT / "pmoves" / "tests" / "_tmp_identity_vocab.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="claimed by both"):
            il.load_vocabulary(path)
    finally:
        path.unlink()


# --------------------------------------------------------------------------
# Corrections preserve what the rewrite destroyed
# --------------------------------------------------------------------------

CORRECTED = ("2026-03-19T22:00:00Z", "CLAIM")


def test_a_corrected_entry_names_both_authors():
    """The register line now says B850 and nothing in it says it ever said
    Z890. Resolution must surface both, or the repair is still laundered."""
    identity, why = il.resolve_author(*CORRECTED, "B850-CLAUDE (Knuckles)")
    assert identity == "b850-claude"
    assert "Z890-CLAUDE" in why, why
    assert "d85b46961" in why, "the correction cites no recoverable evidence"


def test_every_correction_preserves_the_original_string():
    vocab = il.load_vocabulary()
    assert vocab.corrections, "no corrections recorded"
    for record in vocab.corrections:
        assert record.get("recorded_as"), record
        assert record.get("evidence"), record


def test_all_seven_annotated_corrections_are_recorded():
    """Seven, not six. The seventh is B850's own from 2026-08-25 and is a
    different class -- key drift, not misattribution."""
    annotated = il.annotated_corrections()
    assert len(annotated) == 7, [a[:2] for a in annotated]
    for timestamp, kind, _ in annotated:
        assert il.correction_for(timestamp, kind) is not None, (timestamp, kind)


def test_the_six_reattributions_are_not_recorded_as_succession():
    """They were MIS-SIGNED, not handed over.

    Recording them as `z890-claude -> b850-claude` would assert that z890 did
    the work and passed it on. It never did the work. Encoding a false history
    in the field built to fix false history would be the worst outcome here.
    """
    vocab = il.load_vocabulary()
    for record in vocab.successions:
        assert not (record.get("from") == "z890-claude"
                    and record.get("to") == "b850-claude"), record


# --------------------------------------------------------------------------
# Succession -- the edge that did not exist
# --------------------------------------------------------------------------

def test_the_arrow_in_the_data_has_a_structured_form_now():
    edges = il.successors("z890-claude")
    assert edges, "the Z890->5090 handover is not expressible"
    assert any("5090-claude" == e["to"] for e in edges)
    assert edges[0].get("confidence"), (
        "an edge inferred from a naming convention must say so"
    )


def test_predecessors_is_the_inverse():
    assert any(e["from"] == "z890-claude" for e in il.predecessors("5090-claude"))


# --------------------------------------------------------------------------
# Ambiguity is reported, never resolved by guessing
# --------------------------------------------------------------------------

def test_the_doctrinal_ambiguity_is_flagged_not_folded():
    """`CLAUDE-OPUS-5` and `4090-CLAUDE-OPUS-5` sit between two conventions:
    `claude-opus` is declared portable, `4090-claude` is node-named. Folding
    either way silently decides preflight Q1."""
    identity, why = il.resolve_author(
        "2026-08-01T00:00:00Z", "CLAIM", "CLAUDE-OPUS-5")
    assert "AMBIGUOUS" in why
    assert identity not in ("claude-opus", "4090-claude")


def test_the_succession_marker_is_not_collapsed_to_an_endpoint():
    identity, why = il.resolve_author(
        "2026-07-20T00:00:00Z", "CLAIM", "Z890→5090-CLAUDE (opus 4.7 1M)")
    assert "AMBIGUOUS" in why
    assert identity not in ("z890-claude", "5090-claude"), (
        "collapsing the arrow destroys the only record that a handover happened"
    )


# --------------------------------------------------------------------------
# The register cannot be audited with grep
# --------------------------------------------------------------------------

def test_the_register_needs_a_tolerant_reader():
    """It contains a NUL byte, so `grep` calls it binary and stops printing
    after the first match. Any grep-based audit of this file is silently
    truncated -- which is why the reader is centralised here."""
    raw = il.REGISTER_PATH.read_bytes()
    assert b"\x00" in raw, (
        "the NUL is gone -- if the file was cleaned, this test and the warning "
        "in read_register() should go with it"
    )
    text = il.read_register()
    assert len(il.register_entries(text)) > 300
