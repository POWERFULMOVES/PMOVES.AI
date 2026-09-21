"""Tests for the decision-shadow harness.

The harness runs a candidate decision backend ALONGSIDE an incumbent rule and
records both, without ever changing what the incumbent decided. See
pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md section 6.
"""

import pytest

from pmoves.tools.decision_shadow import (
    Outcome,
    ShadowRunner,
    keyword_incumbent,
)


def _filters(title_keywords=None, exclude_keywords=None):
    return {
        "title_keywords": title_keywords or [],
        "exclude_keywords": exclude_keywords or [],
    }


def test_returned_verdict_is_always_the_incumbents_even_when_backend_disagrees():
    """The shadow observes; it must never alter what ships.

    Production change that would make this fail: returning the backend's
    verdict (or any blend of the two) from ShadowRunner.compare().
    """
    # Incumbent excludes it (no keyword match); backend would include it.
    runner = ShadowRunner(
        incumbent=keyword_incumbent,
        backend=lambda state, question: (True, 0.99),
    )

    record = runner.compare(
        state={"title": "Transformers explained end to end"},
        filters=_filters(title_keywords=["machine learning"]),
    )

    assert record.shipped is False, "the incumbent's verdict must be what ships"
    assert record.incumbent is False
    assert record.candidate is True
    assert record.outcome is Outcome.DISAGREE


def test_backend_failure_is_recorded_as_could_not_measure_not_as_agreement():
    """A broken backend must be visibly unmeasured, never silently concordant.

    Production change that would make this fail: catching the backend error and
    falling back to the incumbent's verdict as the candidate, which would report
    100% agreement for a backend that never ran.
    """
    def exploding_backend(state, question):
        raise RuntimeError("connection refused")

    runner = ShadowRunner(incumbent=keyword_incumbent, backend=exploding_backend)

    record = runner.compare(
        state={"title": "anything at all"},
        filters=_filters(),
    )

    assert record.shipped is True, "incumbent still decides; a shadow fault cannot block"
    assert record.outcome is Outcome.COULD_NOT_MEASURE
    assert record.candidate is None, "no verdict may be invented for a backend that failed"
    assert record.error is not None and "connection refused" in record.error


def test_unreadable_input_is_refused_before_the_backend_is_ever_called():
    """Laya's English checkpoint scores 0.000 accuracy at 0.952 confidence on
    Khmer. A confident wrong answer cannot be caught downstream by confidence
    gating, so the guard must run BEFORE the call, in code.

    Production change that would make this fail: calling the backend first and
    filtering on the answer, or folding this into COULD_NOT_MEASURE (which would
    lose the distinction between 'the backend broke' and 'we declined to ask').
    """
    calls = []

    def recording_backend(state, question):
        calls.append(state)
        return True, 0.952

    runner = ShadowRunner(
        incumbent=keyword_incumbent,
        backend=recording_backend,
        readable=lambda state: state.get("title", "").isascii(),
    )

    record = runner.compare(
        state={"title": "សួស្តី​ពិភពលោក"},
        filters=_filters(),
    )

    assert calls == [], "the backend must not be consulted on input it cannot read"
    assert record.outcome is Outcome.REFUSED_UNREADABLE
    assert record.candidate is None
    assert record.shipped is True, "the incumbent still decides"
