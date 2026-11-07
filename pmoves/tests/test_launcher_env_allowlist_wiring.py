"""claude-pmoves.{sh,ps1} export only the allowlist, never all of env.shared.

The list itself is pinned by test_launcher_env_allowlist.py. These tests hold
the launchers to it: a stub `claude` dumps the environment it was handed, and an
unrelated secret in the env file must not be in it.

What crossed before: `set -a; . "$tmpf"` (bash) and a SetEnvironmentVariable
per parsed key (PowerShell) put 433 keys into every session on Z890, the
JWT / service-role / database-password class included.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pmoves.tools.bash_resolver import find_bash  # never System32's WSL stub

import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[2]
SH = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh"
PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"
TOOL = REPO_ROOT / "pmoves" / "tools" / "launcher_env_allowlist.py"

_spec = importlib.util.spec_from_file_location("launcher_env_allowlist_w", TOOL)
lea = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lea)

# One of each case the loader has to get right. HIRAG_URL is an implicit read,
# SUPABASE_REST_URL / SUPABASE_SERVICE_ROLE_KEY / NATS_URL are roster refs.
ENV_FILE = """\
# comment
HIRAG_URL=http://from-file
SUPABASE_REST_URL=http://rest-from-file
SERVICE_ROLE_KEY=canonical-role-key
SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}
SUPABASE_JWT_SECRET=leak-sentinel-jwt
POSTGRES_PASSWORD=leak-sentinel-pg
PMOVES_ALLOWLIST_PARENT_KEY=from-file
NATS_URL=
"""

ENV_DUMPER = """#!/usr/bin/env bash
env -0 > "$ENV_OUT"
"""


def _bash() -> str:
    found = find_bash()
    if not found:
        pytest.skip("bash not available")
    return found


def _parse_env0(raw: bytes) -> dict[str, str]:
    out = {}
    for part in raw.split(b"\0"):
        if b"=" in part:
            k, _, v = part.decode("utf-8", "replace").partition("=")
            out[k] = v
    return out


def _base_env(tmp_path: Path, bin_dir: Path, env_out: Path) -> dict[str, str]:
    envf = tmp_path / "env.shared"
    envf.write_text(ENV_FILE, encoding="utf-8")
    env = dict(os.environ)
    for k in ("HIRAG_URL", "SUPABASE_REST_URL", "SERVICE_ROLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
              "SUPABASE_JWT_SECRET", "POSTGRES_PASSWORD", "NATS_URL", "PMOVES_NODE_IDENTITY"):
        env.pop(k, None)
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        PMOVES_LAUNCHER_ROOT=str(REPO_ROOT),
        PMOVES_ENV_SHARED=str(envf),
        PMOVES_ROSTER_FROM_TREE="1",       # no fetch; the tree roster is the one under test
        PMOVES_NODE_ID="pmoves-5090",
        ENV_OUT=str(env_out),
        # Inherited values the file must and must not beat:
        HIRAG_URL="http://stale-parent",                  # allowed + in file -> file wins
        PMOVES_ALLOWLIST_PARENT_KEY="from-parent",        # NOT allowed -> parent untouched
    )
    return env


def _assert_allowlisted(child: dict[str, str], stderr: str) -> None:
    assert child, f"stub claude was never reached; stderr:\n{stderr}"
    # The launchers run against the REAL roster. If it ever legitimately names a
    # sentinel, say that here rather than as a leak below.
    listed = set(lea.allowlist(REPO_ROOT))
    assert not listed & {"SUPABASE_JWT_SECRET", "POSTGRES_PASSWORD", "SERVICE_ROLE_KEY"}, (
        "the roster now references a sentinel; pick another unrelated key for this test")
    # Not on the list: absent, whatever the file says.
    assert "SUPABASE_JWT_SECRET" not in child
    assert "POSTGRES_PASSWORD" not in child
    # The alias resolves, but its canonical source is not a roster ref.
    assert child.get("SUPABASE_SERVICE_ROLE_KEY") == "canonical-role-key"
    assert "SERVICE_ROLE_KEY" not in child
    assert child.get("SUPABASE_REST_URL") == "http://rest-from-file"
    # Allowed and defined: the file beats the inherited value, as before.
    assert child.get("HIRAG_URL") == "http://from-file"
    # Not allowed: the file must not overwrite an already-exported parent value
    # (sourcing in the launcher's own shell would have, and it would cross).
    assert child.get("PMOVES_ALLOWLIST_PARENT_KEY") == "from-parent"
    # Empty in the file: not exported.
    assert "NATS_URL" not in child
    assert "allowlisted of" in stderr, stderr


def test_sh_launcher_exports_only_the_allowlist(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(ENV_DUMPER, encoding="utf-8")
    stub.chmod(0o755)
    env_out = tmp_path / "env.bin"
    env = _base_env(tmp_path, bin_dir, env_out)
    proc = subprocess.run([_bash(), str(SH), "--print", "hi"],
                          capture_output=True, text=True, env=env, timeout=240)
    child = _parse_env0(env_out.read_bytes()) if env_out.exists() else {}
    _assert_allowlisted(child, proc.stderr)


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


@pytest.mark.skipif(os.name != "nt", reason="the .ps1 launcher runs on Windows nodes")
def test_ps1_launcher_exports_only_the_allowlist(tmp_path: Path):
    ps = _powershell()
    if not ps:
        pytest.skip("no PowerShell")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # `& claude` resolves claude.cmd through PATHEXT; the dump runs in a child
    # process, so it sees exactly what the real harness would inherit.
    (bin_dir / "claude.cmd").write_text(
        '@echo off\r\n"%PMOVES_TEST_PY%" -c "import os,sys;'
        "open(os.environ['ENV_OUT'],'wb').write(b''.join("
        "(k+'='+v).encode('utf-8')+b'\\0' for k,v in os.environ.items()))\"\r\n",
        encoding="utf-8")
    env_out = tmp_path / "env.bin"
    env = _base_env(tmp_path, bin_dir, env_out)
    env["PMOVES_TEST_PY"] = shutil.which("python") or "python"
    proc = subprocess.run(
        [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), "--print", "hi"],
        capture_output=True, text=True, env=env, timeout=300)
    child = _parse_env0(env_out.read_bytes()) if env_out.exists() else {}
    # Windows env names are case-insensitive; os.environ upper-cases them.
    child = {k.upper(): v for k, v in child.items()}
    _assert_allowlisted(child, proc.stdout + proc.stderr)


def test_neither_launcher_bulk_exports_the_env_file():
    sh = SH.read_text(encoding="utf-8")
    assert not re.search(r"set -a[^\n]*\n[^\n]*\n?\s*\.\s+\"\$tmpf\"", sh), \
        "claude-pmoves.sh sources the env file under set -a again"
    loader = sh.split('if [ -f "$ENVF" ]', 1)[1].split("# --- HOST TLS", 1)[0]
    code = "\n".join(ln.split("#", 1)[0] for ln in loader.splitlines())
    assert "set -a" not in code
    ps1 = PS1.read_text(encoding="utf-8")
    assert not re.search(r"foreach\s*\(\$k in \$vars\.Keys\)\s*\{\s*\[Environment\]::SetEnvironmentVariable", ps1)
    for text in (sh, ps1):
        assert "launcher_env_allowlist.py" in text


def test_the_no_python_fallback_reads_the_same_implicit_reads():
    """Both twins grep IMPLICIT_READS out of the tool when python is missing.

    If the dict's layout changes so the grep misses an entry, the fallback
    silently drops that reader's variable. Run the exact bash pipeline.
    """
    sh = SH.read_text(encoding="utf-8")
    pipeline = "sed -n '/^IMPLICIT_READS/,/^}/p' \"$_allow_tool\" | grep -oE '^    \"[A-Za-z_][A-Za-z0-9_]*\"' | tr -d ' \"'"
    assert pipeline in sh
    proc = subprocess.run([_bash(), "-c", pipeline], capture_output=True, text=True,
                          env=dict(os.environ, _allow_tool=str(TOOL)), timeout=30)
    assert set(proc.stdout.split()) == set(lea.IMPLICIT_READS)
    ps_rx = re.compile(r'(?m)^    "([A-Za-z_][A-Za-z0-9_]*)"')
    block = re.search(r"(?ms)^IMPLICIT_READS.*?^\}", TOOL.read_text(encoding="utf-8")).group(0)
    assert set(ps_rx.findall(block)) == set(lea.IMPLICIT_READS)
    assert "(?ms)^IMPLICIT_READS.*?^\\}" in PS1.read_text(encoding="utf-8")


def test_sh_repo_less_mode_still_exports_the_pinned_file(tmp_path: Path):
    """Codex #3464: with no repo, an explicit PMOVES_ENV_SHARED is still honoured.

    There is no tool and no roster to cut a list from, so intersecting against
    them exported nothing and the session started with zero MCP credentials.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(ENV_DUMPER, encoding="utf-8")
    stub.chmod(0o755)
    env_out = tmp_path / "env.bin"
    env = _base_env(tmp_path, bin_dir, env_out)
    nowhere = tmp_path / "not-a-repo"
    nowhere.mkdir()
    env["PMOVES_LAUNCHER_ROOT"] = str(nowhere)
    proc = subprocess.run([_bash(), str(SH), "--print", "hi"],
                          capture_output=True, text=True, env=env, timeout=240)
    child = _parse_env0(env_out.read_bytes()) if env_out.exists() else {}
    assert child, f"stub claude was never reached; stderr:\n{proc.stderr}"
    assert child.get("SUPABASE_REST_URL") == "http://rest-from-file"
    assert child.get("POSTGRES_PASSWORD") == "leak-sentinel-pg"   # pinned by hand: all of it
    assert "no repo, so no allowlist" in proc.stderr
