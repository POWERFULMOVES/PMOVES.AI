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
