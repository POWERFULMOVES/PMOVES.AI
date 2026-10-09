"""The MCP roster normalizer must announce what it cannot resolve.

A server whose ``url`` is ``http://${TS_Z890}:8105/mcp/sse`` with TS_Z890 unset
used to sail through the launcher looking perfectly configured. Claude Code's
documented behaviour is to warn and then send the literal ``${TS_Z890}`` as a
hostname, so the connection died somewhere no agent could observe -- one
session lost its entire memory layer and could not distinguish that from
"cipher is down".

These tests pin the verdict rules: an unresolvable ``url`` is DROPPED and
NAMED, an unresolvable credential is KEPT and NAMED, a resolvable one is
expanded. They live here rather than in deploy/provision/tests/ because that
directory's one test is wired into no CI job and no Make target -- and a test
nobody runs is the same defect class this whole change is about.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "mcp_roster_normalize.py"
LAUNCHER = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh"
LAUNCHER_PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"
TS_HELPER = REPO_ROOT / "pmoves" / "scripts" / "tailscale-node-ips.sh"
CRUSH_ENV = REPO_ROOT / "pmoves" / "scripts" / "crush-env.sh"
REAL_ROSTER = REPO_ROOT / ".claude" / "mcp.json"

sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
import mcp_roster_normalize as norm  # noqa: E402


def _roster(**servers):
    return {"mcpServers": dict(servers)}


# --------------------------------------------------------------------------
# P5 verdict: url misses DROP, credential misses WARN-and-keep
# --------------------------------------------------------------------------


def test_unset_var_in_url_drops_the_server_and_names_the_variable():
    data = _roster(**{"pmoves-cipher": {"type": "sse", "url": "http://${TS_Z890}:8105/mcp/sse"}})
    clean, dropped, degraded = norm.normalize(data, "/repo", {})

    assert "pmoves-cipher" not in clean["mcpServers"], "unresolvable server was handed to Claude"
    assert dropped == [("pmoves-cipher", ["TS_Z890"])]
    assert degraded == []


def test_set_var_in_url_keeps_the_server_and_expands_it():
    data = _roster(**{"pmoves-cipher": {"type": "sse", "url": "http://${TS_Z890}:8105/mcp/sse"}})
    clean, dropped, degraded = norm.normalize(data, "/repo", {"TS_Z890": "node.example"})

    assert (dropped, degraded) == ([], [])
    assert clean["mcpServers"]["pmoves-cipher"]["url"] == "http://node.example:8105/mcp/sse"


def test_every_missing_variable_is_named_not_just_the_first():
    data = _roster(**{
        "agent-zero": {"url": "http://${TS_Z890}:8081/mcp/t-${AGENT_ZERO_MCP_TOKEN}/sse"},
    })
    _clean, dropped, _deg = norm.normalize(data, "/repo", {})
    assert dropped == [("agent-zero", ["AGENT_ZERO_MCP_TOKEN", "TS_Z890"])]


def test_an_unset_credential_is_announced_but_the_server_survives():
    """Several servers treat an absent credential as 'run anonymously'.

    huggingface's own roster note calls HF_TOKEN a rate-limit upgrade, and
    cloudflare authenticates through the local wrangler session. Dropping those
    would remove working servers to fix a different bug.
    """
    data = _roster(
        huggingface={"command": "npx", "env": {"HF_TOKEN": "${HF_TOKEN}"}},
        gateway={"url": "http://localhost:8090/sse",
                 "headers": {"Authorization": "Bearer ${MCP_GATEWAY_AUTH_TOKEN}"}},
    )
    clean, dropped, degraded = norm.normalize(data, "/repo", {})

    assert dropped == []
    assert sorted(clean["mcpServers"]) == ["gateway", "huggingface"]
    assert dict(degraded) == {
        "huggingface": ["HF_TOKEN"],
        "gateway": ["MCP_GATEWAY_AUTH_TOKEN"],
    }


def test_an_exported_empty_string_counts_as_missing():
    """An empty export satisfies a presence check and yields http://:8105/."""
    data = _roster(cipher={"url": "http://${TS_Z890}:8105/mcp/sse"})
    _clean, dropped, _deg = norm.normalize(data, "/repo", {"TS_Z890": ""})
    assert dropped == [("cipher", ["TS_Z890"])]


