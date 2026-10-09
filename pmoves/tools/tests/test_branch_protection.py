"""pmoves/tools/tests/test_branch_protection.py

Unit tests for pmoves.tools.branch_protection. Pure-stdlib; uses
unittest.mock to intercept the `gh api` subprocess calls so the
tests don't need network or a real gh binary.

The tool owns RULESETS only (per operator ratification 2026-08-10).
Classic branch protection is the responsibility of
.github/workflows/branch-protection-sync.yml. The tests reflect the
post-ratification API surface (SpecValidator, resolve_branch,
_ruleset_matches, audit/apply/drift_check).

Test groups:
    A. SpecValidatorTests        — strict spec validation
    B. ResolveRepoProfileTests   — resolve_repo_profile + overrides
    C. ResolveBranchTests        — resolve_branch (override + .gitmodules + default)
    D. RulesetDiffTests          — _ruleset_matches deep diff
    E. AuditTests                — audit() end-to-end with mocked gh
    F. ApplyTests                — apply() end-to-end with mocked gh (dry + live)
    G. DriftCheckTests           — drift_check() across the spec
    H. CLITests                  — main() argv parsing + output format
    I. GHErrorPathTests          — gh missing, timeout, 404
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import sys

# Make pmoves.tools importable when running from the worktree root.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pmoves.tools import branch_protection as bp  # noqa: E402


# --- Test fixtures: a minimal spec + repo state ---

MINIMAL_SPEC = {
    "spec": "pmoves.rulesets/v2",
    "encoder_version": "2.0.0",
    "profiles": {
        "monorepo": {
            "description": "test monorepo",
            "rulesets": [
                {
                    "name": "[ main ]",
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {
                        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
                    },
                    "rules": [
                        {"type": "deletion"},
                        {"type": "non_fast_forward"},
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "merge-gate"},
                                    {"context": "python-tests"},
                                ],
                                "strict_required_status_checks_policy": True,
                            },
                        },
                        {
                            "type": "pull_request",
                            "parameters": {
                                "require_code_owner_review": True,
                                "dismiss_stale_reviews_on_push": True,
                                "required_approving_review_count": 1,
                                "required_review_thread_resolution": True,
                            },
                        },
                    ],
                    "bypass_actors": [
                        {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}
                    ],
                }
            ],
        },
        "fork": {
            "description": "test fork",
            "rulesets": [
                {
                    "name": "[ main ]",
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {
                        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
                    },
                    "rules": [
                        {"type": "deletion"},
                        {"type": "non_fast_forward"},
                        {
                            "type": "pull_request",
                            "parameters": {
                                "require_code_owner_review": False,
                                "dismiss_stale_reviews_on_push": True,
                                "required_approving_review_count": 0,
                                "required_review_thread_resolution": True,
                            },
                        },
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
            "branch": "main",
            "ruleset_overrides": {
                "[ main ]": {
                    "rules": [
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "check-attribution"},
                                    {"context": "ruff + ty diff"},
                                ],
                                "strict_required_status_checks_policy": True,
                            },
                        }
                    ]
                }
            },
        },
    },
}


# GitHub API returns `main` (literal), not `~DEFAULT_BRANCH`.
COMPLIANT_RULESETS = [
    {
        "id": 1,
        "name": "[ main ]",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {"context": "merge-gate"},
                        {"context": "python-tests"},
                    ],
                    "strict_required_status_checks_policy": True,
                },
            },
            {
                "type": "pull_request",
                "parameters": {
                    "require_code_owner_review": True,
                    "dismiss_stale_reviews_on_push": True,
                    "required_approving_review_count": 1,
                    "required_review_thread_resolution": True,
                },
            },
        ],
        "bypass_actors": [
            {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}
        ],
    }
]


# --- Mock subprocess for `gh api` ---

class _MockProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# === A. SpecValidatorTests ===

class SpecValidatorTests(unittest.TestCase):
    def test_A1_valid_spec_passes(self):
        # Should not raise.
        bp.SpecValidator(MINIMAL_SPEC).validate()

    def test_A2_missing_top_level_spec_key_raises(self):
        bad = {k: v for k, v in MINIMAL_SPEC.items() if k != "spec"}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("missing top-level 'spec' key", str(cm.exception))

    def test_A3_missing_profiles_raises(self):
        bad = {k: v for k, v in MINIMAL_SPEC.items() if k != "profiles"}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("missing or non-dict 'profiles'", str(cm.exception))

    def test_A4_empty_profiles_raises(self):
        bad = dict(MINIMAL_SPEC)
        bad["profiles"] = {}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("'profiles' is empty", str(cm.exception))

    def test_A5_invalid_rule_type_raises(self):
        bad = json.loads(json.dumps(MINIMAL_SPEC))
        bad["profiles"]["monorepo"]["rulesets"][0]["rules"].append(
            {"type": "totally_made_up_rule"}
        )
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("not in VALID_RULESET_RULE_TYPES", str(cm.exception))

    def test_A6_invalid_target_raises(self):
        bad = json.loads(json.dumps(MINIMAL_SPEC))
        bad["profiles"]["monorepo"]["rulesets"][0]["target"] = "commit"
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn(".target: 'commit' not in (branch, tag, push)", str(cm.exception))

    def test_A7_invalid_enforcement_raises(self):
        bad = json.loads(json.dumps(MINIMAL_SPEC))
        bad["profiles"]["monorepo"]["rulesets"][0]["enforcement"] = "enforced"
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("not in (active, disabled, evaluate)", str(cm.exception))

    def test_A8_override_unknown_profile_raises(self):
        bad = dict(MINIMAL_SPEC)
        bad["per_repo_overrides"] = {"TEST/x": {"profile": "ghost"}}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        self.assertIn("not in spec.profiles", str(cm.exception))

    def test_A9_multiple_errors_collected(self):
        bad = {"spec": "x"}  # missing profiles + per_repo_overrides
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.SpecValidator(bad).validate()
        # Both errors should be in the message.
        msg = str(cm.exception)
        self.assertIn("missing or non-dict 'profiles'", msg)
        self.assertIn("missing or non-dict 'per_repo_overrides'", msg)

    def test_A10_load_spec_raises_for_missing_path(self):
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.load_spec(Path("/nonexistent/spec.json"))
        self.assertIn("spec not found at", str(cm.exception))

    def test_A13_validator_rejects_required_conversation_resolution(self):
        """It is a CLASSIC branch-protection field, not a ruleset rule type.

        This test asserted the opposite, and the assertion is why the bad
        entry survived: the validator accepted the type, a test pinned the
        acceptance, and the only thing that disagreed was the live API --

            PUT repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588
            422  Invalid property /rules/4: data matches no possible input

        The rulesets way to express the same intent is the `pull_request`
        rule's `required_review_thread_resolution` parameter, which
        pmoves_standard.json already sets (see test_A13b).
        """
        self.assertNotIn(
            "required_conversation_resolution", bp.VALID_RULESET_RULE_TYPES
        )
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["profiles"]["monorepo"]["rulesets"][0]["rules"].append(
            {"type": "required_conversation_resolution"}
        )
        with self.assertRaises(bp.BranchProtectionError):
            bp.SpecValidator(spec).validate()

    def test_A13b_thread_resolution_is_kept_as_a_pull_request_parameter(self):
        """The intent must survive removing the invalid rule.

        Anchored to the real spec rather than a fixture: dropping rule 4
        without this would silently drop conversation-resolution enforcement.
        """
        spec = bp.load_spec()
        rules = spec["profiles"]["monorepo"]["rulesets"][0]["rules"]
        pr = [r for r in rules if r["type"] == "pull_request"][0]
        self.assertTrue(pr["parameters"]["required_review_thread_resolution"])
        self.assertNotIn(
            "required_conversation_resolution", [r["type"] for r in rules]
        )

    def test_A14_validator_accepts_required_linear_history(self):
        # Caught a real bug: spec used "require_linear_history" (typo) but
        # the API expects "required_linear_history". Validator must accept
        # the correct spelling.
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["profiles"]["monorepo"]["rulesets"][0]["rules"].append(
            {"type": "required_linear_history"}
        )
        bp.SpecValidator(spec).validate()  # should not raise

    def test_A11_load_spec_validates_by_default(self):
        """Patch exists() too — otherwise load_spec short-circuits on
        "spec not found" and the test proves nothing about validation.
        """
        with mock.patch.object(Path, "exists", return_value=True), \
                mock.patch.object(
                    Path, "read_text", return_value=json.dumps({"spec": "x"})
                ):
            with self.assertRaises(bp.BranchProtectionError) as ctx:
                bp.load_spec(Path("/tmp/any.json"))
        msg = str(ctx.exception)
        self.assertNotIn("spec not found", msg)
        self.assertIn("profiles", msg)

    def test_A12_load_spec_skip_validation_with_flag(self):
        bad_but_skip = {"spec": "x"}  # would fail validation
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(bad_but_skip, f)
            tmp_path = Path(f.name)
        try:
            spec = bp.load_spec(tmp_path, validate=False)
        finally:
            tmp_path.unlink()
        self.assertEqual(spec, bad_but_skip)


# === B. ResolveRepoProfileTests ===

class ResolveRepoProfileTests(unittest.TestCase):
    def test_B1_resolve_repo_profile_default(self):
        name, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/monorepo")
        self.assertEqual(name, "monorepo")
        self.assertEqual(len(merged["rulesets"]), 1)
        self.assertEqual(merged["rulesets"][0]["name"], "[ main ]")

    def test_B2_resolve_repo_profile_with_ruleset_override(self):
        name, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/fork")
        self.assertEqual(name, "fork")
        # The ruleset_overrides should inject the required_status_checks rule.
        rs = merged["rulesets"][0]
        types = [r["type"] for r in rs["rules"]]
        self.assertIn("required_status_checks", types)
        contexts = {
            c["context"]
            for r in rs["rules"]
            if r["type"] == "required_status_checks"
            for c in r["parameters"]["required_status_checks"]
        }
        self.assertEqual(contexts, {"check-attribution", "ruff + ty diff"})

    def test_B3_resolve_repo_profile_unknown_repo_raises(self):
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/unknown")
        self.assertIn("no per_repo_overrides", str(cm.exception))

    def test_B4_resolve_repo_profile_unknown_profile_raises(self):
        bad_spec = dict(MINIMAL_SPEC)
        bad_spec["per_repo_overrides"] = {"TEST/x": {"profile": "ghost"}}
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp.resolve_repo_profile(bad_spec, "TEST/x")
        self.assertIn("not found in spec", str(cm.exception))

    def test_B5_resolve_repo_profile_does_not_mutate_input(self):
        # The function should deepcopy the profile so callers can safely mutate.
        before = json.dumps(MINIMAL_SPEC)
        _, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/monorepo")
        merged["rulesets"][0]["name"] = "MUTATED"
        after = json.dumps(MINIMAL_SPEC)
        self.assertEqual(before, after)

    def test_B6_resolve_repo_profile_rules_override_merges_by_type(self):
        # The ruleset_overrides for TEST/fork adds a `required_status_checks`
        # rule. The base fork profile already has `deletion`, `non_fast_forward`,
        # and `pull_request`. The merge must EXTEND (not replace) the rules
        # list so the base rules survive.
        _, merged = bp.resolve_repo_profile(MINIMAL_SPEC, "TEST/fork")
        rs = merged["rulesets"][0]
        types = [r["type"] for r in rs["rules"]]
        self.assertIn("deletion", types)
        self.assertIn("non_fast_forward", types)
        self.assertIn("pull_request", types)
        self.assertIn("required_status_checks", types)
        self.assertEqual(len(types), 4)

    def test_B7_resolve_repo_profile_override_rule_replaces_base(self):
        # When the override has a rule with the same type as a base rule,
        # the override wins. (E.g. an override of `pull_request` would
        # replace the base `pull_request`.)
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["per_repo_overrides"]["TEST/fork"]["ruleset_overrides"]["[ main ]"]["rules"].append(
            {
                "type": "pull_request",
                "parameters": {
                    "require_code_owner_review": True,
                    "dismiss_stale_reviews_on_push": False,
                    "required_approving_review_count": 5,
                    "required_review_thread_resolution": False,
                },
            }
        )
        _, merged = bp.resolve_repo_profile(spec, "TEST/fork")
        rs = merged["rulesets"][0]
        pr_rules = [r for r in rs["rules"] if r["type"] == "pull_request"]
        self.assertEqual(len(pr_rules), 1)
        self.assertEqual(pr_rules[0]["parameters"]["required_approving_review_count"], 5)


# === C. ResolveBranchTests ===

class ResolveBranchTests(unittest.TestCase):
    def test_C1_override_branch_wins(self):
        b = bp.resolve_branch(
            "POWERFULMOVES/PMOVES.AI", "main", MINIMAL_SPEC
        )
        self.assertEqual(b, "main")

    def test_C2_gitmodules_branch_when_no_override(self):
        # The branch-protection-sync.yml convention: track the gitlink
        # branch (which is PMOVES.AI-Edition-Hardened for most forks).
        fake_cfg = mock.MagicMock()
        fake_cfg.sections.return_value = [
            'submodule "PMOVES-foo"',
            'submodule "PMOVES.AI"',
        ]

        def fake_get(section, key, **kwargs):
            if key == "url":
                return "https://github.com/POWERFULMOVES/" + section.split('"')[1]
            if key == "branch":
                return "PMOVES.AI-Edition-Hardened"
            return kwargs.get("fallback", "")

        fake_cfg.get.side_effect = fake_get
        with mock.patch.object(bp, "_gitmodules_path", return_value=Path("/fake/.gitmodules")):
            with mock.patch("configparser.ConfigParser", return_value=fake_cfg):
                b = bp.resolve_branch(
                    "POWERFULMOVES/PMOVES.AI", None, MINIMAL_SPEC
                )
        self.assertEqual(b, "PMOVES.AI-Edition-Hardened")

    def test_C3_no_override_no_gitmodules_uses_default(self):
        with mock.patch.object(
            bp, "_gitmodules_path", return_value=Path("/nonexistent/.gitmodules")
        ):
            b = bp.resolve_branch(
                "POWERFULMOVES/PMOVES-newrepo", None, MINIMAL_SPEC
            )
        self.assertEqual(b, "main")

    def test_C4_no_gitmodules_entry_falls_back_to_default(self):
        """A dotted slug with no .gitmodules file resolves to main."""
        with mock.patch.object(
            bp, "_gitmodules_path", return_value=Path("/nonexistent/.gitmodules")
        ):
            b = bp.resolve_branch("POWERFULMOVES/PMOVES.AI", None, MINIMAL_SPEC)
        self.assertEqual(b, "main")  # no .gitmodules, no override -> main

    def test_C5_gitmodules_match_is_exact_not_substring(self):
        """`PMOVES-nats` must NOT match `submodule "PMOVES-nats-server"`.
        A substring match wrote the ruleset to another repo's branch.
        """
        fake_cfg = mock.MagicMock()
        fake_cfg.sections.return_value = ['submodule "PMOVES-nats-server"']

        def fake_get(section, key, **kwargs):
            if key == "url":
                return "https://github.com/POWERFULMOVES/PMOVES-nats-server.git"
            if key == "branch":
                return "PMOVES.AI-Edition-Hardened"
            return kwargs.get("fallback", "")

        fake_cfg.get.side_effect = fake_get
        with mock.patch.object(bp, "_gitmodules_path", return_value=Path("/fake/.gitmodules")), \
                mock.patch("configparser.ConfigParser", return_value=fake_cfg):
            b = bp.resolve_branch("POWERFULMOVES/PMOVES-nats", None, MINIMAL_SPEC)
        self.assertEqual(b, "main")

    def test_C6_gitmodules_matches_on_url_basename(self):
        """A section renamed away from the repo name still matches via url."""
        fake_cfg = mock.MagicMock()
        fake_cfg.sections.return_value = ['submodule "vendor/nats"']

        def fake_get(section, key, **kwargs):
            if key == "url":
                return "https://github.com/POWERFULMOVES/PMOVES-nats-server.git"
            if key == "branch":
                return "PMOVES.AI-Edition-Hardened"
            return kwargs.get("fallback", "")

        fake_cfg.get.side_effect = fake_get
        with mock.patch.object(bp, "_gitmodules_path", return_value=Path("/fake/.gitmodules")), \
                mock.patch("configparser.ConfigParser", return_value=fake_cfg):
            b = bp.resolve_branch(
                "POWERFULMOVES/PMOVES-nats-server", None, MINIMAL_SPEC
            )
        self.assertEqual(b, "PMOVES.AI-Edition-Hardened")

    def test_C7_profile_branch_read_only_from_the_repos_own_profile(self):
        """Step 3 must read spec.profiles[<resolved profile>].branch. Scanning
        every profile let one profile's branch leak onto unrelated repos.
        """
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["profiles"]["monorepo"]["branch"] = "trunk"
        with mock.patch.object(
            bp, "_gitmodules_path", return_value=Path("/nonexistent/.gitmodules")
        ):
            leaked = bp.resolve_branch("TEST/fork-only", None, spec, "fork")
            own = bp.resolve_branch("TEST/mono-only", None, spec, "monorepo")
        self.assertEqual(leaked, "main")   # fork profile declares no branch
        self.assertEqual(own, "trunk")


# === D. RulesetDiffTests ===

class RulesetDiffTests(unittest.TestCase):
    def test_D1_compliant_no_drift(self):
        # GitHub API returns the default branch literal in conditions.
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = COMPLIANT_RULESETS[0]
        drift = bp._ruleset_matches(expected, actual)
        # The ~DEFAULT_BRANCH comparison is skipped in the spec check,
        # so the ruleset should be in-sync.
        self.assertEqual(drift, [])

    def test_D2_missing_required_status_check_is_block(self):
        bad = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        bad["rules"] = [
            r for r in bad["rules"] if r["type"] != "required_status_checks"
        ]
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        drift = bp._ruleset_matches(expected, bad)
        self.assertTrue(
            any(
                d.severity == "block"
                and "required_status_checks" in d.field
                for d in drift
            )
        )

    def test_D3_extra_unexpected_rule_is_warn(self):
        bad = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        bad["rules"].append({"type": "creation"})
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        drift = bp._ruleset_matches(expected, bad)
        self.assertTrue(
            any(
                d.severity == "warn"
                and "creation" in d.field
                for d in drift
            )
        )

    def test_D4_drifted_parameters_is_block(self):
        bad = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        # Change required_approving_review_count from 1 to 0.
        for r in bad["rules"]:
            if r["type"] == "pull_request":
                r["parameters"]["required_approving_review_count"] = 0
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        drift = bp._ruleset_matches(expected, bad)
        self.assertTrue(
            any(
                d.severity == "block"
                and "pull_request" in d.field
                and "parameters" in d.field
                for d in drift
            )
        )

    def test_D5_drifted_bypass_actors_is_block(self):
        bad = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        # Drop the RepositoryRole bypass actor.
        bad["bypass_actors"] = []
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        drift = bp._ruleset_matches(expected, bad)
        self.assertTrue(
            any(
                d.severity == "block" and "bypass_actors" in d.field
                for d in drift
            )
        )

    def test_D6_enforcement_mismatch_is_block(self):
        bad = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        bad["enforcement"] = "disabled"
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        drift = bp._ruleset_matches(expected, bad)
        self.assertTrue(
            any(d.severity == "block" and "enforcement" in d.field for d in drift)
        )

    def test_D7_diff_resolves_default_branch_sentinel_against_resolved_branch(self):
        """The spec's ~DEFAULT_BRANCH resolves to the RESOLVED branch, and the
        actual include is qualified to refs/heads/<name> before comparing.
        """
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        # Sanity: ensure the actual has the literal "main" in include.
        self.assertEqual(actual["conditions"]["ref_name"]["include"], ["main"])
        drift = bp._ruleset_matches(expected, actual, "main")
        self.assertEqual(drift, [])

    def test_D8_diff_reports_include_drift_on_non_default_branch(self):
        """A ruleset targeting refs/heads/main is DRIFT for a fork whose
        gitlink branch is PMOVES.AI-Edition-Hardened. Skipping the include
        check (the pre-fix behavior) reported this as compliant while the
        hardened branch was unprotected.
        """
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        drift = bp._ruleset_matches(expected, actual, "PMOVES.AI-Edition-Hardened")
        self.assertTrue(
            any("conditions.ref_name.include" in d.field for d in drift)
        )

    def test_D10_api_defaulted_parameters_are_not_drift(self):
        """GitHub echoes back keys the spec never declares
        (`required_reviewers`, `allowed_merge_methods`). Strict equality made
        every audit report permanent drift and every apply re-PUT a correct
        ruleset. Only spec-declared keys are in scope.
        """
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        for r in actual["rules"]:
            if r["type"] == "pull_request":
                r["parameters"]["required_reviewers"] = []
                r["parameters"]["allowed_merge_methods"] = [
                    "merge", "squash", "rebase"
                ]
        drift = bp._ruleset_matches(expected, actual, "main")
        self.assertEqual(drift, [])

    def test_D11_declared_parameter_mismatch_still_reported(self):
        """The subset comparison must not mask a real parameter change."""
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        for r in actual["rules"]:
            if r["type"] == "pull_request":
                r["parameters"]["required_approving_review_count"] = 0
                r["parameters"]["allowed_merge_methods"] = ["merge"]
        drift = bp._ruleset_matches(expected, actual, "main")
        item = next(d for d in drift if "pull_request" in d.field)
        self.assertEqual(item.expected, {"required_approving_review_count": 1})
        self.assertEqual(item.actual, {"required_approving_review_count": 0})

    def test_D9_live_sentinel_is_not_silently_treated_as_a_match(self):
        """A live ruleset still carrying ~DEFAULT_BRANCH targets whatever
        GitHub calls the default branch — not necessarily the spec's branch.
        That must surface as drift, not be normalized away.
        """
        expected = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        actual = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        actual["conditions"]["ref_name"]["include"] = ["~DEFAULT_BRANCH"]
        drift = bp._ruleset_matches(
            expected, actual, "PMOVES.AI-Edition-Hardened"
        )
        self.assertTrue(
            any("conditions.ref_name.include" in d.field for d in drift)
        )


# === E. AuditTests ===

class AuditTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E1_audit_compliant_repo(self, mock_api):
        def side_effect(m, p, b=None):
            # The list endpoint returns a summary; the tool re-fetches each
            # ruleset by id for bypass_actors + full rules.
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return COMPLIANT_RULESETS
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return COMPLIANT_RULESETS[0]
            return None
        mock_api.side_effect = side_effect
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        self.assertTrue(result.is_compliant)
        self.assertEqual(result.drift, [])

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E2_audit_no_rulesets_is_block_drift(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: (
            [] if m == "GET" and p == "repos/TEST/monorepo/rulesets" else None
        )
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        self.assertFalse(result.is_compliant)
        self.assertTrue(any(d.severity == "block" for d in result.drift))

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E3_audit_with_explicit_profile(self, mock_api):
        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return COMPLIANT_RULESETS
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return COMPLIANT_RULESETS[0]
            return None
        mock_api.side_effect = side_effect
        result = bp.audit("TEST/monorepo", profile="monorepo", spec=MINIMAL_SPEC)
        self.assertEqual(result.profile, "monorepo")
        self.assertEqual(result.repo, "TEST/monorepo")

    def test_E4_audit_unknown_repo_raises(self):
        with self.assertRaises(bp.BranchProtectionError):
            bp.audit("TEST/unknown", spec=MINIMAL_SPEC)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_E5_audit_refetches_per_ruleset_for_bypass_actors(self, mock_api):
        # Lesson #1: the list endpoint returns a SUMMARY without
        # bypass_actors; the tool must re-fetch the per-ruleset body.
        summary_no_bypass = {
            k: v for k, v in COMPLIANT_RULESETS[0].items()
            if k != "bypass_actors"
        }

        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return [summary_no_bypass]
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return COMPLIANT_RULESETS[0]  # full body w/ bypass_actors
            return None
        mock_api.side_effect = side_effect
        result = bp.audit("TEST/monorepo", spec=MINIMAL_SPEC)
        # With the per-ruleset refetch, the ruleset is in sync.
        self.assertTrue(result.is_compliant)


# === F. ApplyTests ===

class ApplyTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_F1_apply_dry_run_creates_missing(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: (
            [] if m == "GET" and p == "repos/TEST/monorepo/rulesets" else None
        )
        result = bp.apply("TEST/monorepo", dry_run=True, spec=MINIMAL_SPEC)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.applied, [])
        # The dry-run should have prepared a POST call for the ruleset.
        methods = [c["method"] for c in result.calls]
        self.assertIn("POST", methods)
        # But no live API was called.
        self.assertEqual(mock_api.call_count, 1)  # only the GET

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_F2_apply_live_creates_missing(self, mock_api):
        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return []
            if m == "POST" and p == "repos/TEST/monorepo/rulesets":
                return {"id": 42, "name": "[ main ]"}
            return None
        mock_api.side_effect = side_effect
        result = bp.apply("TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC)
        self.assertFalse(result.dry_run)
        self.assertIn("repos/TEST/monorepo/rulesets/42", result.applied)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_F3_apply_updates_existing_with_drift(self, mock_api):
        drifted = json.loads(json.dumps(COMPLIANT_RULESETS[0]))
        # Drop a rule so there's drift.
        drifted["rules"] = [r for r in drifted["rules"] if r["type"] != "required_status_checks"]

        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return [drifted]
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return drifted
            if m == "PUT" and p == "repos/TEST/monorepo/rulesets/1":
                return {"id": 1, "name": "[ main ]"}
            return None
        mock_api.side_effect = side_effect
        result = bp.apply("TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC)
        self.assertFalse(result.dry_run)
        # A PUT was applied.
        put_calls = [a for a in result.applied if "/rulesets/1" in a]
        self.assertEqual(len(put_calls), 1)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_F4_apply_skips_in_sync(self, mock_api):
        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return COMPLIANT_RULESETS
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return COMPLIANT_RULESETS[0]
            return None
        mock_api.side_effect = side_effect
        result = bp.apply("TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC)
        self.assertFalse(result.dry_run)
        self.assertEqual(result.calls, [])
        self.assertEqual(result.applied, [])
        self.assertTrue(
            any("in sync" in s for s in result.skipped)
        )

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_F5_apply_includes_per_repo_ruleset_overrides(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: (
            [] if m == "GET" and p == "repos/TEST/fork/rulesets" else None
        )
        result = bp.apply("TEST/fork", dry_run=True, spec=MINIMAL_SPEC)
        # The POST body should include the per-repo override's required_status_checks.
        post_call = next(c for c in result.calls if c["method"] == "POST")
        rs_rules = post_call["body"]["rules"]
        rsc_rules = [r for r in rs_rules if r["type"] == "required_status_checks"]
        self.assertEqual(len(rsc_rules), 1)
        contexts = {c["context"] for c in rsc_rules[0]["parameters"]["required_status_checks"]}
        self.assertEqual(contexts, {"check-attribution", "ruff + ty diff"})

    def test_F6_apply_unknown_repo_raises(self):
        with self.assertRaises(bp.BranchProtectionError):
            bp.apply("TEST/unknown", spec=MINIMAL_SPEC)

    def test_F7_build_ruleset_body_substitutes_resolved_branch_for_sentinel(self):
        """~DEFAULT_BRANCH must be REPLACED by the resolved branch ref, not
        dropped. Dropping it left include empty, so the ruleset matched no ref.
        """
        rs = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        body = bp._build_ruleset_body(rs, "PMOVES.AI-Edition-Hardened")
        includes = body["conditions"]["ref_name"]["include"]
        self.assertNotIn("~DEFAULT_BRANCH", includes)
        self.assertEqual(includes, ["refs/heads/PMOVES.AI-Edition-Hardened"])

    def test_F8_build_ruleset_body_does_not_mutate_the_spec(self):
        """The builder deep-copies; the in-memory spec keeps its sentinel."""
        rs = MINIMAL_SPEC["profiles"]["monorepo"]["rulesets"][0]
        bp._build_ruleset_body(rs, "main")
        self.assertEqual(
            rs["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"]
        )

    def test_F9_apply_records_ruleset_when_post_returns_empty_body(self):
        """_gh_api returns None on an empty response body. The write already
        happened, so apply must record it rather than raising AttributeError.
        """
        def fake_api(method, path, body=None):
            if method == "GET" and path.endswith("/rulesets"):
                return []
            return None  # POST returns an empty body

        with mock.patch(
            "pmoves.tools.branch_protection._gh_api", side_effect=fake_api
        ):
            result = bp.apply(
                "TEST/monorepo", dry_run=False, spec=MINIMAL_SPEC
            )
        self.assertEqual(result.applied, ["repos/TEST/monorepo/rulesets/?"])


# === G. DriftCheckTests ===

class DriftCheckTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_G1_drift_check_returns_one_report_per_repo(self, mock_audit):
        mock_audit.side_effect = lambda repo, profile=None, spec=None: bp.AuditResult(
            repo=repo, profile=profile or "x", branch="main",
            drift=[], checked_at="t", source_url="u"
        )
        report = bp.drift_check("TEST", spec=MINIMAL_SPEC)
        self.assertEqual(len(report.repos), 2)  # TEST/monorepo + TEST/fork
        self.assertEqual(report.org, "TEST")

    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_G2_drift_check_includes_only_org_repos(self, mock_audit):
        mock_audit.side_effect = lambda repo, profile=None, spec=None: bp.AuditResult(
            repo=repo, profile=profile or "x", branch="main",
            drift=[], checked_at="t", source_url="u"
        )
        report = bp.drift_check("OTHER_ORG", spec=MINIMAL_SPEC)
        self.assertEqual(report.repos, [])

    @mock.patch("pmoves.tools.branch_protection.audit")
    def test_G3_drift_check_surfaces_audit_error(self, mock_audit):
        def fake_audit(repo, profile=None, spec=None):
            if repo == "TEST/monorepo":
                raise bp.BranchProtectionError("gh subprocess failed: token expired")
            return bp.AuditResult(
                repo=repo, profile=profile or "x", branch="main",
                drift=[], checked_at="t", source_url="u"
            )
        mock_audit.side_effect = fake_audit
        report = bp.drift_check("TEST", spec=MINIMAL_SPEC)
        errored = next(r for r in report.repos if r.repo == "TEST/monorepo")
        self.assertFalse(errored.is_compliant)
        self.assertEqual(errored.drift[0].field, "audit_error")


# === H. CLITests ===

class CLITests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_H1_audit_cli_exits_0_when_compliant(self, mock_api):
        def side_effect(m, p, b=None):
            if m == "GET" and p == "repos/TEST/monorepo/rulesets":
                return COMPLIANT_RULESETS
            if m == "GET" and p == "repos/TEST/monorepo/rulesets/1":
                return COMPLIANT_RULESETS[0]
            return None
        mock_api.side_effect = side_effect
        with mock.patch(
            "sys.argv", ["bp", "--spec", "/tmp/none.json", "audit", "--repo", "TEST/monorepo"]
        ):
            with mock.patch(
                "pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC
            ):
                rc = bp.main()
        self.assertEqual(rc, 0)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_H2_audit_cli_exits_1_when_drift(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: (
            [] if m == "GET" and "rulesets" in p else None
        )
        with mock.patch(
            "sys.argv", ["bp", "--spec", "/tmp/none.json", "audit", "--repo", "TEST/monorepo"]
        ):
            with mock.patch(
                "pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC
            ):
                rc = bp.main()
        self.assertEqual(rc, 1)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_H3_drift_check_cli_exits_2_when_any_repo_drift(self, mock_api):
        def side_effect(m, p, b=None):
            if p == "repos/TEST/monorepo/rulesets":
                return []  # drift
            if p == "repos/TEST/fork/rulesets":
                return COMPLIANT_RULESETS  # drifts from the fork profile's checks
            if p == "repos/TEST/fork/rulesets/1":
                return COMPLIANT_RULESETS[0]
            return None
        mock_api.side_effect = side_effect
        with mock.patch(
            "sys.argv", ["bp", "--spec", "/tmp/none.json", "drift-check", "--org", "TEST"]
        ):
            with mock.patch(
                "pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC
            ):
                rc = bp.main()
        self.assertEqual(rc, 2)

    @mock.patch("pmoves.tools.branch_protection._gh_api")
    def test_H4_apply_cli_default_is_dry_run(self, mock_api):
        mock_api.side_effect = lambda m, p, b=None: (
            [] if m == "GET" and "rulesets" in p else None
        )
        with mock.patch(
            "sys.argv", ["bp", "--spec", "/tmp/none.json", "apply", "--repo", "TEST/monorepo"]
        ):
            with mock.patch(
                "pmoves.tools.branch_protection.load_spec", return_value=MINIMAL_SPEC
            ):
                rc = bp.main()
        # dry-run exits 0, even though there's drift.
        self.assertEqual(rc, 0)


# === I. GHErrorPathTests ===

class GHErrorPathTests(unittest.TestCase):
    @mock.patch("pmoves.tools.branch_protection.shutil.which", return_value=None)
    def test_I1_gh_missing_raises(self, mock_which):
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp._gh_api("GET", "repos/foo")
        self.assertIn("gh CLI not found", str(cm.exception))

    @mock.patch("pmoves.tools.branch_protection.shutil.which", return_value="/usr/bin/gh")
    @mock.patch("pmoves.tools.branch_protection.subprocess.run")
    def test_I2_gh_timeout_raises(self, mock_run, mock_which):
        """which() is patched so the test reaches subprocess even on a
        runner with no gh on PATH; the message asserts on GH_TIMEOUT_SECONDS.
        """
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=bp.GH_TIMEOUT_SECONDS
        )
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp._gh_api("GET", "repos/foo/rulesets")
        self.assertIn(f"timed out after {bp.GH_TIMEOUT_SECONDS}s", str(cm.exception))

    @mock.patch("pmoves.tools.branch_protection.shutil.which", return_value="/usr/bin/gh")
    @mock.patch("pmoves.tools.branch_protection.subprocess.run")
    def test_I3_gh_nonzero_returns_raises(self, mock_run, mock_which):
        """A non-zero gh exit that is not "Branch not protected" raises."""
        mock_run.return_value = _MockProc(
            returncode=1, stdout="", stderr="gh: not found"
        )
        with self.assertRaises(bp.BranchProtectionError) as cm:
            bp._gh_api("GET", "repos/foo/rulesets")
        self.assertIn("gh: not found", str(cm.exception))

    @mock.patch("pmoves.tools.branch_protection.shutil.which", return_value="/usr/bin/gh")
    @mock.patch("pmoves.tools.branch_protection.subprocess.run")
    def test_I4_gh_unprotected_branch_returns_none(self, mock_run, mock_which):
        """"Branch not protected" is an expected state, not an error."""
        mock_run.return_value = _MockProc(
            returncode=1, stdout="", stderr="Branch not protected"
        )
        result = bp._gh_api("GET", "repos/foo/branches/main/protection")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
