from attribution import build_cgp_point, summarize_transcript
from fixtures import VALID_RESULT, VALID_WORKORDER


def test_build_cgp_point_carries_provenance():
    p = build_cgp_point(VALID_RESULT, VALID_WORKORDER, model_id="ideogram-4", license_name="non-commercial")
    assert p["meta"]["model"] == "ideogram-4"
    assert p["meta"]["license"] == "non-commercial"
    assert p["meta"]["workflow_id"] == "image.ideogram-ultra"
    assert p["meta"]["has_api_prompt"] is True
    assert p["meta"]["knobs"]["seed"] == 42


def test_summarize_transcript_short():
    s = summarize_transcript(VALID_RESULT["transcript"])
    assert "seed" in s
    assert len(s) <= 280


def test_summarize_transcript_truncates_at_280():
    long_transcript = [
        {"step": f"s{i}", "knob": f"knob{i}", "teaches": "x" * 50}
        for i in range(20)
    ]
    s = summarize_transcript(long_transcript)
    assert len(s) == 280  # hard cap holds for an over-length transcript


def test_summarize_transcript_empty():
    assert summarize_transcript([]) == "run complete"
