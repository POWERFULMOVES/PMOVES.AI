"""Runtime HRM sidecar helpers promoted from the Colab prototype.

This module surfaces the transformer-sidecar components so that runtime
services can optionally attach an ACT-style halting loop to their decoders.
It intentionally keeps the defaults lightweight (CPU-friendly and with an
identity refinement path) so services can enable the behaviour without a
full training pipeline.
"""
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

try:  # pragma: no cover - exercised in integration tests when available
    import torch
    from torch import nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without torch
    torch = None  # type: ignore
    nn = None  # type: ignore
    F = None  # type: ignore

__all__ = [
    "is_torch_available",
    "HrmSidecarConfig",
    "TinyTransformer",
    "TokenHead",
    "LModule",
    "SidecarHRM",
    "ConstantHaltHead",
    "AsciiCodec",
    "create_identity_sidecar",
    "HrmDecoderController",
]

logger = logging.getLogger(__name__)


def is_torch_available() -> bool:
    """Return ``True`` when PyTorch is importable."""

    return torch is not None


def _require_torch() -> None:
    if not is_torch_available():  # pragma: no cover - simple guard
        raise RuntimeError("PyTorch is required for HRM sidecar support")


if is_torch_available():  # pragma: no branch - definition gate

    class TinyTransformer(nn.Module):
        """Minimal transformer encoder used by the original Colab prototype."""

        def __init__(
            self,
            d_model: int = 128,
            nhead: int = 4,
            num_layers: int = 2,
            dim_feedforward: int = 512,
            dropout: float = 0.1,
            vocab_size: int = 32,
        ) -> None:
            super().__init__()
            self.emb = nn.Embedding(vocab_size, d_model)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.pos = nn.Parameter(torch.randn(1, 32, d_model) * 0.01)
            self.d_model = d_model

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            bsz, seq = x.shape
            h = self.emb(x) + self.pos[:, :seq, :]
            return self.encoder(h)

    class TokenHead(nn.Module):
        def __init__(self, d_model: int = 128, vocab_size: int = 32) -> None:
            super().__init__()
            self.ln = nn.LayerNorm(d_model)
            self.proj = nn.Linear(d_model, vocab_size)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            return self.proj(self.ln(h))

    class LModule(nn.Module):
        def __init__(
            self,
            d_model: int = 128,
            nhead: int = 4,
            dim_feedforward: int = 512,
            dropout: float = 0.1,
        ) -> None:
            super().__init__()
            layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
            )
            self.block = nn.TransformerEncoder(layer, num_layers=1)
            self.ln = nn.LayerNorm(d_model)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            return self.ln(self.block(h))

    class ConstantHaltHead(nn.Module):
        """Simple head that emits a constant halt logit for every position."""

        def __init__(self, logit: float) -> None:
            super().__init__()
            value = torch.tensor(float(logit), dtype=torch.float32)
            self.register_buffer("logit", value)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            bsz, seq, _ = h.shape
            return self.logit.expand(bsz, seq, 1)

    class _IdentityEncoder(nn.Module):
        """Embedding encoder that simply returns one-hot vectors for tokens."""

        def __init__(self, vocab_size: int) -> None:
            super().__init__()
            self.emb = nn.Embedding(vocab_size, vocab_size)
            with torch.no_grad():
                self.emb.weight.copy_(torch.eye(vocab_size))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.emb(x)

    class SidecarHRM(nn.Module):
        """Transformer sidecar with ACT-style halting."""

        def __init__(
            self,
            base_encoder: nn.Module,
            token_head: nn.Module,
            *,
            d_model: int = 128,
            Mmax: int = 6,
            Mmin: int = 2,
            l_module: Optional[nn.Module] = None,
            q_head: Optional[nn.Module] = None,
        ) -> None:
            super().__init__()
            self.base = base_encoder
            self.head = token_head
            self.l_module = l_module or LModule(d_model=d_model)
            self.q_head = q_head or nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, 1))
            self.Mmax = int(Mmax)
            self.Mmin = max(1, int(Mmin))

        def forward_once(
            self,
            x: torch.Tensor,
            *,
            h: Optional[torch.Tensor] = None,
        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            if h is None:
                h = self.base(x)
            h2 = h + self.l_module(h)
            logits = self.head(h2)
            q = self.q_head(h2).mean(dim=1)
            return h2, logits, q.squeeze(1)

        @torch.no_grad()
        def infer(
            self,
            x: torch.Tensor,
            *,
            threshold: float = 0.5,
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            self.eval()
            device = x.device
            done = torch.zeros(x.size(0), dtype=torch.bool, device=device)
            steps_taken = torch.zeros(x.size(0), dtype=torch.long, device=device)
            h: Optional[torch.Tensor] = None
            y_best: Optional[torch.Tensor] = None

            for step in range(1, self.Mmax + 1):
                h, logits, q = self.forward_once(x, h=h)
                y_hat = logits.argmax(dim=-1)
                will_halt = (torch.sigmoid(q) > threshold) & (step >= self.Mmin)
                now_done = (~done) & will_halt
                steps_taken[now_done] = step
                done = done | will_halt
                if y_best is None:
                    y_best = y_hat.clone()
                y_best[~done] = y_hat[~done]
                if done.all():
                    break

            if y_best is None:
                y_best = y_hat
            steps_taken[~done] = self.Mmax
            return y_best, steps_taken

        def training_step(
            self,
            x: torch.Tensor,
            y: torch.Tensor,
            *,
            ce_weight: float = 1.0,
            act_weight: float = 0.1,
        ) -> torch.Tensor:
            h: Optional[torch.Tensor] = None
            total_ce = 0.0
            total_act = 0.0
            for step in range(1, self.Mmax + 1):
                if h is not None:
                    h = h.detach()
                h, logits, q = self.forward_once(x, h=h)
                ce = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
                y_hat = logits.argmax(dim=-1)
                correct = (y_hat == y).all(dim=1).float()
                if step >= self.Mmin:
                    target_halt = correct
                else:
                    target_halt = torch.zeros_like(correct)
                act = F.binary_cross_entropy_with_logits(q, target_halt)
                total_ce += ce
                total_act += act
            loss = ce_weight * (total_ce / self.Mmax) + act_weight * (total_act / self.Mmax)
            return loss

else:  # pragma: no cover - exercised in environments without torch

    class TinyTransformer:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()

    class TokenHead:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()

    class LModule:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()

    class ConstantHaltHead:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()

    class SidecarHRM:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()


@dataclass
class HrmSidecarConfig:
    vocab_size: int
    d_model: int = 128
    nhead: int = 4
    dim_feedforward: int = 256
    dropout: float = 0.1
    mmax: int = 4
    mmin: int = 1
    halt_threshold: float = 0.5


class AsciiCodec:
    """Simple codec that maps ASCII characters into token ids."""

    def __init__(self, vocab_size: int = 128) -> None:
        self.vocab_size = max(32, int(vocab_size))

    def encode(self, text: str) -> List[int]:
        if not text:
            return []
        limit = self.vocab_size - 1
        return [min(ord(ch), limit) for ch in text]

    def decode(self, tokens: List[int], *, original_length: Optional[int] = None) -> str:
        if original_length is not None:
            tokens = tokens[: original_length]
        chars = []
        for tok in tokens:
            tok = int(tok)
            tok = max(0, min(self.vocab_size - 1, tok))
            chars.append(chr(tok))
        return "".join(chars)


def _logit(p: float) -> float:
    eps = 1e-6
    p = max(eps, min(1 - eps, p))
    return math.log(p / (1.0 - p))


def create_identity_sidecar(
    config: HrmSidecarConfig,
    *,
    device: Optional["torch.device"] = None,
) -> "SidecarHRM":
    """Construct a sidecar that leaves token predictions unchanged.

    The model uses one-hot embeddings and a constant halting head so that
    inference is deterministic. This is primarily used for integration tests
    and to provide a safe runtime default until a trained sidecar is wired in.
    """

    _require_torch()
    assert torch is not None and nn is not None  # for type checkers

    device = device or torch.device("cpu")
    vocab = int(config.vocab_size)
    d_model = int(config.d_model or vocab)
    if d_model != vocab:
        d_model = vocab
    encoder = _IdentityEncoder(vocab).to(device)
    head = TokenHead(d_model=vocab, vocab_size=vocab).to(device)
    with torch.no_grad():
        if isinstance(head.ln, nn.LayerNorm):
            head.ln.weight.fill_(1.0)
            head.ln.bias.zero_()
        head.proj.weight.copy_(torch.eye(vocab))
        head.proj.bias.zero_()
    halt_logit = _logit(config.halt_threshold)
    q_head = ConstantHaltHead(halt_logit).to(device)
    sidecar = SidecarHRM(
        encoder,
        head,
        d_model=vocab,
        Mmax=config.mmax,
        Mmin=config.mmin,
        l_module=nn.Identity(),
        q_head=q_head,
    )
    return sidecar.to(device)


@dataclass
class _CachedState:
    signature: Tuple[Any, ...]
    enabled: bool
    reason: str
    threshold: float
    mmax: int
    mmin: int
    sidecar: Optional["SidecarHRM"]


class HrmDecoderController:
    """Manage optional HRM refinement based on EvoSwarm decoder packs."""

    def __init__(
        self,
        pack_fetcher: Callable[[str, str], Optional[Dict[str, Any]]],
        *,
        codec: Optional[AsciiCodec] = None,
        modality: str = "text",
        device: Optional["torch.device"] = None,
    ) -> None:
        self._pack_fetcher = pack_fetcher
        self._codec = codec or AsciiCodec()
        self._modality = modality
        self._device = device
        self._lock = threading.RLock()
        self._cache: Dict[Tuple[str, str], _CachedState] = {}

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _ensure_state(self, namespace: str, modality: Optional[str] = None) -> _CachedState:
        key = (namespace, modality or self._modality)
        with self._lock:
            cached = self._cache.get(key)
            pack = self._pack_fetcher(namespace, key[1]) if self._pack_fetcher else None
            if pack is None:
                state = _CachedState((None,), False, "decoder pack unavailable", 0.5, 0, 0, None)
                self._cache[key] = state
                return state

            params = (pack.get("params") or {}) if isinstance(pack, dict) else {}
            threshold = params.get("hrm_halt_thresh")
            mmax = params.get("hrm_mmax")
            mmin = params.get("hrm_mmin")
            pack_id = pack.get("id") or pack.get("pack_id") or pack.get("version")
            signature = (pack_id, threshold, mmax, mmin)
            if cached and cached.signature == signature:
                return cached

            if threshold is None or mmax is None:
                state = _CachedState(signature, False, "hrm parameters missing", 0.5, 0, 0, None)
                self._cache[key] = state
                return state

            try:
                thr = float(threshold)
            except (TypeError, ValueError):
                thr = 0.5
            try:
                mm = max(1, int(mmax))
            except (TypeError, ValueError):
                mm = 1
            try:
                mn = max(1, int(mmin)) if mmin is not None else 1
            except (TypeError, ValueError):
                mn = 1
            if not is_torch_available():
                state = _CachedState(signature, False, "torch not available", thr, mm, mn, None)
                self._cache[key] = state
                return state

            try:
                config = HrmSidecarConfig(
                    vocab_size=self._codec.vocab_size,
                    d_model=self._codec.vocab_size,
                    mmax=mm,
                    mmin=mn,
                    halt_threshold=thr,
                )
                sidecar = create_identity_sidecar(config, device=self._device)
                state = _CachedState(signature, True, "loaded", thr, mm, mn, sidecar)
            except Exception as exc:  # pragma: no cover - rare failure path
                logger.exception("HRM sidecar initialisation failed")
                state = _CachedState(signature, False, f"hrm init failed: {exc}", thr, mm, mn, None)
            self._cache[key] = state
            return state

    def status(self, namespace: str, modality: Optional[str] = None) -> Dict[str, Any]:
        state = self._ensure_state(namespace, modality)
        return {
            "enabled": bool(state.enabled and state.sidecar is not None),
            "reason": state.reason,
            "threshold": state.threshold,
            "mmax": state.mmax,
            "mmin": state.mmin,
            "steps": 0,
        }

    def maybe_refine(
        self,
        text: str,
        *,
        namespace: str,
        modality: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        state = self._ensure_state(namespace, modality)
        info = {
            "enabled": bool(state.enabled and state.sidecar is not None),
            "reason": state.reason,
            "threshold": state.threshold,
            "mmax": state.mmax,
            "mmin": state.mmin,
            "steps": 0,
        }
        if not info["enabled"] or not text:
            return text, info

        tokens = self._codec.encode(text)
        if not tokens:
            info["reason"] = "empty token stream"
            return text, info

        _require_torch()
        assert torch is not None
        device = self._device or torch.device("cpu")
        sidecar = state.sidecar
        if sidecar is None:
            return text, info
        try:
            input_ids = torch.tensor([tokens], dtype=torch.long, device=device)
            preds, steps = sidecar.infer(input_ids, threshold=state.threshold)
            decoded = self._codec.decode(preds[0].detach().cpu().tolist(), original_length=len(tokens))
            info["steps"] = int(steps[0].detach().cpu().item()) if torch.is_tensor(steps) else int(steps)
            info["reason"] = "applied"
            return decoded, info
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("HRM refinement failed")
            info["enabled"] = False
            info["reason"] = f"hrm runtime error: {exc}"
            info["steps"] = 0
            return text, info
