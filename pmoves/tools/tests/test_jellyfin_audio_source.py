# pmoves/tools/tests/test_jellyfin_audio_source.py
import httpx
from pmoves.tools.jellyfin_audio_source import JellyfinAudioSource


def test_list_audio_items_maps_item_id():
    def handler(request):
        assert "/Items" in str(request.url)
        return httpx.Response(200, json={"Items": [
            {"Id": "abc123", "Name": "Track One", "Path": "/music/one.flac", "RunTimeTicks": 1200000000},
        ]})
    src = JellyfinAudioSource("http://jellyfin:8096", "key", transport=httpx.MockTransport(handler))
    items = src.list_audio_items()
    assert items[0]["jellyfin_item_id"] == "abc123"
    assert items[0]["name"] == "Track One"
    assert items[0]["duration_s"] == 120.0
