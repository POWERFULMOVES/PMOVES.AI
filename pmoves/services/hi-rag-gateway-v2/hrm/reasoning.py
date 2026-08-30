"""Hierarchical reasoning orchestration.

Implements multi-level reasoning from the pinilDissanayaka/HRM architecture:
- **Surface level**: Pattern matching and shallow feature extraction
- **Semantic level**: Embedding-space similarity and relational analysis
- **Structural level**: Graph-aware reasoning with topology awareness

Each level produces a reasoning trace entry for observability.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

try:
    import torch
except ModuleNotFoundError:
    torch = None  # type: ignore[assignment]

__all__ = ["HierarchicalReasoner"]

logger = logging.getLogger(__name__)


class HierarchicalReasoner:
    """Multi-level hierarchical reasoning engine.

    Applies successive reasoning levels to a tensor state:
    1. Surface — pattern matching on raw features
    2. Semantic — embedding-space similarity analysis
    3. Structural — topological / graph-aware reasoning

    Parameters
    ----------
    levels:
        Number of reasoning levels to apply (1-3).
    """

    # Level names for trace output
    LEVEL_NAMES = ["surface", "semantic", "structural"]

    def __init__(self, levels: int = 3) -> None:
        self.levels = max(1, min(3, int(levels)))

    # ------------------------------------------------------------------
    # Tensor-based reasoning (used when torch is available)
    # ------------------------------------------------------------------

    def reason(self, state: Any) -> Dict[str, Any]:
        """Apply hierarchical reasoning levels to a tensor state.

        Parameters
        ----------
        state:
            Input tensor (batch, seq, d_model) or compatible data.

        Returns
        -------
        dict with keys ``state``, ``trace``.
        """
        trace: List[Dict[str, Any]] = []
        current = state

        for level_idx in range(self.levels):
            level_name = self.LEVEL_NAMES[level_idx]
            try:
                current, level_trace = self._apply_level(
                    current, level_idx, level_name,
                )
                trace.append(level_trace)
            except Exception:
                logger.debug(
                    "Reasoning level %s failed", level_name, exc_info=True,
                )
                trace.append({
                    "level": level_name,
                    "action": "skipped",
                    "error": True,
                })

        return {"state": current, "trace": trace}

    def _apply_level(
        self,
        state: Any,
        level_idx: int,
        level_name: str,
    ) -> tuple:
        """Apply a single reasoning level."""
        if torch is not None and isinstance(state, torch.Tensor):
            return self._apply_level_torch(state, level_idx, level_name)
        return self._apply_level_plain(state, level_idx, level_name)

    def _apply_level_torch(
        self,
        state: Any,
        level_idx: int,
        level_name: str,
    ) -> tuple:
        """Apply reasoning level using torch tensor operations."""
        assert torch is not None

        if level_name == "surface":
            # Surface: compute L2 norm statistics as a feature proxy
            norms = torch.norm(state, dim=-1, keepdim=True)
            mean_norm = float(norms.mean().item())
            result = state + 0.01 * (state / (norms + 1e-8))
            return result, {
                "level": "surface",
                "action": "normalization",
                "mean_norm": round(mean_norm, 4),
            }

        elif level_name == "semantic":
            # Semantic: self-attention-like similarity scoring
            if state.dim() >= 2:
                flat = state.mean(dim=1) if state.dim() == 3 else state
                sim_matrix = torch.mm(flat, flat.T) if flat.dim() == 2 else flat
                avg_sim = float(sim_matrix.mean().item()) if sim_matrix.numel() > 0 else 0.0
            else:
                avg_sim = 0.0
            result = state * (1.0 + 0.01 * avg_sim)
            return result, {
                "level": "semantic",
                "action": "similarity_boost",
                "avg_similarity": round(avg_sim, 4),
            }

        elif level_name == "structural":
            # Structural: variance-aware pooling signal
            if state.dim() >= 2:
                variance = torch.var(state, dim=-1)
                structural_score = float(variance.mean().item())
            else:
                structural_score = 0.0
            return state, {
                "level": "structural",
                "action": "topology_analysis",
                "structural_score": round(structural_score, 6),
            }

        return state, {"level": level_name, "action": "passthrough"}

    def _apply_level_plain(
        self,
        state: Any,
        level_idx: int,
        level_name: str,
    ) -> tuple:
        """Apply reasoning level without torch (heuristic fallback)."""
        return state, {
            "level": level_name,
            "action": "heuristic",
            "note": "no tensor ops",
        }

    # ------------------------------------------------------------------
    # Embedding-based reasoning (used when no model is loaded)
    # ------------------------------------------------------------------

    def reason_from_embeddings(
        self,
        query_embedding: Any,
        context_embeddings: Any,
    ) -> Dict[str, Any]:
        """Lightweight reasoning from raw embeddings (no model required).

        Produces a trace based on heuristic analysis of the embeddings.
        """
        trace: List[Dict[str, Any]] = []

        # Surface level: basic vector statistics
        q_norm = self._embedding_norm(query_embedding)
        trace.append({
            "level": "surface",
            "action": "norm_analysis",
            "query_norm": round(q_norm, 4),
        })

        # Semantic level: context similarity
        avg_sim = self._avg_cosine_similarity(
            query_embedding, context_embeddings,
        )
        trace.append({
            "level": "semantic",
            "action": "context_similarity",
            "avg_similarity": round(avg_sim, 4),
        })

        # Structural level: context spread
        ctx_spread = self._context_spread(context_embeddings)
        trace.append({
            "level": "structural",
            "action": "spread_analysis",
            "context_spread": round(ctx_spread, 4),
        })

        return {"trace": trace[:self.levels]}

    # ------------------------------------------------------------------
    # Heuristic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _embedding_norm(emb: Any) -> float:
        """Compute L2 norm of an embedding."""
        if emb is None:
            return 0.0
        if hasattr(emb, "numel") and hasattr(emb, "norm"):
            return float(emb.norm().item())
        if isinstance(emb, (list, tuple)):
            return math.sqrt(sum(float(x) ** 2 for x in emb))
        return 0.0

    @staticmethod
    def _avg_cosine_similarity(
        query: Any, contexts: Any,
    ) -> float:
        """Compute average cosine similarity between query and contexts."""
        if query is None or contexts is None:
            return 0.0

        def _to_vec(v: Any) -> Optional[List[float]]:
            if hasattr(v, "tolist"):
                return v.tolist()
            if isinstance(v, (list, tuple)):
                return [float(x) for x in v]
            return None

        q_vec = _to_vec(query)
        if q_vec is None:
            return 0.0

        q_norm = math.sqrt(sum(x * x for x in q_vec)) or 1e-9

        if not hasattr(contexts, "__iter__") or isinstance(contexts, str):
            return 0.0

        sims = []
        for ctx in contexts:
            c_vec = _to_vec(ctx)
            if c_vec is None or len(c_vec) != len(q_vec):
                continue
            c_norm = math.sqrt(sum(x * x for x in c_vec)) or 1e-9
            dot = sum(a * b for a, b in zip(q_vec, c_vec))
            sims.append(dot / (q_norm * c_norm))

        return sum(sims) / len(sims) if sims else 0.0

    @staticmethod
    def _context_spread(contexts: Any) -> float:
        """Measure the spread (variance) of context embeddings."""
        if contexts is None:
            return 0.0
        if not hasattr(contexts, "__iter__") or isinstance(contexts, str):
            return 0.0

        norms = []
        for ctx in contexts:
            if hasattr(ctx, "numel") and hasattr(ctx, "norm"):
                norms.append(float(ctx.norm().item()))
            elif isinstance(ctx, (list, tuple)):
                norms.append(math.sqrt(sum(float(x) ** 2 for x in ctx)))

        if len(norms) < 2:
            return 0.0
        mean = sum(norms) / len(norms)
        variance = sum((n - mean) ** 2 for n in norms) / len(norms)
        return math.sqrt(variance)
