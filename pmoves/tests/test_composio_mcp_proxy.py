"""Contract for the Composio MCP fleet proxy (supergateway in front of Composio Connect).

The compose files are operator-apply (compose is a Known Road domain the
delivery agent could not open), so their reviewed content lives as fenced blocks
in pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md. These tests pin the contract
on those blocks now, and -- once the operator places the files under
deploy/kvm2/composio-mcp/ -- assert the files are byte-identical to the blocks,
so the doc and the kit cannot drift.

Nothing here starts a container or calls Composio. The smoke tool is exercised
in-process against a stdlib HTTP server on loopback.
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

from pmoves.tools import composio_mcp_smoke as smoke
from pmoves.tools import mcp_config_generator as gen

REPO = Path(__file__).resolve().parents[2]
HANDOFF = REPO / "pmoves" / "docs" / "handoffs" / "COMPOSIO_MCP_SELFHOST.md"
KIT = "deploy/kvm2/composio-mcp/docker-compose.yml"
MESH = "deploy/kvm2/composio-mcp/docker-compose.pmoves-mesh.yml"
INFRA_MK = REPO / "pmoves" / "mk" / "infra.mk"
INVENTORY = REPO / "pmoves" / "config" / "mcp_inventory.json"
ROSTER = REPO / ".claude" / "mcp.json"

PIN = re.compile(r"^supercorp/supergateway:4\.2\.0@sha256:[0-9a-f]{64}$")
LOCAL_URL = "http://127.0.0.1:8190/composio/mcp"


def _handoff() -> str:
    return HANDOFF.read_text(encoding="utf-8")


def _blocks() -> dict[str, str]:
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^```yaml file=(\S+)\n(.*?)^```$", _handoff(), re.S | re.M)
    }


def _default(expr: str) -> str:
    """`${VAR:-default}` -> default (what compose substitutes when VAR is unset)."""
    m = re.fullmatch(r"\$\{[A-Z0-9_]+:-(.*)\}", expr)
    assert m, f"{expr!r} is not a ${{VAR:-default}} reference"
    return m.group(1)


@pytest.fixture(scope="module")
def kit() -> dict:
    return yaml.safe_load(_blocks()[KIT])


@pytest.fixture(scope="module")
def svc(kit: dict) -> dict:
    return kit["services"]["composio-mcp"]


@pytest.fixture(scope="module")
def gateway_config(kit: dict) -> dict:
    # compose turns `$$` into a literal `$` before the file reaches the container
    return json.loads(kit["configs"]["composio_gateway"]["content"].replace("$$", "$"))


def test_handoff_carries_both_kit_files() -> None:
    assert set(_blocks()) == {KIT, MESH}


@pytest.mark.parametrize("rel", [KIT, MESH])
def test_kit_file_matches_handoff_block_once_applied(rel: str) -> None:
    path = REPO / rel
    if not path.exists():
        pytest.skip(f"{rel} not yet placed (operator-apply, see {HANDOFF.name})")
    assert path.read_text(encoding="utf-8") == _blocks()[rel], (
        f"{rel} drifted from its block in {HANDOFF.name}; change both together"
    )


def test_image_pinned_by_tag_and_digest(svc: dict) -> None:
    assert PIN.match(_default(svc["image"])), svc["image"]


def test_published_port_is_loopback_by_default(svc: dict) -> None:
    assert svc["ports"], "the proxy must publish its port for host clients"
    for port in svc["ports"]:
        m = re.fullmatch(r"(\$\{[^}]*\}):(\$\{[^}]*\}):(\d+)", str(port))
        assert m, f"{port!r}: host bind must be an explicit, defaulted variable"
        bind, host_port, container_port = m.groups()
        assert bind == "${COMPOSIO_MCP_BIND:-127.0.0.1}", port
        assert _default(host_port) == "8190" and container_port == "8000", port


def test_healthcheck_probes_the_unauthenticated_gateway_endpoint(svc: dict, gateway_config: dict) -> None:
    test = " ".join(svc["healthcheck"]["test"])
    assert "http://127.0.0.1:8000/healthz" in test
    assert gateway_config["healthEndpoint"] == "/healthz"
    assert gateway_config["port"] == 8000


def test_runs_unprivileged(svc: dict) -> None:
    assert svc["user"] == "1000:1000"
    assert svc["read_only"] is True
    assert svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]


def test_secrets_come_only_from_the_required_env_file(svc: dict) -> None:
    (entry,) = svc["env_file"]
    assert _default(entry["path"]) == "/opt/composio-mcp/.env"
    assert entry["required"] is True
    assert "environment" not in svc, "secrets must not be interpolated into compose"
    assert not re.search(r"\b(ck|ak|uak)_[A-Za-z0-9]{8,}", _blocks()[KIT]), "literal Composio key in the kit"


def test_gateway_config_fails_closed_and_targets_connect(gateway_config: dict) -> None:
    (name, server), = gateway_config["mcpServers"].items()
    assert name == "composio"  # -> served at /composio/mcp
    assert server["type"] == "http"
    assert server["outputTransport"] == "streamableHttp"
    assert _default(server["url"]) == "https://connect.composio.dev/mcp"
    # Bare references: supergateway refuses to start when either is unset, so a
    # missing key can never yield an unauthenticated or keyless proxy.
    assert server["headers"] == {"x-consumer-api-key": "${COMPOSIO_MCP_CONSUMER_KEY}"}
    assert server["apiKey"] == "${COMPOSIO_MCP_GATEWAY_KEY}"


def test_mesh_overlay_only_joins_external_pmoves_app() -> None:
    mesh = yaml.safe_load(_blocks()[MESH])
    assert mesh["services"]["composio-mcp"]["networks"] == ["default", "pmoves_app"]
    assert mesh["networks"] == {"pmoves_app": {"external": True}}
    assert "ports" not in mesh["services"]["composio-mcp"]


def test_a0_entry_is_valid_json_and_ships_disabled() -> None:
    m = re.search(r"^```json a0-entry\n(.*?)\n^```$", _handoff(), re.S | re.M)
    assert m, "A0 entry block missing from the handoff"
    rendered = re.sub(r"\$\{[A-Z0-9_]+:-([^}]*)\}", r"\1", m.group(1))  # compose defaults
    rendered = re.sub(r"\$\{[A-Z0-9_]+\}", "tok", rendered)
    entry = json.loads("{" + rendered + "}")["composio"]
    assert entry["type"] == "streamable-http"
    assert entry["url"] == "http://composio-mcp:8000/composio/mcp"
    assert entry["headers"] == {"Authorization": "Bearer tok"}
    assert entry["disabled"] is True


def test_make_road_exists_and_pins_its_own_project() -> None:
    mk = INFRA_MK.read_text(encoding="utf-8")
    for target in ("composio-mcp-preflight", "up-composio-mcp", "down-composio-mcp", "composio-mcp-smoke"):
        assert re.search(rf"^{re.escape(target)}:", mk, re.M), target
    macro = re.search(r"^COMPOSIO_MCP_DC := (.*?)(?:\n(?!\t)|\Z)", mk, re.M | re.S).group(1)
    assert "docker compose -p composio-mcp" in macro
    assert "deploy/kvm2/composio-mcp" in mk
    assert re.search(r"^COMPOSIO_MCP_PORT \?= 8190$", mk, re.M)
    assert "tools/composio_mcp_smoke.py" in mk


def test_inventory_and_roster_carry_the_local_proxy() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    servers = {s["key"]: s for s in inventory["groups"]["core_pmoves"]["servers"]}
    local = servers["composio-local"]
    assert local["url"] == LOCAL_URL
    assert local["endpoint_pinned"] is True
    assert local["headers"] == {"Authorization": "Bearer ${COMPOSIO_MCP_GATEWAY_KEY}"}
    # the hosted entry is kept, untouched
    assert servers["composio"]["url"] == "https://connect.composio.dev/mcp"

    generated = gen.generate_for_client(
        "claude", inventory=gen.load_inventory(INVENTORY), endpoint="fleet", allow_os_environ=False
    )["mcpServers"]
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["mcpServers"]
    for key in ("composio", "composio-local"):
        for field, value in generated[key].items():
            assert roster[key].get(field) == value, (key, field)


# ---------------------------------------------------------------- smoke tool

KEY = "gw-test-key-should-never-print"


class _FakeProxy(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *args) -> None:  # keep pytest output clean
        pass

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("Authorization") != f"Bearer {KEY}" or self.mode == "401":
            self.send_response(401)
            self.end_headers()
            return
        method = body.get("method")
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if self.mode == "upstream-error":
            reply = {"jsonrpc": "2.0", "id": body.get("id"),
                     "error": {"code": -32603, "message": "MCP server process failed"}}
        elif method == "initialize":
            reply = {"jsonrpc": "2.0", "id": body["id"], "result": {
                "protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                "serverInfo": {"name": "composio", "version": "x"}}}
        else:
            tools = [] if self.mode == "empty" else [
                {"name": n} for n in ("COMPOSIO_SEARCH_TOOLS", "COMPOSIO_MULTI_EXECUTE_TOOL", "COMPOSIO_MANAGE_CONNECTIONS")]
            reply = {"jsonrpc": "2.0", "id": body["id"], "result": {"tools": tools}}
        payload = f"event: message\ndata: {json.dumps(reply)}\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "sess-1")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def proxy():
    server = HTTPServer(("127.0.0.1", 0), _FakeProxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://127.0.0.1:{server.server_address[1]}/composio/mcp"
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize(
    "mode,key,code",
    [("ok", KEY, 0), ("empty", KEY, 1), ("401", KEY, 1), ("upstream-error", KEY, 1), ("ok", "", 3)],
)
def test_smoke_exit_codes(proxy, monkeypatch, capsys, mode, key, code) -> None:
    server, url = proxy
    _FakeProxy.mode = mode
    monkeypatch.setenv("COMPOSIO_MCP_GATEWAY_KEY", key)
    assert smoke.main(["--url", url]) == code
    out = capsys.readouterr()
    assert KEY not in out.out + out.err
    if code == 0:
        assert "tools=3" in out.out


def test_smoke_unreachable_is_unmeasured_not_a_pass(monkeypatch, capsys) -> None:
    server = HTTPServer(("127.0.0.1", 0), _FakeProxy)
    port = server.server_address[1]
    server.server_close()  # nothing listens on this port now
    monkeypatch.setenv("COMPOSIO_MCP_GATEWAY_KEY", KEY)
    assert smoke.main(["--url", f"http://127.0.0.1:{port}/composio/mcp", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "unmeasured"
