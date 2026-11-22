# pmoves/tools/tests/test_silent_bind_ratchet.py
"""Tests for the silent-bind ratchet gate.

The gate answers one question: can a service's published host port ever
activate? It must:

  1. REPORT a service that publishes a host port and joins only
     internal:true networks (the moby/moby#36174 class).
  2. NOT report a service that joins a non-internal network.
  3. NOT report a service that declares NO networks key. Such a service
     joins the file's DEFAULT network, which is a normal bridge, so its
     port binds. Scoring an empty network set as a gap is vacuous truth,
     and it is not what Docker does.
  4. NOT report a service whose network internality is UNKNOWN (external,
     or unstated by every source). An unknown network means the service may
     already be reachable; claiming a defect there would be a guess.
  5. RESOLVE a network's internality through the canonical PMOVES
     declarations when the scanned file does not declare it itself. This is
     the split-overlay blind spot: the generated overlays reference
     pmoves_api without declaring it, and a gate that only looks at the
     file's own networks block is blind to all of them.
  6. RESOLVE internality through YAML ANCHORS. The house declares
     pmoves_api with ``<<: *network-internal-only``, and a resolver that
     only reads literal keys reads it as UNKNOWN.
  7. FAIL CLOSED on a compose file it cannot parse: exit 3, NOT a pass.
  8. FAIL on a baseline entry that is no longer a gap (STALE) and on one
     whose reason is still the placeholder (UNREASONED) -- a recorded gap
     must carry a reviewed reason.
  9. FAIL on a NEW gap that is not in the baseline, so the list cannot
     silently grow.
 10. ACCEPT a service that attaches the house's host-reachable tier
     (pmoves_public) -- that is the tier DOCKER_NETWORK_HARDENING.md names
     for a published port, so such a service is clean.

Hermetic: no network, no docker, no gh. Runs on Linux and Windows.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = Path(__file__).resolve().parents[1] / "silent_bind_ratchet.py"
PYTHON = sys.executable


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _tree(tmp_path: Path, files: dict) -> Path:
    """Materialise a pmoves/ directory of compose files."""
    pmoves = tmp_path / "pmoves"
    for name, text in files.items():
        _write(pmoves / name, text)
    return pmoves


def _run(pmoves: Path, baseline: Path | None = None):
    cmd = [PYTHON, str(RATCHET), "--check", "--json",
           "--pmoves-dir", str(pmoves)]
    if baseline is not None:
        cmd += ["--baseline", str(baseline)]
    else:
        # No baseline file -> the tool's own default would be the REPO's
        # real baseline, whose entries describe the real tree. Every temp
        # run must see an EMPTY baseline instead.
        empty = pmoves.parent / "empty_baseline.yaml"
        empty.write_text("known_gaps: []\n", encoding="utf-8", newline="\n")
        cmd += ["--baseline", str(empty)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc


def _report(proc) -> dict:
    return json.loads(proc.stdout)


# The canonical network block the house uses: pmoves_* are internal:true
# (via the anchors), pmoves_public is the host-reachable egress tier.
# The anchors are defined FIRST -- YAML requires an anchor to exist before
# the alias that references it, exactly as the house does it in
# docker-compose.yml (anchors near the top, the networks block near the end).
CANONICAL = """
x-network-internal-only: &network-internal-only
  driver: bridge
  internal: true
x-network-tailnet-published: &network-tailnet-published
  driver: bridge
  internal: false
networks:
  pmoves_api:
    <<: *network-internal-only
    name: pmoves_api
  pmoves_app:
    <<: *network-internal-only
    name: pmoves_app
  pmoves_public:
    <<: *network-tailnet-published
    name: pmoves_public
"""


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------
def test_internal_only_service_is_reported(tmp_path):
    """Case 1 -- the defect class itself."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 1
    gap = rep["findings"][0]
    assert gap["kind"] == "UNACTIVATABLE_PORT"
    assert gap["service"] == "qdrant"
    assert gap["networks"] == ["pmoves_api"]


def test_non_internal_network_is_not_reported(tmp_path):
    """Case 2 -- attaching the host-reachable tier is the fix, not a defect."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  kong:
    ports:
      - "8000:8000"
    networks:
      - pmoves_api
      - pmoves_public
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 0
    assert rep["findings"] == []


def test_service_without_networks_key_is_not_a_gap(tmp_path):
    """Case 3 -- no networks key means the DEFAULT network, not a gap.

    This is the vacuous-truth regression: `all(...)` over an EMPTY set is
    True, so a naive implementation calls every port-less-network service a
    gap. Docker does the opposite -- such a service joins the default
    bridge and its port binds.
    """
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  plain:
    ports:
      - "9999:9999"
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 0
    assert rep["findings"] == []


def test_default_network_declared_internal_is_a_gap(tmp_path):
    """Case 3b -- but if the file declares its default network internal,
    a service with no networks key DOES land on an internal network."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
networks:
  default:
    driver: bridge
    internal: true
services:
  plain:
    ports:
      - "9999:9999"
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 1
    assert rep["findings"][0]["service"] == "plain"


def test_unknown_network_is_never_a_finding(tmp_path):
    """Case 4 -- an external network's internality is not knowable from
    source, so the gate must not guess."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": """
