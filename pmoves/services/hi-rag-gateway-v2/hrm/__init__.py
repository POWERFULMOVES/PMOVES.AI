"""Enhanced HRM (Hierarchical Reasoning Module) package.

Dual-stream architecture with adaptive computation, inspired by
pinilDissanayaka/HRM.

Usage::

    from hrm import HRMSidecar, HRMSidecarConfig
    config = HRMSidecarConfig(enabled=True)
    sidecar = HRMSidecar(config)
    result = sidecar.process(query_embedding, context_embeddings)
"""

from .sidecar import HRMSidecar, HRMSidecarConfig, is_torch_available
from .ponder import PonderingController
from .reasoning import HierarchicalReasoner

__all__ = [
    "HRMSidecar",
    "HRMSidecarConfig",
    "PonderingController",
    "HierarchicalReasoner",
    "is_torch_available",
]
