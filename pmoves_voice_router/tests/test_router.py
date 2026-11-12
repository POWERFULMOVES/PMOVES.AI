import pytest

from voice_router.router import build_route, select_engine


def test_explicit_hint_wins():
    engine, reason = select_engine("hello", hints=("realtime",))
    assert engine == "flute"
    assert "explicit" in reason


def test_explicit_engine_name_hint():
    engine, _ = select_engine("hello", hints=("utts",))
    assert engine == "utts"


def test_text_keyword_routing():
    assert select_engine("long-form narration chapter")[0] == "omnivoice"
    assert select_engine("studio clone of my voice")[0] == "utts"


def test_default_when_no_signal():
    plan = build_route("plain text")
    assert plan.engine == "omnivoice"
    assert plan.wired is False  # scaffold phase marker


def test_unknown_engine_rejected():
    with pytest.raises(ValueError):
        build_route("x", default="nope")
