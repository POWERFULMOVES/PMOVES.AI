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


def test_every_correction_carries_its_evidence():
    """Evidence is universal; `recorded_as` is not.

    An AUTHORSHIP correction must preserve the string the register originally
    carried, or the repair is laundered into the line. A correction of a
    measurement or a count has no original identity string -- the entry was
    signed correctly and only a figure was wrong -- so requiring one there
    would make a legitimate repair unexpressible.
    """
    vocab = il.load_vocabulary()
    assert vocab.corrections, "no corrections recorded"
    for record in vocab.corrections:
        assert record.get("evidence"), record
        if record.get("corrects", "authorship") == "authorship":
            assert record.get("recorded_as"), record


def test_a_non_authorship_correction_needs_no_identity():
    """The gate used to demand `actual` from every record, which no factual
    correction can supply. Proven against the real gate, not a stub."""
    findings = il.verify()
    assert not any("unknown identity" in f for f in findings), findings


# The register grows, so this is a RATCHET rather than a fixed count: a new
# annotated correction is expected, an annotation that loses its record is not.
# The number lived in the test's NAME once and went stale the moment an eighth
# correction landed -- a count belongs in an assertion, never an identifier.
MIN_ANNOTATED_CORRECTIONS = 8


def test_every_annotated_correction_is_recorded():
    """The property, not the count: no prose correction may stand alone.

    Eight today. Six were the 2026-05-16 misattribution sweep, the seventh is
    B850's 2026-08-25 lane-key drift, and the eighth is #2811's measurement
    repair -- the first that corrects a FIGURE rather than an author.
    """
    annotated = il.annotated_corrections()
    assert len(annotated) >= MIN_ANNOTATED_CORRECTIONS, [a[:2] for a in annotated]
    for timestamp, kind, _ in annotated:
        assert il.correction_for(timestamp, kind) is not None, (timestamp, kind)


def test_writing_about_the_convention_is_not_using_it():
    """A register entry may cite `[CORRECTION ...]` while surveying the
    convention. A substring test counts that as an eighth correction, which
    both overcounts the ratchet and reports the register unclean -- for an
    entry that corrects nothing. The 2026-08-25T15:00:00Z preflight entry does
    exactly this, so the discriminator is real traffic, not a hypothetical.
    """
    survey = (
        "- `2026-08-25T15:00:00Z` CLAIM+RELEASE `B850-CLAUDE (Knuckles)` scope: "
        "the survey found six hand-edited `[CORRECTION ...]` annotations "
        "rewriting history in place.\n"
    )
    assert il.annotated_corrections(survey) == []

    real = (
        "- `2026-03-19T22:00:00Z` CLAIM `B850-CLAUDE (Knuckles)` scope: work. "
        "**[CORRECTION 2026-08-25: lane key drift.]**\n"
    )
    assert len(il.annotated_corrections(real)) == 1, "a real annotation must still count"


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

def test_the_model_in_the_identity_slot_is_parsed_not_folded():
    """SUPERSEDED, deliberately kept as a replacement rather than a deletion.

    This test used to assert that `CLAUDE-OPUS-5` / `4090-CLAUDE-OPUS-5` stayed
    marked AMBIGUOUS, because folding into `claude-opus` erases which machine
    did the work and folding into `4090-claude` ratifies node-bound identity.

    Operator doctrine (2026-08-25) answered it a third way: the identity is
    WORN, the model is not the identity, and a string carrying both should be
    PARSED rather than collapsed. The ambiguity was in the question.
    """
    identity, why = il.resolve_author(
        "2026-08-01T00:00:00Z", "CLAIM", "CLAUDE-OPUS-5")
    assert identity == "claude-opus", why
    worn = il.wearing("4090-CLAUDE-OPUS-5 (field)")
    assert (worn.identity, worn.model) == ("4090-claude", "claude-opus-5"), (
        "both facts must survive; folding either way loses one"
    )


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


