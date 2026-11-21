"""Fleet ratchet: no MODULE-SCOPE POSIX-only `os.*` call may exist in this repo.

WHY THIS FILE EXISTS
--------------------
Windows has NO POSIX uid/gid and NO POSIX-only file calls: the `os` module
there has no `geteuid`, `getegid`, `getuid`, `getgid`, `fchmod`, `fchown`,
`chown`, `setuid` or `setgid` (measured on the operator's host:
`os.fchown: False, os.chown: False, os.geteuid: False, os.getuid: False,
os.fchmod: False`).

A POSIX-only `os.*` call at MODULE SCOPE -- in a decorator argument, a default
value, a class body, or plain top-level code -- is evaluated at IMPORT time.
On Windows that does not fail one test: it fails the COLLECTION of the whole
file, so 0 tests in it run. Two test files were silently absent from every
Windows host that way (71 tests).

THE HOUSE PATTERN
-----------------
    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, ...)
The `hasattr` SHORT-CIRCUITS, so the attribute is never touched when it is
absent. See pmoves/tests/test_secrets_funnel_producers.py:126 and
pmoves/tests/tools/test_lgtm_marker_check.py:215.

WHAT THIS FILE ASSERTS
----------------------
1. no UNGUARDED module-scope POSIX-only `os.*` call under pmoves/tests/ (and
   under the rest of the pmoves tree -- same class of import-time bomb);
2. module scope is decided with `ast`, never with line numbers: a call
   inside a function (or a nested one) is FUNCTION scope;
3. POSITIVE: the guard pattern is PRESENT where it is needed -- every
   module-scope reference is wrapped in a `hasattr`/`sys.platform` guard, and
   the fleet really does carry guarded references (so the rule is not
   vacuous);
4. NEGATIVE CONTROL: the scanner FLAGS a synthetic module-scope POSIX call,
   and does NOT flag the same call inside a function -- so the scanner is
   demonstrably not vacuous either;
5. pmoves/tools/env_local_key.py is Windows-safe: structurally (every
   POSIX-only `os.*` reference is guarded) AND behaviourally (run as a
   subprocess, it exits with a documented code and never prints a raw
   traceback).

WHAT COUNTS AS A GUARD
----------------------
A guard must belong to an ANCESTOR of the reference -- the `if
hasattr(os, "fchmod"):` block that encloses it, or the `hasattr(os,
"geteuid") and os.geteuid() == 0` short-circuit inside its own
expression. The walk stops BEFORE the `ast.Module` node, whose subtree is
the WHOLE FILE: crediting that would turn the check into a "has this file
ever heard of `hasattr`" check and issue the bomb a hall pass whenever a
legitimate guard lived somewhere else in the same file.

WHAT COUNTS AS MODULE SCOPE
---------------------------
Module-level code, class bodies, decorator arguments, defaults and
annotations are evaluated at IMPORT time. So is an EAGER comprehension
(`ListComp`/`SetComp`/`DictComp`): a module-level `[os.geteuid() for _ in
range(1)]` is evaluated while the module is imported. A generator
expression is LAZY -- its body runs when the generator is ITERATED -- so
its body is function scope; only its FIRST generator's iterable is
evaluated eagerly, in the enclosing scope.

Hermetic: no network, no docker, no NATS, no gh. It reads files in this
repo and runs the tool against pytest's tmp_path.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[2]
TOOL = PMOVES / "tools" / "env_local_key.py"
TESTS = PMOVES / "tests"

# The os attributes that do not exist on Windows.
POSIX_ONLY = frozenset({
    "geteuid", "getegid", "getuid", "getgid",
    "fchmod", "fchown", "chown", "setuid", "setgid",
})

# Directories that hold no importable module of this project.
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              "site-packages", ".mypy_cache", ".pytest_cache"}

# The platform strings a `sys.platform` guard may compare against.
_PLATFORM_LITERALS = {"win32", "windows", "linux", "linux2", "darwin", "cygwin"}


# ------------------------------------------------------------------ scanner ---

class _Hit:
    """One POSIX-only `os.*` reference, with the scope it was found in."""

    def __init__(self, path: str, lineno: int, attr: str, scope: str,
                 node: ast.AST):
        self.path = path
        self.lineno = lineno
        self.attr = attr
        self.scope = scope            # "module" | "function"
        self.guard: str | None = None  # "hasattr" | "getattr" | "platform"
        self.node = node

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (f"<{self.path}:{self.lineno} os.{self.attr} "
                f"scope={self.scope} guard={self.guard}>")


class _ScopeVisitor(ast.NodeVisitor):
    """Walk a module and record where each POSIX-only `os.*` reference LIVES.

    The scope rules are the ones Python actually uses:

    * module-level code, class bodies, and the decorators / defaults /
      annotations of a definition are evaluated at IMPORT time;
    * a function body (including a nested one) runs at CALL time.

    So `os.geteuid()` inside a `skipif` argument is a MODULE-scope call
    (import time -> collection bomb), while the same call inside `def` is
    FUNCTION scope (call time -> one failing test at worst).
    """

    def __init__(self) -> None:
        self.scope = "module"
        self.found: list[tuple[ast.AST, str, str]] = []

    # -- expressions --
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (isinstance(node.value, ast.Name) and node.value.id == "os"
                and node.attr in POSIX_ONLY):
            self.found.append((node, node.attr, self.scope))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # `from os import geteuid` -> a bare `geteuid()` call.
        if isinstance(node.func, ast.Name) and node.func.id in POSIX_ONLY:
            self.found.append((node, node.func.id, self.scope))
        self.generic_visit(node)

    # -- definitions --
    def _visit_definition_extras(self, node) -> None:
        """Decorators, defaults and annotations are evaluated in the
        ENCLOSING scope when the def/class statement runs."""
        for dec in node.decorator_list:
            self.visit(dec)
        args = node.args
        for default in list(args.defaults) + [d for d in args.kw_defaults
                                              if d is not None]:
            self.visit(default)
        for arg in (list(args.args) + list(args.kwonlyargs)
                    + [args.vararg, args.kwarg]):
            if arg is not None and arg.annotation is not None:
                self.visit(arg.annotation)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_FunctionDef(self, node) -> None:
        self._visit_definition_extras(node)
        outer = self.scope
        self.scope = "function"
        for stmt in node.body:
            self.visit(stmt)
        self.scope = outer

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node) -> None:
        for dec in node.decorator_list:
            self.visit(dec)
        for base in node.bases:
            self.visit(base)
        for kw in node.keywords:
            self.visit(kw.value)
        # The class BODY runs at class-creation time: still import time for a
        # module-level class, so the scope is left as it is.
        for stmt in node.body:
            self.visit(stmt)

    def visit_Lambda(self, node) -> None:
        for default in list(node.args.defaults) + [d for d in node.args.kw_defaults
                                                   if d is not None]:
            self.visit(default)
        outer = self.scope
        self.scope = "function"
        self.visit(node.body)
        self.scope = outer

    def _visit_comprehension(self, node) -> None:
        """Comprehension scopes: EAGER bodies are evaluated WHERE the
        comprehension is written, LAZY bodies are not.

        A list/set/dict comprehension is EAGER: its elements are built
        when the comprehension expression is evaluated. So a module-level
        `[os.geteuid() for _ in range(1)]` raises AttributeError at IMPORT
        time -- precisely the collection bomb this ratchet exists to
        catch -- and its elements must therefore be classified at the
        comprehension's OWN scope (module scope at module level).

        A generator expression is LAZY: its body runs when the generator is
        ITERATED, not when the expression is evaluated. Its body is
        function scope. The ONE eager part is the FIRST generator's
        iterable, which Python evaluates in the ENCLOSING scope when the
        generator expression is evaluated -- that part keeps the
        enclosing scope.
        """
        outer = self.scope
        lazy = isinstance(node, ast.GeneratorExp)
        # EAGER: the body runs with the enclosing scope's timing.
        # LAZY : the body runs at iteration time -> function scope.
        body_scope = "function" if lazy else outer
        for i, gen in enumerate(node.generators):
            # The OUTERMOST iterable is evaluated EAGERLY, in the
            # ENCLOSING scope, for every comprehension kind.
            # Inner iterables follow the body's timing.
            self.scope = outer if i == 0 else body_scope
            self.visit(gen.iter)
            self.scope = body_scope
            self.visit(gen.target)
            for cond in gen.ifs:
                self.visit(cond)
        self.scope = body_scope
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scope = outer

    visit_ListComp = visit_SetComp = visit_GeneratorExp = _visit_comprehension

    def visit_DictComp(self, node) -> None:
        self._visit_comprehension(node)


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _hasattr_guard(node: ast.AST, attr: str) -> bool:
    """True if the subtree contains `hasattr(os, attr)` / `getattr(os, attr, ...)`."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Name):
            continue
        if sub.func.id not in ("hasattr", "getattr"):
            continue
        if len(sub.args) < 2:
            continue
        first, second = sub.args[0], sub.args[1]
        if (isinstance(first, ast.Name) and first.id == "os"
                and isinstance(second, ast.Constant) and second.value == attr):
            return True
    return False


