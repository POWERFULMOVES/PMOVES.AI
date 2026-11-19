from voice_router.config import get_config, redact


def test_env_only_keys_absent_by_default():
    cfg = get_config(env={})
    assert cfg.omnivoice_api_key is None
    assert cfg.default_engine is None


def test_keys_read_from_env_mapping():
    cfg = get_config(env={"OMNIVOICE_API_KEY": "k", "VOICE_ROUTER_DEFAULT_ENGINE": "flute"})
    assert cfg.omnivoice_api_key == "k"
    assert cfg.default_engine == "flute"


def test_redact_strips_secret_looking_keys():
    payload = {"omnivoice_api_key": "x", "nested": {"authorization": "y", "ok": 1}}
    assert redact(payload) == {
        "omnivoice_api_key": "<redacted>",
        "nested": {"authorization": "<redacted>", "ok": 1},
    }
