"""Mutation-kill harness: the smoke-suite catalog ratchet must BITE.

The companion harness for
``pmoves/tests/tools/test_smoke_suite_service_catalog_ratchet.py``.

THE KILL CONTRACT: GREEN, RED, GREEN
-------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine tree must pass the selected tests.
  2. RED AFTER    -- the mutated tree must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored tree must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error or an unrelated
environment failure also satisfies. The harness reads pytest's own short test
summary and requires the NAMED test to be IN it.

THE MUTATIONS
-------------
  M1  the catalog's archon health path goes back to /healthz, the path Archon
      0.10.1 answers with its UI catch-all HTML;
  M2  the catalog's archon port leaves the registry's host_port;
  M3  the catalog's pmoves-ui port goes back to the CONTAINER port;
  M4  the pmoves-ui verdict stops skipping an auth-armed service;
  M5  the archon smoke tests go back to probing the literal /healthz;
  M6  the archon OpenAPI path moves off the API prefix, back to /openapi.json;
  M7  the credential marker set is WIDENED to swallow a genuine dependency
      failure -- which would turn a real outage into a SKIP.

Every mutation keeps the mutated file IMPORTABLE: a duplicate keyword
argument or a syntax error would abort COLLECTION, and then the named test
would not appear in the failure summary at all -- the harness would be
proving nothing about the invariant.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_smoke_suite_service_catalog_ratchet_mutation_kill.py -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_ROOT = REPO_ROOT / "pmoves"
CATALOG = PMOVES_ROOT / "tests" / "utils" / "service_catalog.py"
VERDICT = PMOVES_ROOT / "tests" / "utils" / "health_verdict.py"
ARCHON_TEST = PMOVES_ROOT / "tests" / "smoke" / "test_archon.py"

RATCHET = "tests/tools/test_smoke_suite_service_catalog_ratchet.py"

HEALTH_PATH_TEST = "test_the_catalog_archon_health_path_matches_the_house_smoke_harness"
ARCHON_PORT_TEST = "test_the_catalog_archon_port_matches_the_port_registry"
PMOVES_UI_PORT_TEST = "test_the_catalog_pmoves_ui_port_matches_the_port_registry"
VERDICT_TEST = "test_the_pmoves_ui_verdict_skips_only_credential_failures"
MARKER_SET_TEST = "test_the_credential_marker_set_is_the_enumerated_one"
ARCHON_PROBE_TEST = "test_the_archon_smoke_tests_probe_the_catalog_health_path"
ARCHON_OPENAPI_TEST = "test_the_archon_openapi_path_sits_beside_the_catalog_health_path"

ALL_TARGETS = [
    f"{RATCHET}::{HEALTH_PATH_TEST}",
    f"{RATCHET}::{ARCHON_PORT_TEST}",
    f"{RATCHET}::{PMOVES_UI_PORT_TEST}",
    f"{RATCHET}::{VERDICT_TEST}",
    f"{RATCHET}::{MARKER_SET_TEST}",
    f"{RATCHET}::{ARCHON_PROBE_TEST}",
    f"{RATCHET}::{ARCHON_OPENAPI_TEST}",
]


def _read(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _run_pytest(nodes: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *nodes, "-q", "--tb=no", "-rf"],
        cwd=PMOVES_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def _failed_tests(output: str) -> set[str]:
    """The node ids pytest itself reported as FAILED."""
    failed = set()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            node = line[len("FAILED "):].split(" - ")[0].strip()
            failed.add(node)
    return failed


# ── the mutations ────────────────────────────────────────────────────────────

def _mutate_archon_health_path(text: str) -> str:
    """M1: the catalog's archon health path goes back to /healthz."""
    anchor = (
        '    health_path="/api/health",\n'
        "    health_type=HealthCheckType.STANDARD,\n"
        '    expected_fields=["status"],\n'
        '    profile="agents",\n'
        '    dependencies=["postgres", "agent-zero"],\n'
    )
    assert text.count(anchor) == 1, "mutation anchor not found (archon health path)"
    return text.replace(
        anchor,
        '    health_path="/healthz",\n'
        "    health_type=HealthCheckType.STANDARD,\n"
        '    expected_fields=["status"],\n'
        '    profile="agents",\n'
        '    dependencies=["postgres", "agent-zero"],\n',
    )


def _mutate_archon_port(text: str) -> str:
    """M2: the catalog's archon port leaves the registry's host_port."""
    anchor = '    name="archon",\n    port=8091,\n'
    assert text.count(anchor) == 1, "mutation anchor not found (archon port)"
    return text.replace(anchor, '    name="archon",\n    port=3091,\n')


