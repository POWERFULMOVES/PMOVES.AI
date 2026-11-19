"""Mutation-kill harness: the MCP inventory endpoint ratchet must say no.

The companion harness for
``pmoves/tests/tools/test_mcp_inventory_endpoint_ratchet.py``.

Why this exists
---------------
The flute-gateway's `/mcp` route landed in source on 2026-09-12
(#3036, `8c366f68410`), but the RUNNING container's image was built
2026-08-08T16:37:12Z -- 65 days earlier. The running container had no
`/mcp` route, so the `flute-voice-mcp` inventory entry pointed at a 404
for all six sibling clients that carry it. Nothing asserted the
declared endpoint was actually served, so a 404 sat there for 65 days.

The ratchet fixes that. This harness proves the fix is LOAD-BEARING:
a ratchet that can only pass is decoration.

How it works
------------
Lesson #12 from ``test_gap_ratchet_LEARNINGS.md``: a mutation-kill must
INVOKE the assertion the ratchet uses, never restate it. So this
harness does not re-implement the checks. It:

1. copies the real flute-gateway service tree into a tmp dir,
2. MUTATES the copy (removes the route decorator, removes the router
   mount, or mounts a DIFFERENT router),
3. repoints the ratchet module's own module-level constants at the
   mutated copy,
4. calls the ratchet's OWN test functions and asserts they RAISE with
   the SPECIFIC expected message -- not merely that "something" raised.

The mutated copy is what makes the mutation honest: the ratchet reads
whatever tree it is pointed at, so pointing it at a tree with the route
deleted is exactly the state that must be rejected.

The original defect is preserved here as the mutation, so the harness
keeps the historical failure mode alive and watchable.

What the 2026-10-30 review (PR #3428) added
-------------------------------------------
Four review threads each stated a way the ratchet could pass while the
defect it exists to catch was present. A mutation that leaves such a
ratchet green is a mutation the harness must also kill:

* 4427921337 -- the expected route must be DERIVED from the inventory.
  Mutated here by pointing the ratchet at an inventory whose entry
  declares an UNSERVED path (`/mcp-v2`): a hard-coded assertion would
  keep hunting for the old route and survive.
* 4427921351 -- the live probe must send the credential the INVENTORY
  declares. Asserted here by invoking the ratchet's own header
  resolution with a fixture credential, and by proving the probe SKIPS
  (never sends a placeholder, never prints a secret) when the
  credential is unavailable.
* 4427921357 -- the mount assertion must inspect the `include_router`
  ARGUMENT. Mutated here by mounting a DIFFERENT router: the old
  "the string create_mcp_router appears somewhere" check survives that.
* 4427972925 -- a declared URL with no path must fail loudly. Asserted
  here by invoking the ratchet's own `_probe_url` with a bare host:port.

A fifth thread landed on the same PR afterwards:

* 4428873759 -- the declared route must be attached to the router the
  factory RETURNS. The declaration check answered "does this file,
  anywhere, decorate some `.post('/mcp')` on SOME object", so a route on
  an UNMOUNTED sibling router satisfied both static halves -- the file
  "declares" the path and the factory is "mounted" -- while every client
  got a 404. Mutated here by moving the decorator onto a sibling router
  the factory never returns: the old check survives that, the new one
  does not.

A sixth thread landed on the same PR after that, and it was aimed at the
OWNERSHIP RULE itself -- at how it decided ownership:

* 4429144504 -- ownership must be decided by OBJECT IDENTITY, never by
  comparing SOURCE TEXT. The text comparison failed in BOTH
  directions, so both directions are mutated here:
  * defect (a), a FALSE NEGATIVE: `return APIRouter()` put the literal
    text "APIRouter()" into the returned set, and a stray
    `@APIRouter().post("/mcp")` unparses to the SAME text -- so the
    stray instance looked OWNED and the blind spot stayed open.
    Mutated here: the factory returns a CONSTRUCTED router and the
    decorator sits on ANOTHER fresh instance. The ratchet must FAIL.
  * defect (b), a FALSE POSITIVE: `return router, admin` -- a
    legitimate two-value return -- was recorded as ONE name spelled
    "router, admin", so the router it returns became invisible and a
    VALID module FAILED the ratchet. The ratchet cried wolf.
    Mutated here: the factory returns a TUPLE. The ratchet must PASS.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHET_MODULE = "pmoves.tests.tools.test_mcp_inventory_endpoint_ratchet"

# The mount that makes the declared route reachable at all.
MOUNT_CALL = "app.include_router("
MUTATED_MOUNT_CALL = "app.include_router_DISABLED("

# The MCP router factory call inside the mount. Mutating it mounts a
# DIFFERENT router -- the case the old "the string create_mcp_router
# appears in the file" check could not see (finding 4427921357).
MCP_ROUTER_FACTORY_CALL = "create_mcp_router("
MUTATED_ROUTER_FACTORY_CALL = "some_other_router("

# The suffix appended to a route path to take the route out of service
# while leaving the rest of the source intact.
DISABLED_SUFFIX = "_DISABLED"

# The inventory entry whose declared route this harness mutates.
TARGET_KEY = "flute-voice-mcp"

# A path the source does NOT serve -- the state the inventory mutation
# must be rejected for.
UNSERVED_PATH = "/mcp-v2"


def _load_ratchet():
    """Import the ratchet module fresh, with its constants reset.

    `importlib.reload` matters here: the harness repoints
    `FLUTE_SERVICE_DIR` at a mutated copy, and without a reload the
    next test would copy the ALREADY-MUTATED tree and mutate it again
    -- so the "mutation setup failed: route decl not found" error
    would mask the real assertion.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    importlib.invalidate_caches()
    module = importlib.import_module(RATCHET_MODULE)
    return importlib.reload(module)


