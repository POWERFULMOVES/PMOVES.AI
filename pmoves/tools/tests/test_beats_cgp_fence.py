# pmoves/tools/tests/test_beats_cgp_fence.py
"""Tests for the CGP v2 schema-validation fence (WS-A spec §8).

A real v2 packet must pass; a malformed packet must be rejected with
``typer.Exit`` so it never reaches NATS.
"""
import pytest
import typer

from pmoves.tools.beats_to_cgp import build_cgp_v2, validate_cgp_v2


def _fixtures():
    groups = [
        {"group": "Allegro_warm_Bright", "count": 2, "tracks": ["t0", "t1"]},
        {"group": "Largo_bass_Deep", "count": 1, "tracks": ["t2"]},
    ]
    fps = {
        "t0": {"name": "t0", "tempo_bpm": 128, "spectral_centroid": 3000, "loudness_LRA": 6,
               "spectral_flatness": 0.1, "clap_embedding": [0.9, 0.1] + [0.0] * 510, "duration_s": 200},
        "t1": {"name": "t1", "tempo_bpm": 126, "spectral_centroid": 3200, "loudness_LRA": 7,
               "spectral_flatness": 0.12, "clap_embedding": [0.8, 0.2] + [0.0] * 510, "duration_s": 190},
        "t2": {"name": "t2", "tempo_bpm": 60, "spectral_centroid": 800, "loudness_LRA": 12,
               "spectral_flatness": 0.4, "clap_embedding": [0.1, 0.9] + [0.0] * 510, "duration_s": 240},
    }
    return groups, fps


def test_fence_accepts_valid_v2_packet(monkeypatch):
    """A well-formed build_cgp_v2 packet passes the fence without raising."""
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    # Returns None and does not raise.
    assert validate_cgp_v2(cgp) is None


def test_fence_rejects_malformed_packet():
    """A packet missing required v2 fields is rejected with typer.Exit (no publish)."""
    malformed = {"spec": "chit.cgp.v0.2"}  # missing hyperbolic/attribution/sig/...
    with pytest.raises(typer.Exit):
        validate_cgp_v2(malformed)


def test_fence_rejects_v2_packet_missing_extension_blocks(monkeypatch):
    """A v0.2 packet WITH super_nodes but no hyperbolic/attribution is rejected.

    This is the gap the shared schema cannot cover: ``cgp.v2.schema.json`` also
    validates v0.1 packets, so ``super_nodes`` alone satisfies its top-level
    ``required`` list. Without the explicit extension-block check, a v2 packet
    stripped of its advertised hyperbolic/attribution payload would pass the
    fence and publish.
    """
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    cgp.pop("hyperbolic", None)
    cgp.pop("attribution", None)
    # super_nodes still present → passes JSON-Schema; must be caught by the block check.
    with pytest.raises(typer.Exit) as exc:
        validate_cgp_v2(cgp)
    assert exc.value.exit_code == 1  # fail-fast contract: refuse-to-publish exits non-zero
