"""The formatting tests' import shims must not shadow an installed httpx.

test_formatting.py runs in the same pytest session as other services' tests
(python-tests.yml "Run all service tests"). A module-level
``sys.modules.setdefault("httpx", SimpleNamespace(...))`` replaced httpx for
the WHOLE session whenever nothing had imported the real one yet, so any later
import that reads ``httpx.<attr>`` at import time broke -- google-genai 3.x's
``HttpxClient = httpx.Client`` failed 43 flute-gateway tests on main
(2026-11-21). The shim is for minimal environments where httpx is absent.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

TEST_FILE = Path(__file__).with_name("test_formatting.py")


@pytest.mark.skipif(
    importlib.util.find_spec("httpx") is None,
    reason="httpx not installed: the shim is supposed to apply",
)
def test_formatting_shim_leaves_installed_httpx_alone():
    # Fresh interpreter, so the real httpx has NOT been imported yet -- the
    # exact state in which setdefault() used to install the stub.
    probe = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('tf', {str(TEST_FILE)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "import httpx\n"
        "assert hasattr(httpx, 'Client'), type(httpx).__name__\n"
    )
    pmoves_dir = TEST_FILE.parents[3]  # tests -> publisher-discord -> services -> pmoves
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(pmoves_dir), env.get("PYTHONPATH", "")) if p
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=pmoves_dir,
        env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]