def test_one_bad_server_does_not_take_the_others_down():
    data = _roster(
        bad={"url": "http://${NOPE}:1/x"},
        good={"url": "https://mcp.cloudflare.com/mcp"},
    )
    clean, dropped, _deg = norm.normalize(data, "/repo", {})
    assert list(clean["mcpServers"]) == ["good"]
    assert [n for n, _ in dropped] == ["bad"]


def test_a_disabled_server_gets_no_special_case():
    """`disabled` is a Cline/Roo key, not in Claude Code's documented schema.

    Trusting it as an off-switch would bet the exact silent failure this module
    prevents on an assumption, so it is checked like any other server.
    """
    data = _roster(archon={"url": "http://${TS_Z890}:8051", "disabled": True})
    clean, dropped, _deg = norm.normalize(data, "/repo", {})
    assert dropped == [("archon", ["TS_Z890"])]

    clean, dropped, _deg = norm.normalize(data, "/repo", {"TS_Z890": "node.example"})
    assert dropped == []
    assert clean["mcpServers"]["archon"]["url"] == "http://node.example:8051"


# --------------------------------------------------------------------------
# default forms -- these must NOT be treated as missing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,environ,expected",
    [
        ("Bearer ${CIPHER_API_TOKEN:-}", {}, "Bearer "),
        ("${A:-fallback}", {}, "fallback"),
        ("${A:-fallback}", {"A": "real"}, "real"),
        ("${A:-fallback}", {"A": ""}, "fallback"),
        ("${A:-${B}}", {"B": "nested"}, "nested"),
        ("${A:-${B:-deep}}", {}, "deep"),
        ("${A:-${B}}", {"A": "outer", "B": "inner"}, "outer"),
        ("${URL:-http://localhost:8000/rest/v1}", {}, "http://localhost:8000/rest/v1"),
        # the ':' inside a URL default must not be mistaken for a separator
        ("${H:-https://api.example.com:8443/v1}", {}, "https://api.example.com:8443/v1"),
        ("no references here", {}, "no references here"),
        ("$NOT_BRACED", {}, "$NOT_BRACED"),
    ],
)
def test_default_forms_resolve_without_being_flagged(text, environ, expected):
    missing: list[str] = []
    assert norm.expand(text, environ, missing) == expected
    assert missing == []


def test_a_server_using_only_defaults_survives_an_empty_environment():
    data = _roster(cipher={
        "url": "http://localhost:8105/mcp/sse",
        "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN:-}"},
    })
    clean, dropped, degraded = norm.normalize(data, "/repo", {})
    assert (dropped, degraded) == ([], [])
    assert clean["mcpServers"]["cipher"]["headers"]["Authorization"] == "Bearer "


def test_a_failed_fallback_chain_names_the_primary_variable_first():
    """The inner name is usually a deprecated alias; telling an operator to set
    that is telling them the wrong thing."""
    missing: list[str] = []
    norm.expand("${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY}}", {}, missing)
    assert missing == ["SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY"]


# --------------------------------------------------------------------------
# malformed references must be reported, never guessed at
# --------------------------------------------------------------------------


def test_the_posix_dash_default_form_is_refused_not_guessed():
    """``${TS-Z890}`` is one keystroke from ``${TS_Z890}``.

    Under POSIX rules it means "TS, defaulting to Z890" and would silently
    produce the plausible hostname http://Z890:8105/ -- no warning, no drop,
    strictly worse than the bug this module fixes. An identifier check does not
    catch it either, because ``TS`` is a valid identifier. The form is refused.
    """
    missing: list[str] = []
    assert norm.expand("http://${TS-Z890}:8105/x", {}, missing) == "http://${TS-Z890}:8105/x"
    assert missing == ["${TS-Z890}"]


@pytest.mark.parametrize("text", ["${ }", "${}", "${UNBALANCED", "${A:-{}"])
def test_malformed_references_are_reported_not_swallowed(text):
    missing: list[str] = []
    norm.expand(text, {}, missing)
    assert missing, f"{text!r} passed through silently"


def test_a_malformed_url_reference_drops_the_server():
    data = _roster(bad={"url": "http://${TS-Z890}:8105/x"})
    _clean, dropped, _deg = norm.normalize(data, "/repo", {})
    assert [n for n, _ in dropped] == ["bad"]


# --------------------------------------------------------------------------
# P2 / P3 -- preserved from the heredoc this replaced
# --------------------------------------------------------------------------


