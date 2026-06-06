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


def test_librosa_features_deterministic():
    sr = 22050
    y = np.sin(np.linspace(0, 50, sr * 4)).astype("float32")
    a = librosa_features_from_array(y, sr)
    b = librosa_features_from_array(y, sr)
    assert a == b
