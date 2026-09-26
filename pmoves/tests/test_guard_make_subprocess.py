"""The destructive-docker guard refuses unstubbed make/gmake spawns.

Why: a test that spawns make reaches the daemon through the RECIPES, which the
guard cannot see, and GNU make executes every recipe line containing $(MAKE)
even under -n. pmoves/docker-compose.yml's `name: pmoves` then points any
compose call such a line reaches at the LIVE project.

No test here spawns a real make:

* ``check_command`` cases are a pure function over argv + env.
* The wrapper tests replace ``subprocess.Popen.__init__`` and ``os.system``
  with a recorder that RAISES instead of spawning, then install a fresh guard
  instance on top (the same mechanism as test_destructive_docker_guard.py).
* The one end-to-end test spawns the fixture's own ``make`` RECORDER (a
  3-line /bin/sh script in tmp), never /usr/bin/make.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import uuid
from pathlib import Path
from types import ModuleType

import pytest

GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
NOT_A_STUB_PATH = os.pathsep.join(["/usr/local/bin", "/usr/bin", "/bin"])


def _fresh_guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_guard_make_under_test_{uuid.uuid4().hex[:8]}", GUARD_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _fresh_guard()


@pytest.fixture(autouse=True)
def _deterministic_path(monkeypatch):
    # The unstubbed cases must not depend on whatever PATH the runner has.
    monkeypatch.setenv("PATH", NOT_A_STUB_PATH)


@pytest.fixture
def stub(tmp_path):
    return guard.build_stub_env(tmp_path / "stub", base_env={"PATH": NOT_A_STUB_PATH})


class _WouldSpawn(Exception):
    pass


@pytest.fixture
def installed(monkeypatch):
    seen: list = []

    def fake_init(self, args, *a, **kw):
        seen.append(args)
        raise _WouldSpawn(args)

    def fake_system(command):
        seen.append(command)
        raise _WouldSpawn(command)

    monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)
    monkeypatch.setattr(os, "system", fake_system)
    g = _fresh_guard()
    g.install()
    try:
        yield g, seen
    finally:
        g.uninstall()


# ---------------------------------------------------------------------------
# The six cases the lane brief names, through the installed wrapper
# ---------------------------------------------------------------------------
def test_unstubbed_make_dry_run_is_refused(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked, match=r"\$\(MAKE\).*-n"):
        subprocess.run(["make", "-n", "up"])
    assert seen == []
    assert len(g.VIOLATIONS) == 1


def test_same_call_with_the_stub_env_is_allowed(installed, stub):
    g, seen = installed
    with pytest.raises(_WouldSpawn):
        subprocess.run(["make", "-n", "up"], env=stub)
    assert seen == [["make", "-n", "up"]]
    assert g.VIOLATIONS == []


def test_shell_true_make_up_is_refused(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked):
        subprocess.run("make up", shell=True)
    assert seen == []


def test_stub_dir_not_first_on_path_is_refused(installed, stub):
    g, seen = installed
    env = dict(stub)
    env["PATH"] = os.pathsep.join(["/usr/bin", str(stub.stub_dir), "/bin"])
    with pytest.raises(g.DestructiveDockerCallBlocked, match="first PATH entry '/usr/bin'"):
        subprocess.run(["make", "-n", "up"], env=env)
    assert seen == []


def test_stub_dir_without_the_marker_is_refused(installed, stub):
    g, seen = installed
    (stub.stub_dir / g.STUB_MARKER).unlink()
    with pytest.raises(g.DestructiveDockerCallBlocked, match="is not a stub dir"):
        subprocess.run(["make", "-n", "up"], env=stub)
    assert seen == []


def test_git_commit_message_mentioning_make_is_allowed(installed):
    g, seen = installed
    with pytest.raises(_WouldSpawn):
        subprocess.run(["git", "commit", "-m", "run make up"])
    assert seen == [["git", "commit", "-m", "run make up"]]
    assert g.VIOLATIONS == []


# ---------------------------------------------------------------------------
# The rest of the spawn surface
# ---------------------------------------------------------------------------
def test_os_system_make_is_refused(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked):
        os.system("cd pmoves && make up-cipher")
    assert seen == []


def test_env_passed_positionally_is_read(installed, stub):
    """Popen(args, bufsize, executable, stdin, stdout, stderr, preexec_fn,
    close_fds, shell, cwd, env): a positional env must count like env=."""
    g, seen = installed
    with pytest.raises(_WouldSpawn):
        subprocess.Popen(["make", "up"], -1, None, None, None, None, None, True, False, None, dict(stub))
    assert g.VIOLATIONS == []


def test_executable_make_is_refused(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked):
        subprocess.run(["anything", "-n", "up"], executable="/usr/bin/make")
    assert seen == []


def test_list_with_shell_true_is_judged_as_shell_text(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked):
        subprocess.run(["make up"], shell=True)
    assert seen == []


REFUSED_UNSTUBBED = [
    ["make", "-n", "up"],
    ["gmake", "up"],
    ["/usr/bin/make", "-n", "up"],
    ["make", "-s", "-n", "-o", "cipher-build-pin-check", "-C", "pmoves", "up-cipher"],
    ["sudo", "make", "down"],
    ["timeout", "30", "make", "up"],
    ["env", "FOO=1", "make", "up"],
    ["env", "PATH=/tmp/stub:/usr/bin", "make", "up"],  # env PATH= in argv is not honoured
    ["bash", "-c", "cd pmoves && make up"],
    ["bash", "-lc", "true; make -n up-core-capable"],
    ["bash", "pmoves/scripts/with-env.sh", "make", "-C", "pmoves", "up-p7"],
    ["./pmoves/scripts/with-env.sh", "make", "up-p7"],
    ["make", "--version", "up"],  # the info-only allowance is for a sole argument
    "make up",
    "true && make -n up",
    b"make up",
    # the exec-wrapper shape also exposes docker, not only make
    ["bash", "scripts/with-env.sh", "docker", "compose", "down"],
]

ALLOWED_UNSTUBBED = [
    ["git", "commit", "-m", "run make up"],
    "git commit -m 'run make up'",
    ["grep", "-n", "make", "Makefile"],
    ["rg", "make up", "."],
    "echo make up",
    ["python3", "-c", "print('make up')"],
    ["bash", "scripts/some_script.sh", "make up"],  # one token: text, not a command
    ["make", "--version"],
    ["make", "-v"],
    ["make", "--help"],
    ["cmake", "--build", "."],  # cmake is not make
    ["makepkg", "-s"],
]


@pytest.mark.parametrize("argv", REFUSED_UNSTUBBED, ids=repr)
def test_refused_without_a_stub(argv):
    assert guard.check_command(argv), f"should be refused: {argv!r}"


@pytest.mark.parametrize("argv", ALLOWED_UNSTUBBED, ids=repr)
def test_allowed_without_a_stub(argv):
    assert guard.check_command(argv) is None, f"should be allowed: {argv!r} -> {guard.check_command(argv)}"


@pytest.mark.parametrize(
    "argv",
    [
        ["make", "-n", "up"],
        ["gmake", "up"],
        ["bash", "-c", "cd pmoves && make up"],
        ["bash", "pmoves/scripts/with-env.sh", "make", "up-p7"],
        "make -n up",
    ],
    ids=repr,
)
def test_allowed_with_the_stub_env(argv, stub):
    assert guard.check_command(argv, stub) is None


def test_os_environ_path_counts_when_no_env_is_passed(monkeypatch, stub):
    assert guard.check_command(["make", "up"])
    monkeypatch.setenv("PATH", stub["PATH"])
    assert guard.check_command(["make", "up"]) is None


def test_env_without_path_falls_back_to_defpath_and_is_refused(stub):
    env = {k: v for k, v in stub.items() if k != "PATH"}
    assert guard.check_command(["make", "up"], env)


def test_path_qualified_make_outside_the_stub_dir_is_refused_even_with_stub_env(stub):
    assert guard.check_command(["/usr/bin/make", "up"], stub)
    assert guard.check_command([str(stub.stub_dir / "make"), "up"], stub) is None


def test_stub_dir_missing_the_docker_stub_is_refused(stub):
    (stub.stub_dir / "docker").unlink()
    assert guard.check_command(["make", "up"], stub)


def test_relative_stub_dir_is_refused(stub, monkeypatch):
    monkeypatch.chdir(stub.stub_dir.parent)
    env = dict(stub)
    env["PATH"] = os.pathsep.join([stub.stub_dir.name, NOT_A_STUB_PATH])
    assert guard.check_command(["make", "up"], env)


def test_existing_docker_rules_are_unchanged_by_a_stub_env(stub):
    # The stub PATH licenses make only; a direct compose call is judged as before.
    assert guard.check_command(["docker", "compose", "down"], stub)


# ---------------------------------------------------------------------------
# The fixtures, end to end, under the SESSION guard
# ---------------------------------------------------------------------------
def test_stub_tool_path_fixture_records_make_and_never_runs_a_recipe(stub_tool_path):
    proc = subprocess.run(
        ["make", "-n", "-C", "/nonexistent-dir", "up"], env=stub_tool_path, capture_output=True, text=True
    )
    # Real make would fail on the missing -C dir; the recorder exits 0.
    assert proc.returncode == 0, proc.stderr
    assert stub_tool_path.calls("make") == [["make", "-n", "-C", "/nonexistent-dir", "up"]]


def test_stub_docker_path_fixture_leaves_make_unstubbed(stub_docker_path):
    stub_dir = stub_docker_path.stub_dir
    assert (stub_dir / "docker").is_file() and (stub_dir / "docker-compose").is_file()
    assert not (stub_dir / "make").exists()
    assert stub_docker_path["PATH"].split(os.pathsep)[0] == str(stub_dir)
