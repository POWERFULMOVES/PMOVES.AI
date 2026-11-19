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
from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pull_chit_bundle.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

# Fake gh answers the script's full query surface. State:
#   run 100 = old success (expired bundle), createdAt 2026-11-01
#   run 200 = the self-dispatched run (live bundle), createdAt 2026-11-19
#   run 300 = a live-bundle success used by FAKE_SUCCESS_RUN
# FAKE_FLAKY=1 makes the FIRST `run list` fail once (gh_retry must survive it);
# FAKE_WATCH_RC=1 makes `run watch` fail (PAT fallback must poll status instead).
# FAKE_SNAPSHOT_FAIL=1 makes every pre-dispatch floor query fail.
# FAKE_DISPATCH_URL=<id> makes `workflow run` print the created run's URL.
# FAKE_RACE=1 adds run 250: a CONCURRENT consumer's dispatch, created after
#   ours (12:00:09), already completed with conclusion=failure.
# FAKE_STUCK=1 leaves run 200 queued forever (deadline must still fire).
FAKE_GH = r"""#!/usr/bin/env bash
S="$FAKE_STATE"
echo "$*" >> "$S/calls"
case "$1 $2" in
  "run list")
    case "$*" in
      *"--status success"*)
        # gh applies --jq itself; the fake emulates the POST-jq value
        [ -n "${FAKE_SUCCESS_RUN:-}" ] && echo "${FAKE_SUCCESS_RUN}" || echo "" ;;
      *"--json createdAt"*)
        # correlation floor: newest run's server-side createdAt. FAKE_FLAKY
        # makes the FIRST floor query fail once -- gh_retry must survive it.
        # (post-jq string: quoted, matching real gh output)
        if [ "${FAKE_SNAPSHOT_FAIL:-0}" = 1 ]; then echo "gh: HTTP 502" >&2; exit 1; fi
        if [ "${FAKE_FLAKY:-0}" = 1 ] && [ ! -f "$S/flaked" ]; then
          touch "$S/flaked"; echo "gh: rate limited" >&2; exit 1
        fi
        if [ -f "$S/dispatched" ]; then echo '"2026-11-19T12:00:00Z"'
        else echo '"2026-11-01T00:00:00Z"'; fi ;;
      *"workflow_dispatch"*)
        # post-jq '.[].databaseId': one id per line
        # newest first, like gh
        if [ -f "$S/dispatched" ]; then
          [ "${FAKE_RACE:-0}" = 1 ] && echo 250
          echo 200
        fi ;;
      *)
        # post-jq join(",")
        if [ -f "$S/dispatched" ]; then echo "100,200"; else echo "100"; fi ;;
    esac ;;
  "workflow run")
    [ "${FAKE_REFUSE_DISPATCH:-0}" = 1 ] && exit 1
    touch "$S/dispatched"
    if [ -n "${FAKE_DISPATCH_URL:-}" ]; then
      echo "https://github.com/OWNER/REPO/actions/runs/${FAKE_DISPATCH_URL}"
    fi ;;
  "run view")
    id="$3"
    case "$*" in
      *"--json createdAt"*)
        case "$id" in
          200) echo '"2026-11-19T12:00:05Z"' ;;
          250) echo '"2026-11-19T12:00:09Z"' ;;
          *) echo '"2026-11-01T00:00:00Z"' ;;
        esac ;;
      *"--json status"*)
        case "$id" in
          200) [ "${FAKE_STUCK:-0}" = 1 ] && echo '"queued"' || echo '"completed"' ;;
          250) echo '"completed"' ;;
          *) echo '"in_progress"' ;;
        esac ;;
      *"--json conclusion"*)
        case "$id" in
          200) echo "\"${FAKE_CONCLUSION:-success}\"" ;;
          250) echo '"failure"' ;;
          *) echo 'null' ;;
        esac ;;
    esac ;;
  "run watch")
    # --exit-status: a failed run must make watch exit non-zero
    if [ "${FAKE_CONCLUSION:-success}" != "success" ]; then exit 1; fi
    [ "$3" = 250 ] && exit 1
    # stuck run: behave like a fine-grained PAT (watch unsupported) so the
    # status-polling deadline is what has to stop the wait
    [ "${FAKE_STUCK:-0}" = 1 ] && exit 1
    exit "${FAKE_WATCH_RC:-0}" ;;
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
    gh.write_text(FAKE_GH, encoding="utf-8", newline="\n")
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
        [resolve_bash(), str(SCRIPT)], env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=120,
    )
    calls_file = state / "calls"
    calls = calls_file.read_text(encoding="utf-8") if calls_file.exists() else ""
    return proc, calls


def test_an_expired_bundle_is_replaced_by_a_self_dispatched_run(tmp_path):
    proc, calls = _run(tmp_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "workflow run sync-secrets-local.yml" in calls
    assert "targets=spark,b850" in calls, "dispatch goes to the producers, not this node"
    assert "run watch 200" in calls
    assert "run download 200" in calls
    assert json.loads((tmp_path / "chit" / "env.cgp.json").read_text(encoding="utf-8")) == {"k": "v"}


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
    proc, calls = _run(tmp_path, FAKE_CONCLUSION="failure")

    assert proc.returncode == 1
    assert "did not succeed" in proc.stdout
    assert "run download" not in calls
    assert not (tmp_path / "chit" / "env.cgp.json").exists()


def test_a_failing_watch_falls_back_to_status_polling(tmp_path):
    """Fine-grained PAT: `gh run watch` (streaming) fails, plain polling works.

    The PR review flagged `run watch` as unusable with fine-grained PATs; the
    script must poll run view status/conclusion instead of declaring death.
    """
    proc, calls = _run(tmp_path, FAKE_WATCH_RC="1")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--json status" in calls, "fallback must poll run status"
    assert "run download 200" in calls
    assert json.loads((tmp_path / "chit" / "env.cgp.json").read_text(encoding="utf-8")) == {"k": "v"}


def test_a_transient_gh_failure_does_not_kill_the_dispatch(tmp_path):
    """`set -e` + command substitution: one rate-limited `gh run list` used to
    abort the whole script with zero output. gh_retry must ride it out."""
    proc, calls = _run(tmp_path, FAKE_FLAKY="1")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "workflow run sync-secrets-local.yml" in calls
    assert "run download 200" in calls


def test_the_dispatched_run_is_correlated_by_server_createdat(tmp_path):
    """Two consumers running secrets-pull concurrently must not adopt each
    other's runs by accident: the accepted run is a workflow_dispatch whose
    server-side createdAt postdates the pre-dispatch floor snapshot."""
    proc, calls = _run(tmp_path)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--event workflow_dispatch" in calls, "candidates filtered by event"
    assert "--json createdAt" in calls, "floor snapshot taken before dispatch"
    assert "run watch 200" in calls


def test_a_failed_snapshot_aborts_before_dispatching(tmp_path):
    """gh_retry used to return 0 after three failures (`$?` read after a false
    `if` is 0), so an empty floor was accepted and ANY recent
    workflow_dispatch run counted as ours. The snapshot must fail closed."""
    proc, calls = _run(tmp_path, FAKE_SNAPSHOT_FAIL="1")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Could not snapshot" in proc.stdout
    assert "HTTP 502" in proc.stderr, "gh's own error is replayed"
    assert "workflow run" not in calls, "nothing dispatched without a floor"
    assert not (tmp_path / "chit" / "env.cgp.json").exists()


def test_a_concurrent_foreign_dispatch_is_not_adopted(tmp_path):
    """Run 250 is another consumer's dispatch, created AFTER ours and failed.
    Fallback correlation takes the OLDEST post-floor candidate (200), so this
    pull neither watches nor reports the foreign failure."""
    proc, calls = _run(tmp_path, FAKE_RACE="1")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Adopted run 200" in proc.stdout
    assert "run watch 250" not in calls
    assert "run download 200" in calls


def test_the_run_url_from_the_dispatch_is_used_verbatim(tmp_path):
    """When gh returns the created run's URL, that id is exact: no list-based
    discovery happens at all, so a race cannot occur."""
    proc, calls = _run(tmp_path, FAKE_DISPATCH_URL="200", FAKE_RACE="1")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "id returned by the dispatch API" in proc.stdout
    assert "--event workflow_dispatch" not in calls
    assert "run download 200" in calls


def test_the_dispatch_timeout_holds_without_gh_run_watch(tmp_path):
    """A queued-forever run (offline producer) must fail after the deadline on
    the polling path too -- the path stock macOS (no `timeout`) and
    fine-grained PATs (no `gh run watch`) both take."""
    import time

    t0 = time.monotonic()
    proc, calls = _run(
        tmp_path, FAKE_STUCK="1",
        PMOVES_BUNDLE_DISPATCH_TIMEOUT="2", PMOVES_BUNDLE_POLL_INTERVAL="1",
    )
    elapsed = time.monotonic() - t0

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "status=queued" in proc.stdout
    assert "run download" not in calls
    assert elapsed < 60, f"deadline not enforced ({elapsed:.0f}s)"


def test_a_non_numeric_timeout_is_refused(tmp_path):
    proc, calls = _run(tmp_path, PMOVES_BUNDLE_DISPATCH_TIMEOUT="15m")

    assert proc.returncode == 1
    assert "whole seconds" in proc.stdout
    assert "workflow run" not in calls
