"""geometry_bus._safe_url must keep credentials out of listener-start logs.

The NATS URL carries user:password and the Supabase realtime URL can carry an
apikey query parameter; both used to be logged verbatim at INFO.

The helper is extracted from the module source with ``ast`` so the test does
not need the gateway's heavy import-time stubs.
"""

import ast
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pytest

_SRC = Path(__file__).resolve().parents[1] / "geometry_bus.py"


def _load_safe_url():
    tree = ast.parse(_SRC.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_safe_url")
    ns = {"urlparse": urlparse, "Optional": Optional}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(_SRC), "exec"), ns)
    return ns["_safe_url"]


_safe_url = _load_safe_url()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # user:pass is the credential scanner's sanctioned placeholder pair.
        ("nats://user:pass@nats:4222", "nats://nats:4222"),
        ("nats://nats:4222", "nats://nats:4222"),
        ("wss://db.example.test/realtime/v1/websocket?apikey=abc.def&vsn=1.0.0", "wss://db.example.test/realtime/v1/websocket"),
        ("", ""),
        (None, ""),
        # scheme-less: no netloc to rebuild, so fail closed rather than echo
        ("nats:4222?token=abc", "<redacted>"),
        ("host-only-no-scheme", "<redacted>"),
    ],
)
def test_safe_url_drops_userinfo_and_query(url, expected):
    assert _safe_url(url) == expected


def test_no_log_line_passes_a_raw_url():
    """Any logger call that mentions a URL-bearing name must route it through
    _safe_url -- %-style ("url=%s", NATS_URL) and f-strings ({NATS_URL}) alike."""
    url_names = ("NATS_URL", "ws_url")
    for n, line in enumerate(_SRC.read_text().splitlines(), 1):
        if "logger." not in line:
            continue
        if "url=%s" in line or any(name in line for name in url_names):
            assert "_safe_url(" in line, f"geometry_bus.py:{n}: {line.strip()}"