def _route_declaration(ratchet, key: str = TARGET_KEY) -> tuple[str, str, str]:
    """The decorator the ratchet PINS for `key`, derived from the ratchet.

    WHY derive it (finding 4427921337): the harness must mutate the
    route the ratchet actually asserts. If the harness hard-coded the
    decorator text the way the ratchet used to, an inventory path change
    would leave the mutation aimed at a route nobody checks -- the
    mutation would SURVIVE and the harness would report a false green.
    Deriving it from the ratchet's own inventory-derived path keeps the
    two in lockstep.

    Returns `(decorator_text, path, receiver)` -- `receiver` is the
    router object the decorator is attached to, which the sibling-router
    mutation needs so it can detach the route from the served router.
    """
    server = ratchet._server_by_key(key)
    assert server is not None, f"mutation setup failed: {key} is not in the inventory"
    declared = ratchet._resolved_url(server, ratchet._inventory().get("defaults", {}))
    assert declared, f"mutation setup failed: {key} resolves no URL"
    path = ratchet._url_path(declared)
    bridge = Path(ratchet.FLUTE_SERVICE_DIR) / ratchet.FLUTE_ROUTER_MODULE
    routes = ratchet._declared_routes(bridge.read_text(encoding="utf-8"))
    assert path in routes, (
        f"mutation setup failed: the inventory path {path!r} is not declared "
        f"in {bridge}"
    )
    method = sorted(routes[path])[0]
    pattern = re.compile(
        r"@(?P<receiver>\w+)\."
        + method.lower()
        + r"\(\s*['\"]"
        + re.escape(path)
        + r"['\"]\s*\)"
    )
    match = pattern.search(bridge.read_text(encoding="utf-8"))
    assert match, (
        f"mutation setup failed: no {method} decorator for {path} found in {bridge}"
    )
    return match.group(0), path, match.group("receiver")


def _mutate_route_onto_sibling_router(
    text: str, decl: str, receiver: str
) -> tuple[str, str]:
    """Move the route decorator onto a stray SIBLING router.

    WHY this shape (finding 4428873759): it is the smallest edit that
    reproduces the defect class the finding names -- a route DECLARED on
    a router the factory never RETURNS. A second `APIRouter` is created
    right beside the decorator (a realistic slip: the decorator lands on
    the wrong object) and the decorator is re-targeted at it, while
    `create_mcp_router` still returns the ORIGINAL router.

    The mutation is a plain text edit of the REAL source -- no stub, no
    synthetic module -- so the harness proves the ratchet rejects the
    defect as it would appear in the service tree.

    Returns `(mutated_source, sibling_name)`.
    """
    assert decl in text, "mutation setup failed: route decl not found"
    index = text.index(decl)
    line_start = text.rfind("\n", 0, index) + 1
    indent = text[line_start:index]
    sibling = f"{receiver}_sibling"
    moved = decl.replace(f"{receiver}.", f"{sibling}.", 1)
    assert moved != decl, (
        "mutation setup failed: the decorator receiver could not be re-targeted"
    )
    # The ORIGINAL indent before `decl` stays in the text, so the first
    # replacement line must not repeat it; the moved decorator needs it
    # because it now starts its own line.
    mutated = (
        f"{sibling} = APIRouter()\n"
        f"\n"
        f"{indent}{moved}"
    )
    return text.replace(decl, mutated, 1), sibling