def _platform_guard(node: ast.AST) -> bool:
    """True if the subtree compares `sys.platform` against a known platform."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Compare):
            continue
        operands = [sub.left, *sub.comparators]
        for operand in operands:
            if (isinstance(operand, ast.Attribute)
                    and isinstance(operand.value, ast.Name)
                    and operand.value.id == "sys" and operand.attr == "platform"):
                for other in operands:
                    if (isinstance(other, ast.Constant)
                            and other.value in _PLATFORM_LITERALS):
                        return True
    return False


def _guard_kind(node: ast.AST, attr: str, parents: dict[ast.AST, ast.AST]) -> str | None:
    """Which guard (if any) protects this reference.

    ONLY AN ANCESTOR THAT CAN ACTUALLY PROTECT THE REFERENCE COUNTS.

    The walk stops BEFORE `ast.Module`. The Module node's subtree is the
    WHOLE FILE, so crediting it turns the guard check into a "has this
    file ever heard of `hasattr`" check: an unguarded module-scope
    `os.geteuid()` anywhere in the file would be stamped `guard="hasattr"`
    because some UNRELATED part of that file mentions `hasattr(os, ...)`.
    That is a hall pass for the exact defect this ratchet exists to
    catch -- the ratchet would issue the bomb a pass whenever a
    legitimate guard lives somewhere else in the building.

    What still counts is an ancestor that really can protect the
    reference:

    * an `if hasattr(os, "fchmod"):` node -- the `If` node's subtree
      includes its own `test`, so the `hasattr` call is still found;
    * the `hasattr(os, "geteuid") and os.geteuid() == 0` `BoolOp` -- the
      `hasattr` call is a sibling inside the same expression;
    * a `sys.platform` comparison in the same subtree.

    A module-level call has no such ancestor and correctly ends up
    UNGUARDED.
    """
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Module):
            # The whole file is NOT a guard. Stop before it.
            break
        if _hasattr_guard(current, attr):
            return "hasattr"
        if _platform_guard(current):
            return "platform"
    return None


def scan_source(source: str, path: str = "<snippet>") -> list[_Hit]:
    """Scan source text and return every POSIX-only `os.*` reference."""
    tree = ast.parse(source)
    visitor = _ScopeVisitor()
    visitor.visit(tree)
    parents = _parent_map(tree)
    hits: list[_Hit] = []
    for node, attr, scope in visitor.found:
        hit = _Hit(path, getattr(node, "lineno", 0), attr, scope, node)
        hit.guard = _guard_kind(node, attr, parents)
        hits.append(hit)
    return hits


def scan_file(path: Path) -> list[_Hit]:
    """Scan a file. Unparseable files (docs notebooks, mostly) yield no hits."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        return scan_source(source, str(path))
    except SyntaxError:
        return []


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        yield path