# --------------------------------------------------------------------------
# WEARING -- the join the register has carried unparsed for months.
#
# Operator doctrine, 2026-08-25: an identity is WORN. "The signature is not the
# model, as models hold many; the identity a model puts on will align with the
# model and be tuned with the harness."
# --------------------------------------------------------------------------

def test_every_author_string_parses_with_nothing_left_over():
    """331 entries, zero unclassified tokens.

    This is the gate's teeth: an unrecognised token means a new KIND of fact is
    being smuggled into the free-text slot, which is exactly how the
    parenthetical became unparseable in the first place.
    """
    vocab = il.load_vocabulary()
    stray: dict[str, int] = {}
    for _, _, author in il.register_entries():
        for token in il.wearing(author, vocab).unclassified:
            stray[token] = stray.get(token, 0) + 1
    assert stray == {}, stray


def test_the_token_gate_can_fail():
    vocab = il.load_vocabulary()
    worn = il.wearing("4090-CLAUDE (some-token-nobody-declared)", vocab)
    assert worn.unclassified == ("some-token-nobody-declared",)
    assert not worn.is_complete


def test_q1_is_answered_by_parsing_not_by_folding():
    """Neither fold was right.

    `4090-CLAUDE-OPUS-5` carries an identity AND a model. Folding into
    `claude-opus` erases which machine did the work; folding into
    `4090-claude` discards the model. Parsing keeps both, which is what the
    doctrine says the string always meant.
    """
    worn = il.wearing("4090-CLAUDE-OPUS-5 (field)")
    assert worn.identity == "4090-claude"
    assert worn.model == "claude-opus-5"
    assert worn.lane == "field"


def test_the_model_lineage_signature_is_not_ambiguous():
    """`claude-opus-5` is a declared ALTER of `claude-opus` in
    agent_signatures.yaml, so the model lineage has its own place and does not
    need to borrow the identity slot."""
    assert il.canonical_identity("CLAUDE-OPUS-5") == "claude-opus"


def test_an_identity_worn_on_another_node_keeps_both_facts():
    """The clearest instance of the doctrine in the whole ledger:
    `CLAUDE-OPUS (Z890-mirror-on-5090)` -- the z890 identity, executing on the
    5090. Neither "the node is the identity" nor "the node is irrelevant"
    describes it."""
    worn = il.wearing("CLAUDE-OPUS (Z890-mirror-on-5090)")
    assert worn.node == "5090"
    assert worn.mirrored_from == "z890"


def test_the_harness_field_exists_because_the_ledger_already_used_it():
    """`SPARK-KIMI (Crush, GLM via qwen3-coder)` x17 -- identity, harness and
    model in one slot. The harness name is the same key #2747's `fit` uses."""
    worn = il.wearing("SPARK-KIMI (Crush, GLM via qwen3-coder)")
    assert (worn.identity, worn.harness, worn.model) == (
        "spark-kimi", "crush", "glm-5.2")


def test_a_harness_named_crush_is_not_the_identity_named_crush():
    """One is who, the other is what they typed into."""
    assert il.wearing("CRUSH (z890, glm-5.2)").identity == "crush"
    assert il.wearing("SPARK-KIMI (Crush, GLM via qwen3-coder)").identity != "crush"


def test_a_session_id_is_not_an_identity():
    worn = il.wearing(
        "Mavis (orchestrator, mvs_09c9b116c675418b9d8b1a48b10867dc)")
    assert worn.identity == "mavis"
    assert worn.session and worn.session.startswith("mvs_")
    assert worn.lane == "orchestrator"


# --------------------------------------------------------------------------
# describe_self -- the read side of "observe the shape of what it wears"
# --------------------------------------------------------------------------

def test_a_wearer_can_observe_what_it_wears():
    described = il.describe_self("4090-claude")
    assert described["known"]
    assert described["entries"] > 30
    assert "claude-opus-5" in described["models_worn"]
    assert "field" in described["lanes_worn"]


