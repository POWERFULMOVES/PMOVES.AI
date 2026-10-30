"""Ratchet: every URL-path MCP entry in the inventory must be SERVED by its service.

Why this exists
---------------
The `flute-voice-mcp` inventory entry declares a streamable-http MCP
surface at `POST /mcp` (`pmoves/config/mcp_inventory.json`, key
`flute-voice-mcp`, `endpoint_prefix: flute_mcp` →
`defaults.flute_mcp_local_url = http://localhost:8055/mcp`).

The route is real in the source: `pmoves/services/flute-gateway/mcp_bridge.py:508`
declares `@router.post("/mcp")`, and `pmoves/services/flute-gateway/main.py:619`
mounts `create_mcp_router(...)`.

BUT the entry reached all six sibling clients while the RUNNING container
could not serve it. Measured on the operator's host 2026-10-30:

    $ docker ps --filter name=flute-gateway
    pmoves-flute-gateway-1 | ghcr.io/powerfulmoves/pmoves-flute-gateway:latest | Up 2 days

    $ docker image inspect ghcr.io/powerfulmoves/pmoves-flute-gateway:latest
    created=2026-08-08T16:37:12Z          <-- 65 days BEFORE the route landed

    $ docker exec pmoves-flute-gateway-1 python -c "..."
    GET  /openapi.json ... POST /mcp       <-- NOT in the running container's routes

The `/mcp` route landed in source on 2026-09-12 (#3036, `8c366f68410`).
The image predated it by 65 days. So every client config that carried
the `flute-voice-mcp` entry pointed at a URL that answered 404 -- six
sibling clients' configs, all silently broken.

Two failure classes, one root cause
-----------------------------------
1. **Source/route drift** -- the inventory declares a path the service's
   source does not serve at all. Caught here by asserting the path is
   declared in the serving service's source AND that the router is
   mounted into the ASGI app.
2. **Deployment staleness** -- the source serves the path but the
   RUNNING container is an older image. Caught by a LIVE probe of the
   declared URL.

This module covers BOTH. The static half is always on (no network, no
service required). The live half runs only when the service is actually
reachable, and degrades to skip otherwise.

The rule
--------
An inventory entry with a `flute_mcp`-style endpoint (i.e. one whose URL
carries an explicit PATH) must have that path declared in the serving
service's source. A path that appears nowhere in the service source is
a defect at authoring time, not a runtime surprise.

Mutation-kill
-------------
``pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py`` is the
companion harness. It copies the service tree, removes the route (or the
mount), points THIS module's constants at the mutated copy, and asserts
the corresponding test FAILS. A ratchet nobody re-runs decays.

What the 2026-10-30 review (PR #3428) hardened
----------------------------------------------
Four review threads on this lane changed the shape of the assertions.
They are recorded here because each one is a RULE, not a patch:

* 4427921337 -- the expected route is DERIVED from the inventory's
  declared URL. A hard-coded path proves only that the hard-coded path
  still exists; it cannot notice that the inventory now promises a
  different one.
* 4427921351 -- the live probe sends the credential the INVENTORY
  declares (`X-API-Key`), resolved from the environment, never
  hard-coded and never printed.
* 4427921357 -- the mount assertion inspects the `include_router` CALL
  EXPRESSION and requires the MCP ROUTER to be the argument. The
  presence of a string is not a mount.
* 4427972925 -- a declared URL with no path is a loud failure, not a
  silently rebased URL whose host became a path segment.
* 4428873759 -- the declared route must be attached to the ROUTER the
  factory RETURNS. "The file declares the path SOMEWHERE" is not the
  same fact as "the route the inventory promises is served by the
  router `main.py` mounts": a route declared on an unmounted sibling
  router in the same module satisfies BOTH static halves -- the file
  "declares" the path AND the factory is "mounted" -- while every
  client gets a 404.
"""

from __future__ import annotations

import ast
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

# This file lives at `<repo>/pmoves/tests/tools/<name>.py`:
#   parents[0] = tools,  parents[1] = tests,  parents[2] = pmoves
PMOVES_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = PMOVES_ROOT / "config" / "mcp_inventory.json"
FLUTE_SERVICE_DIR = PMOVES_ROOT / "services" / "flute-gateway"

