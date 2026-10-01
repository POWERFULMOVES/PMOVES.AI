#!/usr/bin/env python3
"""Dataflow sweep for credential-bearing URLs reaching a log, print, route return or raise.

Sources: env reads of NATS_URL / *DATABASE_URL / *_DSN / *REDIS_URL / *BROKER_URL
and friends. Taint follows the VALUE into whatever it is assigned to (self.url,
config.url, url), through keyword args, parameter defaults, dataclass/pydantic
fields and positional args to same-scope callables. Scope = one service
directory under pmoves/services (one file elsewhere). Calls that CONSUME the URL
(nats.connect(url)) do not taint their result. Values passed through
redact_url()/redact*/mask*/scrub*/sanit* are clean.

Sinks: logging-style calls, print/echo/write, JSONResponse/HTTPException,
return inside a route-decorated function, raise. Names matching the classic
*_url/DSN pattern are flagged at sinks even without a traced source.

It is name-based inside a scope, so unrelated variables that share a tainted
name (a download url) are reported; those verified false positives live in
ALLOWLIST with the reason. Exit: 0 clean, 1 findings, 3 could not measure.

Originated: PR #3244 review follow-up (B850-CLAUDE).
"""
import ast
import collections
import pathlib
import re
import sys
import warnings

KEY = re.compile(r"^([A-Z0-9_]*NATS_URL|NATS_SERVERS|[A-Z0-9_]*DATABASE_URL|DB_URL|[A-Z0-9_]*POSTGRES_URL|[A-Z0-9_]*_DSN|DSN|[A-Z0-9_]*REDIS_URL|AMQP_URL|[A-Z0-9_]*BROKER_URL|MONGO_URL|MONGODB_URI|SUPABASE_DB_URL)$")
LOGM = {"info","warning","warn","error","debug","exception","critical","log","print","echo","secho","write","print_json","rule"}
SEED = re.compile(r"(nats_url|database_url|redis_url|db_url|_dsn$|^dsn$|broker_url|amqp_url|mongo_url|postgres_url|nats_servers)", re.I)
ROUTE = re.compile(r"^(get|post|put|delete|patch|route|api_route|websocket)$")
STROPS = {"strip","rstrip","lstrip","replace","split","format","removeprefix","removesuffix","encode","decode"}