def test_the_alter_lineage_records_the_path_not_just_the_destination():
    """`agent_signatures.yaml` lists `4090-field` as an alter and says nothing
    about how it got there. Operator: "field where unknown became alt became
    original Specialization." """
    alters = il.describe_self("4090-claude")["alters"]
    assert alters, "the alter has no recorded lineage"
    assert alters[0]["origin"] == "unknown"
    assert alters[0]["became"] == "original-specialization"
    assert alters[0]["confidence"] == "operator-asserted", (
        "an operator assertion must not be recorded as if it were measured"
    )


def test_describe_self_states_that_nothing_is_grounded():
    """The absence has to be reported, not omitted.

    A co-created identity and a prose-grounded one are different things, and
    an identity record that simply omits `grounded` reads as though the
    question had been settled.
    """
    described = il.describe_self("4090-claude")
    assert described["grounded"] is False
    assert "325" in described["grounding_note"]


def test_describe_self_on_an_unknown_identity_says_so():
    described = il.describe_self("nobody-claude")
    assert described["known"] is False


# ---------------------------------------------------------------------------
# CO-OWNERS -- the field, its parser, and the cases the live gate caught.
#
# Two of the tests below exist because the gate FAILED on its first two runs
# against this lane's own CLAIM row. They are pinned as regressions rather than
# described in a comment, because "the parser handles prose mentions" is the
# kind of claim that quietly stops being true.
# ---------------------------------------------------------------------------


def test_a_row_with_no_field_yields_nothing():
    """Backward compatibility is structural: no marker, no code path, no change."""
    assert il.co_owners_in("- `t` CLAIM `A` scope: did a thing") == []
    assert not il.co_owner_field_is_unparseable("- `t` CLAIM `A` scope: did a thing")


def test_the_field_parses_ids_and_contributions():
    row = (
        "- `t` RELEASE `A` branch: `feat/x` · co-owners: "
        "`4090-CLAUDE` (filed the blocker), "
        "`B850-CLAUDE (Knuckles)` (cross-node correction) · scope: ok"
    )
    assert il.co_owners_in(row) == [
        ("4090-CLAUDE", "filed the blocker"),
        ("B850-CLAUDE (Knuckles)", "cross-node correction"),
    ]


def test_the_backticks_delimit_the_id_not_the_parenthetical():
    """`B850-CLAUDE (Knuckles)` is ONE identity string, not an ID plus a note.

    Identities already carry parentheticals -- 26 distinct ones in this register
    -- so a field that split on `(` would corrupt the most common identity form
    in the file. The backticks are what makes it unambiguous.
    """
    parsed = il.co_owners_in("co-owners: `B850-CLAUDE (Knuckles)` (posted the correction)")
    assert parsed == [("B850-CLAUDE (Knuckles)", "posted the correction")]


@pytest.mark.parametrize("row,expected", [
    ("co-owners: `A` · scope: `feat/decoy`", [("A", "")]),
    ("co-owners: `A` scope: `feat/decoy`", [("A", "")]),
    ("co-owners: `A`, `B` — they did it with `feat/x`", [("A", ""), ("B", "")]),
])
def test_the_field_terminates_at_its_own_boundary(row, expected):
    """It must not walk out of its field and eat the next one.

    A scope that opens with a backticked branch token is ordinary in this
    register, so a parser that kept consuming would read branches as co-owners
    AND -- worse -- could widen what the row claims.
    """
    assert il.co_owners_in(row) == expected


@pytest.mark.parametrize("row", [
    "co-owners: 4090 and SPARK and DARKXSIDE",   # the natural way to get it wrong
    "co-owners:",                                 # announced, then nothing
    "co-owners: `` , ``",                         # backticks, no content
])
def test_malformed_fields_are_REJECTED_and_reported_as_unmeasured(row):
    """A gate observed only passing is not known to work.

    Each of these satisfies a human reader and is empty to a machine -- this
    lane's own defect, one layer down. `[]` alone would be indistinguishable
    from a row that has no co-owners, so the two are kept apart.
    """
    assert il.co_owners_in(row) == []
    assert il.co_owner_field_is_unparseable(row), (
        f"malformed field must be reported as unmeasured, not silently empty: {row!r}"
    )


