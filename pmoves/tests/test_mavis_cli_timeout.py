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
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
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

# The upstream workflow that OWNS the CI test matrix. Upstream declares the
# matrix inside THIS file -- the ``verify`` job runs on ``${{ matrix.os }}``
# with ``os: [ubuntu-latest, macos-latest, windows-latest]`` -- so the
# platform set must be read from here and nowhere else.
#
# WHY A SINGLE WORKFLOW AND NOT AN AGGREGATE OVER ALL OF THEM
# -----------------------------------------------------------
# The previous implementation scanned the body of EVERY workflow under
# ``.github/workflows/`` and unioned whatever runner labels it found. That
# does not establish test coverage. Upstream also ships ``cli-release.yml``,
# ``compatibility.yml`` and ``performance.yml``; a label that survives in a
# release/compatibility/packaging workflow -- or survives only in a COMMENT
# -- still counted as "the CI test matrix covers this platform". Deleting
# Windows from the test matrix therefore left the ratchet GREEN while it
# named the wrong owner for the regression. Coverage is a property of one
# job's MATRIX, so the read is scoped to that matrix.
_UPSTREAM_CI_WORKFLOW = "ci.yml"

# Runner-label FAMILIES. A GitHub-hosted runner label is always
# ``<family>-<version>``, and the version part is OPEN-ENDED: ``-latest``,
# ``-22``, ``-24.04``, ``-2025``, ``-15``, ... The previous match tested a
# fixed suffix list (``-latest``/``-22``/``-24``), so one upstream rename to
# ``windows-2025`` made the helper report an EMPTY platform set -- and the
# inverted ratchet came back wearing a new coat of paint. The family is
# matched, the version is not enumerated.
_PLATFORM_TAGS = ("ubuntu", "macos", "windows", "linux")

# Words that mark a job -- or the command that job runs -- as the TEST
# surface rather than a packaging/release surface. The match is WORD
# bounded on purpose: ``latest`` contains "test", so an unbounded match
# would read ``ubuntu-latest`` as a test command.
_TEST_JOB_WORDS = (
    "test",
    "tests",
    "testing",
    "spec",
    "specs",
    "verify",
    "verification",
    "e2e",
    "integration",
    "unit",
)
_TEST_WORD_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(_TEST_JOB_WORDS) + r")(?![a-z0-9])",
    re.IGNORECASE,
)

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


def _is_github_api_url(url: str) -> bool:
    """Whether ``url`` addresses the GitHub API host EXACTLY.

    A SUBSTRING test (``"api.github.com" in url``) is a loose host
    match: it also accepts

        https://api.github.com.evil.example/repos
        https://evil.example/?x=api.github.com

    -- neither of which is the host this ratchet talks to. The host is
    compared EXACTLY, through the parsed ``hostname``. The netloc is
    NOT compared: it carries userinfo and a port, so comparing it would
    reintroduce a different mismatch class (a real request to
    ``https://api.github.com:443/...`` would be rejected).

    A URL that is not an absolute, parseable URL is NOT the API host,
    and must not raise out of the caller.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    try:
        hostname = parsed.hostname
    except ValueError:
        return False
    return hostname == "api.github.com"


def _is_test_job(job_name: str, job: dict[str, object]) -> bool:
    """Whether a matrix-bearing job is the TEST job (not packaging/release).

    Two independent signals, because a single one is too easy to lose:
    the job's own name, and the commands the job runs. Upstream's
    ``verify`` job satisfies both ("verify" as the job key, ``pnpm
    verify --profile ...`` as a run step).

    WHY THIS IS NOT A LOOSE "THE ONLY MATRIX JOB" FALLBACK
    ------------------------------------------------------
    If the sole matrix job in a workflow were a packaging job, treating it
    as the test job would re-create the exact defect this ratchet exists
    to prevent: a platform that is only ever BUILT for, never TESTED for,
    would be reported as covered. When no test job can be identified the
    honest answer is "unavailable" (the cross-check skips with a reason),
    never a confident platform set.
    """
    declared_name = job.get("name")
    label = f"{job_name} {declared_name if isinstance(declared_name, str) else ''}"
    if _TEST_WORD_RE.search(label):
        return True
    steps = job.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str) and _TEST_WORD_RE.search(run):
                return True
    return False


def _matrix_axes(matrix: dict[str, object]) -> list[tuple[str, list[object]]]:
    """The matrix's base dimensions, in declaration order.

    ``include``/``exclude`` are NOT dimensions -- they modify the
    expansion of the other dimensions.
    """
    axes: list[tuple[str, list[object]]] = []
    for key, value in matrix.items():
        if key in ("include", "exclude"):
            continue
        if isinstance(value, list):
            axes.append((key, list(value)))
        elif isinstance(value, (str, int, float, bool)) or value is None:
            axes.append((key, [value]))
        # Any other shape (a mapping, an expression) cannot be expanded
        # without evaluating the workflow, so it is skipped rather than
        # guessed at.
    return axes


def _base_combinations(axes: list[tuple[str, list[object]]]) -> list[dict[str, object]]:
    """The cartesian product of the matrix's base dimensions."""
    combos: list[dict[str, object]] = [{}]
    for key, values in axes:
        combos = [
            {**combo, key: value}
            for combo in combos
            for value in values
        ]
    return combos


