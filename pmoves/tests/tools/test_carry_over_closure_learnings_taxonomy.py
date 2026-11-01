"""The LEARNINGS bucket summary is a MEASUREMENT, so it needs a gate of its own.

``pmoves/docs/AGENTS/carry_over_closure_LEARNINGS.md`` ends with a
"Bucket summary" section: a per-class tally of the lesson table above it,
with each class's member LIST.

A summary that claims to BE a measurement needs a gate that recomputes it.
Otherwise it is prose that rots: a lesson is added, the table grows, the
summary keeps the old number, and the document reads as authoritative while
being wrong.

So this test does not assert a number someone typed. It PARSES the lesson
table, derives the counts, the total, and each class's member list, and
compares them with what the summary section claims.

Three things are checked, because a count that is right while the list is
wrong is still a wrong summary:

1. every row's CLASS is one of the five house classes, and every house class
   is DECLARED in the summary -- including the ones with zero members, whose
   absence would read as an oversight rather than a measurement;
2. each class's COUNT and MEMBER LIST match the parsed table;
3. the stated TOTAL matches the number of rows.

The lesson numbers in the member lists are parsed as integers, so a list that
names a lesson which does not exist is caught too.

Hermetic: reads one file in this repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEARNINGS = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "carry_over_closure_LEARNINGS.md"

# The five house classes, in taxonomy order. A class with no lessons is still
# declared in the summary -- that is what makes "we considered it and it is
# empty" different from "nobody looked".
HOUSE_CLASSES = (
    "reasoning-gap",
    "semantic-naming drift",
    "contract-correctness",
    "defense-in-depth",
    "pattern-conformance",
)

LESSON_ROW = re.compile(
    r"^\|\s*(?P<num>\d+)\s*\|\s*\*\*(?P<cls>[^*]+)\*\*\s*\|",
    re.MULTILINE,
)

SUMMARY_ROW = re.compile(
    r"^\|\s*(?P<cls>[^|]+?)\s*\|\s*(?P<count>\d+)\s*\|\s*(?P<members>[^|]*?)\s*\|\s*$",
    re.MULTILINE,
)

TOTAL_LINE = re.compile(r"\*\*Total lessons:\s*(?P<total>\d+)\*\*")


def _lesson_rows() -> list[tuple[int, str]]:
    text = LEARNINGS.read_text(encoding="utf-8")
    return [(int(m.group("num")), m.group("cls").strip()) for m in LESSON_ROW.finditer(text)]


def _summary_rows() -> dict[str, tuple[int, list[int]]]:
    text = LEARNINGS.read_text(encoding="utf-8")
    start = text.find("## Bucket summary")
    assert start != -1, "the LEARNINGS file has no '## Bucket summary' section"
    body = text[start:]
    out: dict[str, tuple[int, list[int]]] = {}
    for m in SUMMARY_ROW.finditer(body):
        cls = m.group("cls").strip()
        if cls == "Class":
            continue
        members_raw = m.group("members").strip()
        if members_raw in {"—", "-", ""}:
            members: list[int] = []
        else:
            members = [int(x) for x in re.findall(r"\d+", members_raw)]
        out[cls] = (int(m.group("count")), members)
    return out


def test_the_learnings_file_exists():
    assert LEARNINGS.exists(), f"missing LEARNINGS file: {LEARNINGS}"


def test_every_lesson_class_is_a_house_class():
    rows = _lesson_rows()
    assert rows, "the lesson table parsed as empty -- the table shape changed"
    for num, cls in rows:
        assert cls in HOUSE_CLASSES, f"lesson {num} has unknown class {cls!r}"


def test_the_lesson_numbers_are_contiguous_and_unique():
    nums = [num for num, _cls in _lesson_rows()]
    assert nums == sorted(nums), "the lesson table is not in ascending order"
    assert len(set(nums)) == len(nums), "duplicate lesson numbers"
    assert nums == list(range(1, len(nums) + 1)), (
        f"lesson numbers are not contiguous from 1: {nums}"
    )


def test_the_summary_declares_every_house_class():
    """A class with zero members must still be DECLARED."""
    summary = _summary_rows()
    for cls in HOUSE_CLASSES:
        assert cls in summary, f"house class {cls!r} is not declared in the bucket summary"


def test_the_summary_counts_match_the_lesson_table():
    rows = _lesson_rows()
    summary = _summary_rows()
    for cls in HOUSE_CLASSES:
        expected = [num for num, row_cls in rows if row_cls == cls]
        assert cls in summary, cls
        count, members = summary[cls]
        assert count == len(expected), (
            f"class {cls!r}: summary says {count} lesson(s), the table has {len(expected)}"
        )
        assert members == expected, (
            f"class {cls!r}: summary lists members {members}, the table has {expected}"
        )


def test_the_summary_total_matches_the_lesson_table():
    rows = _lesson_rows()
    text = LEARNINGS.read_text(encoding="utf-8")
    m = TOTAL_LINE.search(text)
    assert m, "the summary has no '**Total lessons: N**' line"
    assert int(m.group("total")) == len(rows), (
        f"the summary claims {m.group('total')} lessons; the table has {len(rows)}"
    )


def test_the_summary_counts_sum_to_the_total():
    summary = _summary_rows()
    assert sum(count for count, _members in summary.values()) == len(_lesson_rows())


@pytest.mark.parametrize("cls", HOUSE_CLASSES)
def test_each_declared_class_row_is_well_formed(cls):
    summary = _summary_rows()
    assert cls in summary, cls
    count, members = summary[cls]
    assert count >= 0
    assert len(members) == count, (
        f"class {cls!r}: {count} lesson(s) declared but {len(members)} member(s) listed"
    )
