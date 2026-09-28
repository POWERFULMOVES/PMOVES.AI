#!/usr/bin/env python3
# test_pmoves_launcher_generator.py
# ============================================================================
# Tests for pmoves/tools/pmoves_launcher_generator.py
#
# Coverage:
#   1. Generator produces a non-empty Plan when run against the live repo.
#   2. Output is byte-stable: re-running produces identical files (idempotence).
#   3. Every emitted `.sh` passes `bash -n`.
#   4. Every emitted `.ps1` parses via System.Management.Automation.Language.
#   5. The manifest hash matches the on-disk file (no drift after regen).
#   6. The hand-written claude-pmoves.{sh,ps1,cmd} are NOT in the plan
#      (managed=hand, include_hand=False default).
#   7. Per-node pin files are emitted for every multi-node CLI identity in
#      agent_registry.yaml that has a matching `signature` (exact OR
#      `-<family>` suffix) AND has no listening port.
#   8. Per-CLI signature_aliases (`kilo` <-> `kilocode`) bind correctly.
#
# Run:
#   python -m pytest pmoves/tools/tests/test_pmoves_launcher_generator.py -v
#   OR
#   python pmoves/tools/tests/test_pmoves_launcher_generator.py     # standalone
# ============================================================================

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make the tools/ folder importable when running standalone.
_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent.parent
sys.path.insert(0, str(_TOOLS))

import pmoves_launcher_generator as gen  # noqa: E402