# (path relative to repo, sink kind, tainted identifiers, stripped sink line) -> why it is safe.
# Keyed on the line TEXT so a real sink sharing a name with a false positive in
# the same file is still reported.
ALLOWLIST = {
    ('pmoves/services/audio-reprocess/app.py', 'log', 'url', 'LOG.info("Downloaded %s -> %s (%d bytes)", url, dest, dest.stat().st_size)'):
        'download URL of the audio asset, not the NATS url (name collision)',
    ('pmoves/services/audio-reprocess/app.py', 'log', 'out', 'sf.write(str(out), reduced, rate)'):
        'sf.write of an audio file path',
    ('pmoves/services/common/chit_lanes.py', 'log', 'params', 'logger.info('):
        'lane params, unrelated name chain',
    ('pmoves/services/common/model_nexus.py', 'raise', 'name', 'raise KeyError(f"Unknown Nexus provider: {name}")'):
        'provider/lane key name',
    ('pmoves/services/common/model_nexus.py', 'raise', 'name', 'raise KeyError(f"Unknown Nexus lane: {name}")'):
        'provider/lane key name',
    ('pmoves/services/common/nats_client.py', 'log', 'service_name', 'logger.info('):
        'service slug',
    ('pmoves/services/common/nats_client.py', 'log', 'service_name', 'logger.info("NATS connected (service=%s)", service_name)'):
        'service slug',
    ('pmoves/services/common/nats_client.py', 'log', 'name', 'logger.warning("%s=%r is not an int; using default %s", name, raw, default)'):
        'env var NAME (key), not its value',
    ('pmoves/services/common/nats_client.py', 'log', 'name', 'logger.warning("%s=%r is not a float; using default %s", name, raw, default)'):
        'env var NAME (key), not its value',
    ('pmoves/services/common/nats_service_listener.py', 'log', 'slug,url', 'logger.debug('):
        'announced service HTTP url from the registry payload',
    ('pmoves/services/common/nats_service_listener.py', 'log', 'slug,url', 'logger.info(f"Service announcement published: {slug} at {url}")'):
        'announced service HTTP url from the registry payload',
    ('pmoves/services/common/port_resolver.py', 'log', 'mode', 'print(f"Topology: {topo.mode.value}")'):
        'topology mode enum',
    ('pmoves/services/common/port_resolver.py', 'log', 'topo', 'print(f"  Compose project: {topo.compose_project}")'):
        'topology object fields',
    ('pmoves/services/common/port_resolver.py', 'log', 'topo', 'print(f"  Supabase runtime: {topo.supabase_runtime}")'):
        'topology object fields',
    ('pmoves/services/common/port_resolver.py', 'log', 'topo', 'print(f"  External services: {\', \'.join(sorted(topo.external_services))}")'):
        'topology object fields',
    ('pmoves/services/common/port_resolver.py', 'log', 'port,slug', 'print(f"{slug:<30} {host:<30} {port:<8}")'):
        'port table',
    ('pmoves/services/common/shape_store.py', 'log', 'records', 'logger.warning('):
        'record count',
    ('pmoves/services/common/tensorzero.py', 'log', 'result', 'logger.warning('):
        'TensorZero result',
    ('pmoves/services/common/tracing.py', 'log', 'service_name', 'logger.info('):
        'service slug',
    ('pmoves/services/creator-operator/app.py', 'route-return', 'NATS_URL', 'return {"service": Config.SERVICE_SLUG, "ok": True, "nats": bool(Config.NATS_URL)}'):
        'bool(NATS_URL) only',
    ('pmoves/services/flute-gateway/main.py', 'log', 'url', 'logger.info("NATS service announcement published: %s at %s", slug, url)'):
        'announced service HTTP url',
    ('pmoves/services/flute-gateway/main.py', 'log', 'name', 'logger.warning("provider %s health check raised: %r", name, result)'):
        'provider name',
    ('pmoves/services/flute-gateway/providers/ultimate_tts.py', 'raise', 'name', 'raise UltimateTTSError('):
        'provider name',
    ('pmoves/services/flute-gateway/providers/ultimate_tts.py', 'log', 'name', 'logger.warning('):
        'provider name',
    ('pmoves/services/flute-gateway/voice_registry.py', 'log', 'name', 'logger.warning("voice_registry: invalid %s=%r; using %d", name, raw, default)'):
        'env var NAME (key), not its value',
    ('pmoves/services/tokenism-simulator/config/tensorzero.py', 'log', 'text', 'logger.error(f"HTTP error from TensorZero: {e.response.status_code} {e.response.text}")'):
        'HTTP response body text',
    ('pmoves/tools/geometry_bus_stream.py', 'log', 'host', 'print('):
        "url.split('@')[-1] already strips userinfo",
    ('pmoves/tools/voice_follow_agent.py', 'log', 'text', 'sys.stderr.write(f"[voice-follow] {msg.subject}: {text[:140]}\\n")'):
        'spoken message text',
    ('pmoves/tools/voice_follow_cast_agent.py', 'log', 'text', 'sys.stderr.write(f"[voice-follow-cast] {msg.subject}: {text[:140]}\\n")'):
        'spoken message text',
}


