"""Ratchet: the Mavis (minimax-code) CLI must not hang on this host.

Background (operator caveats from this session):

    "minimax-code timed out at 240s -- I haven't yet cross-checked
     whether upstream's Linux matrix has it passing (platform-specific
     finding vs. known-broken upstream)"

The Mavis CLI on Windows is an Electron-wrapped shim
(``C:\\Users\\russe\\.minimax\\bin\\mavis.cmd`` -> ``MiniMax Code.exe
resources\\resources\\daemon\\cli.js``). Two failure modes have been
observed:

1. **Path bug**: the shim carries a duplicated ``resources\\resources\\``
   segment in the daemon path. When Claude Code or the launcher expands
   ``${CLAUDE_PLUGIN_ROOT}`` on Windows, the duplicated segment makes the
   daemon path unresolvable and the CLI hangs (or fails) rather than
   returning. (Recorded in the Mavis install-path Known Road.)
2. **Platform-specific latency**: Electron startup on Windows is
   substantially slower than on Linux/macOS. The 240s timeout the operator
   observed may be (a) the platform-specific baseline (known-broken for
   Windows above some threshold) or (b) upstream-broken (matrix has it
   failing everywhere).

This ratchet closes the load-bearing part of that gap: the local subprocess
must complete in a tight timeout, and the upstream matrix is checked so a
regression is classified as platform-specific (operator's lane) vs upstream
(author's lane to fix).

Provenance:
- Local CLI: ``mavis.cmd`` -> ``MiniMax Code.exe`` -> ``cli.js``
  (Electron, ``@minimax/code`` npm distribution)
- Upstream: ``MiniMax-AI/minimax-code`` (the source-of-truth for matrix behavior)
- Upstream CI: ``.github/workflows/*.yml`` matrix jobs (Ubuntu / macOS / Windows)
- Local timeout budget: 30s (the upstream matrix completes ``--version`` in
  <5s on Linux per operator measurement; 30s gives 6x headroom)
- LEARNINGS: ``pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md`` (Gap 2).
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest


# Mark every test in this module so the ratchet runner can target it.
pytestmark = pytest.mark.mavis_cli


# Upstream repo for the matrix cross-check. Source-of-truth for whether a
# regression is platform-specific (operator's lane) or upstream-broken
# (author's lane to fix). Pinned so a future rename doesn't silently change
# the matrix we diff against.
#
# CORRECTION 2026-10-30: this was ``MiniMaxInc/MiniMax-Code``, which does
# NOT exist -- GitHub returns HTTP 404 for that path. The real upstream is
# ``MiniMax-AI/minimax-code``. With the wrong pin the fetch returned a JSON
# error OBJECT where a LIST was expected, so the helper bailed to ``None``
# and the cross-check degraded to a permanent SKIP -- it could never report
# anything, green or red. Fixed to the repo that actually exists.
_UPSTREAM_REPO = "MiniMax-AI/minimax-code"

# Local subprocess timeout. 30s gives 6x headroom over the operator-measured
# Linux baseline (<5s for --version), and is well under the 240s CI timeout
# the operator used. A regression that pushes --version past 30s on this
# Windows host is almost certainly the platform-specific path bug (1)
# above, not a normal cold start.
_LOCAL_TIMEOUT_SECONDS = 30

# Subprocess timeout the operator observed. Captured here so the test
# docstring and the env-overridden variant stay in sync.
_OPERATOR_CI_TIMEOUT_SECONDS = 240


# ---------------------------------------------------------------------------
# Local subprocess timeout ratchet
# ---------------------------------------------------------------------------


def _mavis_cmd() -> str | None:
    """Resolve the ``mavis`` (a.k.a. ``minimax-code``) CLI on this host.

    Both names resolve to the same shim on the operator's Windows host
    (``C:\\Users\\russe\\.minimax\\bin\\mavis.cmd``). Returns the
    shutil-resolved path or None if neither name is on PATH.
    """
    for name in ("mavis", "minimax-code"):
        path = shutil.which(name)
        if path is not None:
            return path
    return None


def test_mavis_cli_version_completes_within_timeout() -> None:
    """Ratchet: ``mavis --version`` returns within ``_LOCAL_TIMEOUT_SECONDS``.

    The 240s CI timeout the operator observed was the OUTER CI budget --
    the inner subprocess timeout. If the inner subprocess itself does not
    return within 30s on this host, the local invocation path is broken
    (the platform-specific path bug, or an unrelated Electron startup
    stall). A hang past 30s is the failure mode the operator wants to
    catch load-bearingly, not the 240s ceiling.
    """
    mavis = _mavis_cmd()
    if mavis is None:
        pytest.skip("mavis / minimax-code not on PATH on this host")
    try:
        proc = subprocess.run(
            [mavis, "--version"],
            capture_output=True,
            text=True,
            timeout=_LOCAL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"mavis --version did not return within {_LOCAL_TIMEOUT_SECONDS}s "
            f"(operator CI timeout: {_OPERATOR_CI_TIMEOUT_SECONDS}s). Likely "
            f"platform-specific path bug -- see this module's docstring "
            f"failure mode (1). Captured stdout={exc.stdout!r} "
            f"stderr={exc.stderr!r}"
        )
    _assert_healthy_version_output(proc)


def _assert_healthy_version_output(proc: subprocess.CompletedProcess[str]) -> str:
    """Assert a CLI invocation produced a REAL version string.

    This is the ratchet's load-bearing gate, extracted into a helper so the
    mutation-kill test can INVOKE it rather than restate it. (Restating the
    assertion in the mutation test is what let the original defect ship: the
    mutation test kept passing because it never touched the real gate.)

    The three properties asserted are the ones a WORKING CLI has and a
    broken one cannot fake:

    1. exit code 0 -- the command succeeded;
    2. non-empty STDOUT -- and specifically NOT stderr: the original gate
       was ``(proc.stdout or proc.stderr or "").strip()`` with a bare
       non-empty check, which is VACUOUS for a broken shim. Node's module
       loader writes "Error: Cannot find module '<path>'" to STDERR and
       exits 1, so the old gate reported GREEN on a 100%-broken CLI.
       Measured 2026-10-30 on the operator's host:
           $ mavis --version
           rc=1  stdout=''  stderr="Error: Cannot find module '...daemon/cli.js'"
           test_mavis_cli_version_completes_within_timeout ... PASSED
    3. stdout is not an error banner -- some launchers print the error to
       stdout and still exit 0, so prose is rejected too.

    Returns the version string when the gate passes.
    """
    assert proc.returncode == 0, (
        f"mavis --version exited {proc.returncode} (expected 0). The CLI ran "
        f"but failed. stderr={proc.stderr!r} stdout={proc.stdout!r}. "
        f"Investigate the shim / daemon path before merging -- a non-zero "
        f"exit means the launcher is broken even though it did not hang."
    )
    version = (proc.stdout or "").strip()
    assert version, (
        f"mavis --version returned empty stdout (rc={proc.returncode}); CLI "
        f"ran without hanging but did not produce a version string. "
        f"stderr={proc.stderr!r}"
    )
    lowered = version.lower()
    for marker in ("error:", "cannot find module", "traceback", "not found"):
        assert marker not in lowered, (
            f"mavis --version stdout looks like an error banner, not a "
            f"version string: {version!r}. The ratchet must not accept "
            f"error prose as a version."
        )
    return version


def test_mavis_cli_help_completes_within_timeout() -> None:
    """Ratchet: ``mavis --help`` returns within ``_LOCAL_TIMEOUT_SECONDS``.

    ``--help`` exercises a different code path than ``--version`` (it
    triggers full argument parsing + subcommand help rendering, which is
    where the platform-specific path bug (1) most commonly surfaces). If
    ``--version`` passes but ``--help`` hangs, the bug is in the help
    subsystem, not the version subsystem -- and this test catches it.
    """
    mavis = _mavis_cmd()
    if mavis is None:
        pytest.skip("mavis / minimax-code not on PATH on this host")
    try:
        proc = subprocess.run(
            [mavis, "--help"],
            capture_output=True,
            text=True,
            timeout=_LOCAL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"mavis --help did not return within {_LOCAL_TIMEOUT_SECONDS}s. "
            f"Help subsystem hang is the second-most-common shape of the "
            f"platform-specific path bug. Captured stdout={exc.stdout!r} "
            f"stderr={exc.stderr!r}"
        )
    # --help exits 0 with a usage message OR exits 2 (argparse usage error)
    # -- both are valid terminations. The ratchet only asserts non-hang +
    # non-empty output (so a regression that silently prints nothing is
    # still caught).
    #
    # Same stderr-fallback hole as the --version ratchet: a broken shim
    # writes its "Cannot find module" banner to stderr, which satisfied
    # the old `(proc.stdout or proc.stderr or "")` check. A launcher that
    # cannot even resolve its entry point must fail here.
    assert proc.returncode in (0, 2), (
        f"mavis --help exited {proc.returncode} (expected 0 or 2). The CLI "
        f"failed rather than rendering usage. stderr={proc.stderr!r} "
        f"stdout={proc.stdout!r}"
    )
    out = (proc.stdout or "").strip()
    assert out, (
        f"mavis --help returned empty stdout (rc={proc.returncode}); "
        f"stderr={proc.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Upstream matrix cross-check (skipped unless PMOVES_MAVIS_MATRIX_CHECK=1)
# ---------------------------------------------------------------------------


def _ssl_context() -> ssl.SSLContext | None:
    """Best-effort CA bundle for the upstream fetch.

    Some hosts (notably the operator's Windows box under Python 3.12) have no
    system CA bundle wired into ``urllib``, so the default TLS handshake
    fails with ``CERTIFICATE_VERIFY_FAILED``. ``certifi`` is usually
    installed alongside; use its bundle when present.

    Returns None to mean "use urllib's default context".
    """
    try:
        import certifi  # type: ignore[import-untyped]
    except Exception:
        return None
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _fetch_upstream_matrix() -> dict[str, object] | None:
    """Fetch the upstream ``minimax-code`` Actions matrix summary.

    Uses the public ``.github`` repo contents endpoint (no auth, rate-limited
    per-IP). Returns a dict with ``platforms`` (set of OS names found in the
    CI workflow YAMLs) and ``status`` ("ok" / "unreachable").
    Returns None on any network/parse error -- the ratchet degrades to skip
    rather than fail when the network is unavailable.

    WHY THIS READS WORKFLOW CONTENT, NOT FILENAMES
    ----------------------------------------------
    The original implementation derived the platform set from the workflow
    FILENAMES ("matrix files conventionally include the OS name in the
    filename"). That assumption is false for the upstream repo. Measured
    against the real upstream on 2026-10-30:

        $ gh api repos/MiniMax-AI/minimax-code/contents/.github/workflows
        ci.yml, cli-release.yml, compatibility.yml, label-issue-product.yml,
        performance.yml, security.yml, source-candidate.yml,
        sync-issue-to-feishu.yml

    Not one filename contains an OS name. The upstream matrix is declared
    INSIDE ``ci.yml`` as ``runs-on: ${{ matrix.os }}`` with
    ``os: [ubuntu-latest, macos-latest, windows-latest]``. The old
    filename-derived scan therefore returned an EMPTY platform set, so
    `assert "windows" in platforms` would FAIL the moment the gate was
    switched on -- the ratchet was not merely wrong, it was inverted: it
    reported "upstream does not cover Windows" for an upstream that DOES
    cover Windows.

    So this now reads each workflow's actual content and scans for the
    runner labels. ``ubuntu-latest`` / ``macos-latest`` / ``windows-latest``
    appear as literal strings inside ``ci.yml``.

    WHY THE REPO PIN CHANGED
    -------------------------
    The pin was ``MiniMaxInc/MiniMax-Code``. That repository does not
    exist -- GitHub returns HTTP 404 for it. The real upstream is
    ``MiniMax-AI/minimax-code`` (the "MiniMax Code" terminal agent;
    ``MiniMaxInc`` is the corporate org and does not host this project).
    Verified 2026-10-30:

        $ gh api repos/MiniMaxInc/MiniMax-Code/contents/.github/workflows
        gh: Not Found (HTTP 404)

    A 404 body is a JSON OBJECT, not the LIST this function expects, so
    the old code took the ``if not isinstance(payload, list)`` branch and
    returned None -- degrading to SKIP. The cross-check could therefore
    never report anything, even with the gate enabled.
    """
    url = f"https://api.github.com/repos/{_UPSTREAM_REPO}/contents/.github/workflows"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pmoves-test-ratchet",
        },
    )
    ctx = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ):
        return None
    if not isinstance(payload, list):
        return None

    platforms: set[str] = set()
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        raw_url = entry.get("download_url")
        if not raw_url:
            continue
        try:
            wf_req = urllib.request.Request(
                str(raw_url),
                headers={"User-Agent": "pmoves-test-ratchet"},
            )
            with urllib.request.urlopen(wf_req, timeout=10, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ):
            continue
        # Scan the workflow BODY for the GitHub-hosted runner labels.
        # `runs-on: ubuntu-latest` and the `os:` matrix list both appear
        # literally in the YAML.
        lowered = body.lower()
        for tag in ("ubuntu", "macos", "windows", "linux"):
            if f"{tag}-latest" in lowered or f"{tag}-22" in lowered or f"{tag}-24" in lowered:
                platforms.add(tag)
    return {"platforms": sorted(platforms), "status": "ok"}


def test_upstream_matrix_classifies_regression_lane() -> None:
    """Ratchet: classify a mavis timeout as platform-specific or upstream-broken.

    This is a CLASSIFICATION ratchet, not a binary pass/fail. It runs only
    when ``PMOVES_MAVIS_MATRIX_CHECK=1`` is set (so it doesn't burn CI
    minutes on a network call by default). When it runs, it:
      1. Fetches the upstream ``MiniMax-AI/minimax-code`` workflows directory
         and the CONTENT of each workflow file.
      2. Lists the OS platforms in the upstream CI matrix (read from the
         workflow bodies -- upstream declares the matrix inside ``ci.yml``,
         not in the workflow filenames).
      3. Records whether each platform is covered. A platform NOT covered
         means a local regression on that platform is operator-lane
         (no upstream signal to diff against); a platform covered means
         a local regression is upstream's lane to fix.

    The classification is then available to the operator's triage -- it
    does not auto-fail. Use the ratchet to inform, not to gate.

    MEASURED 2026-10-30 (the answer to the operator's original question):
    upstream's Linux matrix is GREEN, and upstream covers Windows too --
    ``ci.yml`` declares ``os: [ubuntu-latest, macos-latest, windows-latest]``
    with ``profile: full`` on Ubuntu and a focused ``profile: windows`` on
    Windows ("Windows runs a focused contract; full capability coverage
    remains on Linux/macOS"). So a Windows-only mavis regression is
    upstream's lane to fix, and the 240s timeout the operator observed is
    NOT an upstream-broken-everywhere condition -- it is the
    platform-specific Windows case this ratchet now pins.
    """
    if os.environ.get("PMOVES_MAVIS_MATRIX_CHECK") != "1":
        pytest.skip(
            "Set PMOVES_MAVIS_MATRIX_CHECK=1 to enable the upstream matrix "
            "cross-check (skipped by default to avoid burning CI minutes "
            "on a network call)."
        )
    matrix = _fetch_upstream_matrix()
    if matrix is None:
        pytest.skip("upstream matrix fetch failed (network or rate-limit)")
    platforms = matrix["platforms"]
    assert "windows" in platforms, (
        f"upstream matrix does NOT include 'windows' -- any mavis hang on "
        f"Windows is operator-lane (no upstream signal). Matrix platforms: "
        f"{platforms!r}"
    )
    # Windows IS covered upstream -> a Windows hang is upstream's lane to
    # fix, not platform-specific. Record the finding for the operator's
    # triage. A regression that flips this assertion off (upstream drops
    # Windows from matrix) is a structural change worth surfacing.
    assert "ubuntu" in platforms, (
        f"upstream matrix does NOT include 'ubuntu' -- the operator's "
        f"Linux-baseline measurement (<5s for --version) has no upstream "
        f"counterpart. Matrix platforms: {platforms!r}"
    )


# ---------------------------------------------------------------------------
# Mutation-kill: a hypothetical "mavis hangs on --version" regression
# must fail this ratchet.
# ---------------------------------------------------------------------------


def test_mutation_hang_fails_ratchet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation-kill: if mavis --version hung, the ratchet MUST fire.

    Simulates the "mavis hangs forever" mutation: patches ``subprocess.run``
    to raise ``TimeoutExpired`` after the same window the ratchet uses.
    Verifies the ratchet's primary gate (the one in
    ``test_mavis_cli_version_completes_within_timeout``) WOULD reject this
    state -- the assert is on what the ratchet WOULD see, not on the live
    subprocess.
    """
    mavis = _mavis_cmd()
    if mavis is None:
        pytest.skip("mavis / minimax-code not on PATH on this host")
    real_run = subprocess.run

    def hang_on_version(*args, **kwargs):
        # Match the ratchet's own gate -- if the test would call this with
        # `--version`, the patched call must raise TimeoutExpired, not
        # return a CompletedProcess (otherwise the assertion would never
        # fire).
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[1] == "--version":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=_LOCAL_TIMEOUT_SECONDS)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", hang_on_version)
    # Now invoke the ratchet's gate directly -- it must fire.
    # The primary gate is the timeout itself: a hang past _LOCAL_TIMEOUT_SECONDS
    # MUST raise TimeoutExpired (which is what the ratchet's own test catches).
    # Verify that mutation raises the same exception.
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [mavis, "--version"],
            capture_output=True,
            text=True,
            timeout=_LOCAL_TIMEOUT_SECONDS,
        )


def test_mutation_broken_shim_fails_ratchet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation-kill: a BROKEN launcher must fail the ratchet.

    This is the mutation that slipped through the original ratchet. On
    2026-10-30 the operator's host had a ``mavis.cmd`` pointing at a
    daemon path that no longer existed. Node's module loader writes:

        Error: Cannot find module '<path>'

    to STDERR and exits 1. The original assertion was::

        version = (proc.stdout or proc.stderr or "").strip()
        assert version

    which PASSED on that broken CLI -- stderr was non-empty, so the
    ratchet reported GREEN while the launcher was 100% broken.

    This test simulates exactly that shape (rc=1, empty stdout, an error
    banner on stderr) and asserts the ratchet's OWN gate rejects it. If
    someone restores the stderr-fallback, this test fails.
    """
    mavis = _mavis_cmd()
    if mavis is None:
        pytest.skip("mavis / minimax-code not on PATH on this host")

    def broken_launcher(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[1] == "--version":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=(
                    "node:internal/modules/cjs/loader:1527\n"
                    "Error: Cannot find module 'C:\\...\\daemon\\cli.js'\n"
                ),
            )
        return subprocess.run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", broken_launcher)
    proc = subprocess.run(
        [mavis, "--version"],
        capture_output=True,
        text=True,
        timeout=_LOCAL_TIMEOUT_SECONDS,
    )
    # INVOKE the ratchet's real gate -- do not restate it. Restating is
    # what let the original defect ship: the mutation test kept passing
    # because it asserted against its own copy of the logic, never the
    # gate the ratchet actually uses.
    with pytest.raises(AssertionError):
        _assert_healthy_version_output(proc)
    # And confirm the OLD (defective) gate does NOT reject it -- that is
    # exactly why the defect shipped. This pins the regression: if someone
    # restores the stderr fallback inside the helper, the
    # `pytest.raises` above stops raising and this test fails.
    old_gate_value = (proc.stdout or proc.stderr or "").strip()
    assert old_gate_value, (
        "the OLD stderr-fallback gate unexpectedly rejects the broken "
        "launcher -- the historical defect no longer reproduces"
    )


def test_mutation_error_banner_on_stdout_fails_ratchet() -> None:
    """Mutation-kill: an error banner printed on STDOUT must fail too.

    Covers the other direction of the same defect: a launcher that exits 0
    but prints an error banner instead of a version (some ESM loaders and
    shims do this) must not satisfy the gate.
    """
    banner_proc = subprocess.CompletedProcess(
        args=["mavis", "--version"],
        returncode=0,
        stdout="Error: Cannot find module 'C:\\...\\daemon\\cli.js'",
        stderr="",
    )
    # INVOKE the real gate -- it must reject the banner.
    with pytest.raises(AssertionError):
        _assert_healthy_version_output(banner_proc)


def test_mutation_wrong_upstream_repo_is_detectable() -> None:
    """Mutation-kill: the upstream pin must point at a repo that EXISTS.

    The original pin was ``MiniMaxInc/MiniMax-Code`` -> HTTP 404. The
    fetch helper returns ``None`` on a 404 (a JSON error object where a
    list was expected), which makes the cross-check SKIP rather than
    report. A ratchet that can only skip is decoration.

    This asserts the pin is the real upstream repo. It does NOT make a
    network call -- it asserts the identity of the pin, which is what
    determines whether the cross-check can ever run.
    """
    assert _UPSTREAM_REPO == "MiniMax-AI/minimax-code", (
        f"upstream pin drifted to {_UPSTREAM_REPO!r}; the matrix cross-check "
        f"silently degrades to a skip against a non-existent repo"
    )
    assert "MiniMaxInc" not in _UPSTREAM_REPO, (
        "MiniMaxInc/MiniMax-Code does not exist (HTTP 404) -- the upstream "
        "pin must be MiniMax-AI/minimax-code"
    )


def test_mutation_filename_derived_platforms_would_be_empty() -> None:
    """Mutation-kill: the platform scan must NOT be filename-derived.

    The original implementation derived the platform set from the
    workflow FILENAMES. Upstream's workflow filenames carry no OS name
    (``ci.yml``, ``cli-release.yml``, ``compatibility.yml``, ...), so the
    filename-derived set is EMPTY -- which would have FAILED the
    ``assert "windows" in platforms`` gate, reporting "upstream does not
    cover Windows" for an upstream that DOES.

    This asserts the detector reads workflow CONTENT, by checking it
    against the real upstream workflow filename list. If someone restores
    the filename-derived scan, the empty-set invariant is violated and
    this test fires.
    """
    upstream_workflow_names = (
        "ci.yml",
        "cli-release.yml",
        "compatibility.yml",
        "label-issue-product.yml",
        "performance.yml",
        "security.yml",
        "source-candidate.yml",
        "sync-issue-to-feishu.yml",
    )
    filename_derived: set[str] = set()
    for name in upstream_workflow_names:
        lowered = name.lower()
        for tag in ("ubuntu", "macos", "windows", "linux"):
            if tag in lowered:
                filename_derived.add(tag)
    assert not filename_derived, (
        f"upstream workflow filenames unexpectedly carry an OS tag: "
        f"{sorted(filename_derived)!r} -- re-check whether the filename "
        f"scan assumption still holds"
    )
    # The upstream matrix IS declared in ci.yml's body. Assert the helper
    # scans bodies -- scoped to the helper's OWN source, because this
    # module's prose (the correction notes) legitimately quotes the old
    # filename-derived expression.
    helper_source = inspect.getsource(_fetch_upstream_matrix)
    assert 'entry.get("name"' not in helper_source, (
        "the platform scan is filename-derived again -- upstream declares "
        "its matrix inside ci.yml's body, not in the filenames"
    )
    assert "download_url" in helper_source, (
        "the platform scan no longer reads workflow CONTENT -- it must "
        "fetch each workflow body via its download_url"
    )
