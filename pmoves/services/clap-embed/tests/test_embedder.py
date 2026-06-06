import numpy as np
import pytest
from embedder import Embedder, window_audio


def test_window_audio_fixed_nonoverlapping():
    sr = 48000
    audio = np.ones(sr * 25, dtype="float32")  # 25 s
    wins = window_audio(audio, sr, clip_seconds=10, hop_seconds=10)
    assert len(wins) == 3                      # 0-10, 10-20, 20-25 (padded)
    assert all(w.shape[0] == sr * 10 for w in wins)


def test_window_audio_short_is_padded_to_one_window():
    sr = 48000
    audio = np.ones(sr * 3, dtype="float32")
    wins = window_audio(audio, sr, clip_seconds=10, hop_seconds=10)
    assert len(wins) == 1 and wins[0].shape[0] == sr * 10


class _FakeModel:
    """Returns a deterministic embedding derived from the window mean."""
    def embed_windows(self, windows):
        return np.stack([np.full(512, float(np.mean(w)), dtype="float32") for w in windows])


def test_embed_is_mean_pooled_and_l2_normalised():
    emb = Embedder(model=_FakeModel(), sr=48000, clip_seconds=10, hop_seconds=10)
    audio = np.ones(48000 * 12, dtype="float32")
    vec = emb.embed_audio(audio, 48000)
    assert len(vec) == 512
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-6)


def test_embed_is_deterministic():
    emb = Embedder(model=_FakeModel(), sr=48000, clip_seconds=10, hop_seconds=10)
    audio = (np.sin(np.linspace(0, 100, 48000 * 11))).astype("float32")
    v1 = emb.embed_audio(audio, 48000)
    v2 = emb.embed_audio(audio, 48000)
    assert v1 == v2  # list equality — bit-identical
