"""The shared buildx builder's state volume must be bounded, never deleted.

Measured 2026-09-27: `buildx_buildkit_pmoves-shared0_state` was 139.5GB on
kvm4-1 and 146.4GB on kvm4-2 against a 30GB BuildKit GC cap, growing 5-9
GiB/day, while runner-maintenance.yml succeeded every night. Two defects:

* Between jobs the builder does not exist (setup-buildx removes it at post,
  keeping state), and every maintenance path pruned the DEFAULT builder or
  matched only the old per-run `buildx_buildkit_builder-*` names.
* During jobs the GC config never selected anything: an inline gcpolicy list
  REPLACES BuildKit's defaults (whose last rule is an `all = true` catch-all),
  and our single rule's keepDuration=168h + all=false made everything in daily
  use ineligible (moby/buildkit v0.32.2 cache/manager.go pruneOnce).

deploy/provision/pmoves-buildx-cap.sh is now the one implementation. These
tests pin (a) that every maintenance path and the action call it, (b) that the
cap has one source and the GC config has the catch-all, and (c) what the script
actually does, run against a stub `docker` from build_stub_env that only
records argv.
"""
from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy/provision/pmoves-buildx-cap.sh"
ACTION = REPO / ".github/actions/pmoves-buildx/action.yml"
RUNNER_MAINT = REPO / ".github/workflows/runner-maintenance.yml"
FLEET_WF = REPO / ".github/workflows/fleet-docker-cleanup.yml"
FLEET_SH = REPO / "deploy/provision/docker-fleet-cleanup.sh"
INFRA_MK = REPO / "pmoves/mk/infra.mk"

SHARED_VOLUME = "buildx_buildkit_pmoves-shared0_state"
DOCKER_GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
DOCKER_GUARD_MODULE = "pmoves_tests_destructive_docker_guard"  # conftest's name


