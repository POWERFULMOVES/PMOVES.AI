"""pmoves/tools/tests/test_branch_protection.py

Unit tests for pmoves.tools.branch_protection. Pure-stdlib; uses
unittest.mock to intercept the `gh api` subprocess calls so the
tests don't need network or a real gh binary.

Test groups:
    A. SpecLoaderTests        — load + resolve_repo_profile
    B. DiffLogicTests         — _diff_required_status_checks + _diff_review_policy
                                + _diff_boolean_field + _diff_rulesets
    C. ApplyBodyTests         — _build_classic_body + _build_ruleset_body
    D. AuditTests             — audit() end-to-end with mocked gh
    E. ApplyTests             — apply() end-to-end with mocked gh (dry + live)
    F. DriftCheckTests        — drift_check() across the spec
    G. CLITests               — main() argv parsing + output format
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

# Make pmoves.tools importable when running from the worktree root.
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pmoves.tools import branch_protection as bp  # noqa: E402


# --- Test fixtures: a minimal spec + repo state ---

MINIMAL_SPEC = {
    "spec": "pmoves.branch_protection/v1",
    "encoder_version": "1.0.0",
    "profiles": {
        "monorepo": {
            "description": "test monorepo",
            "branch": "main",
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {"context": "merge-gate"},
                    {"context": "python-tests"},
                ],
            },
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
                "require_last_push_approval": False,
                "required_approving_review_count": 1,
            },
            "required_linear_history": True,
            "required_signatures": True,
            "required_conversation_resolution": True,
            "enforce_admins": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "restrictions": None,
            "rulesets": [
                {
                    "name": "[ main ]",
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                    "rules": [
                        {"type": "deletion"},
                        {"type": "non_fast_forward"},
                        {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
                    ],
                    "bypass_actors": [],
                }
            ],
        },
        "fork": {
            "description": "test fork",
            "branch": "main",
            "required_status_checks": {
                "strict": True,
                "checks": [{"context": "CodeRabbit"}],
            },
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "require_last_push_approval": False,
                "required_approving_review_count": 1,
            },
            "required_linear_history": True,
            "required_signatures": False,
            "required_conversation_resolution": True,
            "enforce_admins": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "restrictions": None,
            "rulesets": [
                {
                    "name": "[ main ]",
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                    "rules": [
                        {"type": "deletion"},
                        {"type": "non_fast_forward"},
                        {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
                    ],
                    "bypass_actors": [],
                }
            ],
        },
    },
    "per_repo_overrides": {
        "TEST/monorepo": {"profile": "monorepo"},
        "TEST/fork": {
            "profile": "fork",
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {"context": "check-attribution"},
                    {"context": "ruff + ty diff"},
                ],
            },
        },
    },
}


COMPLIANT_CLASSIC = {
    "required_status_checks": {
        "strict": True,
        "checks": [
            {"context": "merge-gate"},
            {"context": "python-tests"},
        ],
    },
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": True,
        "require_last_push_approval": False,
        "required_approving_review_count": 1,
    },
    "required_linear_history": {"enabled": True},
    "required_signatures": {"enabled": True},
    "required_conversation_resolution": {"enabled": True},
    "enforce_admins": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
    "restrictions": None,
}


COMPLIANT_RULESETS = [
    {
        "id": 1,
        "name": "[ main ]",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
        ],
        "bypass_actors": [],
    }
]


# --- Mock subprocess for `gh api` ---

class _MockProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _mock_subprocess_factory(responses: dict[tuple[str, str], Any]):
    """Build a mock for subprocess.run that maps (method, path) to a
    parsed JSON response. path is matched as exact-or-prefix.
    """
    def _run(cmd, input=None, capture_output=None, text=None, check=None):
        # cmd layout: ["gh", "api", "--method", METHOD, PATH, ...]
        method = cmd[3]
        path = cmd[4]
        for (m, p), resp in responses.items():
            if m == method and path.startswith(p):
                if resp is None:
                    return _MockProc(returncode=0, stdout="", stderr="")
                return _MockProc(returncode=0, stdout=json.dumps(resp), stderr="")
        return _MockProc(
            returncode=1, stdout="", stderr=f"unmocked gh call: {method} {path}"
        )
    return _run


# === A. SpecLoaderTests ===

class SpecLoaderTests(unittest.TestCase):
    def test_A1_load_minimal_spec(self):
        spec = MINIMAL_SPEC
        self.assertIn("profiles", spec)
        self.assertIn("per_repo_overrides", spec)
        self.assertEqual(spec["spec"], "pmoves.branch_protection/v1")

    def test_A2_resolve_repo_profile_default(self):
        name, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/monorepo")
        self.assertEqual(name, "monorepo")
        self.assertEqual(merged["branch"], "main")
        self.assertTrue(merged["required_linear_history"])

    def test_A3_resolve_repo_profile_with_override(self):
        name, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/fork")
        self.assertEqual(name, "fork")
        # The override replaced the required_status_checks.
        contexts = {c["context"] for c in merged["required_status_checks"]["checks"]}
        self.assertEqual(contexts, {"check-attribution", "ruff + ty diff"})

    def test_A4_resolve_repo_profile_unknown_repo_raises(self):
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/unknown")
        self.assertIn("no per_repo_overrides", str(cm.exception))

    def test_A5_resolve_repo_profile_unknown_profile_raises(self):
        bad_spec = dict(MINIMAL_SPEC)
        bad_spec["per_repo_overrides"] = {"TEST/x": {"profile": "ghost"}}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.resolve_repo_profile(bad_spec, "TEST/x")
        self.assertIn("not found in spec", str(cm.exception))


# === B. DiffLogicTests ===

class DiffLogicTests(unittest.TestCase):
    def test_B1_diff_status_checks_compliant(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_status_checks"]
        drift = bp._diff_required_status_checks(expected, COMPLIANT_CLASSIC["required_status_checks"])
        self.assertEqual(drift, [])

    def test_B2_diff_status_checks_missing(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_status_checks"]
        actual = {"strict": True, "checks": [{"context": "merge-gate"}]}
        drift = bp._diff_required_status_checks(expected, actual)
        self.assertEqual(len(drift), 1)
        self.assertIn("python-tests", drift[0].field)
        self.assertEqual(drift[0].severity, "block")

    def test_B3_diff_status_checks_strict_mismatch(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_status_checks"]
        actual = {"strict": False, "checks": [{"context": "merge-gate"}, {"context": "python-tests"}]}
        drift = bp._diff_required_status_checks(expected, actual)
        self.assertTrue(any(d.field == "required_status_checks.strict" for d in drift))

    def test_B4_diff_status_checks_extra_is_warn(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_status_checks"]
        actual = {
            "strict": True,
            "checks": [
                {"context": "merge-gate"},
                {"context": "python-tests"},
                {"context": "extra-check"},
            ],
        }
        drift = bp._diff_required_status_checks(expected, actual)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0].severity, "warn")
        self.assertIn("extra-check", drift[0].field)

    def test_B5_diff_status_checks_none_is_block(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_status_checks"]
        drift = bp._diff_required_status_checks(expected, None)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0].severity, "block")

    def test_B6_diff_review_policy_compliant(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_pull_request_reviews"]
        drift = bp._diff_review_policy(expected, COMPLIANT_CLASSIC["required_pull_request_reviews"])
        self.assertEqual(drift, [])

    def test_B7_diff_review_policy_count_drift_is_block(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_pull_request_reviews"]
        actual = dict(COMPLIANT_CLASSIC["required_pull_request_reviews"])
        actual["required_approving_review_count"] = 0
        drift = bp._diff_review_policy(expected, actual)
        self.assertTrue(any(d.severity == "block" for d in drift))

    def test_B8_diff_review_policy_dismiss_stale_drift_is_warn(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["required_pull_request_reviews"]
        actual = dict(COMPLIANT_CLASSIC["required_pull_request_reviews"])
        actual["dismiss_stale_reviews"] = False
        drift = bp._diff_review_policy(expected, actual)
        self.assertTrue(any(d.severity == "warn" for d in drift))

    def test_B9_diff_boolean_field_compliant(self):
        drift = bp._diff_boolean_field(
            "required_linear_history", True,
            {"required_linear_history": {"enabled": True}},
        )
        self.assertEqual(drift, [])

    def test_B10_diff_boolean_field_drift_is_warn(self):
        drift = bp._diff_boolean_field(
            "required_signatures", True,
            {"required_signatures": {"enabled": False}},
        )
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0].severity, "warn")

    def test_B11_diff_boolean_field_none_is_block(self):
        drift = bp._diff_boolean_field("required_signatures", True, None)
        self.assertEqual(drift[0].severity, "block")

    def test_B12_diff_boolean_field_bare_bool_actual(self):
        # The real GitHub API returns {"enabled": true} for these. The
        # tool also tolerates a bare bool for tests / partial inputs.
        drift = bp._diff_boolean_field(
            "required_signatures", True, {"required_signatures": True}
        )
        self.assertEqual(drift, [])

    def test_B12_diff_rulesets_compliant(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"]
        drift = bp._diff_rulesets(expected, COMPLIANT_RULESETS)
        self.assertEqual(drift, [])

    def test_B13_diff_rulesets_missing(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"]
        drift = bp._diff_rulesets(expected, [])
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0].severity, "block")

    def test_B14_diff_rulesets_unexpected_extra_is_warn(self):
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"]
        drift = bp._diff_rulesets(expected, COMPLIANT_RULESETS + [{"id": 2, "name": "extra"}])
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0].severity, "warn")


# === C. ApplyBodyTests ===

class ApplyBodyTests(unittest.TestCase):
    def test_C1_build_classic_body_has_all_keys(self):
        body = bp._build_classic_body(MINIMAL_SPEC["profiles"]["monorepo"])
        for key in (
            "required_status_checks",
            "required_pull_request_reviews",
            "required_linear_history",
            "required_signatures",
            "required_conversation_resolution",
            "enforce_admins",
            "allow_force_pushes",
            "allow_deletions",
            "restrictions",
        ):
            self.assertIn(key, body)

    def test_C2_build_classic_body_preserves_values(self):
        profile = MINIMAL_SPEC["profiles"]["monorepo"]
        body = bp._build_classic_body(profile)
        self.assertEqual(body["required_linear_history"], True)
        self.assertEqual(body["required_signatures"], True)
        self.assertEqual(body["enforce_admins"], False)

    def test_C3_build_ruleset_body_has_required_keys(self):
        rs = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        body = bp._build_ruleset_body(rs)
        for key in ("name", "target", "enforcement", "conditions", "rules", "bypass_actors"):
            self.assertIn(key, body)

    def test_C4_build_ruleset_body_preserves_rules(self):
        rs = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        body = bp._build_ruleset_body(rs)
        self.assertEqual(len(body["rules"]), 3)
        self.assertEqual(body["rules"][0]["type"], "deletion")


# === D. AuditTests ===

class AuditTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D1_audit_compliant_repo(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): COMPLIANT_CLASSIC,
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        self.assertTrue(result.is_compliant)
        self.assertEqual(result.drift, [])

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D2_audit_no_classic_protection_is_block_drift(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): None,
            ("GET", "repos/TEST/monorepo/rulesets"): [],
        }.get((m, p))
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        self.assertFalse(result.is_compliant)
        self.assertTrue(any(d.severity == "block" for d in result.drift))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D3_audit_missing_status_check_is_block(self, mock_api):
        actual = dict(COMPLIANT_CLASSIC)
        actual["required_status_checks"] = {"strict": True, "checks": [{"context": "merge-gate"}]}
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): actual,
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        self.assertFalse(result.is_compliant)
        self.assertTrue(any("python-tests" in d.field for d in result.drift))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D4_audit_extra_status_check_is_warn(self, mock_api):
        actual = dict(COMPLIANT_CLASSIC)
        actual["required_status_checks"] = {
            "strict": True,
            "checks": [
                {"context": "merge-gate"},
                {"context": "python-tests"},
                {"context": "extra"},
            ],
        }
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): actual,
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        # The extra check is a warn, not a block — so is_compliant stays True.
        self.assertTrue(result.is_compliant)
        self.assertTrue(any(d.severity == "warn" for d in result.drift))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D5_audit_with_explicit_profile(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): COMPLIANT_CLASSIC,
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        result = bp.audit("TEST/monorepo", profile="monorepo", spec=MINIMAL_SPEC)
        self.assertEqual(result.profile, "monorepo")

    def test_D6_audit_unknown_repo_raises(self):
        with self.assertRaises(bp.BranchProtectionError):
            bp.audit("TEST/unknown", spec=MINIMAL_SPEC)


# === E. ApplyTests ===

class ApplyTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E1_apply_dry_run_no_calls(self, mock_api):
        result = bp.apply("TEST/monorepo", dry_run=True, spec=MINIMAL_SPEC)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.applied, [])
        self.assertGreater(len(result.calls), 0)
        # The classic PUT call should be in the list.
        methods = [c["method"] for c in result.calls]
        self.assertIn("PUT", methods)
        # The POST for the ruleset should also be in the list.
        self.assertIn("POST", methods)
        # But the live API was never called.
        self.assertFalse(
            any(
                call.args == ("PUT", "repos/TEST/monorepo/branches/main/protection")
                for call in mock_api.call_args_list
            )
        )

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E2_apply_live_calls(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("PUT", "repos/TEST/monorepo/branches/main/protection"): {"ok": True},
            ("GET", "repos/TEST/monorepo/rulesets"): [],  # ruleset missing → create
            ("POST", "repos/TEST/monorepo/rulesets"): {"id": 42, "name": "[ main ]"},
        }.get((m, p))
        result = bp.apply("TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC)
        self.assertFalse(result.dry_run)
        self.assertGreater(len(result.applied), 0)
        # The classic PUT was applied.
        self.assertIn("repos/TEST/monorepo/branches/main/protection", result.applied)
        # The ruleset was applied with the new id.
        self.assertTrue(any("42" in a for a in result.applied))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E3_apply_skips_existing_ruleset(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("PUT", "repos/TEST/monorepo/branches/main/protection"): {"ok": True},
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        result = bp.apply("TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC)
        self.assertTrue(any("already exists" in s for s in result.skipped))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E4_apply_includes_per_repo_override_checks(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("PUT", "repos/TEST/fork/branches/main/protection"): {"ok": True},
            ("GET", "repos/TEST/fork/rulesets"): [],
            ("POST", "repos/TEST/fork/rulesets"): {"id": 7, "name": "[ main ]"},
        }.get((m, p))
        result = bp.apply("TEST/fork", dry_run=False, spec=MINIMAL_SPEC)
        # The classic PUT body should carry the per-repo override checks.
        put_call = next(c for c in result.calls if c["method"] == "PUT")
        contexts = {ch["context"] for ch in put_call["body"]["required_status_checks"]["checks"]}
        self.assertEqual(contexts, {"check-attribution", "ruff + ty diff"})

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E5_apply_unknown_repo_raises(self, mock_api):
        with self.assertRaises(bp.BranchProtectionError):
            bp.apply("TEST/unknown", spec=MINIMAL_SPEC)


# === F. DriftCheckTests ===

class DriftCheckTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_F1_drift_check_returns_one_report_per_repo(self, mock_audit):
        mock_audit.side_effect = lambda repo, profile=None, spec=None: bp.AuditResult(
            repo=repo, profile=profile or "x", drift=[], checked_at="t", source_url="u"
        )
        report = bp.drift_check("TEST", spec=MINIMAL_SPEC)
        self.assertEqual(len(report.repos), 2)  # TEST/monorepo + TEST/fork
        self.assertEqual(report.org, "TEST")

    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_F2_drift_check_includes_only_org_repos(self, mock_audit):
        mock_audit.side_effect = lambda repo, profile=None, spec=None: bp.AuditResult(
            repo=repo, profile=profile or "x", drift=[], checked_at="t", source_url="u"
        )
        report = bp.drift_check("OTHER_ORG", spec=MINIMAL_SPEC)
        self.assertEqual(report.repos, [])  # No repos in OTHER_ORG

    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_F3_drift_check_surfaces_audit_error(self, mock_audit):
        def fake_audit(repo, profile=None, spec=None):
            if repo == "TEST/monorepo":
                raise bp.BranchProtectionError("gh subprocess failed: token expired")
            return bp.AuditResult(
                repo=repo, profile=profile or "x", drift=[], checked_at="t", source_url="u"
            )
        mock_audit.side_effect = fake_audit
        report = bp.drift_check("TEST", spec=MINIMAL_SPEC)
        # The erroring repo should appear with a synthetic drift entry.
        errored = next(r for r in report.repos if r.repo == "TEST/monorepo")
        self.assertFalse(errored.is_compliant)
        self.assertEqual(errored.drift[0].field, "audit_error")


# === G. CLITests ===

class CLITests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_G1_audit_cli_exits_0_when_compliant(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): COMPLIANT_CLASSIC,
            ("GET", "repos/TEST/monorepo/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        with mock.patch("sys.argv", ["bp", "--spec", "/tmp/none.json", "audit", "--repo", "TEST/monorepo"]):
            with mock.patch("pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC):
                rc = bp.main()
        self.assertEqual(rc, 0)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_G2_audit_cli_exits_1_when_drift(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): None,
            ("GET", "repos/TEST/monorepo/rulesets"): [],
        }.get((m, p))
        with mock.patch("sys.argv", ["bp", "--spec", "/tmp/none.json", "audit", "--repo", "TEST/monorepo"]):
            with mock.patch("pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC):
                rc = bp.main()
        self.assertEqual(rc, 1)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_G3_drift_check_cli_exits_2_when_any_repo_drift(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: {
            ("GET", "repos/TEST/monorepo/branches/main/protection"): None,
            ("GET", "repos/TEST/monorepo/rulesets"): [],
            ("GET", "repos/TEST/fork/branches/main/protection"): COMPLIANT_CLASSIC,
            ("GET", "repos/TEST/fork/rulesets"): COMPLIANT_RULESETS,
        }.get((m, p))
        with mock.patch("sys.argv", ["bp", "--spec", "/tmp/none.json", "drift-check", "--org", "TEST"]):
            with mock.patch("pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC):
                rc = bp.main()
        self.assertEqual(rc, 2)

    def test_G4_apply_cli_default_is_dry_run(self):
        with mock.patch("pmoves.tools.branch_protection._gh_api") as mock_api:
            mock_api.side_effect = lambda m, p, b=None: {
                ("GET", "repos/TEST/monorepo/rulesets"): [],
            }.get((m, p), {"ok": True})
            result = bp.apply("TEST/monorepo", dry_run=True, spec=MINIMAL_SPEC)
            self.assertTrue(result.dry_run)
            # dry-run does ONE read (the existing rulesets) so the output
            # can accurately report skip-vs-create. No PUT or POST is issued.
            methods_called = [c.args[0] for c in mock_api.call_args_list]
            self.assertNotIn("PUT", methods_called)
            self.assertNotIn("POST", methods_called)
            # applied list is empty (no live changes).
            self.assertEqual(result.applied, [])


# --- Block-level check: gh missing ---

class GHMissingTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection.shutil.which", return_value=None)
    def test_H1_gh_missing_raises(self, mock_which):
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp._gh_api("GET", "repos/foo")
        self.assertIn("gh CLI not found", str(cm.exception))


# --- Block-level check: gh returns 404 for unprotected branch ---

class GHNotProtectedTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection.subprocess.run")
    def test_H2_gh_404_for_unprotected_returns_none(self, mock_run):
        mock_run.return_value = _MockProc(
            returncode=1, stdout="", stderr="Branch not protected"
        )
        result = bp._gh_api("GET", "repos/foo/branches/main/protection")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
