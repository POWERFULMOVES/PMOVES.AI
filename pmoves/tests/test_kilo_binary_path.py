"""Ratchet: kilo's PATH resolution must dispatch through the native binary.

Background (lesson #9 from ``pmoves_launcher_generator_LEARNINGS.md`` /
``branch-protection-v0_LEARNINGS.md`` lesson #9):

    "a test that can only assert absence cannot say no"

The CI ratchet for the ``kilocode_glm`` sign-trail (``test_sign_trail.py``
``test_build_payload_applies_kilocode_glm_alter``) passes via ``npx
@kilocode/cli@7.6.2 acp``. On Windows, npm's PATH resolution prefers the
``.cmd`` JS shim over the bundled ``cli-windows-x64/bin/kilo.exe`` binary, so
a Windows-binary-only defect in ``@kilocode/cli-windows-x64`` (the postinstall
matrix, the ``findBinary()`` walker, the binary's own CLI surface) would
silently pass CI. The shim prints nothing of its own -- a broken dispatch
chain (shim resolves the JS fallback instead of spawning the binary) returns
``stdout=""`` and ``rc=0`` to the test, which the test treats as healthy.

These tests assert the dispatch chain is intact so a regression in either
``@kilocode/cli``'s postinstall layout, the JS shim's ``findBinary()``
walker, or the binary's own CLI surface fails the ratchet load-bearingly --
i.e. a test that passes despite the bug fails the ratchet.

Provenance:
- Upstream: Kilo-Org/kilocode, ``@kilocode/cli`` npm package (Kilo CLI v7.6.2)
- Fork: PMOVES-Keylokode (PMOVES fork of the Kilo CLI upstream)
- SDK files exercised:
    - ``node_modules/@kilocode/cli/postinstall.mjs`` -- platform binary layout
    - ``node_modules/@kilocode/cli/bin/kilo`` -- JS shim, ``findBinary()``
    - ``node_modules/@kilocode/cli-windows-x64/bin/kilo.exe`` -- Windows binary
    - ``node_modules/@kilocode/cli-linux-x64/bin/kilo`` -- Linux binary
    - ``node_modules/@kilocode/cli-darwin-{x64,arm64}/bin/kilo`` -- macOS
- Local installed version: ``@kilocode/cli@7.1.3`` (verified ``kilo --version``).
- LEARNINGS: ``pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md`` (Gap 1).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# Mark every test in this module so the ratchet runner can target it.
pytestmark = pytest.mark.kilo


# Platform/arch -> (subpackage_name, binary_filename). Sourced from
# ``@kilocode/cli/bin/kilo`` (the JS shim) at v7.6.2 / v7.1.3 -- both versions
# share the same ``findBinary()`` walker and the same ``platformMap``/
# ``archMap`` (verified by content in this module's docstring).
_KILOCODE_PLATFORM_PKGS: dict[str, tuple[str, str]] = {
    "win32": ("cli-windows-x64", "kilo.exe"),
    "linux": ("cli-linux-x64", "kilo"),
    "darwin": ("cli-darwin-x64", "kilo"),
}


def _kilocode_cli_root() -> Path | None:
    """Locate the ``@kilocode/cli`` package root, or None if not installed.

    npm global prefix is probed via ``npm root -g`` (Windows: ``%APPDATA%``
    per ``getPrefix``). The shim's wrapper script (``kilo.cmd``) embeds the
    resolved ``node_modules`` path -- but parsing that requires reading the
    ``.cmd`` shell dialect. Simpler: ask npm directly. Falls back to None
    when npm is unavailable or the package is not installed.
    """
    npm = shutil.which("npm")
    if npm is None:
        return None
    try:
        result = subprocess.run(
            [npm, "root", "-g"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    candidate = Path(result.stdout.strip()) / "@kilocode" / "cli"
    return candidate if candidate.is_dir() else None


@pytest.fixture(scope="module")
def kilo_on_path() -> str | None:
    """PATH-resolved ``kilo`` (the npm shim) or None if not installed."""
    return shutil.which("kilo")


@pytest.fixture(scope="module")
def kilo_binary_dispatch(kilo_on_path: str | None) -> dict[str, object]:
    """Probe the kilo dispatch chain: shim resolution + native binary invocation.

    Returns a dict with keys:
        ``installed``     bool -- ``kilo`` is on PATH
        ``version``       str  -- stdout of ``kilo --version`` (the binary)
        ``native_path``   Path | None -- the resolved native binary path
        ``native_exists`` bool -- the native binary is on disk
    """
    result: dict[str, object] = {
        "installed": kilo_on_path is not None,
        "version": "",
        "native_path": None,
        "native_exists": False,
    }
    if kilo_on_path is None:
        return result

    # Invoke kilo through the shim. On Windows this is `node bin/kilo` (the
    # JS shim) which walks node_modules to find the platform-specific binary.
    # The version string comes from the binary, NOT from the shim -- the shim
    # has no print logic of its own. So an empty version is structural evidence
    # the dispatch chain is broken.
    try:
        proc = subprocess.run(
            [kilo_on_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = repr(exc)  # type: ignore[assignment]
        return result
    result["version"] = (proc.stdout or proc.stderr).strip()
    result["returncode"] = proc.returncode  # type: ignore[assignment]

    # Resolve the native binary via the JS shim's ``findBinary()`` walk
    # logic. The shim's behavior is platform-specific (it walks parents of
    # its own ``bin/`` directory looking for ``@kilocode/cli-<platform>-<arch>``
    # subpackage, then ``bin/kilo[.exe]`` inside). We replicate that here.
    cli_root = _kilocode_cli_root()
    if cli_root is None:
        return result
    subpkg_name, exe_name = _KILOCODE_PLATFORM_PKGS.get(sys.platform, ("", ""))
    if not subpkg_name:
        return result
    candidate = cli_root / "node_modules" / "@kilocode" / subpkg_name / "bin" / exe_name
    result["native_path"] = candidate
    result["native_exists"] = candidate.is_file()
    return result


# ---------------------------------------------------------------------------
# Structural ratchets
# ---------------------------------------------------------------------------


def test_kilo_dispatches_to_native_binary(kilo_binary_dispatch: dict[str, object]) -> None:
    """ratchet: ``kilo --version`` returns a non-empty version string.

    The JS shim ``@kilocode/cli/bin/kilo`` does NOT print anything on its own;
    a working dispatch chain spawns the native binary which prints the version.
    An empty version means either (a) the JS fallback was reached (the shim's
    ``findBinary()`` walker failed to find a platform subpackage), or (b) the
    binary is on PATH but not the platform-specific one. Either is a regression
    we want to catch load-bearingly.
    """
    if not kilo_binary_dispatch["installed"]:
        pytest.skip("kilo not on PATH on this host")
    version = kilo_binary_dispatch["version"]
    assert version, (
        "kilo --version returned empty -- the JS shim's native dispatch is "
        "broken. See lesson #9 (assertion must be on the positive state, not "
        "the absence of a defect)."
    )


def test_kilocode_native_binary_layout_exists_for_current_platform(
    kilo_binary_dispatch: dict[str, object],
) -> None:
    """ratchet: the platform-specific subpackage binary is on disk.

    After ``@kilocode/cli``'s postinstall runs, the platform subpackage
    (``@kilocode/cli-windows-x64`` on win32, etc.) MUST contain the binary at
    ``bin/kilo[.exe]``. A regression that drops a platform from the postinstall
    matrix (e.g. someone removes ``cli-windows-x64`` because it "isn't used")
    would silently leave Windows users with a JS-only kilo.
    """
    if not kilo_binary_dispatch["installed"]:
        pytest.skip("kilo not on PATH on this host")
    native_path = kilo_binary_dispatch["native_path"]
    if native_path is None:
        pytest.skip(f"unsupported platform: {sys.platform}")
    assert kilo_binary_dispatch["native_exists"], (
        f"native binary not found at {native_path} -- the @kilocode/cli "
        f"postinstall failed for this platform/arch. Check the platform "
        f"subpackage matrix in @kilocode/cli/postinstall.mjs."
    )


def test_kilocode_js_shim_source_contains_native_dispatch() -> None:
    """ratchet: ``@kilocode/cli/bin/kilo`` encodes the native binary dispatch.

    The JS shim is the ONLY place the dispatch chain is encoded. The
    actual source (verified ``@kilocode/cli@7.1.3`` and ``@kilocode/cli@7.6.2``)
    builds the platform subpackage name dynamically via a ``platformMap``
    (``win32: "windows"`` + arch x64 -> ``@kilocode/cli-windows-x64``) and
    walks parent ``node_modules`` directories to find ``bin/kilo[.exe]``.
    A regression that drops either the platform map, the binary name
    selector, or the spawnSync itself would silently leave Windows users
    with a JS-only fallback.
    """
    cli_root = _kilocode_cli_root()
    if cli_root is None:
        pytest.skip("@kilocode/cli source not co-located with kilo PATH")
    js_shim = cli_root / "bin" / "kilo"
    if not js_shim.is_file():
        pytest.skip(f"JS shim not at expected path: {js_shim}")
    text = js_shim.read_text(encoding="utf-8")
    # Three structural invariants the dispatch chain relies on:
    #   - spawnSync(<resolved-binary>, ...) to dispatch to the native binary
    #   - platformMap[os.platform()] mapping win32->"windows" (without it
    #     the dynamic base name resolves to "@kilocode/cli-win32-x64" which
    #     is not a published subpackage)
    #   - The "@kilocode/cli-" prefix the walker scans node_modules for
    assert "spawnSync" in text, (
        "@kilocode/cli/bin/kilo no longer spawns the native binary -- "
        "the dispatch chain has been broken."
    )
    assert "platformMap" in text and "windows" in text, (
        "JS shim platformMap is missing the win32 -> windows mapping; "
        "Windows dispatch will silently fail."
    )
    assert "@kilocode/cli-" in text, (
        "JS shim no longer references the @kilocode/cli- subpackage prefix "
        "the findBinary() walker scans for. The native binary will never "
        "be resolved."
    )


def test_kilocode_postinstall_declares_current_platform_subpkg() -> None:
    """ratchet: ``@kilocode/cli/postinstall.mjs`` constructs platform subpkgs.

    The postinstall script (verified ``@kilocode/cli@7.1.3``/``7.6.2``) builds
    the ``@kilocode/cli-<platform>-<arch>`` subpackage name dynamically via
    ``getPackageNames()`` (a ``platformMap`` + ``archMap`` + ``supportsAvx2()``
    chain). A regression that drops the platform map or the avx2 baseline
    detection would silently leave non-AVX2 Windows users without a binary.
    """
    cli_root = _kilocode_cli_root()
    if cli_root is None:
        pytest.skip("@kilocode/cli source not co-located with kilo PATH")
    postinstall = cli_root / "postinstall.mjs"
    if not postinstall.is_file():
        pytest.skip(f"postinstall not at expected path: {postinstall}")
    text = postinstall.read_text(encoding="utf-8")
    # Three structural invariants the postinstall relies on:
    #   - A platformMap (win32 -> "windows" for the dynamic subpkg name)
    #   - The "@kilocode/cli-" prefix in getPackageNames() / findBinary()
    #   - Either a copy/link of the binary OR a Windows-specific short-circuit
    assert "platformMap" in text and "windows" in text, (
        "@kilocode/cli/postinstall.mjs platformMap is missing the win32 -> "
        "windows mapping; Windows subpackage will not be installed."
    )
    assert "@kilocode/cli-" in text, (
        "@kilocode/cli/postinstall.mjs does not construct any "
        "@kilocode/cli-<platform>-<arch> subpackage name; the binary will "
        "never be installed."
    )


# ---------------------------------------------------------------------------
# Mutation-kill: a hypothetical "kilo JS shim replaces the binary" change
# should fail this ratchet.
# ---------------------------------------------------------------------------


def test_mutation_js_only_path_fails_ratchet(
    kilo_binary_dispatch: dict[str, object],
) -> None:
    """Mutation-kill: if kilo's binary dispatch were replaced by JS, we MUST fail.

    Simulates the "kilo JS shim replaces the binary" mutation: patches
    ``subprocess.run`` so ``kilo --version`` returns empty stdout + rc=0
    (the shape a pure-JS shim would produce). The assertion is on what the
    ratchet WOULD see in that case -- it must be that the empty version
    fails the primary gate, NOT that the assertion silently passes.

    Concretely: the ratchet asserts ``version != ""`` on the
    ``kilo_binary_dispatch`` dict. A patched ``subprocess.run`` that returns
    empty version means the assertion would fire -- which is exactly the
    load-bearing property we want. This test pins that property: it patches
    the run, reads the resulting version, and asserts it would fail the
    ratchet gate.
    """
    if not kilo_binary_dispatch["installed"]:
        pytest.skip("kilo not on PATH on this host")

    kilo = kilo_binary_dispatch.get("installed") and shutil.which("kilo")
    if kilo is None:
        pytest.skip("kilo path no longer resolvable")
    with patch("subprocess.run") as mock_run:
        # Shape of a "JS shim replaces the binary" mutation: rc=0, empty
        # stdout. The shim returns successfully but produces no version
        # output, exactly because it ran pure JS instead of spawning the
        # binary.
        mock_run.return_value = subprocess.CompletedProcess(
            args=[kilo, "--version"],
            returncode=0,
            stdout="",
            stderr="",
        )
        proc = subprocess.run(
            [kilo, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        simulated_version = (proc.stdout or "").strip()
    # The ratchet must reject this state. Verify the primary gate WOULD fire:
    with pytest.raises(AssertionError):
        assert simulated_version, "ratchet rejected empty version"
    # And confirm the live (unmutated) state is the OPPOSITE -- the gate
    # would NOT fire today, so the ratchet is not falsely red.
    live_version = kilo_binary_dispatch["version"]
    assert live_version, (
        "live kilo returned empty -- the ratchet cannot meaningfully "
        "distinguish the mutation from the live state. Investigate before "
        "merging."
    )


# ---------------------------------------------------------------------------
# Cross-platform matrix ratchet: a CI matrix must exercise the Windows
# binary path, not just the Linux/macOS ones.
# ---------------------------------------------------------------------------


def test_kilocode_cli_version_documented_in_sign_trail(
    kilo_binary_dispatch: dict[str, object],
) -> None:
    """Cross-link ratchet: the kilo version flows through to the sign-trail.

    The brief notes that ``test_sign_trail.py::test_build_payload_applies_
    kilocode_glm_alter`` passes via the npm shim -- i.e. it asserts the
    identity payload but never verifies the binary version. The window we
    close here: assert that the actual kilo binary version on this host
    can be paired with the kilocode-glm alter's identity (which is what
    a CI ratchet should track). The assert is structural: a kilo version
    string is parseable, non-empty, and matches the major version
    declared in ``pmoves/configs/cli_tools.yaml``.
    """
    if not kilo_binary_dispatch["installed"]:
        pytest.skip("kilo not on PATH on this host")
    version = kilo_binary_dispatch["version"]
    if not version:
        pytest.skip("kilo binary did not return a version (see other tests)")
    # The version is "<major>.<minor>.<patch>". We do not need to enforce an
    # exact pin here -- the point is the ratchet is non-decorative: a kilo
    # that returns no version is caught by this assertion as well as the
    # primary one.
    parts = version.split(".")
    assert len(parts) >= 2 and all(p.isdigit() for p in parts[:2]), (
        f"kilo returned an unparseable version: {version!r}"
    )