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
    """Raises a RuntimeError if PyTorch is not available."""
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
            """Initializes the TinyTransformer.

            Args:
                d_model: The number of expected features in the input.
                nhead: The number of heads in the multiheadattention models.
                num_layers: The number of sub-encoder-layers in the encoder.
                dim_feedforward: The dimension of the feedforward network model.
                dropout: The dropout value.
                vocab_size: The size of the vocabulary.
            """
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
            """Forward pass for the TinyTransformer.

            Args:
                x: The input tensor of token IDs.

            Returns:
                The encoded output tensor.
            """
            bsz, seq = x.shape
            h = self.emb(x) + self.pos[:, :seq, :]
            return self.encoder(h)

    class TokenHead(nn.Module):
        """A head for projecting transformer outputs to token logits."""
        def __init__(self, d_model: int = 128, vocab_size: int = 32) -> None:
            """Initializes the TokenHead.

            Args:
                d_model: The number of features in the input tensor.
                vocab_size: The size of the vocabulary for the output projection.
            """
            super().__init__()
            self.ln = nn.LayerNorm(d_model)
            self.proj = nn.Linear(d_model, vocab_size)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            """Forward pass for the TokenHead.

            Args:
                h: The input tensor from the transformer.

            Returns:
                The output logits tensor.
            """
            return self.proj(self.ln(h))

    class LModule(nn.Module):
        """A single-layer transformer block for refinement steps in the SidecarHRM."""
        def __init__(
            self,
            d_model: int = 128,
            nhead: int = 4,
            dim_feedforward: int = 512,
            dropout: float = 0.1,
        ) -> None:
            """Initializes the LModule.

            Args:
                d_model: The number of features in the input.
                nhead: The number of heads in the multiheadattention models.
                dim_feedforward: The dimension of the feedforward network model.
                dropout: The dropout value.
            """
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
            """Forward pass for the LModule.

            Args:
                h: The input tensor.

            Returns:
                The processed output tensor.
            """
            return self.ln(self.block(h))

    class ConstantHaltHead(nn.Module):
        """Simple head that emits a constant halt logit for every position."""

        def __init__(self, logit: float) -> None:
            """Initializes the ConstantHaltHead.

            Args:
                logit: The constant logit value to be emitted.
            """
            super().__init__()
            value = torch.tensor(float(logit), dtype=torch.float32)
            self.register_buffer("logit", value)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            """Forward pass for the ConstantHaltHead.

            Args:
                h: The input tensor (shape is used to expand the constant logit).

            Returns:
                A tensor of shape (batch_size, seq_len, 1) filled with the constant logit.
            """
            bsz, seq, _ = h.shape
            return self.logit.expand(bsz, seq, 1)

    class _IdentityEncoder(nn.Module):
        """Embedding encoder that simply returns one-hot vectors for tokens."""

        def __init__(self, vocab_size: int) -> None:
            """Initializes the _IdentityEncoder.

            Args:
                vocab_size: The size of the vocabulary. The embedding dimension
                    will be equal to this.
            """
            super().__init__()
            self.emb = nn.Embedding(vocab_size, vocab_size)
            with torch.no_grad():
                self.emb.weight.copy_(torch.eye(vocab_size))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass for _IdentityEncoder.

            Args:
                x: Input tensor of token IDs.

            Returns:
                A tensor of one-hot encoded vectors.
            """
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
            """Initializes the SidecarHRM.

            Args:
                base_encoder: The initial encoder module (e.g., TinyTransformer).
                token_head: The module for projecting to token logits.
                d_model: The number of features in the model.
                Mmax: The maximum number of refinement steps.
                Mmin: The minimum number of refinement steps before halting is allowed.
                l_module: The refinement module (L-module). If None, a default
                    LModule is created.
                q_head: The halting head (Q-head). If None, a default linear
                    head is created.
            """
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
            """Performs a single refinement step.

            Args:
                x: The input tensor of token IDs.
                h: The hidden state from the previous step. If None, the base
                    encoder is used to create the initial hidden state.

            Returns:
                A tuple containing:
                - The updated hidden state.
                - The output logits.
                - The halting logits.
            """
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
            """Performs inference with adaptive computation time (halting).

            Args:
                x: The input tensor of token IDs.
                threshold: The probability threshold for halting.

            Returns:
                A tuple containing:
                - The final predicted token IDs.
                - The number of steps taken for each item in the batch.
            """
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
            """Performs a single training step.

            Calculates a combined loss including cross-entropy for token prediction
            and adaptive computation time (ACT) loss for halting.

            Args:
                x: The input tensor of token IDs.
                y: The target tensor of token IDs.
                ce_weight: The weight for the cross-entropy loss component.
                act_weight: The weight for the ACT loss component.

            Returns:
                The combined loss tensor.
            """
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
    """Configuration for an HRM sidecar.

    Attributes:
        vocab_size: The size of the vocabulary.
        d_model: The number of features in the model.
        nhead: The number of attention heads.
        dim_feedforward: The dimension of the feedforward network.
        dropout: The dropout rate.
        mmax: The maximum number of refinement steps.
        mmin: The minimum number of refinement steps before halting.
        halt_threshold: The probability threshold for halting.
    """
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
        """Initializes the AsciiCodec.

        Args:
            vocab_size: The size of the vocabulary. Tokens will be clamped to
                this size.
        """
        self.vocab_size = max(32, int(vocab_size))

    def encode(self, text: str) -> List[int]:
        """Encodes a string into a list of token IDs.

        Args:
            text: The input string.

        Returns:
            A list of integer token IDs.
        """
        if not text:
            return []
        limit = self.vocab_size - 1
        return [min(ord(ch), limit) for ch in text]

    def decode(self, tokens: List[int], *, original_length: Optional[int] = None) -> str:
        """Decodes a list of token IDs into a string.

        Args:
            tokens: The list of token IDs.
            original_length: If provided, the decoded string will be truncated
                to this length.

        Returns:
            The decoded string.
        """
        if original_length is not None:
            tokens = tokens[: original_length]
        chars = []
        for tok in tokens:
            tok = int(tok)
            tok = max(0, min(self.vocab_size - 1, tok))
            chars.append(chr(tok))
        return "".join(chars)


def _logit(p: float) -> float:
    """Calculates the logit for a given probability.

    Args:
        p: A probability value between 0 and 1.

    Returns:
        The logit of the probability.
    """
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

    Args:
        config: The configuration for the sidecar.
        device: The PyTorch device to create the model on.

    Returns:
        An initialized SidecarHRM model.
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
    """Internal state for the HrmDecoderController cache."""
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
        """Initializes the HrmDecoderController.

        Args:
            pack_fetcher: A callable that fetches decoder packs from a source
                like Supabase.
            codec: The codec to use for tokenization. Defaults to AsciiCodec.
            modality: The default modality to use when fetching packs.
            device: The PyTorch device to use for models.
        """
        self._pack_fetcher = pack_fetcher
        self._codec = codec or AsciiCodec()
        self._modality = modality
        self._device = device
        self._lock = threading.RLock()
        self._cache: Dict[Tuple[str, str], _CachedState] = {}

    def clear_cache(self) -> None:
        """Clears the internal cache of decoder pack states."""
        with self._lock:
            self._cache.clear()

    def _ensure_state(self, namespace: str, modality: Optional[str] = None) -> _CachedState:
        """Ensures the cached state for a given namespace/modality is up to date.

        This method fetches the latest decoder pack, compares it with the cached
        version, and re-initializes the sidecar model if necessary.

        Args:
            namespace: The namespace for the decoder pack.
            modality: The modality for the decoder pack.

        Returns:
            The current cached state.
        """
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
        """Gets the current status of the HRM sidecar for a namespace.

        Args:
            namespace: The namespace to check.
            modality: The modality to check.

        Returns:
            A dictionary containing the status information.
        """
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
        """Applies HRM refinement to a text if the sidecar is enabled.

        Args:
            text: The input text to refine.
            namespace: The namespace to use for fetching the decoder pack.
            modality: The modality to use.

        Returns:
            A tuple containing:
            - The refined text.
            - A dictionary with status information about the refinement process.
        """
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