def test_underscore_prefixed_servers_are_still_dropped():
    data = _roster(**{"_legacy": {"command": "uv"}, "live": {"command": "uv"}})
    clean, _d, _g = norm.normalize(data, "/repo", {})
    assert list(clean["mcpServers"]) == ["live"]


def test_relative_launch_paths_are_still_made_absolute():
    data = _roster(nats={"command": "uv", "args": ["--directory", "./pmoves-nats-mcp", "run"]})
    clean, _d, _g = norm.normalize(data, "/repo", {})
    assert clean["mcpServers"]["nats"]["args"][1] == os.path.join("/repo", "pmoves-nats-mcp")


def test_normalize_does_not_mutate_the_tracked_roster():
    data = _roster(cipher={"url": "http://${TS_Z890}:1/x", "args": ["./rel"]})
    norm.normalize(data, "/repo", {"TS_Z890": "node.example"})
    assert data["mcpServers"]["cipher"]["url"] == "http://${TS_Z890}:1/x"
    assert data["mcpServers"]["cipher"]["args"] == ["./rel"]


# --------------------------------------------------------------------------
# the REAL roster -- guards against a regression nobody notices until launch
# --------------------------------------------------------------------------


def test_the_real_roster_keeps_its_optional_credential_servers():
    """Regression guard: these have no ``:-`` default, and dropping them on an
    unset credential would silently shrink every operator's toolset."""
    data = json.loads(REAL_ROSTER.read_text())
    clean, dropped, _deg = norm.normalize(data, "/repo", {})
    names = set(clean["mcpServers"])
    for server in ("huggingface", "cloudflare", "pmoves-4090-web", "pmoves-supabase"):
        assert server in names, f"{server} dropped on an empty environment"
    assert {n for n, _ in dropped} == {"pmoves-cipher", "agent-zero"}
    # archon left the MCP roster with the Python-Archon surface retirement
    # (native 0.6.0 REST-only, fleet decision #2303): it can no longer be
    # dropped on an empty environment because it is no longer an MCP server.


def test_the_real_roster_is_fully_resolvable_when_the_tailnet_resolves():
    data = json.loads(REAL_ROSTER.read_text())
    env = {"TS_Z890": "node.example", "AGENT_ZERO_MCP_TOKEN": "tok"}
    _clean, dropped, _deg = norm.normalize(data, "/repo", env)
    assert dropped == []


# --------------------------------------------------------------------------
# CLI contract -- what the launchers actually depend on
# --------------------------------------------------------------------------


def _run_cli(tmp_path, roster, env):
    src = tmp_path / "mcp.json"
    src.write_text(json.dumps(roster))
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(src), "--root", "/repo",
         "--out-dir", str(tmp_path), "--label", "claude-pmoves"],
        capture_output=True, text=True, env={**os.environ, **env},
    )
    return proc


def test_cli_prints_the_path_it_wrote_on_stdout(tmp_path):
    proc = _run_cli(tmp_path, _roster(good={"url": "https://example.com/mcp"}), {})
    assert proc.returncode == 0
    out = Path(proc.stdout.strip())
    assert out.is_file() and out.parent == tmp_path
    assert "good" in json.loads(out.read_text())["mcpServers"]


def test_cli_does_not_reuse_a_predictable_squattable_name(tmp_path):
    """A fixed name in a world-writable dir lets a local user pre-create it,
    fail our write, and force the launcher back to the raw roster."""
    first = _run_cli(tmp_path, _roster(a={"url": "https://e.com"}), {}).stdout.strip()
    second = _run_cli(tmp_path, _roster(a={"url": "https://e.com"}), {}).stdout.strip()
    assert first != second


def test_cli_warns_on_stderr_naming_server_and_variable(tmp_path):
    proc = _run_cli(
        tmp_path, _roster(**{"pmoves-cipher": {"url": "http://${TS_ZZZ_ABSENT}:8105/mcp/sse"}}), {}
    )
    assert proc.returncode == 0
    assert "pmoves-cipher" in proc.stderr
    assert "TS_ZZZ_ABSENT" in proc.stderr
    assert "[claude-pmoves]" in proc.stderr
    assert "pmoves-cipher" not in json.loads(Path(proc.stdout.strip()).read_text())["mcpServers"]


