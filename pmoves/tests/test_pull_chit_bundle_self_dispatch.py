"""pull_chit_bundle.sh dispatches the producer run itself when no bundle is live.

Measured on the 4090 (2026-11-18): the newest successful sync-secrets-local run
was from 2026-11-03, its bundle long expired (1-day retention), so
`secrets-funnel-from-prod` died at `secrets-pull` and needed a manual
`gh workflow run`. Any node whose gh is authed may dispatch that run; the
producers stay the Linux runners. These tests drive the real script against a
fake `gh` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pull_chit_bundle.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")

# old run 100 has only expired bundles; a dispatch creates run 200 with a live one.
FAKE_GH = r"""#!/usr/bin/env bash
S="$FAKE_STATE"
echo "$*" >> "$S/calls"
case "$1 $2" in
  "run list")
    case "$*" in
      *"--status success"*) echo "${FAKE_SUCCESS_RUN:-100}" ;;
      *) [ -f "$S/dispatched" ] && echo 200; echo 100 ;;
    esac ;;
  "workflow run") [ "${FAKE_REFUSE_DISPATCH:-0}" = 1 ] && exit 1; touch "$S/dispatched" ;;
  "run watch") exit "${FAKE_WATCH_RC:-0}" ;;
  "run download")
    while [ $# -gt 0 ]; do [ "$1" = --dir ] && d="$2"; shift; done
    mkdir -p "$d"; echo '{"k": "v"}' > "$d/env.cgp.json" ;;
  "api repos/"*)
    case "$2" in
      */runs/200/*) echo chit-bundle-b850-200 ;;
      */runs/300/*) echo chit-bundle-b850-300 ;;
      *) echo "" ;;
    esac ;;
esac
"""


def _run(tmp_path: Path, **env_extra: str) -> tuple[subprocess.CompletedProcess, str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gh = fake_bin / "gh"
    gh.write_text(FAKE_GH, newline="\n")
    gh.chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()
    dest = tmp_path / "chit" / "env.cgp.json"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "FAKE_STATE": str(state),
        "CHIT_EXPORT_PATH": str(dest),
        "PMOVES_NODE": "4090",
        **env_extra,
    }
    for k in ("PMOVES_BUNDLE_PRODUCERS", "PMOVES_BUNDLE_PRODUCER", "PMOVES_BUNDLE_NO_DISPATCH"):
        if k not in env_extra:
            env.pop(k, None)
    proc = subprocess.run(
        [BASH, str(SCRIPT)], env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=120,
    )
    calls_file = state / "calls"
    calls = calls_file.read_text() if calls_file.exists() else ""
    return proc, calls


def test_an_expired_bundle_is_replaced_by_a_self_dispatched_run(tmp_path):
    proc, calls = _run(tmp_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "workflow run sync-secrets-local.yml" in calls
    assert "targets=spark,b850" in calls, "dispatch goes to the producers, not this node"
    assert "run watch 200" in calls
    assert "run download 200" in calls
    assert json.loads((tmp_path / "chit" / "env.cgp.json").read_text()) == {"k": "v"}


def test_a_live_bundle_is_pulled_without_dispatching(tmp_path):
    proc, calls = _run(tmp_path, FAKE_SUCCESS_RUN="300")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "workflow run" not in calls
    assert "run download 300" in calls


def test_the_opt_out_restores_the_manual_hint(tmp_path):
    proc, calls = _run(tmp_path, PMOVES_BUNDLE_NO_DISPATCH="1")

    assert proc.returncode == 1
    assert "workflow run" not in calls
    assert "gh workflow run sync-secrets-local.yml --ref main -f targets=spark,b850" in proc.stdout


def test_a_refused_dispatch_fails_closed_and_keeps_no_partial_bundle(tmp_path):
    proc, _ = _run(tmp_path, FAKE_REFUSE_DISPATCH="1")

    assert proc.returncode == 1
    assert "workflow/actions:write" in proc.stdout
    assert not (tmp_path / "chit" / "env.cgp.json").exists()


def test_a_failed_producer_run_is_reported_not_installed(tmp_path):
    proc, calls = _run(tmp_path, FAKE_WATCH_RC="1")

    assert proc.returncode == 1
    assert "did not succeed" in proc.stdout
    assert "run download" not in calls
    assert not (tmp_path / "chit" / "env.cgp.json").exists()
