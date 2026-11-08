"""Static regression: no test may spawn `docker compose` without pinning a project.

Incident 2026-09-26: a fixture spawned ``docker compose down`` with no ``-p``;
pmoves/docker-compose.yml's top-level ``name: pmoves`` then addressed the live
stack from any directory and removed its 19 default-profile containers.

The runtime guard (``_destructive_docker_guard.py``) refuses such a call when it
happens. This test refuses it at REVIEW time: it parses every
``pmoves/tests/**/*.py`` with :mod:`ast` -- it imports and executes none of
them -- and fails on any process-spawning call (``subprocess.run/Popen/call/
check_call/check_output/getoutput/getstatusoutput``, ``os.system/popen``,
``asyncio.create_subprocess_*``) whose command mentions ``docker compose`` or
``docker-compose`` unless

* the command expression goes through ``compose_argv(...)``, or
* every compose occurrence in its literal argv carries ``-p``/``--project-name``
  among compose's global options (before the subcommand).

A command held in a local variable is resolved through assignments and ``for``
targets in the enclosing function (then module), so ``cmd = [...]; run(cmd)``
is caught too. Anything the resolver cannot see (a value from another module,
a function return) is not flagged -- the runtime guard covers that.
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent

SPAWN_ATTRS = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "getoutput",
        "getstatusoutput",
        "system",
        "popen",
        "create_subprocess_exec",
        "create_subprocess_shell",
    }
)
_VARARGS_SPAWNS = frozenset({"create_subprocess_exec"})

# Call sites that deliberately hand a bare compose command to the RUNTIME
# guard, over a faked Popen, to prove the guard refuses it. Keyed by
# (path relative to pmoves/tests, enclosing function). Every entry must still
# match a real finding; a stale entry fails `test_allowlist_is_not_stale`.
ALLOWLIST = frozenset(
    {
        ("test_destructive_docker_guard.py", "test_installed_guard_refuses_before_spawning"),
        ("test_destructive_docker_guard.py", "test_except_exception_cannot_swallow_a_refusal"),
        ("test_destructive_docker_guard.py", "test_installed_guard_passes_throwaway_and_read_only_calls_through"),
    }
)

_COMPOSE_VALUE_OPTS = frozenset(
    {"-f", "--file", "--profile", "--env-file", "--project-directory", "--ansi", "--progress", "--parallel"}
)
_COMPOSE_MENTION = re.compile(r"docker[ -]compose(?![\w.-])")
_DOCKER_VALUE_OPTS = frozenset({"-H", "--host", "-c", "--context", "--config", "-l", "--log-level"})


def _func_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


class _Scanner:
    def __init__(self, tree: ast.AST) -> None:
        self.tree = tree
        self.parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node

    def enclosing_function(self, node: ast.AST) -> ast.AST | None:
        cur = self.parent.get(node)
        while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cur = self.parent.get(cur)
        return cur

    def _bindings(self, scope: ast.AST, name: str, before: int) -> list[ast.AST]:
        """Values assigned to `name` in `scope` before line `before`."""
        values: list[ast.AST] = []
        for node in ast.walk(scope):
            if getattr(node, "lineno", before) >= before:
                continue
            if isinstance(node, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                    values.append(node.value)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                if isinstance(node.target, ast.Name) and node.target.id == name:
                    values.append(node.value)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                if isinstance(node.target, ast.Name) and node.target.id == name:
                    values.append(node.iter)
        return values

    def resolve(self, expr: ast.AST, at: ast.AST, depth: int = 0) -> tuple[list[str], bool]:
        """(string constants in source order, uses_compose_argv) for `expr`."""
        strings: list[str] = []
        uses_helper = False
        nodes = sorted(
            (n for n in ast.walk(expr) if hasattr(n, "lineno")),
            key=lambda n: (n.lineno, n.col_offset),
        )
        for node in nodes:
            if isinstance(node, ast.Call) and _func_name(node) == "compose_argv":
                uses_helper = True
            elif isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
                value = node.value.decode("utf-8", "replace") if isinstance(node.value, bytes) else node.value
                strings.append(value)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and depth < 3:
                scope = self.enclosing_function(at) or self.tree
                bound = self._bindings(scope, node.id, at.lineno)
                if not bound and scope is not self.tree:
                    bound = self._bindings(self.tree, node.id, at.lineno)
                for value in bound:
                    more, helper = self.resolve(value, at, depth + 1)
                    strings.extend(more)
                    uses_helper = uses_helper or helper
        return strings, uses_helper


def _tokens(strings: list[str]) -> list[str]:
    out: list[str] = []
    for s in strings:
        if any(c.isspace() for c in s):
            try:
                out.extend(shlex.split(s))
            except ValueError:
                out.extend(s.split())
        else:
            out.append(s)
    return out


def _unpinned_compose(tokens: list[str]) -> bool:
    """True if some compose occurrence in `tokens` has no -p/--project-name."""
    found_unpinned = False
    for i, tok in enumerate(tokens):
        base = tok.replace("\\", "/").rsplit("/", 1)[-1]
        start: int | None = None
        if base in ("docker-compose", "docker-compose.exe"):
            start = i + 1
        elif base in ("docker", "docker.exe"):
            j = i + 1
            while j < len(tokens) and tokens[j].startswith("-"):
                j += 2 if tokens[j] in _DOCKER_VALUE_OPTS else 1
            if j < len(tokens) and tokens[j] == "compose":
                start = j + 1
        if start is None:
            continue
        pinned = False
        j = start
        while j < len(tokens):
            t = tokens[j]
            if t in ("-p", "--project-name") or t.startswith("--project-name=") or (
                t.startswith("-p") and len(t) > 2 and not t.startswith("--")
            ):
                pinned = True
                j += 1 if "=" in t or (t.startswith("-p") and len(t) > 2 and not t.startswith("--")) else 2
                continue
            if t in _COMPOSE_VALUE_OPTS:
                j += 2
                continue
            if t.startswith("-"):
                j += 1
                continue
            break
        if not pinned:
            found_unpinned = True
    # A string that says "docker compose" but did not tokenise into an
    # occurrence (odd quoting, f-string placeholders) is still unpinned
    # unless it visibly carries a project flag.
    if not found_unpinned:
        joined = " ".join(tokens)
        # `docker-compose.yml` is a filename, not the command.
        if _COMPOSE_MENTION.search(joined) and not any(
            t in ("-p", "--project-name") or t.startswith("--project-name=") for t in tokens
        ):
            found_unpinned = True
    return found_unpinned


def scan_source(source: str, filename: str = "<memory>") -> list[tuple[int, str | None, str]]:
    """Return (line, enclosing function name, snippet) for each offending spawn."""
    tree = ast.parse(source, filename=filename)
    scanner = _Scanner(tree)
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _func_name(node)
        if name not in SPAWN_ATTRS:
            continue
        if name in _VARARGS_SPAWNS:
            exprs = list(node.args)
        else:
            exprs = node.args[:1] or [kw.value for kw in node.keywords if kw.arg in ("args", "cmd", "command")]
        if not exprs:
            continue
        strings: list[str] = []
        uses_helper = False
        for expr in exprs:
            more, helper = scanner.resolve(expr, node)
            strings.extend(more)
            uses_helper = uses_helper or helper
        if uses_helper:
            continue
        tokens = _tokens(strings)
        if _unpinned_compose(tokens):
            fn = scanner.enclosing_function(node)
            findings.append((node.lineno, getattr(fn, "name", None), " ".join(tokens)[:120]))
    return findings


def _scan_tree() -> tuple[int, list[tuple[str, int, str | None, str]]]:
    files = sorted(TESTS_ROOT.rglob("*.py"))
    out = []
    for path in files:
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(TESTS_ROOT).as_posix()
        for line, fn, snippet in scan_source(path.read_text(encoding="utf-8", errors="replace"), rel):
            out.append((rel, line, fn, snippet))
    return len(files), out


# ---------------------------------------------------------------------------
# The real corpus
# ---------------------------------------------------------------------------
def test_no_test_spawns_an_unpinned_compose_command():
    n_files, findings = _scan_tree()
    # An empty scan passes vacuously; make sure the corpus was actually read.
    assert n_files > 100, f"scanned only {n_files} files under {TESTS_ROOT}"
    offenders = [f for f in findings if (f[0], f[2]) not in ALLOWLIST]
    assert not offenders, (
        f"scanned {n_files} files; spawn calls that run `docker compose` without "
        "compose_argv(...) or -p/--project-name in argv (see the incident note in "
        "this file's docstring):\n" + "\n".join(f"  {r}:{ln} in {fn}: {snip}" for r, ln, fn, snip in offenders)
    )


def test_allowlist_is_not_stale():
    _, findings = _scan_tree()
    hit = {(f[0], f[2]) for f in findings}
    assert ALLOWLIST <= hit, f"allowlist entries that no longer match a finding: {sorted(ALLOWLIST - hit)}"


# ---------------------------------------------------------------------------
# Synthetic controls (written to a temp file and parsed; never executed)
# ---------------------------------------------------------------------------
FLAGGED = {
    "bare_list": 'import subprocess\nsubprocess.run(["docker", "compose", "down"])\n',
    "bare_string_shell": 'import subprocess\nsubprocess.run("docker compose down", shell=True)\n',
    "os_system": 'import os\nos.system("cd pmoves && docker compose down")\n',
    "legacy_binary": 'import subprocess\nsubprocess.check_call(["docker-compose", "stop"])\n',
    "via_local_var": (
        "import subprocess\n"
        "def f():\n"
        '    cmd = ["docker", "compose", "up", "-d"]\n'
        "    subprocess.Popen(cmd, cwd='pmoves')\n"
    ),
    "keyword_args": 'import subprocess\nsubprocess.run(args=["docker", "compose", "down"])\n',
    "env_var_is_not_a_pin": (
        "import subprocess, os\n"
        'subprocess.run(["docker", "compose", "down"], env={**os.environ, "COMPOSE_PROJECT_NAME": "x"})\n'
    ),
    "p_after_subcommand_is_not_global": 'import subprocess\nsubprocess.run(["docker", "compose", "exec", "db", "psql", "-p", "5432"])\n',
    "bare_import_run": 'from subprocess import run\nrun(["docker", "compose", "down"])\n',
}

CLEAN = {
    "compose_argv_helper": "import subprocess\nsubprocess.run(compose_argv(project, 'down'), cwd='pmoves')\n",
    "pinned_list": 'import subprocess\nsubprocess.run(["docker", "compose", "-p", "pmoves-test-0123abcd", "down"])\n',
    "pinned_long": 'import subprocess\nsubprocess.run(["docker", "compose", "--project-name=pmoves-test-0123abcd", "ps"])\n',
    "plain_docker": 'import subprocess\nsubprocess.run(["docker", "ps", "--format", "{{.Names}}"])\n',
    "not_a_spawn": 'text = "docker compose down"\nprint(text)\n',
    "compose_file_name_only": 'import subprocess\nsubprocess.run(["yq", ".services", "pmoves/docker-compose.yml"])\n',
    "mocked_in_patch_target": 'patch("x.subprocess.run", return_value=None)\n',
}


@pytest.mark.parametrize("name", sorted(FLAGGED))
def test_synthetic_positive_control_is_flagged(tmp_path, name):
    path = tmp_path / f"test_{name}.py"
    path.write_text(FLAGGED[name], encoding="utf-8")
    findings = scan_source(path.read_text(encoding="utf-8"), str(path))
    assert findings, f"checker missed a bare compose spawn ({name}):\n{FLAGGED[name]}"


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_synthetic_negative_control_is_clean(tmp_path, name):
    path = tmp_path / f"test_{name}.py"
    path.write_text(CLEAN[name], encoding="utf-8")
    assert scan_source(path.read_text(encoding="utf-8"), str(path)) == []
