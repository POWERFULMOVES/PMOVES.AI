"""Validate the validator.

Every detector in disconnection_audit is asserted to FIRE on the ground-truth
fixture measured on PMOVES-B850-AI-TOP on 2026-09-08, and to stay CLEAN on a
known-good counterpart that differs from the fixture in exactly one way.

A detector that cannot fail is the very defect being hunted. These tests are
what stop this tool from becoming instance #6, so the negative cases (the
counterparts) matter as much as the positive ones -- a detector that fires on
everything is as useless as one that fires on nothing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import disconnection_audit as da  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 9, 8, 21, 0, 0, tzinfo=timezone.utc)


# ==========================================================================
# Parsing -- the layer every detector sits on
# ==========================================================================


def test_parses_the_three_port_shapes_this_fleet_emits():
    exposed = da.parse_port_bindings("8090/tcp")
    assert exposed == [], "exposed-but-unpublished is not a host binding"

    wildcard = da.parse_port_bindings("0.0.0.0:8088->8080/tcp, [::]:8088->8080/tcp")
    assert [b.host_port for b in wildcard] == [8088, 8088]
    assert all(b.is_wildcard for b in wildcard)

    loop = da.parse_port_bindings("127.0.0.1:8105->8105/tcp")
    assert loop[0].is_loopback and loop[0].host_port == 8105

    rng = da.parse_port_bindings("127.0.0.1:8000-8001->8000-8001/tcp")
    assert [b.host_port for b in rng] == [8000, 8001]
    assert all(b.is_loopback for b in rng)


def test_health_is_read_from_the_status_line():
    assert da.health_from_status("Up 5 days (healthy)") == "healthy"
    assert da.health_from_status("Up 5 days (unhealthy)") == "unhealthy"
    assert da.health_from_status("Up 5 days") is None
    # No healthcheck at all still counts as "reporting fine" -- promtail has
    # none, and it is the D2 fixture.
    assert da.Container("promtail", "Up 5 days", None).looks_green is True
    assert da.Container("x", "Up 5 days (unhealthy)", "unhealthy").looks_green is False


# ==========================================================================
# Exit-code doctrine
# ==========================================================================


def test_could_not_measure_never_collapses_to_clean():
    clean = [da.Finding("D1", "a", da.CLEAN, "")]
    assert da.aggregate_exit_code(clean) == da.EXIT_CLEAN

    mixed = clean + [da.Finding("D2", "b", da.CNM, "")]
    assert da.aggregate_exit_code(mixed) == da.EXIT_COULD_NOT_MEASURE, (
        "an unmeasured subject is an unknown, not a pass")

    with_fire = mixed + [da.Finding("D3", "c", da.FIRE, "")]
    assert da.aggregate_exit_code(with_fire) == da.EXIT_FINDINGS

    assert da.aggregate_exit_code([]) == da.EXIT_CLEAN


def test_json_verdict_carries_the_exit_code_make_would_destroy():
    # `make` collapses every nonzero recipe exit to 2, so 1 and 3 are
    # indistinguishable through the fleet's standard invocation. The structured
    # verdict is the channel that survives it.
    report = da.build_report([da.Finding("D2", "x", da.CNM, "r")], node="test")
    assert report["exit_code"] == da.EXIT_COULD_NOT_MEASURE
    assert report["verdict"] == "could-not-measure"
    assert json.loads(json.dumps(report))["exit_code"] == 3


# ==========================================================================
# D1 -- fixture 1: cipher-api healthy, /health 200, bound 127.0.0.1:8105
# ==========================================================================

DECL_8105 = [da.Declaration("${TS_Z890}", 8105, ".claude/mcp.json", "fleet-host-url")]
DECL_8091 = [da.Declaration("${TS_Z890}", 8091, ".claude/mcp.json", "fleet-host-url")]


def test_d1_FIRES_on_the_cipher_fixture():
    cipher = da.Container(
        "pmoves-cipher-api-1", "Up 4 days (healthy)", "healthy",
        da.parse_port_bindings("127.0.0.1:8105->8105/tcp"))
    out = da.detect_d1([cipher], da.declared_fleet_ports(DECL_8105))
    assert [f.verdict for f in out] == [da.FIRE]
    assert "unreachable from any peer" in out[0].reason


def test_d1_stays_CLEAN_on_the_known_good_counterpart():
    # Differs from the fixture in exactly one way: the bind address.
    gateway = da.Container(
        "pmoves-mcp-gateway", "Up 5 days (healthy)", "healthy",
        da.parse_port_bindings("0.0.0.0:8091->8091/tcp, [::]:8091->8091/tcp"))
    out = da.detect_d1([gateway], da.declared_fleet_ports(DECL_8091))
    assert [f.verdict for f in out] == [da.CLEAN]


def test_d1_ignores_a_loopback_port_no_peer_is_told_to_dial():
    private = da.Container(
        "pmoves-yt-cookie-refresher-1", "Up 5 days (healthy)", "healthy",
        da.parse_port_bindings("127.0.0.1:8115->8115/tcp"))
    assert da.detect_d1([private], da.declared_fleet_ports(DECL_8105)) == []


def test_d1_does_not_blame_a_service_a_sidecar_bridge_already_publishes():
    # pmoves-registry-port-bridge republishes :8110 on a wildcard. Reachability
    # is a property of the host port, not of one container.
    svc = da.Container("pmoves-model-registry-1", "Up (healthy)", "healthy",
                       da.parse_port_bindings("127.0.0.1:8110->8110/tcp"))
    bridge = da.Container("pmoves-registry-port-bridge", "Up", None,
                          da.parse_port_bindings("0.0.0.0:8110->8110/tcp"))
    decl = [da.Declaration("pmoves-b850", 8110, ".claude/CATALOG.md",
                           "catalog-node-service")]
    out = da.detect_d1([svc, bridge], da.declared_fleet_ports(decl))
    assert {f.verdict for f in out} == {da.CLEAN}


# ==========================================================================
# D2 -- fixture 2: promtail Up 5 days, same docker-socket error every 5s
# ==========================================================================

PROMTAIL_ERR = (
    'level=error ts=2026-09-08T21:10:39.851702956Z caller=refresh.go:90 '
    'component=docker_discovery discovery=docker msg="Unable to refresh target '
    'groups" err="error while listing containers: Cannot connect to the Docker '
    'daemon at unix:///var/run/docker.sock. Is the docker daemon running?"'
)

PROMTAIL = da.Container("monitoring-promtail-1", "Up 5 days", None, [])
HEALTHY = da.Container("monitoring-loki-1", "Up 5 days (healthy)", "healthy", [])


def _lines(text: str, count: int, start_min_ago: int = 1, spacing_s: int = 2):
    """`count` copies of `text`, each with a DIFFERENT timestamp.

    Spacing is kept tight on purpose: at 5s spacing 180 lines span 15 minutes
    and half of them fall outside the default window, which silently halves
    the count the assertions are about.
    """
    return [(NOW - timedelta(minutes=start_min_ago, seconds=spacing_s * i), text)
            for i in range(count)]


def _d2(container, lines, **kw):
    kw.setdefault("window_minutes", 15)
    kw.setdefault("repeat_threshold", 5)
    kw.setdefault("tail", 400)
    return da.detect_d2([container], lambda n, t: lines, now=NOW, **kw)


def test_d2_FIRES_on_the_promtail_fixture():
    out = _d2(PROMTAIL, _lines(PROMTAIL_ERR, 180))
    assert [f.verdict for f in out] == [da.FIRE]
    assert out[0].evidence["top_signature_count"] == 180
    assert out[0].evidence["lines_in_window"] == 180


def test_d2_signature_survives_the_rotating_timestamp():
    # The whole detector rests on this: every promtail line is unique verbatim
    # and identical after normalisation. Counting raw lines would find 1 each.
    sigs = {da.error_signature(t) for _, t in _lines(PROMTAIL_ERR, 20)}
    assert len(sigs) == 1


def test_d2_stays_CLEAN_on_a_healthy_chatty_service():
    info = [(NOW - timedelta(seconds=5 * i),
             f"level=info ts=2026-09-08T21:0{i%10}:00Z msg=\"flushed chunk\"")
            for i in range(180)]
    assert [f.verdict for f in _d2(HEALTHY, info)] == [da.CLEAN]


def test_d2_stays_CLEAN_below_the_repeat_threshold():
    out = _d2(PROMTAIL, _lines(PROMTAIL_ERR, 4), repeat_threshold=5)
    assert [f.verdict for f in out] == [da.CLEAN]
    assert out[0].evidence["top_signature_count"] == 4


def test_d2_threshold_and_window_are_parameters_not_magic_numbers():
    lines = _lines(PROMTAIL_ERR, 10)
    assert _d2(PROMTAIL, lines, repeat_threshold=11)[0].verdict == da.CLEAN
    assert _d2(PROMTAIL, lines, repeat_threshold=10)[0].verdict == da.FIRE
    # Same errors, pushed outside a narrower window -> conclusive silence.
    old = _lines(PROMTAIL_ERR, 10, start_min_ago=60)
    assert _d2(PROMTAIL, old, window_minutes=15)[0].verdict == da.CLEAN


def test_d2_skips_a_container_that_is_already_reporting_badly():
    sick = da.Container("x", "Up 5 days (unhealthy)", "unhealthy", [])
    assert _d2(sick, _lines(PROMTAIL_ERR, 180)) == []


def test_d2_reports_COULD_NOT_MEASURE_rather_than_guessing():
    def boom(name, tail):
        raise da.DockerUnavailable("daemon socket gone")

    out = da.detect_d2([PROMTAIL], boom, window_minutes=15,
                       repeat_threshold=5, tail=400, now=NOW)
    assert [f.verdict for f in out] == [da.CNM]

    # Zero lines from a running container is ambiguous, never a pass.
    assert _d2(PROMTAIL, [])[0].verdict == da.CNM
    # Lines with no parseable timestamp cannot be windowed.
    assert _d2(PROMTAIL, [(None, PROMTAIL_ERR)] * 50)[0].verdict == da.CNM


def test_d2_always_publishes_both_input_sizes():
    # An empty result reads the same whether the service was quiet or the read
    # returned nothing. Both counts are always present so it cannot be misread.
    for lines in ([], _lines(PROMTAIL_ERR, 3), [(None, "x")]):
        ev = _d2(PROMTAIL, lines)[0].evidence
        assert "lines_examined" in ev and "lines_in_window" in ev


def test_d2_reads_container_stderr_not_only_stdout(monkeypatch):
    """Regression: promtail logs 100% to stderr.

    Measured 2026-09-08 -- returning only proc.stdout gave promtail zero lines,
    so D2 could not see its own ground-truth fixture. The merge is asserted at
    the subprocess boundary because that is where the mistake was made.
    """
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = "2026-09-08T21:10:39.000000000Z " + PROMTAIL_ERR + "\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["stderr"] = kwargs.get("stderr")
        return FakeProc()

    monkeypatch.setattr(da.subprocess, "run", fake_run)
    out = da.DockerProbe().logs("monitoring-promtail-1", 400)
    assert seen["stderr"] is da.subprocess.STDOUT, "container stderr must be merged"
    assert "--tail" in seen["cmd"] and "--timestamps" in seen["cmd"]
    assert "--since" not in seen["cmd"], (
        "--since silently returns zero lines on this host -- see module docstring")
    assert len(out) == 1 and out[0][0] is not None


# ==========================================================================
# D3 -- fixture 4: hardware_requirements.cpu_arch, declared, read by nothing
# ==========================================================================


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> Path:
    cfg = tmp_path / "pmoves" / "config"
    cfg.mkdir(parents=True)
    (cfg / "a.room.json").write_text(json.dumps({
        "room_id": "demo.room",
        "hardware_requirements": {"cpu_arch": ["x86_64"], "gpu": "any"},
    }))
    svc = tmp_path / "pmoves" / "services" / "p7"
    svc.mkdir(parents=True)
    (svc / "catalog.py").write_text(
        'def find(rows, room_id):\n'
        '    for row in rows:\n'
        '        if row.get("room_id") == room_id:\n'
        '            return row\n'
        '# cpu_arch is mentioned here but never read -- a comment is not a reader\n'
        '\n'
        'def documented():\n'
        '    """Summary line.\n'
        '\n'
        '    A room declares hardware_requirements.cpu_arch, and this sentence\n'
        '    is prose about it on an INTERIOR docstring line -- the line does\n'
        '    not start with a quote, so the comment-prefix check cannot see it.\n'
        '    Only stripping the triple-quoted block keeps it out of the read set.\n'
        '    """\n'
        '    return None\n'
    )
    return tmp_path


