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
  arbitrary process inside a live container. The ONLY exec shapes allowed are
  ``docker exec [-i|-t|-T] <container> pg_isready [flags]`` and
  ``docker exec [-i|-t|-T] <container> psql [conn flags] -c "<sql>"`` where
  ``<sql>`` is a single plain SELECT: it starts with SELECT, has no ``;``
  except one optional trailing ``;``, no backslash meta-command and no
  ``INTO``. ``sh -c``, ``bash``, ``psql -f``, several ``-c`` and any other exec
  flag (``-u``, ``-e``, ``-w``, ``--privileged``) are refused. Residual risk
  stated plainly: a SELECT can still call a side-effecting function
  (``SELECT pg_terminate_backend(...)``, ``SELECT nextval(...)``); this is a
  read-mostly allowance for two smoke checks, not a SQL sandbox.

``make`` / ``gmake`` (follow-up to #3190). A test that spawns make reaches the
daemon through the RECIPES, which this guard never sees: a recipe's
``docker compose`` runs in make's own child shell, not in this Python process.
``make -n`` is NOT a safe dry run either. GNU make still EXECUTES every recipe
line that contains ``$(MAKE)`` (or starts with ``+``) under ``-n``, so that the
sub-make can print its own plan -- and the whole line runs, including anything
after ``&&``/``;`` on it. ``up-core-capable`` -> ``up-core-hardened`` ->
``supa-start`` is one such chain in pmoves/Makefile, whose nested compose call
runs under ``-n``. Parse-time ``$(shell ...)`` also runs on every invocation.
And because pmoves/docker-compose.yml sets top-level ``name: pmoves``, any
compose call such a line reaches addresses the LIVE project from any directory.

So every spawn of ``make``/``gmake`` is refused -- as argv[0] (or the
``executable=``), after a ``sudo``/``env``/``nice``/``timeout`` wrapper, as
any command in a shell ``-c`` payload or ``shell=True`` string, and as the
first argument of an exec-wrapper script (``bash scripts/with-env.sh make ...``,
``./with-env.sh make ...``, the fleet's canonical loader shape) -- UNLESS the
PATH that make's child processes will search starts with a STUB DIRECTORY:

* the PATH is the call's ``env["PATH"]`` when ``env=`` is given (``os.defpath``
  if that env has no PATH), else ``os.environ["PATH"]``;
* its FIRST entry must be an absolute directory that contains the marker file
  ``.pmoves-test-stub`` AND executable ``docker`` and ``docker-compose``
  stubs. :func:`build_stub_env` (the ``stub_tool_path`` / ``stub_docker_path``
  fixtures in pmoves/tests/conftest.py) is the sanctioned way to make one;
* a path-qualified program (``/usr/bin/make``) bypasses PATH lookup for make
  itself, so it is only accepted when it lives IN such a stub directory.

With ``stub_tool_path`` make itself is a recorder: no recipe runs at all. With
``stub_docker_path`` the real make runs, but every ``docker``/``docker-compose``/
``supabase`` a recipe resolves through PATH lands in a recorder. That second
form is NOT a sandbox: a recipe that calls ``/usr/bin/docker`` by absolute
path, resets PATH, or talks to the daemon socket from Python bypasses it.
Before using it, read the target's recipe chain.

``make --version`` / ``-v`` / ``--help`` / ``-h`` as the ONLY argument are
allowed unstubbed: make exits before reading any makefile. An ``env PATH=...``
wrapper in argv is not honoured as the effective PATH; pass ``env=`` instead.
The exec-wrapper rule also applies to docker: ``bash with-env.sh docker compose
down`` is judged as ``docker compose down``.

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
* It does not interpret ``make`` targets (``make down``); it refuses make
  wholesale unless the stub PATH rule above holds, and it cannot see a make
  that a spawned script runs internally (other than the exec-wrapper shape).
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
from pathlib import Path
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

# The narrow `docker exec` allowlist (see _exec_verdict).
_EXEC_OK_FLAGS = frozenset({"-i", "-t", "-T", "-it", "-ti", "--interactive", "--tty"})
_PSQL_CONN_VALUE_OPTS = frozenset({"-U", "--username", "-d", "--dbname", "-h", "--host", "-p", "--port"})
_PSQL_CONN_FLAGS = frozenset({"-w", "--no-password", "-W", "--password"})
_SELECT_RE = re.compile(r"(?i)select\b")
_INTO_RE = re.compile(r"(?i)\binto\b")

# Wrappers after which the next command token is the real command, with the
# options of each that consume a value.
_WRAPPERS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U"}),
    "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
}

