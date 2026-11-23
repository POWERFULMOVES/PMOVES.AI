"""
PMOVES.AI Container Agent (CA)

Per-node Docker-networking diagnostics sidecar for the multi-node fleet.

Design rule (2026-11-17): NO node-specific topology in this file. Every host,
port and target is environment-driven, because the previous revision hardcoded
the 5090/z890 layout (`nats-leaf`, `pmoves-ollama`, `host.docker.internal:7422`)
and therefore reported false failures on every other node.

Endpoints:
  GET  /healthz     — Liveness + node identity
  GET  /diagnostic  — Full diagnostic report (JSON)
  POST /diagnostic  — Trigger a fresh diagnostic run
  GET  /metrics     — Prometheus exposition
  GET  /config      — Effective probe configuration (no secrets)
  POST /analyze     — OPTIONAL: Ollama Cloud triage of the latest diagnostic.
                      Returns 503 with an explicit reason when unconfigured.

Configuration (all optional; defaults reproduce the 5090/z890 layout):
  CA_PORT                     int    (default 8111)
  NODE_NAME                   str    (default hostname)
  NATS_URL                    str    (no default — omit to disable NATS probe)
  CA_DNS_TARGETS              JSON list[str]
  CA_LOCAL_SERVICES           JSON list[[name, host, port, description]]
  CA_UPSTREAM_SERVICES        JSON list[[name, host, port, description]]
  CA_REQUIRE_UPSTREAM         "1"/"0" (default "0")
  CA_TIMEOUT_S                float  (default 2.0)
  CA_HEARTBEAT_S              int    (default 30)
  OLLAMA_CLOUD_BASE_URL       str    (enables /analyze)
  OLLAMA_CLOUD_API_KEY        str
  CA_ANALYZE_MODEL            str    (default "gpt-oss:120b")
"""
from __future__ import annotations

import asyncio
import json
import re
import os
import platform
import socket
import time
from typing import Any, Dict, List, Tuple

from aiohttp import ClientSession, ClientTimeout, web

CA_PORT = int(os.environ.get("CA_PORT", "8111"))
NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname())
CA_TIMEOUT_S = float(os.environ.get("CA_TIMEOUT_S", "2.0"))
CA_HEARTBEAT_S = int(os.environ.get("CA_HEARTBEAT_S", "30"))
CA_REQUIRE_UPSTREAM = os.environ.get("CA_REQUIRE_UPSTREAM", "0") == "1"

# Deliberately empty. The previous default embedded a user:password pair in
# source (removed in #3139); do not quote it here either -- the
# no-hardcoded-NATS-credentials gate scans comments too.
# Credentials belong in env/secret stores, never in a repository.
NATS_URL = os.environ.get("NATS_URL", "").strip()

OLLAMA_CLOUD_BASE_URL = os.environ.get("OLLAMA_CLOUD_BASE_URL", "").strip().rstrip("/")
OLLAMA_CLOUD_API_KEY = os.environ.get("OLLAMA_CLOUD_API_KEY", "").strip()
CA_ANALYZE_MODEL = os.environ.get("CA_ANALYZE_MODEL", "gpt-oss:120b").strip()


def _json_env(name: str, default: List[Any]) -> List[Any]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[CA] ignoring malformed {name}: {exc}")
        return default
    return val if isinstance(val, list) else default


# Defaults describe the 5090/z890 topology so that node keeps working unchanged.
DEFAULT_DNS_TARGETS = ["nats-leaf", "pmoves-ollama", "host.docker.internal", "google.com", "github.com"]
DEFAULT_LOCAL = [
    ["nats-leaf", "nats-leaf", 4222, "Local NATS leaf node"],
    ["nats-monitor", "nats-leaf", 8222, "NATS leaf monitoring"],
    ["ollama", "pmoves-ollama", 11434, "Ollama LLM server"],
]
DEFAULT_UPSTREAM = [
    ["host-gateway", "host.docker.internal", 7422, "Host to 5090 NATS leafnode port"],
    ["host-nats-client", "host.docker.internal", 4222, "Host to 5090 NATS client port (proxy)"],
]

DNS_TARGETS: List[str] = [str(x) for x in _json_env("CA_DNS_TARGETS", DEFAULT_DNS_TARGETS)]