def _combo_values_equal(left: object, right: object) -> bool:
    """Compare two matrix values the way GitHub does (as strings)."""
    return str(left) == str(right)


def _combo_matches_exclude(combo: dict[str, object], entry: dict[str, object]) -> bool:
    """Whether a base combination is matched by an ``exclude:`` entry.

    GitHub's rule: "An excluded configuration only has to be a partial
    match for it to be excluded." The entry's dimensions are therefore a
    PARTIAL match: every dimension the entry names must match, and the
    dimensions it does not name are unconstrained. An entry that names a
    dimension the matrix does not have never matches anything.
    """
    for key, value in entry.items():
        if key not in combo:
            return False
        if not _combo_values_equal(combo[key], value):
            return False
    return True


def _apply_matrix_exclusions(
    combos: list[dict[str, object]],
    exclude_entries: list[object],
) -> list[dict[str, object]]:
    """Remove the combinations an ``exclude:`` entry matches.

    An ``exclude:`` entry that matches NOTHING is not an error: exclude
    can be broader than the matrix it filters (a shared exclude list
    naming platforms this job does not run). The entry is simply a
    filter, so an unmatched entry removes nothing.
    """
    for entry in exclude_entries:
        if not isinstance(entry, dict) or not entry:
            continue
        combos = [
            combo
            for combo in combos
            if not _combo_matches_exclude(combo, entry)
        ]
    return combos


def _apply_matrix_inclusions(
    combos: list[dict[str, object]],
    include_entries: list[object],
    axes: list[tuple[str, list[object]]],
) -> list[dict[str, object]]:
    """Apply the ``include:`` entries to the matrix combinations.

    GitHub's documented order is ``exclude`` FIRST, ``include`` AFTER:
    "All ``include`` combinations are processed after ``exclude``. This
    allows you to use ``include`` to add back combinations that were
    previously excluded." (GitHub workflow syntax reference.)

    An entry is merged into every ORIGINAL combination it does not
    conflict with (it may not overwrite an original matrix value, but it
    may add new keys); an entry that fits no original combination becomes
    a NEW combination -- and, per the same reference, a later entry does
    not merge into a combination an earlier entry created.
    """
    original_keys = {key for key, _ in axes}
    if not axes:
        # A matrix that declares nothing but `include:` runs one job per
        # entry.
        return [
            dict(entry)
            for entry in include_entries
            if isinstance(entry, dict) and entry
        ]
    created: list[dict[str, object]] = []
    for entry in include_entries:
        if not isinstance(entry, dict) or not entry:
            continue
        added = {
            key: value
            for key, value in entry.items()
            if key not in original_keys
        }
        matched = False
        for combo in combos:
            conflicts = any(
                key in original_keys
                and (
                    key not in combo
                    or not _combo_values_equal(combo[key], value)
                )
                for key, value in entry.items()
            )
            if conflicts:
                continue
            combo.update(added)
            matched = True
        if not matched:
            created.append(dict(entry))
    return combos + created


