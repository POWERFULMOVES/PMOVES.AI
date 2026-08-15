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
