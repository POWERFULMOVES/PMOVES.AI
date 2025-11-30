import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


class _DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


sys.modules.setdefault("httpx", SimpleNamespace(AsyncClient=_DummyAsyncClient))


class _DummyFastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def post(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def on_event(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


fastapi_module = ModuleType("fastapi")
fastapi_module.Body = lambda *a, **k: None
fastapi_module.FastAPI = _DummyFastAPI
fastapi_module.HTTPException = Exception
fastapi_module.__all__ = ["Body", "FastAPI", "HTTPException"]
sys.modules.setdefault("fastapi", fastapi_module)


def _install_nats_stub() -> None:
    if "nats" in sys.modules:
        return
    nats_module = ModuleType("nats")
    aio_module = ModuleType("nats.aio")

    class _DummyNATS:
        def __init__(self, *args, **kwargs):
            pass

    client_module = ModuleType("nats.aio.client")
    client_module.Client = _DummyNATS
    aio_module.client = client_module
    nats_module.aio = aio_module
    sys.modules["nats.aio.client"] = client_module
    sys.modules["nats.aio"] = aio_module
    sys.modules["nats"] = nats_module


_install_nats_stub()

ROOT = Path(__file__).resolve().parents[5]
PM = Path(__file__).resolve().parents[4]
for p in (str(ROOT), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from pmoves.services import publisher_discord as discord


def test_format_content_published_embed_minimal():
    name = "content.published.v1"
    payload = {
        "title": "Sample",
        "namespace": "pmoves",
        "published_path": "/library/pmoves/sample.png",
        "artifact_uri": "s3://assets/pmoves/sample.png",
        "public_url": "http://media.local/pmoves/sample.png",
        "meta": {"duration": 12.3},
    }
    out = discord._format_event(name, payload)
    assert out.get("embeds") and isinstance(out["embeds"], list)
    emb = out["embeds"][0]
    assert emb["title"] == "Published: Sample"
    assert any(f.get("name") == "Published Path" for f in emb.get("fields", []))
    assert any(f.get("name") == "Artifact URI" for f in emb.get("fields", []))


def test_format_adds_jellyfin_link_when_id_present():
    name = "content.published.v1"
    payload = {
        "title": "Episode 1",
        "namespace": "shows",
        "jellyfin_item_id": "abc123",
        "meta": {"jellyfin_base_url": "http://jf"},
    }
    out = discord._format_event(name, payload)
    fields = out["embeds"][0].get("fields", [])
    jf = [f for f in fields if f.get("name") == "Jellyfin"]
    assert jf and jf[0]["value"].startswith("http://jf/web/index.html#!/details?id=abc123")


def test_format_duration_uses_h_mm_ss():
    payload = {
        "title": "Long form",
        "namespace": "pmoves",
        "meta": {"duration": 3661},
    }
    out = discord._format_event("content.published.v1", payload)
    fields = {field["name"]: field["value"] for field in out["embeds"][0]["fields"]}
    assert fields["Duration"] == "1:01:01"


def test_format_prefers_explicit_thumbnail_url_over_fallback():
    payload = {
        "title": "Thumbs",
        "namespace": "pmoves",
        "thumbnail_url": "https://cdn/payload.png",
        "thumb": "https://cdn/fallback.png",
        "meta": {
            "thumbnail_url": "https://cdn/meta.png",
            "cover_art": {"url": "https://cdn/direct.png"},
        },
    }
    out = discord._format_event("content.published.v1", payload)
    embed = out["embeds"][0]
    assert embed["thumbnail"]["url"] == "https://cdn/payload.png"

    payload.pop("thumbnail_url")
    out = discord._format_event("content.published.v1", payload)
    embed = out["embeds"][0]
    assert embed["thumbnail"]["url"] == "https://cdn/meta.png"


def test_format_jellyfin_deep_link_includes_start_time():
    original = discord.JELLYFIN_URL
    try:
        discord.JELLYFIN_URL = ""
        payload = {
            "title": "Playback",
            "namespace": "pmoves",
            "jellyfin_item_id": "xyz",
            "meta": {
                "jellyfin_base_url": "http://jf", 
                "start_time": 42.7,
            },
        }
        out = discord._format_event("content.published.v1", payload)
    finally:
        discord.JELLYFIN_URL = original
    fields = out["embeds"][0]["fields"]
    jf_field = next(field for field in fields if field["name"] == "Jellyfin")
    assert jf_field["value"].endswith("id=xyz&startTime=43")


def test_format_tags_capped_and_summary_spillover_field():
    tags = [f"tag{i}" for i in range(15)]
    summary = "Lorem ipsum " * 150
    payload = {
        "title": "Tagged",
        "namespace": "pmoves",
        "public_url": "https://pmoves.ai/content",
        "tags": tags,
        "summary": summary,
    }
    out = discord._format_event("content.published.v1", payload)
    fields = out["embeds"][0]["fields"]
    tags_field = next(field for field in fields if field["name"] == "Tags")
    quoted_tags = tags_field["value"].split(", ")
    assert len(quoted_tags) == 12
    assert all(tag.startswith("`") and tag.endswith("`") for tag in quoted_tags)

    summary_field = next(field for field in fields if field["name"].startswith("Summary"))
    assert len(summary_field["value"]) <= 1024
    assert summary_field["value"].startswith(summary[:10])