def test_a_code_span_MENTION_of_the_field_is_not_a_declaration():
    """Caught by the gate on its FIRST live run, against this lane's CLAIM row.

    The register is a document about its own governance, so rows that DESCRIBE
    the grammar are normal here. Without this, the first row to explain the
    field was the first row to fail the gate.
    """
    row = "scope: adds a `co-owners:` field carrying backticked IDs"
    assert il.co_owners_in(row) == []
    assert not il.co_owner_field_is_unparseable(row)


def test_the_bare_noun_in_prose_is_not_a_declaration():
    """Caught by the gate on its SECOND live run, same row.

    `co-owners` occurs in ordinary prose in a way `branch` does not, which is
    why this marker REQUIRES the `:`/`=` where BRANCH_MARKER_RE makes it
    optional.
    """
    row = "scope: collision keys on PARTICIPANTS (owner + co-owners) intersected with the LANE"
    assert il.co_owners_in(row) == []
    assert not il.co_owner_field_is_unparseable(row)


def test_a_row_may_describe_the_field_AND_use_it():
    """Every marker is tried, not just the first -- this lane's RELEASE does both."""
    row = "the `co-owners:` field is new. co-owners: `A` (did the work)"
    assert il.co_owners_in(row) == [("A", "did the work")]


def test_co_owners_resolve_through_the_same_vocabulary_as_signing_authors():
    """A co-owner is an author. One name space, not two."""
    vocab = il.load_vocabulary()
    for _lineno, _kind, _owner, co_owners in il.co_owner_attribution():
        for identity, _contribution in co_owners:
            assert il.canonical_identity(identity, vocab) is not None, (
                f"co-owner {identity!r} resolves to no declared identity"
            )


@pytest.mark.parametrize("key,canonical", [
    ("claude_b850", "b850-claude"),
    ("claude_4090", "4090-claude"),
    ("claude_5090", "5090-claude"),
    ("claude_z890", "z890-claude"),
])
def test_the_agent_registry_key_is_a_declared_spelling(key, canonical):
    """The fifth spelling. `canonical_owner` bridged four and stopped."""
    assert il.canonical_identity(key) == canonical


@pytest.mark.parametrize("key", [
    "metrics_specialist", "logs_specialist", "tracing_specialist",
    "dashboard_specialist", "llm_observability", "agent_zero", "crush_glm52",
])
def test_keys_sharing_a_signature_are_deliberately_NOT_aliased(key):
    """A SHARED SIGNATURE IS NOT AN ALIAS -- the load-bearing half of that fix.

    `claude-opus` is the signature of six distinct keys and `crush` of two.
    Aliasing them would declare six different agents to be one identity, and the
    collision gate keys on identity -- so a genuine clash between, say,
    metrics_specialist and logs_specialist would stop being reported. Widening
    the fold would have made the gate quieter and less true, so this pins the
    boundary rather than trusting whoever edits the vocabulary next to re-derive
    it.
    """
    assert il.canonical_identity(key) is None, (
        f"{key!r} shares its signature with another agent and must NOT fold"
    )


