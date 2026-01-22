"""Data structures for deep research requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResearchResources:
    """Optional external resources the runner can hydrate."""

    cookbooks: Optional[List[str]] = None


@dataclass
class ResearchRequest:
    """Input payload for the deep research workflow."""

    prompt: str
    context: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    notebook: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    resources: Optional[ResearchResources] = None
