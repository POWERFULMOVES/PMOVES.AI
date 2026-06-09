import pytest
from omnivoice_client import FakeOmniVoiceClient, OmniVoiceError


def test_fake_client_synthesizes_to_path(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    path = client.synthesize(text="hello fleet", voice_ref="bean")
    assert path.endswith(".wav")
    import os
    assert os.path.exists(path)


def test_fake_client_raises_on_empty_text(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="", voice_ref="bean")