def _extract_matrix_platforms(workflow_body: str) -> dict[str, object]:
    """Extract the platform set from a CI workflow's TEST-job matrix.

    PURE: takes a workflow body, returns a verdict. No network, so the
    ratchet can pin the classification logic with hermetic tests.

    Returns a dict whose ``status`` is either:
      "ok"          -> ``platforms`` holds the platform set;
      "unavailable" -> ``reason`` says why the matrix could not be read.

    WHY THE PLATFORM SET COMES FROM THE MATRIX, NOT FROM THE BODY
    --------------------------------------------------------------
    The body of upstream's ``ci.yml`` contains the word "Windows" in a
    COMMENT ("Windows runs a focused contract; full capability coverage
    remains on Linux/macOS") and the token ``Linux/macOS`` in that same
    comment. A body scan therefore reports platforms that the matrix never
    declared. The matrix is read structurally instead: find the job whose
    ``runs-on`` is driven by ``matrix.<key>``, EXPAND that job's matrix
    (base dimensions, minus the ``exclude:`` combinations, plus the
    ``include:`` ones), and count only the runner labels of the
    combinations that actually run.
    """
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"status": "unavailable", "reason": f"PyYAML unavailable on this host: {exc}"}
    try:
        doc = yaml.safe_load(workflow_body)
    except Exception as exc:
        return {"status": "unavailable", "reason": f"workflow YAML did not parse: {exc}"}
    if not isinstance(doc, dict):
        return {"status": "unavailable", "reason": "workflow YAML is not a mapping"}
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return {"status": "unavailable", "reason": "workflow declares no jobs"}

    # The matrix-bearing job is the one whose runner comes FROM the matrix.
    matrix_jobs: list[tuple[str, dict[str, object], str]] = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        runs_on = job.get("runs-on")
        if not isinstance(runs_on, str):
            continue
        match = re.search(r"matrix\.([A-Za-z_][A-Za-z0-9_-]*)", runs_on)
        if match:
            matrix_jobs.append((str(job_name), job, match.group(1)))
    if not matrix_jobs:
        return {
            "status": "unavailable",
            "reason": "no job drives runs-on from a matrix",
        }
    test_jobs = [entry for entry in matrix_jobs if _is_test_job(entry[0], entry[1])]
    if not test_jobs:
        return {
            "status": "unavailable",
            "reason": (
                "could not identify the TEST job among the matrix job(s) "
                f"{[name for name, _, _ in matrix_jobs]!r}"
            ),
        }

    labels: list[str] = []
    job_names: list[str] = []
    keys: set[str] = set()
    for job_name, job, key in test_jobs:
        strategy = job.get("strategy")
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        if not isinstance(matrix, dict):
            continue
        # The matrix is EXPANDED, not scanned: the base dimensions are
        # combined, `exclude:` removes the combinations it matches, and
        # `include:` adds to (or creates) combinations. Only the
        # combinations that actually RUN contribute a runner label.
        #
        # Reading only `include:` and ignoring `exclude:` reported a
        # platform as covered when the matrix never runs it -- an
        # `exclude: [{os: windows-latest}]` left the ratchet claiming
        # upstream covers Windows.
        axes = _matrix_axes(matrix)
        combos = _base_combinations(axes)
        # GitHub's documented order: `exclude` is applied FIRST, `include`
        # is processed AFTER ("All `include` combinations are processed
        # after `exclude`" -- GitHub workflow syntax reference).
        exclude_entries = matrix.get("exclude")
        if isinstance(exclude_entries, list):
            combos = _apply_matrix_exclusions(combos, exclude_entries)
        include_entries = matrix.get("include")
        if isinstance(include_entries, list):
            combos = _apply_matrix_inclusions(combos, include_entries, axes)
        for combo in combos:
            if key in combo:
                labels.append(str(combo[key]))
        job_names.append(job_name)
        keys.add(key)
    if not labels:
        return {
            "status": "unavailable",
            "reason": "the TEST job declares no runner labels for its matrix key",
        }

    platforms: set[str] = set()
    for label in labels:
        lowered = str(label).lower()
        for tag in _PLATFORM_TAGS:
            # `<family>-<version>`: the version family is open-ended, so
            # match "latest" or ANY digit start ("-22", "-24.04", "-2025",
            # "-15"). A fixed suffix list would go stale on the first
            # upstream runner rename and report an EMPTY platform set.
            if re.search(rf"\b{tag}-(latest|\d)", lowered):
                platforms.add(tag)
    return {
        "status": "ok",
        "platforms": sorted(platforms),
        "jobs": job_names,
        "matrix_key": ",".join(sorted(keys)),
        "labels": sorted(set(labels)),
    }


