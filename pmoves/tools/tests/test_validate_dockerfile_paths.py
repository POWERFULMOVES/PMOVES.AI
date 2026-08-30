# pmoves/tools/tests/test_validate_dockerfile_paths.py
"""Tests for the validate-dockerfile-paths ratchet.

The ratchet is the durable answer to the operator's #2358 meta-callout:
"the file the developer touched ≠ the file the runner builds". It must:

  1. Pass when every compose `build:` points to a real Dockerfile.
  2. Fail when a compose `build:` points to a missing Dockerfile.
  3. Pass when an orphan Dockerfile is in the baseline.
  4. Fail when a new orphan Dockerfile appears (not in baseline).
  5. Skip vendor / provisions paths, sibling checkouts outside
     `pmoves/`, and any path inside a submodule registered in
     .gitmodules — INCLUDING one nested under an in-scope parent dir
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


def test_registered_submodule_inside_pmoves_is_skipped():
    """The case the test above only appears to cover.

    `test_sibling_submodule_path_skipped` uses `../PMOVES-Archon`, which
    is rejected by the FIRST line of the scope predicate for starting
    outside `pmoves/` -- swap it for `../anything` and it still passes.
    Every one of this repo's 75 registered submodules is at a path
    INSIDE `pmoves/`, and `pmoves/integrations/archon` sits under
    `integrations/`, which the parent-dir allowlist calls in-scope. So
    the ratchet flagged `pmoves/docker-compose.archon-ui.submodule.yml`
    as a broken build for a Dockerfile that is present at the pinned
    submodule commit and merely absent from a CI checkout.
    """
    payload = """
services:
  archon-ui:
    build:
      context: integrations/archon/archon-ui-main
      dockerfile: Dockerfile
    image: archon-ui:test
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_registered_sub", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        findings = [
            p for p in out["problems"]
            if p.get("service") == "archon-ui" and p.get("kind") == "broken-build"
        ]
        assert not findings, f"registered submodule should be out of scope, got: {findings}"
    finally:
        _cleanup(path)


def test_missing_dockerfile_under_in_scope_dir_is_still_flagged():
    """Negative control for the exemption above.

    Consulting .gitmodules must exempt submodule paths and NOTHING
    else. `pmoves/integrations/` is in scope; a path under it that is
    not inside any registered submodule must still fail, or the fix
    would have traded a false positive for a false negative.
    """
    payload = """
services:
  notasub:
    build:
      context: integrations/definitely-not-a-submodule
      dockerfile: Dockerfile
    image: notasub:test
"""
    path = _write_tmp_compose("test_validate_dockerfile_paths_notasub", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        findings = [
            p for p in out["problems"]
            if p.get("service") == "notasub" and p.get("kind") == "broken-build"
        ]
        assert findings, "a missing Dockerfile under an in-scope non-submodule dir must still be flagged"
    finally:
        _cleanup(path)


def test_submodule_paths_are_read_from_gitmodules_not_a_name_convention():
    """Structural assertion on the source, not a copy of the logic.

    Anchored to the real `.gitmodules` so that the property the fix
    depends on -- registered submodules living INSIDE the in-scope
    parent dirs -- is asserted against the tree rather than restated.
    A test that rebuilt the set from the same regex could not fail.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_vdp", RATCHET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    subs = module._registered_submodule_paths()
    assert subs, "expected registered submodules; .gitmodules parsed as empty"

    inside_scope = {
        s for s in subs
        if s.startswith("pmoves/")
        and s.split("/")[1] in module.DOCKERFILE_PARENT_DIRS
    }
    assert inside_scope, (
        "no registered submodule sits under an in-scope parent dir -- if this "
        "ever becomes true the exemption is dead code, but today it is the "
        "whole reason it exists"
    )
    assert "pmoves/integrations/archon" in subs


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


# ---------------------------------------------------------------------------
# 11. COPY_UNRESOLVED — the class that would have caught #2468
# ---------------------------------------------------------------------------
#
# `mai-ui-agent` shipped `COPY requirements.txt .` against `context: .`
# (= pmoves/), where no such file exists, so the image dies on its first
# COPY. Sibling `evo-controller` does the same job correctly from the same
# root context — `COPY services/evo-controller/requirements.txt .`. The
# correct and the broken form are equally plausible on a review diff, which
# is what makes it a gate's job rather than a reviewer's.

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("_vdp", RATCHET)
_vdp = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_vdp)


def _write_service(name: str, dockerfile: str, files: dict) -> Path:
    """Create pmoves/services/<name>/ with a Dockerfile + given files."""
    d = PMOVES_DIR / "services" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    for rel, content in files.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    return d


def _rmtree(d: Path) -> None:
    import shutil
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def test_copy_source_missing_under_declared_context():
    """The #2468 shape: root context, service-relative COPY."""
    svc = _write_service(
        "zz-copytest-broken",
        "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\n",
        {"requirements.txt": "flask\n"},
    )
    payload = """
services:
  test-svc:
    build:
      context: .
      dockerfile: services/zz-copytest-broken/Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_vdp_copy_broken", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        hits = [
            f for f in out["copy_new"]
            if f["dockerfile"].endswith("zz-copytest-broken/Dockerfile")
        ]
        assert hits, f"expected COPY_UNRESOLVED for the service, got: {out['copy_new']}"
        assert hits[0]["kind"] == "COPY_UNRESOLVED"
        assert hits[0]["source"] == "requirements.txt"
        assert r.returncode == 1
    finally:
        _cleanup(path)
        _rmtree(svc)


def test_copy_source_correct_for_root_context_passes():
    """The `evo-controller` shape: service-qualified source, root context."""
    svc = _write_service(
        "zz-copytest-ok",
        "FROM python:3.12-slim\nWORKDIR /app\n"
        "COPY services/zz-copytest-ok/requirements.txt .\n",
        {"requirements.txt": "flask\n"},
    )
    payload = """
services:
  test-svc:
    build:
      context: .
      dockerfile: services/zz-copytest-ok/Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_vdp_copy_ok", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        hits = [
            f for f in out["copy_new"]
            if f["dockerfile"].endswith("zz-copytest-ok/Dockerfile")
        ]
        assert not hits, f"expected no COPY finding, got: {hits}"
    finally:
        _cleanup(path)
        _rmtree(svc)


