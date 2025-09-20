"""MindMap router wiring for the gateway demo service."""
from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException, Query
from neo4j import GraphDatabase
from pydantic import BaseModel

router = APIRouter(tags=["MindMap"])

logger = logging.getLogger("pmoves.gateway.mindmap")

NEO4J_URL = os.getenv("NEO4J_URL") or os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") or os.getenv("NEO4J_PASS", "neo4j")

driver = None
if NEO4J_URL:
    try:  # pragma: no cover - depends on external DB
        driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Neo4j unavailable at %s: %s", NEO4J_URL, exc)
        driver = None


class MindMapItem(BaseModel):
    point: dict
    media: dict


class MindMapResponse(BaseModel):
    items: List[MindMapItem]


@router.get("/mindmap/{constellation_id}", response_model=MindMapResponse)
def mindmap(
    constellation_id: str,
    modalities: str = Query("text,video,audio,doc,image"),
    minProj: float = 0.5,
    minConf: float = 0.5,
    limit: int = 200,
):
    """Return MindMap points and media for a constellation."""
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")

    mods = [m.strip() for m in modalities.split(",") if m.strip()]
    if not mods:
        raise HTTPException(status_code=400, detail="At least one modality is required")

    query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point)-[:LOCATES]->(m:MediaRef) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN p{.*, id:p.id} AS point, m{.*, uid:m.uid} AS media ORDER BY p.proj DESC LIMIT $limit"
    )

    with driver.session() as session:
        records = session.run(
            query,
            cid=constellation_id,
            mods=mods,
            minProj=minProj,
            minConf=minConf,
            limit=limit,
        )
        items = [{"point": record["point"], "media": record["media"]} for record in records]

    return {"items": items}
