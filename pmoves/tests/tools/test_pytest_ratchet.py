"""Tests for the python-tests ratchet itself.

The gate this tool replaced reported PASS while running none of the suite, so
the replacement should not be the one untested thing in the repo. These cover
the comparison logic that decides whether CI goes red — pure functions only, no
pytest subprocess and no network.
"""
import ast
import io
import re
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

    #: The four mutation harnesses this lane added, with the allowance each
    #: was given. MEASURED on this host (Windows, Python 3.12.10, pytest
    #: 9.1.1) with the ratchet's OWN invocation
    #: (pmoves/tools/pytest_ratchet.py:run_pytest): the encoding harness
    #: 102.6s, the mmx harness 80.5s, the gh-app harness 41.4s, the
    #: image-staleness harness 39.6s. The basis for each number is stated in
    #: pmoves/configs/pytest_ratchet/_slow_files.yaml.
    LANE_ENTRIES = {
        "pmoves/tests/tools/test_windows_encoding_ratchet_mutation_kill.py": 200,
        "pmoves/tests/tools/test_mmx_surface_parity_mutation_kill.py": 450,
        "pmoves/tests/tools/test_gh_app_installation_audit_mutation_kill.py": 60,
        "pmoves/tools/tests/test_image_staleness_ratchet_mutation_kill.py": 60,
    }

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

    def test_every_declared_path_exists_in_the_tree(self):
        """A declared path that no longer exists is a STALE budget raise: it
        keeps widening the budget of a chunk that no longer contains it, and
        it hides the fact that the file it was written for is gone."""
        entries = pytest_ratchet.load_slow_file_entries()
        missing = [
            path for path in entries
            if not (pytest_ratchet.REPO_ROOT / path).is_file()
        ]
        self.assertEqual(missing, [], f"declared-slow paths that do not exist: {missing}")

    def test_every_declared_path_is_a_test_file(self):
        """The ratchet only ever runs TEST files, so only a test file can be
        the thing whose budget needed widening."""
        entries = pytest_ratchet.load_slow_file_entries()
        not_tests = [
            path for path in entries
            if not Path(path).name.startswith("test_")
        ]
        self.assertEqual(not_tests, [], f"declared-slow paths that are not test files: {not_tests}")

    def test_the_lane_harnesses_are_declared_with_their_measured_allowances(self):
        """The four mutation harnesses this lane added, with the allowance
        each was given.

        MEASURED on this host (Windows, Python 3.12.10, pytest 9.1.1) with the
        ratchet's OWN invocation (pmoves/tools/pytest_ratchet.py:run_pytest):
        the encoding harness 102.6s, the mmx harness 80.5s, the gh-app
        harness 41.4s, the image-staleness harness 39.6s. The basis for each
        number is stated in pmoves/configs/pytest_ratchet/_slow_files.yaml.
        """
        allowances = pytest_ratchet.load_slow_file_allowances()
        for path, expected in self.LANE_ENTRIES.items():
            self.assertEqual(allowances.get(path), expected, path)

    def test_the_lane_allowances_widen_the_chunk_that_holds_each_harness(self):
        """The allowance must reach the CHUNK, not just the file. The chunk
        is what binds: the tools [3] chunk measured 284.7s against a 120s
        budget, so a per-file allowance alone would still have been killed.
        """
        groups = pytest_ratchet.group_files(pytest_ratchet.discover_test_files())
        for key, members in groups.items():
            for path, allowance in self.LANE_ENTRIES.items():
                if not any(str(m).replace("\\", "/").endswith(path) for m in members):
                    continue
                budget = pytest_ratchet.chunk_timeout_seconds(members)
                self.assertGreaterEqual(
                    budget,
                    pytest_ratchet.GROUP_TIMEOUT_SECONDS + allowance,
                    f"{key} does not carry the allowance for {path}",
                )

    def test_a_declared_mutation_count_is_the_measured_one(self):
        """A mutation count in the config's WHY block is a CLAIM.

        MEASURED 2026-11-02, on the review of this pull request: the config
        said the encoding harness "has 7 mutations" and "costs 21 pytest
        startups", and the harness defines FIFTEEN -- so the basis was
        fiction. The allowance was never sized on that arithmetic, but the
        block is what a future editor re-reads when re-sizing the budget,
        and a file whose own footer says "a number in prose is a claim"
        cannot hold one.
        """
        entries = pytest_ratchet.load_slow_file_entries()
        checked = 0
        for path, (_seconds, reason) in entries.items():
            match = re.search(r"(\d+)\s+mutations?\b", reason)
            if match is None:
                continue
            harness = pytest_ratchet.REPO_ROOT / path
            self.assertTrue(harness.is_file(), f"{path} does not exist")
            measured = self._count_mutations(harness)
            self.assertEqual(
                int(match.group(1)),
                measured,
                f"{path}'s config reason claims {match.group(1)} mutations; "
                f"the file defines {measured}",
            )
            checked += 1
        self.assertGreater(checked, 0, "no declared entry states a mutation count")

    @staticmethod
    def _count_mutations(path: Path) -> int:
        """Count `Mutation(...)` entries by AST -- the same shape the
        lane's own asset-count gate uses."""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        total = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "Mutation":
                    total += 1
        return total

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

    def test_the_isolation_PASS_budget_is_allowance_aware(self):
        """THE ESCAPE HATCH MUST NOT HAVE A TRAPDOOR.

        The per-file budget is FALLBACK_FILE_TIMEOUT + allowance, so ONE
        declared-slow file can legally consume more than the flat pass
        budget on its own. If the pass still counted in the old currency it
        could exhaust its budget BEFORE reaching that file -- and the
        "fallback budget exhausted" path would then re-declare the very file
        the allowance exists to defend as BROKEN, with less signal than
        before.
        """
        self.assertEqual(
            pytest_ratchet.fallback_budget_seconds([Path(self.HARNESS)]),
            pytest_ratchet.FALLBACK_BUDGET_SECONDS + self.ALLOWANCE,
        )

    def test_a_declared_slow_file_is_still_measured_when_the_pass_budget_is_gone(self):
        """THE SAME THING, THROUGH THE WIRING.

        A test that only exercises the pure helper would still be GREEN if
        the CALL SITE reverted to the flat budget -- the helper would be
        intact and correct while the runner kept using the old currency.
        So this drives `run_chunk_with_fallback` itself, with the pass
        budget already exhausted, and requires the declared-slow file to
        still be MEASURED rather than declared dead.

        With the flat budget the loop breaks on its first check and the file
        lands in `dead` -- which the runner reports as BROKEN. That is the
        trapdoor, and it is exactly what this test forbids.
        """
        calls = []

        def fake_run(files, junit, timeout=None):
            calls.append(([str(f) for f in files], timeout))
            if len(files) > 1:
                # The CHUNK times out, so the isolation pass runs.
                return -1, "TIMEOUT"
            junit.write_text("<testsuites/>", encoding="utf-8")
            return 0, ""

        original = pytest_ratchet.FALLBACK_BUDGET_SECONDS
        try:
            # The pass budget is already spent.
            pytest_ratchet.FALLBACK_BUDGET_SECONDS = 0
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.object(pytest_ratchet, "run_pytest", fake_run):
                    findings, dead = pytest_ratchet.run_chunk_with_fallback(
                        "grp",
                        [Path(self.HARNESS), Path(self.OTHER)],
                        Path(tmp),
                        1,
                    )
        finally:
            pytest_ratchet.FALLBACK_BUDGET_SECONDS = original
        self.assertEqual(
            dead, [],
            "the declared-slow file was declared BROKEN because the flat "
            "pass budget was exhausted -- the allowance has a trapdoor",
        )
        self.assertEqual(findings, [])
        measured = [
            f.replace(chr(92), "/") for call, _timeout in calls for f in call
        ]
        self.assertIn(self.HARNESS, measured, "the isolation pass never ran")

    def test_the_isolation_PASS_budget_without_an_allowance_is_exactly_the_default(self):
        """The default path must be PROVABLY unchanged."""
        self.assertEqual(
            pytest_ratchet.fallback_budget_seconds([Path(self.OTHER)]),
            pytest_ratchet.FALLBACK_BUDGET_SECONDS,
        )

    def test_the_isolation_PASS_budget_is_the_sum_over_the_files_in_the_chunk(self):
        self.assertEqual(
            pytest_ratchet.fallback_budget_seconds(
                [Path(self.OTHER), Path(self.HARNESS)]
            ),
            pytest_ratchet.FALLBACK_BUDGET_SECONDS + self.ALLOWANCE,
        )

    def test_the_pass_budget_falls_back_exactly_when_the_entry_is_removed(self):
        """NEGATIVE CONTROL for the pass budget: with the entry gone from the
        config, the pass budget falls back to EXACTLY the old value."""
        original = pytest_ratchet.SLOW_FILES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cfg = Path(tmp) / "_slow_files.yaml"
                cfg.write_text(
                    "slow_files:\n"
                    "  pmoves/tests/tools/test_something_else.py: 30\n",
                    encoding="utf-8",
                )
                pytest_ratchet.SLOW_FILES = cfg
                self.assertEqual(
                    pytest_ratchet.fallback_budget_seconds([Path(self.HARNESS)]),
                    pytest_ratchet.FALLBACK_BUDGET_SECONDS,
                )
        finally:
            pytest_ratchet.SLOW_FILES = original

    def test_an_unparseable_entry_is_reported_not_silently_dropped(self):
        """A budget-owning line that fails to parse must NOT vanish.

        A typo'd path means the file silently loses its allowance, and CI
        re-reports it as BROKEN with less signal than before. The parser
        quotes the raw line so the mistake is visible.
        """
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "_slow_files.yaml"
            cfg.write_text(
                "slow_files:\n"
                "  pmoves/tests/tools/test_typo.py: 600s\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with mock.patch.object(pytest_ratchet.sys, "stderr", stderr):
                entries = pytest_ratchet.load_slow_file_entries(cfg)
        self.assertEqual(entries, {})
        self.assertIn("test_typo.py", stderr.getvalue())
        self.assertIn("600s", stderr.getvalue())

    def test_a_prose_line_outside_the_block_is_not_reported(self):
        """Only a line INSIDE the block is a budget-owning line. A top-level
        key that is not `slow_files:` is not this parser's business."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "_slow_files.yaml"
            cfg.write_text(
                "other_section:\n"
                "  something: not-a-number\n"
                "slow_files:\n"
                "  pmoves/tests/tools/test_ok.py: 30\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with mock.patch.object(pytest_ratchet.sys, "stderr", stderr):
                entries = pytest_ratchet.load_slow_file_entries(cfg)
        self.assertIn("pmoves/tests/tools/test_ok.py", entries)
        self.assertNotIn("not-a-number", stderr.getvalue())


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
    burn the budget to learn nothing, so the group is reported as-is: as
    UNMEASURED (never baselinable), not as a dead label."""
    calls = []

    def broken(files, junit, timeout=None):
        calls.append(files)
        return 4, "conftest ImportError"
    monkeypatch.setattr(pytest_ratchet, "run_pytest", broken)
    findings, dead = pytest_ratchet.run_chunk_with_fallback(
        "grp", [Path("a.py"), Path("b.py")], tmp_path, 1)
    assert dead == [] and len(calls) == 1
    assert [f["kind"] for f in findings] == [pytest_ratchet.UNMEASURED]
    assert "a.py" in findings[0]["detail"] and "b.py" in findings[0]["detail"]


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


# ── an ABORTED chunk is unmeasured, not "clean" ─────────────────────────────
#
# Measured 2026-11-21: pmoves/tools/test_all_tts_engines.py called sys.exit(1)
# at import. pytest turned that into an INTERNALERROR (exit 3) for the whole
# session, and its JUnit report held one pseudo-testcase, `ERROR|pytest|internal`.
# That key was baselined, so a whole 20-file chunk sat unmeasured behind it, and
# 11 baselined semantic-cache errors read as "stale" (fixed) as soon as an
# unrelated PR moved them into that chunk.

INTERNAL = {"kind": "ERROR", "where": "pytest", "name": "internal", "detail": ""}


class _AbortingRun:
    """Writes a report for every unit; units containing `bad` exit 3 (INTERNALERROR)."""

    def __init__(self, bad, rc=3):
        self.bad, self.rc, self.calls = set(bad), rc, []

    def __call__(self, files, junit, timeout=None):
        names = [str(f) for f in files]
        self.calls.append(names)
        junit.write_text("<testsuites/>", encoding="utf-8")
        return (self.rc, "INTERNALERROR> SystemExit: 1") if self.bad & set(names) else (0, "")


def test_aborted_chunk_is_isolated_per_file(monkeypatch, tmp_path):
    """The abort is one file's fault; the other files must still report."""
    fake = _AbortingRun(bad=["exits.py"])
    finding = {"kind": "FAIL", "where": "x", "name": "y", "detail": ""}
    findings, dead = _run_fallback(monkeypatch, tmp_path,
                                   ["a.py", "exits.py", "c.py"], fake, parsed=[finding])
    assert len(fake.calls) == 1 + 3
    assert dead == []
    # a.py and c.py report; exits.py is unmeasured and named
    assert findings.count(finding) == 2
    um = [f for f in findings if f["kind"] == pytest_ratchet.UNMEASURED]
    assert [f["where"] for f in um] == ["exits.py"]
    assert "internal error" in um[0]["detail"]


def test_aborted_report_is_not_trusted(monkeypatch, tmp_path):
    """The `pytest|internal` pseudo-testcase from an aborted report must never
    reach the findings, where one baseline key could absorb any number of
    wiped chunks."""
    fake = _AbortingRun(bad=["exits.py"])
    findings, _ = _run_fallback(monkeypatch, tmp_path, ["exits.py"], fake,
                                parsed=[INTERNAL])
    assert INTERNAL not in findings
    assert [f["kind"] for f in findings] == [pytest_ratchet.UNMEASURED]


def test_aborted_single_file_is_unmeasured_not_dead(monkeypatch, tmp_path):
    fake = _AbortingRun(bad=["only.py"])
    findings, dead = _run_fallback(monkeypatch, tmp_path, ["only.py"], fake)
    assert dead == [] and len(fake.calls) == 1
    assert findings[0]["kind"] == pytest_ratchet.UNMEASURED
    assert findings[0]["where"] == "grp" and "only.py" in findings[0]["detail"]


def test_every_aborted_exit_code_is_distrusted(monkeypatch, tmp_path):
    for rc in pytest_ratchet.ABORTED_EXIT_CODES:
        fake = _AbortingRun(bad=["x.py"], rc=rc)
        findings, _ = _run_fallback(monkeypatch, tmp_path, ["x.py"], fake,
                                    parsed=[INTERNAL])
        assert [f["kind"] for f in findings] == [pytest_ratchet.UNMEASURED], rc


def test_a_healthy_report_is_still_trusted(monkeypatch, tmp_path):
    """Exit 1 (tests failed) and 5 (nothing collected) are complete reports."""
    for rc in (0, 1, 5):
        def run(files, junit, timeout=None, rc=rc):
            junit.write_text("<testsuites/>", encoding="utf-8")
            return rc, ""
        findings, dead = _run_fallback(monkeypatch, tmp_path, ["a.py", "b.py"], run,
                                       parsed=[F_FAIL])
        assert (findings, dead) == ([F_FAIL], []), rc


def _main(monkeypatch, capsys, chunk_findings, baseline, argv=()):
    monkeypatch.setattr(pytest_ratchet, "discover_test_files", lambda: [Path("a.py")])
    monkeypatch.setattr(pytest_ratchet, "group_files", lambda files: {"grp": files})
    monkeypatch.setattr(pytest_ratchet, "run_chunk_with_fallback",
                        lambda *a: (list(chunk_findings), []))
    monkeypatch.setattr(pytest_ratchet, "load_baseline", lambda: set(baseline))
    written = []
    monkeypatch.setattr(pytest_ratchet, "write_baseline", written.append)
    monkeypatch.setattr(sys, "argv", ["pytest_ratchet.py", *argv])
    rc = pytest_ratchet.main()
    return rc, capsys.readouterr().out, written


UM = {"kind": "UNMEASURED", "where": "pmoves [4]", "name": "<pytest-harness>",
      "detail": "exit 3 (internal error); unmeasured: a.py"}


def test_unmeasured_fails_the_gate_even_if_baselined(monkeypatch, capsys):
    rc, out, _ = _main(monkeypatch, capsys, [UM, F_FAIL],
                       {pytest_ratchet._key(UM), pytest_ratchet._key(F_FAIL)})
    assert rc == 1
    assert "UNMEASURED" in out and "pmoves [4]" in out and "a.py" in out
    assert "PASS" not in out


def test_unmeasured_is_not_counted_as_a_finding(monkeypatch, capsys):
    """Otherwise it would also show as NEW and invite a re-baseline."""
    rc, out, _ = _main(monkeypatch, capsys, [UM], set())
    assert rc == 1
    assert "0 total" in out and "NEW failures" not in out


def test_unmeasured_fails_json_mode(monkeypatch, capsys):
    import json
    rc, out, _ = _main(monkeypatch, capsys, [UM], set(), argv=["--json"])
    payload = json.loads(out[out.index("{"):])
    assert rc == 1 and payload["unmeasured"] == [UM] and payload["new"] == []


def test_baseline_is_not_written_while_units_are_unmeasured(monkeypatch, capsys):
    rc, out, written = _main(monkeypatch, capsys, [UM, F_FAIL], set(),
                             argv=["--write-baseline"])
    assert rc == 1 and written == []


def test_clean_run_still_passes(monkeypatch, capsys):
    rc, out, _ = _main(monkeypatch, capsys, [F_FAIL], {pytest_ratchet._key(F_FAIL)})
    assert rc == 0 and "PASS" in out


def test_committed_baseline_does_not_absorb_internal_errors():
    """`ERROR|pytest|internal` can only come from an aborted report, which is no
    longer trusted; keeping it baselined would be a promise to stay blind."""
    assert "ERROR|pytest|internal" not in pytest_ratchet.load_baseline()


def test_tts_engine_script_does_not_exit_at_import():
    """pytest collects this script by its test_ name. A module-level sys.exit()
    aborts the whole pytest session, wiping its chunk-mates' results."""
    src = (Path(__file__).resolve().parents[3] / "pmoves" / "tools"
           / "test_all_tts_engines.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    main_guard = [n for n in tree.body if isinstance(n, ast.If)
                  and "__main__" in ast.unparse(n.test) and "!=" not in ast.unparse(n.test)]
    module_level = [n for n in tree.body if n not in main_guard
                    and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    exits = [ast.unparse(c) for n in module_level for c in ast.walk(n)
             if isinstance(c, ast.Call) and ast.unparse(c.func) in ("sys.exit", "exit", "quit")]
    assert exits == []
