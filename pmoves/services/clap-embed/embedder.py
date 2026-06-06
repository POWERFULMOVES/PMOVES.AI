"""Deterministic CLAP embedder. The torch/transformers model is injected so the
pure windowing + pooling logic is testable without any model download."""
from __future__ import annotations

from typing import List, Protocol

import numpy as np


def window_audio(audio: np.ndarray, sr: int, clip_seconds: int, hop_seconds: int) -> List[np.ndarray]:
    """Split mono audio into fixed-length non-overlapping windows (last is zero-padded)."""
    clip = clip_seconds * sr
    hop = hop_seconds * sr
    audio = np.asarray(audio, dtype="float32").reshape(-1)
    if audio.shape[0] <= clip:
        out = np.zeros(clip, dtype="float32")
        out[: audio.shape[0]] = audio
        return [out]
    windows: List[np.ndarray] = []
    for start in range(0, audio.shape[0], hop):
        seg = audio[start : start + clip]
        if seg.shape[0] == 0:
            break
        if seg.shape[0] < clip:
            padded = np.zeros(clip, dtype="float32")
            padded[: seg.shape[0]] = seg
            seg = padded
        windows.append(seg)
    return windows


class _Model(Protocol):
    def embed_windows(self, windows: List[np.ndarray]) -> np.ndarray: ...


class Embedder:
    def __init__(self, model: _Model, sr: int, clip_seconds: int, hop_seconds: int):
        self.model = model
        self.sr = sr
        self.clip_seconds = clip_seconds
        self.hop_seconds = hop_seconds

    def embed_audio(self, audio: np.ndarray, sr: int) -> List[float]:
        if sr != self.sr:
            import librosa
            audio = librosa.resample(np.asarray(audio, dtype="float32"), orig_sr=sr, target_sr=self.sr)
        windows = window_audio(audio, self.sr, self.clip_seconds, self.hop_seconds)
        per_window = self.model.embed_windows(windows)        # (n, 512)
        pooled = per_window.mean(axis=0)                       # mean pool
        norm = float(np.linalg.norm(pooled))
        if norm > 0:
            pooled = pooled / norm
        return [round(float(x), 7) for x in pooled]           # rounded -> bit-stable JSON
