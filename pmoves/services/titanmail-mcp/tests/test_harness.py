"""Mandate (b): the harness measures what it claims and fails the build below target."""
from datetime import timedelta

import pytest

from titanmail.evalkit.fixture import FIXTURE_NOW, build_fixture
from titanmail.evalkit.harness import (EXIT_BELOW_TARGET, EXIT_COULD_NOT_MEASURE, EXIT_PASS,
                                       build_queries, run, score_naive, verdict)
from titanmail.service import TitanMailService
from titanmail.timewindow import FrozenClock, load_tz
from titanmail.transports import InMemoryTransport


@pytest.mark.parametrize("args,expected", [
    ((182, 1.0, 1.0, 0), EXIT_PASS),
    ((182, 0.99, 0.999, 0), EXIT_PASS),
    ((182, 0.9899, 1.0, 0), EXIT_BELOW_TARGET),
    ((182, 1.0, 0.998, 0), EXIT_BELOW_TARGET),
    ((182, 1.0, None, 0), EXIT_COULD_NOT_MEASURE),     # no merges measured is not a pass
    ((99, 1.0, 1.0, 0), EXIT_COULD_NOT_MEASURE),       # fewer than 100 queries
    ((182, 0.0, 1.0, 182), EXIT_COULD_NOT_MEASURE),    # every query errored
])
def test_verdict_threshold_logic(args, expected):
    assert verdict(*args) == expected


def test_fixture_meets_spec_size_and_edge_coverage():
    fx = build_fixture()
    assert len(fx.messages) >= 300 and fx.span_days() >= 90
    utc = {m.date.astimezone(FIXTURE_NOW.tzinfo).isoformat() for m in fx.messages}
    assert "2026-07-01T00:00:00+00:00" in utc and "2026-06-30T23:59:59+00:00" in utc
    offsets = {m.date.utcoffset() for m in fx.messages}
    assert timedelta(hours=5, minutes=30) in offsets and timedelta(hours=13) in offsets
    assert timedelta(hours=-4) in offsets and timedelta(hours=-5) in offsets  # both sides of US DST
    assert len(fx.true_duplicate_pairs()) >= 25
    assert build_fixture().messages[17].date == fx.messages[17].date  # deterministic


def test_query_set_is_large_and_independent():
    qs = build_queries(build_fixture())
    assert len(qs) >= 100
    assert sum(1 for q in qs if q.kind == "relative") >= 20
    assert sum(1 for q in qs if q.expected) >= 0.8 * len(qs)


def _caller(fx, shift_before=timedelta(0)):
    emails = fx.emails()

    async def call(tool, args, tz):
        svc = TitanMailService(InMemoryTransport(emails), clock=FrozenClock(fx.now), tz=load_tz(tz))
        if shift_before and "before_iso" in args:
            from datetime import datetime
            b = datetime.fromisoformat(args["before_iso"]) + shift_before
            args = {**args, "before_iso": b.isoformat()}
        return await getattr(svc, tool)(**args)
    return call


async def test_service_meets_target_in_process():
    fx = build_fixture()
    score = await run(fx, build_queries(fx), _caller(fx))
    assert score.accuracy >= 0.99, score.to_dict()["failures"][:3]
    assert score.dedup_precision is not None and score.dedup_precision >= 0.999
    assert score.verdict() == EXIT_PASS


async def test_harness_detects_an_off_by_one_second_bug():
    """Mutation check: making `before` effectively inclusive (+1 s) must fail the build."""
    fx = build_fixture()
    score = await run(fx, build_queries(fx), _caller(fx, shift_before=timedelta(seconds=1)))
    assert score.accuracy < 0.99
    assert score.verdict() == EXIT_BELOW_TARGET


def test_positive_control_day_granular_filter_scores_far_below_target():
    fx = build_fixture()
    assert score_naive(fx, build_queries(fx)) < 0.6
