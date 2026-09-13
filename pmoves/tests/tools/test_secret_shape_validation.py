"""A secret that is PRESENT BUT CORRUPT must not reach a tier env file silently.

The funnel validated presence, and min_length for a handful of labels. It never
validated CHARSET: ``isascii`` appeared zero times in ``secrets_sync.py`` and
``chit_manifest_register.py``. The defect that opened the gap is measured, not
hypothetical -- ``GATE_API_KEY`` is delivered with an EM DASH (U+2014) inside the
key, and the only reason anyone knows is that a third-party vendor CLI inspected
the value before putting it in an HTTP header and said so in plain language while
our own pipeline stayed silent.

The same family had already cost this fleet weeks once: ``E2B_API_KEY`` arrived 42
characters beginning ``b_`` instead of 44 beginning ``e2b_``, a presence check
passed it, and the E2B Danger Room never ran.

Every value in this file is SYNTHETIC and invented here. No real credential is
read, constructed, or asserted against anywhere in this module -- which is also
what ``test_a_finding_never_contains_the_value`` exists to keep true of the
production code paths.
"""

import pytest

from tools.chit_manifest_register import REGISTRY, RECONCILED_FIELDS, build_entry
from tools.chit_manifest_sync import _build_v1_entry
from tools.secret_shape import (
    LOOKALIKE_SUBSTITUTIONS,
    describe_codepoint,
    inspect_value,
)
from tools.secrets_sync import Entry, Target, build_outputs, load_manifest

# ── Synthetic fixtures. Invented for this test; safe to read aloud. ──────────
EM_DASH = "—"
ZERO_WIDTH = "​"
NBSP = " "

CLEAN = "s3cr3t-synthetic_value.0123456789ABCDEF"
CORRUPT = "Zq7Wx9" + EM_DASH + "Kv3Lm5"          # the observed defect's shape
INVISIBLE = "Ab1" + ZERO_WIDTH + "Cd2"
NON_BREAKING = "Ef3" + NBSP + "Gh4"
DIACRITIC_PASSWORD = "pässw0rd-synthetic"    # plausibly deliberate
E2B_TRUNCATED = "b_" + "0" * 40                   # 42 chars, the delivered shape
E2B_WELL_FORMED = "e2b_" + "0" * 40               # 44 chars, E2B's published shape

FILE = "env.tier-worker"
LABEL = "SYNTHETIC_LABEL"


def _entry(label=LABEL, *, required=False, min_length=0, prefix="") -> Entry:
    return Entry(
        id=label.lower(),
        label=label,
        required=required,
        targets=[Target(file=FILE, key=label)],
        min_length=min_length,
        prefix=prefix,
    )


# ── The non-negotiable invariant: findings never carry secret material ───────


def test_a_finding_never_contains_the_value():
    """Not one two-character run of the value may appear in any finding.

    Adding credential validation that leaks the credential into a log would be a
    worse wound than the defect. A finding may name the VARIABLE, the CODEPOINT,
    the POSITION and the LENGTH -- nothing else. This asserts the negative
    directly rather than trusting the format string to stay disciplined.
    """
    verdict = inspect_value(LABEL, CORRUPT)
    findings = verdict.withhold + verdict.warn
    assert findings, "positive control: this value must produce a finding at all"

    windows = {CORRUPT[i:i + 2] for i in range(len(CORRUPT) - 1)}
    for finding in findings:
        leaked = sorted(w for w in windows if w in finding)
        assert not leaked, f"finding leaks value fragment(s) {leaked}: {finding}"


def test_describe_codepoint_names_the_character_without_printing_it():
    described = describe_codepoint(EM_DASH)
    assert described == "U+2014 EM DASH"
    assert EM_DASH not in described, (
        "the glyph is one character OF THE SECRET; the codepoint already conveys "
        "everything an operator needs to act"
    )


def test_describe_codepoint_survives_an_unnamed_codepoint():
    """unicodedata.name raises for control/unassigned codepoints."""
    assert describe_codepoint("\x01") == "U+0001 (unnamed)"


# ── Positive cases: the corrupt shapes are caught ───────────────────────────


@pytest.mark.parametrize(
    "value,codepoint",
    [(CORRUPT, "U+2014"), (INVISIBLE, "U+200B"), (NON_BREAKING, "U+00A0")],
)
def test_lookalike_substitutions_are_withheld(value, codepoint):
    verdict = inspect_value(LABEL, value)
    assert len(verdict.withhold) == 1
    assert codepoint in verdict.withhold[0]


def test_wrong_vendor_prefix_is_withheld():
    verdict = inspect_value(LABEL, E2B_TRUNCATED, prefix="e2b_")
    assert len(verdict.withhold) == 1
    assert "e2b_" in verdict.withhold[0]


