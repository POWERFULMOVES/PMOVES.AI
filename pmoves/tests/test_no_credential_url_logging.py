"""Guard: never log a URL that can carry credentials without redacting it.

NATS_URL carries ``user:password@`` on this fleet, and 54 modules logged it (or
a DSN / Neo4j URL) verbatim, so the credential landed in ``docker logs``
(measured on Knuckles 2026-10-01: Agent Zero printed it on every start).

Two checks:

1. AST sweep: a logging / print call whose argument is a credential-capable URL
   identifier (``nats_url``, ``NATS_URL``, ``database_url``, ``*_dsn`` ...) must
   wrap it in a redactor. Against origin/main before the fix this found 76
   call sites; it must now find zero.
2. Behaviour: every module-level ``_redact_url`` in the tree is extracted and
   executed against credential-bearing URLs. The copies are module-local by
   convention (service images do not all ship ``services/common``), so each
   copy is tested rather than trusted.

Limits (stated so a green run is not over-read): the sweep sees bare names,
attributes, string-subscripts and ``os.getenv("X")``. It does not see a URL
logged through a whole config object / dict, through an exception message
(``{exc}``), or through a variable whose name does not end in url/uri/dsn/servers.
"""

from __future__ import annotations

import ast
import re
import warnings
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]

CRED = re.compile(
    r"(nats|postgres|pg|db|database|redis|amqp|rabbit|mongo|clickhouse|dsn|broker|"
    r"sql|kafka|mqtt|neo4j|bolt|minio|s3|qdrant|meili|surreal|conn(ection)?_?(str|string|url))",
    re.I,
)
URLISH = re.compile(r"(url|uri|dsn|servers?|conn_str|connection_string)$", re.I)
LOG_FUNCS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log", "print"}
SAFE_CALL = re.compile(r"(redact|mask|scrub|sanit|safe|host|port|hostname|_display|^bool$|^len$)", re.I)
SKIP_PARTS = {"node_modules", ".venv", "site-packages", "__pycache__"}


def _ident(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        # Full dotted chain, so ``config.nats.url`` is seen as a NATS URL even
        # though its last component is only ``url``.
        base = _ident(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
        return _ident(node.value)
    if isinstance(node, ast.Call):
        fn = node.func
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr in ("getenv", "get")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            return node.args[0].value
    return None


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""


def _offenders(arg: ast.AST) -> list[str]:
    found: list[str] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.Call) and SAFE_CALL.search(_call_name(node)):
            return
        if isinstance(node, ast.FormattedValue):
            visit(node.value)
            return
        name = _ident(node)
        if name and URLISH.search(name) and CRED.search(name):
            found.append(name)
            return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(arg)
    return found


def _python_files() -> list[Path]:
    return [
        p
        for p in PMOVES.rglob("*.py")
        if not SKIP_PARTS.intersection(p.parts)
    ]


def _parse(path: Path) -> ast.Module | None:
    try:
        with warnings.catch_warnings():
            # Repo files with invalid escape sequences are not this test's concern.
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(path.read_text(errors="ignore"))
    except SyntaxError:
        return None


def test_no_unredacted_credential_url_in_log_calls() -> None:
    hits = []
    files = _python_files()
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in LOG_FUNCS:
                continue
            if name == "log" and not isinstance(node.func, ast.Attribute):
                continue
            args = list(node.args) + [kw.value for kw in node.keywords]
            bad = sorted({b for a in args for b in _offenders(a)})
            if bad:
                hits.append(f"{path.relative_to(PMOVES)}:{node.lineno} {bad}")
    assert len(files) > 500, f"scanned only {len(files)} files; the tree is not populated"
    assert not hits, "credential-capable URL logged without redaction:\n" + "\n".join(hits)


# Dicts inside a route that are NOT the response body. Keyed by file + value
# expression, never by line number, so an edit elsewhere cannot widen it.
ROUTE_ALLOWLIST = {
    # The row inserted into Supabase, not served back; rewriting it would change stored data.
    "services/render-webhook/webhook.py:body.s3_uri",
}

ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "route", "api_route"}


def _is_route(fn: ast.AST) -> bool:
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in ROUTE_DECORATORS
        for d in getattr(fn, "decorator_list", [])
    )


def test_no_unredacted_credential_url_in_http_route_bodies() -> None:
    """Same leak, different sink: an HTTP route serving the URL in its body.

    Agent Zero's unauthenticated ``/healthz`` returned ``nats.url`` with
    userinfo (measured live on Knuckles 2026-10-01). Flags dict values inside
    route-decorated functions; same identifier rules as the log sweep.
    """
    hits = []
    for path in _python_files():
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _is_route(fn):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Dict):
                    continue
                for value in node.values:
                    bad = _offenders(value) if value is not None else []
                    where = f"{path.relative_to(PMOVES)}:{_ident(value) or '?'}"
                    if bad and where not in ROUTE_ALLOWLIST:
                        hits.append(f"{path.relative_to(PMOVES)}:{node.lineno} {sorted(set(bad))}")
    assert not hits, "credential-capable URL served by an HTTP route:\n" + "\n".join(hits)


REDACT_CASES = {
    "nats://user:pa55@nats:4222": "pa55",
    "nats://user:a,b@nats:4222": "a,b",
    "nats://u:p1@a:4222,nats://v:p2@b:4222": "p1",
    "postgresql://admin:dbpw@db:5432/app": "dbpw",
}


def _redactor_copies() -> list[tuple[str, ast.FunctionDef]]:
    copies = []
    for path in _python_files():
        if "tests" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_redact_url":
                copies.append((str(path.relative_to(PMOVES)), node))
    return copies


COPIES = _redactor_copies()


def test_redactor_copies_were_found() -> None:
    # Guards the parametrised test below against passing vacuously.
    assert len(COPIES) >= 50, f"found only {len(COPIES)} _redact_url copies"


@pytest.mark.parametrize("where,func", COPIES, ids=[c[0] for c in COPIES])
def test_every_redact_url_copy_strips_userinfo(where: str, func: ast.FunctionDef) -> None:
    func.decorator_list = []
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0),
            ast.Import(names=[ast.alias("re")]),
            ast.ImportFrom(
                module="urllib.parse",
                names=[ast.alias(n) for n in ("urlparse", "urlunparse", "urlsplit", "urlunsplit")],
                level=0,
            ),
            ast.ImportFrom(module="typing", names=[ast.alias("Optional")], level=0),
            func,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    ns: dict = {}
    exec(compile(module, where, "exec"), ns)  # noqa: S102 - executing repo code under test
    redact = ns["_redact_url"]
    for url, secret in REDACT_CASES.items():
        try:
            out = redact(url)
        except Exception as exc:  # a crash would surface as a broken log line, not a leak
            pytest.fail(f"{where}: _redact_url({url!r}) raised {exc!r}")
        assert secret not in str(out), f"{where}: _redact_url({url!r}) -> {out!r} still carries the secret"
