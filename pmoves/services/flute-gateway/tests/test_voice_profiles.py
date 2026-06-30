"""Tests for the voice "S1" profile registry (DB-free; httpx mocked).

Covers: select_provider_and_params per-engine mapping, registry
load/cache/refresh/graceful-degradation (404 + unreachable), the request
mutation hook, and the /v1/voice/profiles + /v1/voice/validate routes.

No live DB: every Supabase/PostgREST call is intercepted by a fake
httpx.AsyncClient. Routes are exercised with a Starlette TestClient with the
module-level globals monkeypatched (matches tests/test_gateway.py).
"""

import os
import sys

import pytest

# Set required environment variables before importing main/voice_registry.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://supabase.test")
os.environ.setdefault("FLUTE_API_KEY", "test-api-key")

_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    import httpx
    import prometheus_client  # noqa: F401
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock, patch

    import voice_registry as vr
    from voice_registry import (
        VoiceProfile,
        VoiceRegistry,
        select_provider_and_params,
    )
    DEPS_AVAILABLE = True
except ImportError as e:  # pragma: no cover
    DEPS_AVAILABLE = False
    DEPS_ERROR = str(e)

requires_deps = pytest.mark.skipif(
    not DEPS_AVAILABLE,
    reason=f"Missing test dependencies: {DEPS_ERROR if not DEPS_AVAILABLE else ''}",
)

AUTH = {"X-API-Key": "test-api-key"}


# --- fake httpx --------------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class _FakeClient:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None, params=None):
        return self._handler("GET", url, headers, params, None)

    async def post(self, url, headers=None, params=None, json=None):
        return self._handler("POST", url, headers, params, json)


def _factory(handler):
    def make(*args, **kwargs):
        return _FakeClient(handler)
    return make


def _profile_row(name="alice", engine="vibevoice", **overrides):
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": name,
        "engine": engine,
        "engine_specific": {"voice_preset": "alice-preset"},
        "display_name": "Alice",
        "tags": ["mentor", "en"],
        "grounding": {},
        "ref_audio_path": None,
        "sample_rate_hz": 24000,
        "rights_basis": "owned",
        "is_active": True,
    }
    row.update(overrides)
    return row


# --- select_provider_and_params ---------------------------------------------

@requires_deps
def test_select_provider_and_params_per_engine():
    # vibevoice: voice_preset -> voice
    p, params = select_provider_and_params(
        VoiceProfile.from_row(_profile_row(engine="vibevoice",
                                           engine_specific={"voice_preset": "vp"})),
        "vibevoice",
    )
    assert p == "vibevoice"
    assert params == {"voice": "vp"}

    # voicebox: profile_id -> voice, voice_type -> engine
    p, params = select_provider_and_params(
        VoiceProfile.from_row(_profile_row(
            engine="voicebox",
            engine_specific={"profile_id": "pid-1", "voice_type": "kokoro", "language": "en"})),
        "vibevoice",
    )
    assert p == "voicebox"
    assert params == {"voice": "pid-1", "engine": "kokoro"}

    # ultimate_tts: primary_engine -> engine, <engine>_voice -> voice
    p, params = select_provider_and_params(
        VoiceProfile.from_row(_profile_row(
            engine="ultimate_tts",
            engine_specific={"primary_engine": "f5_tts", "f5_tts_voice": "vx",
                             "fallback_engines": ["kokoro"]})),
        "vibevoice",
    )
    assert p == "ultimate_tts"
    assert params == {"engine": "f5_tts", "voice": "vx"}

    # omnivoice: ref_audio -> voice, instruct -> engine
    p, params = select_provider_and_params(
        VoiceProfile.from_row(_profile_row(
            engine="omnivoice",
            engine_specific={"ref_audio": "juicefs://v/a.wav", "instruct": "calm"})),
        "vibevoice",
    )
    assert p == "omnivoice"
    assert params == {"voice": "juicefs://v/a.wav", "engine": "calm"}


