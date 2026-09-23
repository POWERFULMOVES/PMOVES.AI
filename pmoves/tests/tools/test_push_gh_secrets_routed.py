"""`push-gh-secrets.sh --routed`: each manifest route goes to its own repo/env.

`gh` is replaced by a stub first on PATH that records its argv and its stdin,
so nothing reaches GitHub. Every value below is synthetic. The properties under
test:

  * a routed name lands in the repo -- and the environment, or the repository
    scope -- its mapping pins; an unrouted name takes --repo/--env as today;
  * a value travels ONLY on gh's stdin: never in argv, never on stdout/stderr;
  * a malformed manifest stops the run before gh is ever called;
  * without --routed, the script behaves exactly as before.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "pmoves" / "tools" / "push-gh-secrets.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")

N8N = "POWERFULMOVES/PMOVES-N8N"

# /bin/sh, not the `which` result: a shebang needs a POSIX path, and on Windows
# `which` returns a backslashed one with a space in it (see
# test_pm_python_discovery.py).
_GH_STUB = """#!/bin/sh
# Record argv (one call per line) and stdin (the value) separately, so a test
# can prove the value arrived on stdin and nowhere else.
printf '%s\\n' "$*" >> "$GH_ARGV_LOG"
if [ "$1" = "secret" ]; then
  cat >> "$GH_STDIN_LOG"
  printf '\\n' >> "$GH_STDIN_LOG"
fi
exit 0
"""

VALUES = {
    "PLAIN": "synthval-plain-111",
    "N8N_API_KEY": "synthval-n8n-222",
    "REPO_ONLY": "synthval-repo-333",
}


@pytest.fixture()
def rig(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "gh"
    stub.write_text(_GH_STUB, encoding="utf-8", newline="\n")
    stub.chmod(0o755)

    # A KEY=VALUE file of synthetic values; the script's -f takes any such file.
    env_file = tmp_path / "synthetic_values.txt"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in VALUES.items()), encoding="utf-8")

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "secrets": [
                    {"id": "plain", "targets": [{"github_secret": "PLAIN"}]},
                    {
                        "id": "n8n",
                        "targets": [
                            {"github_secret": "N8N_API_KEY"},
                            {"github_secret": {"name": "N8N_API_KEY", "repo": N8N, "env": "Prod"}},
                        ],
                    },
                    {"id": "repo_only", "targets": [{"github_secret": {"name": "REPO_ONLY", "repo": N8N}}]},
                    {"id": "missing", "targets": [{"github_secret": "MISSING_VALUE"}]},
                ]
            }
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["PYTHON"] = sys.executable
    env["GH_ARGV_LOG"] = str(tmp_path / "gh_argv.log")
    env["GH_STDIN_LOG"] = str(tmp_path / "gh_stdin.log")
    for name in VALUES:
        env.pop(name, None)
    return {"tmp": tmp_path, "env": env, "env_file": env_file, "manifest": manifest}


def _run(rig, *args):
    return subprocess.run(
        [BASH, SCRIPT.as_posix(), "-f", rig["env_file"].as_posix(), *args],
        env=rig["env"],
        cwd=str(rig["tmp"]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def _log(rig, name):
    path = rig["tmp"] / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _assert_no_values(*streams):
    for stream in streams:
        for value in VALUES.values():
            assert value not in stream, f"a secret value was printed: {stream!r}"


def test_routed_dry_run_targets_each_route_and_prints_no_values(rig):
    proc = _run(
        rig, "--routed", "--dry-run", "--repo", "O/R", "--env", "Dev",
        "--manifest", rig["manifest"].as_posix(),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [
        "DRY-RUN: would set PLAIN in O/R (env Dev)",
        "DRY-RUN: would set N8N_API_KEY in O/R (env Dev)",
        f"DRY-RUN: would set N8N_API_KEY in {N8N} (env Prod)",
        f"DRY-RUN: would set REPO_ONLY in {N8N}",
    ]
    assert "MISSING_VALUE" in proc.stderr
    _assert_no_values(proc.stdout, proc.stderr)
    assert _log(rig, "gh_argv.log") == "", "dry-run must not call gh"


def test_routed_push_sends_each_key_to_its_own_repo_and_env(rig):
    proc = _run(rig, "--routed", "--repo", "O/R", "--manifest", rig["manifest"].as_posix())
    assert proc.returncode == 0, proc.stderr
    assert _log(rig, "gh_argv.log").splitlines() == [
        "secret set PLAIN --repo O/R --app actions",
        "secret set N8N_API_KEY --repo O/R --app actions",
        f"secret set N8N_API_KEY --repo {N8N} --app actions --env Prod",
        f"secret set REPO_ONLY --repo {N8N} --app actions",
    ]
    # Values reach gh on stdin, in route order, and nowhere else.
    assert _log(rig, "gh_stdin.log").splitlines() == [
        VALUES["PLAIN"], VALUES["N8N_API_KEY"], VALUES["N8N_API_KEY"], VALUES["REPO_ONLY"],
    ]
    _assert_no_values(proc.stdout, proc.stderr, _log(rig, "gh_argv.log"))


def test_routed_only_filters_by_name(rig):
    proc = _run(
        rig, "--routed", "--dry-run", "--repo", "O/R", "--only", "REPO_ONLY",
        "--manifest", rig["manifest"].as_posix(),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [f"DRY-RUN: would set REPO_ONLY in {N8N}"]


def test_a_malformed_manifest_stops_before_gh(rig):
    bad = rig["tmp"] / "bad.yaml"
    bad.write_text(
        yaml.safe_dump({"secrets": [{"id": "x", "targets": [{"github_secret": {"repo": N8N}}]}]}),
        encoding="utf-8",
    )
    proc = _run(rig, "--routed", "--repo", "O/R", "--manifest", bad.as_posix())
    assert proc.returncode != 0
    assert "name" in proc.stderr
    assert _log(rig, "gh_argv.log") == ""


def test_routed_refuses_ghcr_bootstrap(rig):
    proc = _run(rig, "--routed", "--ghcr-bootstrap", "--dry-run", "--repo", "O/R")
    assert proc.returncode != 0
    assert _log(rig, "gh_argv.log") == ""


def test_without_routed_the_env_file_is_pushed_as_before(rig):
    """Negative control: the default mode ignores routing entirely -- every key
    in the env file goes to --repo/--env, and the manifest's mappings are not
    consulted. Passes on origin/main by construction."""
    proc = _run(rig, "--dry-run", "--all", "--repo", "O/R", "--env", "Dev")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [
        "DRY-RUN: would set PLAIN in O/R (env Dev)",
        "DRY-RUN: would set N8N_API_KEY in O/R (env Dev)",
        "DRY-RUN: would set REPO_ONLY in O/R (env Dev)",
    ]
    _assert_no_values(proc.stdout, proc.stderr)