def test_surrounding_whitespace_warns_but_is_still_delivered():
    """`_first_usable` strips only to decide emptiness; it emits the raw value."""
    verdict = inspect_value(LABEL, CLEAN + "  ")
    assert verdict.withhold == []
    assert len(verdict.warn) == 1
    assert "trailing" in verdict.warn[0]


# ── Proportionality: an ordinary non-ASCII character must NOT withhold ──────


def test_a_diacritic_warns_and_is_not_withheld():
    """Several registered labels are human-chosen passwords.

    DASHBOARD_PASSWORD, AP_POSTGRES_PASSWORD, SMTP_PASS and
    JUICEFS_META_PASSWORD may legitimately contain a letter with a diacritic.
    Withholding those would break a node that works today -- a wider blast radius
    than the defect being closed.
    """
    verdict = inspect_value("SYNTHETIC_PASSWORD", DIACRITIC_PASSWORD)
    assert verdict.withhold == []
    assert len(verdict.warn) == 1
    assert "U+00E4 LATIN SMALL LETTER A WITH DIAERESIS" in verdict.warn[0]


# ── Negative control: a well-formed value raises nothing at all ─────────────


@pytest.mark.parametrize("value", [CLEAN, E2B_WELL_FORMED])
def test_a_well_formed_ascii_value_produces_no_finding(value):
    verdict = inspect_value(LABEL, value, prefix="")
    assert verdict.withhold == []
    assert verdict.warn == []


def test_a_well_formed_value_passes_its_own_prefix():
    verdict = inspect_value(LABEL, E2B_WELL_FORMED, prefix="e2b_")
    assert verdict.withhold == []
    assert verdict.warn == []


# ── The table itself ────────────────────────────────────────────────────────


def test_every_table_key_is_a_single_non_ascii_character():
    """An ASCII key would withhold ordinary credentials fleet-wide."""
    offenders = [k for k in LOOKALIKE_SUBSTITUTIONS if len(k) != 1 or k.isascii()]
    assert offenders == [], f"bad table keys: {[hex(ord(k[0])) for k in offenders]}"


def test_the_observed_defect_is_in_the_table():
    assert LOOKALIKE_SUBSTITUTIONS[EM_DASH] == "-"
    assert LOOKALIKE_SUBSTITUTIONS[ZERO_WIDTH] == ""


# ── End to end: the constraint is only real if the funnel acts on it ────────


def test_a_mis_shaped_value_is_withheld_and_removed_end_to_end():
    """Positive control included, so an empty ``outputs`` means "withheld".

    A withheld key must also be REMOVED. The funnel writes in merge mode by
    default (SECRETS_SYNC_FLAGS), and merge PRESERVES keys it is not given, so
    omitting one leaves the previously-emitted corrupt value live for compose.
    Omission is not removal.
    """
    rejected: dict = {}
    outputs, _ = build_outputs(
        {LABEL: CORRUPT}, [_entry()], strict=False, rejected_out=rejected
    )
    assert LABEL not in outputs.get(FILE, {})
    assert LABEL in rejected.get(FILE, set())

    clean_outputs, _ = build_outputs({LABEL: CLEAN}, [_entry()], strict=False)
    assert clean_outputs[FILE][LABEL] == CLEAN


def test_a_required_mis_shaped_value_reports_as_missing():
    """Mirrors the min_length branch: withheld + required means the funnel fails."""
    _, missing = build_outputs(
        {LABEL: CORRUPT}, [_entry(required=True)], strict=False
    )
    assert missing == [LABEL]

    with pytest.raises(KeyError):
        build_outputs({LABEL: CORRUPT}, [_entry(required=True)], strict=True)


def test_the_truncated_e2b_shape_is_withheld_end_to_end():
    entry = _entry("E2B_API_KEY", min_length=40, prefix="e2b_")
    withheld, _ = build_outputs({"E2B_API_KEY": E2B_TRUNCATED}, [entry], strict=False)
    assert "E2B_API_KEY" not in withheld.get(FILE, {})

    emitted, _ = build_outputs({"E2B_API_KEY": E2B_WELL_FORMED}, [entry], strict=False)
    assert emitted[FILE]["E2B_API_KEY"] == E2B_WELL_FORMED


def test_the_funnel_warning_does_not_print_the_value(capsys):
    build_outputs({LABEL: CORRUPT}, [_entry()], strict=False)
    err = capsys.readouterr().err
    assert "U+2014" in err, "positive control: the warning must actually be emitted"
    windows = {CORRUPT[i:i + 2] for i in range(len(CORRUPT) - 1)}
    leaked = sorted(w for w in windows if w in err)
    assert not leaked, f"the funnel warning leaks value fragment(s) {leaked}"


# ── Registration: GATE_API_KEY and E2B_API_KEY ──────────────────────────────