_SHELL_SEPARATORS = frozenset({";", "&", "&&", "|", "||", "(", ")", "\n"})

# make: refused unless the effective PATH starts with a marked stub dir.
MAKE_NAMES = frozenset({"make", "gmake"})
STUB_MARKER = ".pmoves-test-stub"
# A stub dir must shadow these, or it is not a stub dir.
STUB_REQUIRED = ("docker", "docker-compose")
# make exits on these before reading any makefile.
_MAKE_INFO_ONLY = frozenset({"--version", "-v", "--help", "-h"})
# A command that, as an exec-wrapper script's first argument, the script runs
# (`bash scripts/with-env.sh make up` -- with-env.sh ends in `exec "$@"`).
_EXEC_WRAPPED = MAKE_NAMES | {"docker", "docker-compose"}

# Popen.__init__ positional parameters after `args`, up to `env`.
_POPEN_POSITIONAL = (
    "bufsize", "executable", "stdin", "stdout", "stderr",
    "preexec_fn", "close_fds", "shell", "cwd", "env",
)


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


def select_only_sql_problem(sql: str) -> str | None:
    """Why `sql` is not a single plain SELECT, or None if it is.

    Single statement: after stripping, it must start with SELECT
    (case-insensitive, as a word), contain no `;` except one optional trailing
    `;`, contain no backslash (psql meta-commands such as `\\!` run shell
    commands), and contain no INTO (`SELECT ... INTO t` creates a table).
    """
    s = sql.strip()
    if not _SELECT_RE.match(s):
        return "does not start with SELECT"
    body = s[:-1] if s.endswith(";") else s
    if ";" in body:
        return "contains more than one statement"
    if "\\" in s:
        return "contains a psql backslash meta-command"
    if _INTO_RE.search(s):
        return "uses SELECT ... INTO, which creates a table"
    return None


def _exec_verdict(tail: Sequence[str]) -> str | None:
    """`docker exec` is refused except two exact read-only shapes.

    * ``docker exec [-i|-t|-T ...] <container> pg_isready [pg_isready flags]``
    * ``docker exec [-i|-t|-T ...] <container> psql [conn flags] -c "<SELECT>"``
      with exactly one ``-c``/``--command``, no ``-f``, no other options or
      positional arguments, and SQL accepted by :func:`select_only_sql_problem`.

    Everything else through exec -- ``sh -c``, ``bash``, ``psql -f``, a second
    ``-c``, ``-u root``, ``-e``, arbitrary binaries -- is refused.
    """
    shown = " ".join(["docker", "exec", *tail])
    refuse = f"`{shown}`: docker exec is refused in tests except `pg_isready` or `psql -c '<single SELECT>'`"
    i = 0
    while i < len(tail) and tail[i].startswith("-"):
        if tail[i] not in _EXEC_OK_FLAGS:
            return refuse + f" (exec flag {tail[i]!r} is not allowed)."
        i += 1
    if i + 1 >= len(tail):
        return refuse + "."
    command = _basename(tail[i + 1])
    args = list(tail[i + 2 :])
    if command == "pg_isready":
        return None
    if command != "psql":
        return refuse + "."
    sql: list[str] = []
    j = 0
    while j < len(args):
        tok = args[j]
        if tok in ("-c", "--command"):
            if j + 1 >= len(args):
                return refuse + " (-c without SQL)."
            sql.append(args[j + 1])
            j += 2
        elif tok.startswith("--command="):
            sql.append(tok.split("=", 1)[1])
            j += 1
        elif tok in _PSQL_CONN_VALUE_OPTS:
            j += 2
        elif tok.startswith("--") and tok.split("=", 1)[0] in _PSQL_CONN_VALUE_OPTS:
            j += 1
        elif tok in _PSQL_CONN_FLAGS:
            j += 1
        else:
            return refuse + f" (psql argument {tok!r} is not a connection flag or -c)."
    if len(sql) != 1:
        return refuse + f" (exactly one -c is required, got {len(sql)})."
    problem = select_only_sql_problem(sql[0])
    if problem:
        return refuse + f" (SQL {problem})."
    return None


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
    if sub == "exec":
        return _exec_verdict(tail)
    verb = next((t for t in tail if not t.startswith("-")), None)
    if sub in DOCKER_READ_ONLY_PAIRS and verb in DOCKER_READ_ONLY_PAIRS[sub]:
        return None
    shown = " ".join(["docker", *rest[i:]])
    return (
        f"`{shown}`: plain docker is limited to a read-only allowlist in tests "
        "(info, ps, inspect, images, version, logs, network/volume ls|inspect)."
    )


