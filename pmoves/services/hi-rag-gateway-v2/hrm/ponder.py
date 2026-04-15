"""Adaptive computation with ACT-style pondering.

Implements the pondering mechanism from the pinilDissanayaka/HRM architecture:
- Dynamically allocates compute steps based on query difficulty
- Halt probability computed at each step via a learned sigmoid head
- Minimum and maximum ponder steps are configurable
- Logs ponder statistics for observability
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
    from torch import nn
except ModuleNotFoundError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]

__all__ = ["PonderingController"]

logger = logging.getLogger(__name__)


def _is_torch_available() -> bool:
    return torch is not None


if _is_torch_available():

    class _HaltHead(nn.Module):  # type: ignore[no-redef]
        """Simple learned halt-probability head."""

        def __init__(self, d_model: int = 128) -> None:
            super().__init__()
            self.ln = nn.LayerNorm(d_model)
            self.proj = nn.Linear(d_model, 1)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            # h: (batch, seq, d_model) -> pool -> sigmoid -> (batch,)
            pooled = h.mean(dim=1)
            return torch.sigmoid(self.proj(self.ln(pooled)).squeeze(-1))

    class _StepTransform(nn.Module):  # type: ignore[no-redef]
        """Single residual transformer step used during pondering."""

        def __init__(self, d_model: int = 128, nhead: int = 4,
                     dim_feedforward: int = 512, dropout: float = 0.1) -> None:
            super().__init__()
            layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout, batch_first=True,
            )
            self.block = nn.TransformerEncoder(layer, num_layers=1)
            self.ln = nn.LayerNorm(d_model)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            return self.ln(self.block(h))

else:  # pragma: no cover

    class _HaltHead:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class _StepTransform:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


class PonderingController:
    """ACT-style adaptive computation controller.

    Runs multiple refinement steps on a hidden state, halting early
    when the model is confident enough (halt probability >= threshold).

    Parameters
    ----------
    min_steps:
        Minimum pondering steps before halting is allowed.
    max_steps:
        Maximum pondering steps (hard cap).
    halt_threshold:
        Sigmoid output threshold at which to stop early.
    d_model:
        Model dimensionality for internal heads.
    """

    def __init__(
        self,
        min_steps: int = 1,
        max_steps: int = 8,
        halt_threshold: float = 0.9,
        d_model: int = 128,
        nhead: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
    ) -> None:
        self.min_steps = max(1, int(min_steps))
        self.max_steps = max(self.min_steps, int(max_steps))
        self.halt_threshold = float(halt_threshold)
        self.d_model = int(d_model)
        self._halt_head: Optional[_HaltHead] = None
        self._step_transform: Optional[_StepTransform] = None
        self._stats: List[Dict[str, Any]] = []
        self._initialized = False

        if _is_torch_available():
            try:
                self._halt_head = _HaltHead(d_model)
                self._step_transform = _StepTransform(
                    d_model, nhead, dim_feedforward, dropout,
                )
                self._halt_head.eval()
                self._step_transform.eval()
                self._initialized = True
            except Exception:
                logger.debug("PonderingController torch init failed", exc_info=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ponder(
        self,
        state: Any,
        transform: Optional[Callable] = None,
    ) -> Tuple[Any, int]:
        """Run adaptive computation steps, halting when confident.

        Parameters
        ----------
        state:
            Input tensor (batch, seq, d_model) or compatible data.
        transform:
            Optional callable for each ponder step.  Falls back to the
            internal ``_step_transform`` when not provided.

        Returns
        -------
        (refined_state, steps_taken)
            The accumulated state and the number of pondering steps.
        """
        if not _is_torch_available() or not self._initialized:
            return self._ponder_no_torch(state)

        assert torch is not None
        if not isinstance(state, torch.Tensor):
            return self._ponder_no_torch(state)

        device = state.device
        step_fn = transform
        if step_fn is None:
            step_fn = self._step_transform  # type: ignore[assignment]

        total_state = torch.zeros_like(state)
        steps_taken = 0

        with torch.no_grad():
            for step in range(1, self.max_steps + 1):
                # Compute halt probability
                halt_prob = 1.0
                if self._halt_head is not None:
                    try:
                        halt_prob = float(self._halt_head(state).mean().item())
                    except Exception:
                        halt_prob = 1.0

                # Weight with remainder scheduling (ACT-style)
                remainder = 1.0 - min(step, self.max_steps) / self.max_steps
                weight = min(halt_prob, remainder) if step >= self.min_steps else 0.0

                total_state = total_state + weight * state
                steps_taken = step

                # Halt condition (check raw halt_prob, not remainder-capped weight)
                if halt_prob >= self.halt_threshold and step >= self.min_steps:
                    break

                # Apply transform for next step
                if step_fn is not None:
                    try:
                        state = step_fn(state)
                    except Exception:
                        break

        # Normalize accumulated state
        if steps_taken > 0:
            result = total_state / steps_taken
        else:
            result = state

        # Record stats
        self._stats.append({
            "steps": steps_taken,
            "halt_prob": halt_prob if "halt_prob" in dir() else 1.0,
            "max_steps": self.max_steps,
        })
        # Keep stats bounded
        if len(self._stats) > 1000:
            self._stats = self._stats[-500:]

        return result, steps_taken

    def _ponder_no_torch(self, state: Any) -> Tuple[Any, int]:
        """Fallback when torch is unavailable — identity passthrough."""
        return state, 0

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated ponder statistics."""
        if not self._stats:
            return {
                "total_calls": 0,
                "avg_steps": 0.0,
                "max_steps_seen": 0,
                "min_steps_seen": 0,
            }
        steps_list = [s["steps"] for s in self._stats]
        return {
            "total_calls": len(self._stats),
            "avg_steps": sum(steps_list) / len(steps_list),
            "max_steps_seen": max(steps_list),
            "min_steps_seen": min(steps_list),
        }

    def reset_stats(self) -> None:
        """Clear accumulated statistics."""
        self._stats.clear()