@requires_deps
def test_select_provider_injects_ref_audio_path_when_voice_unset():
    # vibevoice with no voice_preset but a ref_audio_path -> voice injected.
    p, params = select_provider_and_params(
        VoiceProfile.from_row(_profile_row(
            engine="vibevoice", engine_specific={},
            ref_audio_path="juicefs://voices/x.wav")),
        "vibevoice",
    )
    assert p == "vibevoice"
    assert params == {"voice": "juicefs://voices/x.wav"}


# --- registry load / cache / degrade ----------------------------------------

@requires_deps
def test_registry_load_populates_cache(monkeypatch):
    rows = [_profile_row(name="alice", engine="vibevoice"),
            _profile_row(name="bob", engine="ultimate_tts",
                         engine_specific={"primary_engine": "kokoro"})]

    def handler(method, url, headers, params, body):
        assert headers.get("Accept-Profile") == "pmoves_core"
        assert "voice_profiles" in url
        return _FakeResp(200, rows)

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    reg = VoiceRegistry("http://supabase.test", "k")
    import asyncio
    assert asyncio.run(reg.load()) is True
    assert reg.healthy is True
    assert reg.count == 2
    assert reg.get("alice").engine == "vibevoice"
    assert reg.loaded_at is not None
    assert [p.name for p in reg.list(engine="ultimate_tts")] == ["bob"]
    assert [p.name for p in reg.list(tag="mentor")] == ["alice", "bob"]
    assert reg.get("missing") is None


@requires_deps
def test_registry_refresh_updates_cache(monkeypatch):
    state = {"rows": [_profile_row(name="alice")]}

    def handler(method, url, headers, params, body):
        return _FakeResp(200, state["rows"])

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    reg = VoiceRegistry("http://supabase.test", "k", ttl_seconds=1)
    import asyncio
    asyncio.run(reg.load())
    assert reg.count == 1
    state["rows"] = [_profile_row(name="alice"), _profile_row(name="carol")]
    assert asyncio.run(reg.refresh()) is True
    assert reg.count == 2
    assert reg.get("carol") is not None


@requires_deps
@pytest.mark.parametrize("resp", [
    _FakeResp(404, {"code": "PGRST205", "message": "not found"}),
    _FakeResp(200, {"code": "42P01"}),  # body-coded table-absent
])
def test_registry_load_table_absent_degrades(monkeypatch, resp):
    def handler(method, url, headers, params, body):
        return resp

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    reg = VoiceRegistry("http://supabase.test", "k")
    import asyncio
    assert asyncio.run(reg.load()) is False  # no exception
    assert reg.healthy is False
    assert reg.count == 0
    assert reg.get("alice") is None


@requires_deps
def test_registry_load_supabase_unreachable_degrades(monkeypatch):
    def handler(method, url, headers, params, body):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    reg = VoiceRegistry("http://supabase.test", "k")
    import asyncio
    assert asyncio.run(reg.load()) is False
    assert reg.healthy is False
    assert reg.count == 0


@requires_deps
def test_registry_load_no_credentials_degrades():
    reg = VoiceRegistry("", "")
    import asyncio
    assert asyncio.run(reg.load()) is False
    assert reg.healthy is False


# --- request mutation hook ---------------------------------------------------

@requires_deps
def test_resolve_voice_profile_hook_mutates_request():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._cache = {"my-slug": VoiceProfile.from_row(_profile_row(
        name="my-slug", engine="ultimate_tts",
        engine_specific={"primary_engine": "f5_tts", "f5_tts_voice": "vx"}))}
    reg._healthy = True

    req = main.SynthesizeRequest(text="hello", voice="my-slug")
    with patch("main.voice_registry", reg):
        matched = main._resolve_voice_profile(req)
    assert matched is True
    assert req.provider == "ultimate_tts"
    assert req.engine == "f5_tts"
    assert req.voice == "vx"


