#!/usr/bin/env python3
"""Mutation-kill harness for the mesh <-> node-registry compatibility slice.

WHAT THIS PROVES. A test suite that passes proves nothing on its own -- it
proves that the tests agree with the code. This harness proves the tests
would NOTICE if the code regressed: for each defect this slice fixed, it
breaks the fix on purpose and asserts that a NAMED test goes RED.

THE RULE: the harness must MUTATE THE PRODUCTION SOURCE and run the real
test file. It must never restate the assertion it expects to fail. A
harness that re-implements the check proves only that the harness agrees
with itself. The mutations below are the smallest edits that reintroduce
the exact defect each finding named:

  M1  the registry subscribes to the OLD subject again
      -> `compute.nodes.announce.v1`, the string nobody publishes: the mesh
         announces on `mesh.node.announce.v1` and the announcements reach
         nobody again (PRE_RESTART_PREFLIGHT row R8).
  M2  the package directory goes back to its kebab-case name
      -> `node-registry` instead of `node_registry`: the package can no
         longer be imported under the name its importers use, which is the
         D2 defect itself (`resource-detector` -> `resource_detector`).
  M3  the work-marshaling service stops importing the canonical package
      -> its shared models are unreachable again, so the service cannot be
         imported at all.
  M4  the vllm-orchestrator entry point stops importing its canonical package
      -> the service cannot resolve its own orchestrator when it runs as a
         script, and the relative imports inside the package have no parent:
         the D3 defect.
  M5  the COMPUTE JetStream stream stops covering the announce family
      -> the registry's JetStream consumer falls back to core NATS and
         loses every announcement published while it was down (R8a).
  M6  a curated registry entry disappears
      -> the curated set the mesh exposes changes without the contract
         changing: the D1 defect class (the count assertion that stayed
         red for twelve weeks said nothing about WHICH entry moved).
  M7  a curated entry reverts to the LEGACY layer vocabulary
      -> `layer_1..layer_4` instead of `l1_venv` / `l2_container_same_host`
         / `l3_mesh` / `l4_public`: the entry still PARSES, so an
         alias-tolerant check would certify it, but the planner reads the
         canonical names only -- the mesh would be blind to an app the
         registry lists.
  M8  the COMPUTE subject list goes back to the space-separated form
      -> the pinned CLI happens to split on whitespace as well, so this is
         NOT "the old form was broken"; it is the loss of the CANONICAL,
         version-stable list form the validator reads back.
  M9  the registry asks for the lowercase stream name again
      -> `stream="compute"` while init_streams.sh creates `COMPUTE`:
         JetStream stream names are case-sensitive, so the subscribe raises
         and the registry falls back to core NATS (R8a).
  M10 the JetStream subscription is never tracked
      -> it is not appended to `_subscriptions`, so `stop()` leaves it
         alive and it leaks on every restart.
  M11 the registry stops normalising an aware announcement timestamp
      -> `datetime.fromisoformat` returns an aware datetime, the store's
         naive clock cannot be subtracted from it, and `list_online()`
         raises TypeError.
  M12 the HTTP heartbeat endpoint stops normalising its timestamp
      -> the same aware/naive crash, through the other producer of a
         heartbeat timestamp.
  M13 the validator reads only the FIRST JSON object of the capture
      -> `json.loads` on a concatenated capture: the second stream is
         invisible, so a missing stream is never reported.
  M14 the validator compares the subject list as an ORDERED tuple
      -> the guard rejects a stream that carries exactly the expected
         subjects in a different order (JetStream promises no order).

Run:
  python -m pytest pmoves/tests/tools/test_mesh_node_compatibility_mutation_kill.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_FILE = "pmoves/tests/tools/test_mesh_node_compatibility.py"

NODE_REGISTRY_DIR = REPO_ROOT / "pmoves" / "services" / "node_registry"
NODE_REGISTRY_KEBAB_DIR = REPO_ROOT / "pmoves" / "services" / "node-registry"
REGISTRY_PY = NODE_REGISTRY_DIR / "registry.py"
REGISTRY_API_PY = NODE_REGISTRY_DIR / "api.py"
WORK_MARSHALING_INIT = REPO_ROOT / "pmoves" / "services" / "work_marshaling" / "__init__.py"
VLLM_MAIN = REPO_ROOT / "pmoves" / "services" / "vllm_orchestrator" / "main.py"
INIT_STREAMS = REPO_ROOT / "pmoves" / "scripts" / "nats" / "init_streams.sh"
VALIDATE_STREAMS = REPO_ROOT / "pmoves" / "scripts" / "nats" / "validate_streams.py"
CURATED_ENTRY = (
    REPO_ROOT / "pmoves" / "configs" / "pinokio-apps" / "curated" / "crush.yaml"
)


def _run_pytest(node_id: str) -> subprocess.CompletedProcess:
    """Run one test from the real test file in a child interpreter."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"{TEST_FILE}::{node_id}",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )


