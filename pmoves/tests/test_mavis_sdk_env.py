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


if __name__ == "__main__":
    unittest.main(verbosity=2)