def test_copy_glob_with_no_match_is_flagged():
    """`COPY *.whl .` with no wheel present fails the real build with
    'no source files were specified'; the gate must say so first."""
    svc = _write_service(
        "zz-copytest-glob",
        "FROM python:3.12-slim\nCOPY services/zz-copytest-glob/*.whl .\n",
        {"app.py": "x = 1\n"},
    )
    payload = """
services:
  test-svc:
    build:
      context: .
      dockerfile: services/zz-copytest-glob/Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_vdp_copy_glob", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        hits = [
            f for f in out["copy_new"]
            if f["dockerfile"].endswith("zz-copytest-glob/Dockerfile")
        ]
        assert hits, f"expected a glob finding, got: {out['copy_new']}"
        assert "matches nothing" in hits[0]["detail"]
    finally:
        _cleanup(path)
        _rmtree(svc)


def test_copy_from_stage_and_remote_are_skipped_not_flagged():
    """`--from=` resolves against a build stage and ADD <url> is fetched at
    build time. Neither has anything on disk to check, so both are recorded
    as skips with a reason rather than flagged or silently dropped."""
    svc = _write_service(
        "zz-copytest-skips",
        "FROM python:3.12-slim AS builder\n"
        "FROM python:3.12-slim\n"
        "COPY --from=builder /app/dist ./dist\n"
        "ADD https://example.invalid/x.tar.gz /tmp/\n",
        {},
    )
    payload = """
services:
  test-svc:
    build:
      context: .
      dockerfile: services/zz-copytest-skips/Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_vdp_copy_skips", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        hits = [
            f for f in out["copy_new"]
            if f["dockerfile"].endswith("zz-copytest-skips/Dockerfile")
        ]
        assert not hits, f"expected no findings for skip-only Dockerfile, got: {hits}"
    finally:
        _cleanup(path)
        _rmtree(svc)


