"""Session-wide guard: tests may not mutate a compose project that is not theirs.

Incident 2026-09-26: ``fresh_start/test_fresh_deployment.py`` ran
``docker compose down`` against ``pmoves/docker-compose.yml`` with no ``-p``.
That file's top-level ``name: pmoves`` sets the project name, so the call
addressed the LIVE stack's project from ANY directory, not only from a cwd
named ``pmoves``. A full-suite run from worktrees removed all 19
default-profile containers of the running stack. (Compose resolves the project
name as ``-p`` > ``COMPOSE_PROJECT_NAME`` > top-level ``name:`` > the project
directory's basename. Only ``-p`` in argv is visible and certain at the call
site, so it is the only thing this guard accepts.)

That fixture is fixed and now makes no compose calls, but it was one call site.
This guard wraps ``subprocess.Popen.__init__`` (which ``run``/``call``/
``check_call``/``check_output`` and asyncio's subprocess transport all go
through) and ``os.system``, and REFUSES TO SPAWN:

* ``docker compose <sub>`` / ``docker-compose <sub>`` where ``<sub>`` is not a
  read-only verb (``config convert ps ls images logs top version port events
  stats``), unless argv names a throwaway project with ``-p``/``--project-name``
  matching ``^pmoves-test-[0-9a-f]{8}$``. Note that ``exec``, ``run``, ``cp``,
  ``pull`` and ``build`` are NOT on the read-only list and are refused: they run
  code in, write into, or replace images under the target project. An
  unrecognised subcommand is refused. A ``COMPOSE_PROJECT_NAME`` env var does
  not count, and ``pmoves`` is never accepted.
* ``docker compose ... down -v/--volumes`` even with a throwaway ``-p``.
* Any plain ``docker <sub>`` outside a read-only allowlist: ``info``, ``ps``,
  ``inspect``, ``images``, ``version``, ``logs``, ``network ls|inspect``,
  ``volume ls|inspect`` (plus their ``container``/``image`` aliases
  ``container ls|inspect|logs``, ``image ls|inspect``). So ``rm``, ``stop``,
  ``kill``, ``pause``, ``update``, ``rmi``, ``image prune``, ``builder prune``
  and ``exec`` are refused by default. ``exec`` is not read-only: it runs an
  arbitrary process inside a live container.

What counts as a docker call, to avoid false positives on text that merely
mentions docker: ``docker``/``docker-compose`` must be the COMMAND -- the first
token, or the first token after a ``sudo``/``env``/``nice``/``timeout``
wrapper. A whitespace-bearing argument is only parsed as a command when it is
the ``-c`` payload of a known shell (``sh bash dash zsh ksh``). So
``git commit -m 'fix docker compose down'`` and ``rg 'docker compose down'`` are
allowed, while ``bash -c 'docker compose down'`` is refused.

A refusal raises :class:`DestructiveDockerCallBlocked`, a ``BaseException``
subclass, so the ``except Exception: pytest.skip(...)`` pattern common in this
suite cannot swallow it.

Scope, stated so nobody reads more coverage into this than it has:

* The WRAPPER is process-global: once ``pmoves/tests/conftest.py`` is imported
  it applies to every spawn in the pytest process, including tests collected
  from outside ``pmoves/tests`` in the same session. The session-STOP hook
  (``pytest_runtest_teardown`` in that conftest) is directory-scoped: pytest
  only calls it for items under ``pmoves/tests``. Outside that directory a
  refusal still fails the test but does not stop the session.
* It only sees spawns made by THIS Python process. A test that launches a shell
  or Python script which in turn runs ``docker compose down`` is not covered.
* It does not interpret ``make`` targets (``make down``).
* It permits ``up`` under a ``pmoves-test-*`` project because that cannot
  remove live containers, but docker-compose.yml's fixed-name networks
  (``pmoves_data``, ``pmoves_app``, ...) and published host ports are shared with
  the live stack whatever ``-p`` says, so such an ``up`` is not isolated.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import Any, Iterable, Sequence

TEST_PROJECT_RE = re.compile(r"^pmoves-test-[0-9a-f]{8}$")

# Compose subcommands that only read state. Everything else is treated as
# mutating, including subcommands this list has never heard of.
COMPOSE_READ_ONLY = frozenset(
    {"config", "convert", "ps", "ls", "images", "logs", "top", "version", "port", "events", "stats"}
)

# Plain-docker read-only allowlist. Everything else is refused.
DOCKER_READ_ONLY_TOP = frozenset({"info", "ps", "inspect", "images", "version", "logs"})
DOCKER_READ_ONLY_PAIRS = {
    "network": frozenset({"ls", "inspect"}),
    "volume": frozenset({"ls", "inspect"}),
    "container": frozenset({"ls", "inspect", "logs"}),
    "image": frozenset({"ls", "inspect"}),
}

# Compose global options that consume the next token as their value.
_COMPOSE_VALUE_OPTS = frozenset(
    {
        "-f",
        "--file",
        "-p",
        "--project-name",
        "--profile",
        "--env-file",
        "--project-directory",
        "--ansi",
        "--progress",
        "--parallel",
    }
)

# Docker CLI global options that consume the next token.
_DOCKER_VALUE_OPTS = frozenset(
    {"-H", "--host", "-c", "--context", "--config", "-l", "--log-level", "--tlscacert", "--tlscert", "--tlskey"}
)

_SHELLS = frozenset({"sh", "bash", "dash", "zsh", "ksh"})

# Wrappers after which the next command token is the real command, with the
# options of each that consume a value.
_WRAPPERS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U"}),
    "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
}

_SHELL_SEPARATORS = frozenset({";", "&", "&&", "|", "||", "(", ")", "\n"})


class DestructiveDockerCallBlocked(BaseException):
    """Raised instead of spawning a docker call that could touch a live project.

    BaseException on purpose: ``except Exception`` must not swallow it.
    """


def _basename(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1]
    return name[:-4] if name.lower().endswith(".exe") else name


def _split_shell(command: str) -> list[list[str]]:
    """Split a shell command string into per-command token lists."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in _SHELL_SEPARATORS or (tok and set(tok) <= set(";&|()")):
            segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


