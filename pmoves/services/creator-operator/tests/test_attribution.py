from attribution import build_cgp_point, summarize_transcript
from fixtures import VALID_RESULT, VALID_WORKORDER


def test_build_cgp_point_carries_provenance():
    p = build_cgp_point(VALID_RESULT, VALID_WORKORDER, model_id="ideogram-4", license="non-commercial")
    assert p["meta"]["model"] == "ideogram-4"
    assert p["meta"]["license"] == "non-commercial"
    assert p["meta"]["workflow_id"] == "image.ideogram-ultra"
    assert p["meta"]["has_api_prompt"] is True
    assert p["meta"]["knobs"]["seed"] == 42


def test_summarize_transcript_short():
    s = summarize_transcript(VALID_RESULT["transcript"])
    assert "seed" in s
    assert len(s) <= 280