def _replace_factory_return(text: str, ratchet, new_lines: list[str]) -> str:
    """Replace the factory's OWN `return` with `new_lines`.

    WHY the AST (lesson 2.8): the harness must mutate the return the
    ratchet actually reads. The factory's own return is located with
    the RATCHET's own helpers -- `_factory_node()` and
    `_nested_def_nodes()` -- so a nested helper's return (the route
    handlers' own `return {}` / `return responses`) is never the one
    replaced. A text search would hit those first.
    """
    tree = ast.parse(text)
    factory = ratchet._factory_node(tree)
    assert factory is not None, (
        "mutation setup failed: the module does not define "
        f"{ratchet.MCP_ROUTER_FACTORY}()"
    )
    skip = ratchet._nested_def_nodes(factory)
    returns = [
        node
        for node in ast.walk(factory)
        if isinstance(node, ast.Return)
        and node.value is not None
        and id(node) not in skip
    ]
    assert len(returns) == 1, (
        f"mutation setup failed: expected exactly ONE return in "
        f"{ratchet.MCP_ROUTER_FACTORY}(), found {len(returns)}"
    )
    node = returns[0]
    lines = text.splitlines(keepends=True)
    indent = lines[node.lineno - 1][: node.col_offset]
    replaced = (
        lines[: node.lineno - 1]
        + [f"{indent}{line}\n" for line in new_lines]
        + lines[node.end_lineno :]
    )
    return "".join(replaced)


def _mutate_factory_onto_a_constructed_router(
    text: str,
    decl: str,
    receiver: str,
    ratchet,
) -> str:
    """Re-target the decorator at a FRESH instance, and return a FRESH router.

    WHY this shape (finding 4429144504, defect (a)): the false
    negative lived in the TEXT comparison, so the mutation has to put
    the SAME text on both sides of it. `return APIRouter()` puts the
    text "APIRouter()" into the factory's returned set, and
    `@APIRouter().post("/mcp")` puts the same text on the decorator's
    receiver -- two DIFFERENT instances sharing one text. The previous
    round's rule could not tell them apart and called the stray
    instance OWNED.
    """
    assert decl in text, "mutation setup failed: route decl not found"
    moved = decl.replace(f"{receiver}.", "APIRouter().", 1)
    assert moved != decl, (
        "mutation setup failed: the decorator receiver could not be re-targeted"
    )
    text = text.replace(decl, moved, 1)
    return _replace_factory_return(text, ratchet, ["return APIRouter()"])


def _legacy_owned(ratchet, source: str, path: str, method: str) -> bool:
    """The PREVIOUS round's TEXT-based ownership rule, frozen as a witness.

    Finding 4429144504 removed that rule from the ratchet: it decided
    ownership by comparing SOURCE TEXT -- the factory's returned set was
    the unparsed text of the `return` value, and the decorator's
    receiver was the unparsed text of the object it decorates.

    This copy exists ONLY as a WITNESS. It lets the harness state what
    the OLD rule would have said about a mutation, so the new rule's
    verdict can be shown to DIFFER in both directions -- blind on a
    constructed router, crying wolf on a tuple. The rule under test is
    always the ratchet's own AST-based one (lesson 2.5); nothing here
    is asserted on its behalf.
    """
    tree = ast.parse(source)
    factory = ratchet._factory_node(tree)
    if factory is None:
        return False
    skip = ratchet._nested_def_nodes(factory)
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
    module_scope, scopes_by_node = ratchet._scope_tree(tree)
    decorators = ratchet._route_decorators(tree, module_scope, scopes_by_node)
    for dec in decorators:
        if dec["path"] != path or dec["method"] != method.upper():
            continue
        receiver = dec["receiver"]
        in_factory = ratchet.MCP_ROUTER_FACTORY in dec["scopes"]
        if receiver in returned and not (receiver in assigned and not in_factory):
            return True
    return False


def _mutated_service_tree(tmp_path: Path, *, drop_route: bool, drop_mount: bool) -> Path:
    """Copy the flute-gateway tree and apply the requested mutation."""
    ratchet = _load_ratchet()
    source_dir = Path(ratchet.FLUTE_SERVICE_DIR)
    dest = tmp_path / "flute-gateway"
    shutil.copytree(source_dir, dest)

    if drop_route:
        decl, path, _receiver = _route_declaration(ratchet)
        bridge = dest / ratchet.FLUTE_ROUTER_MODULE
        text = bridge.read_text(encoding="utf-8")
        assert decl in text, "mutation setup failed: route decl not found"
        bridge.write_text(text.replace(decl, decl.replace(path, path + DISABLED_SUFFIX)), encoding="utf-8")

    if drop_mount:
        main = dest / "main.py"
        text = main.read_text(encoding="utf-8")
        assert MOUNT_CALL in text, "mutation setup failed: include_router not found"
        main.write_text(text.replace(MOUNT_CALL, MUTATED_MOUNT_CALL), encoding="utf-8")

    return dest


