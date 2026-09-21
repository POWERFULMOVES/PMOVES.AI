"""Shadow-compare a candidate decision backend against an incumbent rule.

The harness runs both and records both. It never changes what the incumbent
decided. See pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


class Outcome(str, Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    # The backend did not produce a verdict. This is NOT agreement, and must
    # never be collapsed into one -- a backend that never ran would otherwise
    # report perfect concordance.
    COULD_NOT_MEASURE = "could_not_measure"
    # We declined to ask, because the input is outside what this backend can
    # read. Distinct from COULD_NOT_MEASURE on purpose: "the backend broke" and
    # "we never asked" are different facts and collapsing them loses the reason.
    REFUSED_UNREADABLE = "refused_unreadable"


@dataclass(frozen=True)
class ShadowRecord:
    shipped: bool
    incumbent: bool
    candidate: Optional[bool]
    confidence: Optional[float]
    outcome: Outcome
    error: Optional[str] = None


Backend = Callable[[Dict[str, Any], str], Tuple[bool, float]]


def keyword_incumbent(state: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Mirror of channel-monitor _apply_filters keyword logic (monitor.py:987)."""
    title = str(state.get("title", "")).lower()
    title_keywords = [kw.lower() for kw in filters.get("title_keywords", [])]
    exclude_keywords = [kw.lower() for kw in filters.get("exclude_keywords", [])]

    if title_keywords and not any(kw in title for kw in title_keywords):
        return False
    if exclude_keywords and any(kw in title for kw in exclude_keywords):
        return False
    return True


class ShadowRunner:
    def __init__(self, incumbent, backend: Backend, readable=None):
        self._incumbent = incumbent
        self._backend = backend
        # Runs in code, before the backend. A model cannot report that its
        # input was outside what it can read -- it answers confidently anyway.
        self._readable = readable

    def compare(self, state: Dict[str, Any], filters: Dict[str, Any]) -> ShadowRecord:
        incumbent = self._incumbent(state, filters)

        if self._readable is not None and not self._readable(state):
            return ShadowRecord(
                shipped=incumbent,
                incumbent=incumbent,
                candidate=None,
                confidence=None,
                outcome=Outcome.REFUSED_UNREADABLE,
            )

        try:
            candidate, confidence = self._backend(state, "is this relevant")
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            return ShadowRecord(
                shipped=incumbent,
                incumbent=incumbent,
                candidate=None,
                confidence=None,
                outcome=Outcome.COULD_NOT_MEASURE,
                error=f"{type(exc).__name__}: {exc}",
            )

        outcome = Outcome.AGREE if candidate == incumbent else Outcome.DISAGREE
        return ShadowRecord(
            shipped=incumbent,
            incumbent=incumbent,
            candidate=candidate,
            confidence=confidence,
            outcome=outcome,
        )
