"""The Windows launcher binds the same cipher token the POSIX launcher does.

Measured on Z890 2026-11-02 with a stub `claude` on the real Windows path
(claude-pmoves.cmd -> claude-pmoves.ps1):

    cipher carry: mode=bootstrap card=yes writes-land-as=bootstrap

while the bash path on the same node bound the minted per-agent token. The
.ps1 had no counterpart to pm-cipher-token-bind.sh (#3143), pm-ca-bundle.sh or
pm-brv-check.sh. This file pins the PowerShell siblings to the bash contracts
and pins claude-pmoves.ps1 to call them in the right order.

Two halves:
  * EXECUTED -- the helpers run under a real PowerShell. CI has none (see
    test_claude_pmoves_roster_fallback.py), so these skip there and run on
    any Windows node, which is where the defect lived.
  * STATIC -- ordering in claude-pmoves.ps1, which runs everywhere. Order is
    the whole bug: a bind before env.shared loads is overwritten by it, and a
    bind after the carry measurement reports the pre-bind state.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "pmoves" / "scripts"
BIND = SCRIPTS / "pm-cipher-token-bind.ps1"
CA = SCRIPTS / "pm-ca-bundle.ps1"
BRV = SCRIPTS / "pm-brv-check.ps1"
LAUNCHER = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"

PWSH = shutil.which("pwsh") or (shutil.which("powershell") if os.name == "nt" else None)
needs_ps = pytest.mark.skipif(PWSH is None, reason="no PowerShell on this host")
# claude-pmoves.cmd runs `powershell` -- Windows PowerShell 5.1, which throws on
# path probes that pwsh 7 tolerates. Tests for those use the launcher's shell.
PS_LAUNCHER = (shutil.which("powershell") if os.name == "nt" else None) or PWSH

# Obviously-fake bearers: shape-valid, never minted.
GOOD = "cipher_0123456789abcdef0123456789abcdef"


def _ps(script: str, env: dict[str, str] | None = None, exe: str | None = None) -> dict:
    full = {k: v for k, v in os.environ.items() if k != "CIPHER_API_TOKEN"}
    full.update(env or {})
    r = subprocess.run(
        [exe or PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, env=full, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _bind(root: Path, agent: str, env: dict[str, str] | None = None) -> dict:
    return _ps(
        f". '{BIND}'; $r = Invoke-PmCipherTokenBind -Root '{root}' -Agent '{agent}'; "
        "@{ ok = $r.Ok; line = $r.Line; tok = \"$env:CIPHER_API_TOKEN\" } | ConvertTo-Json -Compress",
        env,
    )


def _root(tmp_path: Path, body: str | None) -> Path:
    (tmp_path / "pmoves").mkdir()
    if body is not None:
        (tmp_path / "pmoves" / ".env.local").write_text(body, encoding="utf-8", newline="\n")
    return tmp_path


# --------------------------------------------------------------------------- bind

@needs_ps
def test_binds_the_declared_agents_token(tmp_path):
    r = _bind(_root(tmp_path, f"OTHER=x\nCIPHER_TOKEN_Z890_CLAUDE={GOOD}\n"), "z890-claude")
    assert r["ok"] is True and r["tok"] == GOOD
    assert "bound for z890-claude" in r["line"] and GOOD not in r["line"]


@needs_ps
@pytest.mark.parametrize("value", [
    f'"{GOOD}"', f"'{GOOD}'", f"  {GOOD}  ", f"{GOOD} # minted 2026-10-09", f"{GOOD}\r",
])
def test_value_forms_the_bash_twin_accepts(tmp_path, value):
    r = _bind(_root(tmp_path, f"CIPHER_TOKEN_Z890_CLAUDE={value}\n"), "z890-claude")
    assert r["ok"] is True and r["tok"] == GOOD


@needs_ps
def test_explicit_env_token_wins(tmp_path):
    r = _bind(_root(tmp_path, f"CIPHER_TOKEN_Z890_CLAUDE={GOOD}\n"), "z890-claude",
              {"CIPHER_API_TOKEN": "cipher_feedface"})
    assert r["ok"] is True and r["tok"] == "cipher_feedface"
    assert "explicit" in r["line"]


@needs_ps
@pytest.mark.parametrize("body, agent, why", [
    (None, "z890-claude", "absent"),
    ("CIPHER_TOKEN_OTHER=cipher_ab\n", "z890-claude", "not in"),
    ("cipher_token_z890_claude=cipher_ab\n", "z890-claude", "not in"),       # key is case-sensitive
    ("CIPHER_TOKEN_Z890_CLAUDE=bootstrap-shared\n", "z890-claude", "not a cipher_-prefixed"),
    ("CIPHER_TOKEN_Z890_CLAUDE=Cipher_ab\n", "z890-claude", "not a cipher_-prefixed"),  # prefix too
    ("CIPHER_TOKEN_Z890_CLAUDE=cipher_\n", "z890-claude", "not a well-formed"),
    ("CIPHER_TOKEN_Z890_CLAUDE=cipher_ab$x\n", "z890-claude", "not a well-formed"),
    ("", "", "no declared cipher agentId"),
])
def test_refusals_leave_the_bootstrap_token_and_say_why(tmp_path, body, agent, why):
    r = _bind(_root(tmp_path, body), agent, {"CIPHER_API_TOKEN": "bootstrap-shared"})
    assert r["ok"] is False and why in r["line"]
    assert r["tok"] == "bootstrap-shared"


@needs_ps
def test_locked_env_local_degrades_to_unbound_not_a_crash(tmp_path):
    # A .NET exception is terminating in PowerShell; the twin's awk fails soft.
    root = _root(tmp_path, f"CIPHER_TOKEN_Z890_CLAUDE={GOOD}\n")
    envf = root / "pmoves" / ".env.local"
    r = _ps(
        "$ErrorActionPreference = 'Stop'; "
        f"$h = [System.IO.File]::Open('{envf}', 'Open', 'ReadWrite', 'None'); "
        f". '{BIND}'; $r = Invoke-PmCipherTokenBind -Root '{root}' -Agent 'z890-claude'; $h.Close(); "
        "@{ ok = $r.Ok; line = $r.Line; tok = \"$env:CIPHER_API_TOKEN\" } | ConvertTo-Json -Compress",
        {"CIPHER_API_TOKEN": "bootstrap-shared"},
    )
    assert r["ok"] is False and "unreadable" in r["line"]
    assert r["tok"] == "bootstrap-shared"


# ------------------------------------------------------------------- ca + brv

def _ca(env: dict[str, str]) -> str:
    out = _ps(f". '{CA}'; @{{ line = (Invoke-PmCaBundleNormalize) }} | ConvertTo-Json -Compress", env)
    return out["line"] or ""


@needs_ps
def test_ca_broken_configured_path_is_kept_and_named(tmp_path):
    missing = str(tmp_path / "gone" / "cacert.pem")
    line = _ca({"SSL_CERT_FILE": missing})
    assert "WARN" in line and "SSL_CERT_FILE=" + missing in line


@needs_ps
def test_ca_readable_configured_path_is_silent(tmp_path):
    pem = tmp_path / "ca.pem"
    pem.write_text("x", encoding="utf-8")
    assert _ca({"SSL_CERT_FILE": str(pem)}) == ""


@needs_ps
def test_ca_unprobeable_path_warns_under_stop(tmp_path):
    # Under 5.1 Test-Path throws ArgumentException on '<' / '|' (measured); the
    # launcher runs with EAP=Stop, so an unguarded probe kills the launch.
    out = _ps(f"$ErrorActionPreference = 'Stop'; . '{CA}'; @{{ line = (Invoke-PmCaBundleNormalize) }} | ConvertTo-Json -Compress",
              {"SSL_CERT_FILE": r"C:\pki\a<b|c.crt"}, exe=PS_LAUNCHER)
    assert "WARN" in (out["line"] or "") and "SSL_CERT_FILE=" in out["line"]


@needs_ps
def test_brv_missing_is_loud_and_feeds_the_prompt(tmp_path):
    out = _ps(f". '{BRV}'; $r = Invoke-PmBrvCheck; @{{ ok = $r.Ok; line = $r.Line; p = $r.Prompt }} | ConvertTo-Json -Compress",
              {"PATH": str(tmp_path)})
    assert out["ok"] is False and "brv=MISSING" in out["line"] and "brv" in out["p"]


# ------------------------------------------------------------------- static order

def _pos(text: str, needle: str) -> int:
    i = text.find(needle)
    assert i >= 0, f"claude-pmoves.ps1 lacks {needle!r}"
    return i


def test_launcher_dot_sources_all_three_siblings():
    text = LAUNCHER.read_text(encoding="utf-8")
    for helper in ("pm-cipher-token-bind.ps1", "pm-ca-bundle.ps1", "pm-brv-check.ps1"):
        assert helper in text


def test_launcher_binds_after_env_shared_and_before_carry_and_roster():
    text = LAUNCHER.read_text(encoding="utf-8")
    capture = _pos(text, "$script:PmCipherPreEnvToken =")
    env_load = _pos(text, "if (Test-Path $envf)")
    bind = _pos(text, "Invoke-PmCipherTokenBind")
    carry = _pos(text, "pmoves/tools/cipher_identity.py")
    roster = _pos(text, "$roster = Join-Path $root '.claude\\mcp.json'")
    assert capture < env_load < bind < carry < roster


def test_helpers_are_ascii_for_windows_powershell_5():
    # PS 5.1 reads a BOM-less .ps1 as the ANSI code page; a UTF-8 em dash in
    # a message string turns into mojibake on the operator's console.
    for p in (BIND, CA, BRV):
        p.read_bytes().decode("ascii")


def test_explicit_token_restore_does_not_wait_for_identity_success():
    # Every fail-open path in identity resolution would otherwise launch with
    # env.shared's bootstrap bearer standing (Codex + Kilo review, #3449).
    text = LAUNCHER.read_text(encoding="utf-8")
    restore = _pos(text, "if ($script:PmCipherPreEnvToken) { $env:CIPHER_API_TOKEN")
    assert _pos(text, "if (Test-Path $envf)") < restore < _pos(text, "$identTool = Join-Path")
    assert text.count("$env:CIPHER_API_TOKEN = $script:PmCipherPreEnvToken") == 1