@pytest.mark.parametrize("label", ["GATE_API_KEY", "E2B_API_KEY"])
def test_label_is_registered(label):
    assert label in REGISTRY, (
        f"{label} is consumed at runtime but was absent from the code-level "
        "registry, so the funnel never routed it into any tier file"
    )


def test_gate_api_key_targets_the_tier_its_service_reads():
    entry = build_entry("GATE_API_KEY", REGISTRY["GATE_API_KEY"])
    targets = {(t["file"], t["key"]) for t in entry["targets"] if "file" in t}
    assert ("env.tier-worker", "GATE_API_KEY") in targets


def test_gate_api_key_floor_admits_its_documented_generator_and_rejects_a_fragment():
    """Bracket the floor from both sides rather than restating the number.

    env.shared.example documents `openssl rand -hex 32` -> 64 characters. A floor
    that rejected that would withhold the credential fleet-wide.
    """
    floor = REGISTRY["GATE_API_KEY"]["min_length"]
    assert len("0" * 64) >= floor, "the documented 64-char generator must pass"
    assert len("0" * 16) < floor, "an obvious fragment must fail"


def test_e2b_prefix_reaches_the_emitted_manifest_entry():
    """The registry spec and the emitted YAML are separate surfaces."""
    declared = REGISTRY["E2B_API_KEY"]["prefix"]
    assert declared == "e2b_"
    assert build_entry("E2B_API_KEY", REGISTRY["E2B_API_KEY"])["prefix"] == declared


def test_prefix_reconciles_onto_an_entry_that_already_exists():
    """Otherwise a prefix added to an EXISTING label never lands in the manifest.

    The add-only pass keys on absence, so nothing would report as pending while
    the constraint never reached the YAML the funnel reads -- a gate that cannot
    reach the file it gates.
    """
    assert "prefix" in RECONCILED_FIELDS


def test_no_registry_entry_declares_an_unrecognised_constraint_key():
    """A typo'd key (`prefx`) is a silent no-op: build_entry just ignores it."""
    recognised = {"tier", "required", "aliases", "min_length", "prefix"}
    offenders = {
        label: sorted(set(spec) - recognised)
        for label, spec in REGISTRY.items()
        if set(spec) - recognised
    }
    assert offenders == {}, (
        "unrecognised registry keys are silently dropped by build_entry: "
        f"{offenders}"
    )


# ── The derivation hop, where a constraint is easiest to lose ───────────────


@pytest.mark.parametrize("label", ["GATE_API_KEY", "E2B_API_KEY"])
def test_constraints_survive_the_v2_to_v1_derivation(label):
    """secrets_sync reads the DERIVED v1 manifest, not the v2 registry output.

    `secrets-funnel-sync` derives v1 from v2 and hands the derived file to
    secrets_sync.py, whose --manifest default is the v1 path. Anything
    ``_build_v1_entry`` does not explicitly copy is invisible to load_manifest --
    so a constraint declared in v2 would be enforced by nothing while both files
    looked correct. min_length already carries that comment in
    chit_manifest_sync.py for exactly this reason; `prefix` is the second such
    constraint and would have been dropped the same way.
    """
    v2 = build_entry(label, REGISTRY[label])
    v1 = _build_v1_entry(v2)
    for field in ("min_length", "prefix"):
        assert v1.get(field) == v2.get(field), (
            f"{label}: {field} did not survive the v2 -> v1 derivation, so the "
            "funnel would never see it"
        )


def test_load_manifest_parses_prefix_from_the_yaml(tmp_path):
    """The registry, the YAML and the Entry are three separate surfaces."""
    manifest = tmp_path / "m.yaml"
    manifest.write_text(
        "version: 1\n"
        "cgp_file: pmoves/data/chit/synthetic.json\n"
        "entries:\n"
        "  - id: synthetic_label\n"
        "    source: {type: cgp, label: SYNTHETIC_LABEL}\n"
        "    targets: [{file: env.tier-worker, key: SYNTHETIC_LABEL}]\n"
        "    required: false\n"
        "    prefix: e2b_\n",
        encoding="utf-8",
    )
    _, entries = load_manifest(manifest)
    assert entries[0].prefix == "e2b_"


def test_load_manifest_rejects_a_non_string_prefix(tmp_path):
    manifest = tmp_path / "m.yaml"
    manifest.write_text(
        "version: 1\n"
        "cgp_file: pmoves/data/chit/synthetic.json\n"
        "entries:\n"
        "  - id: synthetic_label\n"
        "    source: {type: cgp, label: SYNTHETIC_LABEL}\n"
        "    targets: [{file: env.tier-worker, key: SYNTHETIC_LABEL}]\n"
        "    prefix: 42\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-string prefix"):
        load_manifest(manifest)