def test_strip_py_string_blocks_blanks_interior_docstring_lines():
    src = (
        'def f():\n'
        '    """doc\n'
        '    mentions obj.cpu_arch here\n'
        '    """\n'
        '    return cfg.get("cpu_arch")\n'
    )
    stripped = da.strip_py_string_blocks(src)
    assert "obj.cpu_arch" not in stripped, "prose inside a docstring must not survive"
    assert 'cfg.get("cpu_arch")' in stripped, "real code must survive"
    # Line count is preserved so any reported line number stays true.
    assert len(stripped.splitlines()) == len(src.splitlines())


def test_strip_py_string_blocks_leaves_a_single_line_docstring_harmless():
    src = 'def f():\n    """mentions x.cpu_arch"""\n    return 1\n'
    assert "x.cpu_arch" not in da.strip_py_string_blocks(src)


def test_d3_shows_BOTH_outcomes_on_a_synthetic_repo(synthetic_repo):
    out = {f.subject: f for f in da.detect_d3(synthetic_repo, ["cpu_arch", "room_id"])}
    assert out["cpu_arch"].verdict == da.FIRE
    assert out["cpu_arch"].evidence["read_in_count"] == 0
    assert out["cpu_arch"].evidence["declared_in_count"] == 1
    assert out["room_id"].verdict == da.CLEAN
    assert out["room_id"].evidence["read_in_count"] == 1