def sweep(root: pathlib.Path):

    def ident(n):
        if isinstance(n, ast.Name): return n.id
        if isinstance(n, ast.Attribute): return n.attr
    def skey(n): return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None
    def env_read(n):
        if isinstance(n, ast.Call) and n.args and skey(n.args[0]) and KEY.match(skey(n.args[0])):
            return True
        if isinstance(n, ast.Subscript) and ident(n.value) == "environ" and skey(n.slice) and KEY.match(skey(n.slice)):
            return True
        return False
    def redact_call(n): return isinstance(n, ast.Call) and re.search(r"redact|mask|scrub|sanit", ident(n.func) or "", re.I)
    def preserving(e, T):
        """Return a taint reason if e evaluates to (something containing) the URL itself."""
        if e is None or redact_call(e): return None
        if env_read(e): return "<env " + (skey(e.args[0]) if isinstance(e, ast.Call) else skey(e.slice)) + ">"
        if isinstance(e, (ast.Name, ast.Attribute)) and ident(e) in T: return ident(e)
        if isinstance(e, ast.BoolOp): return next(filter(None, (preserving(v, T) for v in e.values)), None)
        if isinstance(e, ast.IfExp): return preserving(e.body, T) or preserving(e.orelse, T)
        if isinstance(e, ast.JoinedStr): return next(filter(None, (preserving(v.value, T) for v in e.values if isinstance(v, ast.FormattedValue))), None)
        if isinstance(e, ast.BinOp): return preserving(e.left, T) or preserving(e.right, T)
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)): return next(filter(None, (preserving(v, T) for v in e.elts)), None)
        if isinstance(e, ast.Subscript): return preserving(e.value, T)
        if isinstance(e, ast.Await): return preserving(e.value, T)
        if isinstance(e, ast.Lambda): return preserving(e.body, T)
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Attribute) and f.attr in STROPS: return preserving(f.value, T)
            if isinstance(f, ast.Name) and f.id in {"str", "list", "tuple"} and e.args: return preserving(e.args[0], T)
            if ident(f) in {"Option", "Argument"} and e.args: return preserving(e.args[0], T)
            if ident(f) in {"Field", "field", "Option", "Argument", "add_argument"}:
                for k in e.keywords:
                    if k.arg in {"default", "default_factory"}: 
                        r = preserving(k.value, T)
                        if r: return r
                if e.args: return preserving(e.args[0], T)
        return None
    def mentions(e, T):
        """Sink check: tainted value appears anywhere in e (outside redact calls)."""
        out = []
        def v(n):
            if redact_call(n): return
            r = preserving(n, T) if not isinstance(n, ast.Call) or env_read(n) else None
            if isinstance(n, (ast.Name, ast.Attribute)) and (ident(n) in T or (SEED.search(ident(n)) and "redact" not in ident(n).lower())): out.append(ident(n)); return
            if env_read(n): out.append(r); return
            for c in ast.iter_child_nodes(n): v(c)
        v(e); return out
    def scope_of(p):
        parts = p.parts
        if "services" in parts:
            i = parts.index("services")
            if i + 1 < len(parts) - 1: return "/".join(parts[: i + 2])
        return str(p)
    scopes = collections.defaultdict(list)
    for p in root.rglob("*.py"):
        s = "/" + str(p.relative_to(root))
        if "/tests/" in s or p.name.startswith("test_") or "node_modules" in s or "/." in s: continue
        try: scopes[scope_of(p)].append((p, ast.parse(p.read_text(errors="ignore"))))
        except Exception: pass
    total_T = 0; sinks = []; whys = []
    for scope, files in scopes.items():
        T = set(); why = {}
        defs = collections.defaultdict(list)
        for p, tree in files:
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): defs[n.name].append(n)
                if isinstance(n, ast.ClassDef):
                    for b in n.body:
                        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and b.name == "__init__": defs[n.name].append(b)
        def add(i, reason):
            if i and i not in T and i not in {"_", "self", "cls"}: T.add(i); why[i] = reason
        for _ in range(8):
            n0 = len(T)
            for p, tree in files:
                for n in ast.walk(tree):
                    if isinstance(n, (ast.Assign, ast.AnnAssign)):
                        r = preserving(n.value, T)
                        if r:
                            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                                for e in (t.elts if isinstance(t, ast.Tuple) else [t]): add(ident(e), f"{p}:{n.lineno} {ident(e)} <- {r}")
                    elif isinstance(n, ast.Call):
                        if redact_call(n): continue
                        for k in n.keywords:
                            r = preserving(k.value, T)
                            if r and k.arg: add(k.arg, f"{p}:{n.lineno} kw {k.arg}= <- {r}")
                        for idx, a in enumerate(n.args):
                            r = preserving(a, T)
                            if not r: continue
                            for d in defs.get(ident(n.func) or "", []):
                                params = [x.arg for x in d.args.args if x.arg not in {"self", "cls"}]
                                if idx < len(params): add(params[idx], f"{p}:{n.lineno} {ident(n.func)}(arg{idx}) -> {params[idx]} <- {r}")
                    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if n.name == "redact_url": continue
                        a = n.args
                        pairs = list(zip(a.args[len(a.args) - len(a.defaults):], a.defaults)) + [(x, y) for x, y in zip(a.kwonlyargs, a.kw_defaults) if y is not None]
                        for prm, d in pairs:
                            r = preserving(d, T)
                            if r: add(prm.arg, f"{p}:{n.lineno} param {prm.arg}= <- {r}")
                        # functions that return the URL taint their name (callers assign it)
                        for b in ast.walk(n):
                            if isinstance(b, ast.Return):
                                r = preserving(b.value, T)
                                if r: add(n.name, f"{p}:{b.lineno} returns <- {r}")
            if len(T) == n0: break
        total_T += len(T)
        for i in sorted(T): whys.append(f"{scope}\t{i}\t{why[i]}")
        for p, tree in files:
            parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
            def route_fn(n):
                while n in parents:
                    n = parents[n]
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return any(isinstance(d, ast.Call) and ROUTE.match(ident(d.func) or "") for d in n.decorator_list)
                return False
            for n in ast.walk(tree):
                kind = None; ex = []
                if isinstance(n, ast.Call):
                    f = n.func
                    if (isinstance(f, ast.Attribute) and f.attr in LOGM) or (isinstance(f, ast.Name) and f.id in {"print", "echo", "rprint", "pprint"}):
                        kind, ex = "log", list(n.args) + [k.value for k in n.keywords]
                    elif ident(f) in {"JSONResponse", "HTTPException", "json_response", "jsonify"}:
                        kind, ex = "resp", list(n.args) + [k.value for k in n.keywords]
                elif isinstance(n, ast.Return) and n.value is not None and route_fn(n):
                    kind, ex = "route-return", [n.value]
                elif isinstance(n, ast.Raise) and n.exc is not None:
                    kind, ex = "raise", [n.exc]
                if kind:
                    m = [x for e in ex for x in mentions(e, T) if x]
                    if m: sinks.append(f"{p}:{n.lineno}\t{kind}\t{','.join(sorted(set(m)))}")
    return len([f for fs in scopes.values() for f in fs]), total_T, sinks