def _mutated_inventory(tmp_path: Path, ratchet, key: str, path: str) -> Path:
    """A copy of the inventory whose entry declares an UNSERVED path.

    WHY this mutation (finding 4427921337): the inventory is the
    contract the client configs are derived from. If it declares a path
    the service does not serve, every client that carries the entry is
    broken -- and a ratchet that asserts a HARDCODED path cannot see it.
    """
    inventory = json.loads(Path(ratchet.INVENTORY).read_text(encoding="utf-8"))
    defaults = inventory.setdefault("defaults", {})
    server = ratchet._server_by_key(key)
    assert server is not None, f"mutation setup failed: {key} is not in the inventory"
    prefix = server.get("endpoint_prefix")
    endpoint = server.get("endpoint")
    defaults_key = f"{prefix}_{endpoint}_url"
    assert defaults_key in defaults, (
        f"mutation setup failed: the inventory has no {defaults_key} default"
    )
    original = str(defaults[defaults_key])
    defaults[defaults_key] = original.rsplit("/", 1)[0] + path
    dest = tmp_path / "mcp_inventory.json"
    dest.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return dest


def _point_ratchet_at(ratchet, service_dir: Path, inventory: Path | None = None):
    """Repoint the ratchet's own constants at the mutated artefacts."""
    ratchet.FLUTE_SERVICE_DIR = service_dir
    if inventory is not None:
        ratchet.INVENTORY = inventory


