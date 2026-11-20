"""parse_env_file keeps valid base64 values and can report what it drops.

The removed rule rejected any unquoted value containing '+' and ending in '=',
claiming it "will break Docker Compose parsing". Measured 2026-11-20 on B850:
``docker compose config`` renders ``PW=Ab+cd/ef12345678=`` unchanged through
both ``env_file`` and ``${PW}`` interpolation. The rule only dropped real
base64 passwords (WGER_ADMIN_PASSWORD on B850).

All values below are fabricated test strings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pmoves.tools import _secrets_common as sc

PLUS_PADDED = "Ab+cd/ef12345678="

# >100 chars, '=' after position 50, then a base64-looking tail: the
# concatenated-fragment rule (kept) rejects this shape.
CONCATENATED = "fakekey" + "x" * 63 + "==" + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "local.env"
    path.write_text(text, encoding="utf-8")
    return path


def test_plus_with_base64_padding_survives_parse_env_file(tmp_path):
    path = _write(tmp_path, f"WGER_ADMIN_PASSWORD={PLUS_PADDED}\nOTHER=plain\n")
    values = sc.parse_env_file(path)
    assert values == {"WGER_ADMIN_PASSWORD": PLUS_PADDED, "OTHER": "plain"}


@pytest.mark.parametrize("value", [PLUS_PADDED, "a+b==", "+/+/+/+=", "x+y"])
def test_validator_accepts_plus_with_padding(value):
    assert sc.validate_secret_value("PW", value) == (True, None)


@pytest.mark.parametrize("value", ["line1\nline2", "line1\rline2", "-----BEGIN\nKEY-----"])
def test_validator_still_rejects_embedded_newlines(value):
    ok, why = sc.validate_secret_value("PEM", value)
    assert not ok and "newline" in why


def test_validator_still_rejects_concatenated_fragments():
    ok, why = sc.validate_secret_value("API_KEY", CONCATENATED)
    assert not ok and "concatenated" in why


def test_report_variant_names_dropped_keys_and_never_values(tmp_path, capsys):
    path = _write(
        tmp_path,
        f"GOOD={PLUS_PADDED}\nBROKEN_KEY={CONCATENATED}\nALSO_GOOD=1\n",
    )
    values, skipped = sc.parse_env_file_with_report(path)
    assert values == {"GOOD": PLUS_PADDED, "ALSO_GOOD": "1"}
    assert skipped == ["BROKEN_KEY"]
    err = capsys.readouterr().err
    assert "BROKEN_KEY" in err and CONCATENATED not in err


def test_report_variant_drops_and_reports_a_newline_value(tmp_path, monkeypatch):
    # A file reader cannot deliver an embedded newline to the validator:
    # str.splitlines() splits on it first. So the file carries a stand-in
    # character splitlines leaves alone (U+2063), and the REAL validator sees
    # it as '\n'. This proves the newline rejection reaches skipped_keys.
    sentinel = "⁣"
    path = _write(tmp_path, f"PEM_KEY=-----BEGIN{sentinel}KEY-----\nGOOD=ok\n")
    real = sc.validate_secret_value
    monkeypatch.setattr(
        sc, "validate_secret_value",
        lambda key, value: real(key, value.replace(sentinel, "\n")),
    )
    values, skipped = sc.parse_env_file_with_report(path)
    assert skipped == ["PEM_KEY"]
    assert values == {"GOOD": "ok"}


def test_parse_env_file_return_type_unchanged(tmp_path):
    path = _write(tmp_path, f"A=1\nB={CONCATENATED}\n")
    values = sc.parse_env_file(path)
    assert isinstance(values, dict)
    assert values == sc.parse_env_file_with_report(path)[0] == {"A": "1"}


def test_missing_file_reports_nothing(tmp_path):
    assert sc.parse_env_file_with_report(tmp_path / "absent.env") == ({}, [])
    assert sc.parse_env_file(tmp_path / "absent.env") == {}