def _apply_mutation(target: Path, old: str, new: str) -> bytes:
    """Mutate *target* in place, returning the original bytes for restore."""
    original = target.read_bytes()
    text = original.decode("utf-8")
    assert old in text, (
        f"mutation anchor not found in {target.name}; the harness is stale "
        f"and would silently pass. Anchor was:\n{old}"
    )
    assert text.count(old) == 1, (
        f"mutation anchor is not unique in {target.name} "
        f"(found {text.count(old)} times) -- it would mutate more than intended"
    )
    target.write_text(text.replace(old, new), encoding="utf-8")
    return original


def _restore(target: Path, original: bytes) -> None:
    target.write_bytes(original)
    assert target.read_bytes() == original, f"failed to restore {target.name}"


# ---------------------------------------------------------------------------
# The mutations
# ---------------------------------------------------------------------------

# M1 -- the registry subscribes to the old, unpublished subject again.
M1_OLD = '''    "announce": "mesh.node.announce.v1",'''
M1_NEW = '''    "announce": "compute.nodes.announce.v1",'''

# M2 -- the package directory goes back to its kebab-case name.
# (applied as a directory rename, not a text edit -- the defect IS the name)

# M3 -- work-marshaling stops reaching the canonical resource_detector package.
M3_OLD = "from pmoves.services.resource_detector.models import WorkAssignment, WorkRequest"
M3_NEW = "from pmoves.services.resource_detector_typo.models import WorkAssignment, WorkRequest"

# M4 -- the vllm-orchestrator entry point stops importing its canonical
# package, so the service cannot resolve its own orchestrator when it runs
# as a script. (The directory is now `vllm_orchestrator`, a real package, so
# the entry point uses the canonical import directly.)
M4_OLD = "from pmoves.services.vllm_orchestrator import VLLMOrchestrator  # noqa: E402"
M4_NEW = "from pmoves.services.vllm_orchestrator_typo import VLLMOrchestrator  # noqa: E402"

# M5 -- the COMPUTE stream stops covering the mesh announcement family.
M5_OLD = '  --subjects "mesh.node.announce.>,compute.nodes.>" \\'
M5_NEW = '  --subjects "compute.nodes.>" \\'

# M6 -- a curated entry disappears (applied as a file move, not a text edit --
# the defect IS a missing entry, not a changed one).

# M8 -- the COMPUTE subject list goes back to the space-separated form.
# HONESTY NOTE: the pinned CLI splits on whitespace as well, so this does
# NOT reproduce a broken stream -- it removes the CANONICAL, version-stable
# list form that the validator reads back out of `stream info -j`.
M8_OLD = '  --subjects "mesh.node.announce.>,compute.nodes.>" \\'
M8_NEW = '  --subjects "mesh.node.announce.> compute.nodes.>" \\'

# M9 -- the registry asks for the lowercase stream name again.
M9_OLD = 'ANNOUNCE_STREAM = "COMPUTE"'
M9_NEW = 'ANNOUNCE_STREAM = "compute"'

# M10 -- the JetStream subscription is never tracked, so stop() leaks it.
M10_OLD = "            self._subscriptions.append(js_sub)"
M10_NEW = (
    "            pass  # MUTATED: the JetStream subscription is never tracked"
)

# M11 -- the registry stops normalising an aware announcement timestamp.
M11_OLD = '            return naive_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))'
M11_NEW = '            return datetime.fromisoformat(raw.replace("Z", "+00:00"))'

# M12 -- the HTTP heartbeat endpoint stops normalising its timestamp.
M12_OLD = """                timestamp=naive_utc(
                    datetime.fromisoformat(
                        payload.get("timestamp", datetime.now().isoformat())
                    )
                ),"""
M12_NEW = """                timestamp=datetime.fromisoformat(
                    payload.get("timestamp", datetime.now().isoformat())
                ),"""

# M13 -- the validator reads only the FIRST JSON object of the capture.
M13_OLD = "            payload, index = decoder.raw_decode(text, index)"
M13_NEW = (
    "            payload = json.loads(text)  # MUTATED: only the first object\n"
    "            index = length"
)