def _strip_wrappers(tokens: Sequence[str]) -> list[str]:
    """Drop leading sudo/env/nice/timeout wrappers; return the real command argv."""
    toks = list(tokens)
    while toks:
        name = _basename(toks[0])
        if name not in _WRAPPERS:
            return toks
        value_opts = _WRAPPERS[name]
        i = 1
        while i < len(toks):
            tok = toks[i]
            if tok == "--":
                i += 1
                break
            if tok in value_opts:
                i += 2
                continue
            if tok.startswith("-"):
                i += 1
                continue
            if name == "env" and "=" in tok:  # VAR=value
                i += 1
                continue
            if name == "nice" and tok.lstrip("-").isdigit():
                i += 1
                continue
            break
        if name == "timeout" and i < len(toks):
            i += 1  # the DURATION positional
        toks = toks[i:]
    return toks


def _compose_verdict(rest: Sequence[str], label: str) -> str | None:
    """Check the tokens after `docker compose` / `docker-compose`."""
    project: str | None = None
    dry_run = False
    sub: str | None = None
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--dry-run":
            dry_run = True
        elif tok in ("-p", "--project-name"):
            project = rest[i + 1] if i + 1 < len(rest) else ""
            i += 1
        elif tok.startswith("--project-name="):
            project = tok.split("=", 1)[1]
        elif tok.startswith("-p") and len(tok) > 2 and not tok.startswith("--"):
            project = tok[2:]
        elif tok in _COMPOSE_VALUE_OPTS:
            i += 1
        elif tok.startswith("-"):
            pass
        else:
            sub = tok
            break
        i += 1
    if sub is None or dry_run:
        return None
    if sub == "down":
        for tok in rest[i + 1 :]:
            if tok == "--volumes" or tok.startswith("--volumes=") or (
                tok.startswith("-") and not tok.startswith("--") and "v" in tok[1:]
            ):
                return f"`{label} down {tok}`: tests may never delete compose volumes."
    if sub in COMPOSE_READ_ONLY:
        return None
    if project is not None and TEST_PROJECT_RE.match(project):
        return None
    shown = (
        "<none in argv: COMPOSE_PROJECT_NAME, else the compose file's top-level `name:` "
        "(pmoves/docker-compose.yml says `name: pmoves`), else the directory basename>"
        if project is None
        else repr(project)
    )
    return (
        f"`{label} {sub}` against project {shown}. Tests may only mutate a throwaway "
        f"project passed in argv as `-p pmoves-test-<8 hex>`."
    )


