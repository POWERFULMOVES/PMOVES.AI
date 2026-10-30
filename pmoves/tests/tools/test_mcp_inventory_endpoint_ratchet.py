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
"""

from __future__ import annotations

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

# The MCP surface this ratchet pins. Each entry maps an inventory key to
# (service source file, the route decorator that must declare it).
#
# `flute-voice` is the SSE surface (`GET /sse`, mcp_bridge.py:529) and
# `flute-voice-mcp` is the streamable-http surface (`POST /mcp`,
# mcp_bridge.py:508). BOTH must be present in the source -- the SSE
# surface is what existing consumers use and the HTTP surface is the
# newer one.
EXPECTED_ROUTES: dict[str, tuple[str, str]] = {
    "flute-voice": ("mcp_bridge.py", '@router.get("/sse")'),
    "flute-voice-mcp": ("mcp_bridge.py", '@router.post("/mcp")'),
}

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


@pytest.mark.parametrize("key", sorted(EXPECTED_ROUTES))
def test_inventory_flute_endpoint_is_declared_in_service_source(key: str) -> None:
    """The inventory must not declare a path the serving source omits.

    A path that is only in the inventory is a 404 waiting to happen --
    and it reaches EVERY client that carries the entry, because the
    default `clients: null` means "all clients" (see
    `ServerSpec.supports_client` in `pmoves/tools/mcp_config_generator.py`).
    """
    filename, route_decl = EXPECTED_ROUTES[key]
    source_path = FLUTE_SERVICE_DIR / filename
    assert source_path.exists(), (
        f"{key}: expected the serving source {source_path} to exist -- the "
        f"inventory entry and the service tree have diverged"
    )
    source = source_path.read_text(encoding="utf-8")
    assert route_decl in source, (
        f"{key}: the inventory declares this surface, but "
        f"{_display_path(source_path)} does not declare "
        f"{route_decl!r}. Either the route was removed or the inventory "
        f"entry was added without the serving route -- both are 404s for "
        f"every client that carries the entry."
    )


@pytest.mark.parametrize("key", sorted(EXPECTED_ROUTES))
def test_inventory_flute_route_is_mounted_in_service_app(key: str) -> None:
    """The route must be MOUNTED, not merely declared.

    A route decorator in a module that is never included in the ASGI app
    is the same 404 with an extra step of indirection. This pins the
    mount in `main.py`.
    """
    main_path = FLUTE_SERVICE_DIR / "main.py"
    assert main_path.exists(), f"flute-gateway main.py missing at {main_path}"
    main_source = main_path.read_text(encoding="utf-8")
    assert "create_mcp_router" in main_source, (
        "flute-gateway/main.py does not mount the MCP bridge router "
        "(create_mcp_router). The /sse and /mcp routes exist in "
        "mcp_bridge.py but are never mounted into the ASGI app."
    )
    assert re.search(r"app\.include_router\(", main_source), (
        "flute-gateway/main.py declares create_mcp_router but never calls "
        "app.include_router(...) -- the router is built and discarded."
    )


def test_inventory_flute_mcp_entry_resolves_to_a_path_url() -> None:
    """The `flute_mcp` endpoint prefix must resolve to a URL with a PATH.

    A path is what makes the endpoint assertable (the static half of
    this ratchet) and what makes it probeable (the live half). An entry
    that resolved to a bare host:port would be un-assertable and
    un-probeable, which is exactly the gap that let the stale-container
    defect ship.
    """
    server = _server_by_key("flute-voice-mcp")
    assert server is not None, "flute-voice-mcp entry missing from mcp_inventory.json"
    defaults = _inventory().get("defaults", {})
    prefix = server.get("endpoint_prefix")
    endpoint = server.get("endpoint")
    assert prefix and endpoint, (
        "flute-voice-mcp must declare both endpoint_prefix and endpoint so "
        "its URL resolves from the inventory defaults"
    )
    url = _resolved_url(server, defaults)
    assert url, (
        f"flute-voice-mcp resolves no URL: prefix={prefix!r} "
        f"endpoint={endpoint!r} and defaults has no "
        f"{prefix}_{endpoint}_url key"
    )
    assert "/" in str(url).split("://", 1)[-1], (
        f"flute-voice-mcp URL {url!r} carries no path -- it cannot be "
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
    """
    path = "/" + str(declared_url).split("://", 1)[-1].split("/", 1)[-1]
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

    Skips when the service is not running on this host -- deployment is
    a separate lane from the code lane, and a skip must not be read as
    a pass.
    """
    base = _live_flute_base()
    if base is None:
        pytest.skip(f"flute-gateway is not reachable on localhost:{FLUTE_PORT}")

    server = _server_by_key("flute-voice-mcp")
    assert server is not None
    defaults = _inventory().get("defaults", {})
    declared_url = _resolved_url(server, defaults)
    assert declared_url
    url = _probe_url(declared_url, base)
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
        headers={"Content-Type": "application/json"},
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