def test_cli_never_echoes_a_resolved_secret(tmp_path):
    proc = _run_cli(
        tmp_path,
        _roster(gw={"url": "http://x/y", "headers": {"Authorization": "Bearer ${TS_TEST_SECRET}"}}),
        {"TS_TEST_SECRET": "s3cretvalue"},
    )
    assert "s3cretvalue" not in proc.stderr
    assert "s3cretvalue" not in proc.stdout


def test_cli_output_is_owner_only_because_it_now_holds_expanded_secrets(tmp_path):
    proc = _run_cli(
        tmp_path,
        _roster(gw={"url": "http://x/y", "headers": {"Authorization": "Bearer ${TS_TEST_SECRET}"}}),
        {"TS_TEST_SECRET": "s3cret"},
    )
    out = Path(proc.stdout.strip())
    body = json.loads(out.read_text())
    assert body["mcpServers"]["gw"]["headers"]["Authorization"] == "Bearer s3cret"
    assert stat.S_IMODE(out.stat().st_mode) == 0o600


def test_cli_fails_loudly_on_a_broken_roster_so_the_launcher_can_fall_back(tmp_path):
    src = tmp_path / "mcp.json"
    src.write_text("{ not json")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(src), "--root", "/repo", "--out-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert proc.stdout.strip() == "", "a failed run must not print a path"


# --------------------------------------------------------------------------
# wiring -- the half that made an earlier fix land on a path nobody takes
# --------------------------------------------------------------------------


def test_the_posix_launcher_calls_the_normalizer():
    body = LAUNCHER.read_text()
    assert "pmoves/tools/mcp_roster_normalize.py" in body
    assert "<<'PY'" not in body, "the untestable heredoc came back"


def test_the_windows_launcher_calls_the_same_normalizer():
    """The POSIX fix landing alone is the documented repeat-failure here."""
    body = LAUNCHER_PS1.read_text()
    assert "mcp_roster_normalize.py" in body
    assert "$clean[$prop.Name] = $s" not in body, "the inline PowerShell copy came back"


def test_the_launcher_sources_the_shared_tailnet_helper():
    assert "pmoves/scripts/tailscale-node-ips.sh" in LAUNCHER.read_text()


def test_the_tailnet_resolution_has_exactly_one_definition():
    """crush-env.sh must SOURCE the helper, not carry its own copy."""
    body = CRUSH_ENV.read_text()
    assert "tailscale-node-ips.sh" in body
    assert "export TS_Z890=" not in body, "second copy of the resolution reappeared"


def test_the_helper_hardcodes_no_tailnet_address():
    """100.64/10 is CGNAT; a baked address leaks topology and rots."""
    assert not re.search(
        r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.", TS_HELPER.read_text()
    )


# ---------------------------------------------------------------------------
# Pair-review finding: the verdict must survive the TUI. stderr lines printed
# immediately before `exec claude` are overwritten within a second; the payload
# is the durable channel (the tracked roster already ships a `_pinned_versions_note`
# top-level key, so a `_`-prefixed sibling is established convention).
# ---------------------------------------------------------------------------

def test_verdicts_land_in_the_payload_not_only_stderr(tmp_path):
    proc = _run_cli(
        tmp_path,
        _roster(
            dead={"url": "http://${TS_VGONE}:8105/mcp/sse"},
            soft={"url": "http://x/y", "headers": {"Authorization": "Bearer ${TS_VSOFT}"}},
        ),
        {},
    )
    assert proc.returncode == 0
    payload = json.loads(Path(proc.stdout.strip()).read_text())
    verdicts = payload.get("_pmoves_roster_verdicts")
    assert verdicts, "verdict key missing — the announcement dies with the TUI again"
    assert {"server": "dead", "missing": ["TS_VGONE"]} in verdicts["dropped"]
    assert {"server": "soft", "missing": ["TS_VSOFT"]} in verdicts["degraded"]
    assert verdicts.get("generated_utc"), "no timestamp — a stale verdict is indistinguishable from a current one"


def test_verdict_key_is_written_even_when_clean(tmp_path):
    """Empty lists are a positive assertion the check RAN; absence would be
    indistinguishable from the fallback path that never invoked the tool."""
    proc = _run_cli(tmp_path, _roster(good={"url": "https://e.com/mcp"}), {})
    payload = json.loads(Path(proc.stdout.strip()).read_text())
    assert payload["_pmoves_roster_verdicts"]["dropped"] == []
    assert payload["_pmoves_roster_verdicts"]["degraded"] == []


