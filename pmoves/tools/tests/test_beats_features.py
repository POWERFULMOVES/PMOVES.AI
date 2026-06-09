# pmoves/tools/tests/test_beats_features.py
import numpy as np
from pmoves.tools.analyze_beats import librosa_features_from_array


def test_librosa_features_shapes_and_keys():
    sr = 22050
    t = np.linspace(0, 5, sr * 5, endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * 220 * t).astype("float32")  # 220 Hz tone
    f = librosa_features_from_array(y, sr)
    assert {"tempo_bpm", "chroma", "mfcc", "spectral_contrast",
            "tonnetz", "onset_rate", "spectral_centroid"} <= set(f)
    assert len(f["chroma"]) == 12
    assert len(f["mfcc"]) == 20
    assert isinstance(f["tempo_bpm"], float)


def _all_finite(d):
    import math
    for v in d.values():
        if isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, (int, float)) and not math.isfinite(float(x)):
                    return False
        elif isinstance(v, (int, float)):
            if not math.isfinite(float(v)):
                return False
    return True


def test_librosa_features_silence_and_short_finite():
    sr = 22050
    # pure silence: beat_track may raise or yield NaN tempo
    f_sil = librosa_features_from_array(np.zeros(sr, dtype="float32"), sr)
    assert _all_finite(f_sil), f"silence produced non-finite values: {f_sil}"
    assert f_sil["tempo_bpm"] == 0.0
    # very short clip
    f_short = librosa_features_from_array(np.zeros(100, dtype="float32"), sr)
    assert _all_finite(f_short), f"short clip produced non-finite values: {f_short}"
    assert f_short["tempo_bpm"] == 0.0
    # non-finite input (NaN/inf can leak from upstream resampling/normalisation):
    # beat_track raises ParameterError on this; the function must NOT crash and
    # must coerce tempo to 0.0 with all-finite outputs.
    y_nan = np.full(sr, np.nan, dtype="float32")
    f_nan = librosa_features_from_array(y_nan, sr)
    assert _all_finite(f_nan), f"non-finite input produced non-finite values: {f_nan}"
    assert f_nan["tempo_bpm"] == 0.0


def test_librosa_features_deterministic():
    sr = 22050
    y = np.sin(np.linspace(0, 50, sr * 4)).astype("float32")
    a = librosa_features_from_array(y, sr)
    b = librosa_features_from_array(y, sr)
    assert a == b


from pmoves.tools.analyze_beats import cluster_on_embeddings


def test_cluster_on_embeddings_separates_two_blobs():
    import numpy as np
    rng = np.random.default_rng(0)
    a = [{"clap_embedding": (np.r_[rng.normal(0, 0.01, 512)] + 1.0).tolist()} for _ in range(6)]
    b = [{"clap_embedding": (np.r_[rng.normal(0, 0.01, 512)] - 1.0).tolist()} for _ in range(6)]
    records = a + b
    labels, sil = cluster_on_embeddings(records, n_groups=2)
    assert len(labels) == 12
    assert sil > 0.5                                   # clean separation
    assert len(set(labels[:6])) == 1                   # first blob one cluster
    assert labels[0] != labels[6]                      # blobs differ
