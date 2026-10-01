#!/usr/bin/env python3
"""Dataflow sweep for credential-bearing URLs reaching a log, print, publish, route return or raise.

SOURCES
  Env reads (os.getenv / os.environ.get / os.environ[...] / any call whose first
  argument is the key) of NATS_URL, NATS_SERVERS, NATS_EVENT_BUS_URL,
  *DATABASE_URL, DB_URL, *POSTGRES_URL, *_DSN, DSN, *REDIS_URL, AMQP_URL,
  RABBITMQ_URL, *BROKER_URL, MONGO_URL, *_URI and *CLICKHOUSE_URL (each with an
  optional prefix); ``os.environ`` itself; and settings/model fields whose NAME
  looks like one of those (pydantic BaseSettings fills them from env by name).

PROPAGATION (scope = one service directory under pmoves/services, one file elsewhere)
  * VALUES follow value-preserving expressions (the value itself, str ops,
    or/if-else, f-strings, concatenation, lists/tuples, subscripts, split) into
    whatever they are assigned to (``self.url``, ``config.url``, ``url``), keyword
    args, parameter defaults, model/dataclass fields, function returns, and
    positional args to same-scope functions/classes.
  * CONTAINERS that hold a tainted value are tracked separately: dict literals,
    instances of a class with a tainted field, ``os.environ`` and copies of it
    (``dict(...)``, ``.copy()``, ``vars``, ``asdict``, ``.model_dump()``,
    ``.dict()``, ``__dict__``, ``str``/``repr``/``json.dumps``), and exception
    objects constructed with a tainted argument. A container is reported when it
    reaches a sink WHOLE (``%s``, f-string, dump call); ``cfg.port`` is not.
  * Calls that CONSUME the URL (``nats.connect(url)``) do not taint their result.

CLEANING
  Only the canonical ``services/common/redact.py::redact_url`` cleans a value:
  a name imported from ``services.common.redact`` / ``services.common.nats_client``,
  a local function AST-identical to the canonical one, or an alias of either.
  Any other redact/mask/scrub/sanitize helper does NOT clean.

SINKS
  logging-style calls, print/echo/secho/write/console.print, NATS
  ``publish``/``request`` payloads, JSONResponse/HTTPException/jsonify, return
  inside a route-decorated function, raise. Names matching the classic
  ``*_url``/DSN pattern are flagged at sinks even without a traced source.

ALLOWLIST
  Verified false positives, keyed on (path, kind, identifiers, the sink's FULL
  normalised source via ``ast.unparse`` -- every argument, across lines). Each
  row must match exactly ONE sink: a row matching zero (stale) or several
  (ambiguous) fails the run.

KNOWN LIMITS (not covered; do not read exit 0 as "no leak exists")
  * Cross-scope flow: a URL returned by a helper in another service scope (for
    example ``services/common``) and assigned to a non-seed name is not traced.
  * Computed or indirect env keys (``os.getenv(prefix + "_URL")``, keys from
    config files/YAML), and values loaded from files, CLI parsers other than
    typer/argparse defaults, or secrets managers.
  * Dynamic attribute access (getattr/setattr), closures and callbacks that
    receive the value through a framework, ``**kwargs`` fan-out.
  * Logging through wrappers whose method names are not in LOGM, and sinks other
    than those listed (files, HTTP request bodies, metrics labels).
  * Text produced by third-party libraries (``f"{exc}"`` where the library put
    the URL in its own message).
  * Secrets in a URL PATH (webhook URLs) -- ``redact_url`` does not model them.
  * Name-based: unrelated variables sharing a tainted name inside one scope are
    reported (handled by the allowlist), and a container's non-URL attributes
    are not tracked individually.

Exit: 0 clean, 1 findings (or stale/ambiguous allowlist rows), 3 could not measure.
Originated: PR #3244 review follow-up (B850-CLAUDE).
"""
from __future__ import annotations

import ast
import collections
import pathlib
import re
import sys
import warnings

