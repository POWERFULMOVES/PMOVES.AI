"""pmoves/tools/tests/test_branch_protection_publisher.py

Unit tests for the branch protection drift publisher. Pure-stdlib;
covers the MockPublisher + FilePublisher + the publish_drift_report
+ publish_drift_for_org entry points.

Test groups:
    A. MockPublisherTests - in-memory record + failure path
    B. FilePublisherTests - JSONL to file + to stdout
    C. PublishDriftReportTests - per-repo filtering (compliant silent)
    D. EnvelopeTests - source + published_at + audit shape
    E. PublishDriftForOrgTests - end-to-end with mocked drift_check
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pmoves.tools import branch_protection_publisher as pp  # noqa: E402


# --- A. MockPublisherTests ---


class MockPublisherTests(unittest.TestCase):
    def test_A1_publish_records_subject_and_payload(self):
        pub = pp.MockPublisher()
        pub.publish("test.subject", {"key": "value"})
        self.assertEqual(pub.published, [("test.subject", {"key": "value"})])

    def test_A2_publish_records_multiple(self):
        pub = pp.MockPublisher()
        pub.publish("a", {"x": 1})
        pub.publish("b", {"y": 2})
        self.assertEqual(len(pub.published), 2)

    def test_A3_fail_next_raises_on_next_publish(self):
        pub = pp.MockPublisher()
        pub.fail_next = True
        with self.assertRaises(RuntimeError):
            pub.publish("a", {"x": 1})
        # fail_next self-clears so subsequent publishes work.
        pub.publish("b", {"x": 2})
        self.assertEqual([s for s, _ in pub.published], ["b"])


# --- B. FilePublisherTests ---


class FilePublisherTests(unittest.TestCase):
    def test_B1_writes_jsonl_to_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "drift.jsonl"
            pub = pp.FilePublisher(path)
            pub.publish("a", {"x": 1})
            pub.publish("b", {"y": 2})
            content = path.read_text(encoding="utf-8")
            lines = [l for l in content.splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)
            # Each line is a JSON object with subject + payload
            parsed_a = json.loads(lines[0])
            self.assertEqual(parsed_a["subject"], "a")
            self.assertEqual(parsed_a["payload"], {"x": 1})
            parsed_b = json.loads(lines[1])
            self.assertEqual(parsed_b["subject"], "b")
            self.assertEqual(parsed_b["payload"], {"y": 2})

    def test_B2_truncates_existing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "drift.jsonl"
            path.write_text("stale line\n", encoding="utf-8")
            pub = pp.FilePublisher(path)
            pub.publish("a", {"x": 1})
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("stale line", content)
            self.assertIn('"subject": "a"', content)

    def test_B3_publish_to_stdout_collects_lines(self):
        pub = pp.FilePublisher(None)
        pub.publish("a", {"x": 1})
        pub.publish("b", {"x": 2})
        self.assertEqual(len(pub.lines), 2)


# --- C. PublishDriftReportTests ---


class PublishDriftReportTests(unittest.TestCase):
    def _make_report(self, repos):
        """Build a minimal DriftReport for tests."""
        from pmoves.tools.branch_protection import DriftReport, AuditResult
        return DriftReport(
            org="TEST",
            checked_at="2026-08-15T00:00:00Z",
            repos=repos,
        )

    def _make_audit(self, repo, compliant):
        from pmoves.tools.branch_protection import AuditResult
        return AuditResult(
            repo=repo,
            profile="test",
            branch="main",
            drift=[] if compliant else [
                # DriftItem is a dataclass; we can construct directly
            ],
            checked_at="2026-08-15T00:00:00Z",
            source_url=f"https://github.com/{repo}",
        )

    def test_C1_compliant_repos_are_silent(self):
        from pmoves.tools.branch_protection import AuditResult
        a1 = AuditResult(repo="TEST/r1", profile="t", branch="main", drift=[], checked_at="t", source_url="u")
        a2 = AuditResult(repo="TEST/r2", profile="t", branch="main", drift=[], checked_at="t", source_url="u")
        report = self._make_report([a1, a2])
        pub = pp.MockPublisher()
        count = pp.publish_drift_report(report, pub)
        self.assertEqual(count, 0)
        self.assertEqual(pub.published, [])

    def test_C2_non_compliant_repos_publish(self):
        from pmoves.tools.branch_protection import AuditResult, DriftItem
        good = AuditResult(repo="TEST/r1", profile="t", branch="main", drift=[], checked_at="t", source_url="u")
        bad = AuditResult(
            repo="TEST/r2", profile="t", branch="main",
            drift=[DriftItem(field="x", expected="y", actual="z", severity="block")],
            checked_at="t", source_url="u",
        )
        report = self._make_report([good, bad])
        pub = pp.MockPublisher()
        count = pp.publish_drift_report(report, pub)
        self.assertEqual(count, 1)
        # Only the non-compliant one was published
        self.assertEqual(len(pub.published), 1)
        self.assertEqual(pub.published[0][0], pp.SUBJECT_DRIFT)
        self.assertEqual(pub.published[0][1]["audit"]["repo"], "TEST/r2")

    def test_C3_publish_failure_propagates(self):
        from pmoves.tools.branch_protection import AuditResult, DriftItem
        bad = AuditResult(
            repo="TEST/r2", profile="t", branch="main",
            drift=[DriftItem(field="x", expected="y", actual="z", severity="block")],
            checked_at="t", source_url="u",
        )
        report = self._make_report([bad])
        pub = pp.MockPublisher()
        pub.fail_next = True
        with self.assertRaises(RuntimeError):
            pp.publish_drift_report(report, pub)

    def test_C4_subject_is_drift_v1_by_default(self):
        self.assertEqual(pp.SUBJECT_DRIFT, "pmoves.branch_protection.drift.v1")

    def test_C5_custom_subject_can_be_passed(self):
        from pmoves.tools.branch_protection import AuditResult, DriftItem
        bad = AuditResult(
            repo="TEST/r2", profile="t", branch="main",
            drift=[DriftItem(field="x", expected="y", actual="z", severity="block")],
            checked_at="t", source_url="u",
        )
        report = self._make_report([bad])
        pub = pp.MockPublisher()
        count = pp.publish_drift_report(report, pub, subject="custom.subject.v1")
        self.assertEqual(count, 1)
        self.assertEqual(pub.published[0][0], "custom.subject.v1")


# --- D. EnvelopeTests ---


class EnvelopeTests(unittest.TestCase):
    def test_D1_envelope_wraps_audit_shape(self):
        audit = {
            "repo": "TEST/r",
            "profile": "t",
            "branch": "main",
            "compliant": False,
            "drift": [],
            "checked_at": "2026-08-15T00:00:00Z",
            "source_url": "https://github.com/TEST/r/settings/branches",
        }
        env = pp._envelope(audit)
        self.assertEqual(env["envelope"], "drift.v1")
        self.assertEqual(env["source"], "pmoves.branch_protection")
        self.assertIn("published_at", env)
        self.assertEqual(env["audit"], audit)

    def test_D2_published_at_is_iso_utc(self):
        import re
        env = pp._envelope({"repo": "x", "profile": "p", "branch": "main", "compliant": True, "drift": [], "checked_at": "t", "source_url": "u"})
        # ISO format: YYYY-MM-DDTHH:MM:SS[.ffffff][+HH:MM]
        self.assertRegex(
            env["published_at"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        )


# --- E. PublishDriftForOrgTests ---


class PublishDriftForOrgTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection_publisher.drift_check")
    def test_E1_publishes_drift_for_org(self, mock_drift_check):
        from pmoves.tools.branch_protection import AuditResult, DriftItem, DriftReport
        bad = AuditResult(
            repo="TEST/r", profile="t", branch="main",
            drift=[DriftItem(field="x", expected="y", actual="z", severity="block")],
            checked_at="t", source_url="u",
        )
        mock_drift_check.return_value = DriftReport(org="TEST", checked_at="t", repos=[bad])
        pub = pp.MockPublisher()
        count = pp.publish_drift_for_org(org="TEST", publisher=pub)
        self.assertEqual(count, 1)
        mock_drift_check.assert_called_once()
        # The org was the first positional arg
        self.assertEqual(mock_drift_check.call_args.args[0], "TEST")
        # The publisher loaded the spec (the default behavior when no spec passed)
        called_spec = mock_drift_check.call_args.kwargs.get("spec")
        self.assertIsNotNone(called_spec)
        self.assertEqual(called_spec.get("spec"), "pmoves.rulesets/v2")

    @mock.patch("pmoves.tools.branch_protection_publisher.drift_check")
    def test_E2_returns_zero_when_compliant(self, mock_drift_check):
        from pmoves.tools.branch_protection import AuditResult, DriftReport
        good = AuditResult(repo="TEST/r", profile="t", branch="main", drift=[], checked_at="t", source_url="u")
        mock_drift_check.return_value = DriftReport(org="TEST", checked_at="t", repos=[good])
        pub = pp.MockPublisher()
        count = pp.publish_drift_for_org(org="TEST", publisher=pub)
        self.assertEqual(count, 0)
        self.assertEqual(pub.published, [])

    @mock.patch("pmoves.tools.branch_protection_publisher.drift_check")
    def test_E3_default_publisher_is_mock(self, mock_drift_check):
        from pmoves.tools.branch_protection import DriftReport
        mock_drift_check.return_value = DriftReport(org="TEST", checked_at="t", repos=[])
        # No publisher passed -> MockPublisher
        pp.publish_drift_for_org(org="TEST")
        mock_drift_check.assert_called_once()

    @mock.patch("pmoves.tools.branch_protection_publisher.drift_check")
    def test_E4_loads_spec_from_path_when_not_provided(self, mock_drift_check):
        from pmoves.tools.branch_protection import DriftReport
        mock_drift_check.return_value = DriftReport(org="TEST", checked_at="t", repos=[])
        # Default spec path = the canonical one in pmoves/configs/
        pp.publish_drift_for_org(org="TEST")
        # drift_check is called with the spec object (not None, not a path)
        called_spec = mock_drift_check.call_args.kwargs.get("spec")
        self.assertIsNotNone(called_spec)
        self.assertEqual(called_spec.get("spec"), "pmoves.rulesets/v2")


if __name__ == "__main__":
    unittest.main()
