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
2. MUTATES the copy (removes the route decorator, or removes the
   router mount),
3. repoints the ratchet module's own module-level constants at the
   mutated copy,
4. calls the ratchet's OWN test functions and asserts they RAISE.

The mutated copy is what makes the mutation honest: the ratchet reads
whatever tree it is pointed at, so pointing it at a tree with the route
deleted is exactly the state that must be rejected.

The original defect is preserved here as the mutation, so the harness
keeps the historical failure mode alive and watchable.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RATCHET_MODULE = "pmoves.tests.tools.test_mcp_inventory_endpoint_ratchet"

# The route declaration the ratchet requires, and the mutation that
# removes it. This is the ORIGINAL defect shape: the source no longer
# declares the route the inventory promises.
ROUTE_DECL = '@router.post("/mcp")'
MUTATED_ROUTE_DECL = '@router.post("/mcp_DISABLED")'

# The mount that makes the declared route reachable at all.
MOUNT_CALL = "app.include_router("
MUTATED_MOUNT_CALL = "app.include_router_DISABLED("


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


def _mutated_service_tree(tmp_path: Path, *, drop_route: bool, drop_mount: bool) -> Path:
    """Copy the flute-gateway tree and apply the requested mutation."""
    ratchet = _load_ratchet()
    source_dir = Path(ratchet.FLUTE_SERVICE_DIR)
    dest = tmp_path / "flute-gateway"
    shutil.copytree(source_dir, dest)

    if drop_route:
        bridge = dest / "mcp_bridge.py"
        text = bridge.read_text(encoding="utf-8")
        assert ROUTE_DECL in text, "mutation setup failed: route decl not found"
        bridge.write_text(text.replace(ROUTE_DECL, MUTATED_ROUTE_DECL), encoding="utf-8")

    if drop_mount:
        main = dest / "main.py"
        text = main.read_text(encoding="utf-8")
        assert MOUNT_CALL in text, "mutation setup failed: include_router not found"
        main.write_text(text.replace(MOUNT_CALL, MUTATED_MOUNT_CALL), encoding="utf-8")

    return dest


def _point_ratchet_at(ratchet, service_dir: Path):
    """Repoint the ratchet's own constants at the mutated tree."""
    ratchet.FLUTE_SERVICE_DIR = service_dir


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
    """
    ratchet = _load_ratchet()
    mutated = _mutated_service_tree(tmp_path, drop_route=False, drop_mount=True)
    _point_ratchet_at(ratchet, mutated)

    with pytest.raises(AssertionError):
        ratchet.test_inventory_flute_route_is_mounted_in_service_app("flute-voice-mcp")


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
