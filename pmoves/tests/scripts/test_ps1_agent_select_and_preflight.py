"""The Windows launcher selects agents and reports cipher the way the .sh does.

Measured on Z890 2026-11-04 (stub claude, installed `claude-pmoves`): the shim
pmoves/scripts/windows/claude-pmoves.bat resolved the node identity and built
an identity prompt, then called claude-pmoves.ps1, which did both again --
claude received TWO --append-system-prompt blocks. Separately the .ps1 never ran
cipher_preflight.py, so a Windows session was not told whether memory worked.

The shim is now a delegate. Its one rule -- agent selection -- moved to
pm-agent-select.ps1, and the preflight verdict to pm-cipher-preflight.ps1. Both
are executed here under Windows PowerShell 5.1 when present (the shell
claude-pmoves.cmd runs), else pwsh; CI has neither, so these skip there.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "pmoves" / "scripts"
SELECT = SCRIPTS / "pm-agent-select.ps1"
PREFLIGHT = SCRIPTS / "pm-cipher-preflight.ps1"
SH = SCRIPTS / "claude-pmoves.sh"

PS = (shutil.which("powershell") if os.name == "nt" else None) or shutil.which("pwsh")
needs_ps = pytest.mark.skipif(PS is None, reason="no PowerShell on this host")


def _ps(script: str, env: dict[str, str] | None = None) -> dict:
    full = {k: v for k, v in os.environ.items() if k != "PMOVES_DEFAULT_AGENT"}
    full.update(env or {})
    r = subprocess.run([PS, "-NoProfile", "-NonInteractive", "-Command",
                        "$ErrorActionPreference = 'Stop'; " + script],
                       capture_output=True, text=True, env=full, timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _root(tmp_path: Path) -> Path:
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    for name in ("delivery-agent", "node-steward"):
        (agents / f"{name}.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return tmp_path


def _select(root: Path, argv: list[str], **env: str) -> dict:
    arr = ", ".join("'" + a.replace("'", "''") + "'" for a in argv)
    return _ps(
        f". '{SELECT}'; $s = Resolve-PmAgentArgs -Root '{root}' -Argv @({arr}); "
        "@{ argv = @($s.Argv); role = $s.Role; lines = @($s.Lines) } | ConvertTo-Json -Compress",
        env,
    )


# ----------------------------------------------------------------- selection

@needs_ps
def test_default_is_no_agent_and_args_pass_untouched(tmp_path):
    s = _select(_root(tmp_path), ["--print", "hi"])
    assert s["argv"] == ["--print", "hi"] and s["role"] is None and not s["lines"]


@needs_ps
def test_a_defined_positional_agent_becomes_one_agent_flag(tmp_path):
    s = _select(_root(tmp_path), ["delivery-agent", "--print", "hi"])
    assert s["argv"] == ["--agent", "delivery-agent", "--print", "hi"]
    assert s["role"] == "delivery-agent"


@needs_ps
def test_an_undefined_positional_name_is_dropped_loudly_and_runs_with_no_agent(tmp_path):
    # Even with a default set: the .sh sets AGENT="" on a drop, not the default.
    s = _select(_root(tmp_path), ["no-such-agent", "--print", "hi"], PMOVES_DEFAULT_AGENT="node-steward")
    assert s["argv"] == ["--print", "hi"] and s["role"] is None
    assert any("no-such-agent" in l and "dropped" in l for l in s["lines"])


@needs_ps
def test_the_default_env_gives_the_restricted_coordinator(tmp_path):
    s = _select(_root(tmp_path), [], PMOVES_DEFAULT_AGENT="node-steward")
    assert s["argv"] == ["--agent", "node-steward"] and s["role"] == "node-steward"


@needs_ps
def test_a_default_naming_no_definition_is_dropped_loudly(tmp_path):
    s = _select(_root(tmp_path), ["-r"], PMOVES_DEFAULT_AGENT="no-such-agent")
    assert s["argv"] == ["-r"] and s["role"] is None
    assert any("PMOVES_DEFAULT_AGENT='no-such-agent'" in l for l in s["lines"])


@needs_ps
def test_an_explicit_agent_flag_is_not_doubled_by_the_default(tmp_path):
    s = _select(_root(tmp_path), ["--agent", "delivery-agent"], PMOVES_DEFAULT_AGENT="node-steward")
    assert s["argv"].count("--agent") == 1 and s["role"] == "delivery-agent"


@needs_ps
@pytest.mark.parametrize("name", [r"..\..\Windows\win", "a<b", "fix X"])
def test_a_name_that_is_not_a_file_stem_is_never_probed(tmp_path, name):
    s = _select(_root(tmp_path), [name])
    assert s["argv"] == [] and s["role"] is None and s["lines"]


# ----------------------------------------------------------------- preflight

STUB = """import os, sys
sys.stdout.write(os.environ.get("STUB_OUT", ""))
raise SystemExit(int(os.environ.get("STUB_RC", "0")))
"""


def _preflight(tmp_path: Path, rc: int, out: str) -> dict:
    (tmp_path / "pmoves" / "tools").mkdir(parents=True)
    (tmp_path / "pmoves" / "tools" / "cipher_preflight.py").write_text("", encoding="utf-8")
    stub = tmp_path / "stub.py"
    stub.write_text(STUB, encoding="utf-8")
    return _ps(
        f". '{PREFLIGHT}'; $c = Invoke-PmCipherPreflight -Root '{tmp_path}' -Py @('{sys.executable}', '{stub}'); "
        "@{ v = $c.Verdict; line = $c.Line; p = $c.Prompt } | ConvertTo-Json -Compress",
        {"STUB_RC": str(rc), "STUB_OUT": out},
    )


@needs_ps
def test_preflight_up_names_the_endpoint(tmp_path):
    c = _preflight(tmp_path, 0, "cipher OK   pmoves-cipher-local  (http://x/mcp/sse) -> 200\n")
    assert c["v"] == "up" and "pmoves-cipher-local" in c["line"]
    assert "Persistent memory IS available" in c["p"] and "'pmoves-cipher-local'" in c["p"]


@needs_ps
def test_preflight_unauthorized_is_not_an_outage(tmp_path):
    c = _preflight(tmp_path, 1, "cipher UNAUTHORIZED pmoves-cipher-local  (http://x) -> 401\n")
    assert c["v"] == "unauthorized" and "do NOT report Cipher as down" in c["p"]
    assert "`docker logs --since " in c["p"]


@needs_ps
def test_preflight_other_exit_1_is_answered_unusable(tmp_path):
    c = _preflight(tmp_path, 1, "cipher FAIL pmoves-cipher-local -> 503\n")
    assert c["v"] == "unusable" and "do not ask for a re-mint" in c["p"]


@needs_ps
@pytest.mark.parametrize("rc", [3, 2, 9])
def test_preflight_anything_else_is_down(tmp_path, rc):
    c = _preflight(tmp_path, rc, "")
    assert c["v"] == "down" and f"preflight exit {rc}" in c["p"] and "NO persistent memory" in c["p"]


@needs_ps
def test_preflight_absent_tool_is_skipped_not_down(tmp_path):
    c = _ps(f". '{PREFLIGHT}'; $c = Invoke-PmCipherPreflight -Root '{tmp_path}' -Py @('{sys.executable}'); "
            "@{ v = $c.Verdict; p = $c.Prompt } | ConvertTo-Json -Compress")
    assert c["v"] == "skipped" and c["p"] == ""


# ------------------------------------------------------- the .sh is the source

def test_every_preflight_prompt_is_the_sh_sentence():
    """Word-for-word with the .sh, up to the interpolated values."""
    sh = SH.read_text(encoding="utf-8")
    ps = PREFLIGHT.read_text(encoding="utf-8")
    for anchor in (
        "Persistent memory IS available this session via the Cipher MCP server",
        "do not fall back to the auto-memory directory while it is up.",
        "Cipher ANSWERED this session but refused the credential (preflight exit 1, verdict unauthorized)",
        "Remedy when the token itself is wrong: bind CIPHER_API_TOKEN into the roster.",
        "Cipher ANSWERED this session but not usably (preflight exit 1, and NOT a 401/403",
        "so do not ask for a re-mint.",
        "so you have NO persistent memory. Say so at session start rather than recalling nothing silently",
    ):
        assert anchor in sh, f".sh lost {anchor!r}"
        assert anchor in ps, f"pm-cipher-preflight.ps1 lost {anchor!r}"


def test_helpers_are_ascii_for_windows_powershell_5():
    for p in (SELECT, PREFLIGHT):
        p.read_bytes().decode("ascii")