@requires_deps
def test_resolve_voice_profile_hook_unknown_slug_noop():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    req = main.SynthesizeRequest(text="hello", voice="nope")
    with patch("main.voice_registry", reg):
        assert main._resolve_voice_profile(req) is False
    assert req.provider is None  # untouched


# --- synthesize routing via registry ----------------------------------------

@requires_deps
def test_synthesize_voice_slug_routes_via_registry():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._cache = {"my-slug": VoiceProfile.from_row(_profile_row(
        name="my-slug", engine="vibevoice",
        engine_specific={"voice_preset": "alice-preset"}))}
    reg._healthy = True

    mock_vibe = AsyncMock()
    mock_vibe.synthesize = AsyncMock(return_value=b"\x00\x01" * 100)

    with patch("main.voice_registry", reg), \
         patch("main.vibevoice_provider", mock_vibe), \
         patch("main.nats_client", None):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/synthesize",
                           json={"text": "hi", "voice": "my-slug"}, headers=AUTH)
    assert resp.status_code == 200
    mock_vibe.synthesize.assert_awaited_once()
    # engine_specific.voice_preset reached the provider as `voice`
    assert mock_vibe.synthesize.await_args.kwargs["voice"] == "alice-preset"


@requires_deps
def test_synthesize_unknown_slug_falls_back_to_default():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True  # healthy but slug not present

    mock_vibe = AsyncMock()
    mock_vibe.synthesize = AsyncMock(return_value=b"\x00\x01" * 100)

    with patch("main.voice_registry", reg), \
         patch("main.vibevoice_provider", mock_vibe), \
         patch("main.nats_client", None):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/synthesize",
                           json={"text": "hi", "voice": "unknown-slug"}, headers=AUTH)
    assert resp.status_code == 200  # DEFAULT_PROVIDER path, no 500
    mock_vibe.synthesize.assert_awaited_once()


# --- /v1/voice/profiles ------------------------------------------------------

@requires_deps
def test_list_profiles_filter_engine_tag():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._cache = {
        "alice": VoiceProfile.from_row(_profile_row(name="alice", engine="vibevoice")),
        "bob": VoiceProfile.from_row(_profile_row(
            name="bob", engine="ultimate_tts", tags=["narrator"])),
    }
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.get("/v1/voice/profiles?engine=ultimate_tts", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["healthy"] is True
    assert data["count"] == 1
    assert data["profiles"][0]["name"] == "bob"


@requires_deps
def test_list_profiles_degraded_returns_empty_200():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = False
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.get("/v1/voice/profiles", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"profiles": [], "healthy": False, "count": 0}


@requires_deps
def test_get_profile_404():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.get("/v1/voice/profiles/ghost", headers=AUTH)
    assert resp.status_code == 404


@requires_deps
def test_auth_required_on_profiles_post():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/profiles",
                           json={"name": "abc", "engine": "vibevoice"})  # no X-API-Key
    assert resp.status_code == 401


@requires_deps
def test_create_profile_invalid_engine_422():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/profiles",
                           json={"name": "abc", "engine": "bogus"}, headers=AUTH)
    assert resp.status_code == 422


@requires_deps
def test_create_profile_invalid_capability_422():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        # vibevoice requires engine_specific.voice_preset -> capability error
        resp = client.post("/v1/voice/profiles",
                           json={"name": "abc", "engine": "vibevoice",
                                 "engine_specific": {}}, headers=AUTH)
    assert resp.status_code == 422
    assert "capability" in resp.json()["detail"]


@requires_deps
def test_create_profile_invalid_grounding_422(monkeypatch):
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    # forbidden consciousness_shape -> grounding error before any DB write
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/profiles",
                           json={"name": "abc", "engine": "vibevoice",
                                 "engine_specific": {"voice_preset": "p"},
                                 "grounding": {"consciousness_shape": "x"}}, headers=AUTH)
    assert resp.status_code == 422
    assert resp.json()["detail"]["grounding"]