def main() -> int:
    warnings.filterwarnings("ignore")  # SyntaxWarnings from parsing other files
    repo = pathlib.Path(__file__).resolve().parents[2]
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else repo / "pmoves"
    files, tainted, sinks = sweep(root)
    if files == 0:
        print(f"could-not-measure: no Python files under {root}")
        return 3
    findings, allowed = [], 0
    seen = set()
    for line in sorted(sinks):
        loc, kind, ids = line.split("\t")
        file_path, lineno = loc.rsplit(":", 1)
        path = str(pathlib.Path(file_path).resolve().relative_to(repo))
        text = pathlib.Path(file_path).read_text(errors="ignore").splitlines()[int(lineno) - 1].strip()
        key = (path, kind, ids, text)
        if key in ALLOWLIST:
            allowed += 1
            seen.add(key)
        else:
            findings.append(f"{path}:{lineno}\t{kind}\t{ids}")
    print(f"files={files} tainted_identifiers={tainted} sinks={len(sinks)} allowlisted={allowed} findings={len(findings)}")
    for f in findings:
        print(f)
    for stale in sorted(set(ALLOWLIST) - seen):
        print("stale allowlist entry (no longer reported): " + "\t".join(stale))
    return 1 if findings or (set(ALLOWLIST) - seen) else 0


if __name__ == "__main__":
    sys.exit(main())
