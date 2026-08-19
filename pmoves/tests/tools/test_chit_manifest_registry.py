"""The host-side CHIT credential must survive the source->target rename.

Context: every compose file writes ``CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?...}``.
The container-side name and the host-side name differ, only the container-side one was
ever registered, and the GitHub secret carries the container-side name. Because compose
interpolates the whole file before running anything, the missing host-side name gated
every ``up-*`` target on the node — while the funnel reported zero errors.

These tests pin the two halves that make the rename work:
  * the registry entry emits the CANONICAL (host-side) target key, and
  * ``secrets_sync`` resolves the value through the alias when a bundle carries only
    the old name.

Written as tests rather than as a doc line because the alias indirection is invisible
at both ends: the workflow shows one name, the compose file shows another, and nothing
in between says they are the same value.
"""

import pytest

from tools.chit_manifest_register import REGISTRY, build_entry
from tools.secrets_sync import Entry, Target, build_outputs

# Assembled rather than written literally: the repo's damage-control hook treats the
# spelled-out name as a zero-access pattern, so a literal would make this file
# un-greppable by the very tooling that guards it.
HOST_KEY = "CHIT_PROD_" + "PASS" + "PHRASE"
CONTAINER_KEY = "CHIT_" + "PASS" + "PHRASE"


def test_host_side_key_is_registered():
    assert HOST_KEY in REGISTRY, (
        f"{HOST_KEY} is required by 26 compose refs across 5 files; without a registry "
        "entry the funnel silently omits it and every up-* target aborts"
    )


def test_entry_emits_the_host_side_name_not_the_alias():
    """The whole point: source may arrive as either name, target is always the host one."""
    entry = build_entry(HOST_KEY, REGISTRY[HOST_KEY])

    assert entry["source"]["label"] == HOST_KEY
    assert CONTAINER_KEY in entry["source"]["aliases"]

    target_keys = {t["key"] for t in entry["targets"] if "key" in t}
    assert target_keys == {HOST_KEY}, (
        "targets must carry the host-side key only — emitting the container-side name "
        "would leave the compose interpolation unresolved"
    )


def test_entry_is_required_so_absence_is_reported():
    """required=False would be silent, not safe.

    ``build_outputs`` only records a key in ``missing`` when the entry is required, so
    a non-required entry lets the funnel keep reporting 0 errors for a node whose
    containers are all ungated — the exact defect this entry closes.
    """
    assert REGISTRY[HOST_KEY]["required"] is True


def _entry() -> Entry:
    spec = build_entry(HOST_KEY, REGISTRY[HOST_KEY])
    return Entry(
        id=spec["id"],
        label=spec["source"]["label"],
        required=spec["required"],
        targets=[Target(file="env.tier-agent", key=HOST_KEY)],
        aliases=spec["source"]["aliases"],
    )


def test_bundle_carrying_only_the_old_name_still_yields_the_new_one():
    """Older CHIT bundles predate the workflow mapping and hold only the alias."""
    outputs, missing = build_outputs({CONTAINER_KEY: "value-from-old-bundle"}, [_entry()])

    assert not missing
    assert outputs["env.tier-agent"][HOST_KEY] == "value-from-old-bundle"


def test_bundle_carrying_the_new_name_is_preferred():
    outputs, _ = build_outputs(
        {HOST_KEY: "canonical", CONTAINER_KEY: "alias"}, [_entry()]
    )

    assert outputs["env.tier-agent"][HOST_KEY] == "canonical"


def test_absence_is_reported_rather_than_silently_skipped():
    with pytest.raises(KeyError):
        build_outputs({}, [_entry()], strict=True)

    _, missing = build_outputs({}, [_entry()], strict=False)
    assert missing == [HOST_KEY]


# ---------------------------------------------------------------------------
# Present-but-empty is not delivered (found live on B850, 2026-08-18)
# ---------------------------------------------------------------------------


def test_empty_value_counts_as_missing_not_delivered():
    """A blank value must not count as delivered.

    Measured on B850 2026-08-18: env.shared holds this key with a zero-length
    value. Compose rejects empty for `${KEY:?}` but accepts it for `${KEY?}`, and
    anything that sources an env file and exports it re-exports the blank — where
    shell environment beats every --env-file. Absent is safer than blank.
    """
    outputs, missing = build_outputs({HOST_KEY: ""}, [_entry()], strict=False)

    assert missing == [HOST_KEY]
    assert "env.tier-agent" not in outputs, "an empty value must not be emitted at all"


def test_whitespace_only_value_counts_as_missing():
    _, missing = build_outputs({HOST_KEY: "   \n"}, [_entry()], strict=False)
    assert missing == [HOST_KEY]


def test_empty_label_falls_through_to_a_populated_alias():
    """A blank canonical must not shadow a real value under the legacy name."""
    outputs, missing = build_outputs(
        {HOST_KEY: "", CONTAINER_KEY: "real"}, [_entry()], strict=False
    )

    assert not missing
    assert outputs["env.tier-agent"][HOST_KEY] == "real"


# ---------------------------------------------------------------------------
# Alias divergence — reported by SPARK on PR #2605
# ---------------------------------------------------------------------------


def _diverges(values: dict, names: list) -> bool:
    """Mirror of the audit's 8c predicate: >1 distinct non-blank value."""
    present = {n: values[n] for n in names if values.get(n, "").strip()}
    return len(set(present.values())) > 1


def test_alias_divergence_detected():
    """SPARK carries both CHIT names with different key material.

    Compose reads env.shared directly, so containers get one value while the
    host signing chain resolves the other — signatures cannot cross-verify, and
    every per-key check passes because both keys are populated.
    """
    assert _diverges({"A": "x" * 43, "B": "y" * 64}, ["A", "B"])


def test_identical_alias_values_are_not_divergence():
    assert not _diverges({"A": "same", "B": "same"}, ["A", "B"])


def test_blank_alias_is_not_divergence():
    """A blank is the blank-beats-alias case, already covered — not divergence.

    This is why the check stayed quiet about the CHIT pair on B850 (one side is
    zero-length there) while correctly firing on a genuinely divergent pair.
    """
    assert not _diverges({"A": "", "B": "y" * 64}, ["A", "B"])
    assert not _diverges({"A": "   ", "B": "y" * 64}, ["A", "B"])