def test_verdict_key_lives_at_top_level_not_as_a_server(tmp_path):
    """Inside mcpServers, Claude Code would try to LAUNCH it (that is why P2
    drops `_`-keys). The verdict must ride as a top-level sibling."""
    proc = _run_cli(tmp_path, _roster(good={"url": "https://e.com/mcp"}), {})
    payload = json.loads(Path(proc.stdout.strip()).read_text())
    assert "_pmoves_roster_verdicts" not in payload["mcpServers"]


def test_stale_window_is_one_hour_not_twelve(tmp_path):
    """Startup-read file; 12h bounded token-on-disk 12x looser than needed."""
    text = TOOL.read_text()
    m = re.search(r"_STALE_SECONDS = (\d+)", text)
    assert m and int(m.group(1)) <= 3600, (
        f"stale window is {m.group(1) if m else '?'}s — pair-review nit said 1h"
    )


# --------------------------------------------------------------------------
# The sweep is a DELETE path. Age nominates; liveness vetoes.
#
# The pre-fix predicate was `mtime < now - 3600` and nothing else, so the
# roster of a session that was still running was unlinked an hour in. These
# tests use a REAL child process and the REAL /proc scan -- mocking the thing
# under test would prove only that the mock works.
# --------------------------------------------------------------------------

import time as _time


def _roster_file(directory, age_seconds=0.0):
    """Create a file with our roster shape in *directory*, aged *age_seconds*.

    Contents are a placeholder, never a credential: the real file holds
    expanded bearer tokens and nothing in this suite may carry a real value.
    """
    fd, path = tempfile.mkstemp(
        dir=str(directory), prefix=norm._OUT_PREFIX, suffix=norm._OUT_SUFFIX
    )
    with os.fdopen(fd, "w") as fh:
        json.dump({"mcpServers": {}}, fh)
    if age_seconds:
        old = _time.time() - age_seconds
        os.utime(path, (old, old))
    return Path(path)