# The inventory entries this ratchet pins to the flute-gateway service.
#
# WHY the ROUTE is not named here: the expected route is DERIVED from
# the inventory's own declared URL (see `_declared_path`), because a
# hard-coded path proves only that the hard-coded path still exists --
# it cannot notice that the INVENTORY now promises a different one.
# Finding 4427921337: with `/sse` and `/mcp` baked into the test, a
# change of `flute_mcp_local_url` to an unserved `/mcp-v2` left the
# assertion hunting for the OLD route while the inventory promised the
# new one -- so the same client-wide 404 this ratchet exists to prevent
# could merge undetected. The inventory is the contract; the assertion
# must be derived from it.
FLUTE_SERVER_KEYS = ("flute-voice", "flute-voice-mcp")

# The flute-gateway module that DECLARES the MCP routes, and the
# `create_mcp_router` factory that `main.py` mounts.
FLUTE_ROUTER_MODULE = "mcp_bridge.py"

# The factory that BUILDS the router `main.py` mounts. A route
# decorator only counts if it is attached to the router object this
# factory RETURNS -- a route declared on any other router in the
# module is declared on nothing that is served (finding 4428873759).
MCP_ROUTER_FACTORY = "create_mcp_router"

# The HTTP method each MCP transport uses, so the static assertion can
# check the METHOD as well as the path. Derived from the inventory's
# `transport` field rather than hard-coded per entry: the SSE surface is
# a server->client GET stream, the streamable-http surface carries
# client->server JSON-RPC in a POST body. An entry whose transport is
# not listed here is path-checked only.
TRANSPORT_METHODS = {"sse": "GET", "http": "POST"}

# The flute-gateway's declared HTTP port.
FLUTE_PORT = 8055

# The `serverInfo.name` a genuine flute-gateway MCP handshake answers
# with (mcp_bridge.py:401). The live probe asserts it, so a DIFFERENT
# service squatting on the port cannot make the probe pass.
FLUTE_SERVER_NAME = "pmoves-flute-gateway"


def _inventory() -> dict[str, Any]:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def _servers() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group in _inventory().get("groups", {}).values():
        for server in group.get("servers", []):
            out.append(server)
    return out


def _server_by_key(key: str) -> dict[str, Any] | None:
    for server in _servers():
        if server.get("key") == key:
            return server
    return None


def _display_path(path: Path) -> str:
    """A repo-relative path when possible, absolute otherwise.

    The mutation-kill harness points this module at a COPY of the
    service tree in a tmp dir, so the path is not under PMOVES_ROOT.
    `relative_to` raises there, and a ratchet whose failure MESSAGE
    raises is a ratchet that reports the wrong failure.
    """
    try:
        return str(path.relative_to(PMOVES_ROOT))
    except ValueError:
        return str(path)


def _resolved_url(server: dict[str, Any], defaults: dict[str, Any]) -> str | None:
    """The URL an inventory entry resolves to, from its own fields."""
    prefix = server.get("endpoint_prefix")
    endpoint = server.get("endpoint")
    url = server.get("url")
    if not url and prefix and endpoint:
        url = defaults.get(f"{prefix}_{endpoint}_url")
    return url


def _url_path(url: str) -> str:
    """The PATH component of a declared URL -- or a loud failure.

    WHY loud (finding 4427972925): a URL with no path cannot be
    asserted against the serving source and cannot be probed. Coercing it
    to "/" silently demotes the HOST to a path segment -- the override
    would "rebase" `http://host:8055` onto `<override>/host:8055` and
    probe a path nothing serves, which is exactly the inert-control
    defect this ratchet exists to catch. `pytest -O` strips `assert`,
    so this is an explicit raise, not an assert, and the message names
    the offending URL.
    """
    remainder = str(url).split("://", 1)[-1]
    if "/" not in remainder:
        raise ValueError(
            f"declared URL {url!r} carries no path -- it cannot be asserted "
            f"against the serving source or probed live"
        )
    return "/" + remainder.split("/", 1)[-1]


def _declared_path(server: dict[str, Any]) -> str:
    """The PATH the INVENTORY declares for one entry.

    The single place the expected route is derived, so the static
    assertion and the live probe cannot drift apart: both read the
    inventory, neither hard-codes a path (finding 4427921337).
    """
    defaults = _inventory().get("defaults", {})
    url = _resolved_url(server, defaults)
    if not url:
        raise ValueError(
            f"inventory entry {server.get('key')!r} resolves no URL "
            f"(prefix={server.get('endpoint_prefix')!r}, "
            f"endpoint={server.get('endpoint')!r})"
        )
    return _url_path(url)


