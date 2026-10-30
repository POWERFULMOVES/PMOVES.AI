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


# ---------------------------------------------------------------------------
# literal-secret-default (always on). Fixture keys are INVENTED.
# ---------------------------------------------------------------------------

FAKE_HEX64 = "0123456789abcdef" * 4
FAKE_HEX16 = "fedcba9876543210"


def _literal_findings(payload: str, name: str):
    path = _write_tmp_compose(name, payload)
    try:
        r = _run_ratchet_on_file(path)
        out = json.loads(r.stdout)
        return r, [p for p in out["problems"] if p["kind"] == "literal-secret-default"]
    finally:
        _cleanup(path)


def test_literal_hex_secret_default_fails_without_echoing_the_value():
    payload = f"""
services:
  invidious:
    environment:
    - INVIDIOUS_HMAC_KEY=${{INVIDIOUS_HMAC_KEY:-{FAKE_HEX64}}}
  invidious-companion:
    environment:
    - SERVER_SECRET_KEY=${{INVIDIOUS_COMPANION_KEY:-{FAKE_HEX16}}}
"""
    r, found = _literal_findings(payload, "test_validate_composes_literal_hex")
    assert r.returncode == 1
    assert [(p["service"], p["line"]) for p in found] == [("invidious", 5), ("invidious-companion", 8)]
    assert "<64 hex>" in found[0]["detail"] and "<16 hex>" in found[1]["detail"]
    assert FAKE_HEX64 not in r.stdout + r.stderr
    assert FAKE_HEX16 not in r.stdout + r.stderr


def test_literal_inside_a_string_value_is_found():
    """The Invidious HMAC also hid inside the INVIDIOUS_CONFIG YAML string."""
    payload = f"""
services:
  invidious:
    environment:
    - "INVIDIOUS_CONFIG=db:\\n  host: invidious-db\\nhmac_key: \\"${{INVIDIOUS_HMAC_KEY:-{FAKE_HEX64}}}\\"\\n"
"""
    r, found = _literal_findings(payload, "test_validate_composes_literal_embedded")
    assert r.returncode == 1 and len(found) == 1


def test_required_and_non_credential_defaults_pass():
    payload = """
services:
  svc-a:
    environment:
    - INVIDIOUS_HMAC_KEY=${INVIDIOUS_HMAC_KEY:?set INVIDIOUS_HMAC_KEY via secrets funnel}
    - API_KEY=${API_KEY:-}
    - FALLBACK_TOKEN=${FALLBACK_TOKEN:-${OTHER_TOKEN}}
    - DB_PASSWORD=${DB_PASSWORD:-postgres}
    - TOKEN_URL=${TOKEN_URL:-http://auth:8080/token0123456789abcdef}
    - P7_CONTROL_TOKEN_FILE=${P7_CONTROL_TOKEN_FILE:-/run/secrets/p7_control_token_v1}
    - BUILD_SHA=${BUILD_SHA:-0123456789abcdef0123}
"""
    r, found = _literal_findings(payload, "test_validate_composes_literal_clean")
    assert found == [], found
    assert r.returncode == 0, r.stdout


def test_literal_check_runs_on_a_file_outside_the_repo(tmp_path):
    """The failing-before control scans `git show origin/main:<file>` copies."""
    path = tmp_path / "docker-compose.yml"
    path.write_text(
        f"services:\n  s:\n    environment:\n    - K=${{SOME_SECRET:-{FAKE_HEX16}}}\n",
        encoding="utf-8",
    )
    r = _run_ratchet_on_file(path)
    out = json.loads(r.stdout)
    assert r.returncode == 1
    assert [p["kind"] for p in out["problems"]] == ["literal-secret-default"]
