from operator_select import operator_kind


def test_voice_workflow_selects_voice_operator():
    assert operator_kind("voice.omnivoice") == "voice"


def test_image_and_video_select_comfyui_operator():
    assert operator_kind("image.ideogram-ultra") == "comfyui"
    assert operator_kind("video.ltx") == "comfyui"
    assert operator_kind("anime.anima") == "comfyui"


def test_unknown_prefix_defaults_comfyui():
    assert operator_kind("misc.thing") == "comfyui"