def module_scope_hits(root: Path) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in iter_python_files(root):
        hits.extend(h for h in scan_file(path) if h.scope == "module")
    return hits


def _describe(hits: list[_Hit]) -> str:
    return "\n".join(f"  {h.path}:{h.lineno}: os.{h.attr} (guard={h.guard})"
                     for h in hits) or "  (none)"


# ------------------------------------------------------------------- tests ---

def test_no_unguarded_module_scope_posix_only_call_under_pmoves_tests():
    """The collection-bomb rule: under pmoves/tests/ every module-scope
    POSIX-only `os.*` reference must be wrapped in a guard."""
    hits = module_scope_hits(TESTS)
    unguarded = [h for h in hits if h.guard is None]
    assert unguarded == [], (
        "module-scope POSIX-only os.* calls under pmoves/tests/ are import-time "
        "collection bombs on Windows (no os.geteuid/os.fchmod/... there):\n"
        + _describe(unguarded)
        + "\nGuard them the house way: "
          "@pytest.mark.skipif(hasattr(os, \"geteuid\") and os.geteuid() == 0, ...)")


def test_no_unguarded_module_scope_posix_only_call_anywhere_in_pmoves():
    """The same class, fleet-wide: a module-scope POSIX-only `os.*` call in
    ANY importable module crashes that module on Windows at import time."""
    hits = module_scope_hits(PMOVES)
    unguarded = [h for h in hits if h.guard is None]
    assert unguarded == [], (
        "module-scope POSIX-only os.* calls are import-time bombs on Windows:\n"
        + _describe(unguarded))


