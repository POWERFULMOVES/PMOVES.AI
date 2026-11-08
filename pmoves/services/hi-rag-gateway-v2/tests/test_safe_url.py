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


_URL_NAMES = {"NATS_URL", "ws_url"}
_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}


def _raw_url_uses(node: ast.AST):
    """Yield Name nodes for URL-bearing names NOT wrapped in _safe_url(...)."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_safe_url":
        return
    if isinstance(node, ast.Name) and node.id in _URL_NAMES:
        yield node
        return
    for child in ast.iter_child_nodes(node):
        yield from _raw_url_uses(child)


def test_no_logger_call_passes_a_raw_url():
    """Statement-level (AST), so multi-line calls are covered: every argument of
    every logger.<level>(...) call -- %-style args and f-string parts alike --
    may only reach NATS_URL / ws_url through _safe_url(...)."""
    tree = ast.parse(_SRC.read_text())
    offenders = []
    for call in ast.walk(tree):
        # Any receiver: logger.info, logging.getLogger(...).info, log = logger.
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr in _LOG_METHODS):
            continue
        for arg in [*call.args, *(k.value for k in call.keywords)]:
            offenders += [f"geometry_bus.py:{n.lineno} {n.id}" for n in _raw_url_uses(arg)]
    assert not offenders, offenders


def test_guard_catches_a_multiline_raw_url():
    # The guard itself must fail on the multi-line shape a line scan misses.
    bad = ast.parse('logger.info(\n    "listener (url=%s)",\n    NATS_URL,\n)\n')
    good = ast.parse('logger.info(\n    "listener (url=%s)",\n    _safe_url(NATS_URL),\n)\n')
    assert [n.id for c in ast.walk(bad) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) for a in c.args for n in _raw_url_uses(a)] == ["NATS_URL"]
    assert [n.id for c in ast.walk(good) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) for a in c.args for n in _raw_url_uses(a)] == []
