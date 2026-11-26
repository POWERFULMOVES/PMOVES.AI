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


def _run(pmoves: Path, baseline: Path | None = None, repo: Path | None = None,
         base_ref: str | None = None):
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
    if repo is not None:
        cmd += ["--repo", str(repo)]
    if base_ref is not None:
        cmd += ["--base-ref", base_ref]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)} failed:\n{proc.stderr}"
    return proc.stdout.strip()


def _base_repo(tmp_path: Path, base_files: dict, head_files: dict) -> tuple[Path, str]:
    """A git repo with a base commit and a head commit.

    Returns (repo, base_sha). The repo is a real git repository so the gate
    can materialize the base revision's compose files exactly as it does in
    CI -- no network, no clone, no fetch.
    """
    repo = tmp_path / "repo"
    (repo / "pmoves").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "gate@example.invalid")
    _git(repo, "config", "user.name", "Silent Bind Gate")
    _git(repo, "config", "commit.gpgsign", "false")

    for name, text in base_files.items():
        _write(repo / "pmoves" / name, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD")

    for name, text in head_files.items():
        _write(repo / "pmoves" / name, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    return repo, base_sha


QDRANT = """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
"""

QDRANT_AND_NEWCOMER = """
services:
  qdrant:
    ports:
      - "6333:6333"
    networks:
      - pmoves_api
  newcomer:
    ports:
      - "9999:9999"
    networks:
      - pmoves_api
"""


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


# --------------------------------------------------------------------------
# Case 11 -- the baseline may only SHRINK, measured against the base
# --------------------------------------------------------------------------
def test_baseline_addition_relative_to_the_base_is_rejected(tmp_path):
    """Case 11a -- the escape hatch this gate exists to close.

    A change that introduces a new internal-only published port AND adds the
    matching baseline entry compares CLEAN against the same checkout: the
    entry and the gap arrive together. So the gate measures the BASE
    revision too, and an entry for a gap that did not exist there is a
    BASELINE_ADDITION.
    """
    repo, base_sha = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT},
        head_files={"docker-compose.yml": CANONICAL + QDRANT_AND_NEWCOMER},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
  - file: docker-compose.yml
    service: newcomer
    reason: introduced by this change, so it looks fine
""")
    proc = _run(repo / "pmoves", baseline, repo=repo, base_ref=base_sha)
    rep = _report(proc)
    assert rep["base_gaps_measured"] == 1, rep
    additions = [f for f in rep["findings"] if f["kind"] == "BASELINE_ADDITION"]
    assert len(additions) == 1, rep["findings"]
    assert additions[0]["service"] == "newcomer"
    # The gap that DID exist at the base is not an addition.
    assert not any(f["kind"] == "BASELINE_ADDITION" and f["service"] == "qdrant"
                   for f in rep["findings"])
    assert proc.returncode == 1


def test_a_baseline_entry_for_a_base_gap_is_allowed(tmp_path):
    """Case 11b -- the rule must not block the legitimate case: a gap that
    already existed at the base revision may be recorded."""
    repo, base_sha = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT},
        head_files={"docker-compose.yml": CANONICAL + QDRANT_AND_NEWCOMER},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
""")
    proc = _run(repo / "pmoves", baseline, repo=repo, base_ref=base_sha)
    rep = _report(proc)
    # The newcomer is unrecorded, so it is a plain NEW finding -- and it is
    # NOT also a baseline addition.
    assert any(f["detail"] == "not in the baseline" for f in rep["findings"])
    assert not any(f["kind"] == "BASELINE_ADDITION" for f in rep["findings"])


def test_an_unreadable_base_revision_fails_closed(tmp_path):
    """Case 11c -- a gate that cannot read its base cannot judge the
    baseline, and must say so (exit 3) rather than report a clean tree."""
    repo, _ = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT},
        head_files={"docker-compose.yml": CANONICAL + QDRANT_AND_NEWCOMER},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
""")
    proc = _run(repo / "pmoves", baseline, repo=repo,
                base_ref="0000000000000000000000000000000000000000")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rep = _report(proc)
    assert rep["instrument_errors"], rep
    assert "base:" in rep["instrument_errors"][0]["file"]


def test_without_a_base_revision_the_rule_is_not_claimed(tmp_path):
    """Case 11d -- without a base revision there is nothing to compare
    against. The tool must say the rule is NOT enforced rather than imply
    it ran."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + QDRANT,
    })
    proc = subprocess.run(
        [PYTHON, str(RATCHET), "--check",
         "--pmoves-dir", str(pmoves),
         "--baseline", str(pmoves.parent / "empty.yaml")],
        capture_output=True, text=True)
    assert "NOT enforced" in proc.stdout, proc.stdout