# M14 -- the validator compares the subject list as an ORDERED tuple.
M14_OLD = "        if set(row.subjects) != set(expected.subjects):"
M14_NEW = (
    "        if row.subjects != expected.subjects:  # MUTATED: ordered compare"
)


MUTATIONS = [
    (
        "M1",
        REGISTRY_PY,
        M1_OLD,
        M1_NEW,
        "test_the_registry_subscribes_to_the_subjects_the_mesh_publishes",
    ),
    (
        "M3",
        WORK_MARSHALING_INIT,
        M3_OLD,
        M3_NEW,
        "test_the_four_services_import_under_their_canonical_package_names",
    ),
    (
        "M4",
        VLLM_MAIN,
        M4_OLD,
        M4_NEW,
        "test_the_service_entry_points_resolve_their_imports_without_a_package",
    ),
    (
        "M5",
        INIT_STREAMS,
        M5_OLD,
        M5_NEW,
        "test_the_compute_stream_carries_the_announce_family",
    ),
    (
        "M8",
        INIT_STREAMS,
        M8_OLD,
        M8_NEW,
        "test_the_compute_stream_declares_its_subjects_as_a_comma_separated_list",
    ),
    (
        "M9",
        REGISTRY_PY,
        M9_OLD,
        M9_NEW,
        "test_the_registry_and_the_stream_script_name_the_same_stream",
    ),
    (
        "M10",
        REGISTRY_PY,
        M10_OLD,
        M10_NEW,
        "test_the_registry_tears_down_its_jetstream_subscription",
    ),
    (
        "M11",
        REGISTRY_PY,
        M11_OLD,
        M11_NEW,
        "test_every_datetime_that_enters_the_store_is_naive",
    ),
    (
        "M12",
        REGISTRY_API_PY,
        M12_OLD,
        M12_NEW,
        "test_every_datetime_that_enters_the_store_is_naive",
    ),
    (
        "M13",
        VALIDATE_STREAMS,
        M13_OLD,
        M13_NEW,
        "test_the_validator_reads_the_real_stream_info_contract",
    ),
    (
        "M14",
        VALIDATE_STREAMS,
        M14_OLD,
        M14_NEW,
        "test_the_validator_matches_a_two_subject_stream_by_set",
    ),
]


@pytest.mark.parametrize(
    "label,target,old,new,killing_test",
    MUTATIONS,
    ids=[m[0] for m in MUTATIONS],
)
def test_text_mutation_is_killed(label, target, old, new, killing_test):
    """Break the fix on purpose; the named test must go RED."""
    original = _apply_mutation(target, old, new)
    try:
        mutated = _run_pytest(killing_test)
    finally:
        _restore(target, original)

    assert mutated.returncode != 0, (
        f"{label}: the mutation was NOT killed -- {killing_test} still passed "
        f"with the defect reintroduced.\nSTDOUT:\n{mutated.stdout}"
    )
    assert killing_test in mutated.stdout, (
        f"{label}: the suite went red, but not because of {killing_test} -- "
        f"the named test is not in the report.\nSTDOUT:\n{mutated.stdout}"
    )

    # And the suite is green again once the fix is restored -- a test that
    # fails for an unrelated reason would "kill" every mutation.
    restored = _run_pytest(killing_test)
    assert restored.returncode == 0, (
        f"{label}: the test does not pass with the fix restored, so its "
        f"failure above proves nothing.\nSTDOUT:\n{restored.stdout}"
    )


def test_M2_the_kebab_directory_name_is_killed():
    """M2: renaming the package directory back must break the named test.

    This is the D2 defect in its purest form: the directory name and the
    import name disagree, so the package cannot be imported at all.
    """
    assert NODE_REGISTRY_DIR.is_dir(), "the package directory is not where it should be"
    assert not NODE_REGISTRY_KEBAB_DIR.exists(), "the kebab-case directory already exists"

    NODE_REGISTRY_DIR.rename(NODE_REGISTRY_KEBAB_DIR)
    try:
        mutated = _run_pytest(
            "test_the_four_services_import_under_their_canonical_package_names"
        )
    finally:
        NODE_REGISTRY_KEBAB_DIR.rename(NODE_REGISTRY_DIR)

    assert mutated.returncode != 0, (
        "M2: the mutation was NOT killed -- the services still import with a "
        f"kebab-case package directory.\nSTDOUT:\n{mutated.stdout}"
    )
    assert (
        "test_the_four_services_import_under_their_canonical_package_names"
        in mutated.stdout
    ), (
        "M2: the suite went red, but not because of the named test.\n"
        f"STDOUT:\n{mutated.stdout}"
    )

    restored = _run_pytest(
        "test_the_four_services_import_under_their_canonical_package_names"
    )
    assert restored.returncode == 0, (
        "M2: the test does not pass with the fix restored, so its failure "
        f"above proves nothing.\nSTDOUT:\n{restored.stdout}"
    )


