"""archon_release_channel.sh promote gate, driven against a fake `docker`.

No real container is started: DOCKER points at a stub that records its argv and
answers from environment knobs. Each case asserts on the REASON (exit code and
message) and on whether `docker tag ... :current` ran.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest
from pmoves.tools.bash_resolver import resolve_sh  # never System32's WSL stub

TOOL = Path(__file__).resolve().parents[2] / "tools" / "archon_release_channel.sh"
SHA = "b" * 40

FAKE_DOCKER = r"""#!/bin/sh
echo "$*" >> "$FAKE_LOG"
case "$1" in
  image)
    # image inspect [-f FMT] REF
    ref=$(eval echo \${$#})
    case "$ref" in *:current)
      [ -n "${FAKE_HAS_CURRENT:-}" ] || exit 1
      case "$*" in *pmoves.upstream.release*) echo "${FAKE_CURRENT_REL:-<no value>}";; *) echo sha256:prev;; esac
      exit 0;; esac
    [ -n "${FAKE_IMAGE_MISSING:-}" ] && exit 1
    case "$*" in
      *org.opencontainers.image.revision*) echo "${FAKE_REV}";;
      *pmoves.upstream.release*) echo "${FAKE_REL}";;
    esac
    exit 0;;
  run) echo cid123;;
  inspect) echo "${FAKE_RUNNING:-true}";;
  exec) printf '%s' "${FAKE_BODY}";;
  logs) echo "fake log line: boot trace";;
  rm|tag) :;;
esac
"""


@pytest.fixture
def env(tmp_path):
    fake = tmp_path / "docker"
    fake.write_text(FAKE_DOCKER)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "docker.log"
    log.write_text("")
    e = {k: v for k, v in os.environ.items() if k not in {"IMAGE", "FORK_SHA", "RELEASE_TAG", "RELEASE_VERSION"}}
    e.update(
        DOCKER=str(fake), FAKE_LOG=str(log),
        IMAGE="ghcr.io/powerfulmoves/pmoves-archon:0.11.1-pmoves.bbbbbbbb",
        FORK_SHA=SHA, RELEASE_TAG="v0.11.1", RELEASE_VERSION="0.11.1",
        FAKE_REV=SHA, FAKE_REL="v0.11.1",
        FAKE_BODY='{"status":"ok","version":"0.11.1"}',
        ARCHON_SMOKE_TIMEOUT="2", ARCHON_SMOKE_INTERVAL="0.1",
    )
    return e, log


def run(e, *args):
    args = args or ("promote",)
    return subprocess.run([resolve_sh(), str(TOOL), *args], env=e, capture_output=True, text=True, timeout=30)


def tagged(log):
    return any(line.startswith("tag ") and line.rstrip().endswith(":current") for line in log.read_text().splitlines())


def test_pass_promotes_and_never_pulls(env):
    e, log = env
    r = run(e)
    assert r.returncode == 0, r.stderr
    assert tagged(log)
    runs = [l for l in log.read_text().splitlines() if l.startswith("run ")]
    assert runs and "--pull never" in runs[0] and "--network none" in runs[0] and "--rm" not in runs[0]
    assert "rm -f cid123" in log.read_text()


@pytest.mark.parametrize("knob,val,needle", [
    ("FAKE_REV", "c" * 40, "revision label"),
    ("FAKE_REL", "v0.10.1", "release label"),
    ("FAKE_IMAGE_MISSING", "1", "not a local image"),
])
def test_refuses_image_not_matching_handed_values(env, knob, val, needle):
    e, log = env
    e[knob] = val
    r = run(e)
    assert r.returncode == 2
    assert needle in r.stderr
    assert "run " not in log.read_text() and not tagged(log)


def test_unhealthy_leaves_current_and_prints_logs(env):
    e, log = env
    e["FAKE_BODY"] = '{"status":"migration_required"}'
    r = run(e)
    assert r.returncode == 1
    assert "GATE FAILED (timeout" in r.stderr and "left unchanged" in r.stderr
    assert "fake log line" in r.stderr  # logs captured before removal
    assert not tagged(log)


def test_version_mismatch_fails(env):
    e, log = env
    e["FAKE_BODY"] = '{"status":"ok","version":"0.10.1"}'
    r = run(e)
    assert r.returncode == 1
    assert "expected '0.11.1'" in r.stderr
    assert not tagged(log)


def test_exited_container_fails_fast(env):
    e, log = env
    e["FAKE_RUNNING"] = "false"
    r = run(e)
    assert r.returncode == 1 and "container exited" in r.stderr
    assert not tagged(log)


@pytest.mark.parametrize("name,val", [
    ("IMAGE", "-oops:1"),
    ("IMAGE", "repo/../x:1"),
    ("IMAGE", "repo:1\nrm"),
    ("FORK_SHA", "b" * 39),
    ("RELEASE_TAG", "v1;id"),
])
def test_rejects_malformed_values(env, name, val):
    e, log = env
    e[name] = val
    r = run(e)
    assert r.returncode == 2 and "rejected" in r.stderr
    assert log.read_text() == ""


DIGEST = "ghcr.io/powerfulmoves/pmoves-archon@sha256:" + "d" * 64
CURRENT = "ghcr.io/powerfulmoves/pmoves-archon:current"


def test_promote_accepts_a_digest_pinned_image_with_label_checks_intact(env):
    e, log = env
    e["IMAGE"] = DIGEST
    r = run(e)
    assert r.returncode == 0, r.stderr
    assert f"tag {DIGEST} {CURRENT}" in log.read_text()
    e2 = dict(e, FAKE_REV="c" * 40)
    log.write_text("")
    r2 = run(e2)
    assert r2.returncode == 2 and "revision label" in r2.stderr


@pytest.mark.parametrize("has,rel,rc,needle", [
    ("1", "v0.11.1", 0, "is gated"),
    ("1", "", 3, "UNGATED build"),
    ("1", "<no value>", 3, "UNGATED build"),
    ("", "v0.11.1", 3, "not present locally"),
])
def test_verify_current_tells_gated_from_ungated(env, has, rel, rc, needle):
    e, _ = env
    e.update(FAKE_HAS_CURRENT=has, FAKE_CURRENT_REL=rel)
    r = run(e, "verify-current", CURRENT)
    assert r.returncode == rc, (r.stdout, r.stderr)
    assert needle in (r.stdout + r.stderr)


def test_verify_current_ignores_non_channel_tags(env):
    e, log = env
    r = run(e, "verify-current", "pmoves-archon:local-build")
    assert r.returncode == 0 and "not the :current channel tag" in r.stdout
    assert log.read_text() == ""


def test_bad_smoke_interval_is_rejected(env):
    e, log = env
    e["ARCHON_SMOKE_INTERVAL"] = "1;id"
    r = run(e)
    assert r.returncode == 2 and "ARCHON_SMOKE_INTERVAL" in r.stderr
    assert log.read_text() == ""