def test_a_base_file_that_cannot_be_read_does_not_fail_the_run(tmp_path):
    """Case 11e -- a base file that will not parse contributes ZERO gaps.

    The tree being measured is a different thing from the base it is
    compared against. The measured tree must be fully readable -- that is
    exit 3, and it is not negotiable. A base file that cannot be parsed
    cannot have carried a measurable gap at the base, so a baseline entry
    naming it is reported as an ADDITION rather than quietly accepted.

    Without this, a change that REPAIRS a mangled compose file could not
    pass the gate that caught the mangling, because the base it is compared
    against is the mangled one. That is not a hypothetical: it is what
    PR #3519's mangled line would have done to the repair.
    """
    repo, base_sha = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT,
                    "docker-compose.broken.yml": "services:\n  a: [unclosed\n"},
        # The head REPAIRS the mangled file -- the scenario this rule exists
        # for. The repaired file publishes no port, so it measures no gaps.
        head_files={"docker-compose.yml": CANONICAL + QDRANT,
                    "docker-compose.broken.yml": "services:\n  repaired:\n    image: x\n"},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
""")
    proc = _run(repo / "pmoves", baseline, repo=repo, base_ref=base_sha)
    rep = _report(proc)
    # The base file that could not be read is reported, not swallowed.
    assert rep["base_instrument_errors"], rep
    assert "docker-compose.broken.yml" in rep["base_instrument_errors"][0]["file"]
    # It is NOT an instrument error of the tree being measured.
    assert rep["instrument_errors"] == [], rep
    # And the run did not fail closed on the base.
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_base_entry_for_an_unreadable_base_file_is_an_addition(tmp_path):
    """Case 11f -- the conservative direction, proven.

    A base file that cannot be read contributes ZERO gaps, so a baseline
    entry naming it IS an addition -- the fail-OPEN alternative (skipping
    such entries) would let the escape hatch back in through the base.
    """
    repo, base_sha = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT,
                    "docker-compose.broken.yml": "services:\n  a: [unclosed\n"},
        head_files={"docker-compose.yml": CANONICAL + QDRANT,
                    "docker-compose.broken.yml": "services:\n  repaired:\n    image: x\n"},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
  - file: docker-compose.broken.yml
    service: could-not-have-existed
    reason: the base file was unreadable, so this could not be a base gap
""")
    proc = _run(repo / "pmoves", baseline, repo=repo, base_ref=base_sha)
    rep = _report(proc)
    additions = [f for f in rep["findings"] if f["kind"] == "BASELINE_ADDITION"]
    assert len(additions) == 1, rep["findings"]
    assert additions[0]["service"] == "could-not-have-existed"
    assert proc.returncode == 1


def test_a_base_that_cannot_be_materialized_fails_closed(tmp_path):
    """Case 11g -- a base that cannot be materialized at all is an instrument
    error, and the run fails closed. There is no measurement to compare
    against, so the rule cannot be applied and must not be implied."""
    repo, _ = _base_repo(
        tmp_path,
        base_files={"docker-compose.yml": CANONICAL + QDRANT},
        head_files={"docker-compose.yml": CANONICAL + QDRANT_AND_NEWCOMER},
    )
    baseline = tmp_path / "baseline.yaml"
    _write(baseline, """
known_gaps:
  - file: docker-compose.yml
    service: qdrant
    reason: measured at the base revision
""")
    proc = _run(repo / "pmoves", baseline, repo=repo,
                base_ref="0000000000000000000000000000000000000000")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rep = _report(proc)
    assert rep["instrument_errors"], rep
    assert "base:" in rep["instrument_errors"][0]["file"]


def test_same_filename_in_two_scope_directories_does_not_collide(tmp_path):
    """Case 12 -- two files in the house scope share the name
    docker-compose.core.yml: pmoves/docker-compose.core.yml and
    pmoves/compose/docker-compose.core.yml. Keying the baseline on the bare
    filename lets them collide."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + QDRANT,
        "docker-compose.core.yml": CANONICAL + """
services:
  top-level:
    ports:
      - "9999:9999"
    networks:
      - pmoves_api
""",
        "compose/docker-compose.core.yml": CANONICAL + """
services:
  nested:
    ports:
      - "9998:9998"
    networks:
      - pmoves_api