def test_d3_does_not_count_comments_or_docstrings_as_readers(synthetic_repo):
    # This is the exact false CLEAN measured on 2026-09-08: the phrase
    # `hardware_requirements.cpu_arch` in prose satisfied a naive `.field` grep.
    assert da.detect_d3(synthetic_repo, ["cpu_arch"])[0].verdict == da.FIRE


def test_d3_reports_COULD_NOT_MEASURE_for_an_undeclared_field(synthetic_repo):
    out = da.detect_d3(synthetic_repo, ["no_such_field_anywhere"])
    assert out[0].verdict == da.CNM


def test_d3_excludes_itself_from_the_scan():
    # The tool names every field it hunts. Without the exclusion it finds
    # itself and reports every field as read.
    assert da.SELF_PATH.name == "disconnection_audit.py"
    out = da.detect_d3(REPO_ROOT, ["cpu_arch"], search_roots=("pmoves/tools",))
    assert out[0].evidence["read_in_count"] == 0


@pytest.mark.skipif(not (REPO_ROOT / "pmoves" / "config" / "rooms").is_dir(),
                    reason="repo room manifests unavailable (worktree/partial checkout)")
def test_d3_on_the_REAL_repo_fixture_and_its_matched_control():
    """cpu_arch and room_id are declared in the SAME room manifests.

    They differ in exactly one way -- whether any code reads them -- which is
    what makes room_id a control rather than merely another data point.
    """
    out = {f.subject: f for f in da.detect_d3(REPO_ROOT, list(da.DEFAULT_D3_FIELDS))}
    assert out["cpu_arch"].verdict == da.FIRE, out["cpu_arch"].evidence
    assert out["cpu_arch"].evidence["declared_in_count"] > 0
    assert out["cpu_arch"].evidence["read_in_count"] == 0
    assert out["room_id"].verdict == da.CLEAN, out["room_id"].evidence
    assert out["room_id"].evidence["read_in_count"] > 0


