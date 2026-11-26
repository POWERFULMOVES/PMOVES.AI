"""Thin Python wrapper for pmoves/tests/test_mavis_sdk_env.sh.

The actual test logic is a bash script (the helper is bash; bash subprocess
tests have quoting issues on this Windows host that a script file avoids).
This wrapper just invokes the bash runner via subprocess.run with the
runner script as a positional argument, parses exit code, and re-raises
any non-zero exit as a unittest failure.

When a scenario fails, the runner prints FAIL details to stderr. We forward
that to the unittest output so the operator can read the per-assertion
mismatch.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

try:
    from pmoves.tools.bash_resolver import find_bash  # never System32's WSL stub
except ImportError:  # run standalone: put the repo root on sys.path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from pmoves.tools.bash_resolver import find_bash


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "pmoves" / "tests" / "test_mavis_sdk_env.sh"
_HELPER = _REPO_ROOT / "pmoves" / "scripts" / "mavis_sdk_env.sh"


@unittest.skipUnless(_RUNNER.exists(), "bash test runner missing")
@unittest.skipUnless(_HELPER.exists(), "bash helper missing")
@unittest.skipUnless(
    find_bash(), "no usable bash (System32's WSL stub does not count)"
)
class MavisSdkEnvTest(unittest.TestCase):
    """Run the bash test runner once. Forward its exit code + stderr."""

    def test_bash_runner_all_pass(self):
        bash = find_bash()
        # Forward slashes, drive letter kept: Git Bash (what find_bash()
        # returns on Windows) opens C:/... directly. The old /mnt/c/ rewrite
        # was the WSL mount -- it only worked because "bash" was silently
        # resolving to System32's WSL stub.
        runner_arg = str(_RUNNER).replace("\\", "/")
        result = subprocess.run(
            [bash, runner_arg],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
        )
        # Forward the runner's stdout (PASS/FAIL summary + WARN lines from
        # the strip helper) so the operator sees what ran.
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, end="")
        self.assertEqual(
            result.returncode,
            0,
            f"bash test runner exited {result.returncode}; see stderr above for per-scenario FAIL details",
        )


_PS1_HELPER = _REPO_ROOT / "pmoves" / "scripts" / "mavis_sdk_env.ps1"
_PS1_RUNNER = _REPO_ROOT / "pmoves" / "tests" / "test_mavis_sdk_env_audit.ps1"
_AUDIT_KEYS = {
    "ts", "host", "pid", "cli", "stripped_count", "stripped_names", "all_consumed",
}


def _powershells() -> list[str]:
    """Every PowerShell on PATH: Windows PowerShell 5.1 and/or pwsh 7.

    Both are exercised when present. The launchers invoke `powershell` (5.1)
    on the nodes, and 5.1 is where `Get-Date -AsUTC` does not exist, so a
    pwsh-only run would pass while every real launch failed.
    """
    found = []
    for exe in ("powershell", "pwsh"):
        path = shutil.which(exe) or shutil.which(exe + ".exe")
        if path:
            found.append(path)
    return found


@unittest.skipUnless(_PS1_HELPER.exists(), "PowerShell helper missing")
@unittest.skipUnless(_PS1_RUNNER.exists(), "PowerShell test runner missing")
@unittest.skipUnless(_powershells(), "no PowerShell on PATH")
class MavisSdkEnvPs1AuditTest(unittest.TestCase):
    """The PowerShell twin must WRITE an audit line, not merely mention one.

    The token ratchet in test_pmoves_launcher_generator.py checks that both
    helpers name the canonical path and keys. It passed for two months while
    the ps1 block had never produced a line: the `-f` template's outer JSON
    braces were not doubled (format error under every PowerShell), and
    `Get-Date -AsUTC` is PowerShell 7-only. A best-effort catch turned both
    into a warning. This test asserts the artifact instead.
    """

    def test_ps1_audit_append_writes_json_line(self):
        import json
        import os
        import tempfile

        for exe in _powershells():
            with self.subTest(powershell=exe), tempfile.TemporaryDirectory() as tmp:
                # Point the override INTO a directory that does not exist yet:
                # the helper must create the parent of the effective path.
                log_path = Path(tmp) / "nested" / "deeper" / "audit.log"
                env = dict(os.environ)
                env["PMOVES_MAVIS_SDK_LOG_PATH"] = str(log_path)
                env.pop("PMOVES_MAVIS_SDK_LOG_DIR", None)
                result = subprocess.run(
                    [exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-File", str(_PS1_RUNNER)],
                    capture_output=True,
                    text=True,
                    cwd=str(_REPO_ROOT),
                    env=env,
                    timeout=120,
                )
                detail = (
                    f"{exe} exited {result.returncode}\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                )
                self.assertEqual(result.returncode, 0, detail)
                self.assertTrue(log_path.exists(), detail)
                last = log_path.read_text(encoding="utf-8-sig").splitlines()[-1]
                record = json.loads(last)
                self.assertEqual(set(record), _AUDIT_KEYS, detail)
                self.assertEqual(record["cli"], "twin-audit-test", detail)
                self.assertIn("ANTHROPIC_MODEL", record["stripped_names"], detail)
                self.assertIsInstance(record["stripped_count"], int, detail)
                self.assertIsInstance(record["all_consumed"], bool, detail)
                self.assertRegex(record["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