def _as_services(raw: List[Any]) -> Dict[str, Tuple[str, int, str]]:
    out: Dict[str, Tuple[str, int, str]] = {}
    for row in raw:
        try:
            name, host, port, desc = row
            out[str(name)] = (str(host), int(port), str(desc))
        except (TypeError, ValueError):
            print(f"[CA] ignoring malformed service row: {row!r}")
    return out


LOCAL_SERVICES = _as_services(_json_env("CA_LOCAL_SERVICES", DEFAULT_LOCAL))
UPSTREAM_SERVICES = _as_services(_json_env("CA_UPSTREAM_SERVICES", DEFAULT_UPSTREAM))

_metrics = {
    "diagnostics_total": 0,
    "diagnostic_errors_total": 0,
    "nats_connected": 0,
    "nats_skipped": 0,
    "services_reachable": 0,
    "services_total": 0,
    "dns_resolved": 0,
    "dns_total": 0,
    "analyze_total": 0,
    "analyze_errors_total": 0,
}

_last_report: Dict[str, Any] = {}


# ── Probes ──────────────────────────────────────────────────────────────────

def check_dns(hostname: str) -> Dict[str, Any]:
    t0 = time.monotonic()
    try:
        ip = socket.gethostbyname(hostname)
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"hostname": hostname, "resolved": ip, "ms": ms, "ok": True}
    except socket.gaierror as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"hostname": hostname, "error": str(e), "ms": ms, "ok": False}


def check_tcp(host: str, port: int, timeout: float | None = None) -> Dict[str, Any]:
    timeout = CA_TIMEOUT_S if timeout is None else timeout
    t0 = time.monotonic()
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        ip = host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"host": host, "resolved_ip": ip, "port": port,
                "open": result == 0, "ms": ms, "ok": result == 0}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"host": host, "resolved_ip": ip, "port": port,
                "open": False, "ms": ms, "ok": False, "error": str(e)}


async def check_nats() -> Dict[str, Any]:
    """Probe NATS only when NATS_URL is configured."""
    if not NATS_URL:
        _metrics["nats_skipped"] = 1
        return {"url": None, "connected": False, "skipped": True,
                "reason": "NATS_URL not set", "ok": True, "ms": 0.0}
    t0 = time.monotonic()
    try:
        import nats as nats_client
        nc = await nats_client.connect(servers=[NATS_URL], connect_timeout=3)
        info = getattr(nc, "_server_info", {}) or {}
        out = {
            "server_id": info.get("server_id", ""),
            "server_name": info.get("server_name", ""),
            "version": info.get("version", ""),
            "jetstream": info.get("jetstream", False),
            "leafnode": info.get("leafnode", False),
            "connected_url": str(getattr(nc, "connected_url", "") or NATS_URL),
        }
        await nc.close()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"url": NATS_URL, "connected": True, "ms": ms, "server": out, "ok": True}
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000, 1)
        return {"url": NATS_URL, "connected": False, "ms": ms, "error": str(e), "ok": False}


def get_network_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "node_name": NODE_NAME,
    }
    try:
        info["ips"] = sorted({
            addr[4][0]
            for addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        })
    except Exception:
        info["ips"] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            info["default_route_src"] = s.getsockname()[0]
    except Exception:
        info["default_route_src"] = None
    return info


