"""Tests for the claude-pmoves-mavis launcher shim (slice A).

These tests assert the SHAPE of the wrapper, not its runtime behavior.
Runtime smoke tests (executing the launcher, verifying settings.json is NOT
written) belong in tests/test_launchers_smoke.sh and run via the smoke harness.

We test the wrapper because it's a separate-file artifact that has to:
- pin --backend=minimax by default
- inherit operator-set PMOVES_CLAUDE_BACKEND
- exec the main claude-pmoves.sh with --backend=<value> "$@"
- exist in three forms (bash / PowerShell / Windows wrapper)
- have per-node forms (5090 first; 4090/b850/z890 in follow-ups)
- have a NOT-here-yet form for the OTHER 3 nodes (so the registry generator knows)

Per DARKXSIDE practice (2026-09-16, no-workarounds + SDK + doc provenance):
the wrapper is the fix. PR #3184 --backend= flag is the underlying mechanism;
this test class asserts the wrapper's invocation shape, NOT the underlying
mechanism (which has its own 33 tests in pmoves/tools/tests/test_claude_backend.py).
"""

import os
import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]  # pmoves/tools/tests/ -> PMOVES.AI
PROVISION = REPO_ROOT / "deploy" / "provision"


class MavisWrapperShapeTests(unittest.TestCase):
    """The wrapper files exist, have the right shebang / encoding, and don't
    duplicate the env-strip / blocklist logic that lives in claude-pmoves.sh."""

    def test_bash_wrapper_exists_and_is_executable(self):
        path = PROVISION / "claude-pmoves-mavis.sh"
        self.assertTrue(path.exists(), f"missing: {path}")
        self.assertTrue(os.access(path, os.X_OK), f"not executable: {path}")
        with open(path, encoding="utf-8") as f:
            head = f.read(256)
        self.assertTrue(head.startswith("#!/usr/bin/env bash"), "wrong shebang")

    def test_powershell_wrapper_exists(self):
        path = PROVISION / "claude-pmoves-mavis.ps1"
        self.assertTrue(path.exists(), f"missing: {path}")
        with open(path, encoding="utf-8") as f:
            head = f.read(512)
        self.assertIn("$ErrorActionPreference", head, "must declare ErrorActionPreference")

    def test_cmd_wrapper_exists(self):
        path = PROVISION / "claude-pmoves-mavis.cmd"
        self.assertTrue(path.exists(), f"missing: {path}")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("@echo off", content)
        self.assertIn("claude-pmoves-mavis.ps1", content)

    def test_bash_wrapper_does_not_duplicate_env_strip(self):
        """The wrapper should exec the main launcher, NOT inline its own env-strip.
        Duplication would mean bug fixes to env-strip have to land in two places.
        """
        path = PROVISION / "claude-pmoves-mavis.sh"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Should NOT contain the Mavis SDK env strip markers
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", content,
                         "wrapper duplicates env-strip logic; should exec main launcher")
        # Should exec the main launcher
        self.assertIn("claude-pmoves.sh", content,
                      "wrapper does not exec the main launcher")

    def test_bash_wrapper_pins_backend_minimax_default(self):
        path = PROVISION / "claude-pmoves-mavis.sh"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PMOVES_CLAUDE_BACKEND:=minimax", content,
                      "wrapper must default to backend=minimax")
        self.assertIn("--backend=", content,
                      "wrapper must pass --backend flag to main launcher")


class MavisNodeVariantsTests(unittest.TestCase):
    """Per-node variants exist for 5090 (first slice) and are not yet there
    for the other nodes (4090, b850, z890) -- those are follow-up slices."""

    def test_5090_mavis_exists(self):
        for ext in (".sh", ".ps1", ".cmd"):
            path = PROVISION / f"claude-pmoves-5090-mavis{ext}"
            self.assertTrue(path.exists(), f"missing: {path}")

    def test_5090_mavis_sets_node_id_5090(self):
        path = PROVISION / "claude-pmoves-5090-mavis.sh"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('PMOVES_NODE_ID="5090"', content,
                      "5090 variant must set PMOVES_NODE_ID=5090")
        self.assertIn("claude-pmoves-mavis.sh", content,
                      "5090 variant must exec the -mavis wrapper, not the default launcher")

    def test_5090_mavis_ps1_sets_node_id(self):
        path = PROVISION / "claude-pmoves-5090-mavis.ps1"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("$env:PMOVES_NODE_ID = '5090'", content,
                      "5090 .ps1 variant must set $env:PMOVES_NODE_ID")
        self.assertIn("claude-pmoves-mavis.ps1", content,
                      "5090 .ps1 variant must exec the -mavis wrapper")

    def test_other_node_mavis_variants_not_yet_present(self):
        """Document the follow-up slice: 4090/b850/z890 -mavis variants land
        after the 5090 variant ships and the operator confirms the pattern."""
        for node in ("4090", "b850", "z890"):
            for ext in (".sh", ".ps1", ".cmd"):
                path = PROVISION / f"claude-pmoves-{node}-mavis{ext}"
                self.assertFalse(path.exists(),
                                 f"{node}-mavis{ext} present prematurely -- "
                                 f"follow-up slice scope was not yet approved")