# The FastAPI/Starlette route-decorator method names, used to recognise
# a route DECLARATION in the source.
_ROUTE_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "websocket"}
)


def _decorator_route(dec: ast.AST) -> dict[str, str] | None:
    """A route DECORATOR as `{path, method, receiver}`, or None.

    `receiver` is the OBJECT the route is attached to, unparsed:
    `router`, `self.router`, `APIRouter()`. It is the half that says
    WHICH router owns the route -- the half `_declared_routes` threw
    away, and the half finding 4428873759 needs.
    """
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    method = dec.func.attr.lower()
    if method not in _ROUTE_METHODS or not dec.args:
        return None
    first = dec.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return None
    return {
        "path": first.value,
        "method": method.upper(),
        "receiver": ast.unparse(dec.func.value),
    }


def _declared_routes(source: str) -> dict[str, set[str]]:
    """The routes the service source DECLARES, as `{path: {METHOD, ...}}`.

    WHY parse instead of grep: a grep for `"/mcp"` also matches a
    docstring, a log line, a comment or a URL inside another string --
    none of which creates a route. Only the decorator calls
    (`@router.post("/mcp")`) actually register a route, so the AST is
    the only source of truth that cannot be fooled by prose.

    WHAT THIS DOES NOT ANSWER: whether the route is attached to the
    router that is actually mounted. That is `_assert_route_on_returned_router`'s
    job (finding 4428873759) -- this function is deliberately
    scope-blind so it stays a faithful "declared ANYWHERE" census.
    """
    routes: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            route = _decorator_route(dec)
            if route is None:
                continue
            routes.setdefault(route["path"], set()).add(route["method"])
    return routes