def test_mutation_removed_route_declaration_is_killed(tmp_path: Path) -> None:
    """Removing the route the inventory declares MUST make the ratchet fail.

    This is the ORIGINAL defect: the source stopped declaring the
    route, but the inventory kept promising it.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_service_tree(tmp_path, drop_route=True, drop_mount=False)
    _point_ratchet_at(ratchet, mutated)

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
            "flute-voice-mcp"
        )
    assert "does not declare" in str(excinfo.value), (
        "the ratchet raised, but not with the route-drift message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_removed_router_mount_is_killed(tmp_path: Path) -> None:
    """Removing the router mount MUST make the ratchet fail.

    A route decorator in a module that is never included in the ASGI
    app is the same 404 with an extra step of indirection. This is the
    other half of the ORIGINAL defect: the route existed but was never
    mounted, so the running service could not serve it.

    The SPECIFIC failure is asserted, not merely "it raised": a mount
    that vanished and a mount that mounts the WRONG router are
    different defects, and the message says which one fired.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=True)
    _point_ratchet_at(ratchet, mutated)

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_inventory_flute_route_is_mounted_in_service_app("flute-voice-mcp")
    assert "does not mount the MCP bridge router" in str(excinfo.value), (
        "the ratchet raised, but not with the missing-mount message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_mounting_another_router_is_killed(tmp_path: Path) -> None:
    """Mounting a DIFFERENT router MUST make the ratchet fail.

    This is the mutation the old mount check could NOT see
    (finding 4427921357): the MCP router is still constructed, and the
    file still contains the string "create_mcp_router", but the router
    that is INCLUDED is somebody else's -- so `/sse` and `/mcp` both
    404. The old check asserted "some app.include_router( call exists"
    and passed.

    The route-declaration assertion must still PASS here -- that is what
    isolates the failure to the mount.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=False)
    main = mutated / "main.py"
    text = main.read_text(encoding="utf-8")
    assert MCP_ROUTER_FACTORY_CALL in text, (
        "mutation setup failed: the MCP router factory call not found"
    )
    main.write_text(
        text.replace(MCP_ROUTER_FACTORY_CALL, MUTATED_ROUTER_FACTORY_CALL),
        encoding="utf-8",
    )
    _point_ratchet_at(ratchet, mutated)

    # The route is still declared -- only the mount was broken.
    ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
        "flute-voice-mcp"
    )
    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_inventory_flute_route_is_mounted_in_service_app("flute-voice-mcp")
    assert "does not mount the MCP bridge router" in str(excinfo.value), (
        "the ratchet raised, but not with the missing-mount message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )


def test_mutation_inventory_declares_an_unserved_path_is_killed(
    tmp_path: Path,
) -> None:
    """An inventory that promises an UNSERVED path MUST make the ratchet fail.

    This is finding 4427921337. The ratchet used to assert the
    HARDCODED paths `/sse` and `/mcp`, so repointing the inventory at
    `/mcp-v2` left the assertion hunting for the old route: the
    inventory promised a path nothing serves and the ratchet stayed
    green -- exactly the client-wide 404 this lane exists to prevent.

    The expected route must be DERIVED from the inventory, so this
    mutation kills a ratchet that hard-codes it.
    """
    ratchet = _load_ratchet()
    mutated_inventory = _mutated_inventory(
        tmp_path, ratchet, TARGET_KEY, UNSERVED_PATH
    )
    _point_ratchet_at(ratchet, Path(ratchet.FLUTE_SERVICE_DIR), mutated_inventory)

    with pytest.raises(AssertionError) as excinfo:
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
            TARGET_KEY
        )
    assert "does not declare" in str(excinfo.value), (
        "the ratchet raised, but not with the route-drift message -- the "
        f"assertion that should have fired changed shape: {excinfo.value!r}"
    )
    assert UNSERVED_PATH in str(excinfo.value), (
        "the failure does not name the unserved path the inventory declared: "
        f"{excinfo.value!r}"
    )


def test_mutation_route_moved_onto_a_sibling_router_is_killed(tmp_path: Path) -> None:
    """A route on a router the factory does NOT return MUST make the ratchet fail.

    Finding 4428873759: the ratchet derived the PATH the inventory
    promises and pinpointed the ROUTER that gets mounted, but its
    declaration check answered "does this file, anywhere, decorate some
    `.post('/mcp')` on SOME object". A route declared on an UNMOUNTED
    sibling router in the same module therefore satisfied BOTH static
    halves -- the file "declares" the path and the factory is
    "mounted" -- while every client got a 404. CI green, clients 404.

    THE MUTATION is a realistic edit of the REAL file: a second
    `APIRouter` is created beside the decorator and the decorator is
    re-targeted at it, while `create_mcp_router` still returns the
    original router. Nothing is stubbed and no module is synthesised --
    this is the shape the defect would take in the service tree.

    THE THREE STATES are asserted in order, on ONE copy: GREEN on the
    pristine bytes, RED with the mutation applied, GREEN again after the
    original bytes are restored. The restore happens in a `finally`, so
    a failing assertion cannot leave the tree mutated -- and it is
    byte-exact, verified by re-reading the file.
    """
    ratchet = _load_ratchet()
    mutated_tree = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=False)
    bridge = mutated_tree / ratchet.FLUTE_ROUTER_MODULE
    pristine = bridge.read_bytes()
    decl, path, receiver = _route_declaration(ratchet)
    mutated_source, sibling = _mutate_route_onto_sibling_router(
        pristine.decode("utf-8"), decl, receiver
    )
    assert mutated_source != pristine.decode("utf-8"), (
        "mutation setup failed: the route decorator was not moved onto a "
        "sibling router"
    )
    _point_ratchet_at(ratchet, mutated_tree)

    try:
        # GREEN BEFORE: the pristine copy passes the ratchet.
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)

        # RED AFTER: the route now hangs on a router nothing mounts.
        bridge.write_text(mutated_source, encoding="utf-8")
        with pytest.raises(ratchet.RouterOwnershipError) as excinfo:
            ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
                TARGET_KEY
            )
        message = str(excinfo.value)
        assert path in message, (
            "the failure does not name the route the inventory declares: "
            f"{message!r}"
        )
        assert sibling in message, (
            "the failure does not name the router object the route is "
            f"actually attached to: {message!r}"
        )
        assert "is declared on" in message, (
            "the failure is not the route/decorator mismatch message: "
            f"{message!r}"
        )
    finally:
        # Restore the ORIGINAL bytes, byte-exact, whatever happened above.
        bridge.write_bytes(pristine)
        assert bridge.read_bytes() == pristine, (
            "mutation setup failed: the tree was not restored byte-exactly"
        )

    # GREEN AFTER RESTORE: the ratchet passes again on the original bytes.
    ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)


def test_mutation_factory_returning_a_constructed_router_is_killed(
    tmp_path: Path,
) -> None:
    """A factory that returns a CONSTRUCTED router MUST make the ratchet fail.

    Finding 4429144504, defect (a) -- the FALSE NEGATIVE. The previous
    round's ownership rule compared SOURCE TEXT: the factory's returned
    set was the unparsed text of the `return` value, so
    `return APIRouter()` contributed the literal string "APIRouter()".
    A stray `@APIRouter().post("/mcp")` decorator unparses to the SAME
    string -- so the text comparison concluded the STRAY instance was
    the returned router, and the blind spot the ownership rule exists
    to close stayed open. The rule must decide by IDENTITY: a
    constructed router names NO binding, so no route can be shown to
    hang on it.

    THE MUTATION is a realistic edit of the REAL file: the factory
    hands back a freshly constructed router instead of the named one,
    and the `/mcp` decorator is re-targeted at ANOTHER fresh instance.
    Nothing is stubbed and no module is synthesised.

    THE THREE STATES are asserted in order, on ONE copy: GREEN on the
    pristine bytes, RED with the mutation applied, GREEN again after the
    original bytes are restored. The restore happens in a `finally`, so
    a failing assertion cannot leave the tree mutated -- and it is
    byte-exact, verified by re-reading the file.
    """
    ratchet = _load_ratchet()
    mutated_tree = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=False)
    bridge = mutated_tree / ratchet.FLUTE_ROUTER_MODULE
    pristine = bridge.read_bytes()
    decl, path, receiver = _route_declaration(ratchet)
    mutated_source = _mutate_factory_onto_a_constructed_router(
        pristine.decode("utf-8"), decl, receiver, ratchet
    )
    assert mutated_source != pristine.decode("utf-8"), (
        "mutation setup failed: the factory was not made to return a "
        "constructed router"
    )
    _point_ratchet_at(ratchet, mutated_tree)

    # The witness states what the PREVIOUS round's text-based rule said
    # about this mutation: it considered the stray instance OWNED (the
    # text "APIRouter()" was in its returned set), so the mutation
    # SURVIVED that rule. This is the blind spot the new rule closes.
    assert _legacy_owned(ratchet, mutated_source, path, "POST"), (
        "the witness disagrees: the previous round's text-based rule did "
        "NOT consider the stray instance owned, so this mutation does not "
        "reproduce the false negative it is meant to"
    )

    try:
        # GREEN BEFORE: the pristine copy passes the ratchet.
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)

        # RED AFTER: the route now hangs on an instance the factory does
        # not hand back -- the constructed router names no binding.
        bridge.write_text(mutated_source, encoding="utf-8")
        with pytest.raises(ratchet.RouterOwnershipError) as excinfo:
            ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
                TARGET_KEY
            )
        message = str(excinfo.value)
        assert path in message, (
            "the failure does not name the route the inventory declares: "
            f"{message!r}"
        )
        assert "APIRouter()" in message, (
            "the failure does not name the router object the route is "
            f"actually attached to: {message!r}"
        )
        assert "is declared on" in message, (
            "the failure is not the route/decorator mismatch message: "
            f"{message!r}"
        )
    finally:
        # Restore the ORIGINAL bytes, byte-exact, whatever happened above.
        bridge.write_bytes(pristine)
        assert bridge.read_bytes() == pristine, (
            "mutation setup failed: the tree was not restored byte-exactly"
        )

    # GREEN AFTER RESTORE: the ratchet passes again on the original bytes.
    ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)


def test_mutation_factory_returning_a_tuple_is_not_cried_wolf(tmp_path: Path) -> None:
    """A factory that returns a TUPLE MUST NOT make the ratchet fail.

    Finding 4429144504, defect (b) -- the FALSE POSITIVE. The previous
    round's ownership rule recorded the returned name as the SOURCE
    TEXT of the return value, so the legitimate two-value return
    `return router, admin` was recorded as ONE name spelled
    "router, admin". The router it actually returns became invisible to
    the rule, so a VALID module FAILED the ratchet: the ratchet cried
    wolf and broke CI for correct code. The rule must DESTRUCTURE the
    tuple, so `router` and `admin` are two separate bindings and the
    route on `router` is still owned.

    THE MUTATION is a legitimate edit of the REAL file: the factory
    hands back its router AND a second router -- exactly the shape a
    factory serving two surfaces takes.

    THE THREE STATES are asserted in order, on ONE copy: GREEN on the
    pristine bytes, GREEN again with the legitimate two-value return
    applied (the ratchet must NOT cry wolf), and GREEN once more after
    the original bytes are restored. The restore happens in a `finally`
    and is byte-exact, verified by re-reading the file.
    """
    ratchet = _load_ratchet()
    mutated_tree = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=False)
    bridge = mutated_tree / ratchet.FLUTE_ROUTER_MODULE
    pristine = bridge.read_bytes()
    _decl, path, _receiver = _route_declaration(ratchet)
    mutated_source = _replace_factory_return(
        pristine.decode("utf-8"),
        ratchet,
        ["admin = APIRouter()", "return router, admin"],
    )
    assert mutated_source != pristine.decode("utf-8"), (
        "mutation setup failed: the factory was not made to return a tuple"
    )
    _point_ratchet_at(ratchet, mutated_tree)

    # The witness states what the PREVIOUS round's text-based rule said
    # about this mutation: its returned set was the single name
    # "router, admin", so the router it returns was invisible and the
    # route looked UNOWNED -- the ratchet cried wolf. The new rule
    # destructures the tuple and keeps the ownership intact.
    assert not _legacy_owned(ratchet, mutated_source, path, "POST"), (
        "the witness disagrees: the previous round's text-based rule did "
        "NOT reject the two-value return, so this mutation does not "
        "reproduce the false positive it is meant to"
    )

    try:
        # GREEN BEFORE: the pristine copy passes the ratchet.
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)

        # STILL GREEN AFTER: a legitimate two-value return must NOT make
        # the ratchet cry wolf.
        bridge.write_text(mutated_source, encoding="utf-8")
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)
    finally:
        # Restore the ORIGINAL bytes, byte-exact, whatever happened above.
        bridge.write_bytes(pristine)
        assert bridge.read_bytes() == pristine, (
            "mutation setup failed: the tree was not restored byte-exactly"
        )

    # GREEN AFTER RESTORE: the ratchet passes again on the original bytes.
    ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(TARGET_KEY)


def test_mutation_both_route_and_mount_removed_is_killed(tmp_path: Path) -> None:
    """Both mutations together MUST also be caught.

    This is the state the STALE IMAGE actually presented: the running
    container served neither the route nor the mount, because its image
    predated both.
    """
    ratchet = _load_ratchet()
    mutated = _mutated_service_tree(tmp_path, drop_route=True, drop_mount=True)
    _point_ratchet_at(ratchet, mutated)

    with pytest.raises(AssertionError):
        ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
            "flute-voice-mcp"
        )
    with pytest.raises(AssertionError):
        ratchet.test_inventory_flute_route_is_mounted_in_service_app("flute-voice-mcp")


def test_unmutated_service_tree_still_passes(tmp_path: Path) -> None:
    """The control: the real tree must PASS both static assertions.

    Without this, a harness that fails for ANY reason (a typo in the
    mutation, an import error) would look like a successful mutation
    kill. The control proves the harness can also say YES.
    """
    ratchet = _load_ratchet()
    unmutated = _mutated_service_tree(
        tmp_path, drop_route=False, drop_mount=False
    )
    _point_ratchet_at(ratchet, unmutated)

    # These raise on failure, so reaching here IS the pass.
    ratchet.test_inventory_flute_endpoint_is_declared_in_service_source(
        "flute-voice-mcp"
    )
    ratchet.test_inventory_flute_route_is_mounted_in_service_app("flute-voice-mcp")


def test_live_probe_url_follows_the_base_override() -> None:
    """The base override MUST rebase the probe URL, not just gate reachability.

    A knob that looks like it redirects the probe but leaves the probe
    pointed at the original address cannot control anything -- it is
    the same defect class this lane exists to catch. This asserts the
    rebasing is real, by checking the URL the probe would use.
    """
    ratchet = _load_ratchet()

    # The default case: the base is the inventory's own host:port, so
    # the probe URL is the declared URL unchanged.
    default_probe = ratchet._probe_url(
        "http://localhost:8055/mcp", "http://localhost:8055"
    )
    assert default_probe == "http://localhost:8055/mcp"

    # The override case: the host:port changes, the PATH does not.
    rebased = ratchet._probe_url(
        "http://localhost:8055/mcp", "http://flute-node.internal:9000"
    )
    assert rebased == "http://flute-node.internal:9000/mcp", (
        f"the override did not rebase the probe URL: {rebased!r}"
    )
    assert rebased != "http://localhost:8055/mcp"


def test_live_probe_rejects_a_declared_url_with_no_path() -> None:
    """A declared URL with NO PATH must fail loudly, not silently rebase.

    Finding 4427972925: `_probe_url` used to turn `http://host:8055`
    into `<override>/host:8055` -- the host quietly demoted to a path
    segment and the probe aimed at a path nothing serves. That is an
    override that does not control, wearing the costume of one that
    does.

    The failure must NAME the offending URL, and it must be a real
    error rather than an `assert` (which `pytest -O` strips).
    """
    ratchet = _load_ratchet()
    with pytest.raises(ValueError) as excinfo:
        ratchet._probe_url("http://localhost:8055", "http://flute-node.internal:9000")
    message = str(excinfo.value)
    assert "http://localhost:8055" in message, (
        f"the failure does not name the offending URL: {message!r}"
    )


def test_live_probe_sends_the_credential_the_inventory_declares(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe must send the credential the INVENTORY declares.

    Finding 4427921351: the flute-gateway mounts the MCP router with
    `Depends(verify_api_key)`, so on a fleet deployment an
    unauthenticated probe is answered 401 -- and the probe read that as
    "the wrong service answered", rejecting a HEALTHY endpoint.

    The value used here is a TEST FIXTURE, not a secret: it proves the
    header is resolved from the environment and sent under the header
    NAME the inventory declares, without any real key being involved.
    """
    ratchet = _load_ratchet()
    server = ratchet._server_by_key(TARGET_KEY)
    assert server is not None, f"mutation setup failed: {TARGET_KEY} is not in the inventory"
    declared = server.get("headers") or {}
    assert declared, "mutation setup failed: the entry declares no headers"
    header_name = next(iter(declared))
    env_names = re.findall(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", str(declared[header_name])
    )
    assert env_names, (
        "mutation setup failed: the declared header carries no ${VAR} placeholder"
    )
    for env_name in env_names:
        monkeypatch.setenv(env_name, "ratchet-fixture-key")

    headers = ratchet._probe_headers(server)
    assert header_name in headers, (
        f"the probe did not send the header the inventory declares "
        f"(declared: {sorted(declared)})"
    )
    assert headers[header_name] == "ratchet-fixture-key", (
        "the probe did not send the credential resolved from the environment"
    )


def test_live_probe_skips_when_the_declared_credential_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An UNAVAILABLE credential must SKIP -- never fail, never leak.

    Finding 4427921351: a missing credential is an ENVIRONMENTAL
    condition, not a defect in the endpoint. The probe must skip with a
    reason that names the header and the VARIABLE -- and must never
    send a literal `${VAR}` placeholder and never print a secret.
    """
    ratchet = _load_ratchet()
    server = ratchet._server_by_key(TARGET_KEY)
    assert server is not None, f"mutation setup failed: {TARGET_KEY} is not in the inventory"
    declared = server.get("headers") or {}
    assert declared, "mutation setup failed: the entry declares no headers"
    header_name = next(iter(declared))
    env_names = re.findall(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", str(declared[header_name])
    )
    assert env_names, (
        "mutation setup failed: the declared header carries no ${VAR} placeholder"
    )
    for env_name in env_names:
        monkeypatch.delenv(env_name, raising=False)

    with pytest.raises(pytest.skip.Exception) as excinfo:
        ratchet._probe_headers(server)
    message = str(excinfo.value)
    assert env_names[0] in message, (
        f"the skip reason does not name the variable: {message!r}"
    )
    assert "${" not in message, (
        f"the skip reason leaked an unresolved placeholder: {message!r}"
    )


def test_live_probe_rejects_a_responder_that_is_not_the_flute_gateway() -> None:
    """A non-404 responder that is NOT the flute-gateway MUST be rejected.

    "Did not 404" is too weak on its own -- any service holding the
    port satisfies it. The probe also asserts the handshake's
    `serverInfo.name`. This mutation proves that check is load-bearing
    rather than decorative.
    """
    ratchet = _load_ratchet()

    # A well-formed MCP handshake from the WRONG service.
    impostor = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "some-other-service", "version": "1.0.0"},
            },
        }
    )
    with pytest.raises(AssertionError) as excinfo:
        ratchet._assert_responder_is_flute_gateway(
            "http://localhost:8055/mcp", 200, impostor
        )
    assert "serverInfo.name" in str(excinfo.value), (
        "the identity rejection raised, but not with the identity message: "
        f"{excinfo.value!r}"
    )


def test_live_probe_rejects_a_404() -> None:
    """A 404 MUST be rejected -- this is the original defect's symptom."""
    ratchet = _load_ratchet()
    with pytest.raises(AssertionError):
        ratchet._assert_responder_is_flute_gateway(
            "http://localhost:8055/mcp", 404, "Not Found"
        )


def test_live_probe_accepts_the_genuine_flute_gateway() -> None:
    """The control for the live half: the genuine service MUST pass."""
    ratchet = _load_ratchet()
    genuine = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pmoves-flute-gateway", "version": "1.0.0"},
            },
        }
    )
    # Raises on failure, so reaching here IS the pass.
    ratchet._assert_responder_is_flute_gateway(
        "http://localhost:8055/mcp", 200, genuine
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(pytest.main([__file__, "-v"]))