# ==========================================================================
# D4 -- fixture 5: TS_Z890 correct, host reachable, :8105 closed
# ==========================================================================


class FakeNet(da.NetProbe):
    def __init__(self, *, resolves=True, tcp="open", mesh=True):
        super().__init__()
        self._resolves, self._tcp, self._mesh = resolves, tcp, mesh

    def resolves(self, host):
        return self._resolves

    def tcp(self, host, port):
        return self._tcp

    def mesh_reachable(self, host):
        return self._mesh


CIPHER_DECL = [da.Declaration("${TS_Z890}", 8105, ".claude/mcp.json",
                              "fleet-host-url")]
ENV_OK = {"TS_Z890": "a-host-name"}


def _d4(probe, env=ENV_OK, decls=CIPHER_DECL):
    return da.detect_d4(decls, probe, env=env)


def test_d4_FIRES_on_the_z890_cipher_fixture():
    # Config right, mesh carries, nothing listening -> service absent.
    out = _d4(FakeNet(tcp="refused"))
    assert [f.verdict for f in out] == [da.FIRE]
    assert out[0].evidence["classification"] == da.R_PORT_CLOSED


def test_d4_stays_CLEAN_when_something_actually_answers():
    out = _d4(FakeNet(tcp="open"))
    assert [f.verdict for f in out] == [da.CLEAN]
    assert out[0].evidence["classification"] == da.R_LISTENING


