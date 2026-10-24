"""FlOO$ health checks must not pass on a web app's catch-all page.

On SPARK, :8091 is Archon's UI. Its catch-all route answers /healthz with the
app's index.html and HTTP 200, so FlOO$ reported graphiti-trail-sync and
a2ui-chart healthy without reaching either service.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pmoves.tools.chit.floos_resolver import check_health


def _serve(status: int, body: bytes, ctype: str):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/healthz"


@pytest.mark.parametrize("body,ctype", [
    (b'{"status":"ok"}', "application/json"),
    (b"ok", "text/plain"),
])
def test_real_health_endpoints_pass(body, ctype):
    srv, url = _serve(200, body, ctype)
    try:
        assert check_health(url)[0] is True
    finally:
        srv.shutdown()


@pytest.mark.parametrize("ctype", ["text/html", "text/html; charset=utf-8"])
def test_an_html_page_is_not_a_health_endpoint(ctype):
    srv, url = _serve(200, b"<!doctype html><html><head></head></html>", ctype)
    try:
        healthy, msg = check_health(url)
        assert healthy is False and "HTML" in msg
    finally:
        srv.shutdown()


def test_html_body_without_html_content_type_is_also_rejected():
    srv, url = _serve(200, b"\n  <!DOCTYPE html>\n<html lang=en>", "application/octet-stream")
    try:
        assert check_health(url)[0] is False
    finally:
        srv.shutdown()


def test_server_errors_fail():
    srv, url = _serve(503, b'{"status":"down"}', "application/json")
    try:
        assert check_health(url)[0] is False
    finally:
        srv.shutdown()


# --- mesh-only services: refused on the host, healthy in Docker ---------------
# On SPARK qdrant, neo4j, meilisearch and consciousness expose their ports only on
# the compose mesh. A host TCP probe is refused although Docker reports them
# healthy, so validate --live called a running pipeline down.

import subprocess as _sp

from pmoves.tools.chit import floos_resolver as fr

PS = ("pmoves-qdrant-1\t6333-6334/tcp\tUp 2 days (healthy)\n"
      "pmoves-consciousness-service-1\t8106/tcp\tUp 2 days (healthy)\n"
      "pmoves-broken-1\t9911/tcp\tUp 3 minutes (unhealthy)\n"
      "pmoves-plain-1\t9912/tcp\tUp 1 hour\n")


def _fake_ps(monkeypatch, out=PS, rc=0):
    monkeypatch.setattr(fr.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(fr.subprocess, "run",
                        lambda *a, **k: _sp.CompletedProcess(a, rc, stdout=out, stderr=""))


@pytest.mark.parametrize("port,expect", [(6333, True), (6334, True), (8106, True),
                                         (9911, False), (9912, True)])
def test_docker_health_by_exposed_port(monkeypatch, port, expect):
    _fake_ps(monkeypatch)
    healthy, msg = fr.docker_port_health(port)
    assert healthy is expect and "mesh-only" in msg


def test_unknown_port_or_no_docker_gives_no_verdict(monkeypatch):
    _fake_ps(monkeypatch)
    assert fr.docker_port_health(7777) is None
    monkeypatch.setattr(fr.shutil, "which", lambda name: None)
    assert fr.docker_port_health(6333) is None


def test_refused_service_port_falls_back_to_docker(monkeypatch):
    _fake_ps(monkeypatch)
    monkeypatch.setattr(fr.socket, "socket", _RefusingSocket)
    assert fr.check_service_port("qdrant:6333")[0] is True
    assert fr.check_service_port("broken:9911")[0] is False


def test_refused_health_url_falls_back_to_docker(monkeypatch):
    _fake_ps(monkeypatch)
    healthy, msg = check_health("http://127.0.0.1:8106/healthz", timeout=1)
    assert healthy is True and "mesh-only" in msg


class _RefusingSocket:
    def __init__(self, *a, **k):
        pass

    def settimeout(self, t):
        pass

    def connect_ex(self, addr):
        return 111

    def close(self):
        pass
