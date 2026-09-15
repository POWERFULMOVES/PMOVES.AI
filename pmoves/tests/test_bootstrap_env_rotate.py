"""Tests for bootstrap_env.rotate_secret — the secrets-rotate primitive.

rotate_secret surgically replaces a single KEY=value line in env.shared (the
secrets-funnel source), preserving everything else, so a rotation can't corrupt
the file or drop unrelated keys. Multi-line values are refused (they'd corrupt a
line-based env file — same hazard class as the secrets_sync serializer fix).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_env.py"
_spec = importlib.util.spec_from_file_location("bootstrap_env_under_test", _MOD_PATH)
be = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass annotation resolution can find the module.
sys.modules[_spec.name] = be
_spec.loader.exec_module(be)


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_generates_fresh_value_and_replaces_in_place(tmp_path):
    env = _write(
        tmp_path / "env.shared",
        "# header\nFOO=keep\nRENDER_WEBHOOK_SHARED_SECRET=old\nBAR=keep2\n",
    )
    new = be.rotate_secret("RENDER_WEBHOOK_SHARED_SECRET", length=32, env_path=env)
    text = env.read_text(encoding="utf-8")
    assert new and new != "old"
    assert len(new) == 32  # random_urlsafe truncated to length
    assert f"RENDER_WEBHOOK_SHARED_SECRET={new}" in text
    assert "FOO=keep" in text and "BAR=keep2" in text and "# header" in text
    assert text.count("RENDER_WEBHOOK_SHARED_SECRET=") == 1  # replaced, not duplicated


def test_explicit_value_is_used(tmp_path):
    env = _write(tmp_path / "env.shared", "JELLYFIN_API_KEY=oldkey\n")
    new = be.rotate_secret("JELLYFIN_API_KEY", value="abc123def", env_path=env)
    assert new == "abc123def"
    assert env.read_text(encoding="utf-8") == "JELLYFIN_API_KEY=abc123def\n"


def test_appends_when_key_absent(tmp_path):
    env = _write(tmp_path / "env.shared", "EXISTING=1\n")
    be.rotate_secret("NEWKEY", value="v", env_path=env)
    lines = env.read_text(encoding="utf-8").splitlines()
    assert "EXISTING=1" in lines and "NEWKEY=v" in lines


def test_refuses_multiline_value_and_leaves_file_untouched(tmp_path):
    env = _write(tmp_path / "env.shared", "K=old\n")
    with pytest.raises(ValueError):
        be.rotate_secret("K", value="-----BEGIN-----\nabc\n-----END-----", env_path=env)
    assert env.read_text(encoding="utf-8") == "K=old\n"


def test_preserves_comments_blanks_and_order_exactly(tmp_path):
    body = "# c1\nA=1\n\n# c2\nB=2\nTARGET=old\nC=3\n"
    env = _write(tmp_path / "env.shared", body)
    be.rotate_secret("TARGET", value="new", env_path=env)
    assert env.read_text(encoding="utf-8") == "# c1\nA=1\n\n# c2\nB=2\nTARGET=new\nC=3\n"


def test_generated_value_is_url_safe_no_slash(tmp_path):
    # token_urlsafe avoids '/' and '+' -> no connection-string URL-encode fragility
    env = _write(tmp_path / "env.shared", "SUPABASE_DB_PASSWORD=old\n")
    new = be.rotate_secret("SUPABASE_DB_PASSWORD", length=48, env_path=env)
    assert "/" not in new and "+" not in new and len(new) == 48


def test_dedupes_multiple_occurrences(tmp_path):
    # last-wins env parsers would otherwise let a stale later duplicate survive
    env = _write(tmp_path / "env.shared", "DUP=old1\nX=1\nDUP=old2\n")
    be.rotate_secret("DUP", value="fresh", env_path=env)
    text = env.read_text(encoding="utf-8")
    assert text.count("DUP=") == 1
    assert "DUP=fresh" in text and "old1" not in text and "old2" not in text
    assert "X=1" in text


def test_rejects_non_identifier_keys(tmp_path):
    env = _write(tmp_path / "env.shared", "A=1\n")
    for bad in ("1BAD", "#BAD", "BAD KEY", "BA-D", ""):
        with pytest.raises(ValueError):
            be.rotate_secret(bad, value="v", env_path=env)
    assert env.read_text(encoding="utf-8") == "A=1\n"  # untouched


# --- generator-axis resolution -------------------------------------------
#
# The two axes of a generated rotation — type and length — are resolved
# independently. An operator naming one axis on the command line must not
# silently discard the registry's declaration of the other.
#
# `--rotate VAULT_ENC_KEY --gen-type random_hex` used to emit 48 hex chars
# because the whole registry lookup sat under `if gen_type is None`. The
# registry declares 32, and the yt OAuth flow does bytes.fromhex() on it, so
# the 48-char value is the corruption this file already documents — reachable
# through the very flag an operator would reach for to avoid it.


@pytest.fixture()
def registry(tmp_path):
    import json

    p = tmp_path / "registry.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "services": [
                    {
                        "id": "supabase",
                        "variables": [
                            {
                                "key": "VAULT_ENC_KEY",
                                "generate": {"type": "random_hex", "length": 32},
                            },
                            {
                                "key": "TYPE_ONLY",
                                "generate": {"type": "random_hex"},
                            },
                            {"key": "NO_GENERATOR"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return str(p)


def test_registry_supplies_both_axes_when_neither_flag_is_given(registry):
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "VAULT_ENC_KEY", registry, None, None
    )
    assert (gen_type, length) == ("random_hex", 32)
    assert t_src == l_src == "bootstrap registry"


def test_explicit_gen_type_does_not_suppress_the_declared_length(registry):
    """The regression: naming the type stole the length."""
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "VAULT_ENC_KEY", registry, "random_hex", None
    )
    assert gen_type == "random_hex"
    assert length == 32, "registry-declared length must survive an explicit --gen-type"
    assert t_src == "--gen-type"
    assert l_src == "bootstrap registry"


def test_explicit_length_does_not_suppress_the_declared_type(registry):
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "VAULT_ENC_KEY", registry, None, 64
    )
    assert gen_type == "random_hex", "registry-declared type must survive --length"
    assert length == 64
    assert t_src == "bootstrap registry"
    assert l_src == "--length"


def test_explicit_flags_win_over_the_registry(registry):
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "VAULT_ENC_KEY", registry, "passphrase", 12
    )
    assert (gen_type, length, t_src, l_src) == ("passphrase", 12, "--gen-type", "--length")


def test_partial_declaration_falls_back_per_axis(registry):
    """A registry entry declaring only a type still gets the built-in length."""
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "TYPE_ONLY", registry, None, None
    )
    assert (gen_type, length) == ("random_hex", be.DEFAULT_GEN_LENGTH)
    assert t_src == "bootstrap registry"
    assert l_src == "built-in default"


def test_unknown_key_falls_back_to_built_in_defaults(registry):
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "NOT_IN_REGISTRY", registry, None, None
    )
    assert (gen_type, length) == (be.DEFAULT_GEN_TYPE, be.DEFAULT_GEN_LENGTH)
    assert t_src == l_src == "built-in default"


def test_unreadable_registry_does_not_block_a_rotation(tmp_path):
    """_registry_generator swallows read errors; resolution must still return."""
    gen_type, length, t_src, l_src = be._resolve_generator_axes(
        "VAULT_ENC_KEY", str(tmp_path / "nope.json"), None, None
    )
    assert (gen_type, length) == (be.DEFAULT_GEN_TYPE, be.DEFAULT_GEN_LENGTH)
    assert t_src == l_src == "built-in default"