def is_stub_dir(directory: str) -> bool:
    """True if `directory` is an absolute dir holding the marker and the docker stubs."""
    if not directory or not os.path.isabs(directory):
        return False
    if not os.path.isfile(os.path.join(directory, STUB_MARKER)):
        return False
    return all(
        os.path.isfile(os.path.join(directory, name)) and os.access(os.path.join(directory, name), os.X_OK)
        for name in STUB_REQUIRED
    )


def _first_path_entry(path_value: str | None) -> str:
    if path_value is None:
        path_value = os.environ.get("PATH", os.defpath)
    return path_value.split(os.pathsep)[0]


def _make_verdict(toks: Sequence[str], path_value: str | None) -> str | None:
    """`toks` is a make argv (toks[0] is make/gmake, possibly path-qualified)."""
    if len(toks) == 2 and toks[1] in _MAKE_INFO_ONLY:
        return None
    program = toks[0]
    shown = " ".join(toks)
    why = (
        f"`{shown}`: make runs its recipes' docker/compose calls where this guard cannot "
        "see them, and executes every recipe line containing $(MAKE) even under -n; "
        "pmoves/docker-compose.yml's `name: pmoves` makes any compose call they reach "
        "address the LIVE project. Spawn make only with the `stub_tool_path` or "
        "`stub_docker_path` fixture (pmoves/tests/conftest.py), whose env puts a stub "
        f"dir holding `{STUB_MARKER}` first on PATH"
    )
    if "/" in program or "\\" in program:
        where = os.path.dirname(program)
        if os.path.isabs(program) and is_stub_dir(where):
            return None
        return why + f" (a path-qualified make must live in a stub dir; {where!r} is not one)."
    first = _first_path_entry(path_value)
    if is_stub_dir(first):
        return None
    return why + f" (first PATH entry {first!r} is not a stub dir)."


def _argv_verdict(tokens: Sequence[str], depth: int = 0, path_value: str | None = None) -> str | None:
    toks = _strip_wrappers(tokens)
    if not toks:
        return None
    head = _basename(toks[0])
    if head == "docker":
        return _docker_verdict(toks[1:])
    if head == "docker-compose":
        return _compose_verdict(toks[1:], "docker-compose")
    if head in MAKE_NAMES:
        return _make_verdict(toks, path_value)
    if head.endswith(".sh") and len(toks) > 1 and _basename(toks[1]) in _EXEC_WRAPPED and depth < 4:
        # `./scripts/with-env.sh make up`: the script execs its arguments.
        return _argv_verdict(toks[1:], depth + 1, path_value)
    if head in _SHELLS and depth < 4:
        for idx, tok in enumerate(toks[1:], start=1):
            if tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]:
                if idx + 1 < len(toks):
                    return _shell_verdict(toks[idx + 1], depth + 1, path_value)
                return None
            if tok in ("-o", "+o", "-O", "+O"):
                continue  # its value is skipped by the check below
            if not tok.startswith(("-", "+")) and toks[idx - 1] not in ("-o", "+o", "-O", "+O"):
                # `bash script.sh`: a script, not a -c payload. Its first
                # argument is still judged when it names a guarded command
                # (`bash scripts/with-env.sh make up`).
                if idx + 1 < len(toks) and _basename(toks[idx + 1]) in _EXEC_WRAPPED:
                    return _argv_verdict(toks[idx + 1 :], depth + 1, path_value)
                return None
    return None


def _shell_verdict(command: str, depth: int = 0, path_value: str | None = None) -> str | None:
    for seg in _split_shell(command):
        reason = _argv_verdict(seg, depth, path_value)
        if reason:
            return reason
    return None


def _env_path(env: Any) -> str | None:
    """The PATH a child spawned with `env=` will search; None means os.environ's."""
    if env is None:
        return None
    try:
        value = env.get("PATH")
        if value is None:
            value = env.get(b"PATH")
    except (AttributeError, TypeError):
        return None
    if value is None:
        return os.defpath
    return os.fsdecode(value)