KEY = re.compile(
    r"^(?!.*(REDIRECT|CALLBACK)_URI$)(DSN|[A-Z0-9_]*(NATS_URL|NATS_SERVERS|NATS_EVENT_BUS_URL|DATABASE_URL|DB_URL|POSTGRES_URL|_DSN"
    r"|REDIS_URL|AMQP_URL|RABBITMQ_URL|BROKER_URL|MONGO_URL|_URI|CLICKHOUSE_URL))$"
)
SEED = re.compile(
    r"(nats_url|database_url|redis_url|db_url|_dsn$|^dsn$|broker_url|amqp_url|rabbitmq_url|mongo_url"
    r"|postgres_url|nats_servers|clickhouse_url)",
    re.I,
)
LOGM = {"info", "warning", "warn", "error", "debug", "exception", "critical", "log", "print",
        "echo", "secho", "write", "print_json", "rule"}
PUBLISH = {"publish", "request"}
ROUTE = re.compile(r"^(get|post|put|delete|patch|route|api_route|websocket)$")
STROPS = {"strip", "rstrip", "lstrip", "replace", "split", "format", "removeprefix", "removesuffix",
          "encode", "decode"}
DUMPS = {"model_dump", "dict", "copy", "model_dump_json", "json", "items", "values", "to_dict"}
WHOLE_FUNCS = {"dict", "vars", "asdict", "str", "repr", "dumps", "list"}
CANONICAL_MODULES = {"services.common.redact", "services.common.nats_client",
                     "pmoves.services.common.redact", "pmoves.services.common.nats_client"}

# (path relative to the scanned root's parent, kind, identifiers, ast.unparse(sink)) -> why it is safe.
ALLOWLIST: dict[tuple[str, str, str, str], str] = {
    ('pmoves/services/audio-reprocess/app.py', 'log', 'url',
     "LOG.info('Downloaded %s -> %s (%d bytes)', url, dest, dest.stat().st_size)"):
        'download URL of the audio asset being reprocessed, not the NATS url (same name in scope)',
    ('pmoves/services/common/nats_service_listener.py', 'log', 'url',
     "logger.debug(f'Service announcement received: {announcement.slug} at {announcement.url}')"):
        'announced service HTTP base URL from the registry payload, not a broker URL',
    ('pmoves/services/common/nats_service_listener.py', 'publish', 'to_json',
     'nc.publish(SERVICE_ANNOUNCE_SUBJECT, announcement.to_json().encode())'):
        'service announcement (slug, HTTP base/health URLs) is the published contract; no broker URL in it',
    ('pmoves/services/common/nats_service_listener.py', 'log', 'url',
     "logger.info(f'Service announcement published: {slug} at {url}')"):
        'announced service HTTP base URL from the registry payload, not a broker URL',
    ('pmoves/services/creator-operator/app.py', 'route-return', 'NATS_URL',
     "return {'service': Config.SERVICE_SLUG, 'ok': True, 'nats': bool(Config.NATS_URL)}"):
        'returns bool(NATS_URL) only',
    ('pmoves/services/flute-gateway/main.py', 'log', 'url',
     "logger.info('NATS service announcement published: %s at %s', slug, url)"):
        'announced service HTTP URL, not the NATS url',
    ('pmoves/tools/geometry_bus_stream.py', 'log', 'host',
     "print(f'could not reach NATS at {host} within {CONNECT_TIMEOUT_S}s: {exc}\\n If this is a container DNS name (e.g. nats:4222) you are running on the\\n host — use the published address instead, e.g. NATS_URL=nats://…@localhost:4222', file=sys.stderr)"):
        "host = url.split('@')[-1] already drops userinfo",
    ('pmoves/tools/smoke_webhook.py', 'log', 'payload',
     'print(json.dumps(payload, indent=2))'):
        'dry-run print of a webhook payload; its only URI field is WEBHOOK_S3_URI (an s3:// object path)',
}


def _canonical_dump(root: pathlib.Path) -> str:
    for base in (root, pathlib.Path(__file__).resolve().parents[1]):
        path = base / "services" / "common" / "redact.py"
        if path.exists():
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.FunctionDef) and node.name == "redact_url":
                    return ast.dump(node)
    raise FileNotFoundError("services/common/redact.py")


def _ident(n):
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return n.attr
    return None


