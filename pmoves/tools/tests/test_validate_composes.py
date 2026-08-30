# pmoves/tools/tests/test_validate_composes.py
"""Tests for the validate-composes ratchet.

The ratchet is the durable answer to the env.local straggler pattern
that PR #2415 had to clean up manually. It must:
  1. Pass when no overlay has any short-form .env.local listing.
  2. Fail when any overlay re-introduces the short form.
  3. Treat _meta keys (underscore-prefixed) as not-overlay-data.
  4. Tolerate PMOVES Compose custom tags (!override, !reset).
  5. With --check-images, flag moving tags / no-digest refs; without
     it, only env_file patterns are checked (the actual ratchet).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "validate_composes.py"
)
PYTHON = sys.executable


def _run_with_compose(payload: dict, *args: str) -> subprocess.CompletedProcess:
    """Drop a synthetic compose file into a tmp dir, point the
    ratchet at it via the COMPOSE_DIR override (we use --registry
    semantics by monkey-patching; for tests we just put a single
    file in a tmp dir and let the ratchet scan *all* of pmoves).
    For per-test isolation, we instead write a single file into
    pmoves/docker-compose.test-tmp.yml, run, then remove.
    """
    raise NotImplementedError  # not used; we use _run_with_real_dir instead


def _write_tmp_compose(name: str, content: str) -> Path:
    """Write a single file into pmoves/ as docker-compose.<name>.yml
    so the ratchet's glob picks it up, then remove on teardown.

    The test file is at pmoves/tools/tests/test_validate_composes.py,
    so `Path(__file__).resolve().parents[1]` is `pmoves/tools/` and
    `parents[2]` is `pmoves/`. The ratchet's `pmoves/` glob is
    `parents[2] / "pmoves"` from `pmoves/tools/validate_composes.py`,
    which is the same directory.
    """
    target = Path(__file__).resolve().parents[2] / f"docker-compose.{name}.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _run_ratchet(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(RATCHET), *args, "--json"],
        capture_output=True, text=True,
    )


def _run_ratchet_on_file(file: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(RATCHET), "--file", str(file), *args, "--json"],
        capture_output=True, text=True,
    )


def test_clean_overlay_passes():
    payload = """
services:
  svc-a:
    env_file:
    - env.shared
    - env.shared.generated
    # .env.local is a per-node opt-in; short-form listing made it REQUIRED
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_clean", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 0, r.stdout + r.stderr
        out = json.loads(r.stdout)
        assert out["problems"] == []
        assert out["summary"] == {}
    finally:
        _cleanup(path)


def test_short_form_env_local_fails():
    payload = """
services:
  svc-a:
    env_file:
    - env.shared
    - .env.local
"""
    path = _write_tmp_compose("test_validate_composes_shortform", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 1, r.stdout
        out = json.loads(r.stdout)
        assert any(p["kind"] == "env-local-shortform" for p in out["problems"])
        assert any("docker-compose.test_validate_composes_shortform.yml" in p["file"] for p in out["problems"])
        assert any(p["service"] == "svc-a" for p in out["problems"])
    finally:
        _cleanup(path)


def test_long_form_required_true_fails():
    """Marking `.env.local` as required=True in long form is the same
    bug as the short form; surface it the same way."""
    payload = """
services:
  svc-a:
    env_file:
    - path: .env.local
      required: true
"""
    path = _write_tmp_compose("test_validate_composes_longrequired", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 1
        out = json.loads(r.stdout)
        assert any(p["kind"] == "env-local-longform-required" for p in out["problems"])
    finally:
        _cleanup(path)


def test_long_form_required_false_passes():
    payload = """
services:
  svc-a:
    env_file:
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_longopt", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 0, r.stdout
    finally:
        _cleanup(path)


def test_string_form_env_file_env_local_fails():
    """Single-string `env_file: .env.local` is also REQUIRED by default."""
    payload = """
services:
  svc-a:
    env_file: .env.local
"""
    path = _write_tmp_compose("test_validate_composes_strform", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 1
        out = json.loads(r.stdout)
        assert any(p["kind"] == "env-local-shortform" for p in out["problems"])
    finally:
        _cleanup(path)


def test_compose_override_tag_tolerated():
    """`!reset` (PMOVES Compose 2.24+ replace semantics) must not crash."""
    payload = """
services:
  svc-a:
    image: foo:latest
    devices: !reset []
    env_file:
    - env.shared
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_reset", payload)
    try:
        r = _run_ratchet_on_file(path)
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        _cleanup(path)


def test_check_images_off_by_default():
    """Even with no-digest images, default run must not fail on them."""
    payload = """
services:
  svc-a:
    image: foo/bar:latest
    env_file:
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_imgoff", payload)
    try:
        r = _run_ratchet_on_file(path)  # no --check-images
        assert r.returncode == 0, r.stdout
        # and with --check-images, the no-digest image surfaces
        r2 = _run_ratchet_on_file(path, "--check-images")
        assert r2.returncode == 1
        out = json.loads(r2.stdout)
        assert any(p["kind"] == "image-no-digest" for p in out["problems"])
    finally:
        _cleanup(path)


def test_image_no_tag_flagged_under_check_images():
    """`foo/bar` (no tag) defaults to :latest; surface under --check-images."""
    payload = """
services:
  svc-a:
    image: foo/bar
    env_file:
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_notag", payload)
    try:
        r = _run_ratchet_on_file(path, "--check-images")
        assert r.returncode == 1
        out = json.loads(r.stdout)
        assert any(p["kind"] == "image-no-tag" for p in out["problems"])
    finally:
        _cleanup(path)


def test_digest_pinned_passes_under_check_images():
    """An image with @sha256:... passes even with --check-images."""
    payload = """
services:
  svc-a:
    image: foo/bar@sha256:0000000000000000000000000000000000000000000000000000000000000000
    env_file:
    - path: .env.local
      required: false
"""
    path = _write_tmp_compose("test_validate_composes_digest", payload)
    try:
        r = _run_ratchet_on_file(path, "--check-images")
        assert r.returncode == 0, r.stdout
    finally:
        _cleanup(path)
