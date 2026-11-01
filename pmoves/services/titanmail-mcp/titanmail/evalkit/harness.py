"""EmailBench-style date-window smoke harness (seed-spec mandate (b)).

Builds >=100 date-window queries with KNOWN ground truth over the fixture inbox,
runs each one THROUGH THE MCP TOOL LAYER (FastMCP.call_tool, in-process) or the
service directly, and scores exact-set retrieval. A query counts as correct only
when the returned id set equals the ground-truth set AND total_in_window equals
its size -- no partial credit.

Ground truth is computed independently of the service: integer epoch-second
comparisons over the fixture, and, for relative phrases, from a HAND-WRITTEN
table of expected absolute bounds (RELATIVE_EXPECTED) rather than from the
resolver under test.

Targets: date-window accuracy >= 0.99, dedup precision >= 0.999. Below either is a
failing build (exit 1). Could-not-measure is exit 3, never a pass.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

from ..timewindow import UTC
from .fixture import FIXTURE_NOW, TOPICS, Fixture

DATE_TARGET = 0.99
DEDUP_TARGET = 0.999

EXIT_PASS, EXIT_BELOW_TARGET, EXIT_COULD_NOT_MEASURE = 0, 1, 3


def _z(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# Hand-computed for FIXTURE_NOW = 2026-11-15T12:00:00Z (Sunday). NOT derived from the
# resolver. New York: EST (-05) on Nov 15, but Nov 1 00:00 and Oct 1 00:00 are EDT (-04).
# Auckland: NZDT (+13) from 2026-09-27, so local "now" is Monday 2026-11-16 01:00.
RELATIVE_EXPECTED: dict[tuple[str, str], tuple[str, str]] = {
    ("UTC", "today"): ("2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z"),
    ("UTC", "yesterday"): ("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z"),
    ("UTC", "this week"): ("2026-11-09T00:00:00Z", "2026-11-16T00:00:00Z"),
    ("UTC", "last week"): ("2026-11-02T00:00:00Z", "2026-11-09T00:00:00Z"),
    ("UTC", "this month"): ("2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z"),
    ("UTC", "last month"): ("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z"),
    ("UTC", "last 7 days"): ("2026-11-08T12:00:00Z", "2026-11-15T12:00:00Z"),
    ("UTC", "last 24 hours"): ("2026-11-14T12:00:00Z", "2026-11-15T12:00:00Z"),
    ("UTC", "past 2 weeks"): ("2026-11-01T12:00:00Z", "2026-11-15T12:00:00Z"),
    ("UTC", "last 90 days"): ("2026-08-17T12:00:00Z", "2026-11-15T12:00:00Z"),
    ("America/New_York", "today"): ("2026-11-15T05:00:00Z", "2026-11-16T05:00:00Z"),
    ("America/New_York", "yesterday"): ("2026-11-14T05:00:00Z", "2026-11-15T05:00:00Z"),
    ("America/New_York", "this week"): ("2026-11-09T05:00:00Z", "2026-11-16T05:00:00Z"),
    ("America/New_York", "last week"): ("2026-11-02T05:00:00Z", "2026-11-09T05:00:00Z"),
    ("America/New_York", "this month"): ("2026-11-01T04:00:00Z", "2026-12-01T05:00:00Z"),
    ("America/New_York", "last month"): ("2026-10-01T04:00:00Z", "2026-11-01T04:00:00Z"),
    ("America/New_York", "last 7 days"): ("2026-11-08T12:00:00Z", "2026-11-15T12:00:00Z"),
    ("Pacific/Auckland", "today"): ("2026-11-15T11:00:00Z", "2026-11-16T11:00:00Z"),
    ("Pacific/Auckland", "yesterday"): ("2026-11-14T11:00:00Z", "2026-11-15T11:00:00Z"),
    ("Pacific/Auckland", "this week"): ("2026-11-15T11:00:00Z", "2026-11-22T11:00:00Z"),
    ("Pacific/Auckland", "last week"): ("2026-11-08T11:00:00Z", "2026-11-15T11:00:00Z"),
    ("Pacific/Auckland", "this month"): ("2026-10-31T11:00:00Z", "2026-11-30T11:00:00Z"),
    ("Pacific/Auckland", "last month"): ("2026-09-30T11:00:00Z", "2026-10-31T11:00:00Z"),
    ("Asia/Kolkata", "today"): ("2026-11-14T18:30:00Z", "2026-11-15T18:30:00Z"),
    ("Asia/Kolkata", "yesterday"): ("2026-11-13T18:30:00Z", "2026-11-14T18:30:00Z"),
}


@dataclass
class Query:
    qid: str
    kind: str
    args: dict
    expected: frozenset
    server_tz: str = "UTC"


@dataclass
class QueryResult:
    qid: str
    kind: str
    correct: bool
    expected: int
    got: int
    missing: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    error: str = ""


@dataclass
class Score:
    total: int
    correct: int
    failures: list[QueryResult]
    dedup_precision: Optional[float]
    dedup_recall: Optional[float]
    dedup_merged_pairs: int
    dedup_false_merges: int
    errors: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def verdict(self, date_target: float = DATE_TARGET, dedup_target: float = DEDUP_TARGET,
                require_dedup: bool = True) -> int:
        return verdict(self.total, self.accuracy, self.dedup_precision, self.errors,
                       date_target=date_target, dedup_target=dedup_target,
                       require_dedup=require_dedup)

    def to_dict(self) -> dict:
        return {"queries": self.total, "correct": self.correct, "accuracy": round(self.accuracy, 6),
                "date_target": DATE_TARGET, "errors": self.errors,
                "dedup_precision": self.dedup_precision, "dedup_recall": self.dedup_recall,
                "dedup_merged_pairs": self.dedup_merged_pairs,
                "dedup_false_merges": self.dedup_false_merges, "dedup_target": DEDUP_TARGET,
                "failures": [f.__dict__ for f in self.failures[:25]]}


def verdict(total: int, accuracy: float, dedup_precision: Optional[float], errors: int, *,
            date_target: float = DATE_TARGET, dedup_target: float = DEDUP_TARGET,
            require_dedup: bool = True, min_queries: int = 100) -> int:
    """0 pass / 1 below target / 3 could-not-measure. Pure, so it is unit-tested directly."""
    if total < min_queries:
        return EXIT_COULD_NOT_MEASURE
    if errors and errors == total:
        return EXIT_COULD_NOT_MEASURE
    if accuracy < date_target:
        return EXIT_BELOW_TARGET
    if require_dedup:
        if dedup_precision is None:
            return EXIT_COULD_NOT_MEASURE
        if dedup_precision < dedup_target:
            return EXIT_BELOW_TARGET
    return EXIT_PASS


def _gt(fx: Fixture, after: datetime, before: datetime, topic: str = "") -> frozenset:
    a, b = int(after.timestamp()), int(before.timestamp())
    return frozenset(m.fixture_id for m in fx.messages
                     if a <= int(m.date.timestamp()) < b and (not topic or m.topic == topic))


def build_queries(fx: Fixture, seed: int = 7) -> list[Query]:
    rng = random.Random(seed)
    qs: list[Query] = []
    zones = ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London", "Asia/Kolkata",
             "Pacific/Auckland", "Australia/Adelaide", "Pacific/Chatham"]
    start = min(m.date.astimezone(UTC) for m in fx.messages).date()
    days = (FIXTURE_NOW.date() - start).days

    def explicit(kind: str, after: datetime, before: datetime, topic: str = "") -> None:
        args = {"after_iso": after.isoformat(), "before_iso": before.isoformat(), "limit": 500}
        if topic:
            args["query"] = topic
        qs.append(Query(f"q{len(qs) + 1:03d}", kind, args, _gt(fx, after, before, topic)))

    # 1. local calendar days in many zones (includes DST days and +13:45 Chatham)
    for _ in range(40):
        tz = ZoneInfo(rng.choice(zones))
        d = start + timedelta(days=rng.randrange(days))
        a = datetime(d.year, d.month, d.day, tzinfo=tz)
        nd = d + timedelta(days=1)
        explicit("local_day", a, datetime(nd.year, nd.month, nd.day, tzinfo=tz))
    for d in ("2026-03-08", "2026-11-01", "2026-03-29", "2026-10-25", "2026-04-05", "2026-09-27"):
        for tzname in ("America/New_York", "Europe/London", "Pacific/Auckland"):
            tz = ZoneInfo(tzname)
            day = datetime.fromisoformat(d).date()
            nd = day + timedelta(days=1)
            explicit("dst_day", datetime(day.year, day.month, day.day, tzinfo=tz),
                     datetime(nd.year, nd.month, nd.day, tzinfo=tz))

    # 2. boundaries landing exactly on message instants (inclusive after / exclusive before),
    #    re-expressed in a random offset so equality must survive offset conversion
    instants = sorted({m.date.astimezone(UTC) for m in fx.messages})
    for _ in range(30):
        i = rng.randrange(len(instants) - 40)
        j = i + rng.randint(1, 40)
        tz = ZoneInfo(rng.choice(zones))
        explicit("exact_boundary", instants[i].astimezone(tz), instants[j].astimezone(tz))

    # 3. one-second and one-hour windows around UTC midnights and the US fold
    for s in ("2026-07-01T00:00:00Z", "2026-11-01T00:00:00Z", "2026-04-01T00:00:00Z"):
        t = _z(s)
        explicit("utc_midnight_1s", t - timedelta(seconds=1), t)
        explicit("utc_midnight_1s", t, t + timedelta(seconds=1))
        explicit("utc_midnight_1h", t - timedelta(hours=1), t + timedelta(hours=1))
    fold_edt, fold_est = _z("2026-11-01T01:30:00-04:00"), _z("2026-11-01T01:30:00-05:00")
    explicit("dst_fold", fold_edt, fold_edt + timedelta(minutes=30))
    explicit("dst_fold", fold_est, fold_est + timedelta(minutes=30))
    explicit("dst_fold", fold_edt - timedelta(seconds=1), fold_est + timedelta(seconds=1))
    gap = _z("2026-03-08T01:59:59-05:00")
    explicit("dst_gap", gap, gap + timedelta(seconds=2))
    explicit("dst_gap", gap + timedelta(seconds=1), _z("2026-03-08T03:00:01-04:00"))

    # 4. arbitrary windows in odd offsets
    odd = [timedelta(hours=5, minutes=30), timedelta(hours=-3, minutes=-30), timedelta(hours=13),
           timedelta(hours=12, minutes=45), timedelta(hours=-9), timedelta(0)]
    from datetime import timezone as _tzc
    for _ in range(30):
        a = FIXTURE_NOW - timedelta(seconds=rng.randrange(days * 86400))
        b = a + timedelta(seconds=rng.randint(60, 14 * 86400))
        off = _tzc(rng.choice(odd))
        explicit("odd_offset", a.astimezone(off), b.astimezone(off))

    # 5. text + window
    for _ in range(25):
        a = FIXTURE_NOW - timedelta(days=rng.randint(10, days))
        b = a + timedelta(days=rng.randint(3, 90))
        explicit("text_window", a.astimezone(UTC), b.astimezone(UTC), topic=rng.choice(TOPICS))

    # 6. relative phrases, server-resolved, checked against the hand-written table
    for (tzname, phrase), (lo, hi) in RELATIVE_EXPECTED.items():
        qs.append(Query(f"q{len(qs) + 1:03d}", "relative", {"relative": phrase, "limit": 500},
                        _gt(fx, _z(lo), _z(hi)), server_tz=tzname))
    return qs


Caller = Callable[[str, dict, str], Awaitable[Optional[dict]]]


def _ids(payload: dict) -> list[str]:
    out = []
    for m in payload.get("messages") or []:
        fid = (m.get("headers") or {}).get("X-Titanmail-Fixture-Id") or m.get("id")
        out.append(fid)
    return out


async def run(fx: Fixture, queries: list[Query], call: Caller, *,
              dedup_window: Optional[tuple[str, str]] = None) -> Score:
    """``call(tool_name, args, server_tz) -> payload dict``."""
    correct, failures, errors = 0, [], 0
    for q in queries:
        try:
            payload = await call("search_messages", dict(q.args), q.server_tz)
        except Exception as exc:  # noqa: BLE001 - a crash is an error, scored as wrong
            payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if not payload or not payload.get("ok"):
            errors += 1
            failures.append(QueryResult(q.qid, q.kind, False, len(q.expected), 0,
                                        error=str((payload or {}).get("error"))[:300]))
            continue
        got = set(_ids(payload))
        ok = got == q.expected and payload.get("total_in_window") == len(q.expected)
        if ok:
            correct += 1
        else:
            failures.append(QueryResult(q.qid, q.kind, False, len(q.expected), len(got),
                                        missing=sorted(q.expected - got)[:10],
                                        extra=sorted(got - q.expected)[:10]))

    lo, hi = dedup_window or ("2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z")
    precision = recall = None
    merged = false = 0
    rep = await call("dedup_report", {"after_iso": lo, "before_iso": hi}, "UTC")
    if rep and rep.get("ok"):
        pairs = set()
        for c in rep.get("clusters") or []:
            # transport ids (mailpit IDs) -> fixture ids via the passthrough header
            idmap = {tid: h.get("X-Titanmail-Fixture-Id", tid)
                     for tid, h in (c.get("member_headers") or {}).items()}
            ids = [idmap.get(i, i) for i in [c["canonical_id"], *c["duplicate_ids"]]]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pairs.add(frozenset((ids[i], ids[j])))
        truth = fx.true_duplicate_pairs()
        merged = len(pairs)
        false = len(pairs - truth)
        precision = (merged - false) / merged if merged else None
        recall = (merged - false) / len(truth) if truth else None
    return Score(len(queries), correct, failures, precision, recall, merged, false, errors)


def naive_day_filter(fx: Fixture, q: Query) -> set[str]:
    """POSITIVE CONTROL: what a date-only, UTC-day provider filter returns when nobody trims
    to the exact window (the Gmail after:/before: YYYY/MM/DD behaviour Composio documents)."""
    if "relative" in q.args:
        lo, hi = RELATIVE_EXPECTED[(q.server_tz, q.args["relative"])]
        a, b = _z(lo), _z(hi)
    else:
        a, b = _z(q.args["after_iso"]), _z(q.args["before_iso"])
    da, db = a.astimezone(UTC).date(), b.astimezone(UTC).date()
    topic = q.args.get("query", "")
    return {m.fixture_id for m in fx.messages
            if da <= m.date.astimezone(UTC).date() < db and (not topic or m.topic == topic)}


def score_naive(fx: Fixture, queries: list[Query]) -> float:
    ok = sum(1 for q in queries if naive_day_filter(fx, q) == set(q.expected))
    return ok / len(queries)


def summarize(queries: list[Query]) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    for q in queries:
        kinds[q.kind] = kinds.get(q.kind, 0) + 1
    return {"queries": len(queries), "by_kind": kinds,
            "empty_ground_truth": sum(1 for q in queries if not q.expected)}
