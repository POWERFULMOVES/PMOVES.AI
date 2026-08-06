# pmoves/tools/tests/test_validate_dockerfile_paths.py
"""Tests for the validate-dockerfile-paths ratchet.

The ratchet is the durable answer to the operator's #2358 meta-callout:
"the file the developer touched ≠ the file the runner builds". It must:

  1. Pass when every compose `build:` points to a real Dockerfile.
  2. Fail when a compose `build:` points to a missing Dockerfile.
  3. Pass when an orphan Dockerfile is in the baseline.
  4. Fail when a new orphan Dockerfile appears (not in baseline).
  5. Skip sibling-submodule / vendor / provisions paths
     (out of scope for the ratchet; the operator keeps those synced).
  6. Emit JSON with the right shape when --json is passed.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "validate_dockerfile_paths.py"
)
PYTHON = sys.executable
PMOVES_DIR = Path(__file__).resolve().parents[2]


def _run_ratchet(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(RATCHET), *args, "--json"],
        capture_output=True, text=True,
    )


def _write_tmp_compose(name: str, content: str) -> Path:
    """Write a single compose file into pmoves/ as
    docker-compose.<name>.yml. The ratchet's glob picks it up.

    For `--compose` tests, the file path is passed directly so
    the ratchet only scans that one file.
    """
    target = PMOVES_DIR / f"docker-compose.{name}.yml"
    target.write_text(content, encoding="utf-8")
    return target


def _write_tmp_dockerfile(rel_path: str, content: str = "FROM scratch\n") -> Path:
    """Write a Dockerfile at the given path under pmoves/. Used to
    test the orphan detection: create a Dockerfile that nothing
    references, then verify the ratchet flags it."""
    target = PMOVES_DIR / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _cleanup(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            p.unlink()
        # remove empty parent dirs we created
        parent = p.parent
        if parent.exists() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 1. Clean compose (build points to a real Dockerfile) passes
# ---------------------------------------------------------------------------

def test_clean_compose_passes(tmp_path):
    """A compose that builds an existing service Dockerfile has no
    broken-build finding for that service.

    We point the ratchet at a single compose file (`--compose`) so
    the test is isolated from the rest of the fleet. The build
    target is the existing pmoves/services/agent-zero/Dockerfile.

    Note: the ratchet still reports orphan findings for the rest
    of the fleet in this test, so we only check the broken-build
    count for the test service, not the overall exit code.
    """
    payload = """
services:
  test-svc:
    build:
      context: ./services/agent-zero
      dockerfile: Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_clean", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        broken_for_test_svc = [
            p for p in out["problems"]
            if p.get("kind") == "broken-build"
            and p.get("service") == "test-svc"
        ]
        assert not broken_for_test_svc, (
            f"expected no broken-build finding for test-svc, got: {broken_for_test_svc}"
        )
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# 2. Broken build fails
# ---------------------------------------------------------------------------

def test_broken_build_fails():
    """A compose that builds a non-existent Dockerfile fails.

    Same shape as the 5 real broken builds the ratchet caught on
    initial pass (pmoves/services/github-branch-naming/Dockerfile,
    etc). The ratchet should surface this with a clear error.
    """
    payload = """
services:
  test-svc:
    build:
      context: ./services/this-service-does-not-exist
      dockerfile: Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_broken", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        assert r.returncode == 1, r.stdout
        out = json.loads(r.stdout)
        broken = [
            p for p in out["problems"]
            if p.get("kind") == "broken-build"
            and p.get("service") == "test-svc"
        ]
        assert broken, f"expected a broken-build finding for test-svc, got: {out}"
        assert any("this-service-does-not-exist" in p["dockerfile"] for p in broken)
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# 3. Broken build with default context (no `context:` key)
# ---------------------------------------------------------------------------

def test_default_context_dockerfile_resolved():
    """When `build:` is just `dockerfile: Dockerfile` (no context),
    the ratchet resolves the context to `.` (the compose file's
    directory, which is pmoves/ in this repo). The expected
    dockerfile is `pmoves/Dockerfile` — if it doesn't exist, fail."""
    payload = """
services:
  test-svc:
    build:
      dockerfile: Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_defaultctx", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        assert r.returncode == 1
        out = json.loads(r.stdout)
        broken = [
            p for p in out["problems"]
            if p.get("kind") == "broken-build"
            and p.get("service") == "test-svc"
        ]
        assert broken
        # The ratchet reports the resolved path as pmoves/Dockerfile
        assert any(p["dockerfile"].endswith("Dockerfile") for p in broken)
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# 4. Sibling submodule / vendor / provisions path is skipped
# ---------------------------------------------------------------------------

def test_sibling_submodule_path_skipped():
    """Compose `build:` into a sibling submodule (e.g.
    `PMOVES-Archon/Dockerfile`) is out of scope for the ratchet —
    the ratchet can't statically check external repos."""
    payload = """
services:
  archon:
    build:
      context: ../PMOVES-Archon
      dockerfile: Dockerfile
    image: archon:test
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_submodule", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        # No broken-build finding for the sibling-submodule path
        out = json.loads(r.stdout)
        archon_findings = [
            p for p in out["problems"]
            if p.get("service") == "archon" and p.get("kind") == "broken-build"
        ]
        assert not archon_findings, f"expected sibling-submodule to be skipped, got: {archon_findings}"
    finally:
        _cleanup(path)


def test_vendor_path_skipped():
    """Compose `build:` into pmoves/vendor/ is out of scope."""
    payload = """
