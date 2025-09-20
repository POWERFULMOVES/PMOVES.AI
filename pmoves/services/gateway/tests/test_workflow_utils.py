import math
from typing import List

import math
from typing import List

import pytest

pytest.importorskip("fastapi")

from pmoves.services.gateway.gateway.api import workflow
from pmoves.services.gateway.gateway.api.workflow import (
    _build_cgp,
    _build_hirag_items,
    _chunk_segments,
    _normalise_segments,
)


def _sample_segments() -> List[dict]:
    return [
        {"start": 1.0, "end": 2.5, "text": "First segment"},
        {"start": 2.5, "end": 4.0, "text": "Second part"},
        {"start": 4.2, "end": 6.0, "text": "Third piece"},
    ]


def test_normalise_segments_accepts_plain_text():
    segs = workflow._normalise_segments({"text": "Hello world"})
    assert segs
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] >= 5.0


def test_chunk_segments_groups_with_ids():
    chunks = _chunk_segments("vid", _sample_segments(), group_size=2, max_groups=2)
    assert len(chunks) == 2
    first = chunks[0]
    assert first["chunk_id"].startswith("vid:")
    assert all(pt["chunk_id"] == first["chunk_id"] for pt in first["points"])


def test_hirag_items_include_payload():
    chunks = _chunk_segments("vid", _sample_segments(), group_size=2, max_groups=1)
    items = _build_hirag_items("vid", "pmoves", chunks)
    assert items[0]["doc_id"] == "yt:vid"
    assert items[0]["payload"]["start_s"] == pytest.approx(chunks[0]["start"])


def test_build_cgp_validates_with_schema():
    chunks = _chunk_segments("vid", _sample_segments(), group_size=3, max_groups=1)
    cgp_doc, consts = _build_cgp("vid", "Demo Video", "pmoves", chunks)
    assert consts[0]["spectrum"]
    assert math.isfinite(consts[0]["points"][0]["proj"])
    cgp = workflow.CGP.model_validate(cgp_doc)
    assert cgp.super_nodes[0].constellations[0].id == consts[0]["id"]