def test_M6_a_missing_curated_entry_is_killed():
    """M6: a curated entry that disappears must break the named test.

    The old assertion was a COUNT, so it could not say WHICH entry moved --
    and it stayed red for twelve weeks after a legitimate addition. The
    contract is now the slug set: an entry that disappears has to fail.
    """
    assert CURATED_ENTRY.is_file(), f"missing curated entry: {CURATED_ENTRY}"
    moved = CURATED_ENTRY.with_suffix(".yaml.ratchet-mutation")

    CURATED_ENTRY.rename(moved)
    try:
        mutated = _run_pytest(
            "test_the_curated_registry_set_matches_the_curated_directory"
        )
    finally:
        moved.rename(CURATED_ENTRY)

    assert mutated.returncode != 0, (
        "M6: the mutation was NOT killed -- the curated set changed without "
        f"the contract noticing.\nSTDOUT:\n{mutated.stdout}"
    )
    assert (
        "test_the_curated_registry_set_matches_the_curated_directory"
        in mutated.stdout
    ), (
        "M6: the suite went red, but not because of the named test.\n"
        f"STDOUT:\n{mutated.stdout}"
    )

    restored = _run_pytest(
        "test_the_curated_registry_set_matches_the_curated_directory"
    )
    assert restored.returncode == 0, (
        "M6: the test does not pass with the fix restored, so its failure "
        f"above proves nothing.\nSTDOUT:\n{restored.stdout}"
    )


def test_M7_the_legacy_layer_vocabulary_is_killed():
    """M7: a curated entry reverting to the legacy layer names must break the named test.

    `crush.yaml` was authored against `layer_1..layer_4`. The entry PARSED, so
    every count-based or alias-tolerant check was happy -- but the planner
    reads `l3_mesh` / `l4_public` only, so the mesh saw crush as having NO
    exposure contract. A test that tolerates a vocabulary the product ignores
    is worse than no test: it certifies a blind spot.

    The mutation renames the four canonical keys back to the legacy ones.
    """
    assert CURATED_ENTRY.is_file(), f"missing curated entry: {CURATED_ENTRY}"

    original = CURATED_ENTRY.read_bytes()
    text = original.decode("utf-8")
    for canonical, legacy in (
        ("l1_venv", "layer_1"),
        ("l2_container_same_host", "layer_2"),
        ("l3_mesh", "layer_3"),
        ("l4_public", "layer_4"),
    ):
        anchor = f"  {canonical}:\n"
        assert text.count(anchor) == 1, (
            f"M7: the mutation anchor for '{canonical}' is not unique in "
            f"{CURATED_ENTRY.name} (found {text.count(anchor)} times) -- the "
            "harness is stale and would silently pass"
        )
        text = text.replace(anchor, f"  {legacy}:\n")

    CURATED_ENTRY.write_text(text, encoding="utf-8")
    try:
        mutated = _run_pytest(
            "test_the_curated_entries_declare_the_canonical_exposure_layers"
        )
    finally:
        CURATED_ENTRY.write_bytes(original)

    assert CURATED_ENTRY.read_bytes() == original, "failed to restore crush.yaml"

    assert mutated.returncode != 0, (
        "M7: the mutation was NOT killed -- a curated entry in the legacy "
        "layer vocabulary still passes, so the mesh can be blind to an app "
        f"the registry lists.\nSTDOUT:\n{mutated.stdout}"
    )
    assert (
        "test_the_curated_entries_declare_the_canonical_exposure_layers"
        in mutated.stdout
    ), (
        "M7: the suite went red, but not because of the named test.\n"
        f"STDOUT:\n{mutated.stdout}"
    )

    restored = _run_pytest(
        "test_the_curated_entries_declare_the_canonical_exposure_layers"
    )
    assert restored.returncode == 0, (
        "M7: the test does not pass with the fix restored, so its failure "
        f"above proves nothing.\nSTDOUT:\n{restored.stdout}"
    )


def test_the_whole_suite_is_green_before_any_mutation():
    """Baseline: the suite the mutations are measured against is green.

    Without this, a suite that is red for an unrelated reason would make
    every mutation look "killed".
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            TEST_FILE,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, (
        f"the compatibility suite is not green BEFORE any mutation:\n{proc.stdout}"
    )