""",
    })
    rep = _report(_run(pmoves))
    assert rep["gaps_measured"] == 3, rep
    files = {f["file"] for f in rep["findings"]}
    assert "docker-compose.core.yml" in files, files
    assert "compose/docker-compose.core.yml" in files, files


# --------------------------------------------------------------------------
# bind shape -- the tier split the remediation is scoped by
# --------------------------------------------------------------------------
def _load_ratchet():
    """Import the tool from its path, hermetically."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("silent_bind_ratchet", RATCHET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_port_with_no_host_address_is_implicit():
    """Docker's default host address is 0.0.0.0 when the mapping carries NO
    address at all. So a mapping with no address in it is WIDE at runtime,
    even though its text contains no "0.0.0.0" anywhere.

    This is the distinction the prior lane's count missed: it counted the
    mappings whose text said "0.0.0.0" and so under-counted the wide group.
    """
    sbr = _load_ratchet()
    assert sbr.classify_port("${SEMANTIC_CACHE_PORT:-8100}:8100") == sbr.BIND_IMPLICIT
    assert sbr.classify_port("${JAEGER_14250_PORT:-14250}:14250") == sbr.BIND_IMPLICIT
    assert sbr.classify_port("6333:6333") == sbr.BIND_IMPLICIT


def test_a_port_with_an_explicit_host_address_is_classified_by_that_address():
    sbr = _load_ratchet()
    assert sbr.classify_port(
        "${A2UI_BIND:-0.0.0.0}:${A2UI_NATS_BRIDGE_PORT:-9224}:9224") == sbr.BIND_WIDE
    assert sbr.classify_port(
        "${ALERTMANAGER_BIND:-127.0.0.1}:${ALERTMANAGER_PORT:-9093}:9093") == sbr.BIND_LOOPBACK


def test_a_literal_host_address_is_classified_and_not_swept_into_other():
    """Compose short syntax accepts an address with no environment
    indirection at all -- "127.0.0.1:8080:80". Such a mapping is exactly as
    knowable from source as a "${VAR:-127.0.0.1}" whose default is readable,
    so it must be classified rather than swept into OTHER.

    Codex P2 on PR #3522: bind_default() returned a value only for a
    "${VAR:-default}" expression, so every LITERAL address fell into OTHER
    and the --bind-shape counts would be wrong for any population that used
    one. This repo happens to use the indirection form everywhere, so the
    defect was invisible to the population it measures -- it was a REVIEW
    that found it, not a red test.
    """
    sbr = _load_ratchet()
    assert sbr.classify_port("0.0.0.0:8080:80") == sbr.BIND_WIDE
    assert sbr.classify_port("127.0.0.1:8080:80") == sbr.BIND_LOOPBACK


def test_the_component_count_beats_a_first_part_that_looks_like_an_address():
    """Compose decides by COUNT, not by what the text looks like: a
    two-component mapping is host_port:container_port, so "0.0.0.0:80" names
    a PORT named "0.0.0.0" (which Docker would reject) and carries NO host
    address at all. Reading it as "host 0.0.0.0" would put a port into the
    host-address slot -- the same category error the substitution case
    guards against.
    """
    sbr = _load_ratchet()
    assert sbr.classify_port("0.0.0.0:80") == sbr.BIND_IMPLICIT
    assert sbr.classify_port("127.0.0.1:80") == sbr.BIND_IMPLICIT
    host, host_port, container_port = sbr.split_port_spec("0.0.0.0:80")
    assert host is None
    assert host_port == "0.0.0.0"
    assert container_port == "80"


def test_a_bracketed_ipv6_literal_survives_the_split():
    """An IPv6 literal contains colons, which is WHY Compose requires the
    brackets in the short syntax ("[::1]:6001:6001"). Splitting on every
    colon shreds the address into "[", "", "1]", and the mapping would be
    filed as unreadable.
    """
    sbr = _load_ratchet()
    host, host_port, container_port = sbr.split_port_spec("[::1]:6001:6001")
    assert host == "[::1]"
    assert host_port == "6001"
    assert container_port == "6001"
    assert sbr.classify_port("[::1]:6001:6001") == sbr.BIND_LOOPBACK
    assert sbr.classify_port("[::]:6001:6001") == sbr.BIND_WIDE


def test_a_hostname_is_still_not_a_readable_address():
    """A literal that is not an IP address -- a hostname -- stays OTHER: it
    may resolve to anything, so claiming a bind class for it would be a
    guess, and a guess that manufactures a class is worse than an admission
    of ignorance.
    """
    sbr = _load_ratchet()
    assert sbr.classify_port("db.internal:8080:80") == sbr.BIND_OTHER
    assert sbr.classify_port("${BIND_VAR}:8080:80") == sbr.BIND_OTHER