def test_every_module_scope_posix_only_reference_is_guarded():
    """POSITIVE assertion: the guard pattern is PRESENT where it is needed."""
    hits = module_scope_hits(TESTS)
    assert hits, "no module-scope POSIX-only reference found -- the rule is vacuous"
    for hit in hits:
        assert hit.guard is not None, f"{hit} is not guarded"
    kinds = {h.guard for h in hits}
    assert "hasattr" in kinds, (
        f"the house hasattr() guard is not exercised anywhere: {sorted(kinds)}")


def test_the_house_pattern_is_declared_in_the_known_files():
    """The files that already carry the pattern must keep carrying it."""
    lgtm = (TESTS / "tools" / "test_lgtm_marker_check.py").read_text(encoding="utf-8")
    assert 'hasattr(os, "geteuid")' in lgtm
    assert 'sys.platform == "win32"' in lgtm

    funnel = (TESTS / "test_secrets_funnel_producers.py").read_text(encoding="utf-8")
    assert 'hasattr(os, "geteuid")' in funnel
    assert "sys.platform" in funnel


def test_scanner_flags_a_module_scope_posix_call_in_a_decorator():
    """NEGATIVE CONTROL: the scanner must FLAG the defect it exists for."""
    source = (
        "import os\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.skipif(os.geteuid() == 0, reason=\"root\")\n"
        "def test_something():\n"
        "    assert True\n"
    )
    hits = [h for h in scan_source(source) if h.scope == "module"]
    assert len(hits) == 1, hits
    assert hits[0].attr == "geteuid"
    assert hits[0].guard is None
    assert hits[0].lineno == 4


def test_scanner_flags_a_module_scope_posix_call_in_a_class_body():
    """A class body runs at import time, so it is module scope too."""
    source = (
        "import os\n"
        "\n"
        "class Guard:\n"
        "    ROOT = os.geteuid() == 0\n"
    )
    hits = [h for h in scan_source(source) if h.scope == "module"]
    assert len(hits) == 1, hits
    assert hits[0].guard is None


def test_scanner_does_not_flag_a_posix_call_inside_a_function():
    """The other half of the negative control: FUNCTION scope is not a
    collection bomb, and the scanner must say so (scope by ast, not by
    line number)."""
    source = (
        "import os\n"
        "\n"
        "def helper():\n"
        "    return os.geteuid() == 0\n"
        "\n"
        "def outer():\n"
        "    def inner():\n"
        "        return os.geteuid() == 0\n"
        "    return inner()\n"
    )
    hits = scan_source(source)
    assert hits, "the scanner found nothing -- it is not looking"
    assert all(h.scope == "function" for h in hits), hits
    assert [h for h in hits if h.scope == "module"] == []