REPO_ROOT = Path(os.environ.get("PMOVES_REPO_ROOT") or _REPO).resolve()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestGeneratorRegistryDriven(unittest.TestCase):
    """1. Generator produces a non-empty Plan when run against the live repo."""

    def test_plan_loads_tools_from_registry(self):
        plan = gen.build_plan(REPO_ROOT)
        # cli_tools.yaml registers 7 wrappers; all should be loaded.
        names = {t.name for t in plan.tools}
        self.assertIn("claude-pmoves", names)
        self.assertIn("crush-pmoves", names)
        self.assertIn("kilo-pmoves", names)
        self.assertIn("kimi-pmoves", names)
        self.assertIn("codex-pmoves", names)
        self.assertIn("hermes-pmoves", names)
        self.assertIn("pmoves-mini", names)

    def test_plan_finds_per_node_claude_identities(self):
        # 4 claude_<node> identities with no listening port in agent_registry.yaml.
        plan = gen.build_plan(REPO_ROOT)
        claude_idents = [i for i in plan.identities if i.parent_tool == "claude"]
        node_ids = {i.node_id for i in claude_idents}
        # claude_4090 uses node_affinity=[laptop-4090] in the registry;
        # that's the spelling the generator emits -- canonical normalization
        # is a separate resolver (pmoves/configs/node-vocabulary.yaml).
        self.assertIn("laptop-4090", node_ids)
        self.assertIn("pmoves-b850", node_ids, "knuckles entry binds via signature suffix 'b850-claude'")
        self.assertIn("5090", node_ids)
        self.assertIn("z890", node_ids)

    def test_kilo_aliases_match_kilocode_signature(self):
        # kilo-pmoves wrapper family is `kilo`; agent_registry signature is
        # `kilocode`.  DEFAULT_SIGNATURE_ALIASES bridges them.  Without the
        # bridge, kilocode_glm would not appear in plan.identities.
        plan = gen.build_plan(REPO_ROOT)
        kilo_idents = [i for i in plan.identities if i.parent_tool == "kilo"]
        self.assertGreaterEqual(len(kilo_idents), 1, "kilocode_glm should bind via signature_aliases")
        agent_ids = {i.agent_id for i in kilo_idents}
        self.assertIn("kilocode_glm", agent_ids)

    def test_hand_written_launchers_excluded_by_default(self):
        # claude-pmoves.{sh,ps1,cmd} are hand-written, SDK-fixed.  The
        # generator MUST NOT emit them when --include-hand is absent.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        relpaths = {f.relpath for f in plan.files}
        for cli in ("claude-pmoves", "crush-pmoves"):
            for ext in (".sh", ".ps1", ".cmd"):
                self.assertNotIn(
                    f"deploy/provision/{cli}{ext}", relpaths,
                    f"hand-written {cli}{ext} must not be in the default plan",
                )

    def test_install_scripts_emitted_for_generator_managed(self):
        # kilo/codex/kimi/hermes/pmoves-mini get install scripts;
        # claude/crush do not (hand-written, preserved).
        # The CLI names in cli_tools.yaml already include `-pmoves` (the
        # wrapper name), so the install basename is `install-<cli>-command`.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        relpaths = {f.relpath for f in plan.files}
        for cli in ("kilo-pmoves", "codex-pmoves", "kimi-pmoves", "hermes-pmoves", "pmoves-mini"):
            self.assertIn(f"deploy/provision/install-{cli}-command.sh", relpaths)
            self.assertIn(f"deploy/provision/install-{cli}-command.ps1", relpaths)

    def test_pin_files_emitted_for_multi_node(self):
        # Claude: 4 per-node identities -> 4 pin files in `.sh/.ps1/.cmd`.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        relpaths = {f.relpath for f in plan.files}
        for i in plan.identities:
            if i.parent_tool == "claude":
                base = i.launcher_basename
                self.assertIn(f"deploy/provision/{base}.sh", relpaths)
                self.assertIn(f"deploy/provision/{base}.ps1", relpaths)
                self.assertIn(f"deploy/provision/{base}.cmd", relpaths)

    def test_every_emitted_bash_passes_bash_n(self):
        # bash -n: parse-only.  Any emitted `.sh` must parse cleanly.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        bash_files = [f for f in plan.files if f.relpath.endswith(".sh")]
        self.assertGreater(len(bash_files), 0, "no .sh files emitted")
        # On Windows git-bash cannot resolve `C:\...` absolute paths; it needs
        # a path relative to cwd.  Strategy: create a unique scratch dir under
        # the repo's tmp dir (always relative), cd in, run `bash -n <name>`,
        # then cd back.  Avoid `tempfile.TemporaryDirectory` here because its
        # cleanup races with the cwd change on Windows.
        scratch = REPO_ROOT / "pmoves" / "tools" / "tests" / ".bash_n_scratch"
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True, exist_ok=True)
        cwd_before = Path.cwd()
        try:
            os.chdir(scratch)
            for f in bash_files:
                name = Path(f.relpath).name
                (scratch / name).write_text(f.body, encoding="utf-8", newline="\n")
                r = subprocess.run(
                    ["bash", "-n", name],
                    capture_output=True, text=True,
                )
                self.assertEqual(
                    r.returncode, 0,
                    f"bash -n failed for {f.relpath}:\n{r.stderr}",
                )
        finally:
            os.chdir(cwd_before)
            shutil.rmtree(scratch, ignore_errors=True)

    def test_every_emitted_bash_contains_mavis_sdk_strip(self):
        # Every generator-managed bash LAUNCHER must contain the Mavis SDK env
        # strip section that sources pmoves/scripts/mavis_sdk_env.sh and calls
        # mavis_sdk_strip_env_for with the FAMILY name (not the launcher name).
        # Install scripts (install-*-command.sh) are excluded -- they only
        # install PATH/profile entries, they do NOT exec the CLI, so the strip
        # is not their concern.  Per-node pin launchers (e.g.
        # claude-pmoves-4090.sh, kilo-pmoves-kilocode_glm.sh) are excluded --
        # they set PMOVES_NODE_ID and exec the parent launcher (which DOES
        # carry the strip), so the pin launcher delegates the strip.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        bash_files = [
            f for f in plan.files
            if f.relpath.endswith(".sh")
            and not Path(f.relpath).name.startswith("install-")
            # 3-segment launchers are pin wrappers: <cli>-pmoves-<variant>.sh
            # (e.g. claude-pmoves-4090.sh, kilo-pmoves-kilocode_glm.sh,
            # crush-pmoves-glm52.sh).  2-segment launchers are the parent
            # launchers that actually exec the CLI.
            and len(Path(f.relpath).name.split("-")) == 2
        ]
        self.assertGreater(len(bash_files), 0, "no bash launchers emitted")
        for f in bash_files:
            self.assertIn(
                "mavis_sdk_strip_env_for",
                f.body,
                f"{f.relpath} missing mavis_sdk_strip_env_for call",
            )
            # Family name must be the argument (e.g. "kilo", not "kilo-pmoves").
            import re
            m = re.search(r'mavis_sdk_strip_env_for\s+"([^"]+)"', f.body)
            self.assertIsNotNone(m, f"{f.relpath} has unparseable strip call")
            cli_arg = m.group(1)
            self.assertFalse(
                cli_arg.endswith("-pmoves"),
                f"{f.relpath} strip call uses launcher name {cli_arg!r}; "
                f"needs registry family (e.g. 'kilo', not 'kilo-pmoves')",
            )

    def test_every_emitted_ps1_contains_mavis_sdk_strip(self):
        # Same regression pin for the PowerShell twin.
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        ps1_files = [
            f for f in plan.files
            if f.relpath.endswith(".ps1")
            and not Path(f.relpath).name.startswith("install-")
            and len(Path(f.relpath).name.split("-")) == 2
        ]
        self.assertGreater(len(ps1_files), 0, "no ps1 launchers emitted")
        for f in ps1_files:
            self.assertIn(
                "Strip-MavisSdkEnvFor",
                f.body,
                f"{f.relpath} missing Strip-MavisSdkEnvFor call",
            )

    def test_hand_written_launchers_have_strip_step(self):
        # The hand-written claude-pmoves.{sh,ps1} / crush-pmoves.{sh,ps1}
        # ALSO need the Mavis SDK env strip (per operator's "parity along
        # that surface" directive).  Only claude-pmoves is checked here
        # because crush-pmoves may be the next hand-edit target.
        for fname, marker in [
            ("claude-pmoves.sh", "mavis_sdk_strip_env_for"),
            ("claude-pmoves.ps1", "Strip-MavisSdkEnvFor"),
        ]:
            fpath = REPO_ROOT / "deploy" / "provision" / fname
            self.assertTrue(fpath.exists(), f"hand-written {fname} missing")
            content = fpath.read_text(encoding="utf-8")
            self.assertIn(
                marker, content,
                f"{fname} missing Mavis SDK env strip step",
            )

    def test_every_emitted_ps1_parses(self):
        # pwsh parser; skip when pwsh isn't installed (CI portability).
        if not _has_pwsh():
            self.skipTest("pwsh not on PATH")
        plan = gen.build_plan(REPO_ROOT, include_hand=False)
        ps_files = [f for f in plan.files if f.relpath.endswith(".ps1")]
        self.assertGreater(len(ps_files), 0, "no .ps1 files emitted")
        parser_ps = _HERE / "_psparse_inner.ps1"
        parser_ps.write_text(_PS1_PARSE_BODY, encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            for f in ps_files:
                target = tdp / Path(f.relpath).name
                target.write_text(f.body, encoding="utf-8", newline="\n")
                r = subprocess.run(
                    ["pwsh", "-NoProfile", "-File", str(parser_ps), str(target)],
                    capture_output=True, text=True,
                )
                self.assertEqual(
                    r.returncode, 0,
                    f"pwsh parse failed for {f.relpath}:\n{r.stdout}{r.stderr}",
                )


class TestByteStability(unittest.TestCase):
    """2 + 5. Output is byte-stable; manifest hash matches."""

    def test_re_run_produces_identical_plan(self):
        plan1 = gen.build_plan(REPO_ROOT)
        plan2 = gen.build_plan(REPO_ROOT)
        self.assertEqual(len(plan1.files), len(plan2.files))
        for a, b in zip(plan1.files, plan2.files):
            self.assertEqual(a.relpath, b.relpath)
            self.assertEqual(a.body, b.body, f"regen drift in {a.relpath}")
        # Manifest hashes match too.
        m1 = plan1.manifest_dict()
        m2 = plan2.manifest_dict()
        for fa, fb in zip(m1["files"], m2["files"]):
            self.assertEqual(fa["sha256"], fb["sha256"], f"hash drift in {fa['relpath']}")

    def test_manifest_matches_disk_after_regen(self):
        # Write the generator's output to a temp dir and compare bytes.
        plan = gen.build_plan(REPO_ROOT)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            emitted = gen.emit(plan, tdp, plan_root=REPO_ROOT)
            for f in plan.files:
                on_disk = tdp / f.relpath
                self.assertTrue(on_disk.exists(), f"{f.relpath} not emitted")
                self.assertEqual(_file_sha256(on_disk), _file_sha256(REPO_ROOT / f.relpath),
                                 f"hash mismatch after regen: {f.relpath}")
            # Manifest itself.
            m_disk = tdp / "deploy" / "provision" / "launchers.manifest.json"
            m_repo = REPO_ROOT / "deploy" / "provision" / "launchers.manifest.json"
            self.assertTrue(m_disk.exists(), "manifest not emitted")
            self.assertEqual(_file_sha256(m_disk), _file_sha256(m_repo),
                             "manifest hash drift")


class TestManifestShape(unittest.TestCase):
    """Manifest is well-formed JSON with the documented keys."""

    def test_manifest_keys(self):
        plan = gen.build_plan(REPO_ROOT)
        m = plan.manifest_dict()
        self.assertIn("generator_version", m)
        self.assertIn("tool_count", m)
        self.assertIn("identity_count", m)
        self.assertIn("files", m)
        for entry in m["files"]:
            self.assertIn("relpath", entry)
            self.assertIn("sha256", entry)
            self.assertIn("bytes", entry)
            self.assertIn("executable", entry)
            self.assertIn("managed_by", entry)
            self.assertIn(entry["managed_by"], ("generator", "hand"))


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _has_pwsh() -> bool:
    # Use `where` on Windows; fall back to direct invocation probe.
    try:
        r = subprocess.run(["where.exe", "pwsh"], capture_output=True)
        if r.returncode == 0:
            return True
    except FileNotFoundError:
        pass
    try:
        return subprocess.run(
            ["pwsh", "-NoProfile", "-Command", "exit 0"],
            capture_output=True,
        ).returncode == 0
    except FileNotFoundError:
        return False


_PS1_PARSE_BODY = r'''$errs = $null; $tok = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tok, [ref]$errs)
if ($errs -and $errs.Count -gt 0) {
    Write-Host "PARSE_ERRORS:"
    foreach ($x in $errs) { Write-Host ("  line {0}:col {1}: {2}" -f $x.Extent.StartLineNumber, $x.Extent.StartColumnNumber, $x.Message) }
    exit 1
}
Write-Host "OK"
'''


if __name__ == "__main__":
    unittest.main(verbosity=2)
