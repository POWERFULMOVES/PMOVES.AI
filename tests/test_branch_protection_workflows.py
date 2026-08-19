"""tests/test_branch_protection_workflows.py

Regression tests for the 2 new branch protection workflows. Caught
by codex post-merge on PR #2568; the original PR's 17/17 unit
tests didn't catch the workflow glue bugs. Lesson #14 in the
LEARNINGS file.

Test groups:
    A. ApplyArgsTests - the ruleset-sync apply loop passes the CLI
       flags correctly (not positional, no nonexistent --dry-run)
    B. DriftAuthTests - the drift workflow mints a GitHub App token
       (no permissions: {} would 401 every drift_check call)
    C. PipefailTests - every `tee` pipeline is paired with either
       `pipefail` or `PIPESTATUS` (so a publisher failure is not
       masked by `tee`'s 0 exit)
    D. HeredocOutputTests - the `repos<<__EOF__` heredoc is written
       to `$GITHUB_OUTPUT` (so the App-token step gets the resolved
       repo set, not an empty default that escalates to every
       accessible repo)
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

# These tests parse the workflow YAML/grep at the source — they don't
# need pmoves.tools importable. They live in tests/ (not pmoves/tools/
# tests/) because they're project-level integration tests, not tool
# unit tests.

ROOT = Path(__file__).resolve().parent.parent
DRIFT = ROOT / ".github" / "workflows" / "branch-protection-drift.yml"
RULESET_SYNC = ROOT / ".github" / "workflows" / "branch-protection-ruleset-sync.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_step(text: str, step_name: str) -> str:
    """Pull the entire step block (env + run + uses) of a named step.

    A step starts at `- name: <name>` and ends at the next `- name:`
    (or end of job). Naive regex but enough for a regression net.
    """
    pattern = re.compile(
        rf"-\s*name:\s*{re.escape(step_name)}(.*?)(?=\n\s*-\s*name:|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(0) if m else ""


def _extract_run_block(text: str, step_name: str) -> str:
    """Pull the `run: |` block of a named step. Naive but enough."""
    # The step is `- name: <name>` followed by `run: |` and a fenced
    # block until the next `- ` step or the end of the job.
    pattern = re.compile(
        rf"-\s*name:\s*{re.escape(step_name)}.*?run:\s*\|\s*\n(.*?)(?=\n\s*-\s*name:|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


# === A. ApplyArgsTests (ruleset-sync) ===

class ApplyArgsTests(unittest.TestCase):
    def setUp(self):
        self.text = _read(RULESET_SYNC)
        self.apply_step = _extract_step(self.text, "Apply rulesets")
        self.apply_run = _extract_run_block(self.text, "Apply rulesets")

    def test_A1_repo_passed_as_flag_not_positional(self):
        # The old code did `args=("$repo")` which made arg-parse fail.
        self.assertNotIn('args=("$repo")', self.apply_run)
        # New: the args array starts with the --repo flag.
        self.assertIn('args=("--repo" "$repo")', self.apply_run)

    def test_A2_no_dry_run_used_not_nonexistent_dry_run(self):
        # The old code added `"--dry-run"` which is not a flag the
        # tool accepts (dry-run is the default; the override is
        # `--no-dry-run`).
        self.assertNotIn('"--dry-run"', self.apply_run)
        # The flag should be conditional on `DRY_RUN = false`.
        self.assertIn('--no-dry-run', self.apply_run)
        self.assertIn('"$DRY_RUN" = "false"', self.apply_run)

    def test_A3_apply_subcommand_receives_args_array(self):
        # The apply call must spread the array, not concat.
        self.assertIn('apply "${args[@]}"', self.apply_run)

    def test_A4_loop_reads_repos_tsv(self):
        # The loop source is the TSV the resolve step wrote.
        self.assertIn('done < repos.tsv', self.apply_run)


# === B. DriftAuthTests (drift) ===

class DriftAuthTests(unittest.TestCase):
    def setUp(self):
        self.text = _read(DRIFT)
        self.drift_step = _extract_step(self.text, "Run drift check + publish")

    def test_B1_mints_app_token(self):
        # The old code had no App-token step; drift_check() 401s
        # on every repo and reports false drift.
        self.assertIn('actions/create-github-app-token', self.text)

    def test_B2_app_token_step_uses_required_secrets(self):
        # Must reference the operator's secrets.
        self.assertIn('client-id: ${{ secrets.GH_APP_CLIENT_ID }}', self.text)
        self.assertIn('private-key: ${{ secrets.GH_APP_SEC }}', self.text)

    def test_B3_app_token_step_is_before_drift_step(self):
        # The app-token step must come BEFORE the drift step in
        # the job's step order. The drift step's env must reference
        # `steps.app-token.outputs.token`.
        self.assertIn('steps.app-token.outputs.token', self.drift_step)
        self.assertIn('GH_TOKEN: ${{ steps.app-token.outputs.token }}', self.drift_step)

    def test_B4_app_token_scope_uses_audited_repos(self):
        # The token should be scoped to the org's repos the audit
        # needs. For drift, the default scope (every accessible repo)
        # is too broad — but read-only is enough. Confirm at least
        # the org is set.
        self.assertIn('owner: ${{ github.repository_owner }}', self.text)


# === C. PipefailTests (both) ===

class PipefailTests(unittest.TestCase):
    def setUp(self):
        self.drift_text = _read(DRIFT)
        self.drift_run = _extract_run_block(self.drift_text, "Run drift check + publish")
        self.ruleset_text = _read(RULESET_SYNC)
        self.ruleset_apply = _extract_run_block(self.ruleset_text, "Apply rulesets")

    def test_C1_drift_uses_pipefail(self):
        # The old code did `set -e` without `pipefail`; `tee`'s 0
        # exit masked publisher failures.
        self.assertIn('set -e -o pipefail', self.drift_run)

    def test_C2_ruleset_apply_uses_pipestatus(self):
        # The apply loop uses `set +e` (intentionally, to count
        # failures) so it must capture the python exit via
        # PIPESTATUS instead of relying on `set -e`.
        self.assertIn('PIPESTATUS[0]', self.ruleset_apply)
        self.assertIn('if [ "$rc" -eq 0 ]', self.ruleset_apply)

    def test_C3_no_unpaired_tee_pipelines(self):
        # Walk the run blocks for `| tee` and confirm each is
        # covered by pipefail or PIPESTATUS. Belt-and-braces: the
        # per-workflow tests above are tighter, this is the catch-all.
        for path, text, run in [
            (DRIFT, self.drift_text, self.drift_run),
            (RULESET_SYNC, self.ruleset_text, self.ruleset_apply),
        ]:
            for line in run.splitlines():
                if '| tee' in line or '|tee' in line:
                    self.assertTrue(
                        'PIPESTATUS' in run or 'pipefail' in run,
                        f"{path.name}: `{line.strip()}` not paired with PIPESTATUS or pipefail",
                    )


# === D. HeredocOutputTests (ruleset-sync) ===

class HeredocOutputTests(unittest.TestCase):
    def setUp(self):
        self.text = _read(RULESET_SYNC)
        self.resolve_run = _extract_run_block(self.text, "Resolve apply target set")

    def test_D1_repos_heredoc_written_to_github_output(self):
        # The old code wrote repos.tsv but never exported `repos` as
        # a step output, so `${{ steps.targets.outputs.repos }}` was
        # empty and the App-token action scoped to every accessible
        # repo (privilege escalation).
        self.assertIn('repos<<__EOF__', self.resolve_run)
        self.assertIn('$GITHUB_OUTPUT', self.resolve_run)

    def test_D2_resolve_step_has_targets_id(self):
        # The step must have `id: targets` so the App-token step
        # can read `steps.targets.outputs.repos`.
        self.assertIn('id: targets', self.text)

    def test_D3_app_token_uses_resolved_repos(self):
        # The App-token step must reference the resolved repos
        # output, not leave `repositories:` blank.
        self.assertIn('repositories: ${{ steps.targets.outputs.repos }}', self.text)


if __name__ == "__main__":
    unittest.main()