@contextlib.contextmanager
def _process_naming(path):
    """A real live process whose argv contains *path*, as the launcher's does.

    ``python -c CODE ARGS...`` puts ARGS in argv, so /proc/<pid>/cmdline really
    contains the path -- the same observable the sweep now reads. The glued
    ``--mcp-config=`` spelling is deliberate: that is how the launcher passes
    it, and it is one NUL-separated argv entry, not two.
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)", f"--mcp-config={path}"]
    )
    try:
        # Wait for the kernel to have argv readable before anyone scans.
        deadline = _time.time() + 10
        while _time.time() < deadline:
            try:
                with open(f"/proc/{proc.pid}/cmdline", "rb") as fh:
                    if str(path).encode() in fh.read():
                        break
            except OSError:
                pass
            _time.sleep(0.05)
        else:  # pragma: no cover - only on a pathologically slow box
            pytest.skip("child process argv never became readable")
        yield proc
    finally:
        proc.kill()
        proc.wait()


needs_proc = pytest.mark.skipif(
    not os.path.isdir("/proc"), reason="liveness scan needs /proc"
)


@needs_proc
def test_a_roster_a_live_process_still_names_is_not_deleted(tmp_path):
    """THE defect. Age alone deleted the roster of a running session.

    No mocks: a real child process, the real /proc scan, a real file older than
    the window.
    """
    victim = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    with _process_naming(victim):
        norm._sweep_stale(str(tmp_path))
    assert victim.exists(), (
        "the roster of a process that is still running was unlinked -- "
        "this is the bug, not a nit"
    )


@needs_proc
def test_an_expired_roster_nobody_references_is_still_deleted(tmp_path):
    """The security goal must not regress.

    The file holds expanded bearer tokens and the launcher ``exec``s, so the
    next launch is the only chance to clean up. A liveness check that kept
    everything would be a different bug wearing this fix's clothes.
    """
    orphan = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    norm._sweep_stale(str(tmp_path))
    assert not orphan.exists(), "expired unreferenced token file survived the sweep"


def test_undeterminable_liveness_keeps_everything(tmp_path):
    """Cannot prove it is unreferenced => do not delete it.

    A leaked token file is recoverable and detectable. A session stripped of
    its servers is neither. The asymmetry decides the direction.
    """
    old = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    norm._sweep_stale(str(tmp_path), live=None)
    assert old.exists()


def test_an_empty_live_set_is_not_the_same_as_undeterminable(tmp_path):
    """``None`` and ``set()`` must not collapse into each other.

    ``set()`` is "I enumerated the process table and found no reference";
    ``None`` is "I could not enumerate it". Treating the second as the first is
    the exact shape of the defect being fixed -- an absent signal read as a
    negative answer -- so it gets its own test rather than riding on the two
    above.
    """
    a = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    norm._sweep_stale(str(tmp_path), live=set())
    assert not a.exists(), "an empty live set is a positive answer; it must delete"

    b = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    norm._sweep_stale(str(tmp_path), live=None)
    assert b.exists(), "None is not an answer; it must keep"


def test_a_fresh_roster_survives_even_with_nothing_referencing_it(tmp_path):
    """The window still guards the launch race.

    A process that starts *after* the scan cannot be seen by it. Its roster is
    seconds old, so the freshness test covers what liveness cannot. The two
    predicates cover each other; neither alone is sufficient.
    """
    fresh = _roster_file(tmp_path, age_seconds=0)
    norm._sweep_stale(str(tmp_path), live=set())
    assert fresh.exists()


def test_the_sweep_still_refuses_another_users_file(tmp_path, monkeypatch):
    """The pre-existing uid guard is preserved, not traded away for liveness."""
    other = _roster_file(tmp_path, age_seconds=norm._STALE_SECONDS * 4)
    real_uid = os.getuid()
    monkeypatch.setattr(norm.os, "getuid", lambda: real_uid + 12345)
    norm._sweep_stale(str(tmp_path), live=set())
    assert other.exists()


def test_the_sweep_leaves_files_that_are_not_ours_alone(tmp_path):
    """Prefix/suffix scoping is unchanged: the 210 zero-byte
    ``pmoves-roster-origin-main.*`` scratch files in /tmp are somebody else's
    business and stay that way."""
    stranger = tmp_path / "pmoves-roster-origin-main.abc123"
    stranger.write_text("")
    old = _time.time() - norm._STALE_SECONDS * 4
    os.utime(stranger, (old, old))
    norm._sweep_stale(str(tmp_path), live=set())
    assert stranger.exists()


@pytest.mark.parametrize(
    "text",
    [
        "--mcp-config=/run/user/1000/claude-pmoves-mcp-roster.ab12cd.json",
        "/tmp/claude-pmoves-mcp-roster.ab12cd.json",
        '"C:\\\\Temp\\\\claude-pmoves-mcp-roster.ab12cd.json"',
        "claude --mcp-config /tmp/claude-pmoves-mcp-roster.ab12cd.json --agent x",
    ],
)
def test_every_spelling_the_launchers_use_is_recognised(text):
    """Own argv entry, glued to the flag, and the one-quoted-string form
    Windows hands back. A path we fail to recognise is a delete."""
    found = list(norm._roster_paths_in(text))
    assert found, f"no roster path found in {text!r}"
    assert found[0].endswith("claude-pmoves-mcp-roster.ab12cd.json")


def test_a_command_line_with_no_roster_yields_nothing():
    """Positive control for the matcher: it must be capable of finding
    nothing, or the tests above prove only that it always matches."""
    assert list(norm._roster_paths_in("claude --agent node-steward")) == []


@needs_proc
def test_the_live_scan_returns_a_set_not_none_on_this_box(tmp_path):
    """Positive control for the scan itself.

    Every KEEP assertion above would also pass if ``_live_roster_paths`` simply
    always returned ``None`` -- keep-everything satisfies them by accident. So
    pin that on a box with a readable /proc it returns a real answer, and that
    the answer actually contains our path when a process names it.
    """
    victim = _roster_file(tmp_path, age_seconds=0)
    with _process_naming(victim):
        live = norm._live_roster_paths()
    assert live is not None, "scan degraded to undeterminable on a readable /proc"
    assert any(Path(p).name == victim.name for p in live)


@needs_proc
def test_a_refused_cmdline_read_degrades_the_whole_scan(monkeypatch, tmp_path):
    """EACCES (a ``hidepid`` mount) is not evidence of absence.

    One unreadable process means we can no longer assert that NOTHING
    references a roster, so the answer for the whole sweep becomes
    undeterminable rather than a confident empty set.
    """
    import builtins

    real_open = builtins.open

    def refusing_open(path, *a, **kw):
        if isinstance(path, str) and path.startswith("/proc/"):
            raise PermissionError(13, "Permission denied")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(builtins, "open", refusing_open)
    assert norm._live_roster_paths() is None


# --------------------------------------------------------------------------
# Custody: XDG_RUNTIME_DIR beats a world-writable temp dir for a file that
# holds expanded bearer tokens.
# --------------------------------------------------------------------------


def test_custody_prefers_xdg_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert norm._default_out_dir() == str(tmp_path)


def test_custody_falls_back_when_xdg_is_unset(monkeypatch):
    """Absent on Windows, in most CI containers, and under sudo/cron."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert norm._default_out_dir() == tempfile.gettempdir()


