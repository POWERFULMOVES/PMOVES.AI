"""Regression tests for the funnel's non-value secret guard.

Guards the Z890 2026-09-09 reversion: env.shared held
``SUPABASE_JWT_SECRET=${JWT_SECRET}`` (13 chars) where a fresh 58-char value
belonged. ``chit_encode_secrets`` exported the ref verbatim into the CGP,
``secrets_sync._first_usable`` accepted any non-empty string as usable, and the
merge write-back spread the ref across env.shared and every tier file — the
"JWT went 58 -> 13 after funnel#2" signature.

Three layers must now refuse a non-value:
1. ``is_placeholder`` — unexpanded ``${VAR}``/``$VAR`` refs count as placeholders.
2. ``secrets_sync`` — refs/placeholder literals are skipped in alias fallback,
   withheld from outputs, and warned about; merge mode preserves what targets
   already hold.
3. ``chit_encode_secrets`` — non-values never enter the CGP at all.
"""

from __future__ import annotations

import json
import sys

import pytest

from pmoves.tools import secrets_sync
from pmoves.tools._secrets_common import is_placeholder


# ---------------------------------------------------------------------------
# Layer 1: is_placeholder recognizes unexpanded refs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "${JWT_SECRET}",
        "$JWT_SECRET",
        "${JWT_SECRET:-fallback}",
        "${SERVICE_KEY}",
        "PLACEHOLDER_JWT_SECRET_HERE_GENERATE_WITH_OPENSSL_RAND_HEX_32",
    ],
)
def test_is_placeholder_rejects_refs_and_literals(value):
    assert is_placeholder(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "xT9mQ2vLpK4wR7zJ3nB8cD5fH1sA6yU0eG4iO2aW",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sig",
        "sk-live-$OTHER",  # interior ref, not a whole-value ref
        "pmoves4482$real",  # contains a placeholder-ish substring, not whole
    ],
)
def test_is_placeholder_accepts_real_values(value):
    assert is_placeholder(value) is False


# ---------------------------------------------------------------------------
# Layer 2: secrets_sync alias fallback + withholding
# ---------------------------------------------------------------------------


def _entry(label, aliases=(), targets=None, required=False, min_length=None):
    return secrets_sync.Entry(
        id=label.lower(),
        label=label,
        required=required,
        targets=targets
        or [secrets_sync.Target(file="env.tier-test", key=label)],
        aliases=aliases,
        min_length=min_length,
    )


def test_first_usable_skips_ref_and_falls_through_to_alias():
    secrets = {
        "SUPABASE_JWT_SECRET": "${JWT_SECRET}",
        "JWT_SECRET": "xT9mQ2vLpK4wR7zJ3nB8cD5fH1sA6yU0eG4iO2aW",
    }
    entry = _entry("SUPABASE_JWT_SECRET", aliases=("JWT_SECRET",))
    nonvalues: set[str] = set()
    assert secrets_sync._first_usable(secrets, entry, nonvalues) == "JWT_SECRET"
    assert nonvalues == {"SUPABASE_JWT_SECRET"}


def test_first_usable_returns_none_when_only_refs_exist():
    secrets = {"SUPABASE_JWT_SECRET": "${JWT_SECRET}"}
    entry = _entry("SUPABASE_JWT_SECRET", aliases=("JWT_SECRET",))
    nonvalues: set[str] = set()
    assert secrets_sync._first_usable(secrets, entry, nonvalues) is None
    assert nonvalues == {"SUPABASE_JWT_SECRET"}


def test_build_outputs_withholds_nonvalue_and_warns(capsys):
    entry = _entry("SUPABASE_JWT_SECRET", aliases=("JWT_SECRET",), required=True)
    outputs, missing = secrets_sync.build_outputs(
        {"SUPABASE_JWT_SECRET": "${JWT_SECRET}"},
        [entry],
        strict=False,
    )
    assert "env.tier-test" not in outputs
    assert missing == ["SUPABASE_JWT_SECRET"]
    err = capsys.readouterr().err
    assert "non-value secret(s)" in err
    assert "SUPABASE_JWT_SECRET" in err


def test_merge_writeback_preserves_fresh_value_when_source_is_ref(tmp_path, monkeypatch):
    """The actual reversion: a fresh tier value must survive a ref-carrying CGP."""
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    fresh = "xT9mQ2vLpK4wR7zJ3nB8cD5fH1sA6yU0eG4iO2aW"
    tier = tmp_path / "env.tier-test"
    tier.write_text(f"SUPABASE_JWT_SECRET={fresh}\n")

    entry = _entry("SUPABASE_JWT_SECRET", aliases=("JWT_SECRET",))
    outputs, _missing = secrets_sync.build_outputs(
        {"SUPABASE_JWT_SECRET": "${JWT_SECRET}"}, [entry], strict=False
    )
    secrets_sync.write_env_files(outputs, merge=True)

    parsed = _parse_strict(tier.read_text())
    assert parsed["SUPABASE_JWT_SECRET"] == fresh


def _parse_strict(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        k, v = s.split("=", 1)
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# Layer 3: chit_encode_secrets keeps non-values out of the CGP
# ---------------------------------------------------------------------------


def test_chit_encode_excludes_nonvalues(tmp_path, monkeypatch, capsys):
    from pmoves.tools import chit_encode_secrets

    env_file = tmp_path / "env.shared"
    env_file.write_text(
        "SUPABASE_JWT_SECRET=${JWT_SECRET}\n"
        "JWT_SECRET=xT9mQ2vLpK4wR7zJ3nB8cD5fH1sA6yU0eG4iO2aW\n"
        "POSTGRES_PASSWORD=\n",
        encoding="utf-8",
    )
    out = tmp_path / "env.cgp.json"
    monkeypatch.setattr(
        sys, "argv", ["chit_encode_secrets", "--env-file", str(env_file), "--out", str(out)]
    )
    chit_encode_secrets.main()

    err = capsys.readouterr().err
    assert "non-value key(s)" in err
    assert "SUPABASE_JWT_SECRET" in err
    assert "POSTGRES_PASSWORD" in err

    from pmoves.chit.codec import decode_secret_map, load_cgp

    secrets = decode_secret_map(load_cgp(out))
    assert "JWT_SECRET" in secrets
    assert "SUPABASE_JWT_SECRET" not in secrets
    assert "POSTGRES_PASSWORD" not in secrets
    assert json.loads(out.read_text(encoding="utf-8"))["points"]
