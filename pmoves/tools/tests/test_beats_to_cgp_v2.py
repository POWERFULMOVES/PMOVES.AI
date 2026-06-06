# pmoves/tools/tests/test_beats_to_cgp_v2.py
import json
import os
from pathlib import Path

import jsonschema
from pmoves.tools.beats_to_cgp import build_cgp_v2

SCHEMA = json.loads(Path("pmoves/contracts/schemas/geometry/cgp.v2.schema.json").read_text(encoding="utf-8"))


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


def test_cgp_v2_validates_against_schema(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    jsonschema.validate(cgp, SCHEMA)
    assert cgp["spec"] == "chit.cgp.v0.2"


def test_cgp_v2_has_hyperbolic_attribution_sig(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    assert cgp["hyperbolic"]["space"] == "poincare_disk"
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in cgp["hyperbolic"]["points"])
    assert abs(sum(c["weight"] for c in cgp["attribution"]["contributors"]) - 1.0) < 1e-6
    assert cgp["sig"]["alg"] == "HMAC-SHA256" and cgp["sig"]["hmac"]


def test_cgp_v2_signature_verifies(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    from pmoves.tools.chit_security import verify_cgp
    groups, fps = _fixtures()
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    assert verify_cgp(cgp, passphrase="test-key") is True
