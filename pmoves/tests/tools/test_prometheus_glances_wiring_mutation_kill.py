"""Mutation-kill harness: the Glances<->Prometheus ratchet must BITE when the
defect is put back.

This is the PROVENANCE HARNESS for the Glances wiring ratchet
(``pmoves/tests/tools/test_prometheus_glances_wiring.py``).

THE DEFECT
----------
The Glances exporter binds to a host port that lives in PROSE (the runbook's
section 4.4: ``[prometheus] host=localhost port=9091 prefix=glances``) while
the scrape target that must reach it lives in YAML
(``pmoves/monitoring/prometheus/prometheus.yml``). Nothing else in the repo
connects the two files. The pre-fix state was that they were never connected
at all: the exporter port was prescribed in the runbook, the scrape job did
not exist, and GLANCES_RUNBOOK.md finding F12 ("Wire Prometheus and/or NATS
export") was left open while the runbook's own section heading still read
"not wired".

THE KILL CONTRACT: GREEN, RED, GREEN
-------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected tests.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted. The source is
read and written with ``newline=""`` so the tool's LF line endings survive
the harness untouched.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it. A harness may
only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below restores the PRE-FIX behaviour of the exact branch the
named test guards:

  M1  the scrape target's port drifts from the exporter port the runbook
      prescribes -- the two files are edited independently and nothing
      connects them;
  M2  the scrape target stops using the Docker host gateway, i.e. it starts
      naming a compose service for an exporter that has no compose service;
  M3  the `glances` scrape job is removed while the runbook still claims the
      Prometheus half is wired -- the claim outlives the wiring;
  M4  the runbook stops naming the service that ALSO owns the exporter port
      in the port registry, so the collision caveat silently disappears.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_prometheus_glances_wiring_mutation_kill.py -q
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_ROOT = REPO_ROOT / "pmoves"

PROMETHEUS_YML = PMOVES_ROOT / "monitoring" / "prometheus" / "prometheus.yml"
GLANCES_RUNBOOK = PMOVES_ROOT / "docs" / "operations" / "GLANCES_RUNBOOK.md"

RATCHET = "tests/tools/test_prometheus_glances_wiring.py"

TARGET_PORT_TEST = "test_glances_scrape_target_port_matches_runbook_exporter_port"
TARGET_KIND_TEST = "test_glances_scrape_target_uses_the_docker_host_gateway"
WIRING_CLAIM_TEST = "test_runbook_prometheus_wiring_claim_matches_the_config"
COLLISION_CAVEAT_TEST = "test_headscale_port_collision_caveat_is_recorded"

ALL_TARGETS = [
    f"{RATCHET}::{TARGET_PORT_TEST}",
    f"{RATCHET}::{TARGET_KIND_TEST}",
    f"{RATCHET}::{WIRING_CLAIM_TEST}",
    f"{RATCHET}::{COLLISION_CAVEAT_TEST}",
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

def _mutate_port_drift(prom: str, runbook: str) -> tuple[str, str]:
    """M1: the scraped port drifts from the prescribed exporter port."""
    assert "host.docker.internal:9091" in prom, "mutation anchor not found"
    return prom.replace("host.docker.internal:9091", "host.docker.internal:9092"), runbook


def _mutate_target_kind(prom: str, runbook: str) -> tuple[str, str]:
    """M2: the target stops using the Docker host gateway."""
    assert "host.docker.internal:9091" in prom, "mutation anchor not found"
    return prom.replace("host.docker.internal:9091", "glances:9091"), runbook


def _mutate_remove_job(prom: str, runbook: str) -> tuple[str, str]:
    """M3: the glances scrape job disappears; the runbook still claims it."""
    anchor = '  - job_name: glances\n'
    assert anchor in prom, "mutation anchor not found"
    start = prom.index(anchor)
    end = prom.index("  - job_name:", start + len(anchor))
    return prom[:start] + prom[end:], runbook


def _mutate_drop_caveat(prom: str, runbook: str) -> tuple[str, str]:
    """M4: the runbook stops naming the service that also owns the port."""
    assert "headscale" in runbook.lower(), "mutation anchor not found"
    # Every case variant, including the slot name HEADSCALE_9091_PORT -- a
    # mutation that left the slot name behind would leave the service named.
    out = re.sub(r"headscale", "someother", runbook, flags=re.IGNORECASE)
    return prom, out


MUTATIONS = [
    ("M1_port_drift", _mutate_port_drift, TARGET_PORT_TEST),
    ("M2_target_kind", _mutate_target_kind, TARGET_KIND_TEST),
    ("M3_remove_job", _mutate_remove_job, WIRING_CLAIM_TEST),
    ("M4_drop_caveat", _mutate_drop_caveat, COLLISION_CAVEAT_TEST),
]


# ── the harness ──────────────────────────────────────────────────────────────

def test_mutation_kills_are_proven():
    """Every mutation must turn the NAMED test RED, and the tree must restore."""
    original_prom = _read(PROMETHEUS_YML)
    original_runbook = _read(GLANCES_RUNBOOK)

    # 1. GREEN BEFORE -- the pristine tree passes every target.
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"pristine tree is not green before mutation:\n{out}"

    kills: list[str] = []
    try:
        for name, mutate, named_test in MUTATIONS:
            prom, runbook = mutate(original_prom, original_runbook)
            assert prom != original_prom or runbook != original_runbook, (
                f"{name} produced no mutation"
            )
            _write(PROMETHEUS_YML, prom)
            _write(GLANCES_RUNBOOK, runbook)

            node = f"{RATCHET}::{named_test}"
            rc, out = _run_pytest([node])
            failed = _failed_tests(out)
            assert rc != 0, f"{name}: {named_test} still passed on the mutated tree:\n{out}"
            assert any(named_test in f for f in failed), (
                f"{name}: expected {named_test} in pytest's failure summary, got {sorted(failed)}"
            )
            kills.append(f"{name} -> {named_test}")
    finally:
        _write(PROMETHEUS_YML, original_prom)
        _write(GLANCES_RUNBOOK, original_runbook)

    # 3. GREEN AFTER -- the byte-exact restore passes again.
    assert _read(PROMETHEUS_YML) == original_prom, "prometheus.yml was not restored byte-exactly"
    assert _read(GLANCES_RUNBOOK) == original_runbook, "GLANCES_RUNBOOK.md was not restored byte-exactly"
    rc, out = _run_pytest(ALL_TARGETS)
    assert rc == 0, f"restored tree is not green after mutation:\n{out}"

    assert len(kills) == len(MUTATIONS), f"expected {len(MUTATIONS)} kills, got {kills}"
    print("\nproven kills:")
    for k in kills:
        print(f"  {k}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