def test_scanner_accepts_the_house_guard_pattern():
    """The house pattern is GUARDED, so it must not be reported as a bomb."""
    source = (
        "import os\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.skipif(hasattr(os, \"geteuid\") and os.geteuid() == 0,\n"
        "                    reason=\"root\")\n"
        "def test_something():\n"
        "    assert True\n"
    )
    hits = [h for h in scan_source(source) if h.scope == "module"]
    assert len(hits) == 1, hits
    assert hits[0].guard == "hasattr"
    assert [h for h in hits if h.guard is None] == []


def test_scanner_accepts_a_sys_platform_guard():
    source = (
        "import os\n"
        "import sys\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.skipif(sys.platform == \"win32\", reason=\"POSIX mode bits\")\n"
        "@pytest.mark.skipif(os.geteuid() == 0, reason=\"root\")\n"
        "def test_something():\n"
        "    assert True\n"
    )
    hits = [h for h in scan_source(source) if h.scope == "module"]
    assert len(hits) == 1, hits
    assert hits[0].guard == "platform"


def test_scanner_does_not_credit_a_guard_that_lives_elsewhere_in_the_file():
    """A `hasattr(os, ...)` that lives ELSEWHERE in the file is not a guard.

    The ratchet exists to catch the collection bomb. If any `hasattr` in
    the file could vouch for any call in the file, the ratchet would issue
    the bomb a hall pass whenever a legitimate guard lived somewhere else
    in the building. So the guard must belong to an ANCESTOR of the call
    -- the `if hasattr(...)` block that encloses it, or the `and` inside
    its own expression -- and NOT to the file as a whole.

    Here the file carries a legitimate `hasattr(os, "geteuid")` in two
    unrelated places: a module-level constant and a helper function. The
    decorator argument below has NEITHER, so it must still be flagged.
    """
    source = (
        "import os\n"
        "import pytest\n"
        "\n"
        "HAS_UID = hasattr(os, \"geteuid\")\n"
        "\n"
        "\n"
        "def helper():\n"
        "    return HAS_UID\n"
        "\n"
        "\n"
        "@pytest.mark.skipif(os.geteuid() == 0, reason=\"root\")\n"
        "def test_something():\n"
        "    assert True\n"
    )
    hits = [h for h in scan_source(source) if h.scope == "module"]
    assert len(hits) == 1, hits
    assert hits[0].attr == "geteuid"
    assert hits[0].guard is None, (
        "an unrelated hasattr() elsewhere in the file must not guard this "
        f"call: {hits[0]}")


def test_scanner_credits_the_hasattr_block_that_encloses_the_call():
    """POSITIVE: the `if hasattr(os, ...):` guard shape credits the call it
    ENCLOSES -- the `hasattr` lives in the `If` node's own subtree, so the
    walk finds it without ever reaching the module."""
    source = (
        "import os\n"
        "\n"
        "def adapt(fd, mode):\n"
        "    if hasattr(os, \"fchmod\"):\n"
        "        os.fchmod(fd, mode)\n"
        "    else:\n"
        "        os.chmod(\"overlay.txt\", mode)\n"
    )
    hits = scan_source(source)
    assert len(hits) == 1, hits
    assert hits[0].attr == "fchmod"
    assert hits[0].guard == "hasattr"


def test_scanner_flags_a_module_level_eager_comprehension_as_module_scope():
    """An EAGER comprehension at module level runs AT IMPORT TIME.

    `[os.geteuid() for _ in range(1)]` at module level is evaluated while
    the module is imported, so on Windows it raises AttributeError before
    a single test in the file can run -- the same collection bomb as a
    decorator argument. It must be MODULE scope.
    """
    source = (
        "import os\n"
        "\n"
        "UIDS = [os.geteuid() for _ in range(1)]\n"
    )
    hits = scan_source(source)
    assert len(hits) == 1, hits
    assert hits[0].scope == "module"
    assert hits[0].attr == "geteuid"
    assert hits[0].guard is None


