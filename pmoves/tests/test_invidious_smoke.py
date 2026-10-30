"""Hermetic tests for tools/invidious_smoke.py against local stub servers.

The stubs model the vendor behaviour the smoke relies on: Invidious serves
/api/v1/stats, the companion serves /healthz and bearer-guards
/companion/youtubei/v1/* with SERVER_SECRET_KEY. Keys are invented.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[1] / "tools" / "invidious_smoke.py"
_spec = importlib.util.spec_from_file_location("invidious_smoke_under_test", _MOD)
smoke = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = smoke
_spec.loader.exec_module(smoke)

SERVER_KEY = "a1b2c3d4e5f60718"


def _serve(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


class _Quiet(BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass

    def _send(self, code, body=b""):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Invidious(_Quiet):
    def do_GET(self):
        if self.path == "/api/v1/stats":
            self._send(200, json.dumps({"software": {"name": "invidious"}}).encode())
        else:
            self._send(404)


def _companion(key):
    class Companion(_Quiet):
        def do_GET(self):
            if self.path == "/healthz":
                return self._send(200, b"OK")
            if self.path.startswith("/companion/youtubei/v1/"):
                if self.headers.get("Authorization") != f"Bearer {key}":
                    return self._send(401)
                return self._send(404)  # authorised, but no GET route
            return self._send(404)
    return Companion


@pytest.fixture
def stack():
    servers = []

    def start(companion_key):
        inv, inv_url = _serve(Invidious)
        comp, comp_url = _serve(_companion(companion_key))
        servers.extend([inv, comp])
        return ["--invidious-url", inv_url, "--companion-url", comp_url]

    yield start
    for s in servers:
        s.shutdown()


def test_clean_when_keys_agree(stack, monkeypatch, capsys):
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", SERVER_KEY)
    assert smoke.main(stack(SERVER_KEY)) == 0
    assert SERVER_KEY not in capsys.readouterr().out


def test_finding_when_companion_holds_a_different_key(stack, monkeypatch, capsys):
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", SERVER_KEY)
    assert smoke.main(stack("ffffffffffffffff")) == 1
    out = capsys.readouterr().out
    assert "up-invidious" in out and SERVER_KEY not in out


def test_could_not_measure_without_the_key(stack, monkeypatch):
    monkeypatch.delenv("INVIDIOUS_COMPANION_KEY", raising=False)
    assert smoke.main(stack(SERVER_KEY)) == 3


def test_could_not_measure_when_unreachable(monkeypatch):
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", SERVER_KEY)
    assert smoke.main(["--invidious-url", "http://127.0.0.1:9", "--companion-url", "http://127.0.0.1:9"]) == 3