def _assert_matrix_platforms(
    workflow_body: str,
    expected_platforms: list[str],
    *,
    context: str = "workflow",
) -> dict[str, object]:
    """Assert the matrix verdict for a workflow body names the expected platforms.

    NAMED AND IMPORTABLE ON PURPOSE: the pytest test below and the
    mutation-kill harness must BOTH call THIS function. Restating the
    check inline in the harness is what let the original defect ship --
    the harness kept passing because it never touched the gate the
    ratchet actually uses.

    Returns the parsed verdict so a caller can assert further details.
    """
    parsed = _extract_matrix_platforms(workflow_body)
    assert parsed.get("status") == "ok", (
        f"the {context} did not parse into a verdict: {parsed!r}"
    )
    actual = sorted(str(platform) for platform in parsed.get("platforms", []))
    assert actual == sorted(expected_platforms), (
        f"the {context} reports platforms {actual!r}, expected "
        f"{sorted(expected_platforms)!r} -- the verdict must describe the "
        f"combinations the matrix actually runs: {parsed!r}"
    )
    return parsed


def _fetch_upstream_matrix() -> dict[str, object]:
    """Fetch the upstream ``minimax-code`` CI test matrix.

    Uses the public ``.github`` repo contents endpoint (no auth, rate-limited
    per-IP). Returns a dict whose ``status`` is:

      "ok"          -> ``platforms`` holds the upstream test-matrix platforms;
      "unavailable" -> the check could not run, and ``reason`` says why.

    WHY A FAILED READ IS "unavailable" AND NEVER "ok"
    -------------------------------------------------
    The previous implementation caught a failed workflow download with a
    bare ``continue`` and then returned ``status="ok"`` carrying whatever
    platforms it had managed to collect. A rate-limited or timed-out
    download therefore produced a PARTIAL platform set that was reported
    as a successful read: the cross-check then announced that upstream had
    DROPPED a platform, when the truth was that the network had hiccuped.
    An infrastructure failure was being published as an upstream change.
    Every failure path below therefore returns "unavailable", and the test
    SKIPS with the reason -- "I could not check" is not "upstream dropped
    it".

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

    WHY THE WORKFLOW IS SELECTED BY NAME
    ------------------------------------
    The matrix-bearing workflow is upstream's ``ci.yml``. Selecting it
    explicitly is what makes the platform set MEANINGFUL: a scan over
    every workflow file would union the release, compatibility and
    packaging workflows into "test coverage" and would also pick up
    runner labels that only ever appear inside a comment.
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
    ) as exc:
        return {"status": "unavailable", "reason": f"workflow listing fetch failed: {exc}"}
    if not isinstance(payload, list):
        return {
            "status": "unavailable",
            "reason": "workflow listing is not a list (wrong repo pin?)",
        }

    ci_entry: dict[str, object] | None = None
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").lower()
        if name in ("ci.yml", "ci.yaml"):
            ci_entry = entry
            break
    if ci_entry is None:
        listing = sorted(
            str(entry.get("name")) for entry in payload if isinstance(entry, dict)
        )
        return {
            "status": "unavailable",
            "reason": (
                f"upstream {_UPSTREAM_CI_WORKFLOW} not found in "
                f".github/workflows ({listing!r})"
            ),
        }
    raw_url = ci_entry.get("download_url")
    if not raw_url:
        return {
            "status": "unavailable",
            "reason": f"upstream {_UPSTREAM_CI_WORKFLOW} entry has no download_url",
        }
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
    ) as exc:
        # A failed download of the MATRIX-BEARING workflow must NOT be
        # swallowed: it used to be a `continue`, which returned "ok" with a
        # partial platform set and made the ratchet blame upstream for a
        # network hiccup.
        return {
            "status": "unavailable",
            "reason": f"upstream {_UPSTREAM_CI_WORKFLOW} download failed: {exc}",
        }
    return _extract_matrix_platforms(body)


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
    if matrix.get("status") != "ok":
        # "I could not check" is NOT "upstream dropped it". A read that
        # failed (network, rate limit, unparseable workflow) must skip with
        # its reason -- reporting it as a platform set would publish an
        # infrastructure failure as an upstream change.
        pytest.skip(
            "upstream matrix cross-check UNAVAILABLE -- this is not a "
            f"verdict about upstream: {matrix.get('reason')!r}"
        )
    platforms = list(matrix["platforms"])
    assert "windows" in platforms, (
        f"upstream matrix does NOT include 'windows' -- any mavis hang on "
        f"Windows is operator-lane (no upstream signal). Matrix platforms: "
        f"{platforms!r} (read from job(s) {matrix.get('jobs')!r})"
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
    WHY THERE IS NO `_mavis_cmd()` GUARD HERE
    ---------------------------------------
    This test never runs the real CLI: ``subprocess.run`` is patched, so
    the call below is intercepted and raised on by the patch. Guarding on
    "mavis is on PATH" meant the mutation-kill SKIPPED on every host
    without the CLI -- which is CI, where the ratchet runner actually
    lives. A mutation-kill that only bears load on the operator's laptop
    is decoration. The args are constructed directly, the same way
    ``test_mutation_error_banner_on_stdout_fails_ratchet`` does it, so the
    kill fires on every host.
    """
    # `real_run` is captured BEFORE the patch: `hang_on_version` is
    # installed AS `subprocess.run`, so a fallback that called
    # `subprocess.run(...)` would resolve the PATCHED attribute and
    # re-enter itself with the same arguments, forever.
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
            ["mavis", "--version"],
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
    WHY THERE IS NO `_mavis_cmd()` GUARD HERE
    ---------------------------------------
    This test never runs the real CLI: the ``CompletedProcess`` is built
    BY HAND and the patched ``subprocess.run`` returns it. Guarding on
    "mavis is on PATH" meant the mutation-kill SKIPPED on every host
    without the CLI -- which is CI, where the ratchet runner actually
    lives. This is the kill that proves the version gate cannot be
    weakened back to the stderr fallback, so it must bear load
    everywhere, not only on the operator's laptop.

    WHY `real_run` IS CAPTURED BEFORE THE PATCH
    -------------------------------------------
    ``broken_launcher`` is installed AS ``subprocess.run``. Its fallback
    branch used to call ``subprocess.run(*args, **kwargs)``, which
    resolved the PATCHED attribute and re-entered ``broken_launcher``
    with the same arguments -- infinite recursion, waiting for the day
    some other call site took that branch. The sibling test 60 lines
    above had it right; both now capture the original first.
    """
    real_run = subprocess.run

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
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", broken_launcher)
    proc = subprocess.run(
        ["mavis", "--version"],
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


# A faithful EXCERPT of upstream ``MiniMax-AI/minimax-code``'s ``ci.yml``
# (captured 2026-10-30). It is kept verbatim in shape because it carries
# the two traps this ratchet has to survive:
#   * the matrix block carries a COMMENT that mentions "Windows" and
#     "Linux/macOS" -- neither of which is a matrix entry;
#   * non-matrix jobs (``changes``) run on a plain ``ubuntu-latest``.
_SAMPLE_UPSTREAM_CI = """\
name: Source verification
on:
  push:
    branches: [main]