def _docker_guard():
    if DOCKER_GUARD_MODULE in sys.modules:
        return sys.modules[DOCKER_GUARD_MODULE]
    import importlib.util
    spec = importlib.util.spec_from_file_location(DOCKER_GUARD_MODULE, DOCKER_GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[DOCKER_GUARD_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _code(path: Path) -> str:
    """Executable text only: comment lines describe the fix and must not satisfy it."""
    return "\n".join(l for l in path.read_text().splitlines() if not l.lstrip().startswith("#"))


# ── static: every maintenance path reaches the NAMED builder ──────────────────

@pytest.mark.parametrize("wf", [RUNNER_MAINT, FLEET_WF], ids=lambda p: p.name)
def test_maintenance_workflows_run_the_cap_script(wf: Path) -> None:
    code = _code(wf)
    assert "bash deploy/provision/pmoves-buildx-cap.sh" in code, (
        f"{wf.name} never bounds the shared builder; `docker builder prune` only "
        "reaches the DEFAULT builder"
    )
    # The script lives in the repo, so the job must check it out first.
    assert re.search(r"sparse-checkout:\s*deploy/provision", code)


def test_runner_maintenance_bounds_after_existing_cleanup() -> None:
    code = _code(RUNNER_MAINT)
    assert code.index("Aggressive Docker cleanup") < code.index("pmoves-buildx-cap.sh")


def test_systemd_cleanup_calls_script_before_sweep_and_spares_volume() -> None:
    code = _code(FLEET_SH)
    call = code.index("$CAP_SCRIPT")
    sweep = code.index("--filter dangling=true --filter name=buildx_buildkit_")
    assert call < sweep, "the shared builder must be bounded before the orphan sweep"
    assert f'SHARED_STATE_VOLUME="{SHARED_VOLUME}"' in code
    assert 'grep -vxF "$SHARED_STATE_VOLUME"' in code[sweep:], (
        "the dangling-volume sweep would delete the shared cache it just bounded"
    )


def test_install_target_ships_the_script_beside_the_cleanup() -> None:
    mk = INFRA_MK.read_text()
    assert "CLEANUP_CAP_SCRIPT := ../deploy/provision/pmoves-buildx-cap.sh" in mk
    assert "cp $(CLEANUP_CAP_SCRIPT) /usr/local/bin/pmoves-buildx-cap.sh" in mk


def test_systemd_cleanup_never_runs_all_inactive_over_the_shared_builder() -> None:
    # --all-inactive does not keep state: it would delete the shared cache if a
    # failed detach left pmoves-shared registered.
    code = _code(FLEET_SH)
    guard = code.index("docker buildx inspect pmoves-shared")
    reclaim = code.index("docker buildx rm --all-inactive")
    assert guard < reclaim
    between = code[guard:reclaim]
    assert "else" in between and "fi" not in between.split("else", 1)[0]


def test_runner_maintenance_comment_matches_the_prune() -> None:
    assert "never prunes with --all" not in RUNNER_MAINT.read_text()


def test_action_preflights_then_trims_the_named_builder() -> None:
    code = _code(ACTION)
    preflight = code.index("--preflight")
    setup = code.index("docker/setup-buildx-action@")
    trim = code.index("--attached")
    assert preflight < setup < trim, (
        "preflight must run before setup-buildx (which reuses a registered builder "
        "without re-applying the config); the trim must run while the builder exists"
    )
    assert '--builder "$BUILDER"' in code[trim - 200:trim + 200]
    assert "BUILDER: ${{ inputs.builder-name }}" in code


def _gc_rules(action_code: str) -> list[dict[str, str]]:
    toml = action_code[action_code.index("buildkitd-config-inline: |"):]
    rules: list[dict[str, str]] = []
    for line in toml.splitlines()[1:]:
        if line.strip() and not line.startswith("          "):
            break  # end of the block scalar
        s = line.strip()
        if s == "[[worker.oci.gcpolicy]]":
            rules.append({})
        elif rules and "=" in s:
            k, v = (x.strip() for x in s.split("=", 1))
            rules[-1][k] = v.strip('"')
    return rules


def test_gc_config_has_an_all_true_catch_all_without_keep_duration() -> None:
    rules = _gc_rules(_code(ACTION))
    assert rules, "no gcpolicy rules parsed"
    last = rules[-1]
    assert last.get("all") == "true", (
        "an inline gcpolicy list replaces BuildKit's defaults; without an all=true "
        "catch-all, internal/frontend/shared records are never GC'd"
    )
    assert "keepDuration" not in last, "keepDuration makes recently used records ineligible"
    assert last.get("maxUsedSpace") == "${{ steps.cap.outputs.value }}"
    assert last.get("minFreeSpace") == "${{ inputs.min-free-space }}"


def test_cap_has_one_source() -> None:
    code = _code(ACTION)
    # No literal default in the action: it is read from the script.
    block = code[code.index("  max-used-space:"):code.index("  reserved-space:")]
    assert re.search(r'default:\s*""', block)
    assert "pmoves-buildx-cap.sh\" --print-cap" in code
    assert all(r.get("maxUsedSpace") == "${{ steps.cap.outputs.value }}" for r in _gc_rules(code))
    assert "CAP: ${{ steps.cap.outputs.value }}" in code
    assert re.search(r'^DEFAULT_CAP="\d+GB"$', SCRIPT.read_text(), re.M)


@pytest.mark.parametrize("path", [SCRIPT, RUNNER_MAINT, FLEET_WF, FLEET_SH, ACTION], ids=lambda p: p.name)
def test_no_path_removes_the_shared_volume(path: Path) -> None:
    code = _code(path)
    assert not re.search(r"docker\s+volume\s+rm\s+[\"']?\$\{?VOLUME", code)
    assert not re.search(rf"docker\s+volume\s+rm\s+{re.escape(SHARED_VOLUME)}", code)
    assert not re.search(r"docker\s+volume\s+prune", code)
    if path == SCRIPT:
        for line in code.splitlines():
            if re.search(r"docker buildx rm\b", line):
                assert "--keep-state" in line and "--all-inactive" not in line, line


# ── behaviour: the script against a recording stub docker ─────────────────────

STUB_DOCKER = r"""
case "$1 $2" in
  "volume inspect")
    [ "${FAKE_VOLUME:-present}" = present ] && { echo '[{}]'; exit 0; } || exit 1 ;;
  "ps -q") [ "${FAKE_RUNNING:-0}" = 1 ] && echo abc123; exit 0 ;;
  "buildx du") echo "Total:	${FAKE_DU:-140GB}"; exit 0 ;;
  "buildx inspect")
    [ "$3" = "--bootstrap" ] && exit "${FAKE_BOOT_RC:-0}"
    [ "${FAKE_REGISTERED:-0}" = 1 ] || exit 1
    printf 'Name: %s\nGC Policy rule#0:\n\tAll:\tfalse\n' "$3"
    [ "${FAKE_ALL_TRUE:-0}" = 1 ] && printf 'GC Policy rule#1:\n\tAll:\ttrue\n'
    exit 0 ;;
  "buildx rm") exit "${FAKE_RM_RC:-0}" ;;
  "buildx prune")
    if [ "$3" = "--help" ]; then
      echo "      --keep-storage bytes"
      [ "${FAKE_NEW_BUILDX:-1}" = 1 ] && echo "      --max-used-space bytes"
      exit 0
    fi
    exit "${FAKE_PRUNE_RC:-0}" ;;
esac
[ "$1" = info ] && exit "${FAKE_INFO_RC:-0}"
exit 0
"""

# `pgrep -c` prints the count and exits 1 when it is zero.
STUB_PGREP = r"""
echo "${FAKE_WORKERS:-0}"
[ "${FAKE_WORKERS:-0}" -gt 0 ] || exit 1
exit 0
"""


def _run(tmp_path: Path, *args: str, pgrep: str | None = STUB_PGREP, **fake: str):
    """Run the script with stub docker (and stub pgrep, or NO pgrep at all)."""
    behaviours = {"docker": STUB_DOCKER}
    if pgrep is not None:
        behaviours["pgrep"] = pgrep
    stub = _docker_guard().build_stub_env(tmp_path / "bin", stub_make=True, behaviours=behaviours)
    env = dict(stub)
    if pgrep is None:
        # PATH = stubs + only the real tools the script needs, so pgrep is absent.
        tools = tmp_path / "tools"
        tools.mkdir(exist_ok=True)
        for name in ("bash", "flock", "grep", "tail"):
            real = shutil.which(name)
            assert real, name
            link = tools / name
            if not link.exists():
                link.symlink_to(real)
        env["PATH"] = os.pathsep.join([str(stub.stub_dir), str(tools)])
    env.pop("PMOVES_BUILDX_CAP", None)
    env.pop("GITHUB_ACTIONS", None)  # the suite itself may run inside Actions
    env["PMOVES_BUILDX_CAP_LOCK"] = str(tmp_path / "cap.lock")
    env.update(fake)
    proc = subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60,
    )
    calls = [row[1:] for row in stub.calls() if row[0] == "docker"]
    return proc.returncode, calls, proc.stdout + proc.stderr


def _mutations(calls):
    """Calls that change builder/volume state (probes like `--help` excluded)."""
    return [c for c in calls if c[:2] in (["buildx", "create"], ["buildx", "prune"], ["buildx", "rm"], ["volume", "rm"])
            and "--help" not in c]


def _assert_never_destroys_state(calls) -> None:
    for c in calls:
        assert c[:2] != ["volume", "rm"], c
        assert c[:2] != ["volume", "prune"], c
        if c[:2] == ["buildx", "rm"]:
            assert "--keep-state" in c and "--all-inactive" not in c, c


PRUNE_30 = ["buildx", "prune", "--builder", "pmoves-shared", "--all", "--max-used-space", "30GB", "--force"]
DETACH = ["buildx", "rm", "--keep-state", "pmoves-shared"]


def test_reattaches_prunes_all_to_cap_and_detaches_keeping_state(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path)
    assert rc == 0, out
    assert _mutations(calls) == [
        ["buildx", "create", "--name", "pmoves-shared", "--driver", "docker-container", "--node", "pmoves-shared0"],
        PRUNE_30,
        DETACH,
    ]
    assert ["volume", "inspect", SHARED_VOLUME] in calls
    assert "before:" in out and "after:" in out
    _assert_never_destroys_state(calls)


def test_old_buildx_falls_back_to_keep_storage(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, FAKE_NEW_BUILDX="0")
    assert rc == 0, out
    assert ["buildx", "prune", "--builder", "pmoves-shared", "--all", "--keep-storage", "30GB", "--force"] in calls


def test_reuses_a_registered_builder(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, FAKE_REGISTERED="1")
    assert rc == 0, out
    assert not any(c[:2] == ["buildx", "create"] for c in calls)
    assert DETACH in calls


def test_no_volume_means_nothing_to_do(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, FAKE_VOLUME="absent")
    assert rc == 0, out
    assert _mutations(calls) == []


@pytest.mark.parametrize("running", ["0", "1"])
def test_another_job_active_means_hands_off_whatever_the_container_state(tmp_path: Path, running: str) -> None:
    # Inside a maintenance job: our own Runner.Worker plus one more. With the
    # container NOT running the other job may be between its preflight and
    # setup-buildx, about to create the builder: re-attaching and detaching it
    # then would pull it out from under that job (the #3203 review race).
    rc, calls, out = _run(tmp_path, FAKE_RUNNING=running, FAKE_WORKERS="2", GITHUB_ACTIONS="true")
    assert rc == 0, out
    assert _mutations(calls) == [], "detaching a builder in use kills an in-flight build"
    assert "skipped" in out


@pytest.mark.parametrize("running", ["0", "1"])
def test_systemd_timer_skips_while_any_job_is_active(tmp_path: Path, running: str) -> None:
    rc, calls, out = _run(tmp_path, FAKE_RUNNING=running, FAKE_WORKERS="1")
    assert rc == 0, out
    assert _mutations(calls) == []


def test_running_leftover_builder_with_no_other_job_is_bounded(tmp_path: Path) -> None:
    # The kvm4-2 shape: a builder left running, only our own job on the host.
    rc, calls, out = _run(tmp_path, FAKE_RUNNING="1", FAKE_WORKERS="1", GITHUB_ACTIONS="true", FAKE_REGISTERED="1")
    assert rc == 0, out
    assert _mutations(calls) == [PRUNE_30, DETACH]


def test_failed_prune_still_detaches_and_reports(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, FAKE_PRUNE_RC="1")
    assert rc == 1, out
    assert _mutations(calls)[-1] == DETACH
    _assert_never_destroys_state(calls)


def test_docker_unavailable_is_could_not_measure(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, FAKE_INFO_RC="1")
    assert rc == 3, out
    assert _mutations(calls) == []


def test_attached_mode_prunes_only(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--attached", "--builder", "b1", "--cap", "50GB")
    assert rc == 0, out
    assert _mutations(calls) == [["buildx", "prune", "--builder", "b1", "--all", "--max-used-space", "50GB", "--force"]]


def test_env_overrides_cap_and_print_cap(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--print-cap", PMOVES_BUILDX_CAP="12GB")
    assert (rc, out.strip(), calls) == (0, "12GB", [])
    rc, _, out = _run(tmp_path, "--print-cap")
    assert (rc, out.strip()) == (0, "30GB")


# ── preflight: a pre-registered builder must not dodge the GC config ──────────

def test_preflight_nothing_registered_is_a_no_op(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", GITHUB_ACTIONS="true", FAKE_WORKERS="1")
    assert rc == 0, out
    assert _mutations(calls) == []


@pytest.mark.parametrize("running", ["0", "1"])
def test_preflight_detaches_a_leftover_builder_keeping_state(tmp_path: Path, running: str) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", FAKE_REGISTERED="1", FAKE_RUNNING=running,
                          GITHUB_ACTIONS="true", FAKE_WORKERS="1")
    assert rc == 0, out
    assert _mutations(calls) == [DETACH], "setup-buildx would reuse it without the GC config"
    _assert_never_destroys_state(calls)


def test_preflight_reuses_an_in_use_builder_that_has_the_catch_all(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", FAKE_REGISTERED="1", FAKE_RUNNING="1",
                          FAKE_ALL_TRUE="1", GITHUB_ACTIONS="true", FAKE_WORKERS="2")
    assert rc == 0, out
    assert _mutations(calls) == []


def test_preflight_fails_loudly_on_an_in_use_builder_without_the_catch_all(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", FAKE_REGISTERED="1", FAKE_RUNNING="1",
                          GITHUB_ACTIONS="true", FAKE_WORKERS="2")
    assert rc == 1, out
    assert _mutations(calls) == []
    assert "has no all=true catch-all" in out and "docker buildx rm --keep-state pmoves-shared" in out


def test_preflight_detach_failure_fails(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", FAKE_REGISTERED="1", FAKE_RM_RC="1")
    assert rc == 1, out


def test_preflight_leaves_a_stopped_builder_alone_while_another_job_is_active(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", FAKE_REGISTERED="1", FAKE_RUNNING="0",
                          FAKE_ALL_TRUE="1", GITHUB_ACTIONS="true", FAKE_WORKERS="2")
    assert rc == 0, out
    assert _mutations(calls) == []


# ── fail closed: pgrep missing, failing or unparseable means "another job" ────

PGREP_ERROR = "echo 'pgrep: bad option' >&2\nexit 2\n"
PGREP_GARBAGE = "echo 'not-a-number'\nexit 0\n"


@pytest.mark.parametrize("pgrep", [None, PGREP_ERROR, PGREP_GARBAGE], ids=["missing", "error", "garbage"])
def test_maintenance_fails_closed_when_pgrep_cannot_answer(tmp_path: Path, pgrep) -> None:
    rc, calls, out = _run(tmp_path, pgrep=pgrep, FAKE_RUNNING="0")
    assert rc == 0, out
    assert _mutations(calls) == [], "an unknown job count must never read as zero"
    assert "assuming another job is active" in out and "skipped" in out


@pytest.mark.parametrize("pgrep", [None, PGREP_ERROR, PGREP_GARBAGE], ids=["missing", "error", "garbage"])
def test_preflight_fails_closed_when_pgrep_cannot_answer(tmp_path: Path, pgrep) -> None:
    rc, calls, out = _run(tmp_path, "--preflight", pgrep=pgrep, FAKE_REGISTERED="1", GITHUB_ACTIONS="true")
    assert rc == 1, out
    assert _mutations(calls) == []


# ── host-wide lock: every mode, and never proceeds without it ─────────────────

@pytest.mark.parametrize("mode", [[], ["--attached"], ["--preflight"]], ids=["maintenance", "attached", "preflight"])
def test_every_mode_waits_for_the_host_lock(tmp_path: Path, mode: list[str]) -> None:
    lock = tmp_path / "cap.lock"
    with open(lock, "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)  # another invocation holds it
        rc, calls, out = _run(tmp_path, *mode, FAKE_REGISTERED="1", PMOVES_BUILDX_CAP_LOCK_WAIT="1")
    assert rc == 3, out
    assert calls == [], "nothing may touch docker without the host lock"
    assert "timed out waiting for host lock" in out


def test_lock_released_after_a_run(tmp_path: Path) -> None:
    rc, _, out = _run(tmp_path)
    assert rc == 0, out
    with open(tmp_path / "cap.lock") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if still held


def test_unopenable_lock_is_could_not_measure(tmp_path: Path) -> None:
    rc, calls, out = _run(tmp_path, PMOVES_BUILDX_CAP_LOCK=str(tmp_path / "no-such-dir" / "cap.lock"))
    assert rc == 3, out
    assert calls == []


def test_usage_error_is_exit_2(tmp_path: Path) -> None:
    rc, calls, _ = _run(tmp_path, "--bogus")
    assert (rc, calls) == (2, [])
