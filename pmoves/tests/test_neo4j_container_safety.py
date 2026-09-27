"""Neo4j lifecycle scripts must never start a second Neo4j, or a volumeless one.

On Knuckles (2026-09) the live graph ran in an out-of-compose container named
`pmoves-neo4j` on the only Neo4j volume, `pmoves_neo4j-data`. Every lifecycle
path disagreed about its name, and each one's fallback was destructive:

  * backup-neo4j.sh looked for `pmoves-neo4j-1`, never found it, and ran
    `compose up -d neo4j`: a SECOND Neo4j on the volume the first one held.
  * `make neo4j-backup` looked it up with `$(DC) ps -q neo4j`, which cannot see
    an out-of-compose container, and fell through to `neo4j-local-up`: the same.
  * `make neo4j-restore` removed only the compose service, then ran a volume
    removal that silently failed on the held volume, then started a compose
    Neo4j beside the running one.
  * start-cipher-stack.sh force-removed `pmoves-neo4j` and started a replacement
    with NO volume, an empty graph in place of the live one.

The name now has ONE source (`services.neo4j.container_name`, read by
scripts/neo4j_container.py). These tests run the real scripts against a stub
`docker` that only records its argv; nothing touches a real container.

The stubs come from build_stub_env (pmoves/tests/_destructive_docker_guard.py),
the one helper that defines a stub dir, so the session guard's make-spawn
contract (marker + header-carrying recorders for docker, docker-compose and
supabase, first on PATH) holds by construction. `docker` gets a behaviour
snippet (canned `ps`/`inspect` answers) that runs AFTER its record line.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
SCRIPTS = PMOVES / "scripts"
HELPER = SCRIPTS / "neo4j_container.py"

sys.path.insert(0, str(SCRIPTS))
import neo4j_container  # noqa: E402

DOCKER_GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
DOCKER_GUARD_MODULE = "pmoves_tests_destructive_docker_guard"  # conftest's name


def _docker_guard():
    """The guard instance conftest registered, or a fresh load of the same file."""
    if DOCKER_GUARD_MODULE in sys.modules:
        return sys.modules[DOCKER_GUARD_MODULE]
    import importlib.util
    spec = importlib.util.spec_from_file_location(DOCKER_GUARD_MODULE, DOCKER_GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[DOCKER_GUARD_MODULE] = module
    spec.loader.exec_module(module)
    return module


FAKE_COMPOSE = "services:\n  neo4j:\n    image: neo4j:x\n    container_name: fake-neo4j\n"

# Runs after the recorder's own record line (build_stub_env behaviours).
STUB_DOCKER_BEHAVIOUR = r"""
if [ "$1" = "ps" ]; then
  for n in $FAKE_RUNNING; do echo "$n"; done
fi
daemon_down() {
  echo "failed to connect to the docker API at unix:///var/run/docker.sock; check if the path is correct and if the daemon is running: dial unix /var/run/docker.sock: connect: no such file or directory" >&2
  exit 1
}
if [ "$1" = "volume" ] && [ "$2" = "inspect" ]; then
  case "${FAKE_VOLUME:-absent}" in
    present) echo '[{"Name":"pmoves_neo4j-data"}]'; exit 0 ;;
    absent)  echo "Error response from daemon: get $3: no such volume" >&2; exit 1 ;;
    *)       daemon_down ;;
  esac
fi
if [ "$1" = "inspect" ] && [ "$2" = "--type" ] && [ "$3" = "container" ]; then
  case "${FAKE_CONTAINER:-absent}" in
    compose) echo "pmoves"; exit 0 ;;
    stray)   echo ""; exit 0 ;;
    stray-warn) echo ""; echo "WARNING: Plugin \"/usr/libexec/docker/cli-plugins/docker-x\" is not valid" >&2; exit 0 ;;
    absent)  echo "Error response from daemon: No such container: ${@: -1}" >&2; exit 1 ;;
    *)       daemon_down ;;
  esac
fi
if [ "$1" = "volume" ] && [ "$2" = "rm" ]; then
  [ "${FAKE_VOLUME_RM_FAILS:-0}" = "1" ] && exit 1 || exit 0