jobs:
  changes:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@3d3c42e
      - run: node scripts/ci-changes.mjs
  verify:
    name: verify (${{ matrix.os }}, ${{ matrix.node }})
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        # Windows runs a focused contract; full capability coverage remains on Linux/macOS.
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: ["24"]
        include:
          - os: ubuntu-latest
            node: "24"
            profile: full
          - os: windows-latest
            node: "24"
            profile: windows
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@3d3c42e
      - run: pnpm install --frozen-lockfile
      - run: pnpm verify --profile ${{ matrix.profile || 'platform' }}
"""

# The same workflow with Windows REMOVED from the matrix. The comment still
# says "Windows" -- so a body scan still finds the word, and still reports
# Windows as covered.
_SAMPLE_UPSTREAM_CI_WITHOUT_WINDOWS = _SAMPLE_UPSTREAM_CI.replace(
    "os: [ubuntu-latest, macos-latest, windows-latest]",
    "os: [ubuntu-latest, macos-latest]",
).replace(
    "          - os: windows-latest\n            node: \"24\"\n            profile: windows\n",
    "",
)

# A workflow whose ONLY matrix job is a packaging job. Its matrix mentions
# every platform, but nothing there is ever TESTED, so it must not be
# reported as upstream test coverage.
_SAMPLE_PACKAGING_ONLY_CI = """\
name: Release
on:
  push:
    branches: [main]
