"""Unit tests for pmoves.tools.bash_resolver.

The Windows branch is exercised on every OS by patching the module's
``_is_windows`` / ``_isfile`` seams and passing an explicit env mapping, so
these run identically on Linux CI and on a Windows node. Paths are Windows
strings handled with ntpath inside the resolver.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from pmoves.tools import bash_resolver as br

PF = r"C:\Program Files"
PF86 = r"C:\Program Files (x86)"
LAD = r"C:\Users\op\AppData\Local"
GIT_PF = PF + r"\Git\bin\bash.exe"
GIT_PF86 = PF86 + r"\Git\bin\bash.exe"
GIT_LAD = LAD + r"\Programs\Git\bin\bash.exe"
WSL_STUB = r"C:\Windows\System32\bash.exe"
STORE_ALIAS = LAD + r"\Microsoft\WindowsApps\bash.exe"


def _env(path: str = "", **extra: str) -> dict:
    env = {
        "ProgramFiles": PF,
        "ProgramFiles(x86)": PF86,
        "LOCALAPPDATA": LAD,
        "SystemRoot": r"C:\Windows",
        "PATH": path,
    }
    env.update(extra)
    return env


@pytest.fixture
def windows(monkeypatch):
    """Force the Windows branch; returns the set of paths that 'exist'."""
    existing: set = set()
    monkeypatch.setattr(br, "_is_windows", lambda: True)
    monkeypatch.setattr(br, "_isfile", lambda p: p.lower() in {e.lower() for e in existing})
    return existing


def test_non_windows_returns_bare_bash_unchanged(monkeypatch):
    monkeypatch.setattr(br, "_is_windows", lambda: False)
    monkeypatch.setattr(br, "_isfile", lambda p: pytest.fail("must not probe the filesystem"))
    assert br.resolve_bash(_env()) == "bash"
    assert br.resolve_sh(_env()) == "sh"


def test_program_files_git_wins_over_everything(windows):
    windows.update({GIT_PF, GIT_PF86, GIT_LAD, r"C:\tools\bash.exe"})
    assert br.resolve_bash(_env(path=r"C:\tools")) == GIT_PF


def test_x86_then_localappdata_in_shim_order(windows):
    windows.update({GIT_PF86, GIT_LAD})
    assert br.resolve_bash(_env()) == GIT_PF86
    windows.discard(GIT_PF86)
    assert br.resolve_bash(_env()) == GIT_LAD


def test_path_hit_used_when_no_git_install(windows):
    windows.add(r"C:\msys64\usr\bin\bash.exe")
    assert br.resolve_bash(_env(path=r"C:\msys64\usr\bin")) == r"C:\msys64\usr\bin\bash.exe"


def test_system32_wsl_stub_is_rejected_and_skipped(windows):
    # System32 FIRST on PATH, a real bash later: the stub must be skipped.
    windows.update({WSL_STUB, r"D:\Git\usr\bin\bash.exe"})
    got = br.resolve_bash(_env(path=r"C:\Windows\System32;D:\Git\usr\bin"))
    assert got == r"D:\Git\usr\bin\bash.exe"


def test_system32_only_raises_never_falls_back(windows):
    windows.add(WSL_STUB)
    with pytest.raises(br.BashNotFoundError) as exc:
        br.resolve_bash(_env(path=r"C:\WINDOWS\system32"))  # case differs, still rejected
    msg = str(exc.value)
    assert WSL_STUB.lower() in msg.lower()  # names what it rejected
    assert GIT_PF in msg and GIT_PF86 in msg and GIT_LAD in msg  # names what it searched
    assert "Rejected" in msg


def test_windowsapps_alias_is_rejected(windows):
    windows.add(STORE_ALIAS)
    with pytest.raises(br.BashNotFoundError):
        br.resolve_bash(_env(path=LAD + r"\Microsoft\WindowsApps"))


@pytest.mark.parametrize(
    "path",
    [
        WSL_STUB,
        r"c:\windows\system32\BASH.EXE",
        r"C:\Windows\SysWOW64\bash.exe",
        r"C:\Windows\Sysnative\bash.exe",
        STORE_ALIAS,
    ],
)
def test_is_rejected_windows_bash(path):
    assert br.is_rejected_windows_bash(path, _env())


@pytest.mark.parametrize("path", [GIT_PF, r"C:\msys64\usr\bin\bash.exe", r"C:\Windows-tools\bash.exe"])
def test_is_not_rejected(path):
    assert not br.is_rejected_windows_bash(path, _env())


def test_nonstandard_systemroot_honoured(windows):
    windows.add(r"E:\Win\System32\bash.exe")
    with pytest.raises(br.BashNotFoundError):
        br.resolve_bash(_env(path=r"E:\Win\System32", SystemRoot=r"E:\Win"))


def test_env_lookup_is_case_insensitive(windows):
    # dict(os.environ) on Windows upper-cases keys; that copy must still work.
    windows.add(GIT_PF)
    env = {k.upper(): v for k, v in _env().items()}
    assert br.resolve_bash(env) == GIT_PF


def test_unset_vars_are_reported_not_crashed(windows):
    with pytest.raises(br.BashNotFoundError) as exc:
        br.resolve_bash({"PATH": ""})
    assert "variable unset" in str(exc.value)


def test_resolve_sh_searches_sh_exe(windows):
    windows.add(PF + r"\Git\bin\sh.exe")
    assert br.resolve_sh(_env()) == PF + r"\Git\bin\sh.exe"


@pytest.mark.skipif(os.name != "nt", reason="live Windows-host check")
def test_live_windows_resolution_is_not_wsl():
    """On a Windows node the resolved bash must report an MSYS/MINGW kernel."""
    bash = br.resolve_bash()
    assert os.path.isabs(bash) and not br.is_rejected_windows_bash(bash)
    out = subprocess.run([bash, "-c", "uname -s"], capture_output=True, text=True, timeout=60).stdout
    assert out.startswith(("MINGW", "MSYS")), out