def _docker_verdict(rest: Sequence[str]) -> str | None:
    """Check the tokens after `docker`."""
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in _DOCKER_VALUE_OPTS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        break
    if i >= len(rest):
        return None  # `docker --version`, `docker --help`
    sub = rest[i]
    tail = list(rest[i + 1 :])
    if sub == "compose":
        return _compose_verdict(tail, "docker compose")
    if sub in DOCKER_READ_ONLY_TOP:
        return None
    verb = next((t for t in tail if not t.startswith("-")), None)
    if sub in DOCKER_READ_ONLY_PAIRS and verb in DOCKER_READ_ONLY_PAIRS[sub]:
        return None
    shown = " ".join(["docker", *rest[i:]])
    return (
        f"`{shown}`: plain docker is limited to a read-only allowlist in tests "
        "(info, ps, inspect, images, version, logs, network/volume ls|inspect)."
    )


def _argv_verdict(tokens: Sequence[str], depth: int = 0) -> str | None:
    toks = _strip_wrappers(tokens)
    if not toks:
        return None
    head = _basename(toks[0])
    if head == "docker":
        return _docker_verdict(toks[1:])
    if head == "docker-compose":
        return _compose_verdict(toks[1:], "docker-compose")
    if head in _SHELLS and depth < 4:
        for idx, tok in enumerate(toks[1:], start=1):
            if tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]:
                if idx + 1 < len(toks):
                    return _shell_verdict(toks[idx + 1], depth + 1)
                return None
            if tok in ("-o", "+o", "-O", "+O"):
                continue  # its value is skipped by the check below
            if not tok.startswith(("-", "+")) and toks[idx - 1] not in ("-o", "+o", "-O", "+O"):
                return None  # `bash script.sh`: a script, not a -c payload
    return None


def _shell_verdict(command: str, depth: int = 0) -> str | None:
    for seg in _split_shell(command):
        reason = _argv_verdict(seg, depth)
        if reason:
            return reason
    return None


def check_command(args: Any) -> str | None:
    """Return a refusal reason if spawning ``args`` would be a forbidden docker call.

    Accepts what ``subprocess.Popen`` accepts: a string (shell form, or a bare
    program name) or a sequence of str/bytes/PathLike.
    """
    if isinstance(args, (bytes, bytearray)):
        args = bytes(args).decode("utf-8", "replace")
    if isinstance(args, (str, os.PathLike)):
        return _shell_verdict(os.fspath(args))
    if not isinstance(args, Iterable):
        return None
    tokens = [(os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a)) for a in args]
    return _argv_verdict(tokens)


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
VIOLATIONS: list[str] = []
_ORIGINALS: dict[str, Any] = {}


def _refuse(reason: str) -> None:
    VIOLATIONS.append(reason)
    raise DestructiveDockerCallBlocked(
        "BLOCKED by pmoves/tests/_destructive_docker_guard.py (incident 2026-09-26: a test "
        "tore down the live `pmoves` compose project): " + reason
    )


def install() -> None:
    """Wrap Popen.__init__ and os.system. Idempotent."""
    if "Popen.__init__" in _ORIGINALS:
        return
    orig_init = subprocess.Popen.__init__
    orig_system = os.system

    def guarded_init(self, args, *a, **kw):  # type: ignore[no-untyped-def]
        reason = check_command(args)
        if reason:
            _refuse(reason)
        return orig_init(self, args, *a, **kw)

    def guarded_system(command):  # type: ignore[no-untyped-def]
        reason = check_command(command)
        if reason:
            _refuse(reason)
        return orig_system(command)

    guarded_init.__wrapped__ = orig_init  # type: ignore[attr-defined]
    guarded_system.__wrapped__ = orig_system  # type: ignore[attr-defined]
    _ORIGINALS["Popen.__init__"] = orig_init
    _ORIGINALS["os.system"] = orig_system
    subprocess.Popen.__init__ = guarded_init  # type: ignore[method-assign]
    os.system = guarded_system


def uninstall() -> None:
    if "Popen.__init__" in _ORIGINALS:
        subprocess.Popen.__init__ = _ORIGINALS.pop("Popen.__init__")  # type: ignore[method-assign]
    if "os.system" in _ORIGINALS:
        os.system = _ORIGINALS.pop("os.system")


def is_installed() -> bool:
    return "Popen.__init__" in _ORIGINALS
