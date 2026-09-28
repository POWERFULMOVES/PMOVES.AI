"""Regression: the ``fresh_deployment`` fixture must never address the live project.

Incident 2026-09-26: the fixture ran ``docker compose down`` against
pmoves/docker-compose.yml with no ``-p``. That file's top-level ``name: pmoves``
selects the live stack's project from any directory, so the call removed its 19
default-profile containers. The fixture now makes no compose calls at all.

These tests drive the fixture function directly and NEVER reach Docker:

* ``subprocess.run`` is replaced by :class:`_Recorder`, which appends the argv to
  a list and returns a fabricated ``CompletedProcess``. It does not call the
  original ``run`` and does not construct a ``Popen``.
* ``subprocess.Popen.__init__`` and ``os.system`` are replaced by a function that
  raises, so any spawn route that bypasses ``subprocess.run`` fails the test
  instead of executing.
* Importing ``test_fresh_deployment.py`` runs only path arithmetic at module
  level; it spawns nothing.

(And ``pmoves/tests/conftest.py`` installs the session-wide docker guard as a
further backstop; these tests do not rely on it.)
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
import subprocess
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

FIXTURE_FILE = Path(__file__).with_name("test_fresh_deployment.py")
THROWAWAY_RE = re.compile(r"^pmoves-test-[0-9a-f]{8}$")
LIVE_PROJECT = "pmoves"


def _load_fixture_module(path: Path = FIXTURE_FILE) -> ModuleType:
    name = f"_fresh_deployment_under_test_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw(fixture: Any):
    """The plain function behind a ``@pytest.fixture`` (pytest 7 and 8/9)."""
    wrapped = getattr(fixture, "__wrapped__", None)
    if wrapped is not None:
        return wrapped
    legacy = getattr(fixture, "__pytest_wrapped__", None)
    if legacy is not None:
        return legacy.obj
    return fixture


class _Recorder:
    """Stand-in for ``subprocess.run``. Records, fabricates, never spawns."""

    def __init__(self, ps_stdout: str = "pmoves-agent-zero-1\npmoves-nats-1\n") -> None:
        self.calls: list[dict[str, Any]] = []
        self.ps_stdout = ps_stdout

    def __call__(self, args, *a, **kw):  # noqa: ANN001 - mirrors subprocess.run
        argv = [str(x) for x in args] if not isinstance(args, str) else args.split()
        self.calls.append({"argv": argv, "env": kw.get("env"), "cwd": kw.get("cwd")})
        # A non-empty `ps` makes the fixture take its `down` branch -- the branch
        # that did the damage -- so the assertions below actually see it.
        stdout = self.ps_stdout if "ps" in argv else ""
        if not kw.get("text") and not kw.get("universal_newlines"):
            stdout = stdout.encode()
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=stdout[:0])

    @property
    def docker_calls(self) -> list[list[str]]:
        return [c["argv"] for c in self.calls if c["argv"] and Path(c["argv"][0]).name.startswith("docker")]

    @property
    def compose_calls(self) -> list[dict[str, Any]]:
        out = []
        for c in self.calls:
            argv = c["argv"]
            if not argv:
                continue
            head = Path(argv[0]).name
            if head == "docker-compose" or (head == "docker" and "compose" in argv[1:2]):
                out.append(c)
        return out


def _forbid_spawn(*_a, **_kw):
    raise AssertionError("test attempted a real process spawn; it must stay on the recorder")


@pytest.fixture
def recorder(monkeypatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(subprocess, "run", rec)
    monkeypatch.setattr(subprocess.Popen, "__init__", _forbid_spawn)
    monkeypatch.setattr(os, "system", _forbid_spawn)
    return rec


@pytest.fixture
def fixture_module() -> ModuleType:
    return _load_fixture_module()


def _drive(module: ModuleType) -> Any:
    """Run the fixture's setup and teardown the way pytest would.

    If the fixture requests ``docker_available`` (origin/main's did), resolve
    it by calling that fixture's function too, as pytest would -- which is
    itself a recorded ``docker info``.
    """
    fn = _raw(module.fresh_deployment)
    kwargs = {}
    if "docker_available" in inspect.signature(fn).parameters:
        kwargs["docker_available"] = _raw(module.docker_available)()
    result = fn(**kwargs)
    if not inspect.isgenerator(result):
        return result
    value = next(result)
    with pytest.raises(StopIteration):
        next(result)
    return value


# ---------------------------------------------------------------------------
# Opt-in gate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("opt_in", [None, "", "0", "true", "yes"])
def test_without_opt_in_fixture_skips_and_calls_no_docker(monkeypatch, recorder, fixture_module, opt_in):
    if opt_in is None:
        monkeypatch.delenv("PMOVES_DESTRUCTIVE_TESTS", raising=False)
    else:
        monkeypatch.setenv("PMOVES_DESTRUCTIVE_TESTS", opt_in)
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)

    with pytest.raises(pytest.skip.Exception, match="PMOVES_DESTRUCTIVE_TESTS"):
        _drive(fixture_module)

    assert recorder.docker_calls == [], (
        "without the opt-in the fixture must not contact Docker at all, "
        f"not even `docker info`; recorded: {recorder.docker_calls}"
    )


@pytest.mark.parametrize("live_name", ["pmoves", "PMOVES", " pmoves "])
def test_compose_project_name_env_naming_live_project_is_refused(monkeypatch, recorder, fixture_module, live_name):
    monkeypatch.setenv("PMOVES_DESTRUCTIVE_TESTS", "1")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", live_name)

    with pytest.raises(pytest.skip.Exception, match="COMPOSE_PROJECT_NAME"):
        _drive(fixture_module)

    assert recorder.docker_calls == []


# ---------------------------------------------------------------------------
# With the opt-in: no compose call at all, only a read-only `docker info`
# ---------------------------------------------------------------------------
def test_opt_in_makes_no_compose_calls_and_yields_a_throwaway_name(monkeypatch, recorder, fixture_module):
    monkeypatch.setenv("PMOVES_DESTRUCTIVE_TESTS", "1")
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)

    yielded = _drive(fixture_module)

    # Any compose call, even one pinned with `-p`, is out: the fixture creates
    # nothing to clean up, and older compose removes the fixed-name networks
    # (pmoves_data, pmoves_app, ...) by name on `down`.
    compose = recorder.compose_calls
    assert compose == [], f"the fixture must make no compose calls; recorded: {[c['argv'] for c in compose]}"
    assert recorder.docker_calls == [["docker", "info"]], (
        f"only the read-only availability probe is allowed: {recorder.docker_calls}"
    )
    assert isinstance(yielded, str) and THROWAWAY_RE.match(yielded), yielded
    assert yielded != LIVE_PROJECT


def test_each_module_run_gets_a_distinct_throwaway_project(monkeypatch, recorder, fixture_module):
    monkeypatch.setenv("PMOVES_DESTRUCTIVE_TESTS", "1")
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)
    assert _drive(fixture_module) != _drive(fixture_module)


# ---------------------------------------------------------------------------
# Helpers the fixture relies on (these are new symbols; see the PR for why the
# failing-before control counts them separately from the behavioural tests)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["pmoves", "PMOVES", "pmoves-test-", "pmoves-test-XYZ12345", "pmoves-test-0123abcd9", "other"])
def test_compose_argv_refuses_anything_but_a_throwaway_name(fixture_module, bad):
    with pytest.raises(RuntimeError):
        fixture_module.compose_argv(bad, "down")


@pytest.mark.parametrize("flag", ["-v", "--volumes", "--volumes=true"])
def test_compose_argv_refuses_down_with_volumes(fixture_module, flag):
    with pytest.raises(RuntimeError, match="volumes"):
        fixture_module.compose_argv(fixture_module.throwaway_project_name(), "down", flag)


def test_compose_argv_pins_the_throwaway_project(fixture_module):
    project = fixture_module.throwaway_project_name()
    argv = fixture_module.compose_argv(project, "down", "--remove-orphans")
    assert argv == ["docker", "compose", "-p", project, "down", "--remove-orphans"]


def test_throwaway_name_shape(fixture_module):
    for _ in range(50):
        assert THROWAWAY_RE.match(fixture_module.throwaway_project_name())