def _skey(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _cleaners(tree: ast.Module, canonical: str) -> set[str]:
    """Names in this module that are bound ONLY to the canonical redact_url."""
    good, bad = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module in CANONICAL_MODULES:
            for a in n.names:
                if a.name in {"redact_url", "_redact_url"}:
                    good.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            renamed = ast.dump(ast.FunctionDef(**{**{f: getattr(n, f) for f in n._fields}, "name": "redact_url"})) \
                if isinstance(n, ast.FunctionDef) else None
            (good if renamed == canonical else bad).add(n.name)
    changed = True
    while changed:
        changed = False
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id in good - bad:
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id not in good:
                        good.add(t.id)
                        changed = True
    return good - bad


def sweep(root: pathlib.Path):
    """Return (files_scanned, tainted_identifiers, sinks); sink = (path, lineno, kind, ids, text)."""
    root = root.resolve()
    rel_base = root.parent
    canonical = _canonical_dump(root)

    def env_read(n):
        if isinstance(n, ast.Call) and n.args and _skey(n.args[0]) and KEY.match(_skey(n.args[0])):
            return True
        if isinstance(n, ast.Subscript) and _ident(n.value) == "environ" and _skey(n.slice) and KEY.match(_skey(n.slice)):
            return True
        return False

    def is_environ(n):
        return isinstance(n, ast.Attribute) and n.attr == "environ" and _ident(n.value) == "os"

    scopes = collections.defaultdict(list)
    for p in sorted(root.rglob("*.py")):
        s = "/" + str(p.relative_to(root))
        if "/tests/" in s or p.name.startswith("test_") or "node_modules" in s or "/." in s:
            continue
        try:
            tree = ast.parse(p.read_text(errors="ignore"))
        except Exception:
            continue
        parts = p.relative_to(root).parts
        scope = "/".join(parts[:2]) if parts[0] == "services" and len(parts) > 2 else str(p)
        cleaners = _cleaners(tree, canonical)
        inside = {id(x) for d in ast.walk(tree)
                  if isinstance(d, ast.FunctionDef) and d.name in cleaners for x in ast.walk(d)}
        scopes[scope].append((p, tree, cleaners, inside))

    total_t = 0
    sinks = []
    for scope, files in scopes.items():
        T: set[str] = set()      # identifiers holding a tainted VALUE
        C: set[str] = set()      # identifiers holding a CONTAINER of a tainted value
        CLS: set[str] = set()    # classes with a tainted field
        defs = collections.defaultdict(list)
        for _p, tree, _c, _i in files:
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs[n.name].append(n)
                if isinstance(n, ast.ClassDef):
                    for b in n.body:
                        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name == "__init__":
                            defs[n.name].append(b)

        def make(cleaners):
            def clean_call(e):
                return isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id in cleaners

            def value(e):
                """Reason string if e evaluates to (something containing) the URL value."""
                if e is None or clean_call(e):
                    return None
                if env_read(e):
                    return "<env>"
                if isinstance(e, (ast.Name, ast.Attribute)) and _ident(e) in T:
                    return _ident(e)
                if isinstance(e, ast.BoolOp):
                    return next(filter(None, (value(v) for v in e.values)), None)
                if isinstance(e, ast.IfExp):
                    return value(e.body) or value(e.orelse)
                if isinstance(e, ast.JoinedStr):
                    return next(filter(None, (value(v.value) or container(v.value)
                                              for v in e.values if isinstance(v, ast.FormattedValue))), None)
                if isinstance(e, ast.BinOp):
                    return value(e.left) or value(e.right) or container(e.right)
                if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
                    return next(filter(None, (value(v) for v in e.elts)), None)
                if isinstance(e, ast.Subscript):
                    if is_environ(e.value):
                        return None  # only env_read() decides which os.environ keys are sources
                    if _skey(e.slice) and SEED.search(_skey(e.slice)):
                        return f"[{_skey(e.slice)!r}]"
                    return value(e.value) or container(e.value)
                if isinstance(e, (ast.Await, ast.Starred)):
                    return value(e.value)
                if isinstance(e, ast.Lambda):
                    return value(e.body)
                if isinstance(e, ast.Call):
                    f = e.func
                    if isinstance(f, ast.Attribute) and f.attr in STROPS:
                        return value(f.value)
                    if isinstance(f, ast.Name) and f.id in {"str", "list", "tuple"} and e.args:
                        return value(e.args[0])
                    if _ident(f) in {"Option", "Argument"} and e.args:
                        return value(e.args[0])
                    if _ident(f) in {"Field", "field", "Option", "Argument", "add_argument"}:
                        for k in e.keywords:
                            if k.arg in {"default", "default_factory"} and value(k.value):
                                return value(k.value)
                        if e.args:
                            return value(e.args[0])
                return None

            def container(e):
                """Reason string if e evaluates to an object/dict/exception HOLDING the URL."""
                if e is None or clean_call(e):
                    return None
                if is_environ(e):
                    return "<os.environ>"
                if isinstance(e, (ast.Name, ast.Attribute)) and _ident(e) in C:
                    return _ident(e)
                if isinstance(e, ast.Dict):
                    return next(filter(None, (value(v) or container(v) for v in e.values)), None)
                if isinstance(e, (ast.Await,)):
                    return container(e.value)
                if isinstance(e, ast.Call):
                    f = e.func
                    name = _ident(f) or ""
                    args = list(e.args) + [k.value for k in e.keywords]
                    if name in CLS:
                        return f"{name}()"
                    if isinstance(f, ast.Attribute) and f.attr in DUMPS:
                        return container(f.value)
                    if name in WHOLE_FUNCS and e.args:
                        return container(e.args[0])
                    if re.search(r"(Error|Exception)$", name):
                        return next(filter(None, (value(a) or container(a) for a in args)), None)
                return None

            return clean_call, value, container

        def add(target_set, i, _why):
            if i and i not in target_set and i not in {"_", "self", "cls"}:
                target_set.add(i)
                return True
            return False

        for _ in range(10):
            before = (len(T), len(C), len(CLS))
            for _p, tree, cleaners, inside in files:
                clean_call, value, container = make(cleaners)
                for n in ast.walk(tree):
                    if id(n) in inside:
                        continue
                    if isinstance(n, ast.ClassDef):
                        settings_like = any(re.search(r"Settings|Config", _ident(b) or "") for b in n.bases) \
                            or re.search(r"Settings|Config", n.name)
                        for b in n.body:
                            if isinstance(b, (ast.AnnAssign, ast.Assign)):
                                tgts = [b.target] if isinstance(b, ast.AnnAssign) else b.targets
                                names = [_ident(t) for t in tgts]
                                named = any(nm and SEED.search(nm) for nm in names)
                                if (settings_like and named) or value(b.value):
                                    add(CLS, n.name, "field")
                                    for nm in names:
                                        add(T, nm, "field")
                    if isinstance(n, (ast.Assign, ast.AnnAssign)):
                        tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
                        r, k = value(n.value), container(n.value)
                        for t in tgts:
                            for e in (t.elts if isinstance(t, ast.Tuple) else [t]):
                                if r:
                                    add(T, _ident(e), r)
                                if k:
                                    add(C, _ident(e), k)
                    elif isinstance(n, ast.Call):
                        if clean_call(n):
                            continue
                        for kw in n.keywords:
                            if kw.arg and value(kw.value):
                                add(T, kw.arg, "kw")
                        # Positional args flow only into a same-scope callable named directly
                        # (foo(x), Foo(x)) or via self (self.foo(x)); obj.get(x) is not resolved.
                        fn = n.func
                        direct = isinstance(fn, ast.Name) or (
                            isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "self")
                        for idx, a in enumerate(n.args if direct else []):
                            r, k = value(a), container(a)
                            if not (r or k):
                                continue
                            for d in defs.get(_ident(n.func) or "", []):
                                params = [x.arg for x in d.args.args if x.arg not in {"self", "cls"}]
                                if idx < len(params):
                                    add(T if r else C, params[idx], "positional")
                    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if n.name in cleaners:
                            continue
                        a = n.args
                        pairs = list(zip(a.args[len(a.args) - len(a.defaults):], a.defaults)) + [
                            (x, y) for x, y in zip(a.kwonlyargs, a.kw_defaults) if y is not None]
                        for prm, d in pairs:
                            if value(d):
                                add(T, prm.arg, "default")
                        for b in ast.walk(n):
                            if isinstance(b, ast.Return):
                                if value(b.value):
                                    add(T, n.name, "returns")
                                elif container(b.value):
                                    add(C, n.name, "returns")
                    elif isinstance(n, ast.ExceptHandler) and n.name:
                        pass
            if (len(T), len(C), len(CLS)) == before:
                break
        total_t += len(T) + len(C)

        for p, tree, cleaners, inside in files:
            clean_call, value, container = make(cleaners)
            parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}

            def route_fn(n):
                while n in parents:
                    n = parents[n]
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return any(isinstance(d, ast.Call) and ROUTE.match(_ident(d.func) or "") for d in n.decorator_list)
                return False

            def mentions(e):
                out = []

                def v(n):
                    if clean_call(n):
                        return
                    if env_read(n):
                        out.append("<env>")
                        return
                    if isinstance(n, ast.Name):
                        if n.id in T or n.id in C or (SEED.search(n.id) and "redact" not in n.id.lower()):
                            out.append(n.id)
                        return
                    if isinstance(n, ast.Attribute):
                        if n.attr in T or n.attr in C or (SEED.search(n.attr) and "redact" not in n.attr.lower()):
                            out.append(n.attr)
                            return
                        if is_environ(n):
                            out.append("os.environ")
                            return
                        if not isinstance(n.value, (ast.Name, ast.Attribute)):
                            v(n.value)
                        return
                    if isinstance(n, ast.Subscript) and not is_environ(n.value) and _skey(n.slice) \
                            and SEED.search(_skey(n.slice)):
                        out.append(f"[{_skey(n.slice)}]")
                        return
                    if isinstance(n, ast.Call):
                        k = container(n)
                        if k:
                            out.append(k)
                            return
                    for c in ast.iter_child_nodes(n):
                        v(c)

                v(e)
                return out

            for n in ast.walk(tree):
                kind, ex = None, []
                if isinstance(n, ast.Call):
                    f = n.func
                    if (isinstance(f, ast.Attribute) and f.attr in LOGM) or (
                            isinstance(f, ast.Name) and f.id in {"print", "echo", "rprint", "pprint"}):
                        kind, ex = "log", list(n.args) + [k.value for k in n.keywords]
                    elif isinstance(f, ast.Attribute) and f.attr in PUBLISH:
                        kind, ex = "publish", list(n.args[1:]) + [k.value for k in n.keywords if k.arg in {"payload", "data", "body"}]
                    elif _ident(f) in {"JSONResponse", "HTTPException", "json_response", "jsonify"}:
                        kind, ex = "resp", list(n.args) + [k.value for k in n.keywords]
                elif isinstance(n, ast.Return) and n.value is not None and route_fn(n):
                    kind, ex = "route-return", [n.value]
                elif isinstance(n, ast.Raise) and n.exc is not None:
                    kind, ex = "raise", [n.exc]
                if kind and id(n) not in inside:
                    m = sorted({x for e in ex for x in mentions(e) if x})
                    if m:
                        text = " ".join(ast.unparse(n).split())
                        sinks.append((str(p.relative_to(rel_base)), n.lineno, kind, ",".join(m), text))
    files_scanned = sum(len(fs) for fs in scopes.values())
    return files_scanned, total_t, sinks