def _route_decorators(tree: ast.Module) -> list[dict[str, Any]]:
    """Every route decorator in the module, WITH THE SCOPE it lives in.

    Each entry carries `path`, `method`, `receiver` and `scopes` -- the
    tuple of enclosing function names (empty at module scope). The
    scope is what decides WHICH OBJECT a receiver name binds to: a
    name the factory ASSIGNS is the factory's own local, while a name
    it never assigns is the module-level one.
    """
    found: list[dict[str, Any]] = []

    def visit(node: ast.AST, scopes: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in child.decorator_list:
                    route = _decorator_route(dec)
                    if route is not None:
                        found.append({**route, "scopes": scopes})
                visit(child, scopes + (child.name,))
            elif isinstance(child, ast.ClassDef):
                visit(child, scopes)
            else:
                visit(child, scopes)

    visit(tree, ())
    return found


def _factory_node(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The AST node of the router factory, or None when it is absent."""
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == MCP_ROUTER_FACTORY
        ):
            return node
    return None


def _nested_def_nodes(node: ast.AST) -> set[int]:
    """The ids of the nodes that belong to a NESTED def/class inside `node`.

    A nested function has its OWN scope, so its assignments and returns
    are not the factory's.
    """
    skip: set[int] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            skip.update(id(sub) for sub in ast.walk(child))
    return skip


def _factory_bindings(
    factory: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], set[str]]:
    """(assigned, returned) -- the names the factory binds, and hands back.

    `assigned` are the names the factory creates LOCALLY, so a decorator
    inside the factory that names one of them attaches to the factory's
    OWN object. `returned` are the names the factory hands back -- the
    router objects a caller can mount, and therefore the only objects a
    route may be attached to if it is to be served.

    A non-name return (a call, a conditional expression) cannot be
    matched to a decorator receiver by name; it is recorded as its
    source text so the failure message can name it instead of silently
    matching nothing.
    """
    skip = _nested_def_nodes(factory)
    assigned: set[str] = set()
    returned: set[str] = set()
    for node in ast.walk(factory):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned.add(node.target.id)
        elif isinstance(node, ast.Return) and node.value is not None:
            value = node.value
            returned.add(
                value.id if isinstance(value, ast.Name) else ast.unparse(value)
            )
    return assigned, returned


def _route_ownership(source: str) -> dict[str, Any]:
    """Who owns the routes in this module -- and which object is served.

    Returns a dict with:
      * `factory`  -- the factory's AST node, or None when it is absent
      * `assigned` -- the names the factory binds LOCALLY
      * `returned` -- the names the factory RETURNS (the mountable routers)
      * `decorators` -- every route decorator, each with an `owned` flag

    THE OWNERSHIP RULE: a route is owned when the object its decorator
    names is one the factory RETURNS, and both refer to the SAME
    binding. A name the factory assigns binds to the factory's local;
    a name it never assigns binds to the module-level object. So a
    module-level decorator naming a factory-local is a DIFFERENT
    object -- and is not owned.
    """
    tree = ast.parse(source)
    factory = _factory_node(tree)
    assigned: set[str] = set()
    returned: set[str] = set()
    if factory is not None:
        assigned, returned = _factory_bindings(factory)

    decorators = _route_decorators(tree)
    for dec in decorators:
        receiver = dec["receiver"]
        in_factory = MCP_ROUTER_FACTORY in dec["scopes"]
        dec["owned"] = (
            receiver in returned
            and not (receiver in assigned and not in_factory)
        )
    return {
        "factory": factory,
        "assigned": assigned,
        "returned": returned,
        "decorators": decorators,
    }


class RouterOwnershipError(AssertionError):
    """A declared route is attached to a router the factory does NOT return.

    An `AssertionError` subclass, so the mutation-kill harness's
    `pytest.raises(AssertionError)` idiom keeps working, and a SPECIFIC
    type, so a caller can name the failure mode instead of matching on
    a message.
    """


def _scope_label(scopes: tuple[str, ...]) -> str:
    """Where a decorator lives, in words.

    Two DIFFERENT objects can share a name -- a module-level `router`
    and the factory's own local `router` are not the same binding -- so
    the failure message has to say which one it means.
    """
    if not scopes:
        return "module scope"
    if MCP_ROUTER_FACTORY in scopes:
        return f"inside {MCP_ROUTER_FACTORY}()"
    return "inside " + " -> ".join(scopes)


def _assert_route_on_returned_router(
    source: str,
    path: str,
    method: str | None = None,
) -> None:
    """The route must be attached to the router the factory RETURNS.

    WHY this exists (finding 4428873759): `_declared_routes` answers
    "does this file, anywhere, decorate some `.post('/mcp')` on SOME
    object". That is not the same fact as "is the route the inventory
    promises served by the router `main.py` mounts". A route declared on
    an UNMOUNTED sibling router in the same module satisfies BOTH
    static halves -- the file "declares" the path and the factory is
    "mounted" -- while every client gets a 404.

    Raises `RouterOwnershipError` (an AssertionError) naming the path
    and the router object the route IS attached to, when the route is
    not attached to a router the factory returns. It is an explicit
    `raise`, not an `assert`, so `pytest -O` cannot switch the ratchet
    off -- a ratchet that can be switched off by a flag is not a
    ratchet.
    """
    ownership = _route_ownership(source)
    if ownership["factory"] is None:
        raise RouterOwnershipError(
            f"route {path!r} cannot be served: the module does not define "
            f"{MCP_ROUTER_FACTORY}(...), so there is no router to attach it to"
        )

    candidates = [
        dec
        for dec in ownership["decorators"]
        if dec["path"] == path
        and (method is None or dec["method"] == method.upper())
    ]
    if not candidates:
        raise RouterOwnershipError(
            f"route {path!r} is not declared in the module at all"
        )
    if any(dec["owned"] for dec in candidates):
        return

    owners = ", ".join(
        f"{dec['receiver']!r} ({_scope_label(dec['scopes'])})" for dec in candidates
    )
    returned = ", ".join(
        f"{name!r} ("
        + (
            "the factory's own local"
            if name in ownership["assigned"]
            else "module level"
        )
        + ")"
        for name in sorted(ownership["returned"])
    )
    raise RouterOwnershipError(
        f"route {path!r}"
        + (f" ({method.upper()})" if method else "")
        + f" is declared on {owners}, but {MCP_ROUTER_FACTORY}() returns "
        + (returned or "<nothing>")
        + " -- the route is attached to a router that is never mounted, so "
        "the endpoint the inventory promises 404s for every client that "
        "carries the entry"
    )


def _mcp_router_mounted(main_source: str) -> tuple[bool, str]:
    """Is the MCP router the ARGUMENT of an `app.include_router(...)` call?

    WHY the call EXPRESSION (finding 4427921357): the previous check
    proved only that `main.py` contained SOME `app.include_router(` call,
    independently of the string "create_mcp_router" appearing somewhere
    in the file. A router that is constructed and DISCARDED while some
    other router is included passes that check -- and `/sse` and `/mcp`
    both 404. So this inspects what is actually passed to
    `include_router`, and requires it to be the MCP router.

    Returns `(mounted, detail)`; `detail` names WHAT was found so a
    failure says which of the two ways the mount can be wrong.
    """
    tree = ast.parse(main_source)

    # (1) the MCP router factory, imported from the module that declares
    #     the routes the static assertion just checked.
    factory_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").lstrip(".") == (
            FLUTE_ROUTER_MODULE.removesuffix(".py")
        ):
            for alias in node.names:
                if alias.name == "create_mcp_router":
                    factory_names.add(alias.asname or alias.name)
    if not factory_names:
        return False, (
            f"main.py does not import create_mcp_router from "
            f"{FLUTE_ROUTER_MODULE.removesuffix('.py')}, so the router that "
            f"declares the routes is not a router this app could mount"
        )

    # (2) a variable bound to the MCP router, e.g. `router = create_mcp_router(...)`.
    bound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Name) and func.id in factory_names:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)

    # (3) an `include_router` whose ARGUMENT is the MCP router.
    seen: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "include_router":
            continue
        arg = node.args[0] if node.args else next(
            (kw.value for kw in node.keywords if kw.arg == "router"), None
        )
        seen.append(ast.unparse(arg) if arg is not None else "<no router argument>")
        if arg is None:
            continue
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
            if arg.func.id in factory_names:
                return True, f"app.include_router({arg.func.id}(...))"
        if isinstance(arg, ast.Name) and arg.id in bound:
            return True, f"app.include_router({arg.id})"
    return False, (
        f"no app.include_router(...) call takes the MCP router as its argument "
        f"(include_router argument(s) seen: {seen or 'none'})"
    )


# A `${VAR}` placeholder in a declared header value, e.g. `${FLUTE_API_KEY}`.
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_declared_headers(
    server: dict[str, Any],
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Resolve the headers the INVENTORY declares for one entry.

    WHY the inventory is the source (finding 4427921351): the inventory
    is the contract the client configs are DERIVED from, so it is where
    the credential's HEADER NAME and its ENVIRONMENT SOURCE are
    declared -- `flute-voice-mcp` declares `X-API-Key: ${FLUTE_API_KEY}`.
    The flute-gateway mounts the MCP router with
    `dependencies=[Depends(verify_api_key)]` (main.py:624), so on a fleet
    deployment where `FLUTE_API_KEY` is configured, a probe that sends
    no key is rejected with 401 -- and a 401 reads exactly like "some
    other service answered" to a probe whose identity check is the
    handshake body. The probe was rejecting a HEALTHY endpoint.

    Returns `(resolved_headers, unresolved)` where `unresolved` is a
    list of `(header name, env var name)` pairs. The VALUE of an
    unresolved credential is never returned, never logged and never
    printed -- only the header name and the variable name are.
    """
    resolved: dict[str, str] = {}
    unresolved: list[tuple[str, str]] = []
    declared = server.get("headers") or {}
    for name, raw in declared.items():
        value = str(raw)
        env_names = _PLACEHOLDER.findall(value)
        if not env_names:
            resolved[name] = value
            continue
        missing: list[str] = []
        for env_name in env_names:
            env_value = os.environ.get(env_name)
            if not env_value:
                missing.append(env_name)
                continue
            value = value.replace("${" + env_name + "}", env_value)
        if missing:
            unresolved.append((name, missing[0]))
            continue
        resolved[name] = value
    return resolved, unresolved


def _probe_headers(server: dict[str, Any]) -> dict[str, str]:
    """The headers the live probe must send -- or SKIP, loudly.

    WHY skip and not fail: a missing credential is an ENVIRONMENTAL
    condition, not a defect in the endpoint. The ratchet must never
    fail for a reason it cannot fix, and must never silently pass
    either -- so it skips, and the skip reason names the header and the
    variable (never the value). A skip here is not a pass; the static
    half is what carries the lane in CI.
    """
    resolved, unresolved = _resolve_declared_headers(server)
    if unresolved:
        names = ", ".join(f"{name} (env {env_name})" for name, env_name in unresolved)
        pytest.skip(
            f"flute-gateway probe cannot authenticate: the inventory declares "
            f"credential(s) that are not available in this environment: {names}. "
            f"Export the variable(s) and re-run -- a probe skipped for a "
            f"missing credential must not be read as a pass."
        )
    return resolved


@pytest.mark.parametrize("key", sorted(FLUTE_SERVER_KEYS))
def test_inventory_flute_endpoint_is_declared_in_service_source(key: str) -> None:
    """The inventory must not declare a path the serving source omits.

    A path that is only in the inventory is a 404 waiting to happen --
    and it reaches EVERY client that carries the entry, because the
    default `clients: null` means "all clients" (see
    `ServerSpec.supports_client` in `pmoves/tools/mcp_config_generator.py`).

    The expected route is DERIVED from the inventory's own declared URL
    (finding 4427921337). Asserting a hard-coded `/sse` and `/mcp` would
    only prove that the hard-coded paths still exist: repoint the
    inventory at `/mcp-v2` and the assertion would keep hunting for the
    old route while the clients were handed a path nothing serves.
    """
    server = _server_by_key(key)
    assert server is not None, f"{key}: entry missing from mcp_inventory.json"
    try:
        expected_path = _declared_path(server)
    except ValueError as exc:
        pytest.fail(f"{key}: {exc}")
    declared_url = _resolved_url(server, _inventory().get("defaults", {}))

    source_path = FLUTE_SERVICE_DIR / FLUTE_ROUTER_MODULE
    assert source_path.exists(), (
        f"{key}: expected the serving source {source_path} to exist -- the "
        f"inventory entry and the service tree have diverged"
    )
    source_text = source_path.read_text(encoding="utf-8")
    routes = _declared_routes(source_text)
    assert expected_path in routes, (
        f"{key}: the inventory declares {declared_url!r} (path {expected_path!r}), "
        f"but {_display_path(source_path)} does not declare that route "
        f"(routes declared there: {sorted(routes)}). Either the route was "
        f"removed or the inventory entry was added without the serving route "
        f"-- both are 404s for every client that carries the entry."
    )

    # The METHOD matters as much as the path: a route served with the
    # wrong verb answers 405, which the live probe would catch only when
    # a service happens to be running. The method is derived from the
    # inventory's own `transport` field, so an entry that changes
    # transport is caught here rather than silently keeping the old verb.
    transport = server.get("transport")
    expected_method = TRANSPORT_METHODS.get(str(transport))
    if expected_method:
        assert expected_method in routes[expected_path], (
            f"{key}: the inventory declares {declared_url!r} on transport "
            f"{transport!r}, which is {expected_method}, but "
            f"{_display_path(source_path)} declares "
            f"{sorted(routes[expected_path])} for {expected_path!r}."
        )

    # And the route must hang on the ROUTER THE FACTORY RETURNS
    # (finding 4428873759). "Declared somewhere in this module" is not
    # "served by the router `main.py` mounts": a route on an unmounted
    # sibling router satisfies the two assertions above and still 404s
    # for every client that carries the entry. This check raises
    # `RouterOwnershipError` -- naming the path and the router object --
    # when the route belongs to some other object.
    _assert_route_on_returned_router(source_text, expected_path, expected_method)


_MINIMAL_ROUTER_SOURCE = (
    "from fastapi import APIRouter\n"
    "\n"
    "\n"
    "def create_mcp_router():\n"
    "    router = APIRouter()\n"
    "{sibling}"
    "\n"
    "    @{receiver}.post('/mcp')\n"
    "    async def mcp_streamable(request):\n"
    "        return {{}}\n"
    "\n"
    "    return router\n"
)


def _minimal_router_source(receiver: str, sibling: str = "") -> str:
    """A minimal module shaped like the flute-gateway's router factory.

    Used to exercise the OWNERSHIP CHECK's own decision on both sides.
    The realistic version of this defect -- a REAL service file with the
    decorator moved onto a sibling router -- is the mutation-kill
    harness's job; this is the unit-level proof that the check can say
    NO at all.
    """
    return _MINIMAL_ROUTER_SOURCE.format(
        receiver=receiver,
        sibling=sibling,
    )


def test_route_ownership_rejects_a_route_on_an_unreturned_router() -> None:
    """The ownership check MUST be able to say NO.

    A ratchet that can only assert absence cannot catch a route that is
    declared on the wrong object (finding 4428873759). The failure must
    name the offending path AND the router object the route is
    actually attached to.
    """
    source = _minimal_router_source(receiver="stray", sibling="    stray = APIRouter()\n")
    with pytest.raises(RouterOwnershipError) as excinfo:
        _assert_route_on_returned_router(source, "/mcp", "POST")
    message = str(excinfo.value)
    assert "/mcp" in message, (
        f"the failure does not name the offending path: {message!r}"
    )
    assert "stray" in message, (
        f"the failure does not name the router object the route is attached to: {message!r}"
    )


def test_route_ownership_accepts_a_route_on_the_returned_router() -> None:
    """The control for the ownership check: the RIGHT shape must PASS.

    Without it, a check that failed for ANY reason (a typo in the
    fixture, an over-eager parser) would look like a working ratchet.
    """
    source = _minimal_router_source(receiver="router")
    # Raises on failure, so reaching here IS the pass.
    _assert_route_on_returned_router(source, "/mcp", "POST")


@pytest.mark.parametrize("key", sorted(FLUTE_SERVER_KEYS))
def test_inventory_flute_route_is_mounted_in_service_app(key: str) -> None:
    """The route must be MOUNTED, not merely declared.

    A route decorator in a module that is never included in the ASGI app
    is the same 404 with an extra step of indirection. This pins the
    mount in `main.py` -- and pins it at the ARGUMENT (finding
    4427921357): the included object must BE the MCP router, not merely
    a router of some kind.
    """
    main_path = FLUTE_SERVICE_DIR / "main.py"
    assert main_path.exists(), f"flute-gateway main.py missing at {main_path}"
    main_source = main_path.read_text(encoding="utf-8")
    mounted, detail = _mcp_router_mounted(main_source)
    assert mounted, (
        f"flute-gateway/main.py does not mount the MCP bridge router: {detail}. "
        f"The router that declares the routes is built and discarded, so every "
        f"path the inventory promises 404s for every client that carries the entry."
    )


@pytest.mark.parametrize("key", sorted(FLUTE_SERVER_KEYS))
def test_inventory_flute_entry_resolves_to_a_path_url(key: str) -> None:
    """Every pinned entry must resolve to a URL with a PATH.

    A path is what makes the endpoint assertable (the static half of
    this ratchet) and what makes it probeable (the live half). An entry
    that resolved to a bare host:port would be un-assertable and
    un-probeable, which is exactly the gap that let the stale-container
    defect ship.

    This guard used to cover `flute-voice-mcp` only, while the URL it
    protects is resolved for EVERY entry (finding 4427972925).
    """
    server = _server_by_key(key)
    assert server is not None, f"{key}: entry missing from mcp_inventory.json"
    defaults = _inventory().get("defaults", {})
    prefix = server.get("endpoint_prefix")
    endpoint = server.get("endpoint")
    assert prefix and endpoint, (
        f"{key} must declare both endpoint_prefix and endpoint so "
        f"its URL resolves from the inventory defaults"
    )
    url = _resolved_url(server, defaults)
    assert url, (
        f"{key} resolves no URL: prefix={prefix!r} "
        f"endpoint={endpoint!r} and defaults has no "
        f"{prefix}_{endpoint}_url key"
    )
    assert "/" in str(url).split("://", 1)[-1], (
        f"{key} URL {url!r} carries no path -- it cannot be "
        f"asserted against the source or probed live"
    )


def _live_flute_base() -> str | None:
    """Resolve the live flute-gateway base URL, or None when not running."""
    override = os.environ.get("FLUTE_GATEWAY_URL")
    if override:
        return override.rstrip("/")
    try:
        import socket

        with socket.create_connection(("localhost", FLUTE_PORT), timeout=0.5):
            return f"http://localhost:{FLUTE_PORT}"
    except OSError:
        return None


def _probe_url(declared_url: str, base: str) -> str:
    """The URL to actually probe, honouring the base override.

    The override must REBASE the declared URL, not merely gate
    reachability. A knob that looks like it redirects the probe but
    leaves the probe pointed at the original address is the same
    defect class this ratchet exists to catch: a control that does not
    control.

    WHY the path guard (finding 4427972925): a declared URL with no
    path used to be "rebased" into `<override>/host:8055` -- the host
    quietly demoted to a path segment, and the probe aimed at a path
    nothing serves. That is an override that does not control, wearing
    the costume of one that does. `_url_path` raises instead, naming
    the offending URL; the raise is explicit rather than an `assert`
    because `pytest -O` strips asserts.
    """
    path = _url_path(declared_url)
    return f"{base.rstrip('/')}{path}"


def _assert_responder_is_flute_gateway(url: str, status: int, body: str) -> None:
    """Assert the responder at `url` IS the flute-gateway MCP surface.

    Three properties, because "did not 404" alone is too weak -- any
    service holding the port satisfies it:

    1. the path is NOT a 404 (the stale-image symptom);
    2. the status is not a 5xx (mounted but broken);
    3. the handshake identifies the responder as `pmoves-flute-gateway`
       (a port collision cannot masquerade as the service).

    Extracted as a shared function so the mutation-kill harness
    INVOKES this exact check rather than restating it (lesson #12 from
    `test_gap_ratchet_LEARNINGS.md`).
    """
    assert status != 404, (
        f"the inventory declares {url!r} but the RUNNING flute-gateway "
        f"answers 404. The source declares POST /mcp "
        f"(pmoves/services/flute-gateway/mcp_bridge.py), so the running "
        f"IMAGE is older than the source -- rebuild it: "
        f"make -C pmoves rebuild-svc SVC=flute-gateway. Body: {body[:400]!r}"
    )
    assert status < 500, (
        f"the inventory declares {url!r} and the running service answered "
        f"{status} -- the route is mounted but broken. Body: {body[:400]!r}"
    )

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = {}
    server_name = (parsed.get("result") or {}).get("serverInfo", {}).get("name")
    assert server_name == FLUTE_SERVER_NAME, (
        f"the inventory declares {url!r} and the responder answered {status} "
        f"with serverInfo.name={server_name!r}, not {FLUTE_SERVER_NAME!r}. "
        f"Either a different service holds the port, or the MCP bridge is "
        f"not the thing answering -- either way this endpoint is not the "
        f"flute-gateway the inventory declares. Body: {body[:400]!r}"
    )


def test_inventory_flute_mcp_endpoint_answers_live() -> None:
    """LIVE probe: the declared MCP URL must actually answer.

    This is the half that would have caught the stale container. The
    static source assertions above prove the route is DECLARED; only a
    live probe proves the RUNNING image serves it.

    The three response properties are asserted by
    `_assert_responder_is_flute_gateway`, which the companion
    mutation-kill harness exercises directly.

    The request carries the credential the INVENTORY declares
    (finding 4427921351): the flute-gateway mounts the MCP router with
    `Depends(verify_api_key)`, so on a fleet deployment an
    unauthenticated probe is answered 401 -- and a 401 reads exactly
    like "the wrong service answered" to a probe whose identity check
    is the handshake body. The probe was rejecting a HEALTHY endpoint.

    Skips when the service is not running on this host -- deployment is
    a separate lane from the code lane, and a skip must not be read as
    a pass. Skips equally when the declared credential is not available
    in this environment: a missing credential is environmental, not a
    defect in the endpoint.
    """
    base = _live_flute_base()
    if base is None:
        pytest.skip(f"flute-gateway is not reachable on localhost:{FLUTE_PORT}")

    server = _server_by_key("flute-voice-mcp")
    assert server is not None
    defaults = _inventory().get("defaults", {})
    declared_url = _resolved_url(server, defaults)
    assert declared_url
    try:
        url = _probe_url(declared_url, base)
    except ValueError as exc:
        pytest.fail(f"flute-voice-mcp: {exc}")
    # The declared credential, resolved from the inventory and the
    # environment. Never logged, never printed, never hard-coded.
    headers = {"Content-Type": "application/json"}
    headers.update(_probe_headers(server))
    # A streamable-http MCP endpoint answers an initialize POST. We only
    # assert the path is NOT a 404 and that the responder is the
    # flute-gateway -- the protocol handshake is the MCP client's job,
    # not this ratchet's.
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pmoves-inventory-ratchet", "version": "1"},
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        pytest.skip(f"flute-gateway MCP endpoint unreachable: {exc}")

    _assert_responder_is_flute_gateway(url, status, body)
