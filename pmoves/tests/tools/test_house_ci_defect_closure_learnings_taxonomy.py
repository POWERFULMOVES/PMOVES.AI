"""The LEARNINGS bucket summary is a MEASUREMENT, so it needs a gate of its own.

``pmoves/docs/AGENTS/house_ci_defect_closure_LEARNINGS.md`` ends with a
"Bucket summary" section: a per-class tally of the lesson table above it, with
each class's member LIST. It also carries a "What shipped" table whose rows
state per-suite test and mutation counts.

A summary that claims to BE a measurement needs a gate that recomputes it.
Otherwise it is prose that rots: a lesson is added, the table grows, the summary
keeps the old number, and the document reads as authoritative while being wrong.

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

THE "WHAT SHIPPED" COUNTS ARE MEASUREMENTS TOO
----------------------------------------------
Each F-row states how many behavioural test functions and how many mutation
kills a gate ships. Those are recomputed by AST:

* the behavioural count is the number of `test_*` functions in the file the row
  cites;
* the mutation count is the number of `Mutation(...)` entries in the harness the
  row cites WHOSE `target_test` names a test in THAT ROW'S behavioural file.

The second rule matters because one harness can serve two gates: the deploy
workflow carries BOTH the compose-mirror gate and the change-detection gate, and
a naive "count every Mutation in the harness" would charge each row for the
other row's kills.

Hermetic: reads files in this repo, writes nothing.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LEARNINGS = (
    REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "house_ci_defect_closure_LEARNINGS.md"
)

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

# A "What shipped" row: | F1 | prose | **6** behavioural tests and **6** mutation kills | files |
_F_ROW = re.compile(
    r"^\|\s*(?P<label>F\d+[a-z]?)\s*\|(?P<body>[^|]*)\|(?P<files>[^|]*)\|\s*$",
    re.MULTILINE,
)

_STATED_TESTS = re.compile(r"(\d+)\s+behavioural test")
_STATED_MUTATIONS = re.compile(r"(\d+)\s+mutation kill")

# The lane total: **Total: 15 behavioural test functions and 13 mutation kills ...**
_TOTAL_ROW = re.compile(
    r"\*\*Total:\s*(?P<tests>\d+)\s+behavioural test functions\s+and\s+"
    r"(?P<mutations>\d+)\s+mutation kills"
)


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


# ---------------------------------------------------------------------------
# The "What shipped" counts (rows F1..Fn) are MEASUREMENTS too, so they get a
# gate of their own: the same "a number in prose is a claim" rule as the bucket
# summary above.
# ---------------------------------------------------------------------------


def _count_test_functions(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def _test_function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _mutation_target_tests(path: Path) -> list[str]:
    """The `target_test` of every `Mutation(...)` entry in a harness.

    The value is read from the CALL's keyword argument -- not from a re-typed
    list -- so the count follows the harness as it changes.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "Mutation":
            continue
        for keyword in node.keywords:
            if keyword.arg == "target_test":
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    targets.append(value.value)
    return targets


def _cited_paths(files_cell: str) -> list[Path]:
    cited = re.findall(r"`([^`]+\.py)`", files_cell)
    out = []
    for rel in cited:
        path = REPO_ROOT / rel
        assert path.exists(), f"the row cites a file that does not exist: {rel}"
        out.append(path)
    return out


def test_every_shipped_row_count_is_the_measured_one():
    """A row that states a per-suite count is a MEASUREMENT.

    The counts are recomputed by AST from the files the row cites, so a suite
    that grew -- or a row that names the wrong suite -- fails the gate instead
    of sitting there as a stale claim.
    """
    text = LEARNINGS.read_text(encoding="utf-8")

    checked = 0
    for match in _F_ROW.finditer(text):
        label = match.group("label")
        body = match.group("body")
        files_cell = match.group("files")

        stated_tests = _STATED_TESTS.search(body)
        stated_mutations = _STATED_MUTATIONS.search(body)
        if stated_tests is None and stated_mutations is None:
            continue

        cited = _cited_paths(files_cell)
        assert cited, (
            f"{label} states a count but cites no .py file; the count cannot be "
            f"recomputed"
        )

        # A HARNESS is the file that declares `Mutation(...)` entries. A
        # BEHAVIOURAL file is the one that does not. Classifying by the
        # mutation entries rather than by the filename is what lets one
        # harness serve two rows without either row being charged for the
        # other's kills.
        harnesses = [p for p in cited if _mutation_target_tests(p)]
        behavioural = [
            p
            for p in cited
            if p not in harnesses and _count_test_functions(p) > 0
        ]

        if stated_tests is not None:
            assert len(behavioural) == 1, (
                f"{label} states a behavioural-test count but cites "
                f"{len(behavioural)} behavioural file(s); the row must name exactly one"
            )
            measured = _count_test_functions(behavioural[0])
            assert int(stated_tests.group(1)) == measured, (
                f"{label} claims {stated_tests.group(1)} behavioural tests for "
                f"{behavioural[0].name}; the tree has {measured}"
            )

        if stated_mutations is not None:
            assert len(harnesses) == 1, (
                f"{label} states a mutation-kill count but cites "
                f"{len(harnesses)} harness file(s); the row must name exactly one"
            )
            assert behavioural, (
                f"{label} states a mutation-kill count but cites no behavioural "
                f"file, so the harness's kills cannot be attributed to it"
            )
            names = _test_function_names(behavioural[0])
            measured = sum(
                1 for target in _mutation_target_tests(harnesses[0]) if target in names
            )
            assert int(stated_mutations.group(1)) == measured, (
                f"{label} claims {stated_mutations.group(1)} mutation kills for "
                f"{behavioural[0].name}; the harness holds {measured} whose "
                f"target_test names one of that file's tests"
            )
        checked += 1

    assert checked >= 3, (
        f"only {checked} shipped rows were checked; this lane ships three gates "
        f"that state a count, and every one of them must be recomputed"
    )


def test_the_lane_total_is_the_measured_total():
    """The lane total is the sum of its rows -- and it is recomputed, not read."""
    text = LEARNINGS.read_text(encoding="utf-8")
    m = _TOTAL_ROW.search(text)
    assert m, "the 'What shipped' table has no '**Total: N behavioural test functions and N mutation kills**' line"

    total_tests = 0
    total_mutations = 0
    for match in _F_ROW.finditer(text):
        body = match.group("body")
        files_cell = match.group("files")
        stated_tests = _STATED_TESTS.search(body)
        stated_mutations = _STATED_MUTATIONS.search(body)
        if stated_tests is None or stated_mutations is None:
            continue
        cited = _cited_paths(files_cell)
        harnesses = [p for p in cited if _mutation_target_tests(p)]
        behavioural = [
            p
            for p in cited
            if p not in harnesses and _count_test_functions(p) > 0
        ]
        assert len(behavioural) == 1 and len(harnesses) == 1, (
            f"row {match.group('label')} does not name exactly one behavioural "
            f"file and one harness"
        )
        names = _test_function_names(behavioural[0])
        total_tests += _count_test_functions(behavioural[0])
        total_mutations += sum(
            1 for target in _mutation_target_tests(harnesses[0]) if target in names
        )

    assert int(m.group("tests")) == total_tests, (
        f"the lane total claims {m.group('tests')} behavioural test functions; "
        f"the rows add up to {total_tests}"
    )
    assert int(m.group("mutations")) == total_mutations, (
        f"the lane total claims {m.group('mutations')} mutation kills; the rows "
        f"add up to {total_mutations}"
    )