def evaluate(sinks, allowlist=None):
    """Split sinks into (findings, allowlist problems)."""
    allowlist = ALLOWLIST if allowlist is None else allowlist
    counts = collections.Counter((p, k, i, t) for p, _l, k, i, t in sinks)
    findings = [s for s in sinks if (s[0], s[2], s[3], s[4]) not in allowlist]
    problems = []
    for key in allowlist:
        if counts[key] != 1:
            problems.append((counts[key], key))
    return findings, problems


def main() -> int:
    warnings.filterwarnings("ignore")  # SyntaxWarnings from parsing other files
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1]
    try:
        files, tainted, sinks = sweep(root)
    except Exception as exc:  # noqa: BLE001 -- a crash is not a finding
        print(f"could-not-measure: {type(exc).__name__}: {exc}")
        return 3
    if files == 0:
        print(f"could-not-measure: no Python files under {root}")
        return 3
    findings, problems = evaluate(sinks)
    print(f"files={files} tainted={tainted} sinks={len(sinks)} allowlisted={len(sinks) - len(findings)} "
          f"findings={len(findings)} allowlist_problems={len(problems)}")
    for p, line, kind, ids, text in sorted(findings):
        print(f"{p}:{line}\t{kind}\t{ids}\t{text[:160]}")
    for count, key in problems:
        print(f"allowlist row matched {count} sinks (must be exactly 1): {key[0]} {key[1]} {key[2]} :: {key[3][:120]}")
    return 1 if findings or problems else 0


if __name__ == "__main__":
    sys.exit(main())
