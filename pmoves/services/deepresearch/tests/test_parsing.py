from services.deepresearch.parser import parse_model_output, prepare_result


def test_parse_model_output_from_code_block():
    raw = """```json\n{\n  \"summary\": \"Key findings\",\n  \"notes\": [\"Observation one\", \"Observation two\"],\n  \"sources\": [\n    {\n      \"title\": \"Doc\",\n      \"url\": \"https://example.com\",\n      \"confidence\": 0.82\n    }\n  ],\n  \"steps\": [\"Initial search\", {\"action\": \"visit\"}]\n}\n```"""
    parsed = parse_model_output(raw)
    summary, notes, sources, iterations, raw_log = prepare_result(parsed)

    assert summary == "Key findings"
    assert notes == ["Observation one", "Observation two"]
    assert sources[0]["url"] == "https://example.com"
    assert sources[0]["confidence"] == 0.82
    assert iterations and iterations[0]["detail"] == "Initial search"
    assert iterations[1]["action"] == "visit"
    assert raw_log is None


def test_parse_model_output_falls_back_to_text():
    raw = "Research indicates strong growth in the geometry sector."
    parsed = parse_model_output(raw)
    summary, notes, sources, iterations, raw_log = prepare_result(parsed)

    assert summary == raw
    assert notes == []
    assert sources == []
    assert iterations is None
    assert raw_log is None


def test_parse_model_output_handles_inline_json():
    raw = "Something went wrong but {\"summary\": \"Partial\", \"notes\": \"Fix later\"}"
    parsed = parse_model_output(raw)
    summary, notes, sources, iterations, raw_log = prepare_result(parsed)

    assert summary == "Partial"
    assert notes == ["Fix later"]
    assert sources == []
    assert iterations is None
    assert raw_log is None
