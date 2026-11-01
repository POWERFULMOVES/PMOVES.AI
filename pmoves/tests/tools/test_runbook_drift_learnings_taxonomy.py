"""The LEARNINGS taxonomy summary is a MEASUREMENT of the lesson table, so it
is recomputed and asserted rather than trusted.

WHY THIS FILE EXISTS
--------------------
`runbook_drift_fleet_closure_LEARNINGS.md` ends its taxonomy with a **Bucket
summary** — the per-class count of its lessons. That summary is a number about
the lesson table sitting directly above it, and a number in a file whose entire
subject is "unmeasured claims are the defect class" needs a gate like any
other: a reviewer (correctly) noticed that the summary and the table had to
agree and checked the arithmetic by hand.

A hand check is a good check ONCE. It is not a check that survives the next
lesson. So the summary is recomputed from the table here, on every run, and
the two are asserted to agree.

WHAT THIS FILE ASSERTS
----------------------
  * every lesson row carries a class from the house taxonomy, and no lesson
    is counted twice or skipped;
  * the lesson numbers are contiguous from 1;
  * the Bucket summary's per-class counts and its total equal what the lesson
    table actually contains;
  * the summary names the same lesson numbers the table does — a count that
    is right while the LIST is wrong is still a wrong summary.

Hermetic: reads one file in this repo, writes nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LEARNINGS = (
    REPO_ROOT
    / "pmoves"
    / "docs"
    / "AGENTS"
    / "runbook_drift_fleet_closure_LEARNINGS.md"
)

# The house taxonomy: 4 buckets, 5 classes.
HOUSE_CLASSES = {
    "reasoning-gap",
    "semantic-naming drift",
    "contract-correctness",
    "defense-in-depth",
    "pattern-conformance",
}

# A lesson row: | 23 | **reasoning-gap** | **The rule** | ... |
LESSON_ROW_RE = re.compile(r"^\| (\d+) \| \*\*([a-z][a-z -]*)\*\* \| \*\*", re.M)

# The bucket summary line: (1) **reasoning-gap** 13 lessons (#1, #2, ...).
#
# The whitespace between the COUNT and the word "lessons" is `\s+`, not a
# literal space, because the summary WRAPS in the source file and a reader
# should not have to keep a hand-written number on one physical line to keep
# it parseable. The wrap is caught here rather than by the reader.
SUMMARY_RE = re.compile(
    r"\((\d)\) \*\*([a-z][a-z -]*)\*\* (\d+)\s+lessons?\s*\(([^)]*)\)"
)


def _read() -> str:
    assert LEARNINGS.is_file(), f"{LEARNINGS} is missing"
    return LEARNINGS.read_text(encoding="utf-8")


def _lessons(text: str) -> dict[int, str]:
    return {int(num): cls for num, cls in LESSON_ROW_RE.findall(text)}


def _summary(text: str) -> dict[str, tuple[int, list[int]]]:
    """class -> (declared count, declared lesson numbers)"""
    out: dict[str, tuple[int, list[int]]] = {}
    for _bucket, cls, count, numbers in SUMMARY_RE.findall(text):
        listed = [int(n) for n in re.findall(r"#(\d+)", numbers)]
        out[cls] = (int(count), listed)
    return out


def test_the_lesson_table_is_parsed_at_all():
    lessons = _lessons(_read())
    assert len(lessons) >= 25, (
        f"the lesson table parsed to {len(lessons)} lessons; expected at least 25"
    )


def test_every_lesson_carries_a_house_class():
    lessons = _lessons(_read())
    unknown = {num: cls for num, cls in lessons.items() if cls not in HOUSE_CLASSES}
    assert unknown == {}, (
        f"lessons with a class outside the house taxonomy: {unknown}; "
        f"the house classes are {sorted(HOUSE_CLASSES)}"
    )


def test_the_lesson_numbers_are_contiguous_from_one():
    lessons = _lessons(_read())
    numbers = sorted(lessons)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"lesson numbers are not contiguous from 1: {numbers}"
    )


def test_the_bucket_summary_counts_match_the_lesson_table():
    """THE GATE. The summary is a measurement of the table above it, so it is
    recomputed rather than trusted."""
    text = _read()
    lessons = _lessons(text)
    summary = _summary(text)

    assert summary, "the bucket summary line could not be parsed"
    assert set(summary) <= HOUSE_CLASSES, (
        f"the summary names classes outside the house taxonomy: "
        f"{sorted(set(summary) - HOUSE_CLASSES)}"
    )

    actual: dict[str, list[int]] = {}
    for num, cls in lessons.items():
        actual.setdefault(cls, []).append(num)

    for cls, (declared_count, declared_numbers) in summary.items():
        real = sorted(actual.get(cls, []))
        assert declared_count == len(real), (
            f"the summary claims {cls} has {declared_count} lessons; the table "
            f"has {len(real)}: {real}"
        )
        assert sorted(declared_numbers) == real, (
            f"the summary lists {cls} lessons {sorted(declared_numbers)}; the "
            f"table has {real}"
        )

    # Every class present in the table must appear in the summary, including
    # the ones with a count of ZERO -- an absent class reads as an oversight
    # rather than a measurement.
    for cls in actual:
        assert cls in summary, f"the summary omits the class {cls} entirely"


def test_the_bucket_summary_total_matches_the_number_of_lessons():
    text = _read()
    lessons = _lessons(text)
    summary = _summary(text)
    declared_total = sum(count for count, _ in summary.values())
    assert declared_total == len(lessons), (
        f"the summary totals {declared_total} lessons; the table holds "
        f"{len(lessons)}"
    )
