"""Hi-RAG v2 response parsing for the github-issue-triage client.

Two shape mismatches sat between a successful query and a usable result, and
fixing only the first would have looked like a fix while changing nothing:

1. v2's ``QueryResp`` returns its list under ``hits`` (hi-rag-gateway-v2/models.py:36).
   The client accepted ``results`` or a bare list, so every successful query fell
   through to "unexpected format" and returned ``None`` -- triage used pattern
   matching even when the gateway answered correctly.
2. A ``QueryHit`` keeps the indexed document under ``payload`` and carries only
   scoring at the top level, while ``app.py`` reads ``issue.get("labels")``. So
   even once ``hits`` parsed, every hit would contribute zero labels.

Imported via importlib because the service directory contains a hyphen and is
therefore not a legal Python package path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SERVICE = (
    Path(__file__).resolve().parents[1]
    / "services" / "github-issue-triage" / "hirag_client.py"
)


@pytest.fixture(scope="module")
def client_cls():
    spec = importlib.util.spec_from_file_location("hirag_client", SERVICE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HiRAGClient


def _v2_response():
    """The shape hi-rag-gateway-v2 actually returns."""
    return {
        "query": "crash on startup",
        "k": 5,
        "used_rerank": False,
        "hits": [
            {
                "chunk_id": "c1",
                "text": "app crashes",
                "score": 0.91,
                "payload": {"labels": ["bug", "p1"], "number": 42},
            },
            {
                "chunk_id": "c2",
                "text": "also crashes",
                "score": 0.44,
                "payload": {"labels": ["bug"], "number": 7},
            },
        ],
    }


def test_v2_hits_are_parsed(client_cls):
    out = client_cls._extract_hits(_v2_response())
    assert out is not None, "v2 'hits' must not fall through to the None branch"
    assert len(out) == 2


def test_labels_are_reachable_the_way_app_py_reads_them(client_cls):
    """app.py does `issue.get('labels', [])` -- payload must be merged up."""
    out = client_cls._extract_hits(_v2_response())
    scores: dict[str, int] = {}
    for issue in out:
        for label in issue.get("labels", []):
            scores[label] = scores.get(label, 0) + 1
    assert scores == {"bug": 2, "p1": 1}, "empty here means triage still falls back"


def test_retrieval_score_wins_over_a_payload_field_of_the_same_name(client_cls):
    """A document that happens to carry `score` must not shadow the ranking score."""
    out = client_cls._extract_hits(
        {"hits": [{"score": 0.9, "payload": {"score": "document-field"}}]}
    )
    assert out[0]["score"] == 0.9


def test_legacy_results_key_still_works(client_cls):
    assert client_cls._extract_hits({"results": [{"labels": ["x"]}]}) == [{"labels": ["x"]}]


def test_bare_list_still_works(client_cls):
    assert client_cls._extract_hits([{"labels": ["y"]}]) == [{"labels": ["y"]}]


def test_hit_without_payload_is_passed_through(client_cls):
    assert client_cls._extract_hits({"hits": [{"chunk_id": "c"}]}) == [{"chunk_id": "c"}]


@pytest.mark.parametrize("bad", [{"nope": 1}, "a string", 7, None])
def test_unrecognised_shapes_return_none_rather_than_raising(client_cls, bad):
    assert client_cls._extract_hits(bad) is None
