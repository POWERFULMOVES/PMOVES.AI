"""ollama_host_channel.sh gates: each refusal happens before the host is touched.

Nothing here needs Docker, network or root, and nothing reaches the real host:
`ollama`, `curl`, `systemctl` and `docker` resolve to recorder stubs on a PATH
built per test, and every refusal under test fires before the installer would
run. The canary's A/B itself (Docker + GPU) is exercised by hand on a node; its
PASS/REFUSE report is what install reads, and that is faked here.

The tool is `#!/bin/sh` and production runs it with bare `sh` (pmoves/Makefile),
so the tests run it under resolve_sh() -- dash on Debian/Ubuntu, not bash.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import resolve_sh  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "ollama_host_channel.sh"

# Knobs the tool reads; scrubbed so the developer's own shell cannot steer a test.
_TOOL_ENV = (
    "OLLAMA_CHANNEL_STATE", "OLLAMA_CHANNEL_VERSION", "OLLAMA_CHANNEL_MODELS", "OLLAMA_CANARY_MODEL",
    "OLLAMA_CANARY_PORT", "OLLAMA_CANARY_RUNS", "OLLAMA_CANARY_LAYER_MARGIN", "OLLAMA_CANARY_DIR",
    "OLLAMA_CANARY_MAX_AGE_HOURS", "OLLAMA_ACCEPT_STORE_MIGRATION", "OLLAMA_UPSTREAM_REPO",
    "XDG_STATE_HOME", "SUDO_USER", "DOCKER",
)

# One recorder for every external command the tool may call. Answers come from
# FAKE_* variables; anything unanticipated fails, so a missed stub cannot fall
# through to the real host.
_STUB = r"""#!/bin/sh
printf '%s %s\n' "$(basename "$0")" "$*" >> "$FAKE_LOG"
case "$(basename "$0")" in
  ollama) [ -n "${FAKE_OLLAMA_VERSION+x}" ] && { printf '%s\n' "$FAKE_OLLAMA_VERSION"; exit 0; }; exit 1 ;;
  curl)
    case "$*" in *127.0.0.1:11434/api/tags*)
      [ -n "${FAKE_TAGS:-}" ] && { printf '%s' "$FAKE_TAGS"; exit 0; }; exit 7 ;; esac
    exit 22 ;;
  systemctl)
    case "$*" in *EnvironmentFiles*) printf '%s\n' "${FAKE_ENVFILES:-}"; exit 0 ;;
                 *show*Environment*) printf '%s\n' "${FAKE_ENV:-}"; exit 0 ;; esac
    exit 1 ;;
  docker) exit 0 ;;