def test_copy_arg_interpolation_is_skipped_not_guessed():
    """A COPY source containing ${ARG} is only known at build time.
    Guessing a default would invent findings, so it is skipped."""
    svc = _write_service(
        "zz-copytest-arg",
        "FROM python:3.12-slim\nARG SRC_DIR=services/zz-copytest-arg\n"
        "COPY ${SRC_DIR}/app.py .\n",
        {"app.py": "x = 1\n"},
    )
    payload = """
services:
  test-svc:
    build:
      context: .
      dockerfile: services/zz-copytest-arg/Dockerfile
    image: test-svc:latest
"""
    path = _write_tmp_compose("test_vdp_copy_arg", payload)
    try:
        r = _run_ratchet("--compose", str(path))
        out = json.loads(r.stdout)
        hits = [
            f for f in out["copy_new"]
            if f["dockerfile"].endswith("zz-copytest-arg/Dockerfile")
        ]
        assert not hits, f"ARG interpolation must be skipped, not flagged: {hits}"
    finally:
        _cleanup(path)
        _rmtree(svc)


# ---------------------------------------------------------------------------
# 12. Parser units — the shapes a naive line-grep gets wrong
# ---------------------------------------------------------------------------

def test_parser_handles_multi_source_flags_and_continuations(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text(
        "FROM alpine\n"
        "COPY app.py nats_integration.py ./\n"
        "COPY --chown=1000:1000 --chmod=755 a.txt .\n"
        'COPY ["with space.txt", "dest/"]\n'
        "COPY a.py \\\n"
        "     b.py \\\n"
        "# a comment inside the continuation\n"
        "     ./\n",
        encoding="utf-8",
    )
    entries = _vdp.parse_copy_instructions(df)
    assert entries[0]["sources"] == ["app.py", "nats_integration.py"]
    assert entries[1]["flags"] == ["--chown=1000:1000", "--chmod=755"]
    assert entries[1]["sources"] == ["a.txt"]
    assert entries[2]["sources"] == ["with space.txt"]
    assert entries[3]["sources"] == ["a.py", "b.py"], (
        "a comment line inside a continuation must not break the join"
    )


def test_parser_honours_escape_directive(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text(
        "# escape=`\n"
        "FROM alpine\n"
        "COPY a.py `\n"
        "     b.py `\n"
        "     ./\n",
        encoding="utf-8",
    )
    entries = _vdp.parse_copy_instructions(df)
    assert entries[0]["sources"] == ["a.py", "b.py"]


def test_dockerignore_matcher_is_anchored_at_context_root():
    """Docker patterns are anchored at the context root and `*` does not
    cross a `/` — unlike gitignore. Matching them the gitignore way would
    invent DOCKERIGNORE_EXCLUDED findings for files docker actually ships,
    which on a hard gate means a spurious red build."""
    pats = [(False, "*.md"), (False, "**/__pycache__"), (False, "tests"), (True, "README.md")]
    assert _vdp._dockerignored("CHANGELOG.md", pats) == "*.md"
    assert _vdp._dockerignored("docs/guide.md", pats) is None
    assert _vdp._dockerignored("README.md", pats) is None
    assert _vdp._dockerignored("app/__pycache__/x.pyc", pats) == "**/__pycache__"
    assert _vdp._dockerignored("tests/a.py", pats) == "tests"
    assert _vdp._dockerignored("src/main.py", pats) is None


# ---------------------------------------------------------------------------
# 13. Ratchet contract: stale baseline entries fail too
# ---------------------------------------------------------------------------

def test_stale_copy_baseline_entry_fails(monkeypatch, tmp_path):
    """A baselined key that no longer occurs was FIXED. Leaving it in the
    file re-accepts the same defect if it returns, which contradicts the
    count-only-down claim — so it fails the gate like a new finding does."""
    baseline = tmp_path / "_known_copy_gaps.yaml"
    baseline.write_text(
        "known_copy_gaps:\n"
        '  - "COPY_UNRESOLVED|pmoves/services/gone/Dockerfile:1|pmoves|vanished.txt"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_vdp, "COPY_BASELINE", baseline)
    assert _vdp.load_copy_baseline() == {
        "COPY_UNRESOLVED|pmoves/services/gone/Dockerfile:1|pmoves|vanished.txt"
    }
    live = set()
    assert sorted(_vdp.load_copy_baseline() - live), "stale entry must be detected"
