#!/usr/bin/env python3
"""Agent Zero smoke checks — PMOVES supervisor surface (services/agent-zero/main.py).

Route/schema ground truth re-verified against source on 2026-09-05:

  main.py:821  GET  /healthz            -> 200 {status, command, pid, last_returncode, nats[, runtime]}
                                           503 + same body when the inner runtime is down.
                                           NOTE: /healthz has NO `form` / `default_form` key. Never had one.
  main.py:867  GET  /config/environment -> AgentZeroServiceConfig (non-empty)
  main.py:872  GET  /mcp/commands       -> {default_form, forms_dir, runtime, commands}
                                           commands = mcp_server.list_commands() -> [{name, description}]
  main.py:891  POST /mcp/execute        -> MCPExecuteResponse {cmd, result}
                                           body = MCPExecuteRequest {cmd: str, arguments: dict}  (main.py:608)
                                           form.get -> {"form": <form>}  (mcp_server.py:698)

Port ground truth (docker-compose.yml:3438-3439):
    ${AGENT_ZERO_PORT:-8080}:8080   <- THIS supervisor REST API
    ${AGENT_ZERO_UI_PORT:-8081}:80  <- the A0 UI/runtime. Probing 8081 measures the wrong service.

There is NO `/mcp` route, and no `/mcp/command`, `/mcp/health`, `/mcp/agents`,
`/mcp/task/{id}` or `/mcp/subordinate/create`. Those appear only in
.claude/context/mcp-api.md and .claude/context/agent-zero-orchestration.md, both
of which are SUPERSEDED and describe endpoints that were never implemented.
Canonical reference: pmoves/docs/operations/AGENT_ZERO_API.md.

Auth: the core routes take no inbound auth. Do NOT send MCP_CLIENT_SECRET —
nothing reads it (it exists only because brand_defaults.py auto-generates one).

Env:
  AGENT_ZERO_SUPERVISOR_URL  full base URL; wins if set
  AGENT_ZERO_PORT            host port from compose (default 8080), used to build the default base

Modes: health | mcp-list | mcp-exec | selftest

`selftest` is the POSITIVE CONTROL. It runs every probe against an in-process
stub that implements the contract above, asserts they go green, and then runs
them against deliberately-broken stubs (each encoding one historical defect)
and asserts they go RED. It needs no running Agent Zero, so "no findings" stays
distinguishable from "measured nothing".
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Exit codes — distinct so a CI log says which probe failed, not just "1".
EXIT_UNREACHABLE = 2  # transport failed: nothing was measured
EXIT_CONTRACT = 3  # service answered, but not the documented contract
EXIT_DEGRADED = 4  # service answered and reported itself unhealthy


def _default_base() -> str:
    explicit = os.environ.get("AGENT_ZERO_SUPERVISOR_URL")
    if explicit:
        return explicit.rstrip("/")
    # Mirror compose: ${AGENT_ZERO_PORT:-8080} publishes the supervisor.
    port = os.environ.get("AGENT_ZERO_PORT") or "8080"
    return f"http://localhost:{port}"


BASE = _default_base()


class SmokeFailure(SystemExit):
    """A probe turned red. Carries a distinct exit code."""

    def __init__(self, message: str, code: int = EXIT_CONTRACT) -> None:
        super().__init__(code)
        self.message = message
        print(f"✗ {message}", file=sys.stderr)


def _request(path: str, payload: dict | None = None) -> dict:
    """Issue a request and return the decoded JSON body, or turn red trying.

    urlopen raises HTTPError on any non-2xx, so a bare `resp.status != 200`
    guard is unreachable dead code. Both branches are handled explicitly here
    so a 204/302/422 cannot slip through as a pass.
    """
    url = f"{BASE}{path}"
    if payload is None:
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()[:300]
        except Exception:  # noqa: BLE001 - body is best-effort context only
            pass
        if exc.code == 503:
            raise SmokeFailure(
                f"{path} -> HTTP 503: supervisor is up but reports itself degraded. {body}",
                EXIT_DEGRADED,
            ) from exc
        if exc.code == 404:
            raise SmokeFailure(
                f"{path} -> HTTP 404: route not registered on this service. "
                f"Check the port — {BASE} may be the A0 UI (8081), not the supervisor (8080). {body}"
            ) from exc
        if exc.code == 422:
            raise SmokeFailure(
                f"{path} -> HTTP 422: request body rejected by the endpoint schema. {body}"
            ) from exc
        raise SmokeFailure(f"{path} -> HTTP {exc.code}. {body}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFailure(
            f"{path} -> unreachable at {BASE}: {exc.reason}. NOT a pass — nothing was measured.",
            EXIT_UNREACHABLE,
        ) from exc

    if status != 200:
        raise SmokeFailure(f"{path} -> HTTP {status}, expected 200")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(
            f"{path} -> body is not JSON ({exc}). First 120 bytes: {raw[:120]!r}. "
            "An HTML body here means the probe hit the A0 UI, not the supervisor API."
        ) from exc
    if not isinstance(data, dict):
        raise SmokeFailure(f"{path} -> expected a JSON object, got {type(data).__name__}")
    return data


def health() -> None:
    """GET /healthz + GET /config/environment against the supervisor."""
    data = _request("/healthz")
    # Assert the real /healthz contract (main.py:821-858) — not a `form`, which
    # this endpoint has never returned.
    for key in ("status", "nats"):
        if key not in data:
            raise SmokeFailure(
                f"/healthz 200 but missing required key {key!r}: {json.dumps(data)[:200]}. "
                "This is not the Agent Zero supervisor payload."
            )
    if data.get("status") != "ok":
        raise SmokeFailure(
            f"/healthz reports status={data.get('status')!r} (expected 'ok'): {json.dumps(data)[:200]}",
            EXIT_DEGRADED,
        )
    nats = data.get("nats") or {}
    print(
        f"✔ /healthz 200 status=ok nats.connected={nats.get('connected')} pid={data.get('pid')}"
    )

    cfg = _request("/config/environment")
    if not cfg:
        raise SmokeFailure("/config/environment returned an empty object")
    print(f"✔ /config/environment non-empty ({len(cfg)} keys)")


def mcp_list() -> None:
    """GET /mcp/commands — the registered listing route. There is no bare /mcp."""
    data = _request("/mcp/commands")
    cmds = data.get("commands")
    if not isinstance(cmds, list) or not cmds:
        raise SmokeFailure(f"/mcp/commands returned no commands: {json.dumps(data)[:200]}")
    names = []
    for entry in cmds:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise SmokeFailure(
                f"/mcp/commands entry is not {{name, description}}: {json.dumps(entry)[:120]}"
            )
        names.append(entry["name"])

    # default_form is the CHIT persona form and it lives HERE, not on /healthz.
    # Reporting "MISSING" and exiting 0 would make this a check that cannot fail.
    form = data.get("default_form")
    if not form:
        raise SmokeFailure(
            f"/mcp/commands has no default_form (got {form!r}) — the supervisor has no "
            f"configured CHIT persona form. Payload: {json.dumps(data)[:200]}"
        )
    print(
        f"✔ /mcp/commands: {len(names)} commands, default_form={form!r} "
        f"(sample: {', '.join(names[:5])})"
    )


def mcp_exec() -> None:
    """POST /mcp/execute with the MCPExecuteRequest schema: {cmd, arguments}."""
    data = _request("/mcp/execute", {"cmd": "form.get", "arguments": {}})
    if data.get("cmd") != "form.get":
        raise SmokeFailure(
            f"/mcp/execute echoed cmd={data.get('cmd')!r}, expected 'form.get': {json.dumps(data)[:200]}"
        )
    result = data.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"/mcp/execute result is not an object: {json.dumps(data)[:200]}")
    # form.get returns {"form": <form>} (mcp_server.py:698). Assert exactly that —
    # no `or data.get(...)` fallback chains, which only widen what counts as a pass.
    form = result.get("form")
    if not isinstance(form, dict) or not form:
        raise SmokeFailure(
            f"form.get returned no usable form (got {type(form).__name__}): {json.dumps(data)[:200]}"
        )
    print(
        f"✔ form.get via /mcp/execute ok — CHIT persona form present "
        f"({json.dumps(form)[:80]}…)"
    )


# ---------------------------------------------------------------------------
# Positive control
# ---------------------------------------------------------------------------

PROBES = {"health": health, "mcp-list": mcp_list, "mcp-exec": mcp_exec}

# A payload set that mirrors the real supervisor.
GOOD_ROUTES: dict = {
    ("GET", "/healthz"): (
        200,
        {
            "status": "ok",
            "command": "python run_ui.py",
            "pid": 42,
            "last_returncode": None,
            "nats": {"url": "nats://stub:4222", "connected": True},
        },
    ),
    ("GET", "/config/environment"): (
        200,
        {"agent_form": "pmoves.default", "nats_url": "nats://stub:4222"},
    ),
    ("GET", "/mcp/commands"): (
        200,
        {
            "default_form": "pmoves.default",
            "forms_dir": "/forms",
            "runtime": {},
            "commands": [
                {"name": "form.get", "description": "Return the currently configured MCP form"},
                {"name": "form.switch", "description": "Switch the active MCP form"},
            ],
        },
    ),
    ("POST", "/mcp/execute"): (
        200,
        {"cmd": "form.get", "result": {"form": {"name": "pmoves.default"}}},
    ),
}


def _serve(routes: dict):
    """Start a stub supervisor on an ephemeral port. Returns (server, base_url)."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # keep the smoke output clean
            pass

        def _reply(self, method: str) -> None:
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
            entry = routes.get((method, self.path))
            if entry is None:
                body = b'{"detail":"Not Found"}'
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            status, payload = entry
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming
            self._reply("GET")

        def do_POST(self) -> None:  # noqa: N802 - stdlib naming
            self._reply("POST")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _run_against(routes: dict, probe: str, serve: bool = True):
    """Run one probe against a stub. Returns (went_green, detail)."""
    global BASE
    saved = BASE
    server = None
    try:
        if serve:
            server, base = _serve(routes)
        else:
            # Bind and immediately close, so the port is real but nothing listens.
            import socket

            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            base = f"http://127.0.0.1:{sock.getsockname()[1]}"
            sock.close()
        BASE = base
        PROBES[probe]()
        return True, "green"
    except SystemExit as exc:
        return False, f"red(exit={exc.code}) {getattr(exc, 'message', '')}"
    except Exception as exc:  # noqa: BLE001 - any escape is still a red
        return False, f"red(unhandled {type(exc).__name__}) {exc}"
    finally:
        BASE = saved
        if server is not None:
            server.shutdown()
            server.server_close()