def check_command(args: Any, env: Any = None, *, executable: Any = None, shell: bool = False) -> str | None:
    """Return a refusal reason if spawning ``args`` would be a forbidden call.

    Accepts what ``subprocess.Popen`` accepts: a string (shell form, or a bare
    program name) or a sequence of str/bytes/PathLike. ``env``, ``executable``
    and ``shell`` are the matching Popen arguments; ``env`` decides which PATH
    a spawned make is judged against (see the module docstring).
    """
    path_value = _env_path(env)
    if isinstance(args, (bytes, bytearray)):
        args = bytes(args).decode("utf-8", "replace")
    if isinstance(args, (str, os.PathLike)):
        return _shell_verdict(os.fspath(args), 0, path_value)
    if not isinstance(args, Iterable):
        return None
    tokens = [(os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a)) for a in args]
    if not tokens:
        return None
    reason = _argv_verdict(tokens, 0, path_value)
    if reason is None and shell:
        # Popen runs [/bin/sh, "-c", args[0], *args[1:]]: args[0] is shell text.
        reason = _shell_verdict(tokens[0], 0, path_value)
    if reason is None and executable is not None:
        # `executable=` replaces the program that actually runs; argv[0] stays.
        exe = os.fsdecode(executable) if isinstance(executable, (bytes, os.PathLike)) else str(executable)
        reason = _argv_verdict([exe, *tokens[1:]], 0, path_value)
    return reason


def _spawn_context(a: tuple, kw: dict) -> tuple[Any, Any, bool]:
    """(env, executable, shell) from Popen.__init__'s positional + keyword args."""
    bound = dict(zip(_POPEN_POSITIONAL, a))
    bound.update(kw)
    return bound.get("env"), bound.get("executable"), bool(bound.get("shell", False))


# ---------------------------------------------------------------------------
# Stub tool directory: the sanctioned way for a test to spawn make
# ---------------------------------------------------------------------------
STUB_TOOLS = ("docker", "docker-compose", "supabase")
STUB_LOG_NAME = "stub-calls.log"


class StubEnv(dict):
    """An env dict whose PATH starts with a marked stub dir.

    ``stub_dir`` holds the recorders, ``log`` the file they append to, and
    :meth:`calls` parses it into ``[[tool, arg1, ...], ...]``.
    """

    stub_dir: Path
    log: Path

    def calls(self, tool: str | None = None) -> list[list[str]]:
        if not self.log.exists():
            return []
        rows = [line.split("\t") for line in self.log.read_text().splitlines() if line]
        return [r for r in rows if tool is None or r[0] == tool]


def _recorder(name: str, log: Path) -> str:
    return (
        "#!/bin/sh\n"
        "# pmoves test stub (pmoves/tests/_destructive_docker_guard.py): records argv, exits 0,\n"
        "# never reaches a daemon.\n"
        f"{{ printf '%s' {shlex.quote(name)}; for a in \"$@\"; do printf '\\t%s' \"$a\"; done; "
        f"printf '\\n'; }} >> {shlex.quote(str(log))}\n"
        "exit 0\n"
    )


def build_stub_env(
    directory: str | os.PathLike[str],
    *,
    stub_make: bool = True,
    extra: Iterable[str] = (),
    base_env: dict[str, str] | None = None,
) -> StubEnv:
    """Create a stub tool dir in `directory` and return an env with it FIRST on PATH.

    ``stub_make=True``: make/gmake are recorders too, so no recipe runs.
    ``stub_make=False``: the real make is found further down PATH and runs its
    recipes; docker/docker-compose/supabase still resolve to recorders. Read
    the module docstring for what that second form does NOT cover.
    """
    stub_dir = Path(os.path.realpath(os.fspath(directory)))
    stub_dir.mkdir(parents=True, exist_ok=True)
    log = stub_dir / STUB_LOG_NAME
    names = list(STUB_TOOLS) + (sorted(MAKE_NAMES) if stub_make else []) + list(extra)
    for name in names:
        tool = stub_dir / name
        tool.write_text(_recorder(name, log))
        tool.chmod(0o755)
    (stub_dir / STUB_MARKER).write_text("pmoves test stub dir: see pmoves/tests/_destructive_docker_guard.py\n")
    env = StubEnv(os.environ if base_env is None else base_env)
    env["PATH"] = os.pathsep.join([str(stub_dir), env.get("PATH", os.defpath)])
    env.stub_dir = stub_dir
    env.log = log
    return env


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
        env, executable, shell = _spawn_context(a, kw)
        reason = check_command(args, env, executable=executable, shell=shell)
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