async def run_full_diagnostic() -> Dict[str, Any]:
    dns_results = [check_dns(h) for h in DNS_TARGETS]

    all_services = {**LOCAL_SERVICES, **UPSTREAM_SERVICES}
    svc_results: Dict[str, Any] = {}
    for name, (host, port, desc) in all_services.items():
        result = check_tcp(host, port)
        result["description"] = desc
        result["tier"] = "local" if name in LOCAL_SERVICES else "upstream"
        svc_results[name] = result

    nats_result = await check_nats()
    net_info = get_network_info()

    local_ok = sum(1 for n, s in svc_results.items() if s["tier"] == "local" and s["ok"])
    local_total = sum(1 for s in svc_results.values() if s["tier"] == "local")
    upstream_ok = sum(1 for s in svc_results.values() if s["tier"] == "upstream" and s["ok"])
    upstream_total = sum(1 for s in svc_results.values() if s["tier"] == "upstream")
    dns_ok = sum(1 for d in dns_results if d["ok"])

    _metrics["dns_resolved"] = dns_ok
    _metrics["dns_total"] = len(dns_results)
    _metrics["services_reachable"] = sum(1 for s in svc_results.values() if s["ok"])
    _metrics["services_total"] = len(svc_results)
    _metrics["nats_connected"] = 1 if nats_result.get("connected") else 0

    # Health semantics (corrected): a node is healthy when its REQUIRED probes pass.
    # Upstream reachability is optional because edge/laptop nodes legitimately have
    # no upstream path -- the old rule `upstream_ok > 0` marked those nodes unhealthy
    # forever. A node with zero configured local services is not judged on them.
    required_pass = (local_total == 0) or (local_ok == local_total)
    nats_pass = nats_result.get("ok", False)
    upstream_pass = (not CA_REQUIRE_UPSTREAM) or (upstream_total == 0) or (upstream_ok > 0)
    healthy = bool(required_pass and nats_pass and upstream_pass)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "node": NODE_NAME,
        "network": net_info,
        "config": {
            "local_services": len(LOCAL_SERVICES),
            "upstream_services": len(UPSTREAM_SERVICES),
            "dns_targets": len(DNS_TARGETS),
            "nats_probe": bool(NATS_URL),
            "require_upstream": CA_REQUIRE_UPSTREAM,
            "analyze_enabled": bool(OLLAMA_CLOUD_BASE_URL and OLLAMA_CLOUD_API_KEY),
        },
        "dns": dns_results,
        "services": svc_results,
        "nats": nats_result,
        "summary": {
            "dns": f"{dns_ok}/{len(dns_results)} resolved",
            "local": f"{local_ok}/{local_total} reachable",
            "upstream": f"{upstream_ok}/{upstream_total} reachable",
            "nats": ("skipped" if nats_result.get("skipped")
                     else "connected" if nats_result.get("connected") else "disconnected"),
            "healthy": healthy,
            "rule": ("healthy = all local probes pass AND nats passes "
                     "AND (upstream optional unless CA_REQUIRE_UPSTREAM=1)"),
        },
    }
    _last_report.clear()
    _last_report.update(report)
    return report


# ── Optional Ollama Cloud triage ────────────────────────────────────────────

def analyze_available() -> Tuple[bool, str]:
    if not OLLAMA_CLOUD_BASE_URL:
        return False, "OLLAMA_CLOUD_BASE_URL is not set"
    if not OLLAMA_CLOUD_API_KEY:
        return False, "OLLAMA_CLOUD_API_KEY is not set"
    return True, ""


async def analyze_report(report: Dict[str, Any]) -> Dict[str, Any]:
    ok, why = analyze_available()
    if not ok:
        return {"ok": False, "reason": why}

    system = (
        "You are a Docker networking diagnostician for the PMOVES.AI fleet. "
        "You receive a JSON diagnostic report from one node. Answer in at most "
        "6 short bullet points: likely cause, what to check next, and whether "
        "this looks like a config defect, a runtime fault, or a correct-but-"
        "isolated node. Do not invent hosts that are not in the report."
    )
    payload = {
        "model": CA_ANALYZE_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(_redact(report), separators=(",", ":"))},
        ],
        "stream": False,
    }
    # The documented base (https://ollama.com/v1) is OpenAI-compatible; a bare
    # host (https://ollama.com) speaks the native /api/chat contract.
    openai_compat = OLLAMA_CLOUD_BASE_URL.endswith("/v1")
    url = (f"{OLLAMA_CLOUD_BASE_URL}/chat/completions" if openai_compat
           else f"{OLLAMA_CLOUD_BASE_URL}/api/chat")
    headers = {"Authorization": f"Bearer {OLLAMA_CLOUD_API_KEY}",
               "Content-Type": "application/json"}
    _metrics["analyze_total"] += 1
    try:
        async with ClientSession(timeout=ClientTimeout(total=60)) as sess:
            async with sess.post(url, json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status != 200:
                    _metrics["analyze_errors_total"] += 1
                    return {"ok": False, "status": resp.status,
                            "reason": f"ollama cloud returned {resp.status}",
                            "body": body[:400]}
                data = json.loads(body)
        if openai_compat:
            choice = (data.get("choices") or [{}])[0]
            message = (choice.get("message") or {}).get("content", "")
        else:
            message = (data.get("message") or {}).get("content", "")
        return {"ok": True, "model": CA_ANALYZE_MODEL, "analysis": message.strip(),
                "raw_meta": {k: data.get(k) for k in ("done", "eval_count", "prompt_eval_count")}}
    except Exception as e:
        _metrics["analyze_errors_total"] += 1
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


_USERINFO_RE = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")


def _redact(obj):
    """Strip URL userinfo (user:password@) from every string in a report.

    The diagnostic report carries NATS_URL verbatim; /analyze ships the report
    to an external model, so credentials must never ride along."""
    if isinstance(obj, str):
        return _USERINFO_RE.sub(r"\g<scheme>***@", obj)
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


# ── HTTP handlers ───────────────────────────────────────────────────────────

_diagnostic_lock = asyncio.Lock()


async def handle_healthz(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "node": NODE_NAME, "ts": int(time.time())})


