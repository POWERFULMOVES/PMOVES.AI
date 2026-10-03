"""Resolve the bash a Python subprocess should execute -- never the WSL stub.

Why this exists
---------------
On Windows, ``subprocess.run(["bash", ...])`` does NOT run the bash that
``shutil.which("bash")`` reports. CreateProcess searches the application
directory, the current directory and the *system directory* before PATH, so a
bare ``"bash"`` resolves to ``C:\\Windows\\System32\\bash.exe`` -- the WSL
launcher -- whenever WSL is installed. Measured on Z890 (2026-09-29):
``shutil.which("bash")`` -> ``C:\\Program Files\\Git\\usr\\bin\\bash.EXE``, but
``subprocess.run(["bash", "-c", "uname -s"])`` -> ``Linux`` (Ubuntu in WSL).

That is a silent OS switch: the child gets a different filesystem view
(``/mnt/d`` instead of ``D:``), different tooling (no uv, an older python) and
sometimes a stale clone of the repo, and still exits 0. The Windows ``.bat``
launchers in ``pmoves/scripts/windows/`` already guard against it by probing
the Git for Windows install first; this module is that same guard for Python.

Contract
--------
* Non-Windows: return ``"bash"`` unchanged (PATH lookup by the OS is correct).
* Windows: return an ABSOLUTE path, searched in this order --
    1. ``%ProgramFiles%\\Git\\bin\\bash.exe``        (same order as the .bat shims)
    2. ``%ProgramFiles(x86)%\\Git\\bin\\bash.exe``
    3. ``%LOCALAPPDATA%\\Programs\\Git\\bin\\bash.exe`` (per-user Git install)
    4. the first PATH hit that is NOT under ``%SystemRoot%\\System32`` (or
       SysWOW64 / Sysnative) and NOT under a ``WindowsApps`` directory.
  If nothing qualifies, raise :class:`BashNotFoundError` naming every location
  searched. There is deliberately no fallback to the WSL stub.

Why ``Git\\bin\\bash.exe`` and not ``Git\\usr\\bin\\bash.exe``: ``bin\\bash.exe``
is Git's launcher. It PREPENDS ``/mingw64/bin:/usr/bin`` to PATH, so coreutils
are always found even when the caller's PATH carries no Git directory
(measured on Z890: ``usr\\bin\\bash.exe`` with PATH=System32 cannot even run
``uname``). The cost of that choice: a caller that stubs a coreutil by putting
a directory FIRST on PATH (tests stubbing ``mv``) is shadowed by Git's
``/usr/bin`` on Windows. Stub non-coreutils (gh, docker, kilo) or use a
POSIX host for such tests.

``resolve_sh()`` is the same search for ``sh`` (Git for Windows ships
``bin\\sh.exe``); off Windows it returns ``"sh"`` so a dash-based /bin/sh keeps
exercising POSIX-sh scripts as POSIX sh.

Usage::

    from pmoves.tools.bash_resolver import resolve_bash
    subprocess.run([resolve_bash(), "-c", "uname -s"])
"""

from __future__ import annotations

import ntpath
import os
from typing import List, Mapping, Optional, Tuple

__all__ = ["BashNotFoundError", "resolve_bash", "resolve_sh", "is_rejected_windows_bash"]

# Git for Windows install roots, in the order the .bat shims probe them.
_GIT_BIN_DIRS: Tuple[Tuple[str, str], ...] = (
    ("ProgramFiles", r"Git\bin"),
    ("ProgramFiles(x86)", r"Git\bin"),
    ("LOCALAPPDATA", r"Programs\Git\bin"),
)


class BashNotFoundError(RuntimeError):
    """No acceptable bash found on Windows (the WSL stub is never acceptable)."""


def _is_windows() -> bool:
    # A function rather than a constant so tests can exercise the Windows branch
    # on any OS without patching the process-global os.name (which would also
    # flip pathlib's flavour and break unrelated code).
    return os.name == "nt"


def _isfile(path: str) -> bool:
    return os.path.isfile(path)


def _get(env: Mapping[str, str], name: str) -> Optional[str]:
    """Case-insensitive lookup: Windows env names are, but a plain dict copy of
    os.environ is not (``dict(os.environ)`` upper-cases every key on Windows)."""
    if name in env:
        return env[name]
    lowered = name.lower()
    for key, value in env.items():
        if key.lower() == lowered:
            return value
    return None


def _norm(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path))


def _system_dirs(env: Mapping[str, str]) -> List[str]:
    system_root = _get(env, "SystemRoot") or _get(env, "windir") or r"C:\Windows"
    return [_norm(ntpath.join(system_root, sub)) for sub in ("System32", "SysWOW64", "Sysnative")]


def is_rejected_windows_bash(path: str, env: Optional[Mapping[str, str]] = None) -> bool:
    """True if *path* is a bash that must never be used: the WSL stub.

    That is anything under %SystemRoot%\\System32 (and its WOW64 aliases) or
    under a WindowsApps directory (the Store's app-execution aliases, which
    also launch WSL).
    """
    env = os.environ if env is None else env
    p = _norm(path)
    for sysdir in _system_dirs(env):
        if p == sysdir or p.startswith(sysdir + "\\"):
            return True
    return "windowsapps" in p.split("\\")


def _git_candidates(env: Mapping[str, str], exe: str) -> List[Tuple[str, Optional[str]]]:
    """(label, absolute candidate -- or None when the base variable is unset)."""
    out: List[Tuple[str, Optional[str]]] = []
    for var, sub in _GIT_BIN_DIRS:
        tail = ntpath.join(sub, exe)
        base = _get(env, var)
        out.append((f"%{var}%\\{tail}", ntpath.join(base, tail) if base else None))
    return out


def _resolve(name: str, env: Optional[Mapping[str, str]]) -> str:
    if not _is_windows():
        return name
    env = os.environ if env is None else env
    exe = f"{name}.exe"

    searched: List[str] = []
    for label, candidate in _git_candidates(env, exe):
        if candidate is None:
            searched.append(f"{label} (variable unset)")
            continue
        searched.append(candidate)
        if _isfile(candidate):
            return candidate

    rejected: List[str] = []
    for entry in (_get(env, "PATH") or "").split(";"):
        entry = entry.strip().strip('"')
        if not entry:
            continue
        for fname in (exe, name):
            candidate = ntpath.join(entry, fname)
            if not _isfile(candidate):
                continue
            if is_rejected_windows_bash(candidate, env):
                rejected.append(candidate)
                break  # same directory: the other spelling is the same stub
            return ntpath.abspath(candidate)

    lines = [f"No usable {name} found on Windows. Searched, in order:"]
    lines += [f"  - {s}" for s in searched]
    lines.append("  - PATH entries (excluding %SystemRoot%\\System32 and WindowsApps)")
    if rejected:
        lines.append("Rejected (WSL launcher -- it would run a different OS):")
        lines += [f"  - {r}" for r in rejected]
    lines.append(
        f"Install Git for Windows (https://git-scm.com/download/win) "
        f"or put a non-WSL {name} on PATH."
    )
    raise BashNotFoundError("\n".join(lines))


def resolve_bash(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the bash executable to put in argv[0]. See the module docstring."""
    return _resolve("bash", env)


def resolve_sh(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the POSIX sh executable to put in argv[0]. See the module docstring."""
    return _resolve("sh", env)