def selftest() -> None:
    """Prove the probes work: green on the real contract, red on each known defect.

    Without this, a smoke that silently measured nothing is indistinguishable
    from one that found no problems.
    """
    failures = []

    print("— positive control: probes must go GREEN against the documented contract —")
    for probe in PROBES:
        ok, detail = _run_against(GOOD_ROUTES, probe)
        print(f"  {'✔' if ok else '✗'} {probe}: {detail}")
        if not ok:
            failures.append(f"{probe} failed against a compliant stub: {detail}")

    # Each negative encodes a defect this tool has actually shipped with.
    negatives = [
        (
            "wrong port (8081 A0 UI serves HTML, not the supervisor API)",
            "health",
            {**GOOD_ROUTES, ("GET", "/healthz"): (200, b"<!doctype html><title>Agent Zero</title>")},
            True,
        ),
        (
            "supervisor degraded (/healthz status != ok)",
            "health",
            {
                **GOOD_ROUTES,
                ("GET", "/healthz"): (200, {"status": "stopped", "nats": {"connected": False}}),
            },
            True,
        ),
        (
            "healthz carries no form (it never did — must not be asserted there)",
            "health",
            {**GOOD_ROUTES, ("GET", "/healthz"): (200, {"nats": {}})},
            True,
        ),
        (
            "legacy bare /mcp route only (/mcp/commands 404s)",
            "mcp-list",
            {k: v for k, v in GOOD_ROUTES.items() if k != ("GET", "/mcp/commands")},
            True,
        ),
        (
            "commands listed but default_form missing (the cannot-fail regression)",
            "mcp-list",
            {
                **GOOD_ROUTES,
                ("GET", "/mcp/commands"): (
                    200,
                    {"default_form": None, "commands": [{"name": "form.get", "description": "d"}]},
                ),
            },
            True,
        ),
        (
            "legacy {'command': ...} schema rejected with 422",
            "mcp-exec",
            {**GOOD_ROUTES, ("POST", "/mcp/execute"): (422, {"detail": "field required: cmd"})},
            True,
        ),
        (
            "form.get returns an empty form",
            "mcp-exec",
            {**GOOD_ROUTES, ("POST", "/mcp/execute"): (200, {"cmd": "form.get", "result": {"form": {}}})},
            True,
        ),
        ("service down entirely (connection refused)", "health", {}, False),
    ]

    print("— negative control: probes must go RED on each known defect —")
    for label, probe, routes, serve in negatives:
        ok, detail = _run_against(routes, probe, serve=serve)
        print(f"  {'✗' if ok else '✔'} {probe} / {label}: {detail}")
        if ok:
            failures.append(f"{probe} stayed GREEN against '{label}' — this check cannot fail")

    if failures:
        for item in failures:
            print(f"✗ {item}", file=sys.stderr)
        raise SystemExit(EXIT_CONTRACT)
    print(
        f"✔ selftest: {len(PROBES)} probes green on contract, "
        f"{len(negatives)} defects all caught red"
    )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "health"
    if mode == "selftest":
        selftest()
        return
    fn = PROBES.get(mode)
    if not fn:
        raise SystemExit(f"unknown mode: {mode} ({'|'.join(PROBES)}|selftest)")
    fn()


if __name__ == "__main__":
    main()