async def handle_config(request: web.Request) -> web.Response:
    return web.json_response({
        "node": NODE_NAME,
        "port": CA_PORT,
        "dns_targets": DNS_TARGETS,
        "local_services": {k: {"host": v[0], "port": v[1], "description": v[2]}
                           for k, v in LOCAL_SERVICES.items()},
        "upstream_services": {k: {"host": v[0], "port": v[1], "description": v[2]}
                              for k, v in UPSTREAM_SERVICES.items()},
        "require_upstream": CA_REQUIRE_UPSTREAM,
        "nats_probe_enabled": bool(NATS_URL),
        "analyze_enabled": analyze_available()[0],
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


async def handle_analyze(request: web.Request) -> web.Response:
    ok, why = analyze_available()
    if not ok:
        return web.json_response(
            {"ok": False, "reason": why,
             "hint": "set OLLAMA_CLOUD_BASE_URL and OLLAMA_CLOUD_API_KEY to enable triage"},
            status=503)
    async with _diagnostic_lock:
        report = dict(_last_report) or await run_full_diagnostic()
    result = await analyze_report(report)
    return web.json_response(result, status=200 if result.get("ok") else 502)


async def handle_metrics(request: web.Request) -> web.Response:
    gauges = {"nats_connected", "nats_skipped", "services_reachable", "services_total",
              "dns_resolved", "dns_total"}
    lines: List[str] = []
    for key, val in _metrics.items():
        prom_name = f"container_agent_{key}"
        prom_type = "gauge" if key in gauges else "counter"
        lines.append(f"# TYPE {prom_name} {prom_type}")
        lines.append(f"{prom_name} {val}")
    lines.append("# TYPE container_agent_up gauge")
    lines.append("container_agent_up 1")
    return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")


# ── NATS heartbeat ──────────────────────────────────────────────────────────

async def nats_heartbeat_loop() -> None:
    if not NATS_URL:
        return
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
            nc = None
        await asyncio.sleep(CA_HEARTBEAT_S)


# ── Lifecycle ───────────────────────────────────────────────────────────────

async def on_startup(app: web.Application) -> None:
    try:
        report = await run_full_diagnostic()
        summary = report.get("summary", {})
        print(f"[CA] Boot diagnostic: local={summary.get('local')} "
              f"upstream={summary.get('upstream')} nats={summary.get('nats')} "
              f"healthy={summary.get('healthy')}")
    except Exception as e:
        print(f"[CA] Boot diagnostic failed: {e}")
    app["nats_task"] = asyncio.create_task(nats_heartbeat_loop())


async def on_cleanup(app: web.Application) -> None:
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
    app.router.add_get("/config", handle_config)
    app.router.add_get("/diagnostic", handle_diagnostic)
    app.router.add_post("/diagnostic", handle_diagnostic)
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_post("/analyze", handle_analyze)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    print(f"[CA] Container Agent starting on :{CA_PORT} node={NODE_NAME}")
    web.run_app(create_app(), host="0.0.0.0", port=CA_PORT)
