"""
PMOVES.AI Container Agent (CA)

Docker networking diagnostics + sidecar bridge for multi-node fleet.
Runs on each node to diagnose and report container networking issues.

Endpoints:
  GET  /healthz     — Liveness probe
  GET  /diagnostic  — Full network diagnostic report (JSON)
  POST /diagnostic  — Trigger fresh diagnostic run
  GET  /metrics     — Prometheus metrics
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import socket
import time
from typing import Any, Dict, Tuple

from aiohttp import web

CA_PORT = int(os.environ.get("CA_PORT", "8111"))
NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname())
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats-leaf:4222")

# ── Service Catalog ─────────────────────────────────────────────────────────
# Services reachable from containers on this node's Docker bridge network.
# Tuple: (hostname, port, description)

LOCAL_SERVICES: Dict[str, Tuple[str, int, str]] = {
    "nats-leaf":        ("nats-leaf", 4222, "Local NATS leaf node"),
    "nats-monitor":     ("nats-leaf", 8222, "NATS leaf monitoring"),
    "ollama":           ("pmoves-ollama", 11434, "Ollama LLM server"),
}

UPSTREAM_SERVICES: Dict[str, Tuple[str, int, str]] = {
    "host-gateway":     ("host.docker.internal", 7422, "Host → 5090 NATS leafnode port"),
    "host-nats-client": ("host.docker.internal", 4222, "Host → 5090 NATS client port (proxy)"),
}

DNS_TARGETS = [
    "nats-leaf",
    "pmoves-ollama",
    "host.docker.internal",
    "google.com",
    "github.com",
]

# ── Prometheus Counters ─────────────────────────────────────────────────────

_metrics = {
    "diagnostics_total": 0,
    "diagnostic_errors_total": 0,
    "nats_connected": 0,
    "services_reachable": 0,
    "services_total": 0,
    "dns_resolved": 0,
    "dns_total": 0,
}

# ── Diagnostic Functions ────────────────────────────────────────────────────


def check_dns(hostname: str) -> Dict[str, Any]:
    """Resolve a hostname via container DNS."""
    t0 = time.monotonic()
    try:
        ip = socket.gethostbyname(hostname)
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"hostname": hostname, "resolved": ip, "ms": ms, "ok": True}
    except socket.gaierror as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"hostname": hostname, "error": str(e), "ms": ms, "ok": False}


def check_tcp(host: str, port: int, timeout: float = 2.0) -> Dict[str, Any]:
    """Check TCP connectivity to host:port."""
    t0 = time.monotonic()
    try:
        # Resolve first so we report the actual IP
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        ip = host
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "host": host, "resolved_ip": ip, "port": port,
            "open": result == 0, "ms": ms, "ok": result == 0,
        }
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "host": host, "resolved_ip": ip, "port": port,
            "open": False, "ms": ms, "ok": False, "error": str(e),
        }


async def check_nats() -> Dict[str, Any]:
    """Test NATS client connectivity."""
    t0 = time.monotonic()
    try:
        import nats as nats_client
        nc = await nats_client.connect(servers=[NATS_URL], connect_timeout=3)
        info = {
            "server_id": nc._server_info.get("server_id", ""),
            "server_name": nc._server_info.get("server_name", ""),
            "version": nc._server_info.get("version", ""),
            "jetstream": nc._server_info.get("jetstream", False),
            "leafnode": nc._server_info.get("leafnode", False),
            "connected_url": str(nc.connected_url) if nc.connected_url else NATS_URL,
        }
        await nc.close()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"url": NATS_URL, "connected": True, "ms": ms, "server": info, "ok": True}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"url": NATS_URL, "connected": False, "ms": ms, "error": str(e), "ok": False}


def get_network_info() -> Dict[str, Any]:
    """Gather container network identity."""
    info: Dict[str, Any] = {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "node_name": NODE_NAME,
    }
    # Collect all IPv4 addresses
    try:
        info["ips"] = list({
            addr[4][0]
            for addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        })
    except Exception:
        info["ips"] = []
    # Default gateway (best-effort)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["default_route_src"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["default_route_src"] = None
    return info


async def run_full_diagnostic() -> Dict[str, Any]:
    """Execute complete diagnostic suite."""
    # DNS checks
    dns_results = [check_dns(h) for h in DNS_TARGETS]

    # Service connectivity (local + upstream)
    all_services = {**LOCAL_SERVICES, **UPSTREAM_SERVICES}
    svc_results = {}
    for name, (host, port, desc) in all_services.items():
        result = check_tcp(host, port)
        result["description"] = desc
        result["tier"] = "local" if name in LOCAL_SERVICES else "upstream"
        svc_results[name] = result

    # NATS
    nats_result = await check_nats()

    # Network info
    net_info = get_network_info()

    # Update metrics
    dns_ok = sum(1 for d in dns_results if d["ok"])
    svc_ok = sum(1 for s in svc_results.values() if s["ok"])
    _metrics["dns_resolved"] = dns_ok
    _metrics["dns_total"] = len(dns_results)
    _metrics["services_reachable"] = svc_ok
    _metrics["services_total"] = len(svc_results)
    _metrics["nats_connected"] = 1 if nats_result["ok"] else 0

    # Check upstream services separately for health assessment
    upstream_ok = sum(
        1 for name, s in svc_results.items()
        if s.get("tier") == "upstream" and s["ok"]
    )
    upstream_total = sum(
        1 for name, s in svc_results.items()
        if s.get("tier") == "upstream"
    )

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "node": NODE_NAME,
        "network": net_info,
        "dns": dns_results,
        "services": svc_results,
        "nats": nats_result,
        "summary": {
            "dns": f"{dns_ok}/{len(dns_results)} resolved",
            "services": f"{svc_ok}/{len(svc_results)} reachable",
            "upstream": f"{upstream_ok}/{upstream_total} reachable",
            "nats": "connected" if nats_result["ok"] else "disconnected",
            "healthy": dns_ok > 0 and nats_result["ok"] and upstream_ok > 0,
        },
    }
    return report


# ── HTTP Handlers ───────────────────────────────────────────────────────────

_diagnostic_lock = asyncio.Lock()


async def handle_healthz(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "node": NODE_NAME,
        "ts": int(time.time()),
    })


async def handle_diagnostic(request: web.Request) -> web.Response:
    async with _diagnostic_lock:
        _metrics["diagnostics_total"] += 1
        try:
            report = await run_full_diagnostic()
        except Exception as e:
            _metrics["diagnostic_errors_total"] += 1
            return web.json_response({"error": str(e)}, status=500)
    return web.json_response(report)


async def handle_metrics(request: web.Request) -> web.Response:
    lines = []
    for key, val in _metrics.items():
        prom_name = f"container_agent_{key}"
        prom_type = "gauge" if key in ("nats_connected", "services_reachable",
                                        "services_total", "dns_resolved", "dns_total") else "counter"
        lines.append(f"# TYPE {prom_name} {prom_type}")
        lines.append(f"{prom_name} {val}")
    lines.append("# TYPE container_agent_up gauge")
    lines.append("container_agent_up 1")
    return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")


# ── NATS Heartbeat Loop ────────────────────────────────────────────────────

async def nats_heartbeat_loop():
    """Publish CA presence on NATS every 30s."""
    import nats as nats_client
    nc = None
    while True:
        try:
            if nc is None or not nc.is_connected:
                nc = await nats_client.connect(servers=[NATS_URL], connect_timeout=5)
            msg = {
                "type": "container.agent.heartbeat.v1",
                "node": NODE_NAME,
                "port": CA_PORT,
                "ts": int(time.time()),
                "services_reachable": _metrics.get("services_reachable", 0),
                "services_total": _metrics.get("services_total", 0),
            }
            await nc.publish("mesh.container.agent.v1", json.dumps(msg).encode())
        except Exception:
            nc = None  # will reconnect next iteration
        await asyncio.sleep(30)


# ── Startup / Shutdown ──────────────────────────────────────────────────────

async def on_startup(app: web.Application):
    # Run initial diagnostic on boot
    try:
        report = await run_full_diagnostic()
        healthy = report.get("summary", {}).get("healthy", False)
        svc = report.get("summary", {}).get("services", "?")
        nats_s = report.get("summary", {}).get("nats", "?")
        print(f"[CA] Boot diagnostic: services={svc} nats={nats_s} healthy={healthy}")
    except Exception as e:
        print(f"[CA] Boot diagnostic failed: {e}")
    app["nats_task"] = asyncio.create_task(nats_heartbeat_loop())


async def on_cleanup(app: web.Application):
    task = app.get("nats_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", handle_healthz)
    app.router.add_get("/diagnostic", handle_diagnostic)
    app.router.add_post("/diagnostic", handle_diagnostic)
    app.router.add_get("/metrics", handle_metrics)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    print(f"[CA] Container Agent starting on :{CA_PORT} node={NODE_NAME}")
    web.run_app(create_app(), host="0.0.0.0", port=CA_PORT)
