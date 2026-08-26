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

import json
import os
import re
import stat
import subprocess
import sys
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
    assert {n for n, _ in dropped} == {"pmoves-cipher", "agent-zero", "archon"}


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