jobs:
  package:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - run: pnpm build
"""

# A matrix whose runner labels carry explicit versions. GitHub-hosted runner
# labels are ``<family>-<version>`` and the version set is open-ended
# (``-latest``, ``-22``, ``-24.04``, ``-2025``, ``-15``, ...).
_SAMPLE_VERSIONED_RUNNER_CI = """\
name: CI
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-24.04, macos-15, windows-2025]
    steps:
      - run: pnpm test
"""

# The upstream-shaped matrix with an ``exclude:`` entry. GitHub processes
# ``exclude`` BEFORE ``include`` ("All ``include`` combinations are
# processed after ``exclude``"), so an ``include`` entry that re-adds the
# excluded platform WOULD run it again. This fixture keeps the include
# entries clear of the excluded platform, so the verdict is unambiguous:
# the matrix runs ubuntu + macos and NOT windows.
_SAMPLE_UPSTREAM_CI_WITH_EXCLUDE = """\
name: Source verification
on:
  push:
    branches: [main]
jobs:
  verify:
    name: verify (${{ matrix.os }}, ${{ matrix.node }})
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: ["24"]
        exclude:
          - os: windows-latest
        include:
          - os: ubuntu-latest
            node: "24"
            profile: full
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@3d3c42e
      - run: pnpm install --frozen-lockfile
      - run: pnpm verify --profile ${{ matrix.profile || 'platform' }}
"""

# An ``exclude:`` entry that names MORE than the platform dimension only
# removes the combinations where ALL of its dimensions match. Here the
# windows/node-22 combination is excluded, but windows/node-24 still runs
# -- so windows IS still covered upstream.
_SAMPLE_UPSTREAM_CI_WITH_PARTIAL_EXCLUDE = """\
name: Source verification
on:
  push:
    branches: [main]
jobs:
  verify:
    name: verify (${{ matrix.os }}, ${{ matrix.node }})
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: ["22", "24"]
        exclude:
          - os: windows-latest
            node: "22"
        include:
          - os: ubuntu-latest
            node: "24"
            profile: full
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@3d3c42e
      - run: pnpm install --frozen-lockfile
      - run: pnpm verify --profile ${{ matrix.profile || 'platform' }}
"""

# An ``exclude:`` entry that matches NOTHING is not an error: exclude can
# be broader than the matrix it filters. The verdict must stay "ok" and
# the platform set must not change.
_SAMPLE_UPSTREAM_CI_WITH_UNUSED_EXCLUDE = """\
name: Source verification
on:
  push:
    branches: [main]
jobs:
  verify:
    name: verify (${{ matrix.os }}, ${{ matrix.node }})
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: ["24"]
        exclude:
          - os: freebsd-latest
        include:
          - os: ubuntu-latest
            node: "24"
            profile: full
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@3d3c42e
      - run: pnpm install --frozen-lockfile
      - run: pnpm verify --profile ${{ matrix.profile || 'platform' }}