def test_scanner_keeps_a_generator_expression_lazy():
    """A generator expression is LAZY: its body runs when the generator is
    ITERATED, not when the expression is evaluated. So a module-level
    generator expression's body is FUNCTION scope -- it is not an
    import-time bomb.

    The one eager part is the FIRST generator's iterable, which Python
    evaluates in the ENCLOSING scope when the expression is evaluated --
    that part keeps the enclosing scope.
    """
    source = (
        "import os\n"
        "\n"
        "LAZY = (os.geteuid() for _ in range(1))\n"
        "\n"
        "EAGER_ITERABLE = (x for x in os.geteuid())\n"
    )
    hits = scan_source(source)
    assert len(hits) == 2, hits
    lazy_body = [h for h in hits if h.lineno == 3]
    assert len(lazy_body) == 1, hits
    assert lazy_body[0].scope == "function"
    eager_iterable = [h for h in hits if h.lineno == 5]
    assert len(eager_iterable) == 1, hits
    assert eager_iterable[0].scope == "module"


# ------------------------------------------------- the tool, structurally ---

def test_env_local_key_has_no_unguarded_posix_only_os_reference():
    """Every POSIX-only `os.*` reference in the tool is guarded, so importing
    and running it on Windows cannot raise AttributeError."""
    hits = scan_file(TOOL)
    assert hits, "the tool no longer references any POSIX-only os.* -- " \
                 "update this ratchet if that was deliberate"
    unguarded = [h for h in hits if h.guard is None]
    assert unguarded == [], (
        "unguarded POSIX-only os.* references in the tool:\n"
        + _describe(unguarded))


# ----------------------------------------------- the tool, behaviourally ---

def _run_tool(tmp_path: Path, *args: str, stdin: bytes = b""
              ) -> subprocess.CompletedProcess:
    target = tmp_path / "overlay.txt"
    audit = tmp_path / "audit" / "edits.jsonl"
    return subprocess.run(
        [sys.executable, str(TOOL), "--file", str(target),
         "--audit-log", str(audit), *args],
        input=stdin, capture_output=True, timeout=60, cwd=str(tmp_path),
    )


@pytest.mark.parametrize("args,stdin", [
    (("has", "TARGET_KEY"), b""),
    (("set", "TARGET_KEY"), b"a-value\n"),
    (("unset", "TARGET_KEY"), b""),
])
def test_env_local_key_never_emits_a_raw_traceback(tmp_path, args, stdin):
    """BEHAVIOURAL: on this platform the tool must refuse cleanly or work --
    it must never die with a raw AttributeError traceback."""
    (tmp_path / "overlay.txt").write_bytes(b"TARGET_KEY=old\n")
    proc = _run_tool(tmp_path, *args, stdin=stdin)
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert "Traceback (most recent call last)" not in stderr, stderr
    assert "has no attribute" not in stderr, stderr
    # The documented exit codes: 0 done/noop, 1 refused, 2 usage,
    # 3 could-not-measure, 4 applied-unaudited.
    assert proc.returncode in (0, 1, 2, 3, 4), (proc.returncode, stderr)


def test_env_local_key_completes_the_edit_on_this_platform(tmp_path):
    """The tool must WORK on Windows, not merely avoid crashing: the value
    lands, the audit row lands, and the value is printed nowhere."""
    target = tmp_path / "overlay.txt"
    target.write_bytes(b"TARGET_KEY=old\n")
    proc = _run_tool(tmp_path, "set", "TARGET_KEY", stdin=b"a-value\n")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert "Traceback (most recent call last)" not in stderr, stderr
    assert proc.returncode == 0, stderr
    assert b"result=done" in proc.stdout
    assert target.read_bytes() == b"TARGET_KEY=a-value\n"
    audit = tmp_path / "audit" / "edits.jsonl"
    rows = audit.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert "a-value" not in audit.read_text(encoding="utf-8")
    assert "a-value" not in proc.stdout.decode("utf-8", errors="replace")
    assert "a-value" not in stderr
