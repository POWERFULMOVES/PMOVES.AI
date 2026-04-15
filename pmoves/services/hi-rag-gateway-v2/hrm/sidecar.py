"""Enhanced HRM sidecar with dual-stream architecture.

Implements the pinilDissanayaka/HRM dual-stream pattern:
- **Fast stream**: Low-latency single-pass path for simple queries
- **Deep stream**: Multi-step reasoning with ACT-style pondering for complex queries

Auto-routes queries based on an estimated complexity score and maintains
backward compatibility with the existing ``HrmDecoderController`` interface.

Opt-in via the ``HRM_ENABLED`` environment variable (defaults to *False*).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import torch
    from torch import nn
except ModuleNotFoundError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]

from .ponder import PonderingController
from .reasoning import HierarchicalReasoner

__all__ = [
    "HRMSidecarConfig",
    "HRMSidecar",
    "is_torch_available",
]

logger = logging.getLogger(__name__)


def is_torch_available() -> bool:
    """Return ``True`` when PyTorch is importable."""
    return torch is not None


def _require_torch() -> None:
    if not is_torch_available():
        raise RuntimeError("PyTorch is required for the enhanced HRM sidecar")


@dataclass
class HRMSidecarConfig:
    """Configuration for the enhanced dual-stream HRM sidecar."""

    enabled: bool = False
    device: str = "cpu"
    fast_threshold: float = 0.3
    max_ponder_steps: int = 8
    min_ponder_steps: int = 1
    halt_threshold: float = 0.9
    d_model: int = 128
    nhead: int = 4
    dim_feedforward: int = 512
    dropout: float = 0.1
    reasoning_levels: int = 3


# ---------------------------------------------------------------------------
# Minimal dual-stream encoder (torch-gated)
# ---------------------------------------------------------------------------

if is_torch_available():

    class _StreamEncoder(nn.Module):  # type: ignore[no-redef]
        """Lightweight transformer block shared by both streams."""

        def __init__(self, d_model: int = 128, nhead: int = 4,
                     dim_feedforward: int = 512, dropout: float = 0.1) -> None:
            super().__init__()
            layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=1)
            self.ln = nn.LayerNorm(d_model)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            return self.ln(self.encoder(h))

    class _ComplexityHead(nn.Module):  # type: ignore[no-redef]
        """Estimates query complexity from the pooled embedding."""

        def __init__(self, d_model: int = 128) -> None:
            super().__init__()
            self.head = nn.Sequential(
                nn.LayerNorm(d_model),
                nn.Linear(d_model, 1),
                nn.Sigmoid(),
            )

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            pooled = h.mean(dim=1)
            return self.head(pooled).squeeze(-1)

else:

    class _StreamEncoder:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()

    class _ComplexityHead:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require_torch()


class HRMSidecar:
    """Enhanced HRM sidecar with dual-stream architecture.

    Routes queries to either a *fast stream* (single forward pass, low
    latency) or a *deep stream* (multi-step pondering with hierarchical
    reasoning) based on an estimated complexity score.
    """

    def __init__(self, config: Optional[HRMSidecarConfig] = None) -> None:
        self.config = config or HRMSidecarConfig()
        self.device = self.config.device
        self._model: Optional[_StreamEncoder] = None
        self._complexity_head: Optional[_ComplexityHead] = None
        self.ponder = PonderingController(
            min_steps=self.config.min_ponder_steps,
            max_steps=self.config.max_ponder_steps,
            halt_threshold=self.config.halt_threshold,
        )
        self.reasoner = HierarchicalReasoner(
            levels=self.config.reasoning_levels,
        )
        self._lock = threading.RLock()
        self._loaded = False
        self._load_model()

    def _load_model(self) -> None:
        """Initialise the stream encoder and complexity head."""
        if not self.config.enabled:
            logger.info("HRM sidecar disabled (HRM_ENABLED=false)")
            return
        if not is_torch_available():
            logger.warning("HRM sidecar: torch not available; running in no-op mode")
            return
        try:
            self._model = _StreamEncoder(
                d_model=self.config.d_model,
                nhead=self.config.nhead,
                dim_feedforward=self.config.dim_feedforward,
                dropout=self.config.dropout,
            ).to(self.device)
            self._complexity_head = _ComplexityHead(
                d_model=self.config.d_model,
            ).to(self.device)
            self._model.eval()
            self._complexity_head.eval()
            self._loaded = True
            logger.info(
                "HRM sidecar loaded (d_model=%d, device=%s, fast_threshold=%.2f)",
                self.config.d_model,
                self.device,
                self.config.fast_threshold,
            )
        except Exception:
            logger.exception("HRM sidecar model init failed")
            self._loaded = False

    def _estimate_complexity(
        self,
        query_embedding: Any,
        context_embeddings: Any,
    ) -> float:
        """Estimate query complexity on [0, 1]."""
        if self._loaded and self._complexity_head is not None and torch is not None:
            try:
                q_tensor = self._to_tensor(query_embedding)
                if q_tensor is not None:
                    if q_tensor.dim() == 1:
                        q_tensor = q_tensor.unsqueeze(0).unsqueeze(0)
                    elif q_tensor.dim() == 2:
                        q_tensor = q_tensor.unsqueeze(0)
                    with torch.no_grad():
                        return float(self._complexity_head(q_tensor).item())
            except Exception:
                logger.debug("Complexity head failed; using heuristic", exc_info=True)

        # Heuristic: ratio of context count to a baseline
        ctx_count = 0
        if context_embeddings is not None:
            if hasattr(context_embeddings, "__len__"):
                ctx_count = len(context_embeddings)
            elif isinstance(context_embeddings, (list, tuple)):
                ctx_count = len(context_embeddings)
        return min(1.0, ctx_count / 20.0)

    def _to_tensor(self, data: Any) -> Any:
        """Convert various data formats to a torch tensor."""
        if torch is None:
            return None
        if isinstance(data, torch.Tensor):
            return data.to(self.device)
        if isinstance(data, (list, tuple)):
            return torch.tensor(data, dtype=torch.float32, device=self.device)
        return None

    def _fast_stream(
        self,
        query_embedding: Any,
        context_embeddings: Any,
    ) -> Dict[str, Any]:
        """Low-latency single-pass path."""
        result_tensor = query_embedding
        if self._loaded and self._model is not None and torch is not None:
            try:
                q_tensor = self._to_tensor(query_embedding)
                if q_tensor is not None:
                    if q_tensor.dim() == 1:
                        q_tensor = q_tensor.unsqueeze(0).unsqueeze(0)
                    elif q_tensor.dim() == 2:
                        q_tensor = q_tensor.unsqueeze(0)
                    with torch.no_grad():
                        refined = self._model(q_tensor)
                    result_tensor = refined.squeeze(0).detach().cpu().tolist()
            except Exception:
                logger.debug("Fast stream model inference failed", exc_info=True)

        return {
            "stream": "fast",
            "complexity": 0.0,
            "ponder_steps": 0,
            "reasoning_levels": 0,
            "embedding": result_tensor,
            "trace": [{"level": "fast", "action": "single_pass"}],
        }

    def _deep_stream(
        self,
        query_embedding: Any,
        context_embeddings: Any,
        complexity_score: float,
    ) -> Dict[str, Any]:
        """Multi-step reasoning with pondering."""
        state = query_embedding
        ponder_steps = 0
        reasoning_trace: List[Dict[str, Any]] = []

        if self._loaded and self._model is not None and torch is not None:
            try:
                q_tensor = self._to_tensor(query_embedding)
                if q_tensor is not None:
                    if q_tensor.dim() == 1:
                        q_tensor = q_tensor.unsqueeze(0).unsqueeze(0)
                    elif q_tensor.dim() == 2:
                        q_tensor = q_tensor.unsqueeze(0)

                    # Pondering: adaptive computation steps
                    state_tensor, ponder_steps = self.ponder.ponder(
                        q_tensor, transform=self._model,
                    )

                    # Hierarchical reasoning
                    reasoning_result = self.reasoner.reason(state_tensor)
                    reasoning_trace = reasoning_result.get("trace", [])

                    state = state_tensor.squeeze(0).detach().cpu().tolist()
            except Exception:
                logger.debug("Deep stream inference failed", exc_info=True)
                ponder_steps = 0
        else:
            reasoning_result = self.reasoner.reason_from_embeddings(
                query_embedding, context_embeddings,
            )
            reasoning_trace = reasoning_result.get("trace", [])

        return {
            "stream": "deep",
            "complexity": complexity_score,
            "ponder_steps": ponder_steps,
            "reasoning_levels": len(reasoning_trace),
            "embedding": state,
            "trace": reasoning_trace,
        }

    def process(
        self,
        query_embedding: Any,
        context_embeddings: Any = None,
        complexity_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Process a query through the dual-stream architecture.

        Parameters
        ----------
        query_embedding:
            Embedding tensor / list for the query.
        context_embeddings:
            Optional list of context embeddings.
        complexity_score:
            Pre-computed complexity on [0, 1].

        Returns
        -------
        dict with keys stream, complexity, ponder_steps,
            reasoning_levels, embedding, trace.
        """
        if not self.config.enabled:
            return {
                "stream": "disabled",
                "complexity": 0.0,
                "ponder_steps": 0,
                "reasoning_levels": 0,
                "embedding": query_embedding,
                "trace": [],
            }

        if complexity_score is None:
            complexity_score = self._estimate_complexity(
                query_embedding, context_embeddings,
            )

        if complexity_score < self.config.fast_threshold:
            return self._fast_stream(query_embedding, context_embeddings)
        else:
            return self._deep_stream(
                query_embedding, context_embeddings, complexity_score,
            )

    def status(self) -> Dict[str, Any]:
        """Return current sidecar status for diagnostics."""
        return {
            "enabled": self.config.enabled,
            "loaded": self._loaded,
            "device": self.device,
            "fast_threshold": self.config.fast_threshold,
            "max_ponder_steps": self.config.max_ponder_steps,
            "halt_threshold": self.config.halt_threshold,
            "reasoning_levels": self.config.reasoning_levels,
            "architecture": "dual-stream",
        }
