"""pmoves/tools/tests/test_branch_protection_migrate_pmai.py

Unit tests for the PMOVES.AI branch-protection migration script.

Test groups:
    A. ComputeMainRulesetTests — compute_new_main_ruleset body shape
    B. CaptureStateTests        — capture_current_state + bypass_actors re-fetch
    C. PlanTests                — plan() end-to-end
    D. ApplyTests               — apply() dry-run + live + skip-if-missing
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

# Make pmoves.tools importable when running from the worktree root.
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pmoves.tools import branch_protection as bp  # noqa: E402
from pmoves.tools import branch_protection_migrate_pmai as migrate  # noqa: E402


# --- Fixtures ---

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
                    {"context": "hardening-validation"},
                    {"context": "verify"},
                    {"context": "submodule-gitlink-gate"},
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
                        {"type": "copilot_code_review"},
                    ],
                    "bypass_actors": [
                        {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
                    ],
                }
            ],
        }
    },
    "per_repo_overrides": {},
}


def _full_main_ruleset() -> dict:
    """The full body of the [main] ruleset as returned by the
    individual /rulesets/{id} endpoint. Includes bypass_actors.
    """
    return {
        "id": 10887588,
        "name": "[ main ]",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
            {"type": "copilot_code_review"},
        ],
        "bypass_actors": [
            {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"},
            {"actor_type": "Integration", "actor_id": 1144995, "bypass_mode": "always"},
            {"actor_type": "Integration", "actor_id": 1236702, "bypass_mode": "always"},
        ],
    }


def _list_endpoint_main_ruleset_summary() -> dict:
    """The summary body of the [main] ruleset as returned by the
    list /rulesets endpoint. NO bypass_actors (this is the bug
    the migration's re-fetch guards against).
    """
    return {
        "id": 10887588,
        "name": "[ main ]",
        "target": "branch",
        "enforcement": "active",
    }


def _list_endpoint_rulesets() -> list:
    return [
        _list_endpoint_main_ruleset_summary(),
        {"id": 8204234, "name": "pmoves rules", "target": "branch", "enforcement": "active"},
        {"id": 17234200, "name": "tag-protection", "target": "tag", "enforcement": "active"},
    ]


def _classic_protection() -> dict:
    return {
        "required_status_checks": {
            "strict": True,
            "checks": [
                {"context": "merge-gate", "app_id": 15368},
                {"context": "python-tests", "app_id": 15368},
                {"context": "hardening-validation", "app_id": 15368},
                {"context": "verify", "app_id": 15368},
                {"context": "submodule-gitlink-gate", "app_id": 15368},
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


# === A. ComputeMainRulesetTests ===

class ComputeMainRulesetTests(unittest.TestCase):
    def test_A1_includes_required_status_checks_rule(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        types = [r.get("type") for r in new["rules"]]
        self.assertIn("required_status_checks", types)

    def test_A2_required_status_checks_has_all_five(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        rsc_rule = next(r for r in new["rules"] if r["type"] == "required_status_checks")
        contexts = [c["context"] for c in rsc_rule["parameters"]["required_status_checks"]]
        self.assertEqual(
            set(contexts),
            {"merge-gate", "python-tests", "hardening-validation", "verify", "submodule-gitlink-gate"},
        )

    def test_A3_required_status_checks_strict_true(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        rsc_rule = next(r for r in new["rules"] if r["type"] == "required_status_checks")
        self.assertTrue(rsc_rule["parameters"]["strict_required_status_checks_policy"])

    def test_A4_pull_request_parameters_from_spec(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        pr_rule = next(r for r in new["rules"] if r["type"] == "pull_request")
        params = pr_rule["parameters"]
        self.assertEqual(params["required_approving_review_count"], 1)
        self.assertTrue(params["require_code_owner_review"])
        self.assertTrue(params["dismiss_stale_reviews_on_push"])
        self.assertFalse(params["require_last_push_approval"])
        self.assertTrue(params["required_review_thread_resolution"])

    def test_A5_preserves_existing_bypass_actors(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        # The new body should have the 3 bypass_actors from the existing
        # ruleset, NOT just the 1 from the spec.
        self.assertEqual(len(new["bypass_actors"]), 3)
        actor_ids = {a["actor_id"] for a in new["bypass_actors"]}
        self.assertEqual(actor_ids, {5, 1144995, 1236702})

    def test_A6_no_existing_main_uses_spec_defaults(self):
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, None, _classic_protection())
        # When no existing [main] ruleset, the spec's 1 bypass_actor
        # is used as the default.
        self.assertEqual(len(new["bypass_actors"]), 1)

    def test_A7_preserves_ruleset_name(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        self.assertEqual(new["name"], "[ main ]")

    def test_A8_preserves_target_and_enforcement(self):
        main = _full_main_ruleset()
        new = migrate.compute_new_main_ruleset(MINIMAL_SPEC, main, _classic_protection())
        self.assertEqual(new["target"], "branch")
        self.assertEqual(new["enforcement"], "active")


# === B. CaptureStateTests ===

class CaptureStateTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_B1_capture_refetches_main_for_bypass_actors(self, mock_api):
        # The list endpoint returns a summary WITHOUT bypass_actors.
        # The individual endpoint returns the full body WITH bypass_actors.
        # The script should re-fetch so bypass_actors is captured.
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588":
                return _full_main_ruleset()
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        state = migrate.capture_current_state()
        self.assertEqual(len(state["main_ruleset"]["bypass_actors"]), 3)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_B2_capture_preserves_other_rulesets(self, mock_api):
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588":
                return _full_main_ruleset()
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        state = migrate.capture_current_state()
        names = {r["name"] for r in state["rulesets"]}
        self.assertIn("pmoves rules", names)
        self.assertIn("tag-protection", names)
        self.assertIn("[ main ]", names)


# === C. PlanTests ===

class PlanTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_C1_plan_captures_bypass_actors_and_status_checks(self, mock_api):
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588":
                return _full_main_ruleset()
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        plan_obj = migrate.plan(spec=MINIMAL_SPEC)
        self.assertEqual(len(plan_obj.captured_bypass_actors), 3)
        self.assertEqual(len(plan_obj.captured_required_status_checks), 5)
        self.assertTrue(plan_obj.delete_classic)
        self.assertTrue(plan_obj.put_main_ruleset)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_C2_plan_new_main_ruleset_has_5_status_checks(self, mock_api):
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588":
                return _full_main_ruleset()
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        plan_obj = migrate.plan(spec=MINIMAL_SPEC)
        rsc = next(
            r for r in plan_obj.new_main_ruleset_body["rules"]
            if r["type"] == "required_status_checks"
        )
        self.assertEqual(
            len(rsc["parameters"]["required_status_checks"]),
            5,
        )


# === D. ApplyTests ===

class ApplyTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D1_dry_run_no_live_calls(self, mock_api):
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588":
                return _full_main_ruleset()
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        plan_obj = migrate.plan(spec=MINIMAL_SPEC)
        result = migrate.apply(plan_obj, dry_run=True)
        self.assertTrue(result.dry_run)
        # mock_api.call_args_list is a list of Call objects; .args[0] is the
        # positional method, .args[1] is the path. We check both.
        methods_called = []
        for call in mock_api.call_args_list:
            if call.args:
                methods_called.append(call.args[0])
        self.assertNotIn("DELETE", methods_called)
        self.assertNotIn("PUT", methods_called)
        # applied is empty (no live changes)
        self.assertEqual(result.applied, [])

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D2_live_calls_delete_classic_put_main(self, mock_api):
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection" and method == "GET":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets" and method == "GET":
                return _list_endpoint_rulesets()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588" and method == "GET":
                return _full_main_ruleset()
            if method == "DELETE":
                return None
            if method == "PUT":
                return {"id": 10887588}
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        plan_obj = migrate.plan(spec=MINIMAL_SPEC)
        result = migrate.apply(plan_obj, dry_run=False)
        self.assertIn("repos/POWERFULMOVES/PMOVES.AI/branches/main/protection", result.applied)
        self.assertIn("repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588", result.applied)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_D3_skips_if_main_ruleset_missing(self, mock_api):
        # If the [main] ruleset doesn't exist on the second re-fetch,
        # apply() should skip the PUT and add a skip entry.
        def side_effect(method, path, body=None):
            if path == "repos/POWERFULMOVES/PMOVES.AI/branches/main/protection" and method == "GET":
                return _classic_protection()
            if path == "repos/POWERFULMOVES/PMOVES.AI/rulesets" and method == "GET":
                # No [main] ruleset in the list
                return [
                    {"id": 8204234, "name": "pmoves rules", "target": "branch"},
                    {"id": 17234200, "name": "tag-protection", "target": "tag"},
                ]
            if method == "DELETE":
                return None
            raise AssertionError(f"unmocked call: {method} {path}")
        mock_api.side_effect = side_effect
        plan_obj = migrate.plan(spec=MINIMAL_SPEC)
        # The plan has put_main_ruleset=False because the [main] ruleset
        # wasn't found in the list.
        self.assertFalse(plan_obj.put_main_ruleset)
        result = migrate.apply(plan_obj, dry_run=False)
        # The DELETE still ran, the PUT did not.
        self.assertTrue(any("branches/main/protection" in a for a in result.applied))
        self.assertFalse(any("rulesets/10887588" in a for a in result.applied))


if __name__ == "__main__":
    unittest.main()