networks:
  somebody_elses:
    external: true
services:
  mystery:
    ports:
      - "9999:9999"
    networks:
      - somebody_elses
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 0


def test_canonical_inheritance_covers_the_split_overlay(tmp_path):
    """Case 5 -- the generated overlays reference pmoves_api without
    declaring it. A gate that only reads the file's own networks block is
    blind to every one of them."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  base-service:
    image: x
""",
        "docker-compose.core.yml": """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 1
    assert rep["findings"][0]["file"] == "docker-compose.core.yml"


def test_anchor_resolved_internality(tmp_path):
    """Case 6 -- the house declares pmoves_api through an anchor; a resolver
    that reads only literal keys sees UNKNOWN and misses the gap."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_app
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 1
    assert rep["findings"][0]["networks"] == ["pmoves_app"]


def test_unparseable_compose_file_fails_closed(tmp_path):
    """Case 7 -- a gate that cannot read its input must not report success."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  ok:
    image: x
""",
        "docker-compose.broken.yml": "services:\n  a: [unclosed\n",
    })
    proc = _run(pmoves)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rep = _report(proc)
    assert rep["instrument_errors"], rep
    assert rep["instrument_errors"][0]["file"] == "docker-compose.broken.yml"


def test_stale_baseline_entry_fails(tmp_path):
    """Case 8a -- a recorded gap that is no longer a gap fails the gate."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  clean:
    ports:
      - "9999:9999"
    networks:
      - pmoves_public
""",
    })
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: fixed-long-ago
    reason: it was broken once
""")
    rep = _report(_run(pmoves, baseline))
    assert any(f["kind"] == "STALE_GAP" for f in rep["findings"])


def test_placeholder_reason_fails(tmp_path):
    """Case 8b -- a recorded gap must carry a REVIEWED reason."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
""",
    })
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: REVIEW THIS
""")
    rep = _report(_run(pmoves, baseline))
    assert rep["gaps_measured"] == 1
    assert any(f["detail"] == "recorded without a reviewed reason"
               for f in rep["findings"])


def test_new_gap_not_in_baseline_fails(tmp_path):
    """Case 9 -- the baseline may not silently grow."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
""",
    })
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, "known_gaps: []\n")
    rep = _report(_run(pmoves, baseline))
    assert any(f["detail"] == "not in the baseline" for f in rep["findings"])


def test_exit_codes_are_the_house_convention(tmp_path):
    """0 clean, 1 drift, 3 COULD NOT MEASURE."""
    clean = _tree(tmp_path / "clean", {
        "docker-compose.yml": CANONICAL + """
services:
  ok:
    ports:
      - "9999:9999"
    networks:
      - pmoves_public
""",
    })
    assert _run(clean).returncode == 0

    drift = _tree(tmp_path / "drift", {
        "docker-compose.yml": CANONICAL + """
services:
  bad:
    ports:
      - "9999:9999"
    networks:
      - pmoves_api
""",
    })
    assert _run(drift).returncode == 1

    broken = _tree(tmp_path / "broken", {
        "docker-compose.yml": "services:\n  a: [unclosed\n",
    })
    assert _run(broken).returncode == 3


def test_real_tree_has_no_instrument_errors():
    """The real house scope must be fully readable -- otherwise the gate is
    reporting on a partial view and its exit code would be a lie."""
    proc = subprocess.run(
        [PYTHON, str(RATCHET), "--check", "--json",
         "--pmoves-dir", str(RATCHET.resolve().parents[1])],
        capture_output=True, text=True)
    rep = json.loads(proc.stdout)
    assert rep["instrument_errors"] == []
    assert rep["files_in_scope"] > 0


def test_real_tree_canonical_map_matches_the_house_doctrine():
    """pmoves_public is the host-reachable tier (internal:false); the
    pmoves_* tiers are internal:true. Both are stated in
    DOCKER_NETWORK_HARDENING.md -- the gate must resolve them that way."""
    proc = subprocess.run(
        [PYTHON, str(RATCHET), "--check", "--json",
         "--pmoves-dir", str(RATCHET.resolve().parents[1])],
        capture_output=True, text=True)
    canon = json.loads(proc.stdout)["canonical_networks"]
    assert canon.get("pmoves_public") is False
    assert canon.get("pmoves_api") is True
    assert canon.get("pmoves_app") is True
    assert canon.get("pmoves_bus") is True
    assert canon.get("pmoves_data") is True
    # pmoves_external / pmoves_db_egress are `external: true` -- compose does
    # not own them, so their internality is NOT knowable from source.
    assert canon.get("pmoves_external") is None
    assert canon.get("pmoves_db_egress") is None


def test_house_precedent_service_is_clean():
    """supabase-edge-runtime attaches pmoves_public precisely because
    pmoves_api is internal:true -- so it must NOT be reported."""
    proc = subprocess.run(
        [PYTHON, str(RATCHET), "--check", "--json",
         "--pmoves-dir", str(RATCHET.resolve().parents[1])],
        capture_output=True, text=True)
    rep = json.loads(proc.stdout)
    reported = {(f["file"], f["service"]) for f in rep["findings"]}
    assert ("docker-compose.yml", "supabase-edge-runtime") not in reported