def test_custody_falls_back_when_xdg_points_at_nothing(tmp_path, monkeypatch):
    """Set-but-wrong is the shadow that beats a presence check."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "does-not-exist"))
    assert norm._default_out_dir() == tempfile.gettempdir()


def test_the_out_dir_flag_still_wins(tmp_path, monkeypatch):
    """--out-dir is an existing contract; custody must not quietly override it."""
    other = tmp_path / "xdg"
    other.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(other))
    proc = _run_cli(tmp_path, _roster(good={"url": "https://example.com/mcp"}), {})
    assert proc.returncode == 0
    assert Path(proc.stdout.strip()).parent == tmp_path


def test_moving_custody_does_not_strand_rosters_in_the_old_location(monkeypatch):
    """The legacy temp dir stays in scope in DEFAULT custody, or the security
    goal silently stops applying to exactly the files it was written for."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/never")
    dirs = norm._sweep_dirs("/run/user/1000", explicit=False)
    assert tempfile.gettempdir() in dirs


def test_an_explicit_out_dir_does_not_reach_into_the_shared_temp_dir():
    """A sweep is a delete path and gets the narrowest scope that still works.

    Under test this is not theoretical: the suite runs the CLI repeatedly with
    a throwaway out-dir on a machine whose real temp dir holds the roster of a
    running session.
    """
    assert norm._sweep_dirs("/somewhere/else", explicit=True) == ["/somewhere/else"]


def test_the_written_roster_is_still_owner_only_wherever_it_lands(tmp_path):
    """Custody moved; the 0600 guarantee did not."""
    proc = _run_cli(tmp_path, _roster(good={"url": "https://example.com/mcp"}), {})
    mode = stat.S_IMODE(Path(proc.stdout.strip()).stat().st_mode)
    assert mode == 0o600, f"roster is {oct(mode)}, it holds expanded tokens"


# --------------------------------------------------------------------------
# Windows: no /proc, no XDG_RUNTIME_DIR.
# --------------------------------------------------------------------------


def test_windows_liveness_failure_keeps_everything(monkeypatch):
    """Every failure mode -- powershell absent, WMI refused, timeout, non-zero
    exit -- must return None, i.e. KEEP. 4090/5090/Z890 all take this path."""
    import subprocess as sp

    def boom(*a, **kw):
        raise FileNotFoundError(2, "powershell.exe not found")

    monkeypatch.setattr(sp, "run", boom)
    assert norm._windows_live_roster_paths() is None


def test_windows_liveness_timeout_keeps_everything(monkeypatch):
    import subprocess as sp

    def slow(*a, **kw):
        raise sp.TimeoutExpired(cmd="powershell.exe", timeout=1)

    monkeypatch.setattr(sp, "run", slow)
    assert norm._windows_live_roster_paths() is None


def test_windows_liveness_nonzero_exit_keeps_everything(monkeypatch):
    import subprocess as sp

    class R:
        returncode = 1
        stdout = b""

    monkeypatch.setattr(sp, "run", lambda *a, **kw: R())
    assert norm._windows_live_roster_paths() is None


def test_windows_liveness_reads_command_lines_when_the_query_works(monkeypatch):
    """Positive control: the Windows path must be capable of a non-None,
    non-empty answer, or the three tests above prove only that it never works.
    """
    import subprocess as sp

    class R:
        returncode = 0
        stdout = (
            'claude --mcp-config="C:\\Temp\\claude-pmoves-mcp-roster.zz99.json"\r\n'
            "svchost.exe -k netsvcs\r\n"
        ).encode()

    monkeypatch.setattr(sp, "run", lambda *a, **kw: R())
    live = norm._windows_live_roster_paths()
    assert live is not None
    assert any(p.endswith("claude-pmoves-mcp-roster.zz99.json") for p in live)


