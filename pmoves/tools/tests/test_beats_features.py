# pmoves/tools/tests/test_beats_features.py
"""Feature-extraction tests for the librosa-backed beats analyser.

These SKIP rather than fail when librosa is absent, matching the contract the
source already sets: `analyze_beats.librosa_features_from_array` imports librosa
lazily *inside the function* (analyze_beats.py:128) precisely so the module is
usable without it. A test that hard-fails on a dependency the production code
treats as optional is asserting a stricter contract than the code has.

librosa is deliberately not in .github/requirements-tests.txt. It pulls numba,
scipy, soundfile and audioread -- a large install on every run of a 279-file
suite, to exercise three tests. If the audio lane later needs CI coverage, add
it there and this importorskip becomes a no-op; nothing else has to change.

Why this surfaced when it did: before #2630, `pmoves/tests [1]` timed out and
its whole chunk was discarded unmeasured. With per-file isolation these results
became visible for the first time -- they are not new breakage, they are newly
observed, which is exactly what that change was for.
"""
import pytest

pytest.importorskip(
    "librosa",
    reason="librosa is an optional heavy dependency; analyze_beats imports it lazily",
)

import numpy as np  # noqa: E402
from pmoves.tools.analyze_beats import librosa_features_from_array  # noqa: E402


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


def test_cluster_on_embeddings_partial_embeddings_no_nan_crash():
    """Some records have a real 512-d embedding, others are padded/missing.
    Padding leaves ~509 zero-variance columns -> StandardScaler /0 -> NaN ->
    KMeans 'array contains NaN' crash. Must return finite labels instead."""
    import math
    # Some records have a real 512-d embedding; some are missing it and fall
    # back to a padded acoustic vector. When an acoustic feature is itself NaN
    # (degenerate audio upstream), the unsanitised fallback vector carries NaN
    # into StandardScaler -> KMeans ValueError("Input X contains NaN.").
    records = [
        {"clap_embedding": [0.9, 0.1] + [0.0] * 510},
        {"clap_embedding": [0.1, 0.9] + [0.0] * 510},
        {"tempo_bpm": float("nan"), "spectral_centroid": 3000.0, "spectral_flatness": 0.2},
        {"tempo_bpm": 120.0, "spectral_centroid": float("nan"), "spectral_flatness": 0.2},
    ]
    labels, sil = cluster_on_embeddings(records, n_groups=2)
    assert len(labels) == len(records)
    assert all(isinstance(l, int) for l in labels)
    assert math.isfinite(sil)


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