fi
"""


def _tree(tmp_path: Path, script: str):
    """A throwaway pmoves/ with the real script + helper and a fake compose,
    plus the stub env whose PATH starts with the recorders' dir."""
    root = tmp_path / "pmoves"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPTS / script, root / "scripts" / script)
    shutil.copy2(HELPER, root / "scripts" / "neo4j_container.py")
    (root / "docker-compose.yml").write_text(FAKE_COMPOSE)
    stub = _docker_guard().build_stub_env(
        tmp_path / "bin", stub_make=False, extra=("curl", "sleep"),
        behaviours={"docker": STUB_DOCKER_BEHAVIOUR},
    )
    return root, stub


def _docker_calls(stub) -> list[list[str]]:
    """docker AND docker-compose calls from the recorder log, in call order.

    `docker <args>` is returned as `<args>`; the v1 CLI `docker-compose <args>`
    as `compose <args>`, the shape `docker compose` also takes, so
    _neo4j_mutations sees both.
    """
    calls = []
    for row in stub.calls():
        if row[0] == "docker":
            calls.append(row[1:])
        elif row[0] == "docker-compose":
            calls.append(["compose", *row[1:]])
    return calls


def _run(tmp_path: Path, script: str, running: str) -> tuple[int, list[list[str]], str]:
    root, stub = _tree(tmp_path, script)
    env = dict(stub)
    env.update(FAKE_RUNNING=running)
    proc = subprocess.run(
        ["bash", str(root / "scripts" / script)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, _docker_calls(stub), proc.stdout + proc.stderr


def _neo4j_mutations(calls: list[list[str]]) -> list[list[str]]:
    """docker calls that would remove, (re)start or compose-up a Neo4j, or drop a volume."""
    bad = []
    for c in calls:
        if not c:
            continue
        verb = c[1:2] if c[0] == "container" else c[:1]   # `docker container rm` == `docker rm`
        touches_neo4j = any("neo4j" in a for a in c)
        if verb and verb[0] in ("rm", "run", "start", "restart", "create", "update", "stop", "kill") and touches_neo4j:
            bad.append(c)
        elif c[0] == "volume" and c[1:2] in (["rm"], ["prune"]):
            bad.append(c)
        elif c[0] == "system" and c[1:2] == ["prune"]:
            bad.append(c)
        elif c[0] == "compose" and any(v in c for v in ("up", "start", "restart", "run", "create", "stop", "kill", "down", "rm")):
            bad.append(c)
    return bad


# --- the single name source -------------------------------------------------

def test_the_helper_reads_container_name_from_compose(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(FAKE_COMPOSE)
    assert neo4j_container.container_name(f) == "fake-neo4j"


def test_no_container_name_is_could_not_measure_not_a_guess(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text("services:\n  neo4j:\n    image: neo4j:x\n")
    proc = subprocess.run([sys.executable, str(HELPER), str(f)], capture_output=True, text=True)
    assert proc.returncode == 3
    assert proc.stdout == ""


def test_the_real_compose_names_the_live_container():
    """The name the live Knuckles container already has, so Phase 1b keeps it."""
    assert neo4j_container.container_name() == "pmoves-neo4j"


# --- backup-neo4j.sh --------------------------------------------------------

def test_backup_refuses_instead_of_starting_a_second_neo4j(tmp_path):
    rc, calls, out = _run(tmp_path, "backup-neo4j.sh", running="")
    assert rc == 1, out
    assert _neo4j_mutations(calls) == [], calls
    assert "not running" in out


def test_backup_uses_the_compose_declared_name(tmp_path):
    rc, calls, out = _run(tmp_path, "backup-neo4j.sh", running="fake-neo4j")
    execs = [c for c in calls if c[:1] == ["exec"]]
    assert execs and all(c[1] == "fake-neo4j" for c in execs), calls
    assert _neo4j_mutations(calls) == [], calls


# --- start-cipher-stack.sh --------------------------------------------------

def test_start_cipher_stack_leaves_a_running_neo4j_alone(tmp_path):
    rc, calls, out = _run(tmp_path, "start-cipher-stack.sh", running="fake-neo4j")
    assert _neo4j_mutations(calls) == [], calls
    assert "leaving it untouched" in out


def test_start_cipher_stack_never_starts_a_volumeless_neo4j(tmp_path):
    rc, calls, out = _run(tmp_path, "start-cipher-stack.sh", running="")
    assert rc == 1, out
    assert _neo4j_mutations(calls) == [], calls
    assert "up-data-tier DATA_SERVICES=neo4j" in out


# --- Makefile targets ---------------------------------------------------------

def _recipe(target: str) -> str:
    text = (PMOVES / "Makefile").read_text()
    start = text.index(f"\n{target}:")
    end = text.index("\n\n", start + 1)
    return text[start:end]


def test_make_neo4j_backup_does_not_start_neo4j():
    r = _recipe("neo4j-backup")
    assert "neo4j-local-up" not in r
    assert "container_name=$$($(DC) ps -q neo4j" not in r, "the lookup that cannot see the live container"
    assert "scripts/neo4j_container.py" in r


def test_make_neo4j_restore_refuses_over_an_out_of_compose_container():
    r = _recipe("neo4j-restore")
    guard = r.index("not managed by compose")
    assert guard < r.index("neo4j-local-down"), "the refusal must precede the destructive steps"
    assert "container_name=$$($(DC) ps -q neo4j" not in r
    assert "scripts/neo4j_container.py" in r


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_make_n_neo4j_backup_renders_no_start(tmp_path):
    """Dry run of the real target, with the stub docker FIRST on PATH.

    A line containing $(MAKE) executes even under -n -- that is how the OLD
    recipe ran for real in this suite's failing-before control. The target has
    no nested make today, but if one comes back, every docker call it makes
    lands in the stub's log instead of the live daemon, and is asserted on.
    """
    _, stub = _tree(tmp_path, "backup-neo4j.sh")  # only for its stub env
    env = dict(stub)
    env.update(FAKE_RUNNING="")
    proc = subprocess.run(
        ["make", "-s", "-n", "-C", str(PMOVES), "neo4j-backup"],
        capture_output=True, text=True, timeout=120, env=env,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "neo4j-local-up" not in proc.stdout
    assert "up -d neo4j" not in proc.stdout
    calls = _docker_calls(stub)
    assert _neo4j_mutations(calls) == [], calls


def test_the_mutation_detector_sees_every_form():
    """NEGATIVE CONTROL for the detector every test here relies on."""
    for call in (["rm", "-f", "pmoves-neo4j"], ["container", "rm", "pmoves-neo4j"],
                 ["start", "pmoves-neo4j"], ["restart", "pmoves-neo4j"],
                 ["run", "--name", "pmoves-neo4j", "neo4j:x"], ["volume", "rm", "pmoves_neo4j-data"],
                 ["compose", "-f", "x.yml", "up", "-d", "neo4j"],
                 ["update", "--restart=no", "pmoves-neo4j"], ["stop", "pmoves-neo4j"], ["kill", "pmoves-neo4j"],
                 ["volume", "prune", "-f"], ["system", "prune", "-af"]):
        assert _neo4j_mutations([call]) == [call], call
    for call in (["ps", "--format", "{{.Names}}"], ["exec", "pmoves-neo4j", "true"],
                 ["inspect", "--type", "container", "pmoves-neo4j"], ["network", "create", "pmoves-net"]):
        assert _neo4j_mutations([call]) == [], call


def _restore_volume_block() -> str:
    """The recipe lines of neo4j-restore that clear pmoves_neo4j-data."""
    lines = _recipe("neo4j-restore").splitlines()
    i = next(n for n, ln in enumerate(lines) if "volume inspect pmoves_neo4j-data" in ln)
    j = next(n for n in range(i, len(lines)) if lines[n].strip() == "fi")
    return "\n".join(lines[i:j + 1])


def _restore_guard_block() -> str:
    """The recipe lines of neo4j-restore that refuse over an out-of-compose container."""
    lines = _recipe("neo4j-restore").splitlines()
    i = next(n for n, ln in enumerate(lines) if "scripts/neo4j_container.py" in ln)
    j = next(n for n in range(i, len(lines)) if lines[n].strip() == "fi")
    return "\n".join(lines[i:j + 1])


def _run_block(tmp_path: Path, block: str, **fake) -> tuple[int, list[list[str]], str]:
    """Run recipe lines, verbatim, in a temp Makefile with the REAL Makefile's shell."""
    root, stub = _tree(tmp_path, "backup-neo4j.sh")  # pmoves/ with the helper + a fake compose; stub env
    (root / "Makefile").write_text("SHELL := bash\nt:\n" + block + "\n")
    env = dict(stub)
    env.update(**fake)
    proc = subprocess.run(["make", "-s", "-C", str(root), "t", "PYTHON=python3"],
                          capture_output=True, text=True, timeout=60, env=env)
    calls = _docker_calls(stub)
    out = proc.stdout + proc.stderr
    # make collapses every non-zero recipe exit to 2, so 1 (refused) and 3
    # (could not measure) are only visible in its "Error N" line.
    m = re.search(r"\] Error (\d+)", proc.stderr)
    recipe_rc = int(m.group(1)) if m else proc.returncode
    return recipe_rc, calls, out


def test_the_real_makefile_runs_recipes_in_bash():
    """The temp Makefiles below set SHELL := bash to match this."""
    text = (PMOVES / "Makefile").read_text()
    assert "SHELL := bash" in text


def test_the_volume_block_sits_between_stop_and_start():
    r = _recipe("neo4j-restore")
    stop, vol, start = (r.index("neo4j-local-down"), r.index("volume inspect pmoves_neo4j-data"),
                        r.index("neo4j-local-up"))
    assert stop < vol < start


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("volume,rm_fails,want_rc,want_rm", [
    ("absent", "0", 0, False),   # explicit "no such volume": nothing to clear
    ("present", "0", 0, True),   # present and removable
    ("present", "1", 1, True),   # present but held by another Neo4j: fail CLOSED
    ("error", "0", 3, False),    # daemon unreachable: could-not-measure, never "absent"
])
def test_make_neo4j_restore_volume_step(tmp_path, volume, rm_fails, want_rc, want_rm):
    """The recipe's own volume block, extracted verbatim, against the stub.

    It used to swallow a failed removal (`2>/dev/null || true`) and go on to
    start and load over a volume another Neo4j still held. The first fix also
    read every inspect failure as "absent"; now only the daemon's explicit
    "no such volume" is.
    """
    rc, calls, out = _run_block(tmp_path, _restore_volume_block(),
                                FAKE_VOLUME=volume, FAKE_VOLUME_RM_FAILS=rm_fails)
    assert rc == want_rc, out
    removed = any(c[:2] == ["volume", "rm"] for c in calls)
    assert removed == want_rm, calls


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("container,want_rc", [
    ("absent", 0),    # explicit "No such container": nothing to protect
    ("compose", 0),   # compose-managed: the restore may proceed
    ("stray", 1),     # exists outside compose: refuse
    ("stray-warn", 1),  # same, with a CLI warning on stderr: still refuse (label is stdout only)
    ("error", 3),     # daemon unreachable: could-not-measure, never "absent"
])
def test_make_neo4j_restore_guard(tmp_path, container, want_rc):
    rc, calls, out = _run_block(tmp_path, _restore_guard_block(), FAKE_CONTAINER=container)
    assert rc == want_rc, out
    assert _neo4j_mutations(calls) == [], calls


def test_make_neo4j_restore_volume_removal_is_never_swallowed():
    block = _restore_volume_block()
    assert "|| true" not in block
    assert "exit 1" in block and "exit 3" in block
    assert "2>/dev/null" not in block and "2>&1 >/dev/null" in block


def test_the_stub_bin_meets_the_make_spawn_guard_contract(tmp_path):
    """The stub dir satisfies the guard's own is_stub_dir(), checked directly.

    The conftest guard refuses a make spawn unless the FIRST PATH entry is such
    a dir (marker + header-carrying docker, docker-compose and supabase
    recorders). Asserted here on the guard's predicate itself rather than on a
    restatement of it, so the two cannot drift.
    """
    guard = _docker_guard()
    _, stub = _tree(tmp_path, "backup-neo4j.sh")
    b = stub.stub_dir
    assert b.is_absolute()
    assert stub["PATH"].split(os.pathsep)[0] == str(b)
    assert guard.is_stub_dir(str(b)), sorted(p.name for p in b.iterdir())
    assert guard.check_command(["make", "-n", "neo4j-backup"], stub) is None
    # The recorder records, proven with a READ-ONLY argv: the session guard
    # (#3190) refuses spawning `docker-compose up` with no project, stub or
    # not, and must not be worked around.
    # A throwaway project is pinned, per #3190's static rule: every compose command
    # a test spawns carries -p, even to a recorder.
    project = f"pmoves-test-{uuid.uuid4().hex[:12]}"
    subprocess.run([str(b / "docker-compose"), "-p", project, "ps"], env=dict(stub), check=True)
    recorded = _docker_calls(stub)
    assert recorded == [["compose", "-p", project, "ps"]], recorded
    # ...and a mutating call, in exactly the shape _docker_calls returns, is flagged.
    assert _neo4j_mutations([["compose", "up", "-d", "neo4j"]]) != []
