"""The GitHub App identity behind every signing card must reach env.tier-agent.

Context: ``pmoves/config/signing_identity_cards.yaml`` sets
``ml.primary_method: github-app`` on the agent cards and leaves
``ml.github_app_installation_id`` null, annotated "populated from
GH_APP_INSTALLATION_ID secret at runtime". Nothing was responsible for supplying
it — the label appeared zero times in the code-level REGISTRY — so the CHIT
room-activation checklist resolves on the one node where an operator hand-placed
the value and has nothing to resolve on every node the funnel builds.

These tests pin three things that are each invisible from one end alone:

  * the labels are REGISTERED, and their target file is the one
    ``github_webhook_auto_config.py`` actually opens by name;
  * the constraint is a SHAPE constraint, and it is enforced end to end —
    ``build_outputs`` withholds a truncated id rather than emitting it, which is
    the difference between this and a ``[ -n "$VAR" ]`` presence test;
  * ``GH_APP_SEC`` stays deliberately UNregistered, because a PEM cannot travel
    this pipeline at all (``_drop_multiline``). Absence here is a decision, and
    without a test it reads as the same oversight being fixed.
"""

import pytest

from tools.chit_manifest_register import REGISTRY, build_entry
from tools.secrets_sync import Entry, Target, build_outputs, _drop_multiline

INSTALLATION_ID = "GH_APP_INSTALLATION_ID"
APP_ID = "GH_APP_ID"
PEM_KEY = "GH_APP_SEC"

# The tier file github_webhook_auto_config.py:447 opens by name and reports
# "GH_APP_ID or GH_APP_SEC not found in env.tier-agent" when it cannot find them.
CONSUMER_FILE = "env.tier-agent"


@pytest.mark.parametrize("label", [INSTALLATION_ID, APP_ID])
def test_label_is_registered(label):
    assert label in REGISTRY, (
        f"{label} is read at runtime by the GitHub App token minter and by the "
        "signing cards; unregistered, the funnel never routes it to any node but "
        "the one where it was hand-placed"
    )


@pytest.mark.parametrize("label", [INSTALLATION_ID, APP_ID])
def test_entry_targets_the_file_the_consumer_reads(label):
    entry = build_entry(label, REGISTRY[label])
    targets = {(t["file"], t["key"]) for t in entry["targets"] if "file" in t}
    assert (CONSUMER_FILE, label) in targets, (
        f"{label} must land in {CONSUMER_FILE} — that is the path "
        "github_webhook_auto_config.py opens; any other tier file is a slot "
        "nothing reads"
    )


@pytest.mark.parametrize("label", [INSTALLATION_ID, APP_ID])
def test_entry_carries_a_shape_constraint_not_just_presence(label):
    """min_length is the only measured constraint the registry supports.

    Presence tests accept a truncated value. This asserts the entry declares a
    positive floor AND that ``build_entry`` actually carries it into the emitted
    manifest — the registry spec and the emitted YAML are separate surfaces.
    """
    declared = REGISTRY[label].get("min_length")
    assert isinstance(declared, int) and declared > 0, (
        f"{label} has no min_length; presence alone would pass a truncated id"
    )
    assert build_entry(label, REGISTRY[label])["min_length"] == declared


def test_installation_id_floor_admits_a_real_id_and_rejects_a_truncation():
    """Bracket the floor from both sides rather than restating the number.

    A modern installation id is 8 digits. The floor must accept that and reject
    the two-character truncation family; a floor that rejects a genuine id would
    withhold the credential fleet-wide, which is the failure this closes.
    """
    floor = REGISTRY[INSTALLATION_ID]["min_length"]
    assert len("8" * 8) >= floor, "an 8-digit installation id must pass"
    assert len("8" * 6) < floor, "a 2-char truncation of an 8-digit id must fail"


def _entry(label: str) -> Entry:
    spec = REGISTRY[label]
    return Entry(
        id=label.lower(),
        label=label,
        required=bool(spec.get("required", False)),
        targets=[Target(file=CONSUMER_FILE, key=label)],
        min_length=int(spec.get("min_length", 0)),
    )


def test_truncated_installation_id_is_withheld_end_to_end():
    """The constraint is only real if the funnel acts on it.

    Positive control below: the same call with a full-length id emits the value,
    so an empty ``outputs`` here means "withheld", not "the harness emits nothing".
    """
    entry = _entry(INSTALLATION_ID)
    rejected: dict = {}

    truncated, _ = build_outputs(
        {INSTALLATION_ID: "8" * 6}, [entry], strict=False, rejected_out=rejected
    )
    assert INSTALLATION_ID not in truncated.get(CONSUMER_FILE, {})
    assert INSTALLATION_ID in rejected.get(CONSUMER_FILE, set()), (
        "a withheld key must also be REMOVED: the funnel writes in merge mode, so "
        "omitting it leaves the previously-emitted bad value live for compose"
    )

    full, _ = build_outputs({INSTALLATION_ID: "8" * 8}, [entry], strict=False)
    assert full[CONSUMER_FILE][INSTALLATION_ID] == "8" * 8


def test_pem_leg_is_deliberately_unregistered_because_it_cannot_travel_this_path():
    """GH_APP_SEC is the third leg of the same credential and is NOT registered.

    Registering it would produce a slot that reports as delivered and is silently
    dropped on every run: ``_drop_multiline`` refuses newline-bearing values into
    a line-based env file, because compose ``env_file`` is strictly one VAR=VAL
    per line. It needs the ``*_FILE`` convention or a Docker secret instead.
    """
    assert PEM_KEY not in REGISTRY

    pem = "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----"
    survivors = _drop_multiline(CONSUMER_FILE, {PEM_KEY: pem, APP_ID: "123456"})
    assert PEM_KEY not in survivors, (
        "if this ever passes, the pipeline gained multi-line support and the PEM "
        "leg can be registered — until then, registering it would be a lie"
    )
    assert APP_ID in survivors  # positive control: single-line values do survive