def _mutate_pmoves_ui_port(text: str) -> str:
    """M3: the catalog's pmoves-ui port goes back to the CONTAINER port."""
    anchor = "    port=4482,\n"
    assert text.count(anchor) == 1, "mutation anchor not found (pmoves-ui port)"
    return text.replace(anchor, "    port=3000,\n")


def _mutate_no_skip(text: str) -> str:
    """M4: the verdict stops skipping an auth-armed service."""
    anchor = (
        "            if isinstance(database, dict):\n"
        '                error = str(database.get("error") or "").lower()\n'
        '                if (database.get("status") == "unhealthy"\n'
        "                        and any(m in error for m in CREDENTIAL_MARKERS)):\n"
        "                    return SKIP\n"
    )
    assert text.count(anchor) == 1, "mutation anchor not found (verdict skip)"
    return text.replace(
        anchor,
        "            if isinstance(database, dict):\n"
        '                error = str(database.get("error") or "").lower()\n',
    )


def _mutate_widen_marker_set(text: str) -> str:
    """M7: the marker set swallows a genuine dependency failure.

    Adding "connection refused" to the credential markers would make a real
    database outage SKIP -- the smoke gate would go blind to it, which is the
    exact failure mode the narrow marker set exists to prevent.
    """
    anchor = '    "no service key",\n)'
    assert text.count(anchor) == 1, "mutation anchor not found (marker set)"
    return text.replace(
        anchor,
        '    "no service key",\n    "connection refused",\n)',
    )


def _mutate_archon_test_path(text: str) -> str:
    """M5: the archon smoke tests go back to probing the literal /healthz."""
    anchor = "ARCHON.health_path"
    assert text.count(anchor) >= 4, "mutation anchor not found (archon probes)"
    return text.replace(anchor, '"/healthz"')


def _mutate_archon_openapi_path(text: str) -> str:
    """M6: the archon OpenAPI path moves off the API prefix."""
    anchor = 'ARCHON_OPENAPI_PATH = "/api/openapi.json"'
    assert text.count(anchor) == 1, "mutation anchor not found (openapi path)"
    return text.replace(anchor, 'ARCHON_OPENAPI_PATH = "/openapi.json"')


MUTATIONS = [
    (CATALOG, _mutate_archon_health_path, f"{RATCHET}::{HEALTH_PATH_TEST}"),
    (CATALOG, _mutate_archon_port, f"{RATCHET}::{ARCHON_PORT_TEST}"),
    (CATALOG, _mutate_pmoves_ui_port, f"{RATCHET}::{PMOVES_UI_PORT_TEST}"),
    (VERDICT, _mutate_no_skip, f"{RATCHET}::{VERDICT_TEST}"),
    (VERDICT, _mutate_widen_marker_set, f"{RATCHET}::{MARKER_SET_TEST}"),
    (ARCHON_TEST, _mutate_archon_test_path, f"{RATCHET}::{ARCHON_PROBE_TEST}"),
    (ARCHON_TEST, _mutate_archon_openapi_path, f"{RATCHET}::{ARCHON_OPENAPI_TEST}"),
]


# ── the harness ──────────────────────────────────────────────────────────────

def test_mutation_kills_are_proven() -> None:
    """Every mutation must turn the NAMED test RED, and the tree must restore."""
    originals = {path: _read(path) for path, _, _ in MUTATIONS}

    # 1. GREEN BEFORE -- the pristine tree passes every target.
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"the pristine tree is not green before mutation:\n{out}"

    kills: list[str] = []
    try:
        for path, mutate, node in MUTATIONS:
            original = originals[path]
            mutated = mutate(original)
            assert mutated != original, f"{node} produced no mutation"
            _write(path, mutated)

            rc, out = _run_pytest([node])
            failed = _failed_tests(out)
            assert rc != 0, f"{node} still passed on the mutated tree:\n{out}"
            assert any(node in f for f in failed), (
                f"{node}: expected the named test in pytest's failure summary, "
                f"got {sorted(failed)}"
            )
            kills.append(f"{node} -> {path.name}")
    finally:
        for path, original in originals.items():
            _write(path, original)

    # 3. GREEN AFTER -- the byte-exact restore passes again.
    for path, original in originals.items():
        assert _read(path) == original, f"{path.name} was not restored byte-exactly"
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"the restored tree is not green after mutation:\n{out}"

    assert len(kills) == len(MUTATIONS), f"expected {len(MUTATIONS)} kills, got {kills}"
    print("\nproven kills:")
    for k in kills:
        print(f"  {k}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
