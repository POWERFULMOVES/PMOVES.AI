"""Tests for pmoves/tools/pinokio_apps/discover.py (slice 4).

Tests use a tmp_path Pinokio fixture and the live registry schema.
No real Pinokio install required.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
for p in (
    os.path.join(_ROOT, "pmoves", "tools", "pinokio_apps"),
    os.path.join(_ROOT, "pmoves", "tools"),
    os.path.join(_ROOT, "pmoves"),
    _ROOT,
):
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

import discover  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def fake_pinokio_home(tmp_path) -> Path:
    """A fake Pinokio home with 3 app dirs, 1 with bad manifest, 1 hidden."""
    home = tmp_path / "pinokio"
    api = home / "api"
    api.mkdir(parents=True)

    # App 1: well-formed pinokio.js with all the fields
    a1 = api / "comfyui-desktop"
    a1.mkdir()
    (a1 / "pinokio.js").write_text(json.dumps({
        "title": "ComfyUI Desktop",
        "description": "Node-based SD workflow runner",
        "start_script": "start.js",
        "requirements": {"gpu": True, "vram_mb": 16384, "gpu_arch": ["sm_120"]},
        "endpoints": [{"port": 8188, "protocol": "http", "health": "/system_stats"}],
    }))

    # App 2: minimal pinokio.js, no manifest fields
    a2 = api / "minimal-app"
    a2.mkdir()
    (a2 / "pinokio.js").write_text(json.dumps({}))

    # App 3: malformed pinokio.js (jsonc with comments + trailing commas)
    a3 = api / "js-style-app"
    a3.mkdir()
    (a3 / "pinokio.js").write_text(textwrap_style(
        '{\n  // a comment\n  "title": "JS Style App",\n  "endpoints": [],\n}\n'
    ))

    # App 4: pinokio.json instead of pinokio.js
    a4 = api / "json-app"
    a4.mkdir()
    (a4 / "pinokio.json").write_text(json.dumps({
        "title": "JSON App", "description": "Uses pinokio.json", "start_script": "main.js"
    }))

    # App 5: hidden dir, should be skipped
    a5 = api / ".hidden-app"
    a5.mkdir()

    # App 6: invalid slug (uppercase) — the discover tool should reject it
    a6 = api / "InvalidSlug"
    a6.mkdir()
    (a6 / "pinokio.js").write_text(json.dumps({"title": "Invalid"}))

    return home


def textwrap_style(s: str) -> str:
    """Tiny helper: no-op (the textwrap import would be unused)."""
    return s


@pytest.fixture
def validator() -> Draft202012Validator:
    return discover.load_schema()


@pytest.fixture
def registry_dir(tmp_path) -> Path:
    """An empty curated dir."""
    d = tmp_path / "curated"
    d.mkdir()
    return d


@pytest.fixture
def user_dir(tmp_path) -> Path:
    """An empty user dir."""
    d = tmp_path / "user"
    d.mkdir()
    return d


# --------------------------------------------------------------------------
# Helpers: read/write the live schema
# --------------------------------------------------------------------------

def test_schema_loads_and_validates_basic_entry(validator) -> None:
    entry = {
        "schema_version": "1.0.0", "slug": "x", "title": "X", "description": "test",
        "owner": "pinokio", "version_seen": "0.0.1",
        "runtime": {
            "launcher_script": "start.js", "autostart": False,
            "gpu_required": False, "min_vram_mb": 0, "gpu_arch": [],
            "gpu_reservation_mb": 0, "gpu_reservation_mode": "concurrent",
            "dependencies": [], "requires_hf_login": False,
        },
        "endpoints": {"primary": {"port": 0, "protocol": "http", "health": None}, "alt": []},
        "pinokio_skill_ref": None,
        "network_exposure": {
            "l1_venv": {"reachable": True}, "l2_container_same_host": {"reachable": True, "address": None},
            "l3_mesh": {"reachable": False, "address": None, "headscale_acl_ports": [], "tags_required": []},
            "l4_public": {"reachable": False, "tunnel": None, "dns_record": None, "public_url": None},
        },
        "notes": [],
    }
    errs = list(validator.iter_errors(entry))
    assert not errs, errs[0].message if errs else ""


# --------------------------------------------------------------------------
# Manifest reading
# --------------------------------------------------------------------------

def test_read_pinokio_manifest_finds_js(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "comfyui-desktop" / "pinokio.js"
    m = discover.read_pinokio_manifest(p.parent)
    assert m is not None
    assert m["title"] == "ComfyUI Desktop"


def test_read_pinokio_manifest_finds_json(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "json-app"
    m = discover.read_pinokio_manifest(p)
    assert m is not None
    assert m["title"] == "JSON App"


def test_read_pinokio_manifest_strips_js_comments_and_trailing_commas(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "js-style-app"
    m = discover.read_pinokio_manifest(p)
    assert m is not None
    assert m["title"] == "JS Style App"


def test_read_pinokio_manifest_returns_none_when_missing(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "minimal-app"
    # Remove the pinokio.js to force the "no manifest" path
    (p / "pinokio.js").unlink()
    assert discover.read_pinokio_manifest(p) is None


# --------------------------------------------------------------------------
# Detection helpers
# --------------------------------------------------------------------------

def test_detect_endpoints_with_manifest(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "comfyui-desktop"
    manifest = discover.read_pinokio_manifest(p)
    e = discover.detect_endpoints(manifest, p)
    assert e["primary"]["port"] == 8188
    assert e["primary"]["protocol"] == "http"
    assert e["primary"]["health"] == "/system_stats"


def test_detect_endpoints_without_manifest(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "minimal-app"
    e = discover.detect_endpoints(None, p)
    assert e["primary"]["port"] == 0
    assert e["primary"]["protocol"] == "http"
    assert e["primary"]["health"] is None


def test_detect_hardware_from_manifest(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "comfyui-desktop"
    manifest = discover.read_pinokio_manifest(p)
    h = discover.detect_hardware(manifest, p)
    assert h["gpu_required"] is True
    assert h["min_vram_mb"] == 16384
    assert h["gpu_arch"] == ["sm_120"]
    assert h["gpu_reservation_mb"] == 16384


def test_detect_version_reads_version_json(tmp_path) -> None:
    api = tmp_path / "app"
    api.mkdir()
    (api / "version.json").write_text(json.dumps({"version": "1.2.3"}))
    assert discover.detect_version(api) == "1.2.3"


def test_detect_version_falls_back_to_unknown(tmp_path) -> None:
    api = tmp_path / "app"
    api.mkdir()
    assert discover.detect_version(api) == "0.0.0-unknown"


def test_detect_p8_skill_extracts_skill_ref(fake_pinokio_home) -> None:
    p = fake_pinokio_home / "api" / "comfyui-desktop"
    manifest = discover.read_pinokio_manifest(p)
    # The test manifest doesn't declare a skill
    assert discover.detect_p8_skill(manifest) is None


# --------------------------------------------------------------------------
# Build + validation
# --------------------------------------------------------------------------

def test_build_entry_for_well_formed_app(fake_pinokio_home, validator) -> None:
    p = fake_pinokio_home / "api" / "comfyui-desktop"
    manifest = discover.read_pinokio_manifest(p)
    entry = discover.build_entry(p, manifest)
    assert entry["slug"] == "comfyui-desktop"
    assert entry["title"] == "ComfyUI Desktop"
    errs = list(validator.iter_errors(entry))
    assert not errs


def test_build_entry_rejects_invalid_slug(tmp_path, validator) -> None:
    p = tmp_path / "InvalidSlug"
    p.mkdir()
    with pytest.raises(ValueError, match="invalid slug"):
        discover.build_entry(p, None)


# --------------------------------------------------------------------------
# Discover
# --------------------------------------------------------------------------

def test_discover_finds_4_new_apps_and_skips_hidden(
    fake_pinokio_home, registry_dir, validator
) -> None:
    entries, source_dirs, errors = discover.discover(
        str(fake_pinokio_home), set(), validator
    )
    # 5 visible (comfyui, minimal, js-style, json, InvalidSlug)
    # - InvalidSlug is rejected at build (invalid slug)
    # - .hidden-app is skipped
    # - minimal has no manifest, but the build path handles that
    assert len(entries) == 4  # comfyui, minimal, js-style, json
    assert len(errors) == 1  # InvalidSlug
    slugs = {e["slug"] for e in entries}
    assert slugs == {"comfyui-desktop", "minimal-app", "js-style-app", "json-app"}


def test_discover_skips_existing_slugs(
    fake_pinokio_home, registry_dir, validator
) -> None:
    entries, _, errors = discover.discover(
        str(fake_pinokio_home), {"comfyui-desktop", "minimal-app"}, validator
    )
    slugs = {e["slug"] for e in entries}
    assert "comfyui-desktop" not in slugs
    assert "minimal-app" not in slugs
    # The only error is the InvalidSlug fixture (rejected at build);
    # the existing-slug skips do not produce errors.
    assert len(errors) == 1
    assert "InvalidSlug" in str(errors[0][0])


def test_discover_raises_when_api_dir_missing(tmp_path, validator) -> None:
    with pytest.raises(FileNotFoundError):
        discover.discover(str(tmp_path / "nope"), set(), validator)


# --------------------------------------------------------------------------
# Write
# --------------------------------------------------------------------------

def test_write_entries_creates_files(validator, fake_pinokio_home, user_dir) -> None:
    entries, _, _ = discover.discover(str(fake_pinokio_home), set(), validator)
    written = discover.write_entries(entries, str(user_dir), dry_run=False)
    assert len(written) == 4
    for p in written:
        assert p.exists()
        # Re-parse and re-validate
        data = yaml.safe_load(p.read_text())
        assert not list(validator.iter_errors(data))


def test_write_entries_dry_run_does_not_create_files(validator, fake_pinokio_home, user_dir) -> None:
    entries, _, _ = discover.discover(str(fake_pinokio_home), set(), validator)
    written = discover.write_entries(entries, str(user_dir), dry_run=True)
    assert len(written) == 4
    for p in written:
        assert not p.exists()


def test_write_entries_creates_user_dir_if_missing(validator, fake_pinokio_home, tmp_path) -> None:
    target = tmp_path / "new_user_dir"
    assert not target.exists()
    entries, _, _ = discover.discover(str(fake_pinokio_home), set(), validator)
    discover.write_entries(entries, str(target), dry_run=False)
    assert target.is_dir()
