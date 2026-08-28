# pmoves/tools/tests/test_clap_client.py
import httpx
from pmoves.tools.clap_client import ClapClient


def test_embed_audio_success():
    def handler(request):
        return httpx.Response(200, json={"embedding": [0.5] * 512, "model_rev": "main"})
    client = ClapClient("http://clap-embed:8108", transport=httpx.MockTransport(handler))
    vec = client.embed_audio_bytes(b"fakewav", "x.wav")
    assert len(vec) == 512 and client.last_grounding == "full"


def test_embed_audio_failure_flags_partial_and_returns_none():
    def handler(request):
        return httpx.Response(503)
    client = ClapClient("http://clap-embed:8108", transport=httpx.MockTransport(handler))
    vec = client.embed_audio_bytes(b"fakewav", "x.wav")
    assert vec is None and client.last_grounding == "partial"
