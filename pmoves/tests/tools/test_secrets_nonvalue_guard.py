"""Regression tests for the funnel's non-value secret guard.

Guards the Z890 2026-09-09 reversion: env.shared held
``SUPABASE_JWT_SECRET=${JWT_SECRET}`` (13 chars) where a fresh 58-char value
belonged. ``chit_encode_secrets`` exported the ref verbatim into the CGP,
``secrets_sync._first_usable`` accepted any non-empty string as usable, and the
merge write-back spread the ref across every tier file.

Layers that now refuse a non-value:
1. ``is_unexpanded_ref`` -- recognises whole-value ``${VAR}``/``$VAR`` refs. It
   is deliberately NOT part of ``is_placeholder``, which also drives config
   defaults outside the secrets pipe.
2. ``secrets_sync`` -- refs and placeholder literals are skipped in alias
   fallback, withheld, named (never valued) in a warning, and NOT removed from
   merge targets.
3. ``chit_encode_secrets`` -- refs never enter the CGP.
4. ``fill_self_generated`` -- a ref is mirrored over like a blank and is never
   used as the JWT signing secret.

Every file these tests write lives under ``tmp_path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pmoves.tools import secrets_sync
from pmoves.tools._secrets_common import is_placeholder, is_unexpanded_ref
from pmoves.tools.secrets_self_generated import derive_supabase_jwt, fill_self_generated

FRESH = "xT9mQ2vLpK4wR7zJ3nB8cD5fH1sA6yU0eG4iO2aW"
REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Layer 1: ref detection, kept separate from is_placeholder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["${JWT_SECRET}", "$JWT_SECRET", "${JWT_SECRET:-fallback}", '"${SERVICE_KEY}"', " ${A} "],
)
def test_is_unexpanded_ref_recognises_whole_value_refs(value):
    assert is_unexpanded_ref(value) is True


@pytest.mark.parametrize(
    "value",
    [None, "", FRESH, "sk-live-$OTHER", "${A}${B}", "$1abc", "prefix${A}"],
)
def test_is_unexpanded_ref_leaves_real_and_interior_values_alone(value):
    assert is_unexpanded_ref(value) is False


def test_is_placeholder_does_not_absorb_refs():
    """brand_defaults fills config defaults wherever is_placeholder is True, so a
    deliberate ``KEY=${OTHER}`` in env.shared must not read as a placeholder."""
    assert is_placeholder("${SUPABASE_URL}") is False


# ---------------------------------------------------------------------------
# Layer 2: secrets_sync
# ---------------------------------------------------------------------------


def _entry(label, aliases=(), required=False):
    return secrets_sync.Entry(
        id=label.lower(),
        label=label,
        required=required,
        targets=[secrets_sync.Target(file="env.tier-test", key=label)],
        aliases=aliases,
    )


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            k, v = s.split("=", 1)
            out[k] = v
    return out


def test_first_usable_skips_ref_and_falls_through_to_alias():
    secrets = {"SUPABASE_JWT_SECRET": "${JWT_SECRET}", "JWT_SECRET": FRESH}
    entry = _entry("SUPABASE_JWT_SECRET", aliases=("JWT_SECRET",))
    nonvalues: set[str] = set()
    assert secrets_sync._first_usable(secrets, entry, nonvalues) == "JWT_SECRET"
    assert nonvalues == {"SUPABASE_JWT_SECRET"}


def test_first_usable_skips_placeholder_literal():
    secrets = {"GATE_API_KEY": "PLACEHOLDER_GENERATE_ME", "LEGACY_GATE_KEY": FRESH}
    entry = _entry("GATE_API_KEY", aliases=("LEGACY_GATE_KEY",))
    assert secrets_sync._first_usable(secrets, entry) == "LEGACY_GATE_KEY"


def test_build_outputs_withholds_nonvalue_and_warns_names_only(capsys):
    entry = _entry("SUPABASE_JWT_SECRET", required=True)
    other = _entry("OTHER_TOKEN")
    outputs, missing = secrets_sync.build_outputs(
        {"SUPABASE_JWT_SECRET": "${JWT_SECRET}", "OTHER_TOKEN": FRESH},
        [entry, other],
        strict=False,
    )
    assert outputs["env.tier-test"] == {"OTHER_TOKEN": FRESH}
    assert missing == ["SUPABASE_JWT_SECRET"]
    err = capsys.readouterr().err
    assert "non-value secret(s)" in err
    assert "SUPABASE_JWT_SECRET" in err
    assert FRESH not in err


def test_merge_writeback_preserves_fresh_value_on_main_s_path(tmp_path, monkeypatch):
    """main() passes rejected_out to build_outputs and remove= to write_env_files;
    a ref must not put the key in ``remove`` and delete the value it could not
    replace."""
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    tier = tmp_path / "env.tier-test"
    tier.write_text(f"SUPABASE_JWT_SECRET={FRESH}\n", encoding="utf-8")

    rejected: dict[str, set] = {}
    outputs, _ = secrets_sync.build_outputs(
        {"SUPABASE_JWT_SECRET": "${JWT_SECRET}"},
        [_entry("SUPABASE_JWT_SECRET")],
        strict=False,
        rejected_out=rejected,
    )
    secrets_sync.write_env_files(outputs, merge=True, remove=rejected)

    assert _parse(tier.read_text(encoding="utf-8"))["SUPABASE_JWT_SECRET"] == FRESH


def test_cleared_secret_is_still_removed(tmp_path, monkeypatch):
    """Preserving non-values must not widen into a blanket preserve: a blank is a
    clear, and omission is not removal."""
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    tier = tmp_path / "env.tier-test"
    tier.write_text("CIPHER_API_TOKEN=stale-value-to-be-cleared\n", encoding="utf-8")

    rejected: dict[str, set] = {}
    outputs, _ = secrets_sync.build_outputs(
        {"CIPHER_API_TOKEN": ""},
        [_entry("CIPHER_API_TOKEN")],
        strict=False,
        rejected_out=rejected,
    )
    secrets_sync.write_env_files(outputs, merge=True, remove=rejected)

    assert "CIPHER_API_TOKEN" not in _parse(tier.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Layer 3: chit_encode_secrets keeps refs out of the CGP
# ---------------------------------------------------------------------------


def test_chit_encode_excludes_refs_and_names_them(tmp_path, monkeypatch, capsys):
    from pmoves.chit.codec import decode_secret_map, load_cgp
    from pmoves.tools import chit_encode_secrets

    env_file = tmp_path / "shared.env"
    env_file.write_text(
        "SUPABASE_JWT_SECRET=${JWT_SECRET}\n"
        f"JWT_SECRET={FRESH}\n"
        "LOG_SINK=none\n"
        "POSTGRES_PASSWORD=\n",
        encoding="utf-8",
    )
    out = tmp_path / "env.cgp.json"
    monkeypatch.setattr(
        sys, "argv", ["chit_encode_secrets", "--env-file", str(env_file), "--out", str(out)]
    )
    chit_encode_secrets.main()

    err = capsys.readouterr().err
    assert "SUPABASE_JWT_SECRET" in err
    assert FRESH not in err
    secrets = decode_secret_map(load_cgp(out))
    assert "SUPABASE_JWT_SECRET" not in secrets
    assert secrets["JWT_SECRET"] == FRESH
    # Blanks and placeholder-looking config are secrets_sync's call, not this one's.
    assert secrets["LOG_SINK"] == "none"
    assert "POSTGRES_PASSWORD" in secrets


# ---------------------------------------------------------------------------
# Layer 4: fill_self_generated
# ---------------------------------------------------------------------------


def test_self_generated_mirrors_real_secret_over_a_ref():
    out = fill_self_generated({"JWT_SECRET": FRESH, "SUPABASE_JWT_SECRET": "${JWT_SECRET}"})
    assert out["SUPABASE_JWT_SECRET"] == FRESH


def test_self_generated_never_signs_with_a_ref():
    out = fill_self_generated({"JWT_SECRET": "${OTHER}", "SUPABASE_JWT_SECRET": FRESH})
    assert out["ANON_KEY"] == derive_supabase_jwt(FRESH, "anon")

    only_refs = fill_self_generated({"JWT_SECRET": "${A}", "SUPABASE_JWT_SECRET": "${B}"})
    assert "ANON_KEY" not in only_refs


def test_self_generated_rederives_a_ref_carrying_jwt_label():
    out = fill_self_generated({"JWT_SECRET": FRESH, "ANON_KEY": "${SUPABASE_ANON_KEY}"})
    assert out["ANON_KEY"] == derive_supabase_jwt(FRESH, "anon")


# ---------------------------------------------------------------------------
# Clear-key tombstone
# ---------------------------------------------------------------------------


def test_supabase_opaque_keys_are_in_the_clear_tombstone():
    """The tombstone's own header names these as the motivating case (Kong's
    duplicate keyauth crash-loop, #2593/#2595); they must be on the list."""
    from pmoves.scripts.bootstrap_env import read_cleared_keys

    keys = read_cleared_keys(REPO_ROOT / "pmoves" / "configs" / "secrets_cleared.yaml")
    assert {"SUPABASE_SECRET_KEY", "SUPABASE_PUBLISHABLE_KEY"} <= set(keys)
