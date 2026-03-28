"""Tests for sign_trail alter resolution."""

from tools.sign_trail import _resolve_alter, build_payload


def test_resolve_alter_accepts_legacy_id_shape():
    sig = {"alters": [{"id": "kilocode-glm", "display_name": "KiloCode GLM"}]}

    resolved = _resolve_alter(sig, "kilocode-glm")

    assert resolved == sig["alters"][0]


def test_build_payload_applies_kilocode_glm_alter(capsys):
    payload = build_payload("kilocode", "test", alter="kilocode-glm")
    captured = capsys.readouterr()

    assert payload["selected_alter"] == "kilocode-glm"
    assert payload["accent"] == "#A7F3D0"
    assert "not found" not in captured.err
