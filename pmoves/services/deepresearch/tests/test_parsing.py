from pmoves.services.deepresearch.parser import parse_model_output, prepare_result

import pytest


def test_parse_model_output_from_json_fence():
    raw = """
    The model responded with the following payload:

    ```json
    {
        "query": "latest ai news",
        "summary": "A concise overview",
        "sources": [
            {"title": "Example", "url": "https://example.com", "score": 0.9}
        ]
    }
    ```
    """

    parsed = parse_model_output(raw)

    assert parsed["query"] == "latest ai news"
    assert parsed["summary"] == "A concise overview"
    assert parsed["sources"][0]["url"] == "https://example.com"


def test_parse_model_output_from_inline_json():
    raw = "Here you go {\"summary\": \"Done\", \"sources\": []} extra commentary"

    parsed = parse_model_output(raw)

    assert parsed == {"summary": "Done", "sources": []}


@pytest.mark.parametrize(
    "sources, expected_urls",
    [
        (
            [
                {"title": "Low", "url": "https://low.test", "score": 0.1},
                {"title": "High", "url": "https://high.test", "score": 0.9},
                {"title": "Missing score", "url": "https://mid.test"},
            ],
            ["https://high.test", "https://low.test", "https://mid.test"],
        ),
        (
            ["https://string-source.test"],
            ["https://string-source.test"],
        ),
    ],
)
def test_prepare_result_normalises_sources(sources, expected_urls):
    payload = {
        "query": "who invented radar",
        "answer": "A detailed explanation",
        "reasoning": "Collected from encyclopaedias",
        "sources": sources,
    }

    result = prepare_result(payload)

    assert result["summary"] == "A detailed explanation"
    assert [item["url"] for item in result["sources"]] == expected_urls
    assert result["query"] == "who invented radar"
    assert result["reasoning"] == "Collected from encyclopaedias"
