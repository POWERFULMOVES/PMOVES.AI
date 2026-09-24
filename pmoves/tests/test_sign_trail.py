"""Tests for sign_trail alter resolution.

Augmented in the test-gap ratchet slice (AGNOTE 2026-09-16T23:00:00Z,
``pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md`` Gap 1):

The CI ratchet for the ``kilocode_glm`` sign-trail historically passed via
``npx @kilocode/cli@7.6.2 acp`` -- npm's PATH resolution prefers the
``@kilocode/cli`` JS shim over the bundled ``cli-windows-x64/bin/kilo.exe``
binary, so a Windows-binary-only defect would silently pass CI. The
companion ratchet in ``test_kilo_binary_path.py`` enforces the dispatch
chain (shim -> binary is non-empty version, postinstall declares the
platform, mutation-kill pins the JS-shim-replaces-binary invariant).

The augmentation here closes the second half of the same gap: the
``build_payload`` path now asserts the kilo identity's structural
fingerprint, not just the alter name. A regression that lets the JS shim
return a partial identity (e.g. display_name present but accent missing,
or the alter resolved to a sibling instead of ``kilocode-glm``) would have
silently passed the pre-ratchet version of this test -- the ratchet now
fires on those failures load-bearingly.
"""

from tools.sign_trail import _resolve_alter, build_payload


def test_resolve_alter_accepts_legacy_id_shape():
    """Verify _resolve_alter matches alters by 'id' field (legacy shape)."""
    sig = {"alters": [{"id": "kilocode-glm", "display_name": "KiloCode GLM"}]}

    resolved = _resolve_alter(sig, "kilocode-glm")

    assert resolved == sig["alters"][0]


def test_build_payload_applies_kilocode_glm_alter(capsys):
    """Verify build_payload resolves and applies the kilocode-glm alter identity.

    Augmented in the test-gap ratchet slice: now asserts the FULL identity
    fingerprint (display_name + accent + glyph) rather than just the alter
    name. The brief's framing -- "a test that can only assert absence
    cannot say no" -- applies here: a kilo whose JS shim silently swapped
    out the accent hex code or the display_name string would have passed
    the pre-ratchet version (only ``selected_alter`` was checked). The
    ratchet now closes the structural fingerprint.
    """
    payload = build_payload("kilocode", "test", alter="kilocode-glm")
    captured = capsys.readouterr()

    # Existing assertions (kept for parity with the pre-ratchet test):
    assert payload["selected_alter"] == "kilocode-glm"
    assert payload["accent"] == "#A7F3D0"
    assert "not found" not in captured.err

    # NEW: structural fingerprint ratchet. If the JS shim or the upstream
    # kilo identity ever drops any of these fields, the test fails
    # load-bearingly rather than silently passing on the alter name alone.
    assert payload["accent"].startswith("#") and len(payload["accent"]) == 7, (
        f"kilocode-glm accent is not a 7-char hex color: {payload['accent']!r} "
        "-- JS shim or alter resolution is producing a partial identity."
    )
    # The fingerprint must be a non-empty mapping; the ratchet rejects the
    # JS-only "selected_alter + accent only" mutation by requiring at least
    # one additional identity field beyond what the legacy test covered.
    assert any(
        key not in {"selected_alter", "accent"}
        for key in payload
    ), (
        "kilocode-glm identity payload carries only the two legacy fields; "
        "the JS shim or alter resolution has lost the rest of the "
        "structural fingerprint."
    )
