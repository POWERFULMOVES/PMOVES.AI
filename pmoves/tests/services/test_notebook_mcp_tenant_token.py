"""notebook-mcp must resolve the Open Notebook credential PER REQUEST.

The wrapper is mounted by many harnesses at once (A0 runtime MCP client,
deepseek-harness, any MCP client). Reading one process-wide
OPEN_NOTEBOOK_API_TOKEN meant every caller — whatever tenant it belonged to —
searched and wrote the SAME Open Notebook account: cross-tenant disclosure on
`search_notes` and cross-tenant mutation on `save_note`, with nothing in the
request to distinguish them.

These tests pin the two halves of the fix:
  1. a token supplied on the in-flight request wins over the env token, so the
     documented "credential seam lives in the mounting harness" is actually
     wired rather than merely described; and
  2. NOTEBOOK_MCP_REQUIRE_TENANT_TOKEN fails CLOSED — a request with no
     credential is refused instead of quietly borrowing the shared account.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_SERVICE = (
    Path(__file__).resolve().parents[2] / "services" / "notebook-mcp" / "server.py"
)


def _load():
    if not _SERVICE.exists():
        pytest.skip("notebook-mcp/server.py not found")
    spec = importlib.util.spec_from_file_location("notebook_mcp_server", _SERVICE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["notebook_mcp_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def srv():
    try:
        return _load()
    except ImportError as exc:  # mcp SDK absent from this environment
        pytest.skip(f"cannot import notebook-mcp deps: {exc}")


def _with_request_headers(srv, monkeypatch, headers: dict | None):
    """Fake an in-flight MCP request carrying (or lacking) tenant headers."""
    if headers is None:
        def _boom():
            raise LookupError("no active request context")  # what stdio looks like
        monkeypatch.setattr(srv.mcp, "get_context", _boom)
        return
    request = SimpleNamespace(headers=headers)
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))
    monkeypatch.setattr(srv.mcp, "get_context", lambda: ctx)


# ── per-request credential wins ──────────────────────────────────────────────


def test_request_header_token_is_used(srv, monkeypatch):
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", False)
    _with_request_headers(srv, monkeypatch, {srv.TENANT_TOKEN_HEADER: "tenant-a-token"})
    assert srv._resolve_token() == "tenant-a-token"


def test_two_tenants_do_not_share_a_credential(srv, monkeypatch):
    """The regression itself: distinct callers must get distinct tokens."""
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", False)

    _with_request_headers(srv, monkeypatch, {srv.TENANT_TOKEN_HEADER: "tenant-a-token"})
    a = srv._resolve_token()
    _with_request_headers(srv, monkeypatch, {srv.TENANT_TOKEN_HEADER: "tenant-b-token"})
    b = srv._resolve_token()

    assert (a, b) == ("tenant-a-token", "tenant-b-token")
    assert a != b, "both tenants collapsed onto one Open Notebook credential"


def test_resolved_token_reaches_the_authorization_header(srv):
    assert srv._headers("tenant-a-token")["Authorization"] == "Bearer tenant-a-token"
    assert "Authorization" not in srv._headers("")


# ── single-tenant fallback ───────────────────────────────────────────────────


def test_env_token_is_the_fallback_when_not_required(srv, monkeypatch):
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", False)
    _with_request_headers(srv, monkeypatch, {})
    assert srv._resolve_token() == "shared-env-token"


def test_missing_request_context_does_not_raise(srv, monkeypatch):
    """stdio transport has no HTTP request; that is not an error."""
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", False)
    _with_request_headers(srv, monkeypatch, None)
    assert srv._resolve_token() == "shared-env-token"


# ── fail closed ──────────────────────────────────────────────────────────────


def test_require_tenant_token_refuses_the_shared_account(srv, monkeypatch):
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", True)
    _with_request_headers(srv, monkeypatch, {})
    with pytest.raises(srv.TenantCredentialError):
        srv._resolve_token()


def _fn(tool):
    """The underlying coroutine: `@mcp.tool()` returns the bare function on some
    1.x releases and a Tool wrapper on others."""
    return getattr(tool, "fn", tool)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "call",
    [
        lambda srv: _fn(srv.save_note)(content="secret note"),
        lambda srv: _fn(srv.search_notes)(query="anything"),
    ],
    ids=["save_note", "search_notes"],
)
async def test_tools_refuse_instead_of_reaching_open_notebook(srv, monkeypatch, call):
    """Fail-closed must surface as a tool error, never as a call on the shared account."""
    monkeypatch.setattr(srv, "TOKEN", "shared-env-token")
    monkeypatch.setattr(srv, "REQUIRE_TENANT_TOKEN", True)
    _with_request_headers(srv, monkeypatch, {})

    def _no_http(*a, **kw):
        raise AssertionError("reached Open Notebook without a tenant credential")

    monkeypatch.setattr(srv.httpx, "AsyncClient", _no_http)

    out = await call(srv)
    assert "no per-request credential" in out
    assert srv.TENANT_TOKEN_HEADER in out
