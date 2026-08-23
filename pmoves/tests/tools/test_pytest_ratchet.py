"""Tests for the python-tests ratchet itself.

The gate this tool replaced reported PASS while running none of the suite, so
the replacement should not be the one untested thing in the repo. These cover
the comparison logic that decides whether CI goes red — pure functions only, no
pytest subprocess and no network.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pmoves" / "tools"))

import pytest_ratchet  # noqa: E402


F_FAIL = {"kind": "FAIL", "where": "tests.test_thing", "name": "test_a", "detail": "x"}
F_ERR = {"kind": "ERROR", "where": "tests.test_broken", "name": "<collection-error>", "detail": "y"}


class TestKey(unittest.TestCase):
    def test_key_shape_matches_the_other_ratchets(self):
        self.assertEqual(pytest_ratchet._key(F_FAIL), "FAIL|tests.test_thing|test_a")
        self.assertEqual(
            pytest_ratchet._key(F_ERR), "ERROR|tests.test_broken|<collection-error>"
        )

    def test_key_ignores_the_failure_message(self):
        """Messages change with library versions; the set of broken things does not."""
        a = dict(F_FAIL, detail="AssertionError: 1 != 2")
        b = dict(F_FAIL, detail="AssertionError: 3 != 4")
        self.assertEqual(pytest_ratchet._key(a), pytest_ratchet._key(b))


class TestBaselineRoundTrip(unittest.TestCase):
    def test_written_baseline_loads_back_identically(self):
        original = pytest_ratchet.BASELINE
        try:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                pytest_ratchet.BASELINE = Path(tmp) / "b.yaml"
                pytest_ratchet.write_baseline([F_FAIL, F_ERR])
                loaded = pytest_ratchet.load_baseline()
            self.assertEqual(
                loaded, {pytest_ratchet._key(F_FAIL), pytest_ratchet._key(F_ERR)}
            )
        finally:
            pytest_ratchet.BASELINE = original

    def test_missing_baseline_is_an_empty_set_not_a_crash(self):
        original = pytest_ratchet.BASELINE
        try:
            pytest_ratchet.BASELINE = Path("does") / "not" / "exist.yaml"
            self.assertEqual(pytest_ratchet.load_baseline(), set())
        finally:
            pytest_ratchet.BASELINE = original

    def test_the_committed_baseline_parses(self):
        """The real file must load — an unparseable baseline would silently
        become an empty set, i.e. every finding 'new'."""
        self.assertTrue(pytest_ratchet.BASELINE.is_file())
        self.assertGreater(len(pytest_ratchet.load_baseline()), 0)


class TestRatchetDecision(unittest.TestCase):
    """new = fails the build; stale = also fails, so the count only goes down."""

    @staticmethod
    def _decide(findings, baseline):
        live = {pytest_ratchet._key(f) for f in findings}
        new = [f for f in findings if pytest_ratchet._key(f) not in baseline]
        stale = sorted(baseline - live)
        return new, stale

    def test_baselined_failure_does_not_fail_the_build(self):
        new, stale = self._decide([F_FAIL], {pytest_ratchet._key(F_FAIL)})
        self.assertEqual((new, stale), ([], []))

    def test_a_new_failure_is_reported(self):
        new, stale = self._decide([F_FAIL, F_ERR], {pytest_ratchet._key(F_FAIL)})
        self.assertEqual([pytest_ratchet._key(f) for f in new], [pytest_ratchet._key(F_ERR)])
        self.assertEqual(stale, [])

    def test_a_fixed_test_still_listed_is_stale(self):
        """The half that makes the count go down: a repaired test must be
        removed from the baseline, so it cannot regress back in silently."""
        new, stale = self._decide([], {pytest_ratchet._key(F_FAIL)})
        self.assertEqual(new, [])
        self.assertEqual(stale, [pytest_ratchet._key(F_FAIL)])

    def test_empty_baseline_makes_everything_new(self):
        new, stale = self._decide([F_FAIL, F_ERR], set())
        self.assertEqual(len(new), 2)
        self.assertEqual(stale, [])


class TestGrouping(unittest.TestCase):
    def test_chunks_are_bounded(self):
        files = [Path("pmoves/tests") / f"test_{i}.py" for i in range(45)]
        groups = pytest_ratchet.group_files(files)
        self.assertTrue(all(len(v) <= pytest_ratchet.CHUNK_SIZE for v in groups.values()))
        self.assertEqual(sum(len(v) for v in groups.values()), 45)

    def test_every_file_lands_in_exactly_one_group(self):
        files = [Path("a/test_1.py"), Path("b/test_2.py"), Path("a/test_3.py")]
        groups = pytest_ratchet.group_files(files)
        placed = [f for v in groups.values() for f in v]
        self.assertEqual(sorted(placed), sorted(files))


if __name__ == "__main__":
    unittest.main()


# ── per-file fallback for a timed-out chunk ─────────────────────────────────
#
# A timed-out chunk is killed before pytest writes its JUnit report, so treating
# the timeout as one opaque "no report" discards every result in the chunk.
# Measured on 2026-08-19: `pmoves/tests [1]` timed out on every run on record,
# and isolating its 20 files per-file recovered 113 findings (104 FAIL, 9 ERROR)
# that had never once been reported, narrowing the unmeasured set to the 3 files
# that actually hang.

class _FakeRun:
    """Stands in for run_pytest: writes a report for every file except the hangs."""

    def __init__(self, hangs, chunk_times_out=True):
        self.hangs = set(hangs)
        self.chunk_times_out = chunk_times_out
        self.calls = []

    def __call__(self, files, junit, timeout=None):
        self.calls.append(([str(f) for f in files], timeout))
        if len(files) > 1:
            if self.chunk_times_out:
                return -1, "TIMEOUT"
            junit.write_text("<testsuites/>", encoding="utf-8")
            return 0, ""
        if str(files[0]) in self.hangs:
            return -1, "TIMEOUT"
        junit.write_text("<testsuites/>", encoding="utf-8")
        return 0, ""


def _run_fallback(monkeypatch, tmp_path, files, fake, parsed=None):
    monkeypatch.setattr(pytest_ratchet, "run_pytest", fake)
    monkeypatch.setattr(pytest_ratchet, "parse_junit",
                        lambda j: list(parsed or []))
    return pytest_ratchet.run_chunk_with_fallback("grp", [Path(f) for f in files], tmp_path, 1)


def test_timed_out_chunk_is_retried_per_file(monkeypatch, tmp_path):
    files = ["a.py", "b.py", "c.py"]
    fake = _FakeRun(hangs=[])
    findings, dead = _run_fallback(monkeypatch, tmp_path, files, fake)
    assert dead == []
    # one chunk attempt + one per file
    assert len(fake.calls) == 1 + len(files)


def test_only_the_hanging_file_stays_unmeasured(monkeypatch, tmp_path):
    """The whole point: 1 hang must not cost the other files their results."""
    files = ["a.py", "hang.py", "c.py"]
    fake = _FakeRun(hangs=["hang.py"])
    findings, dead = _run_fallback(monkeypatch, tmp_path, files, fake)
    assert dead == ["hang.py"]


def test_dead_label_names_the_file_not_the_chunk(monkeypatch, tmp_path):
    """A positional label like `pmoves/tests [1]` cannot tell anyone WHAT hangs."""
    fake = _FakeRun(hangs=["hang.py"])
    _, dead = _run_fallback(monkeypatch, tmp_path, ["a.py", "hang.py"], fake)
    assert dead == ["hang.py"]
    assert not any("[" in d for d in dead)


def test_findings_from_reporting_files_are_kept(monkeypatch, tmp_path):
    fake = _FakeRun(hangs=["hang.py"])
    finding = {"kind": "FAIL", "where": "x", "name": "y", "detail": ""}
    findings, _ = _run_fallback(monkeypatch, tmp_path, ["a.py", "hang.py"], fake,
                                parsed=[finding])
    # a.py reports (1 finding); hang.py does not
    assert findings == [finding]


def test_fallback_uses_the_shorter_per_file_timeout(monkeypatch, tmp_path):
    fake = _FakeRun(hangs=[])
    _run_fallback(monkeypatch, tmp_path, ["a.py", "b.py"], fake)
    chunk_call, *file_calls = fake.calls
    assert chunk_call[1] is None                      # chunk uses the group default
    assert all(t == pytest_ratchet.FALLBACK_FILE_TIMEOUT for _, t in file_calls)


def test_no_fallback_when_the_chunk_reports(monkeypatch, tmp_path):
    """A healthy chunk must not pay the isolation cost."""
    fake = _FakeRun(hangs=[], chunk_times_out=False)
    findings, dead = _run_fallback(monkeypatch, tmp_path, ["a.py", "b.py"], fake)
    assert dead == []
    assert len(fake.calls) == 1


def test_non_timeout_failure_is_not_retried(monkeypatch, tmp_path):
    """An unimportable conftest fails identically per file — isolating it would
    burn the budget to learn nothing, so the group is reported as-is."""
    def broken(files, junit, timeout=None):
        return 4, "conftest ImportError"
    monkeypatch.setattr(pytest_ratchet, "run_pytest", broken)
    findings, dead = pytest_ratchet.run_chunk_with_fallback(
        "grp", [Path("a.py"), Path("b.py")], tmp_path, 1)
    assert dead == ["grp"] and findings == []


def test_single_file_group_is_not_retried(monkeypatch, tmp_path):
    fake = _FakeRun(hangs=["only.py"])
    findings, dead = _run_fallback(monkeypatch, tmp_path, ["only.py"], fake)
    assert dead == ["grp"]
    assert len(fake.calls) == 1


def test_budget_exhaustion_reports_the_rest_as_unmeasured(monkeypatch, tmp_path):
    """Stopping silently at the budget would reintroduce exactly the defect this
    function exists to fix."""
    monkeypatch.setattr(pytest_ratchet, "FALLBACK_BUDGET_SECONDS", 0)
    fake = _FakeRun(hangs=[])
    findings, dead = _run_fallback(monkeypatch, tmp_path, ["a.py", "b.py"], fake)
    assert set(dead) == {"a.py", "b.py"}
    assert len(fake.calls) == 1        # chunk only; no file ever ran
