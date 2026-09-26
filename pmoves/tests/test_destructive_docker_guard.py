"""Tests for pmoves/tests/_destructive_docker_guard.py.

No test here can reach Docker:

* ``check_command`` is a pure function over argv; the parametrised cases only
  parse strings.
* The wrapper tests first replace ``subprocess.Popen.__init__`` and
  ``os.system`` with a recorder that RAISES instead of spawning, then install a
  fresh guard instance on top of that recorder. A call the guard lets through
  lands in the recorder, never in a real ``fork/exec``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
SESSION_GUARD_NAME = "pmoves_tests_destructive_docker_guard"
T = "pmoves-test-0123abcd"


def _fresh_guard() -> ModuleType:
    """A separate instance, so installing/uninstalling it cannot disturb the session guard."""
    spec = importlib.util.spec_from_file_location(f"_guard_under_test_{uuid.uuid4().hex[:8]}", GUARD_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _fresh_guard()

BLOCKED = [
    ["docker", "compose", "down"],
    ["docker", "compose", "up", "-d"],
    ["docker", "compose", "-p", "pmoves", "down"],
    ["docker", "compose", "--project-name", "pmoves", "down"],
    ["docker", "compose", "--project-name=pmoves", "stop"],
    ["docker", "compose", "-ppmoves", "rm", "-f"],
    ["docker", "compose", "-p", "pmoves-test-XYZ12345", "down"],
    ["docker", "compose", "-p", "pmoves-test-0123abcd9", "down"],
    ["docker", "compose", "-f", "docker-compose.yml", "restart"],
    ["docker", "compose", "frobnicate"],  # unknown subcommand => mutating
    ["docker", "--context", "default", "compose", "down"],
    ["/usr/bin/docker", "compose", "kill"],
    ["docker-compose", "down"],
    ["sudo", "docker", "compose", "stop"],
    ["env", "COMPOSE_PROJECT_NAME=" + T, "docker", "compose", "down"],  # env is not argv
    ["bash", "-c", "cd pmoves && docker compose down"],
    ["docker", "rm", "-f", "pmoves-agent-zero-1"],
    ["docker", "stop", "supabase-db"],
    ["docker", "kill", "pmoves-nats-1"],
    ["docker", "container", "rm", "pmoves-nats-1"],
    ["docker", "network", "rm", "pmoves_app"],
    ["docker", "volume", "rm", "pmoves_supabase-data"],
    ["docker", "volume", "prune", "-f"],
    ["docker", "container", "prune", "-f"],
    ["docker", "system", "prune", "-af"],
    ["docker", "rm", "-f", f"{T}-web-1", "pmoves-agent-zero-1"],  # one live target poisons the call
    ["docker", "stop", "-t", "10", f"{T}-web-1"],  # unknown value-option: fail-closed
    "docker compose down",
    "cd pmoves; docker compose down --remove-orphans",
    "true && docker-compose rm -f",
    b"docker compose down",
]

ALLOWED = [
    ["docker", "info"],
    ["docker", "ps", "--format", "{{.Names}}"],
    ["docker", "inspect", "pmoves-nats-1"],
    ["docker", "exec", "supabase-db", "pg_isready"],
    ["docker", "network", "ls"],
    ["docker", "compose", "config"],
    ["docker", "compose", "ps"],
    ["docker", "compose", "-f", "docker-compose.yml", "config", "--services"],
    ["docker", "compose", "--dry-run", "down"],
    ["docker", "compose", "-p", T, "down", "--remove-orphans"],
    ["docker", "compose", "--project-name", T, "up", "-d"],
    ["docker", "compose", f"--project-name={T}", "stop"],
    ["docker-compose", "-p", T, "down"],
    ["docker", "rm", "-f", f"{T}-web-1"],
    ["git", "status"],
    ["grep", "-n", "docker", "Makefile"],
    ["python3", "-c", "print(1)"],
    "echo hello",
    f"docker compose -p {T} down",
]


@pytest.mark.parametrize("argv", BLOCKED, ids=lambda a: a if isinstance(a, str) else " ".join(map(str, a)) if not isinstance(a, bytes) else a.decode())
def test_blocked(argv):
    assert guard.check_command(argv), f"should be refused: {argv!r}"


@pytest.mark.parametrize("argv", ALLOWED, ids=lambda a: a if isinstance(a, str) else " ".join(a))
def test_allowed(argv):
    assert guard.check_command(argv) is None, f"should be allowed: {argv!r} -> {guard.check_command(argv)}"


def test_blocked_error_is_not_an_exception_subclass():
    # `except Exception: pytest.skip(...)` is common in this suite; it must not
    # be able to swallow a refusal.
    assert issubclass(guard.DestructiveDockerCallBlocked, BaseException)
    assert not issubclass(guard.DestructiveDockerCallBlocked, Exception)


# ---------------------------------------------------------------------------
# The installed wrapper, over a recorder that never spawns
# ---------------------------------------------------------------------------
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


def test_installed_guard_refuses_before_spawning(installed):
    g, seen = installed
    for argv in (["docker", "compose", "down"], ["docker", "rm", "-f", "pmoves-nats-1"]):
        with pytest.raises(g.DestructiveDockerCallBlocked):
            subprocess.run(argv)
    with pytest.raises(g.DestructiveDockerCallBlocked):
        subprocess.check_output("docker compose down", shell=True)
    with pytest.raises(g.DestructiveDockerCallBlocked):
        os.system("docker compose down")
    assert seen == [], f"refused calls reached the spawn layer: {seen}"
    assert len(g.VIOLATIONS) == 4


def test_except_exception_cannot_swallow_a_refusal(installed):
    g, seen = installed
    with pytest.raises(g.DestructiveDockerCallBlocked):
        try:
            subprocess.run(["docker", "compose", "down"])
        except Exception:  # the pattern the old fixture used
            pass
    assert seen == []


def test_installed_guard_passes_throwaway_and_read_only_calls_through(installed):
    g, seen = installed
    for argv in (["docker", "compose", "-p", T, "down"], ["docker", "info"], ["docker", "compose", "config"]):
        with pytest.raises(_WouldSpawn):
            subprocess.run(argv)
    assert seen == [["docker", "compose", "-p", T, "down"], ["docker", "info"], ["docker", "compose", "config"]]
    assert g.VIOLATIONS == []


def test_uninstall_restores_the_previous_popen_init(monkeypatch):
    sentinel = lambda self, args, *a, **kw: None  # noqa: E731
    monkeypatch.setattr(subprocess.Popen, "__init__", sentinel)
    g = _fresh_guard()
    g.install()
    assert subprocess.Popen.__init__ is not sentinel
    g.install()  # idempotent
    g.uninstall()
    assert subprocess.Popen.__init__ is sentinel


# ---------------------------------------------------------------------------
# Wiring: the conftest actually installed it for this session
# ---------------------------------------------------------------------------
def test_conftest_installed_the_session_guard():
    session_guard = sys.modules.get(SESSION_GUARD_NAME)
    assert session_guard is not None, "pmoves/tests/conftest.py did not load the docker guard"
    assert session_guard.is_installed()
    assert getattr(subprocess.Popen.__init__, "__wrapped__", None) is not None, (
        "subprocess.Popen.__init__ is not wrapped in this session"
    )
    assert session_guard.check_command(["docker", "compose", "down"])


def test_conftest_teardown_hook_stops_the_session_after_a_violation(request):
    conftest = next(
        p for p in request.config.pluginmanager.get_plugins()
        if isinstance(p, ModuleType) and getattr(p, "_DOCKER_GUARD", None) is not None
    )
    session_guard = conftest._DOCKER_GUARD
    item = SimpleNamespace(session=SimpleNamespace(shouldstop=False))

    conftest.pytest_runtest_teardown(item, None)
    assert item.session.shouldstop is False

    session_guard.VIOLATIONS.append("synthetic violation for this test")
    try:
        conftest.pytest_runtest_teardown(item, None)
    finally:
        session_guard.VIOLATIONS.pop()
    assert "synthetic violation" in item.session.shouldstop