def _executable_lines(launcher):
    """A launcher's code with comment lines removed.

    Both of the launcher assertions below are substring greps, and both were
    tripped by the explanatory comments this same change added -- prose that
    NAMES `--out-dir` and `XDG_RUNTIME_DIR` in order to warn a future editor
    off them read as a use of them. Weakening the assertions would have been
    the wrong repair; a grep over a shell script should look at the script.
    """
    lines = launcher.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(l for l in lines if not l.lstrip().startswith("#"))


def test_the_windows_launcher_does_not_hand_the_tool_a_posix_only_out_dir():
    """XDG_RUNTIME_DIR does not exist on Windows; the .ps1 must not invent one.
    Custody there stays the temp dir -- already per-user on Windows -- chosen
    by the tool's own fallback."""
    assert "XDG_RUNTIME_DIR" not in _executable_lines(LAUNCHER_PS1)


# --------------------------------------------------------------------------
# The launchers must not defeat the fix.
# --------------------------------------------------------------------------


def test_neither_launcher_pins_the_roster_to_the_shared_temp_dir():
    """A hardcoded --out-dir in either launcher would silently undo the custody
    move for every session on the fleet while these unit tests stayed green."""
    for launcher in (LAUNCHER, LAUNCHER_PS1):
        assert "--out-dir" not in _executable_lines(launcher), (
            f"{launcher.name} pins --out-dir; the tool must choose custody"
        )


def test_the_sweep_has_a_liveness_check_at_all():
    """Regression guard on the shape of the defect.

    The pre-fix file scored 0 for every liveness idiom -- that measurement is
    what identified the bug, so it is what gets pinned.
    """
    text = TOOL.read_text()
    assert re.search(r"/proc/|cmdline|Win32_Process", text), (
        "the sweep unlinks on mtime alone again"
    )


def test_default_custody_is_xdg_runtime_dir_not_the_shared_temp_dir(tmp_path):
    """BEHAVIOURAL control for the custody move, through the existing CLI
    contract rather than through a new symbol.

    Neither launcher passes ``--out-dir`` -- they let the tool choose -- so
    "where does the CLI put the file when nobody tells it" IS the shipped
    behaviour, and it is observable on both the old and the new code. Pre-fix
    this lands in the shared temp dir; post-fix in XDG_RUNTIME_DIR, mode 0700
    and owned by the login session.

    TMPDIR is redirected at the fake temp dir on purpose: this test runs the
    CLI in DEFAULT custody, which also sweeps the temp dir, and the real one on
    this node holds the roster of a running session. A test must not be able to
    delete it.
    """
    xdg = tmp_path / "run-user"
    faketmp = tmp_path / "faketmp"
    xdg.mkdir()
    faketmp.mkdir()

    src = tmp_path / "mcp.json"
    src.write_text(json.dumps(_roster(good={"url": "https://example.com/mcp"})))
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(src), "--root", "/repo", "--label", "t"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "XDG_RUNTIME_DIR": str(xdg),
            "TMPDIR": str(faketmp),
        },
    )
    assert proc.returncode == 0, proc.stderr
    written = Path(proc.stdout.strip())
    assert written.parent == xdg, (
        f"roster landed in {written.parent} -- a file holding expanded bearer "
        f"tokens belongs in XDG_RUNTIME_DIR, not the shared temp dir"
    )


def test_the_launchers_pass_the_roster_path_where_the_liveness_scan_can_see_it():
    """The fix depends on a launcher coupling, so the coupling gets a test.

    The sweep can only spare a live session's roster if that path appears in
    the session's own command line. Both launchers use the glued
    ``--mcp-config=<path>`` form -- chosen originally because ``--mcp-config``
    is variadic and the space form swallowed a trailing prompt -- and that is
    exactly the spelling ``_roster_paths_in`` matches. If either launcher ever
    stops naming the path on the command line, the liveness check goes blind
    and the sweep silently reverts to deleting live sessions' rosters.
    """
    for launcher in (LAUNCHER, LAUNCHER_PS1):
        text = launcher.read_text(encoding="utf-8", errors="replace")
        assert "--mcp-config=" in text, (
            f"{launcher.name} no longer passes the roster path in argv; "
            f"the liveness scan cannot see it"
        )