esac
exit 1
"""


def _stub_env(tmp_path: Path, **extra: str) -> dict:
    bindir = tmp_path / "stub-bin"
    if not bindir.exists():
        bindir.mkdir()
        for name in ("ollama", "curl", "systemctl", "docker"):
            stub = bindir / name
            stub.write_text(_STUB)
            stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in _TOOL_ENV}
    env.update({"PATH": f"{bindir}:{os.environ['PATH']}", "FAKE_LOG": str(tmp_path / "calls.log"),
                "DOCKER": str(bindir / "docker"), "OLLAMA_CHANNEL_STATE": str(tmp_path / "state")})
    env.update(extra)
    return env


def _calls(tmp_path: Path) -> str:
    log = tmp_path / "calls.log"
    return log.read_text() if log.exists() else ""


def _run(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([resolve_sh(), str(TOOL), *args], env=env,
                          capture_output=True, text=True, timeout=60)


def _install(state: Path, version: str, **extra: str) -> subprocess.CompletedProcess:
    env = _stub_env(state, OLLAMA_CHANNEL_STATE=str(state), OLLAMA_CHANNEL_VERSION=version, **extra)
    return _run(env, "install")


def _report(state: Path, version: str, **fields) -> Path:
    data = {"verdict": "PASS", "baseline": "0.30.0", "candidate": version,
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    data.update(fields)
    state.mkdir(parents=True, exist_ok=True)
    p = state / f"canary-{version}.json"
    p.write_text(json.dumps(data))
    return p


@pytest.mark.parametrize("bad", ["0.40.5;id", "0.40.5 && id", "$(id)", "-v", "../0.40.5", "latest"])
def test_install_rejects_anything_that_is_not_a_version(tmp_path, bad):
    r = _install(tmp_path, bad)
    assert r.returncode == 2 and "rejected" in r.stderr
    assert "uid=" not in r.stdout + r.stderr


def test_install_refuses_without_a_canary(tmp_path):
    r = _install(tmp_path, "0.41.0")
    assert r.returncode == 3 and "no canary for 0.41.0" in r.stderr


def test_install_refuses_a_refused_canary(tmp_path):
    (tmp_path / "canary-0.40.5.json").write_text(json.dumps({"verdict": "REFUSE"}))
    r = _install(tmp_path, "v0.40.5")  # leading v is accepted and stripped
    assert r.returncode == 3 and "did not PASS" in r.stderr


# --- a PASS is bound to the host it measured -------------------------------

def _bound_install(tmp_path, **report_fields):
    """A PASS for 0.40.5 measured on store S against host 0.30.0, then install."""
    store = tmp_path / "store"; store.mkdir(exist_ok=True)
    state = tmp_path / "state"
    _report(state, "0.40.5", **{"store": str(store), **report_fields})
    env = _stub_env(tmp_path, OLLAMA_CHANNEL_VERSION="0.40.5", OLLAMA_CHANNEL_MODELS=str(store),
                    FAKE_OLLAMA_VERSION="ollama version is 0.30.0",
                    FAKE_TAGS=json.dumps({"models": [{}, {}, {}]}))
    return _run(env, "install")


def test_install_refuses_a_pass_measured_against_another_host_version(tmp_path):
    r = _bound_install(tmp_path, baseline="0.29.0")
    assert r.returncode == 3, r.stderr
    assert "measured against host 0.29.0, but the host is now 0.30.0" in r.stderr


def test_install_refuses_a_pass_from_another_store(tmp_path):
    r = _bound_install(tmp_path, store=str(tmp_path / "elsewhere"))
    assert r.returncode == 3 and "but the host store is now" in r.stderr


def test_install_refuses_a_stale_pass(tmp_path):
    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    r = _bound_install(tmp_path, at=old.isoformat())
    assert r.returncode == 3 and "h old (limit OLLAMA_CANARY_MAX_AGE_HOURS=72)" in r.stderr


def test_install_refuses_a_pass_without_a_timestamp(tmp_path):
    r = _bound_install(tmp_path, at=None)
    assert r.returncode == 3 and "no readable timestamp" in r.stderr


def test_install_refuses_when_host_version_is_unreadable(tmp_path):
    # Report baseline 0.30.0 vs a host whose --version prints no version: "none".
    store = tmp_path / "store"; store.mkdir()
    _report(tmp_path / "state", "0.40.5", store=str(store))
    env = _stub_env(tmp_path, OLLAMA_CHANNEL_VERSION="0.40.5", OLLAMA_CHANNEL_MODELS=str(store),
                    FAKE_OLLAMA_VERSION="Warning: could not connect to a running Ollama instance")
    r = _run(env, "install")
    assert r.returncode == 3 and "the host is now none" in r.stderr


# --- the model count must be readable BEFORE the installer -----------------

def test_install_refuses_before_the_installer_when_model_count_is_unreadable(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    _report(tmp_path / "state", "0.40.5", store=str(store))
    env = _stub_env(tmp_path, OLLAMA_CHANNEL_VERSION="0.40.5", OLLAMA_CHANNEL_MODELS=str(store),
                    FAKE_OLLAMA_VERSION="ollama version is 0.30.0")  # no FAKE_TAGS: curl fails
    r = _run(env, "install")
    assert r.returncode == 3 and "cannot read the model count" in r.stderr
    calls = _calls(tmp_path)
    assert "install.sh" not in calls and "restart" not in calls
    assert not list((tmp_path / "state").glob("*-preinstall.tar.gz"))


@pytest.mark.skipif(getattr(os, "geteuid", lambda: -1)() == 0, reason="the root check is what is under test")
def test_install_needs_root_even_after_a_bound_pass(tmp_path):
    r = _bound_install(tmp_path)
    assert r.returncode == 3 and "needs root" in r.stderr
    assert "install.sh" not in _calls(tmp_path)


def test_make_passes_version_through_the_environment_not_the_recipe():
    text = (REPO_ROOT / "pmoves" / "Makefile").read_text(encoding="utf-8")
    for target in ("ollama-host-canary", "ollama-host-install"):
        assert f"{target}: export OLLAMA_CHANNEL_VERSION = $(VERSION)" in text
    assert "ollama_host_channel.sh canary $(VERSION)" not in text
    assert "ollama_host_channel.sh install $(VERSION)" not in text


# --- knobs ------------------------------------------------------------------

@pytest.mark.parametrize("runs", ["10", "99"])
def test_two_digit_canary_runs_are_accepted(tmp_path, runs):
    r = _install(tmp_path, "0.41.0", OLLAMA_CANARY_RUNS=runs)
    assert r.returncode == 3 and "no canary for 0.41.0" in r.stderr  # got past validation


@pytest.mark.parametrize("runs", ["0", "100", "01"])
def test_canary_runs_out_of_range_say_so(tmp_path, runs):
    r = _install(tmp_path, "0.41.0", OLLAMA_CANARY_RUNS=runs)
    assert r.returncode == 2 and "OLLAMA_CANARY_RUNS rejected (must be 1-99)" in r.stderr


def test_xdg_state_home_is_honoured(tmp_path):
    env = _stub_env(tmp_path, OLLAMA_CHANNEL_VERSION="0.41.0", XDG_STATE_HOME=str(tmp_path / "xdg"))
    env.pop("OLLAMA_CHANNEL_STATE")
    r = _run(env, "install")
    assert r.returncode == 3 and f"in {tmp_path / 'xdg'}/pmoves/ollama-channel" in r.stderr


# --- canary preflight (never reaches a container) ----------------------------

def test_canary_refuses_an_unparsable_host_version(tmp_path):
    env = _stub_env(tmp_path, FAKE_OLLAMA_VERSION="ollama version is unknown")
    r = _run(env, "canary", "0.40.5")
    assert r.returncode == 2 and "no host ollama version detected" in r.stderr
    assert "docker" not in _calls(tmp_path)


def _canary_store(tmp_path, *, missing_blob=False, layer_size=10):
    store = tmp_path / "store"
    man = store / "manifests" / "registry.ollama.ai" / "library" / "tiny" / "latest"
    man.parent.mkdir(parents=True)
    (store / "blobs").mkdir()
    man.write_text(json.dumps({
        "config": {"digest": "sha256:aaa", "size": 3},
        "layers": [{"digest": "sha256:bbb", "size": layer_size}, {"digest": "sha256:ccc", "size": 3}]}))
    (store / "blobs" / "sha256-aaa").write_text("cfg")
    (store / "blobs" / "sha256-bbb").write_text("x" * 10)
    if not missing_blob:
        (store / "blobs" / "sha256-ccc").write_text("ccc")
    scratch_root = tmp_path / "scratch"; scratch_root.mkdir()
    return _stub_env(tmp_path, OLLAMA_CHANNEL_MODELS=str(store), OLLAMA_CANARY_MODEL="tiny",
                     OLLAMA_CANARY_DIR=str(scratch_root), FAKE_OLLAMA_VERSION="ollama version is 0.30.0")


def test_canary_cleans_up_a_copy_that_dies_half_way(tmp_path):
    env = _canary_store(tmp_path, missing_blob=True)
    r = _run(env, "canary", "0.40.5")
    assert r.returncode != 0
    assert list((tmp_path / "scratch").iterdir()) == []  # trap was armed before the copy
    assert "run -d" not in _calls(tmp_path)               # never reached a container


def test_canary_refuses_a_copy_that_would_not_fit(tmp_path):
    env = _canary_store(tmp_path, layer_size=10**18)
    r = _run(env, "canary", "0.40.5")
    assert r.returncode == 2 and "not enough free space" in r.stderr
    assert list((tmp_path / "scratch").iterdir()) == []
    assert "run -d" not in _calls(tmp_path)


def test_missing_store_is_refused_not_guessed(tmp_path):
    env = _stub_env(tmp_path, FAKE_OLLAMA_VERSION="ollama version is 0.30.0",
                    FAKE_ENV=f"OLLAMA_MODELS={tmp_path / 'gone'}")
    r = _run(env, "canary", "0.40.5")
    assert r.returncode != 0 and "model store not found" in r.stderr


# --- store detection + rollback (print-only) --------------------------------

def _rollback(tmp_path, environment: str, env_files: str = ""):
    return _run(_stub_env(tmp_path, FAKE_ENV=environment, FAKE_ENVFILES=env_files), "rollback")


def test_store_found_when_ollama_models_is_the_first_environment_entry(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    r = _rollback(tmp_path, f"OLLAMA_MODELS={store} OLLAMA_HOST=0.0.0.0")
    assert r.returncode == 0 and f'-C "{store}" ' in r.stdout


def test_store_found_in_an_environment_file(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    envfile = tmp_path / "ollama-service-environment"
    envfile.write_text(f'export OLLAMA_MODELS="{store}"\n')
    r = _rollback(tmp_path, "OLLAMA_HOST=0.0.0.0", f"{envfile} (ignore_errors=no)")
    assert r.returncode == 0 and f'-C "{store}" ' in r.stdout


def test_rollback_still_prints_every_step_when_the_store_is_undetectable(tmp_path):
    r = _rollback(tmp_path, f"OLLAMA_MODELS={tmp_path / 'gone'}")
    assert r.returncode == 0, r.stderr
    assert "store not detected" in r.stdout
    assert '-C "/usr/share/ollama/.ollama/models" ' in r.stdout
    assert "unset-environment OLLAMA_NOPRUNE" in r.stdout  # the last step printed


def test_rollback_removes_everything_a_migration_creates(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    r = _rollback(tmp_path, f"OLLAMA_MODELS={store}")
    assert f'"{store}/manifests-v2" "{store}/metadata" -delete' in r.stdout


def test_rollback_noprune_is_first_start_only(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    r = _rollback(tmp_path, f"OLLAMA_MODELS={store}")
    line = next(ln for ln in r.stdout.splitlines() if "set-environment OLLAMA_NOPRUNE=1" in ln)
    assert line.rstrip().endswith("sudo systemctl unset-environment OLLAMA_NOPRUNE")
