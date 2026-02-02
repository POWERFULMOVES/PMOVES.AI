"""
Gateway Package for Agent Zero

Implements the central orchestration layer for multi-agent coordination.
Based on PMOVES-BoTZ gateway pattern and aligned roadmap Phase 5.

Components:
- gateway: Main task dispatch and orchestration logic
- threads: Thread type definitions and execution templates
"""

__version__ = "1.0.0"
__author__ = "PMOVES.AI"

from .gateway import Gateway
from .threads import (
    BaseThread,  # Abstract base class
    BaseSimpleThread,  # Concrete BASE thread implementation
    ParallelThread,
    ChainedThread,
    FusionThread,
    BigThread,
    LongThread,
    ThreadType,
    ThreadStatus,
    ThreadResult,
    ThreadFactory
)

__all__ = [
    "Gateway",
    "BaseThread",
    "BaseSimpleThread",
    "ParallelThread",
    "ChainedThread",
    "FusionThread",
    "BigThread",
    "LongThread",
    "ThreadType",
    "ThreadStatus",
    "ThreadResult",
    "ThreadFactory",
]
