# pmoves/tools/tests/test_reproducibility.py
from pmoves.tools.beats_to_cgp import fingerprint_hash


def test_same_features_same_hash():
    rec = {"name": "t", "tempo_bpm": 128.0, "spectral_centroid": 3000.0,
           "clap_embedding": [0.1, 0.2, 0.3], "mfcc": [1.0, 2.0]}
    assert fingerprint_hash(rec) == fingerprint_hash(dict(rec))


def test_different_embedding_different_hash():
    a = {"name": "t", "clap_embedding": [0.1, 0.2]}
    b = {"name": "t", "clap_embedding": [0.1, 0.3]}
    assert fingerprint_hash(a) != fingerprint_hash(b)


def test_hash_ignores_volatile_fields():
    a = {"name": "t", "clap_embedding": [0.1], "ts": 1.0, "sense_mode": "glaze"}
    b = {"name": "t", "clap_embedding": [0.1], "ts": 999.0, "sense_mode": "gaze"}
    assert fingerprint_hash(a) == fingerprint_hash(b)
