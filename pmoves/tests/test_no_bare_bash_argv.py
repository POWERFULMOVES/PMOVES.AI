"""Ratchet: no repo Python may spawn a bare ``"bash"`` / ``"sh"`` as argv[0].

On Windows a bare ``"bash"`` handed to CreateProcess resolves to
``C:\\Windows\\System32\\bash.exe`` -- the WSL launcher -- before PATH is ever
consulted, so the child silently runs in a different OS (see
``pmoves/tools/bash_resolver.py`` for the measurement). Every subprocess that
starts bash must take argv[0] from ``resolve_bash()`` (tools / tests) or be
code that only ever runs inside a Linux container (listed in ``EXEMPT``, each
with the reason it can never execute on a Windows host).

The scanner is AST-based. It flags, inside a call to a process-spawning
function (subprocess.run/call/check_call/check_output/Popen,
asyncio.create_subprocess_exec/_shell, os.system/popen, os.exec*/spawn*):

* a list/tuple first argument whose first element is a literal bash/sh name;
* the same with argv[0] taken from ``shutil.which("bash"/"sh")`` -- directly,
  via a variable (``BASH = shutil.which("bash")``, ``... or which("bash.exe")``)
  or via a module-local helper that returns it (``def _bash(): ...``). With the
  registry PATH a PowerShell / cmd / VS Code session gets on Windows, ``which``
  returns ``C:\\Windows\\system32\\bash.EXE`` -- the same WSL stub. Use
  ``find_bash()`` (absolute path or None) for "skip if no bash" callers;
* ``["bash", ...] + rest`` concatenations;
* a Name first argument that the enclosing scope assigned such a list to
  (``cmd = ["bash", "-lc", ...]; subprocess.run(cmd)`` -- the mini_cli shape);
* a string command (``shell=True`` / os.system / create_subprocess_shell)
  whose text starts with ``bash `` / ``sh ``.

``test_scanner_flags_the_pre_fix_shapes`` is the positive control: it feeds the
scanner the exact pre-fix lines from mini_cli.py and crush_configurator.py so
this ratchet can never pass by flagging nothing.
"""

from __future__ import annotations

import ast
import re
import subprocess
import warnings
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SHELL_NAMES = {"bash", "sh", "bash.exe", "sh.exe"}

# Spawners whose first positional argument is the argv (or command string).
_ARGV_FUNCS = {"run", "call", "check_call", "check_output", "Popen", "create_subprocess_exec"}
_STRING_FUNCS = {"system", "popen", "create_subprocess_shell", "getoutput", "getstatusoutput"}
# os.exec*/spawn*: first argument is the program (spawn*: second, after mode).
_EXEC_FUNCS = {"execv", "execve", "execvp", "execvpe", "execl", "execle", "execlp", "execlpe"}
_SPAWN_FUNCS = {"spawnv", "spawnve", "spawnvp", "spawnvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe"}
_SPAWNER_MODULES = {"subprocess", "asyncio", "os"}

# Files that only ever execute inside a Linux container, so the Windows WSL-stub
# lookup cannot occur. Path -> reason. Keep this list short and justified.
EXEMPT: Dict[str, str] = {
    "pmoves/data/agent-zero/instruments/default/claude_code/instrument.py":
        "Agent Zero instrument: mounted into and executed by the A0 Linux container only",
}

_TEXTUAL_SPAWN = re.compile(
    r"""(subprocess\.\w+|Popen|create_subprocess_\w+|os\.system)\(\s*[\[(]?\s*f?['"](ba)?sh(\.exe)?['"\s]"""
)

_SKIP_PREFIXES = (".claude/worktrees/",)
_SKIP_PARTS = ("/node_modules/", "/.venv/", "/venv/", "/site-packages/")


def _shell_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in SHELL_NAMES


