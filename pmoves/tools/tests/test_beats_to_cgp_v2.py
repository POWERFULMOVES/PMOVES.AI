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


def test_legacy_path_not_mislabeled_as_v2():
    """The legacy (--no-v2) builder emits point.proj as a 3-element RGB array,
    which is INVALID under cgp.v2.schema.json (point.proj must be a number).
    So a legacy packet must NOT claim spec 'chit.cgp.v0.2'. Relabel to v0.1."""
    from pmoves.tools.beats_to_cgp import group_to_cgp, select_builder
    groups, fps = _fixtures()

    pkt = group_to_cgp(groups[0], fps, coherence=0.7)
    pt = pkt["super_nodes"][0]["constellations"][0]["points"][0]
    # the legacy packet really does carry an array proj (the reason it's not v2)
    assert isinstance(pt["proj"], list) and len(pt["proj"]) == 3
    assert pkt["spec"] != "chit.cgp.v0.2", "array-proj packet must not claim v0.2"
    assert pkt["spec"] == "chit.cgp.v0.1"

    # the select_builder legacy wrapper must agree
    legacy = select_builder(v2=False)(groups, fps, coherence=0.7)
    assert legacy["spec"] != "chit.cgp.v0.2"
    assert legacy["spec"] == "chit.cgp.v0.1"


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


def test_render_dump_uses_v2_by_default(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    from pmoves.tools.beats_to_cgp import select_builder
    groups, fps = _fixtures()
    cgp = select_builder(v2=True)(groups, fps, coherence=0.7)
    assert cgp["spec"] == "chit.cgp.v0.2" and "hyperbolic" in cgp


def _poincare_point(cgp, point_id):
    return next(p for p in cgp["hyperbolic"]["points"] if p.get("id") == point_id)


def test_full_embedding_used_for_poincare(monkeypatch):
    """FIX 1: embeddings differing ONLY in dims 3..511 (identical dims 0..1)
    must yield DIFFERENT Poincaré points — proves the full vector is projected,
    not just the first two dims."""
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups = [{"group": "G", "count": 2, "tracks": ["a", "b"]}]
    base_head = [0.5, 0.5]
    emb_a = base_head + [0.0] * 510
    emb_b = base_head + [0.0, 0.0, 0.9] + [0.0] * 507   # differs only at dims >= 3
    assert emb_a[:2] == emb_b[:2] and emb_a != emb_b
    fps = {
        "a": {"name": "a", "tempo_bpm": 120, "spectral_centroid": 3000, "loudness_LRA": 6,
              "spectral_flatness": 0.1, "clap_embedding": emb_a, "duration_s": 100},
        "b": {"name": "b", "tempo_bpm": 120, "spectral_centroid": 3000, "loudness_LRA": 6,
              "spectral_flatness": 0.1, "clap_embedding": emb_b, "duration_s": 100},
    }
    from pmoves.tools.beats_to_cgp import build_cgp_v2, _stable_id
    cgp = build_cgp_v2(groups, fps, coherence=0.5)
    pa = _poincare_point(cgp, _stable_id("a"))
    pb = _poincare_point(cgp, _stable_id("b"))
    assert (pa["x"], pa["y"]) != (pb["x"], pb["y"])


def test_project_2d_deterministic():
    """FIX 1: same embedding -> same 2D point (fixed seed)."""
    from pmoves.tools.beats_to_cgp import _project_2d
    v = [0.1 * i for i in range(512)]
    import numpy as np
    assert np.allclose(_project_2d(v), _project_2d(list(v)))


def test_unsigned_packet_when_no_chit_env(monkeypatch):
    """FIX 2: with no CHIT key set, build_cgp_v2 must NOT raise and must emit a
    schema-valid unsigned packet (no sig) with meta.signed == False."""
    monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
    monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
    groups, fps = _fixtures()
    from pmoves.tools.beats_to_cgp import build_cgp_v2
    cgp = build_cgp_v2(groups, fps, coherence=0.6)
    jsonschema.validate(cgp, SCHEMA)
    assert cgp["meta"]["signed"] is False
    assert not cgp.get("sig")


def test_signature_reproducible(monkeypatch):
    """FIX 3: same input + fixed key -> identical sig.hmac across two builds
    (created_at lives outside the HMAC scope)."""
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    from pmoves.tools.beats_to_cgp import build_cgp_v2
    a = build_cgp_v2(groups, fps, coherence=0.8)
    b = build_cgp_v2(groups, fps, coherence=0.8)
    assert a["meta"]["signed"] is True
    assert a["sig"]["hmac"] == b["sig"]["hmac"]


def test_fingerprint_hash_emitted_in_points(monkeypatch):
    """FIX 4: each track point carries meta.fingerprint_hash matching
    fingerprint_hash(rec)."""
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-key")
    groups, fps = _fixtures()
    from pmoves.tools.beats_to_cgp import build_cgp_v2, fingerprint_hash, _stable_id
    cgp = build_cgp_v2(groups, fps, coherence=0.8)
    points = cgp["super_nodes"][0]["constellations"][0]["points"]
    by_id = {p["id"]: p for p in points}
    p_t0 = by_id[_stable_id("t0")]
    assert p_t0["meta"]["fingerprint_hash"] == fingerprint_hash(fps["t0"])