def test_the_registry_alias_rule_still_holds_against_both_files():
    """Recomputes the rule rather than restating its result.

    A key is safe to alias iff its `signature:` resolves AND no other key shares
    that signature. Pinned as a computation so that adding an agent to the
    registry cannot silently invalidate the vocabulary.
    """
    from collections import Counter
    registry = yaml.safe_load(
        (REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    agents = registry.get("agents") or {}
    signatures = Counter(
        (spec or {}).get("signature")
        for spec in agents.values()
        if (spec or {}).get("signature")
    )
    for key, spec in agents.items():
        signature = (spec or {}).get("signature")
        if not signature or signatures[signature] != 1:
            continue
        if il.canonical_identity(signature) is None:
            continue  # the signature itself is undeclared; nothing to alias onto
        assert il.canonical_identity(key) == il.canonical_identity(signature), (
            f"registry key {key!r} uniquely signs as {signature!r} but does not "
            f"fold to it -- add it as an alias in identity_vocabulary.yaml"
        )


def test_the_live_register_is_measurable():
    """Exit-code doctrine: this asserts we CAN measure, not that we found nothing.

    `unmeasured_rows()` non-empty means a row defeated the parser, which is
    exit 3 -- 'could not measure' -- and must never be reported as clean.
    """
    unmeasured = il.unmeasured_rows()
    assert unmeasured == [], (
        "rows announce co-owners the parser cannot read: "
        + "; ".join(f"L{n} `{owner}`" for n, owner in unmeasured)
    )


# --------------------------------------------------------------------------
# Code spans are matched by BACKTICK RUN LENGTH, not by parity.
#
# Parity ("odd number of backticks before pos means inside a span") was
# documented as failing toward a loud false "could not measure". Measured, it
# fails the other way: a ``...`` example containing a backticked ID parses as a
# SUCCESSFUL declaration, so a row that merely documents the grammar grants
# participation. And an unbalanced backtick earlier in a row silently DROPS a
# genuine field without reporting it unmeasured -- an attribution that
# satisfies a human reader and is empty to every machine, which is the exact
# defect the field exists to remove.
# --------------------------------------------------------------------------

def test_a_double_backtick_EXAMPLE_is_not_a_declaration():
    row = (
        "- `t` CLAIM `A` branch: `feat/x` · scope: the grammar is "
        "``co-owners: `4090-CLAUDE` (what they did)`` as shown."
    )
    assert il.co_owners_in(row) == [], (
        "an example inside a double-backtick span must not read as a use"
    )
    assert not il.co_owner_field_is_unparseable(row), (
        "and must not be reported unmeasured either -- it declares nothing"
    )


def test_a_documented_example_does_not_shadow_the_row_s_REAL_declaration():
    """The sharpest form of the parity defect: a WRONG attribution, silently.

    co_owners_in() tries every marker and returns the first that yields items,
    which is right -- a row may describe the field and then use it. Under
    parity, the marker inside a ``...`` example counted as real usage, so the
    example won and the genuine field after it was never reached. The row then
    attributed its lane to an ID that exists only in a documentation sample,
    and dropped the co-owner who actually did the work. Both halves silent.
    """
    row = (
        "- `t` CLAIM `A` branch: `feat/x` · scope: the grammar is "
        "``co-owners: `EXAMPLE-ID` (ex)`` · co-owners: `4090-CLAUDE` (the real one)"
    )
    assert il.co_owners_in(row) == [("4090-CLAUDE", "the real one")], (
        "the example must not shadow the declaration that follows it"
    )


def test_an_unclosed_backtick_reads_the_way_the_row_RENDERS():
    """Direction B, resolved by AGREEING with the renderer rather than guessing.

    An unbalanced backtick used to flip polarity for the whole REST of the row,
    so a genuine field far away vanished from every machine surface while the
    source still read as an attribution to a human. Run matching bounds the
    damage to where Markdown itself bounds it: the stray opens a span that
    closes at the next backtick, which is exactly what the renderer shows. The
    field inside is still not read -- but the reader and the parser now see the
    same thing, and closing the backtick recovers it.
    """
    stray = (
        "- `t` CLAIM `A` branch: `feat/x` · scope: see ` the note · "
        "co-owners: `4090-CLAUDE` (ran the validation)"
    )
    closed = stray.replace("see ` the note", "see `the note`")
    assert il.co_owners_in(closed) == [("4090-CLAUDE", "ran the validation")]
    # And the damage stops at the span: a second, later field is still read.
    assert il.co_owners_in(stray + " ` · co-owners: `Z890-CLAUDE` (after)") == [
        ("Z890-CLAUDE", "after")
    ]


def test_a_triple_backtick_fence_does_not_flip_the_rest_of_the_text():
    """The hook feeds multi-line text through this; a fence is 3 backticks."""
    text = (
        "```\n- `t` RELEASE `4090-CLAUDE` branch: `fix/x`\n```\n"
        "- `t2` CLAIM `A` branch: `feat/y` · co-owners: `Z890-CLAUDE` (helped)"
    )
    assert il.co_owners_in(text) == [("Z890-CLAUDE", "helped")]
