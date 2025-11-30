"""Workflow orchestration endpoints for the gateway."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...event_bus import EventBus
from .chit import (
    CGP,
    GeometryDecodeTextRequest,
    geometry_calibration_report,
    geometry_decode_text,
    ingest_cgp,
)
from .mindmap import driver as neo4j_driver

router = APIRouter(prefix="/workflow", tags=["Workflow Demo"])
logger = logging.getLogger("pmoves.gateway.workflow")


class DemoRunRequest(BaseModel):
    """Input payload for running the orchestration workflow."""

    youtube_url: Optional[str] = Field(default=None, alias="url")
    namespace: Optional[str] = None
    bucket: Optional[str] = None
    query: Optional[str] = None
    per_constellation: int = Field(default=20, ge=1, le=100)
    codebook_path: Optional[str] = None
    cgp: Dict[str, Any] | None = None  # optional offline fallback


def _event_bus(request: Request) -> EventBus | None:
    bus = getattr(request.app.state, "event_bus", None)
    return bus if isinstance(bus, EventBus) else None


@router.post("/demo_run")
async def demo_run(body: DemoRunRequest, request: Request) -> Dict[str, Any]:
    if body.cgp:
        return _run_offline(body)

    yt_base = os.getenv("YT_URL", "http://pmoves-yt:8077").rstrip("/")
    if not yt_base:
        raise HTTPException(status_code=503, detail="YT_URL not configured")

    namespace = body.namespace or os.getenv("INDEXER_NAMESPACE", "pmoves")
    bucket = body.bucket or os.getenv("YT_BUCKET", "assets")
    youtube_url = body.youtube_url or os.getenv("WORKFLOW_SAMPLE_URL")
    if not youtube_url:
        raise HTTPException(status_code=400, detail="youtube_url required")

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        ingest_payload = {
            "url": youtube_url,
            "namespace": namespace,
            "bucket": bucket,
        }
        try:
            ingest_resp = await client.post(f"{yt_base}/yt/ingest", json=ingest_payload)
            ingest_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("/yt/ingest failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"yt ingest failed: {exc}")
        ingest_data = ingest_resp.json()

        video = ingest_data.get("video") or {}
        transcript = ingest_data.get("transcript") or {}
        video_id = video.get("video_id") or transcript.get("video_id") or "video"
        title = video.get("title") or f"YouTube {video_id}"

        segments = _normalise_segments(transcript)
        if not segments:
            raise HTTPException(status_code=502, detail="no transcript segments returned")

        chunks = _chunk_segments(video_id, segments)
        if not chunks:
            raise HTTPException(status_code=502, detail="unable to derive transcript chunks")

        hirag_items = _build_hirag_items(video_id, namespace, chunks)
        event_bus = _event_bus(request)
        if event_bus:
            await event_bus.publish(
                "kb.upsert.request.v1",
                _kb_event_payload(hirag_items, namespace, video_id),
                source="gateway",
                correlation_id=video_id,
            )

        hirag_base = os.getenv("HIRAG_URL", "http://hi-rag-gateway-v2:8086").rstrip("/")
        if not hirag_base:
            raise HTTPException(status_code=503, detail="HIRAG_URL not configured")
        try:
            upsert_resp = await client.post(
                f"{hirag_base}/hirag/upsert-batch",
                json={"items": hirag_items, "ensure_collection": True, "index_lexical": True},
            )
            upsert_resp.raise_for_status()
            hirag_upsert = upsert_resp.json()
        except httpx.HTTPError as exc:
            logger.error("/hirag/upsert-batch failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"Hi-RAG upsert failed: {exc}")

        if event_bus:
            await event_bus.publish(
                "kb.upsert.result.v1",
                {"upserted_count": len(hirag_items), "meta": {"video_id": video_id}},
                source="gateway",
                correlation_id=video_id,
            )

        query_text = body.query or title
        hirag_query = None
        try:
            query_resp = await client.post(
                f"{hirag_base}/hirag/query",
                json={"query": query_text, "namespace": namespace, "k": 5},
            )
            if query_resp.status_code < 500:
                hirag_query = query_resp.json()
        except Exception as exc:  # pragma: no cover - network availability dependent
            logger.debug("/hirag/query failed: %s", exc)

        cgp_doc, constellations = _build_cgp(video_id, title, namespace, chunks)
        shape_id = ingest_cgp(cgp_doc)
        const_ids = [const["id"] for const in constellations]
        decode_resp = geometry_decode_text(
            GeometryDecodeTextRequest(
                shape_id=shape_id,
                constellation_ids=const_ids,
                per_constellation=body.per_constellation,
                codebook_path=body.codebook_path,
            )
        )
        calib = geometry_calibration_report(cgp=CGP.model_validate(cgp_doc), codebook_path=body.codebook_path)

        graph_sample = await _upsert_neo4j(shape_id, video_id, constellations)

        jelly_base = os.getenv("JELLYFIN_BRIDGE_URL") or os.getenv("JELLYFIN_URL", "").rstrip("/")
        playback = None
        if jelly_base:
            try:
                playback_resp = await client.post(
                    f"{jelly_base}/jellyfin/playback-url",
                    json={"video_id": video_id, "t": segments[0]["start"] if segments else 0.0},
                )
                if playback_resp.status_code < 500:
                    playback = playback_resp.json()
            except Exception as exc:  # pragma: no cover
                playback = {"error": str(exc)}

    events = event_bus.recent(10) if event_bus else []

    manifest = {
        "video": {
            "video_id": video_id,
            "title": title,
            "namespace": namespace,
            "thumbnail": video.get("thumb"),
            "segments_indexed": len(chunks),
        },
        "ingest": ingest_data,
        "hirag": {"upsert": hirag_upsert, "query": hirag_query},
        "shape": {
            "shape_id": shape_id,
            "constellations": const_ids,
            "data_url": f"/data/{shape_id}.json",
            "artifacts": {"reconstruction_report": "/artifacts/reconstruction_report.md"},
            "decode": decode_resp,
            "calibration": calib,
        },
        "neo4j": {
            "points_indexed": len(graph_sample) if graph_sample else 0,
            "sample": graph_sample,
        },
        "playback": playback,
        "events": events,
    }
    return manifest


def _run_offline(body: DemoRunRequest) -> Dict[str, Any]:
    fixture = Path(__file__).resolve().parents[2] / "tests" / "data" / "cgp_fixture.json"
    if body.cgp is not None:
        cgp_obj = body.cgp
    else:
        if not fixture.exists():
            raise HTTPException(status_code=500, detail="Fixture cgp not found")
        cgp_obj = json.loads(fixture.read_text(encoding="utf-8"))
    cgp = CGP.model_validate(cgp_obj)
    shape_id = ingest_cgp(cgp.model_dump())
    const_ids = [const.id for sn in cgp.super_nodes for const in sn.constellations if const.id]
    decode_resp = geometry_decode_text(
        GeometryDecodeTextRequest(
            shape_id=shape_id,
            constellation_ids=const_ids,
            per_constellation=body.per_constellation,
            codebook_path=body.codebook_path,
        )
    )
    calib = geometry_calibration_report(cgp=cgp, codebook_path=body.codebook_path)
    return {
        "mode": "offline",
        "shape": {
            "shape_id": shape_id,
            "constellations": const_ids,
            "data_url": f"/data/{shape_id}.json",
            "decode": decode_resp,
            "calibration": calib,
            "artifacts": {"reconstruction_report": "/artifacts/reconstruction_report.md"},
        },
        "events": [],
    }


def _normalise_segments(transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
    segs = transcript.get("segments") or []
    out: List[Dict[str, Any]] = []
    for seg in segs:
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or seg.get("start_s") or 0.0)
        end = float(seg.get("end") or seg.get("end_s") or (start + 0.5))
        if end <= start:
            end = start + 0.5
        out.append({"start": start, "end": end, "text": text})
    if not out and transcript.get("text"):
        text = str(transcript.get("text") or "").strip()
        out.append({"start": 0.0, "end": max(5.0, len(text) / 8.0), "text": text})
    out.sort(key=lambda item: (item["start"], item["end"]))
    return out


def _chunk_segments(video_id: str, segments: List[Dict[str, Any]], group_size: int = 5, max_groups: int = 6) -> List[Dict[str, Any]]:
    trimmed = segments[: group_size * max_groups]
    chunks: List[Dict[str, Any]] = []
    for idx in range(0, len(trimmed), group_size):
        group = trimmed[idx : idx + group_size]
        if not group:
            continue
        start = group[0]["start"]
        end = group[-1]["end"]
        chunk_text = " ".join(seg["text"] for seg in group)
        chunk_id = f"{video_id}:{int(start * 1000):06d}"
        points = []
        for seg in group:
            point_id = f"pt:{video_id}:{int(seg['start'] * 1000):06d}"
            points.append(
                {
                    "id": point_id,
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "chunk_id": chunk_id,
                }
            )
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "start": start,
                "end": end,
                "points": points,
            }
        )
        if len(chunks) >= max_groups:
            break
    return chunks


def _build_hirag_items(video_id: str, namespace: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    doc_id = f"yt:{video_id}"
    items = []
    for chunk in chunks:
        items.append(
            {
                "doc_id": doc_id,
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "namespace": namespace,
                "payload": {
                    "video_id": video_id,
                    "chunk_id": chunk["chunk_id"],
                    "start_s": chunk["start"],
                    "end_s": chunk["end"],
                },
            }
        )
    return items


def _kb_event_payload(items: List[Dict[str, Any]], namespace: str, video_id: str) -> Dict[str, Any]:
    entries = []
    for item in items:
        payload = item.get("payload") or {}
        entries.append(
            {
                "id": item.get("chunk_id"),
                "text": item.get("text"),
                "metadata": {
                    "video_id": video_id,
                    "namespace": namespace,
                    "start_s": payload.get("start_s"),
                    "end_s": payload.get("end_s"),
                },
            }
        )
    return {"namespace": namespace, "items": entries}


def _build_cgp(
    video_id: str,
    title: str,
    namespace: str,
    chunks: List[Dict[str, Any]],
    bins: int = 8,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    duration = max((chunk["end"] for chunk in chunks), default=1.0)
    duration = max(duration, 1e-6)
    constellations: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        center = ((chunk["start"] + chunk["end"]) / 2.0) / duration
        angle = center * math.tau
        magnitude = min(1.0, 0.2 + len(chunk["text"]) / 800.0)
        anchor = [math.cos(angle) * magnitude, math.sin(angle) * magnitude, min(1.0, (chunk["end"] - chunk["start"]) / duration)]
        spec = _spectrum_from_text(chunk["text"], bins=bins)
        points = []
        for point in chunk["points"]:
            seg_text = point["text"]
            start = point["start"]
            end = point["end"]
            proj = max(0.05, min(1.0, ((start + end) / 2.0) / duration))
            conf = max(0.2, min(0.95, len(seg_text) / 120.0))
            points.append(
                {
                    "id": point["id"],
                    "modality": "video",
                    "ref_id": f"video:{video_id}#t={start:.2f}-{end:.2f}",
                    "video_id": video_id,
                    "proj": round(proj, 4),
                    "conf": round(conf, 4),
                    "text": seg_text,
                    "t_start": start,
                    "t_end": end,
                    "char_len": len(seg_text),
                    "word_count": len(seg_text.split()),
                    "summary": seg_text[:160],
                    "meta": {
                        "chunk_id": chunk["chunk_id"],
                        "namespace": namespace,
                    },
                }
            )
        constellations.append(
            {
                "id": f"{video_id}:{idx:02d}",
                "summary": f"{title} · Segment {idx + 1}",
                "anchor": [round(x, 6) for x in anchor],
                "radial_minmax": [round(max(0.0, chunk["start"] / duration), 6), round(min(1.0, chunk["end"] / duration), 6)],
                "spectrum": spec,
                "points": points,
                "meta": {
                    "video_id": video_id,
                    "start_s": chunk["start"],
                    "end_s": chunk["end"],
                    "text_excerpt": chunk["text"][:240],
                },
            }
        )
    cgp_doc = {
        "spec": "chit.cgp.v0.1",
        "meta": {
            "source": "pmoves-yt",
            "video_id": video_id,
            "title": title,
            "namespace": namespace,
            "bins": bins,
        },
        "super_nodes": [
            {
                "id": f"sn:{video_id}",
                "label": title,
                "summary": f"Auto-generated from transcript ({len(constellations)} segments)",
                "constellations": constellations,
            }
        ],
    }
    return cgp_doc, constellations


def _spectrum_from_text(text: str, bins: int = 8) -> List[float]:
    tokens = [tok for tok in re.findall(r"[\w']+", text.lower()) if len(tok) > 2]
    if not tokens:
        return [round(1.0 / bins, 6)] * bins
    counts = Counter(tokens)
    top = counts.most_common(bins)
    total = float(sum(freq for _, freq in top)) or 1.0
    spec = [freq / total for _, freq in top]
    if len(spec) < bins:
        spec.extend([0.0] * (bins - len(spec)))
    # Normalise and clamp
    norm = sum(spec) or 1.0
    return [round(max(0.0, val / norm), 6) for val in spec]


async def _upsert_neo4j(shape_id: str, video_id: str, constellations: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    driver = neo4j_driver
    if driver is None:
        return None

    def _write() -> List[Dict[str, Any]]:
        with driver.session() as session:  # type: ignore[operator]
            session.run("MATCH (c:Constellation {shape_id:$shape_id}) DETACH DELETE c", shape_id=shape_id)
            for const in constellations:
                session.run(
                    """
                    MERGE (v:Video {video_id:$video_id})
                    MERGE (c:Constellation {id:$cid})
                    SET c.shape_id=$shape_id, c.summary=$summary, c.start_s=$start, c.end_s=$end
                    MERGE (v)-[:HAS_CONSTELLATION]->(c)
                    """,
                    video_id=video_id,
                    cid=const["id"],
                    shape_id=shape_id,
                    summary=const.get("summary"),
                    start=const.get("meta", {}).get("start_s"),
                    end=const.get("meta", {}).get("end_s"),
                )
                for point in const.get("points", []):
                    session.run(
                        """
                        MERGE (p:Point {id:$pid})
                        SET p += {text:$text, proj:$proj, conf:$conf, t_start:$t_start, t_end:$t_end, modality:$modality}
                        WITH p
                        MERGE (c:Constellation {id:$cid})
                        MERGE (c)-[:HAS]->(p)
                        MERGE (m:MediaRef {uid:$ref})
                        SET m += {video_id:$video_id, start_s:$t_start, end_s:$t_end}
                        MERGE (p)-[:LOCATES]->(m)
                        """,
                        pid=point.get("id"),
                        text=point.get("text"),
                        proj=point.get("proj"),
                        conf=point.get("conf"),
                        t_start=point.get("t_start"),
                        t_end=point.get("t_end"),
                        modality=point.get("modality"),
                        cid=const.get("id"),
                        ref=point.get("ref_id"),
                        video_id=video_id,
                    )
            result = session.run(
                """
                MATCH (c:Constellation {shape_id:$shape_id})-[:HAS]->(p:Point)
                RETURN c.id AS constellation_id, p{.*, id:p.id} AS point
                ORDER BY p.proj DESC LIMIT 10
                """,
                shape_id=shape_id,
            )
            return [dict(row) for row in result]

    try:
        return await asyncio.to_thread(_write)
    except Exception as exc:  # pragma: no cover - depends on runtime DB
        logger.warning("Neo4j upsert failed: %s", exc)
        return None