class HyperagintFormTests(unittest.TestCase):
    """The HyPeRAGInT agent form (per-agent identity) exists and follows the
    established pattern (5090-CLAUDE.yaml / DARKXSIDE.yaml etc.)."""

    def test_form_exists(self):
        path = REPO_ROOT / "pmoves" / "configs" / "agents" / "forms" / "hyperagint.yaml"
        self.assertTrue(path.exists(), f"missing: {path}")

    def test_form_has_required_keys(self):
        path = REPO_ROOT / "pmoves" / "configs" / "agents" / "forms" / "hyperagint.yaml"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Standard form keys (mirrors 5090-CLAUDE.yaml)
        for key in ("name:", "weights:", "band_emphasis:",
                    "mesh_offload_threshold:", "sharing:"):
            self.assertIn(key, content, f"missing required key: {key}")
        # HyPeRAGInT-specific keys (per design doc H1)
        self.assertIn("harness_target:", content,
                      "HyPeRAGInT form must declare harness_target")
        self.assertIn("memory_overrides:", content,
                      "HyPeRAGInT form must declare memory_overrides for Cipher/Hi-RAG")
        self.assertIn("miniagent_policy:", content,
                      "HyPeRAGInT form must declare miniagent_policy (miniagents are HyPeRAGInT not Archon)")

    def test_form_name_is_hyperagint(self):
        path = REPO_ROOT / "pmoves" / "configs" / "agents" / "forms" / "hyperagint.yaml"
        with open(path, encoding="utf-8") as f:
            first_line = f.readline().strip()
        self.assertEqual(first_line, "name: HyPeRAGInT",
                         f"form name line must be exactly 'name: HyPeRAGInT', got: {first_line}")

    def test_form_references_built_from_minimaxx_agint(self):
        path = REPO_ROOT / "pmoves" / "configs" / "agents" / "forms" / "hyperagint.yaml"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PMOVES-MiniMaXX-AGInT", content,
                      "HyPeRAGInT form must declare build-from MiniMaXX-AGInT lineage")


class DefaultLauncherMia120BackwardsCompatTests(unittest.TestCase):
    """The DEFAULT claude-pmoves (no -mavis suffix) MUST NOT load the Mavis
    overlay. This is the operator's 2026-10-03 directive: vanilla Claude Code
    settings, Claude Max by default, no SDK hijack."""

    def test_default_bash_does_not_set_pmoves_claude_backend(self):
        path = PROVISION / "claude-pmoves.sh"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # The default launcher should NOT pin a backend; it should default to auto.
        # (PR #3184 sets the default to empty/auto, which is correct.)
        # We look for actual shell ASSIGNMENT patterns, not comments or
        # error-message strings that name "minimax" as one of the valid values.
        # Assignment patterns: `PMOVES_CLAUDE_BACKEND=minimax`, `export PMOVES_CLAUDE_BACKEND=minimax`
        # Reject also: `${PMOVES_CLAUDE_BACKEND:-minimax}` (default-value override)
        #              `${VAR:=minimax}` (parameter expansion with default)
        for line in content.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Skip quoted strings (Write-Error / Write-Host / echo / printf)
            if any(q in line for q in ('Write-', 'echo ', 'printf ', 'Write-Error')):
                # Even inside a quoted message, only fail if it's clearly a
                # default-value expansion (`${VAR:=minimax}` or `${VAR:-minimax}`)
                # which would actually pin the default.
                if "${PMOVES_CLAUDE_BACKEND:-minimax}" in line or "${PMOVES_CLAUDE_BACKEND:=minimax}" in line:
                    self.fail(f"default launcher pins minimax via default-value expansion: {line!r}")
                continue
            # Pure shell assignment `KEY=minimax` (case-insensitive minimax)
            if re.search(r"\bPMOVES_CLAUDE_BACKEND\s*=\s*['\"]?minimax['\"]?\s*$", line, re.IGNORECASE):
                self.fail(f"default launcher pins minimax: {line!r}")
            # Default-value expansion
            if "${PMOVES_CLAUDE_BACKEND:-minimax}" in line or "${PMOVES_CLAUDE_BACKEND:=minimax}" in line:
                self.fail(f"default launcher pins minimax via default-value expansion: {line!r}")

    def test_default_ps1_does_not_set_pmoves_claude_backend_minimax(self):
        path = PROVISION / "claude-pmoves.ps1"
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Same invariant for PowerShell. Look for actual PowerShell assignment
        # patterns, not Write-Error / Write-Host messages.
        for line in content.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Skip Write-Error / Write-Host / echo strings (they mention "minimax"
            # in validation messages but aren't assignments)
            if any(q in line for q in ('Write-Error', 'Write-Host', 'Write-Verbose')):
                continue
            # PowerShell assignment: `$env:PMOVES_CLAUDE_BACKEND = "minimax"` or `='minimax'`
            if re.search(r"\$env:PMOVES_CLAUDE_BACKEND\s*=\s*['\"]minimax['\"]", line, re.IGNORECASE):
                self.fail(f"default .ps1 launcher pins minimax: {line!r}")
            # Default-value expansion (rare in PS but possible)
            if "${env:PMOVES_CLAUDE_BACKEND:-minimax}" in line or "${env:PMOVES_CLAUDE_BACKEND:=minimax}" in line:
                self.fail(f"default .ps1 launcher pins minimax via default-value expansion: {line!r}")


if __name__ == "__main__":
    unittest.main()