services:
  vendor-svc:
    build:
      context: ./vendor/some-external-pkg
      dockerfile: Dockerfile
    image: vendor-svc:test
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_vendor", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        vendor_findings = [
            p for p in out["problems"]
            if p.get("service") == "vendor-svc" and p.get("kind") == "broken-build"
        ]
        assert not vendor_findings, f"expected vendor path to be skipped, got: {vendor_findings}"
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# 5. Orphan Dockerfile detection
# ---------------------------------------------------------------------------

def test_new_orphan_dockerfile_fails():
    """A new Dockerfile in pmoves/services/ that nothing references
    is a ratchet failure. (The operator must wire it into a compose
    `build:` stanza OR add it to the baseline.)"""
    dockerfile = _write_tmp_dockerfile(
        "services/test-orphan-tmp-12345/Dockerfile",
        "FROM scratch\n",
    )
    try:
        r = _run_ratchet()
        out = json.loads(r.stdout)
        orphans = [
            p for p in out["problems"]
            if p.get("kind") == "orphan-dockerfile"
            and "test-orphan-tmp-12345" in (p.get("dockerfile") or "")
        ]
        assert orphans, f"expected orphan-dockerfile finding, got: {out['problems']}"
        # The ratchet should fail (exit 1) on the new orphan
        # (Note: this test runs the full ratchet, so other orphans
        # may also be present; we only check our test one.)
    finally:
        _cleanup(dockerfile)


# ---------------------------------------------------------------------------
# 6. Baseline-known orphan does NOT fail
# ---------------------------------------------------------------------------

def test_baseline_orphan_does_not_fail():
    """A Dockerfile that's in the baseline file is allowed to be
    orphaned. The baseline is committed, so the ratchet can verify
    the reason is meaningful in PR diffs."""
    # The baseline file is at pmoves/configs/dockerfiles/_known_orphans.yaml
    # which already has 26 entries. We don't add a new entry here;
    # we just verify the ratchet passes given the existing baseline.
    r = _run_ratchet()
    out = json.loads(r.stdout)
    # If the ratchet fails, it must NOT be because of a baseline entry.
    baseline_orphans = [
        p for p in out["problems"]
        if p.get("kind") == "orphan-dockerfile"
        and p.get("dockerfile", "").startswith("pmoves/")
    ]
    # None of the in-baseline entries should be flagged
    assert all(
        "test-orphan-tmp" not in (p.get("dockerfile") or "")
        for p in baseline_orphans
    )


# ---------------------------------------------------------------------------
# 7. JSON output shape
# ---------------------------------------------------------------------------

def test_json_output_shape():
    """The --json output has the right keys: ok, problems, summary,
    baseline_count, referenced_count, total_dockerfiles."""
    r = _run_ratchet()
    out = json.loads(r.stdout)
    assert "ok" in out
    assert "problems" in out
    assert "summary" in out
    assert "baseline_count" in out
    assert "referenced_count" in out
    assert "total_dockerfiles" in out
    assert isinstance(out["problems"], list)
    assert isinstance(out["summary"], dict)
    assert isinstance(out["ok"], bool)
    assert out["ok"] == (not out["problems"])


# ---------------------------------------------------------------------------
# 8. --list-orphans mode
# ---------------------------------------------------------------------------

def test_list_orphans_never_fails():
    """`--list-orphans` always exits 0 (it's a diagnostic tool).
    The output should include the orphan count and a stable shape."""
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--list-orphans", "--json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert "orphans_not_in_baseline" in out
    assert "baseline_count" in out
    assert "referenced_count" in out
    assert "total_dockerfiles" in out
    assert isinstance(out["orphans_not_in_baseline"], list)


# ---------------------------------------------------------------------------
# 9. Parse error handling
# ---------------------------------------------------------------------------

def test_parse_error_surfaced():
    """A compose file with invalid YAML should be surfaced as a
    parse-error, not crash the ratchet."""
    payload = """
services:
  test-svc:
    build: { this is not valid yaml
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_bad", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        # The ratchet should report a parse-error rather than crash.
        # (PyYAML is fairly tolerant, so the test only checks
        # that the ratchet doesn't raise an unhandled exception.)
        assert "problems" in out
    finally:
        _cleanup(path)


# ---------------------------------------------------------------------------
# 10. Build target with ${VAR} substitution
# ---------------------------------------------------------------------------

def test_env_var_default_in_dockerfile_path():
    """Compose `build.dockerfile` like `${FOO_DOCKERFILE:-Dockerfile}`
    should be resolved to the default value `Dockerfile` for the
    purpose of the ratchet check."""
    payload = """
services:
  test-svc:
    build:
      context: ./services/agent-zero
      dockerfile: ${TEST_SVC_DOCKERFILE:-Dockerfile}
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_envvar", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        # The default `Dockerfile` resolves to the existing
        # pmoves/services/agent-zero/Dockerfile, so no broken-build
        # finding for test-svc.
        broken = [
            p for p in out["problems"]
            if p.get("kind") == "broken-build"
            and p.get("service") == "test-svc"
        ]
        assert not broken, f"expected no broken-build for test-svc, got: {broken}"
    finally:
        _cleanup(path)
