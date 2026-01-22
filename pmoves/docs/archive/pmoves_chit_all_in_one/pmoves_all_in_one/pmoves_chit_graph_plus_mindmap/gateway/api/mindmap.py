import os
from typing import List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from neo4j import GraphDatabase
router = APIRouter(tags=["MindMap"])
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "password")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
class MindMapItem(BaseModel):
    point: dict
    media: dict
class MindMapResponse(BaseModel):
    items: List[MindMapItem]
@router.get("/mindmap/{constellation_id}", response_model=MindMapResponse)
def mindmap(constellation_id: str, modalities: str = Query("text,video,audio,doc,image"), minProj: float = 0.5, minConf: float = 0.5, limit: int = 200):
    mods = [m.strip() for m in modalities.split(",") if m.strip()]
    if not mods: raise HTTPException(status_code=400, detail="At least one modality is required")
    q = ("MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point)-[:LOCATES]->(m:MediaRef) "
         "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj AND coalesce(p.conf,0.0) >= $minConf "
         "RETURN p{.*, id:p.id} AS point, m{.*, uid:m.uid} AS media ORDER BY p.proj DESC LIMIT $limit")
    with driver.session() as s:
        recs = s.run(q, cid=constellation_id, mods=mods, minProj=minProj, minConf=minConf, limit=limit)
        items = [{"point": r["point"], "media": r["media"]} for r in recs]
        return {"items": items}
