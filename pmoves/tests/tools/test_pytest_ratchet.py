"""Tests for the python-tests ratchet itself.

The gate this tool replaced reported PASS while running none of the suite, so
the replacement should not be the one untested thing in the repo. These cover
the comparison logic that decides whether CI goes red — pure functions only, no
pytest subprocess and no network.
"""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestDeclaredSlowFiles(unittest.TestCase):
    """A declared-slow file must be MEASURED, not lost.

    The budget model used file COUNT as a proxy for cost, so a healthy but
    slow file was killed by the chunk timeout, killed again by the per-file
    isolation timeout, and then REPORTED AS BROKEN -- the exact inversion this
    gate exists to prevent. `_slow_files.yaml` names the files that are
    legitimately slow, and these tests pin both what it buys and what it must
    NOT buy.
    """

    HARNESS = "pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py"
    OTHER = "pmoves/tests/tools/test_pytest_ratchet.py"
    ALLOWANCE = 600

    def test_the_committed_config_declares_the_harness(self):
        allowances = pytest_ratchet.load_slow_file_allowances()
        self.assertEqual(allowances.get(self.HARNESS), self.ALLOWANCE)

    def test_every_declared_entry_carries_a_reason(self):
        """A declared cost with no stated reason is a budget raise nobody
        signed off on."""
        entries = pytest_ratchet.load_slow_file_entries()
        self.assertTrue(entries)
        for path, (_seconds, reason) in entries.items():
            self.assertTrue(reason.strip(), f"{path} declares no reason")

    def test_a_missing_config_is_an_empty_mapping_not_a_crash(self):
        missing = Path("does") / "not" / "exist.yaml"
        self.assertEqual(pytest_ratchet.load_slow_file_allowances(missing), {})

    def test_chunk_timeout_for_an_allowed_file_is_the_default_plus_the_allowance(self):
        timeout = pytest_ratchet.chunk_timeout_seconds([Path(self.HARNESS)])
        self.assertEqual(
            timeout, pytest_ratchet.GROUP_TIMEOUT_SECONDS + self.ALLOWANCE
        )

    def test_chunk_timeout_without_an_allowance_is_exactly_the_default(self):
        """The default path must be PROVABLY unchanged, not merely unchanged."""
        timeout = pytest_ratchet.chunk_timeout_seconds([Path(self.OTHER)])
        self.assertEqual(timeout, pytest_ratchet.GROUP_TIMEOUT_SECONDS)

    def test_the_chunk_allowance_is_the_sum_over_the_files_in_it(self):
        files = [Path(self.OTHER), Path(self.HARNESS)]
        self.assertEqual(
            pytest_ratchet.chunk_timeout_seconds(files),
            pytest_ratchet.GROUP_TIMEOUT_SECONDS + self.ALLOWANCE,
        )

    def test_file_timeout_for_an_allowed_file_is_the_default_plus_the_allowance(self):
        timeout = pytest_ratchet.file_timeout_seconds(Path(self.HARNESS))
        self.assertEqual(
            timeout, pytest_ratchet.FALLBACK_FILE_TIMEOUT + self.ALLOWANCE
        )

    def test_file_timeout_without_an_allowance_is_exactly_the_default(self):
        timeout = pytest_ratchet.file_timeout_seconds(Path(self.OTHER))
        self.assertEqual(timeout, pytest_ratchet.FALLBACK_FILE_TIMEOUT)

    def test_the_allowance_is_driven_by_the_config_not_by_the_code(self):
        """NEGATIVE CONTROL: remove the entry from the config and the budgets
        fall back to EXACTLY the old values. If this failed, the extra time
        would be hardcoded rather than declared -- and could never be taken
        back."""
        original = pytest_ratchet.SLOW_FILES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = Path(tmp) / "_slow_files.yaml"
                cfg.write_text(
                    "# the harness entry deliberately absent\n"
                    "slow_files:\n"
                    "  pmoves/tests/tools/test_something_else.py: 30\n",
                    encoding="utf-8",
                )
                pytest_ratchet.SLOW_FILES = cfg
                self.assertEqual(
                    pytest_ratchet.chunk_timeout_seconds([Path(self.HARNESS)]),
                    pytest_ratchet.GROUP_TIMEOUT_SECONDS,
                )
                self.assertEqual(
                    pytest_ratchet.file_timeout_seconds(Path(self.HARNESS)),
                    pytest_ratchet.FALLBACK_FILE_TIMEOUT,
                )
        finally:
            pytest_ratchet.SLOW_FILES = original

    def test_the_chunk_run_actually_receives_the_allowance(self):
        """The widened budget must reach the subprocess, not just a helper."""
        captured = {}

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return _Proc()

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pytest_ratchet.subprocess, "run", fake_run):
                pytest_ratchet.run_pytest(
                    [Path(self.HARNESS)], Path(tmp) / "report.xml"
                )
        self.assertEqual(
            captured.get("timeout"),
            pytest_ratchet.GROUP_TIMEOUT_SECONDS + self.ALLOWANCE,
        )

    def test_the_isolation_pass_gives_the_allowed_file_its_allowance(self):
        """The per-file budget must widen too, or the file is lost TWICE."""
        calls = []

        def fake_run(files, junit, timeout=None):
            calls.append(([str(f) for f in files], timeout))
            if len(files) > 1:
                return -1, "TIMEOUT"
            junit.write_text("<testsuites/>", encoding="utf-8")
            return 0, ""

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pytest_ratchet, "run_pytest", fake_run):
                findings, dead = pytest_ratchet.run_chunk_with_fallback(
                    "grp", [Path(self.HARNESS), Path(self.OTHER)], Path(tmp), 1
                )
        self.assertEqual(dead, [])
        self.assertEqual(findings, [])
        _chunk, *file_calls = calls
        self.assertEqual(
            file_calls[0][1], pytest_ratchet.FALLBACK_FILE_TIMEOUT + self.ALLOWANCE
        )
        self.assertEqual(file_calls[1][1], pytest_ratchet.FALLBACK_FILE_TIMEOUT)


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