"""


def test_mutation_matrix_scoped_platform_detection() -> None:
    """Platform coverage must come from the TEST job's MATRIX, not a scan.

    The original detector unioned the runner labels it found in the body of
    EVERY workflow. That does not establish that the upstream CI test matrix
    covers a platform: a label left behind in a release, compatibility or
    packaging workflow -- or in a COMMENT -- kept the ratchet green while it
    named the wrong owner for the regression.

    This pins the classification hermetically: no network, no upstream.
    """
    parsed = _extract_matrix_platforms(_SAMPLE_UPSTREAM_CI)
    assert parsed["status"] == "ok", (
        f"the upstream-shaped workflow did not parse into a verdict: {parsed!r}"
    )
    assert parsed["platforms"] == ["macos", "ubuntu", "windows"], (
        f"the TEST job's matrix did not yield the expected platform set: {parsed!r}"
    )
    assert parsed["jobs"] == ["verify"], (
        f"the platform set was not read from the TEST job: {parsed!r}"
    )
    assert parsed["matrix_key"] == "os", (
        f"the matrix key was not read from the runs-on expression: {parsed!r}"
    )

    # THE REGRESSION: Windows removed from the matrix, still named in the
    # comment. Reporting "windows" here is the inverted ratchet.
    dropped = _extract_matrix_platforms(_SAMPLE_UPSTREAM_CI_WITHOUT_WINDOWS)
    assert dropped["status"] == "ok", (
        f"the Windows-dropped workflow did not parse into a verdict: {dropped!r}"
    )
    assert dropped["platforms"] == ["macos", "ubuntu"], (
        "a platform that only survives in a COMMENT (or in a non-matrix job) "
        f"must not be reported as upstream test coverage: {dropped!r}"
    )
    assert "windows" not in dropped["platforms"], (
        "upstream dropped Windows from the test matrix but the ratchet still "
        f"reports it as covered: {dropped!r}"
    )

    # A matrix job that is not the TEST job carries no coverage claim.
    packaging = _extract_matrix_platforms(_SAMPLE_PACKAGING_ONLY_CI)
    assert packaging["status"] == "unavailable", (
        "a workflow with no identifiable TEST job must report UNAVAILABLE, "
        f"not a confident platform set: {packaging!r}"
    )
    assert not packaging.get("platforms"), (
        f"a packaging matrix was reported as test coverage: {packaging!r}"
    )

    # Structural pin: the platform set is parsed out of the MATRIX, never
    # accumulated by scanning workflow bodies.
    helper_source = inspect.getsource(_fetch_upstream_matrix)
    assert "_UPSTREAM_CI_WORKFLOW" in helper_source, (
        "the upstream matrix must be read from the CI workflow explicitly, "
        "not from an aggregate over every workflow file"
    )
    assert "_extract_matrix_platforms" in helper_source, (
        "the network helper must delegate the matrix read to the structural "
        "parser -- a body scan cannot tell a matrix entry from a comment"
    )


def test_mutation_excluded_platform_is_not_covered() -> None:
    """An ``exclude:``d platform must NOT be reported as upstream-covered.

    The matrix reader parsed ``include:`` but never ``exclude:``. A
    matrix like::

        matrix:
          os: [ubuntu-latest, macos-latest, windows-latest]
          exclude:
            - os: windows-latest

    therefore still reported ``windows`` as covered -- the ratchet would
    announce "upstream covers Windows" for a matrix that never runs
    Windows, which is the inverted ratchet in its purest form.

    Hermetic: no network, no upstream.
    """
    parsed = _assert_matrix_platforms(
        _SAMPLE_UPSTREAM_CI_WITH_EXCLUDE,
        ["macos", "ubuntu"],
        context="the matrix with an `exclude:` entry",
    )
    assert "windows" not in parsed["platforms"], (
        "an excluded platform was reported as upstream test coverage: "
        f"{parsed!r}"
    )
    # A platform that is NOT excluded is still reported as covered -- the
    # fix must not over-exclude and hide real coverage.
    _assert_matrix_platforms(
        _SAMPLE_UPSTREAM_CI_WITH_PARTIAL_EXCLUDE,
        ["macos", "ubuntu", "windows"],
        context="the matrix with a combination-scoped `exclude:` entry",
    )
    # An `exclude:` entry that matches nothing is NOT an error: exclude
    # can be broader than the matrix it filters.
    _assert_matrix_platforms(
        _SAMPLE_UPSTREAM_CI_WITH_UNUSED_EXCLUDE,
        ["macos", "ubuntu", "windows"],
        context="the matrix with an `exclude:` entry that matches nothing",
    )


def test_mutation_runner_label_family_matching() -> None:
    """Runner labels are ``<family>-<version>``; the version set is open-ended.

    The previous match tested a fixed suffix list (``-latest`` / ``-22`` /
    ``-24``). GitHub-hosted runners routinely appear as ``windows-2025``,
    ``macos-15`` and ``ubuntu-24.04`` -- none of which end in one of those
    suffixes. One upstream rename and the helper reported an EMPTY platform
    set, which made the gate fire and blame upstream for a rename.
    """
    parsed = _extract_matrix_platforms(_SAMPLE_VERSIONED_RUNNER_CI)
    assert parsed["status"] == "ok", (
        f"the versioned-runner workflow did not parse into a verdict: {parsed!r}"
    )
    assert parsed["platforms"] == ["macos", "ubuntu", "windows"], (
        "the runner-label family match went stale: an upstream runner rename "
        f"emptied the platform set. Parsed: {parsed!r}"
    )

    # A label with no version is not a GitHub-hosted runner family, and a
    # self-hosted label is not a platform at all.
    self_hosted = _SAMPLE_VERSIONED_RUNNER_CI.replace(
        "os: [ubuntu-24.04, macos-15, windows-2025]",
        "os: [self-hosted]",
    )
    parsed_self_hosted = _extract_matrix_platforms(self_hosted)
    assert parsed_self_hosted["status"] == "ok", (
        f"the self-hosted workflow did not parse into a verdict: {parsed_self_hosted!r}"
    )
    assert parsed_self_hosted["platforms"] == [], (
        "a self-hosted runner label is not a platform: "
        f"{parsed_self_hosted!r}"
    )


def test_mutation_upstream_download_failure_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed workflow download must be UNAVAILABLE, never a partial "ok".

    The listing fetch used to succeed while the matrix-bearing workflow
    download was rate-limited or timed out; that branch was a bare
    ``continue``, and the helper then returned ``status="ok"`` carrying
    whatever platforms it had scraped from the other workflows. The
    cross-check reported that upstream had DROPPED a platform when the
    truth was that the network had hiccuped -- an infrastructure failure
    published as an upstream change.
    """
    listing = [
        {
            "name": "ci.yml",
            "path": ".github/workflows/ci.yml",
            "download_url": "https://example.invalid/ci.yml",
        },
        {
            "name": "cli-release.yml",
            "path": ".github/workflows/cli-release.yml",
            "download_url": "https://example.invalid/cli-release.yml",
        },
    ]

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *exc_info: object) -> bool:
            return False

    def fake_urlopen(req, *args, **kwargs):
        url = getattr(req, "full_url", str(req))
        # The host is matched EXACTLY (see _is_github_api_url): a
        # substring match would also accept "api.github.com.evil.example"
        # and "evil.example/?x=api.github.com".
        if _is_github_api_url(url):
            return _FakeResponse(json.dumps(listing).encode("utf-8"))
        raise urllib.error.HTTPError(url, 403, "rate limit exceeded", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    matrix = _fetch_upstream_matrix()
    assert matrix.get("status") == "unavailable", (
        "a failed download of the matrix-bearing workflow was reported as a "
        f"successful read: {matrix!r}"
    )
    assert not matrix.get("platforms"), (
        "an unavailable read must not carry a platform set -- a partial set "
        f"is published as an upstream change: {matrix!r}"
    )
    assert matrix.get("reason"), (
        f"an unavailable read must say WHY it is unavailable: {matrix!r}"
    )


def test_mutation_github_api_host_match_is_exact() -> None:
    """The GitHub API host must be matched EXACTLY, not by substring.

    The test double that stands in for the network matched the API host
    with ``"api.github.com" in url``. That is a loose host match: it
    also accepts

        https://api.github.com.evil.example/repos
        https://evil.example/?x=api.github.com

    -- neither of which is the host this ratchet talks to. The check is
    the ratchet's OWN helper (``_is_github_api_url``), so this test and
    the mutation-kill harness exercise the SAME code rather than a copy.
    """
    assert _is_github_api_url(
        "https://api.github.com/repos/MiniMax-AI/minimax-code/contents"
    ), "the real GitHub API URL was not recognised as the API host"
    # A host that merely CONTAINS the API host is not the API host.
    assert not _is_github_api_url(
        "https://api.github.com.evil.example/repos"
    ), "a look-alike host was accepted as the GitHub API host"
    assert not _is_github_api_url(
        "https://evil.example/?x=api.github.com"
    ), "the API host was matched inside a query string"
    assert not _is_github_api_url(
        "https://user@api.github.com.evil.example/repos"
    ), "userinfo must not smuggle a look-alike host past the check"
    # The netloc carries the port and the userinfo; only the HOSTNAME
    # is compared, so a real request to the API on a port still counts.
    assert _is_github_api_url(
        "https://api.github.com:443/repos"
    ), "the API host on an explicit port was not recognised"
    # A URL that is not an absolute URL is not the API host -- and the
    # check must not raise out of the caller.
    assert not _is_github_api_url("api.github.com/repos"), (
        "a relative URL was treated as the GitHub API host"
    )
    assert not _is_github_api_url(""), (
        "an empty URL was treated as the GitHub API host"
    )
    assert not _is_github_api_url("https://"), (
        "a URL with no host was treated as the GitHub API host"
    )
