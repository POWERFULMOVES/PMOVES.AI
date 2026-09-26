"""Session-wide guard: tests may not mutate a compose project that is not theirs.

Incident 2026-09-26: ``fresh_start/test_fresh_deployment.py`` ran
``docker compose down`` with ``cwd=pmoves`` and no project name. Compose names
the default project after the cwd's basename -- ``pmoves`` -- which is also the
LIVE stack's project, so a full-suite run from a worktree removed all 19
default-profile containers of the running stack.

That fixture is fixed, but it was one call site. This guard makes the whole
class of mistake impossible to repeat from any test under ``pmoves/tests``: it
wraps ``subprocess.Popen.__init__`` (which ``run``/``call``/``check_call``/
``check_output`` and asyncio's subprocess transport all go through) and
``os.system``, and REFUSES TO SPAWN any of:

* ``docker compose <sub>`` / ``docker-compose <sub>`` where ``<sub>`` is not on
  the read-only allowlist, unless argv names a throwaway project with
  ``-p``/``--project-name`` matching ``^pmoves-test-[0-9a-f]{8}$``. A
  ``COMPOSE_PROJECT_NAME`` env var does not count: the name must be visible in
  argv, and ``pmoves`` is never accepted.
* ``docker rm|stop|kill|restart`` and ``docker container|network|volume|system``
  removal/prune verbs, unless every positional target starts with
  ``pmoves-test-``. Prune verbs have no targets and are always refused.

A refusal raises :class:`DestructiveDockerCallBlocked`, a ``BaseException``
subclass, so the ``except Exception: pytest.skip(...)`` pattern common in this
suite cannot swallow it. The conftest also stops the session after the test
that tripped it.

Parsing is deliberately fail-closed: an unrecognised compose subcommand is
treated as mutating, and a value-taking option the parser does not know about
(``docker stop -t 10 x``) makes ``10`` look like a target and is refused.

Known limits (stated so nobody reads more coverage into this than it has):

* It only sees spawns made by THIS Python process. A test that launches a shell
  or Python script which in turn runs ``docker compose down`` is not covered.
* It does not interpret ``make`` targets (``make down``); it cannot know what a
  recipe runs.
* It does not isolate ``up``: ``docker-compose.yml`` pins ``container_name:`` on
  many services, so even a throwaway project's ``up`` collides with live
  container names. The guard permits it under ``pmoves-test-*`` because it
  cannot remove live containers, but it can fail.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from typing import Any, Iterable, Sequence

TEST_PROJECT_RE = re.compile(r"^pmoves-test-[0-9a-f]{8}$")
TEST_RESOURCE_PREFIX = "pmoves-test-"

# Compose subcommands that only read state. Everything else is treated as
# mutating, including subcommands this list has never heard of.
COMPOSE_READ_ONLY = frozenset(
    {"config", "convert", "ps", "ls", "images", "logs", "top", "version", "port", "events", "stats"}
)

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

# (subcommand,) or (object, verb) pairs that remove or stop things.
_DOCKER_DESTRUCTIVE_TOP = frozenset({"rm", "stop", "kill", "restart"})
_DOCKER_DESTRUCTIVE_PAIRS = {
    "container": frozenset({"rm", "stop", "kill", "restart", "prune"}),
    "network": frozenset({"rm", "prune", "disconnect"}),
    "volume": frozenset({"rm", "prune"}),
    "system": frozenset({"prune"}),
}
_PRUNE = "prune"

_SHELL_SEPARATORS = frozenset({";", "&", "&&", "|", "||", "(", ")", "\n"})


class DestructiveDockerCallBlocked(BaseException):
    """Raised instead of spawning a docker call that could touch a live project.

    BaseException on purpose: ``except Exception`` must not swallow it.
    """


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1]


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
        if tok in _SHELL_SEPARATORS or set(tok) <= set(";&|()"):
            segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


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
    if sub is None or sub in COMPOSE_READ_ONLY or dry_run:
        return None
    if project is not None and TEST_PROJECT_RE.match(project):
        return None
    shown = "<default: cwd basename, e.g. 'pmoves'>" if project is None else repr(project)
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
        return None
    sub = rest[i]
    tail = list(rest[i + 1 :])
    if sub == "compose":
        return _compose_verdict(tail, "docker compose")
    verb: str | None = None
    if sub in _DOCKER_DESTRUCTIVE_TOP:
        verb = sub
    elif sub in _DOCKER_DESTRUCTIVE_PAIRS and tail and tail[0] in _DOCKER_DESTRUCTIVE_PAIRS[sub]:
        verb = f"{sub} {tail[0]}"
        tail = tail[1:]
    if verb is None:
        return None
    targets = [t for t in tail if not t.startswith("-")]
    if verb.endswith(_PRUNE) or not targets or not all(t.startswith(TEST_RESOURCE_PREFIX) for t in targets):
        shown = " ".join(["docker", verb, *tail])
        return (
            f"`{shown}`: tests may only remove/stop resources named "
            f"`{TEST_RESOURCE_PREFIX}*`, and may never prune."
        )
    return None


def _segment_verdict(tokens: Sequence[str]) -> str | None:
    for idx, tok in enumerate(tokens):
        name = _basename(tok)
        if name in ("docker", "docker.exe"):
            return _docker_verdict(tokens[idx + 1 :])
        if name in ("docker-compose", "docker-compose.exe"):
            return _compose_verdict(tokens[idx + 1 :], "docker-compose")
    return None


def check_command(args: Any) -> str | None:
    """Return a refusal reason if spawning ``args`` would be a forbidden docker call.

    Accepts what ``subprocess.Popen`` accepts: a string (shell form) or a
    sequence of str/bytes/PathLike. Elements that themselves look like shell
    commands (``bash -c "docker compose down"``) are inspected too.
    """
    if isinstance(args, (bytes, bytearray)):
        args = bytes(args).decode("utf-8", "replace")
    if isinstance(args, (str, os.PathLike)):
        for seg in _split_shell(os.fspath(args)):
            reason = _segment_verdict(seg)
            if reason:
                return reason
        return None
    if not isinstance(args, Iterable):
        return None
    tokens = [
        (os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a)) for a in args
    ]
    reason = _segment_verdict(tokens)
    if reason:
        return reason
    for tok in tokens:
        if "docker" in tok and any(c.isspace() for c in tok):
            reason = check_command(tok)
            if reason:
                return reason
    return None


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