@requires_deps
def test_create_profile_success_warms_cache(monkeypatch):
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    created = _profile_row(name="new-slug", engine="vibevoice",
                           engine_specific={"voice_preset": "p"})

    def handler(method, url, headers, params, body):
        assert method == "POST"
        assert headers.get("Content-Profile") == "pmoves_core"
        return _FakeResp(201, [created])

    monkeypatch.setattr(main.httpx, "AsyncClient", _factory(handler))
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/profiles",
                           json={"name": "new-slug", "engine": "vibevoice",
                                 "engine_specific": {"voice_preset": "p"}}, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["name"] == "new-slug"
    assert reg.get("new-slug") is not None  # cache warmed via upsert_local


# --- /v1/voice/validate ------------------------------------------------------

@requires_deps
def test_validate_contract_get():
    import main
    client = TestClient(main.app)
    resp = client.get("/v1/voice/validate")  # introspection, no auth
    assert resp.status_code == 200
    data = resp.json()
    assert "consciousness_shape" in data["forbidden_keys"]
    assert set(data["engines"]) == {"omnivoice", "vibevoice", "voicebox", "ultimate_tts"}


@requires_deps
def test_validate_forbidden_consciousness_shape():
    import main
    client = TestClient(main.app)
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"consciousness_shape": "blob"}}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any("consciousness_shape" in e for e in data["errors"])


_UUID1 = "11111111-1111-1111-1111-111111111111"
_UUID2 = "22222222-2222-2222-2222-222222222222"


@requires_deps
def test_validate_grounding_pk_resolution(monkeypatch):
    import main

    def make_handler(resolved_ids):
        def handler(method, url, headers, params, body):
            assert headers.get("Accept-Profile") == "pmoves_core"
            assert "personas" in url
            return _FakeResp(200, [{"persona_id": pid} for pid in resolved_ids])
        return handler

    # all ids resolve -> valid
    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(make_handler([_UUID1, _UUID2])))
    client = TestClient(main.app)
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"persona_ids": [_UUID1, _UUID2]}}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True

    # a missing id -> invalid
    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(make_handler([_UUID1])))
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"persona_ids": [_UUID1, _UUID2]}}, headers=AUTH)
    assert resp.json()["valid"] is False
    assert any("persona_ids" in e for e in resp.json()["errors"])


@requires_deps
def test_validate_grounding_malformed_uuid_rejected_without_query(monkeypatch):
    """A non-UUID persona_id is a hard error caught locally (no PostgREST call)."""
    import main

    def handler(method, url, headers, params, body):
        raise AssertionError("must not query substrate for a malformed UUID")

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    client = TestClient(main.app)
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"persona_ids": ["not-a-uuid"]}}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any("malformed UUID" in e for e in data["errors"])


@requires_deps
def test_validate_grounding_client_error_is_hard_error(monkeypatch):
    """A PostgREST 400 (bad input) is a rejection, not an 'unreachable' warning."""
    import main

    def handler(method, url, headers, params, body):
        return _FakeResp(400, {"code": "22P02", "message": "invalid input syntax"})

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    client = TestClient(main.app)
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"persona_ids": [_UUID1]}}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any("rejected by substrate" in e for e in data["errors"])
    assert data["warnings"] == []  # NOT excused as unreachable


