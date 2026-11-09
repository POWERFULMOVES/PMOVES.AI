import pytest

from voice_router.clients import (
    build_flute_request,
    build_omnivoice_request,
    build_utts_request,
)


def test_omnivoice_request_shape():
    r = build_omnivoice_request("hi", base_url="http://x")
    assert r["method"] == "POST"
    assert r["url"].endswith("/synthesize")
    assert r["payload"] == {"text": "hi", "voice": "default"}


def test_flute_stream_flag_sets_accept():
    assert build_flute_request("hi", stream=True)["headers"]["Accept"] == "text/event-stream"
    assert build_flute_request("hi", stream=False)["headers"]["Accept"] == "audio/wav"


def test_utts_request_shape():
    r = build_utts_request("hi", base_url="http://x")
    assert r["payload"] == {"text": "hi", "speaker": "default"}


def test_empty_text_rejected_everywhere():
    for fn in (build_omnivoice_request, build_flute_request, build_utts_request):
        with pytest.raises(ValueError):
            fn("")
