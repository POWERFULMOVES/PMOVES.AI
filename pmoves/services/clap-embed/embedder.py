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
    def embed_text(self, texts) -> np.ndarray: ...


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

    def embed_text(self, texts):
        """Delegate text embedding to the underlying model (real CLAP path)."""
        return self.model.embed_text(texts)


class ClapHFModel:
    """laion CLAP loaded via transformers. Deterministic: eval(), no grad, fp32."""

    def __init__(self, model_id: str, revision: str = "main", device: str = "cpu", sr: int = 48000):
        import torch
        from transformers import ClapModel, ClapProcessor

        torch.manual_seed(0)
        self._torch = torch
        self.device = device
        self.sr = sr
        self.processor = ClapProcessor.from_pretrained(model_id, revision=revision)
        self.model = ClapModel.from_pretrained(model_id, revision=revision, torch_dtype=torch.float32)
        self.model.eval().to(device)

    def embed_windows(self, windows):
        import numpy as np
        torch = self._torch
        with torch.no_grad():
            inputs = self.processor(audios=[w for w in windows], sampling_rate=self.sr, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_audio_features(**inputs)   # (n, 512)
            return feats.detach().cpu().float().numpy()

    def embed_text(self, texts):
        import numpy as np
        torch = self._torch
        with torch.no_grad():
            inputs = self.processor(text=list(texts), return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self.model.get_text_features(**inputs)
            return feats.detach().cpu().float().numpy()