def test_the_colon_inside_a_substitution_does_not_confuse_the_split():
    """The same trap the house smoke suite hit with _http_port: the colon
    inside "${BIND:-0.0.0.0}" is not a separator."""
    sbr = _load_ratchet()
    host, host_port, container_port = sbr.split_port_spec(
        "${A2UI_BIND:-0.0.0.0}:${A2UI_NATS_BRIDGE_PORT:-9224}:9224")
    assert host == "${A2UI_BIND:-0.0.0.0}"
    assert host_port == "${A2UI_NATS_BRIDGE_PORT:-9224}"
    assert container_port == "9224"


def test_a_two_component_mapping_has_no_host_address():
    """A two-component mapping is host_port:container_port. Reading the port
    expression as a host ADDRESS would be a category error -- it names a
    port, not an interface."""
    sbr = _load_ratchet()
    host, host_port, container_port = sbr.split_port_spec(
        "${SEMANTIC_CACHE_PORT:-8100}:8100")
    assert host is None
    assert host_port == "${SEMANTIC_CACHE_PORT:-8100}"
    assert container_port == "8100"


def test_a_service_with_one_implicit_port_is_wide_even_beside_a_loopback_port():
    """jaeger publishes 127.0.0.1 for its UI and NO address for its three
    collector ports. The service is WIDE at runtime, so it inherits the wide
    class rather than the reassuring one."""
    sbr = _load_ratchet()
    assert sbr.service_bind_class([
        "${JAEGER_BIND:-127.0.0.1}:${JAEGER_UI_PORT:-16686}:16686",
        "${JAEGER_14268_PORT:-14268}:14268",
    ]) == sbr.CLASS_WIDE_OR_IMPLICIT
    assert sbr.service_bind_class([
        "${ALERTMANAGER_BIND:-127.0.0.1}:${ALERTMANAGER_PORT:-9093}:9093",
    ]) == sbr.CLASS_LOOPBACK


def test_the_bind_shape_counts_entries_and_services_separately():
    """A claim that mixes the units is how "37 services bound to 0.0.0.0" gets
    written when the truth is 37 ENTRIES across 20 SERVICES."""
    sbr = _load_ratchet()
    gaps = [
        {"file": "docker-compose.yml", "service": "wide-svc",
         "ports": ["${B:-0.0.0.0}:${P:-1}:1"]},
        {"file": "docker-compose.core.yml", "service": "wide-svc",
         "ports": ["${B:-0.0.0.0}:${P:-1}:1"]},
        {"file": "docker-compose.yml", "service": "loop-svc",
         "ports": ["${B:-127.0.0.1}:${P:-2}:2"]},
        {"file": "docker-compose.core.yml", "service": "loop-svc",
         "ports": ["${B:-127.0.0.1}:${P:-2}:2"]},
    ]
    shape = sbr.bind_shape(gaps)
    assert shape["entries"] == 4, shape
    assert shape["services"] == 2, shape
    assert shape["entries_by_class"]["wide_or_implicit"] == 2, shape
    assert shape["services_by_class"]["wide_or_implicit"] == 1, shape
    assert shape["services_by_class"]["loopback"] == 1, shape


def test_the_report_carries_the_bind_shape(tmp_path):
    """The shape travels with the report so a claim about the tier split can
    be recomputed instead of asserted."""
    pmoves = _tree(tmp_path, {
        "docker-compose.yml": CANONICAL + QDRANT,
    })
    rep = _report(_run(pmoves))
    assert "bind_shape" in rep, rep
    assert rep["bind_shape"]["entries"] == rep["gaps_measured"], rep
    assert rep["bind_shape"]["services"] == rep["gap_services"], rep
    # "6333:6333" carries no host address -> implicit -> wide at runtime
    assert rep["bind_shape"]["ports_by_class"]["implicit"] == 1, rep
    assert rep["bind_shape"]["services_by_class"]["wide_or_implicit"] == 1, rep


def test_an_empty_baseline_says_so_in_its_own_header(tmp_path):
    """The empty baseline is a real state with its own meaning -- every
    measured gap is fixed, so the gate now fails on ANY new gap. A header
    that still describes a populated list makes the reviewer guess whether
    the emptiness is intentional."""
    sbr = _load_ratchet()
    out = tmp_path / "baseline.yaml"
    assert sbr.write_baseline([], out) == 0
    text = out.read_text(encoding="utf-8")
    assert "THIS LIST IS EMPTY" in text, text
    assert "known_gaps: []" in text, text