def _string_text(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values:
        head = node.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
    return None


def _starts_with_shell(text: str) -> bool:
    first = text.lstrip().split(None, 1)
    return bool(first) and first[0] in SHELL_NAMES and len(text.lstrip()) > len(first[0])


def _callee_name(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _Scanner(ast.NodeVisitor):
    def __init__(self, indirect: bool = False) -> None:
        self.indirect = indirect
        self.hits: List[Tuple[int, str, str]] = []
        self.aliases: Dict[str, str] = {}  # local name -> module ("sp" -> "subprocess")
        self.from_imports: Dict[str, str] = {}  # local name -> "subprocess.run"
        self._scopes: List[Dict[str, ast.AST]] = [{}]
        # Names of functions/methods defined in this module that themselves
        # spawn a process: `run(cmd, shell=True)` helpers, `self._run_command`.
        self.wrappers: set = set()
        # Names of module-local functions that return shutil.which("bash").
        self.which_funcs: set = set()

    def prepare(self, tree: ast.AST) -> None:
        """Pre-pass: imports first (they may sit below a helper), then wrappers."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.visit_Import(node)
            elif isinstance(node, ast.ImportFrom):
                self.visit_ImportFrom(node)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(
                    isinstance(c, ast.Call) and self._spawner(c.func)
                    for c in ast.walk(node)
                ):
                    self.wrappers.add(node.name)
        # Module-level names first, so a function visited before a later
        # `BASH = shutil.which("bash")` still resolves it.
        if isinstance(tree, ast.Module):
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        self._record_assign(t, stmt.value)
                elif isinstance(stmt, ast.AnnAssign):
                    self._record_assign(stmt.target, stmt.value)
        # Local helpers that hand back shutil.which("bash"): `def _bash(): ...`
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(self._is_which_call(c) for c in ast.walk(node)):
                    self.which_funcs.add(node.name)

    # -- argv[0] classification ----------------------------------------------
    @staticmethod
    def _is_which_call(node: ast.AST) -> bool:
        """``shutil.which("bash")`` / ``which("sh")`` -- on Windows that can be
        ``C:\\Windows\\system32\\bash.EXE``, the WSL stub."""
        return (
            isinstance(node, ast.Call)
            and _callee_name(node.func) == "which"
            and bool(node.args)
            and _shell_literal(node.args[0])
        )

    def _is_which_sourced(self, node: Optional[ast.AST], depth: int = 0) -> bool:
        if node is None or depth > 5:
            return False
        if self._is_which_call(node):
            return True
        if isinstance(node, ast.BoolOp):
            return any(self._is_which_sourced(v, depth + 1) for v in node.values)
        if isinstance(node, ast.Name):
            return self._is_which_sourced(self._lookup(node.id), depth + 1)
        if isinstance(node, ast.Call) and not node.args:
            return _callee_name(node.func) in self.which_funcs
        return False

    def _argv_kind(self, node: Optional[ast.AST]) -> Optional[str]:
        """'argv' for a literal bash/sh argv[0], 'which' for one taken from
        shutil.which, else None."""
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            head = node.elts[0]
            if _shell_literal(head):
                return "argv"
            if self._is_which_sourced(head):
                return "which"
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._argv_kind(node.left)
        return None

    # -- import tracking ---------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            root = a.name.split(".")[0]
            if root in _SPAWNER_MODULES:
                self.aliases[a.asname or root] = root

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in _SPAWNER_MODULES:
            for a in node.names:
                self.from_imports[a.asname or a.name] = f"{node.module}.{a.name}"

    # -- scope tracking for `cmd = [...]` ----------------------------------
    def _visit_scope(self, node: ast.AST) -> None:
        self._scopes.append({})
        self.generic_visit(node)
        self._scopes.pop()

    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope
    visit_Lambda = _visit_scope

    def _record_assign(self, target: ast.AST, value: Optional[ast.AST]) -> None:
        if isinstance(target, ast.Name) and value is not None:
            self._scopes[-1][target.id] = value

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            self._record_assign(t, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record_assign(node.target, node.value)
        self.generic_visit(node)

    def _lookup(self, name: str) -> Optional[ast.AST]:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    # -- calls ---------------------------------------------------------------
    def _spawner(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            mod = self.aliases.get(func.value.id)
            if mod:
                return func.attr
        if isinstance(func, ast.Name) and func.id in self.from_imports:
            return self.from_imports[func.id].split(".", 1)[1]
        return None

    def visit_Call(self, node: ast.Call) -> None:
        fn = self._spawner(node.func)
        if fn:
            self._check(node, fn)
        elif node.args and not isinstance(node.args[0], ast.Starred):
            callee = _callee_name(node.func)
            is_wrapper = callee is not None and callee in self.wrappers
            if is_wrapper or self.indirect:
                arg = node.args[0]
                resolved = self._lookup(arg.id) if isinstance(arg, ast.Name) else arg
                text = _string_text(resolved) if resolved is not None else None
                if self._argv_kind(resolved) or (
                    text is not None and _starts_with_shell(text)
                ):
                    self._hit(node, "wrapper" if is_wrapper else "indirect")
        self.generic_visit(node)

    def _first_arg(self, node: ast.Call, index: int = 0) -> Optional[ast.AST]:
        if len(node.args) > index and not isinstance(node.args[index], ast.Starred):
            return node.args[index]
        for kw in node.keywords:
            if kw.arg in ("args", "cmd", "program", "file", "path"):
                return kw.value
        return None

    def _check(self, node: ast.Call, fn: str) -> None:
        if fn in _EXEC_FUNCS or fn in _SPAWN_FUNCS:
            arg = self._first_arg(node, 1 if fn in _SPAWN_FUNCS else 0)
            if arg is not None and _shell_literal(arg):
                self._hit(node, "exec")
            return
        if fn == "create_subprocess_exec":
            if node.args and _shell_literal(node.args[0]):
                self._hit(node, "argv")
            return
        arg = self._first_arg(node)
        if arg is None:
            return
        if fn in _ARGV_FUNCS:
            resolved = self._lookup(arg.id) if isinstance(arg, ast.Name) else arg
            kind = self._argv_kind(resolved)
            if kind:
                self._hit(node, kind if resolved is arg else f"{kind}-var")
                return
        if fn in _ARGV_FUNCS or fn in _STRING_FUNCS:
            text = _string_text(arg)
            if text is None and isinstance(arg, ast.Name):
                text = _string_text(self._lookup(arg.id) or ast.Constant(None))
            if text is not None and _starts_with_shell(text):
                self._hit(node, "shell-string")

    def _hit(self, node: ast.Call, kind: str) -> None:
        self.hits.append((node.lineno, kind, ast.unparse(node)[:160]))


def scan_source(
    source: str, filename: str = "<src>", *, indirect: bool = False
) -> List[Tuple[int, str, str]]:
    """Return (line, kind, snippet) for every bare-shell spawn in *source*.

    Calls to a function defined in the same module that itself spawns a
    process (a ``run(cmd, shell=True)`` helper, ``self._run_command``) are
    checked like the spawner itself (kind ``wrapper``).

    ``indirect=True`` additionally reports bare-shell argv / shell strings
    handed to ANY call. That mode is an audit aid, not part of the ratchet: it
    cannot tell a wrapper imported from elsewhere from a guard test that passes
    ``["bash", "-c", ...]`` as data, or from ``pytest.skip("bash not ...")``.
    """
    with warnings.catch_warnings():  # invalid-escape noise from scanned files
        warnings.simplefilter("ignore")
        tree = ast.parse(source, filename=filename)
    s = _Scanner(indirect=indirect)
    s.prepare(tree)
    s.visit(tree)
    return sorted(s.hits)


def _repo_python_files() -> Iterator[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    for rel in out.split("\0"):
        if not rel or rel.startswith(_SKIP_PREFIXES) or any(p in f"/{rel}" for p in _SKIP_PARTS):
            continue
        yield rel


# ---------------------------------------------------------------------------
# Positive control -- the ratchet is only meaningful if it catches these.
# ---------------------------------------------------------------------------

PRE_FIX_MINI_CLI = '''
import subprocess
import warnings
def tailscale_join(env_file, script, env):
    cmd = ["bash", "-lc", f". ./pmoves/scripts/with-env.sh '{env_file}'; bash '{script}'"]
    rc = subprocess.run(cmd, cwd=".", env=env).returncode
'''

PRE_FIX_CRUSH = '''
import subprocess
import warnings
def resolve(cmd, env):
    proc = subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, timeout=30,
        env={k: v for k, v in env.items() if k != "PMOVES_PYTHON"},
    )
'''


# Pre-fix shapes of the shutil.which("bash") callers (review of PR #3266):
# test_claude_pmoves_roster_fallback.py:42/224 (module constant),
# test_mavis_sdk_env.py:36/46 (`or` chain in a local),
# test_launcher_prompt_accumulation.py:74 (helper returning which()).
PRE_FIX_WHICH_CONSTANT = '''
import shutil, subprocess
BASH = shutil.which("bash")
class T:
    def run(self):
        subprocess.run([BASH, str(self.launcher), "--some-arg"], capture_output=True)
'''

PRE_FIX_WHICH_OR_CHAIN = '''
import shutil, subprocess
def test_bash_runner_all_pass():
    bash = shutil.which("bash") or shutil.which("bash.exe")
    result = subprocess.run([bash, runner_arg], capture_output=True)
'''

PRE_FIX_WHICH_HELPER = '''
import shutil, subprocess
def _bash() -> str:
    found = shutil.which("bash")
    if not found:
        pytest.skip("bash not available")
    return found
def _run(launcher):
    return subprocess.run([_bash(), str(launcher)], capture_output=True)
'''


def test_scanner_flags_the_pre_fix_shapes() -> None:
    assert [k for _, k, _ in scan_source(PRE_FIX_MINI_CLI)] == ["argv-var"]
    assert [k for _, k, _ in scan_source(PRE_FIX_CRUSH)] == ["argv"]
    assert [k for _, k, _ in scan_source(PRE_FIX_WHICH_CONSTANT)] == ["which"]
    assert [k for _, k, _ in scan_source(PRE_FIX_WHICH_OR_CHAIN)] == ["which"]
    assert [k for _, k, _ in scan_source(PRE_FIX_WHICH_HELPER)] == ["which"]


def test_find_bash_forms_are_not_flagged() -> None:
    """The post-fix shapes of the three which() callers above."""
    for src in (PRE_FIX_WHICH_CONSTANT, PRE_FIX_WHICH_OR_CHAIN, PRE_FIX_WHICH_HELPER):
        fixed = (
            src.replace('shutil.which("bash") or shutil.which("bash.exe")', "find_bash()")
            .replace('shutil.which("bash")', "find_bash()")
        )
        assert scan_source(fixed) == [], fixed


@pytest.mark.parametrize(
    "src",
    [
        "import subprocess as sp\nsp.Popen(('sh', '-c', 'x'))",
        "from subprocess import check_output\ncheck_output(['bash.exe', 'x'])",
        "import subprocess\nsubprocess.run('bash -c \"uname\"', shell=True)",
        "import subprocess\nsubprocess.run(['bash'] + rest)",
        "import os\nos.system(f'bash {script}')",
        "import os\nos.execvp('bash', ['bash', '-c', 'x'])",
        "import asyncio\nasync def f():\n    await asyncio.create_subprocess_exec('bash', '-c', 'x')",
        "import asyncio\nasync def f():\n    await asyncio.create_subprocess_shell('sh ./x.sh')",
        # a module-local wrapper that spawns (bootstrap-supabase-stack.py's run())
        "import subprocess\ndef run(cmd):\n    subprocess.run(cmd, shell=True)\nrun('bash scripts/x.sh')",
        "import subprocess\nclass I:\n    def _run_command(self, cmd):\n        subprocess.run(cmd)\n"
        "    def go(self):\n        cmd = ['bash', 'x.sh']\n        self._run_command(cmd)",
        # argv[0] from shutil.which: direct, `sh`, and via `cmd = [...]`
        "import shutil, subprocess\nsubprocess.run([shutil.which('bash'), '-c', 'x'])",
        "import shutil, subprocess\nSH = shutil.which('sh')\nsubprocess.check_call([SH, 'x.sh'])",
        "import shutil, subprocess\ndef f():\n    b = shutil.which('bash')\n    cmd = [b, 'x']\n    subprocess.run(cmd)",
    ],
)
def test_scanner_flags_other_spawn_forms(src: str) -> None:
    assert scan_source(src), src


@pytest.mark.parametrize(
    "src",
    [
        # resolved argv[0] -- the sanctioned form
        "import subprocess\nsubprocess.run([resolve_bash(), '-c', 'x'])",
        "import subprocess\nBASH = find_bash()\nsubprocess.run([BASH, '-c', 'x'])",
        # which() of something that is not a shell is fine
        "import shutil, subprocess\nGIT = shutil.which('git')\nsubprocess.run([GIT, 'status'])",
        # "bash" as data, not as a spawn
        "x = ['bash', '-c', 'docker compose down']",
        "allowed = ['bash', 'ls', 'view']",
        # a local helper named run() is not subprocess.run
        "def run(*a): pass\nrun(root, 'bash', payload)",
        # bash as a later argument is fine (e.g. wsl.exe bash, env bash)
        "import subprocess\nsubprocess.run(['git', 'bash'])",
        # a word that merely starts with 'sh'
        "import os\nos.system('shasum x')",
        # prose starting with "bash" handed to a call that does not spawn
        "import pytest, subprocess\npytest.skip('bash not available')",
    ],
)
def test_scanner_ignores_non_spawns(src: str) -> None:
    assert scan_source(src) == [], src


# ---------------------------------------------------------------------------
# The ratchet itself.
# ---------------------------------------------------------------------------

def test_no_repo_python_spawns_a_bare_bash() -> None:
    offenders: List[str] = []
    scanned = 0
    for rel in _repo_python_files():
        if rel in EXEMPT:
            continue
        path = REPO_ROOT / rel
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            hits = scan_source(source, rel)
        except SyntaxError:
            # Not parseable by this interpreter (PEP 695 syntax under 3.11, or
            # a notebook export with `!pip` lines). Do not let that become a
            # blind spot: fall back to a textual check.
            if _TEXTUAL_SPAWN.search(source):
                offenders.append(f"{rel}: unparseable here and textually spawns a bare shell")
            continue
        scanned += 1
        offenders += [f"{rel}:{line}: [{kind}] {snippet}" for line, kind, snippet in hits]
    assert scanned > 500, f"scanner saw only {scanned} files -- the ratchet would be vacuous"
    assert not offenders, (
        "Bare bash/sh as argv[0] runs the WSL stub on Windows (System32\\bash.exe "
        "is searched before PATH). Use pmoves.tools.bash_resolver.resolve_bash(), "
        "or add the file to EXEMPT with the reason it only runs in a Linux "
        "container:\n  " + "\n  ".join(offenders)
    )


def test_exemptions_still_exist() -> None:
    for rel in EXEMPT:
        assert (REPO_ROOT / rel).is_file(), f"stale EXEMPT entry: {rel}"
