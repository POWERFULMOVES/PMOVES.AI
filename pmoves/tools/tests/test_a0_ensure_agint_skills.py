"""Regression tests for pmoves/tools/a0/ensure-agint-skills.ps1.

Pins:
1. The path-separator fix on the destination: `"usr\\skills\\" + $skill.Name`
   must use a trailing backslash, NOT bare concatenation. The original v0
   dropped the separator and produced `usr\\skillsfind-skills` instead of
   `usr\\skills\\find-skills`, which writes the skill to the wrong directory.
2. The `-WhatIf` switch must be wired and must NOT call Copy-Item.
3. The `-SourcePath` parameter must override the default `skills\\PMOVES-skills\\skills`.

The tests are static (read the .ps1 source) because the script's
operational surface depends on the live PMOVES-skills submodule checkout,
which is not portable across the test fleet. Static pinning catches the
regression class without coupling the test to a host layout.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PS1_PATH = (
    Path(__file__).resolve().parents[1]
    / "a0"
    / "ensure-agint-skills.ps1"
)


class EnsureAgintSkillsScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PS1_PATH.read_text(encoding="utf-8")

    def test_script_exists(self):
        self.assertTrue(PS1_PATH.exists(), f"missing: {PS1_PATH}")

    def test_destination_path_uses_separator(self):
        """The destination must be `usr\\skills\\<skill>` not `usr\\skills<skill>`.

        Pin via a regex that matches the canonical form. A regression to the
        bare-concat form (`"usr\\skills" + $skill.Name`) fails this.
        """
        # Look for the line that constructs $dst. The fixed form contains a
        # trailing backslash inside the literal. The buggy form does not.
        pattern = re.compile(
            r'\$dst\s*=\s*Join-Path\s+\$inst\s+\(\s*["\']usr\\skills\\["\']\s*\+\s*\$skill\.Name\s*\)'
        )
        self.assertRegex(
            self.text,
            pattern,
            "ensure-agint-skills.ps1 must use 'usr\\skills\\' (trailing slash) before concatenating $skill.Name; "
            "the bare-concat form drops the path separator and writes skills to usr\\skills<name> instead of usr\\skills\\<name>.",
        )

    def test_no_bare_concat_path(self):
        """Negative pin: the buggy form must NOT appear anywhere in the file."""
        bug = re.compile(
            r'\$dst\s*=\s*Join-Path\s+\$inst\s+\(\s*["\']usr\\skills["\']\s*\+\s*\$skill\.Name\s*\)'
        )
        self.assertNotRegex(
            self.text,
            bug,
            "ensure-agint-skills.ps1 still contains the bare-concat path bug; "
            "the destination is computed without a separator, producing usr\\skills<name>.",
        )

    def test_whatif_parameter_declared(self):
        """The script must declare `[switch]$WhatIf` so operators can dry-run."""
        self.assertRegex(
            self.text,
            re.compile(r"\[switch\]\s*\$WhatIf"),
            "ensure-agint-skills.ps1 must declare [switch]$WhatIf for safe dry-run.",
        )

    def test_whatif_branch_skips_copy_item(self):
        """The WhatIf branch must early-return BEFORE Copy-Item runs."""
        # Find the WhatIf block and assert Copy-Item appears AFTER the early
        # return, not inside the WhatIf branch.
        whatif_match = re.search(
            r"if\s*\(\$WhatIf\)\s*\{(?P<body>.*?)\}",
            self.text,
            re.DOTALL,
        )
        self.assertIsNotNone(whatif_match, "missing WhatIf branch in ensure-agint-skills.ps1")
        body = whatif_match.group("body")
        # Inside the WhatIf branch, only Write-Output / counter++ is allowed.
        self.assertNotIn(
            "Copy-Item",
            body,
            "WhatIf branch must not call Copy-Item; the dry-run mode exists precisely to avoid mutation.",
        )
        # And the WhatIf branch must have an early return so the Copy-Item
        # later in the script is not reached.
        self.assertIn(
            "return",
            body,
            "WhatIf branch must early-return so Copy-Item is not reached for WhatIf invocations.",
        )

    def test_sourcepath_parameter_declared(self):
        """The `-SourcePath` parameter must exist so operators can override the default."""
        self.assertRegex(
            self.text,
            re.compile(r"\[string\]\s*\$SourcePath"),
            "ensure-agint-skills.ps1 must declare [string]$SourcePath to override the default PMOVES-skills path.",
        )

    def test_default_sourcepath_is_pmoves_skills(self):
        """The default `$src` must point at `skills\\PMOVES-skills\\skills` (or be overridden by -SourcePath)."""
        # The script does: $src = if ($SourcePath) { $SourcePath } else { Join-Path $repoRoot "skills\PMOVES-skills\skills" }
        self.assertRegex(
            self.text,
            re.compile(r'skills\\PMOVES-skills\\skills'),
            "ensure-agint-skills.ps1 default source must be the PMOVES-skills submodule path.",
        )

    def test_exit_codes_2_on_partial_failure(self):
        """On any per-skill copy failure, the script must exit 2 (not 0)."""
        self.assertRegex(
            self.text,
            re.compile(r"\$failed\s*-\s*gt\s*0.*\bexit\s+2", re.DOTALL),
            "ensure-agint-skills.ps1 must exit 2 when any per-skill copy fails.",
        )

    def test_error_message_includes_hint(self):
        """Missing-source error must include a `-SourcePath` hint for the operator."""
        # The check is for the literal string 'pass -SourcePath' in the
        # Write-Output error block.
        self.assertIn(
            "pass -SourcePath",
            self.text,
            "missing-source error must include 'pass -SourcePath' hint for the operator.",
        )

    def test_regression_note_present(self):
        """The pinned regression note must be present in the header so future authors see it."""
        self.assertIn(
            "REGRESSION NOTE",
            self.text,
            "header must contain REGRESSION NOTE documenting the path-separator bug.",
        )


if __name__ == "__main__":
    unittest.main()