def test_d4_discriminates_the_three_failure_modes():
    """HTTP 000 meant an expired node key, not a down service.

    Collapsing these three into "down" sends someone to restart a container
    that was never the problem, so each has to come back distinctly.
    """
    wrong = _d4(FakeNet(resolves=False))[0]
    assert wrong.evidence["classification"] == da.R_ADDRESS_WRONG

    dead = _d4(FakeNet(tcp="timeout", mesh=False))[0]
    assert dead.evidence["classification"] == da.R_TRANSPORT_DEAD

    closed = _d4(FakeNet(tcp="timeout", mesh=True))[0]
    assert closed.evidence["classification"] == da.R_PORT_CLOSED

    assert len({wrong.evidence["classification"],
                dead.evidence["classification"],
                closed.evidence["classification"]}) == 3


def test_d4_cannot_measure_without_a_mesh_prober():
    out = _d4(FakeNet(tcp="timeout", mesh=None))
    assert [f.verdict for f in out] == [da.CNM]


def test_d4_unset_env_var_is_could_not_measure_not_a_pass():
    out = _d4(FakeNet(tcp="open"), env={})
    assert [f.verdict for f in out] == [da.CNM]
    assert out[0].evidence["env_var"] == "TS_Z890"


def test_d4_never_records_a_resolved_address():
    """No LAN or tailnet addresses in output -- names and ports only."""
    secret_host = "host-value-that-must-not-appear"
    out = _d4(FakeNet(tcp="refused"), env={"TS_Z890": secret_host})
    blob = json.dumps(da.build_report(out, node="test"))
    assert secret_host not in blob
    assert "TS_Z890" in blob  # the NAME is kept; the value is not


# ==========================================================================
# Repo evidence -- "declared fleet-reachable" is derived, never hardcoded
# ==========================================================================


def test_fleet_hosts_come_from_the_node_vocabulary(tmp_path):
    (tmp_path / "pmoves" / "configs").mkdir(parents=True)
    (tmp_path / "pmoves" / "configs" / "node-vocabulary.yaml").write_text(
        "version: 1\nnodes:\n- canonical: '5090'\n  reach: pmoves-5090\n")
    assert da.load_node_reach_names(tmp_path) == {"pmoves-5090"}


def test_a_compose_service_name_is_not_a_fleet_declaration(tmp_path):
    """`http://cipher-api:8105` means the container next door, not a peer.

    Treating compose names as fleet declarations would flag every loopback
    binding in the stack and drown the real finding.
    """
    cfgs = tmp_path / "pmoves" / "configs"
    cfgs.mkdir(parents=True)
    (cfgs / "node-vocabulary.yaml").write_text(
        "nodes:\n  - canonical: '5090'\n    reach: pmoves-5090\n")
    cfg = tmp_path / "pmoves" / "config"
    cfg.mkdir(parents=True)
    (cfg / "x.yaml").write_text(
        "a: http://cipher-api:8105\n"
        "b: http://${TS_Z890}:8105\n"
        "c: http://pmoves-5090:8055\n"
        "d: http://localhost:9999\n")
    ports = {(d.host_expr, d.port) for d in da.discover_declarations(tmp_path)}
    assert ("${TS_Z890}", 8105) in ports
    assert ("pmoves-5090", 8055) in ports
    assert not any(h == "cipher-api" for h, _ in ports)
    assert 9999 not in {p for _, p in ports}


@pytest.mark.skipif(not (REPO_ROOT / ".claude" / "mcp.json").exists(),
                    reason="repo config unavailable")
def test_real_repo_declares_the_cipher_port_as_fleet_reachable():
    decls = da.discover_declarations(REPO_ROOT)
    assert decls, "no declarations parsed -- D1/D4 would silently judge nothing"
    assert 8105 in da.declared_fleet_ports(decls), (
        "the cipher fixture depends on :8105 being a derived declaration")