@requires_deps
def test_validate_grounding_unreachable_is_warning_not_error(monkeypatch):
    import main

    def handler(method, url, headers, params, body):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    client = TestClient(main.app)
    resp = client.post("/v1/voice/validate",
                       json={"engine": "vibevoice",
                             "engine_specific": {"voice_preset": "p"},
                             "grounding": {"persona_ids": [_UUID1]}}, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True  # unverifiable != invalid
    assert any("unreachable" in w for w in data["warnings"])


# --- review-fix regression tests --------------------------------------------

@requires_deps
def test_registry_load_filters_soft_deleted(monkeypatch):
    """The registry query must exclude soft-deleted rows (deleted_at IS NULL)."""
    seen = {}

    def handler(method, url, headers, params, body):
        seen["params"] = params
        return _FakeResp(200, [_profile_row(name="alice")])

    monkeypatch.setattr(vr.httpx, "AsyncClient", _factory(handler))
    reg = VoiceRegistry("http://supabase.test", "k")
    import asyncio
    assert asyncio.run(reg.load()) is True
    assert seen["params"].get("deleted_at") == "is.null"
    assert seen["params"].get("is_active") == "eq.true"


@requires_deps
def test_hook_clears_slug_when_no_provider_voice():
    """A matched profile with no provider-native voice must NOT leak the slug."""
    import main
    reg = VoiceRegistry("http://x", "k")
    # omnivoice design profile: instruct only, no ref_audio / ref_audio_path.
    reg._cache = {"design-1": VoiceProfile.from_row(_profile_row(
        name="design-1", engine="omnivoice",
        engine_specific={"instruct": "calm narrator"}, ref_audio_path=None))}
    reg._healthy = True

    req = main.SynthesizeRequest(text="hi", voice="design-1")
    with patch("main.voice_registry", reg):
        matched = main._resolve_voice_profile(req)
    assert matched is True
    assert req.provider == "omnivoice"
    assert req.engine == "calm narrator"   # instruct -> engine slot
    assert req.voice is None               # slug cleared, not leaked


@requires_deps
def test_hook_noop_when_registry_unhealthy():
    """Honor the health gate: do not read the cache when unhealthy."""
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._cache = {"alice": VoiceProfile.from_row(_profile_row(name="alice"))}
    reg._healthy = False  # unhealthy -> must no-op
    req = main.SynthesizeRequest(text="hi", voice="alice")
    with patch("main.voice_registry", reg):
        assert main._resolve_voice_profile(req) is False
    assert req.provider is None  # untouched


@requires_deps
def test_capability_ultimate_tts_requires_voice_key():
    from voice_registry import validate_capability
    # primary_engine present but the derived voice key missing -> error
    errs = validate_capability("ultimate_tts", {"primary_engine": "f5_tts"})
    assert any("f5_tts_voice" in e for e in errs)
    # voice key present -> ok
    assert validate_capability(
        "ultimate_tts", {"primary_engine": "f5_tts", "f5_tts_voice": "vx"}) == []


@requires_deps
def test_env_int_guards_malformed_ttl(monkeypatch):
    monkeypatch.setenv("VOICE_REGISTRY_TTL_SECONDS", "not-an-int")
    assert vr._env_int("VOICE_REGISTRY_TTL_SECONDS", 300) == 300


@requires_deps
def test_create_profile_invalid_name_pattern_422():
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    with patch("main.voice_registry", reg):
        client = TestClient(main.app)
        # "ab" is too short (<3) and "bad name!" has illegal chars
        for bad in ["ab", "bad name!"]:
            resp = client.post("/v1/voice/profiles",
                               json={"name": bad, "engine": "vibevoice",
                                     "engine_specific": {"voice_preset": "p"}}, headers=AUTH)
            assert resp.status_code == 422, bad


@requires_deps
def test_create_profile_publishes_invalidation(monkeypatch):
    """After a successful write, peer instances are notified via NATS."""
    import main
    reg = VoiceRegistry("http://x", "k")
    reg._healthy = True
    created = _profile_row(name="new-slug", engine="vibevoice",
                           engine_specific={"voice_preset": "p"})

    def handler(method, url, headers, params, body):
        return _FakeResp(201, [created])

    mock_nats = AsyncMock()
    mock_nats.publish = AsyncMock()
    monkeypatch.setattr(main.httpx, "AsyncClient", _factory(handler))
    with patch("main.voice_registry", reg), patch("main.nats_client", mock_nats):
        client = TestClient(main.app)
        resp = client.post("/v1/voice/profiles",
                           json={"name": "new-slug", "engine": "vibevoice",
                                 "engine_specific": {"voice_preset": "p"}}, headers=AUTH)
    assert resp.status_code == 201
    mock_nats.publish.assert_awaited_once()
    assert mock_nats.publish.await_args.args[0] == "voice.registry.update.v1"
