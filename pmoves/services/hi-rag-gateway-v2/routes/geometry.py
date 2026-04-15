"""Geometry, mindmap, signaling, and mesh endpoints for hi-rag-gateway-v2."""

import json
import math
import io
from typing import Any, Dict, List, Optional

import anyio
from fastapi import APIRouter, Body, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
import urllib3

from config import (
    CHIT_REQUIRE_SIGNATURE, CHIT_PASSPHRASE, CHIT_DECRYPT_ANCHORS, CHIT_PERSIST_DB,
    CHIT_DECODE_TEXT, CHIT_DECODE_IMAGE, CHIT_DECODE_AUDIO,
    CHIT_CODEBOOK_PATH, CHIT_T5_MODEL, CHIT_CLIP_MODEL,
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE,
    GAN_SIDECAR_ENABLED, NATS_URL, NAMESPACE_DEFAULT, logger,
)
from security import (
    require_tailscale, require_admin_tailscale,
    _tailscale_ip_allowed, _tailscale_violation_detail,
    _fetch_remote_image, _enrich_mindmap_item,
)
from geometry_bus import (
    shape_store, _hrm_controller,
    _room_add, _room_remove, _room_broadcast, _room_broadcast_roster,
    _geometry_context, _get_active_builder_pack,
    _load_codebook, _get_gan_sidecar, _persist_cgp_to_db,
)
import clients.neo4j as _neo4j_mod

# Access _neo4j_mod.driver via module attribute so test monkeypatching of module._neo4j_mod.driver
# (re-exported via app.py) can propagate into routes.

router = APIRouter()


@router.get("/mindmap/{constellation_id}")
def mindmap_route(
    constellation_id: str,
    modalities: str = "text,video,audio,doc,image",
    minProj: float = 0.5,
    minConf: float = 0.5,
    limit: int = 200,
    offset: int = 0,
    enrich: bool = True,
    _=Depends(require_tailscale),
):
    if _neo4j_mod.driver is None:
        raise HTTPException(503, "Neo4j unavailable")
    mods = [m.strip() for m in modalities.split(",") if m.strip()]
    if not mods:
        raise HTTPException(400, "At least one modality is required")
    if limit <= 0:
        raise HTTPException(400, "limit must be positive")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    db_limit = limit + 1
    stats_map: Dict[str, int] = {}
    total_query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN count(*) AS total"
    )
    stats_query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN coalesce(p.modality,'unknown') AS modality, count(*) AS count"
    )
    query = (
        "MATCH (c:Constellation {id:$cid})-[:HAS]->(p:Point)-[:LOCATES]->(m:MediaRef) "
        "WHERE p.modality IN $mods AND coalesce(p.proj,0.0) >= $minProj "
        "AND coalesce(p.conf,0.0) >= $minConf "
        "RETURN p{.*, id:p.id} AS point, m{.*, uid:m.uid} AS media "
        "ORDER BY p.proj DESC SKIP $offset LIMIT $limit"
    )
    try:
        with _neo4j_mod.driver.session() as session:
            total_result = session.run(
                total_query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
            )
            total_row = next(iter(total_result), {"total": 0})
            total = int(total_row.get("total") or 0)
            stats_rows = session.run(
                stats_query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
            )
            stats_map: Dict[str, int] = {}
            for row in stats_rows:
                mod = str(row.get("modality") or "unknown").lower()
                stats_map[mod] = int(row.get("count") or 0)
            records = session.run(
                query,
                cid=constellation_id,
                mods=mods,
                minProj=minProj,
                minConf=minConf,
                limit=db_limit,
                offset=offset,
            )
            raw_items = [(rec["point"], rec["media"]) for rec in records]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mindmap query failed")
        raise HTTPException(500, f"mindmap query failed: {exc}")
    has_more = len(raw_items) > limit
    trimmed = raw_items[:limit]
    if enrich:
        items = [
            _enrich_mindmap_item(constellation_id, point or {}, media or {})
            for point, media in trimmed
        ]
    else:
        items = [{"point": point, "media": media} for point, media in trimmed]
    returned = len(items)
    remaining = max(total - (offset + returned), 0)
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "total": total,
        "remaining": remaining,
        "has_more": has_more,
        "stats": {"per_modality": stats_map},
    }


@router.post("/geometry/event")
def geometry_event(body: Dict[str, Any], _=Depends(require_tailscale)):
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    payload = body.get("data") if isinstance(body, dict) else None
    if not isinstance(payload, dict):
        raise HTTPException(400, "missing data")
    if CHIT_REQUIRE_SIGNATURE:
        try:
            from tools.chit_security import verify_cgp, decrypt_anchors
        except Exception as exc:
            logger.exception("security module import failed")
            raise HTTPException(500, f"security module not available: {type(exc).__name__}: {exc}") from exc
        if not CHIT_PASSPHRASE:
            raise HTTPException(500, "CHIT_REQUIRE_SIGNATURE=true but CHIT_PASSPHRASE not set")
        if not verify_cgp(payload, CHIT_PASSPHRASE):
            raise HTTPException(401, "invalid CGP signature")
        if CHIT_DECRYPT_ANCHORS:
            payload = decrypt_anchors(payload, CHIT_PASSPHRASE)
    shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": payload})
    if CHIT_PERSIST_DB and PGHOST and PGUSER and PGPASSWORD and PGDATABASE:
        try:
            _persist_cgp_to_db(payload)
        except Exception:
            logger.exception("persist CGP failed")
    try:
        import anyio
        async def _notify():
            await _room_broadcast("geometry", {"type": "geometry.cgp.v1", "data": payload})
        anyio.from_thread.run(_notify)
    except Exception:
        pass
    return {"ok": True}


@router.get("/shape/point/{point_id}/jump")
def shape_point_jump(point_id: str, _=Depends(require_tailscale)):
    if shape_store is None:
        raise HTTPException(503, "ShapeStore unavailable")
    loc = shape_store.jump_locator(point_id)
    if not loc:
        raise HTTPException(404, f"point '{point_id}' not found")
    return {"ok": True, "locator": loc}


@router.post("/geometry/decode/text")
def geometry_decode_text(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_TEXT:
        raise HTTPException(501, "text decoder disabled")
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    k = int(body.get("k", 5))
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    context_body = dict(body)
    context_body.setdefault("modality", "text")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
    namespace = str(
        body.get("namespace")
        or (const.get("namespace") if isinstance(const, dict) and const.get("namespace") else NAMESPACE_DEFAULT)
    )
    pts: List[Dict[str, Any]] = []
    if const:
        for p in const.get("points", []) or []:
            cid = p.get("id")
            if not cid:
                continue
            pts.append({
                "id": cid,
                "text": p.get("text"),
                "proj": p.get("proj"),
                "conf": p.get("conf"),
                "meta": p.get("meta"),
                "ref_id": p.get("ref_id") or p.get("doc_id") or p.get("video_id"),
            })
    pts.sort(key=lambda x: (x.get("conf") or 0.0, x.get("proj") or 0.0), reverse=True)
    top_pts = pts[:k]

    if mode == "learned":
        try:
            from transformers import pipeline
        except (ImportError, ModuleNotFoundError) as exc:
            raise HTTPException(500, f"transformers not available: {type(exc).__name__}")
        texts = []
        cb = _load_codebook(CHIT_CODEBOOK_PATH)
        for rec in cb[: min(64, len(cb))]:
            t = rec.get("text") or rec.get("summary")
            if t:
                texts.append(t)
        if const:
            s = const.get("summary")
            if s:
                texts.insert(0, s)
        if not texts:
            raise HTTPException(400, "no codebook or constellation text available")
        nlp = pipeline("summarization", model=CHIT_T5_MODEL)
        out = nlp("\n".join(texts)[:4000], max_length=128, min_length=32, do_sample=False)
        summary = out[0].get("summary_text", "")
        summary, hrm_info = _hrm_controller.maybe_refine(summary, namespace=namespace)
        return {
            "mode": mode,
            "summary": summary,
            "used": len(texts),
            "hrm": hrm_info,
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }

    elif mode == "swarm":
        sidecar = _get_gan_sidecar()
        accept_threshold = float(body.get("accept_threshold", 0.55))
        max_edits = int(body.get("max_edits", 1))
        if sidecar is None:
            return {
                "mode": mode,
                "raw_points": top_pts,
                "selected": top_pts[0] if top_pts else None,
                "candidates": [],
                "telemetry": {
                    "enabled": GAN_SIDECAR_ENABLED,
                    "decision": "unavailable",
                    "threshold": accept_threshold,
                },
                "namespace": namespace,
                "modality": modality,
                "builder_pack": builder_pack,
            }
        review = sidecar.review_text_candidates(
            top_pts,
            enabled=GAN_SIDECAR_ENABLED,
            max_edits=max(0, max_edits),
            accept_threshold=accept_threshold,
        )
        review["mode"] = mode
        review["raw_points"] = top_pts
        review["namespace"] = namespace
        review["modality"] = modality
        review["builder_pack"] = builder_pack
        return review

    else:
        hrm_info = _hrm_controller.status(namespace) if _hrm_controller is not None else None
        return {
            "mode": mode,
            "points": top_pts,
            "hrm": hrm_info,
            "namespace": namespace,
            "modality": modality,
            "builder_pack": builder_pack,
        }


@router.post("/geometry/calibration/report")
def geometry_calibration_report(body: Dict[str, Any], _=Depends(require_tailscale)):
    def _js(p, q):
        import math
        def _kl(a, b):
            eps = 1e-9
            s = 0.0
            for i in range(min(len(a), len(b))):
                ai = max(a[i], eps); bi = max(b[i], eps)
                s += ai * math.log(ai/bi)
            return s
        m = [(pi+qi)*0.5 for pi,qi in zip(p,q)]
        return 0.5*(_kl(p,m)+_kl(q,m))
    def _w1(p, q):
        from itertools import accumulate
        cdp=list(accumulate(p)); cdq=list(accumulate(q))
        n=max(1,len(cdp));
        return sum(abs((cdp[i] if i<len(cdp) else 1.0)-(cdq[i] if i<len(cdq) else 1.0)) for i in range(n))/n
    data = body.get("data")
    const_ids = body.get("constellation_ids") or []
    consts = []
    if isinstance(data, dict):
        for sn in data.get("super_nodes", []) or []:
            consts.extend(sn.get("constellations", []) or [])
    for cid in const_ids:
        c = shape_store.get_constellation(cid) if shape_store else None
        if c: consts.append(c)
    report = []
    for c in consts:
        s = c.get("spectrum") or []
        if not s:
            report.append({"id": c.get("id"), "coverage": 0.0, "js": None, "w1": None}); continue
        s = [float(x) for x in s]; mass = sum(s) or 1.0; s = [x/mass for x in s]
        u = [1.0/len(s)]*len(s)
        js = _js(s, u); w1 = _w1(s, u); coverage = sum(1 for x in s if x > 0.01)/float(len(s))
        report.append({"id": c.get("id"), "coverage": coverage, "js": js, "w1": w1})
    return {"constellations": report}


@router.post("/geometry/decode/image")
def geometry_decode_image(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_IMAGE:
        raise HTTPException(501, "image decoder disabled")
    try:
        from sentence_transformers import SentenceTransformer
        from PIL import Image
        import numpy as np
    except Exception:
        raise HTTPException(500, "missing dependencies for image decode (sentence-transformers, Pillow)")
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    images = body.get("images") or []
    if not images:
        raise HTTPException(400, "images list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    context_body = dict(body)
    context_body.setdefault("modality", "image")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
    try:
        model = SentenceTransformer(CHIT_CLIP_MODEL)
        text_emb = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)
        img_list = []
        for url in images:
            try:
                r = _fetch_remote_image(url)
            except (urllib3.exceptions.HTTPError, OSError) as e:
                raise HTTPException(502, f"failed to fetch image: {e}")
            image_bytes = r.data
            if not image_bytes:
                raise HTTPException(400, f"remote image returned empty body for {url}")
            try:
                img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            except Exception as e:
                raise HTTPException(400, f"invalid image payload for {url}: {e}")
            img_list.append(img)
        img_embs = model.encode(img_list, normalize_embeddings=True, convert_to_numpy=True)
        sims = (img_embs @ text_emb.T).squeeze()
        ranked = sorted(zip(images, sims.tolist()), key=lambda x: x[1], reverse=True)
        if mode == "swarm":
            payload = {"mode": mode, "ranked": [{"url": u, "score": float(s)} for u, s in ranked]}
            sidecar = _get_gan_sidecar()
            accept_threshold = float(body.get("accept_threshold", 0.55))
            max_edits = int(body.get("max_edits", 0))
            if sidecar is None:
                payload["swarm"] = {
                    "selected": None,
                    "candidates": [],
                    "telemetry": {
                        "enabled": GAN_SIDECAR_ENABLED,
                        "decision": "unavailable",
                        "threshold": accept_threshold,
                    },
                }
            else:
                captions = body.get("captions") or {}
                candidates = []
                for item in payload["ranked"]:
                    url = item["url"]
                    caption = captions.get(url) or text or f"Image candidate {url}"
                    candidates.append({"id": url, "text": caption})
                payload["swarm"] = sidecar.review_text_candidates(
                    candidates,
                    enabled=GAN_SIDECAR_ENABLED,
                    max_edits=max(0, max_edits),
                    accept_threshold=accept_threshold,
                )
            return payload
        else:
            return {
                "ranked": [{"url": u, "score": float(s)} for u, s in ranked],
                "namespace": namespace,
                "modality": modality,
                "builder_pack": builder_pack,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("image decode error")
        raise HTTPException(500, f"image decode error: {e}")


@router.post("/geometry/decode/audio")
def geometry_decode_audio(body: Dict[str, Any], _=Depends(require_tailscale)):
    if not CHIT_DECODE_AUDIO:
        raise HTTPException(501, "audio decoder disabled")
    try:
        from laion_clap import CLAP_Module
    except Exception:
        raise HTTPException(500, "missing laion-clap/torch; install extras and set CHIT_DECODE_AUDIO=true")
    mode = (body.get("mode") or "geometry").lower()
    const_id = body.get("constellation_id")
    audios = body.get("audios") or []
    if not audios:
        raise HTTPException(400, "audios list required")
    const = shape_store.get_constellation(const_id) if (shape_store and const_id) else None
    text = body.get("text") or (const.get("summary") if const else None)
    if not text:
        raise HTTPException(400, "text or constellation summary required for anchor")
    context_body = dict(body)
    context_body.setdefault("modality", "audio")
    namespace, modality = _geometry_context(context_body, const)
    builder_pack = _get_active_builder_pack(namespace, modality)
    try:
        model = CLAP_Module(enable_fusion=True)
        model.load_ckpt()
        a_emb = model.get_audio_embedding_from_filelist(x=audios, use_tensor=False)
        t_emb = model.get_text_embedding([text], use_tensor=False)
        import numpy as np
        a = np.asarray(a_emb, dtype=float)
        t = np.asarray(t_emb, dtype=float).reshape(1, -1)
        a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        t = t / (np.linalg.norm(t, axis=1, keepdims=True) + 1e-9)
        sims = (a @ t.T).squeeze()
        ranked = sorted(zip(audios, sims.tolist()), key=lambda x: x[1], reverse=True)
        if mode == "swarm":
            payload = {"mode": mode, "ranked": [{"path": u, "score": float(s)} for u, s in ranked]}
            sidecar = _get_gan_sidecar()
            accept_threshold = float(body.get("accept_threshold", 0.55))
            max_edits = int(body.get("max_edits", 0))
            if sidecar is None:
                payload["swarm"] = {
                    "selected": None,
                    "candidates": [],
                    "telemetry": {
                        "enabled": GAN_SIDECAR_ENABLED,
                        "decision": "unavailable",
                        "threshold": accept_threshold,
                    },
                }
            else:
                captions = body.get("captions") or {}
                candidates = []
                for item in payload["ranked"]:
                    path = item["path"]
                    caption = captions.get(path) or text or f"Audio candidate {path}"
                    candidates.append({"id": path, "text": caption})
                payload["swarm"] = sidecar.review_text_candidates(
                    candidates,
                    enabled=GAN_SIDECAR_ENABLED,
                    max_edits=max(0, max_edits),
                    accept_threshold=accept_threshold,
                )
            return payload
        else:
            return {
                "ranked": [{"path": u, "score": float(s)} for u, s in ranked],
                "namespace": namespace,
                "modality": modality,
                "builder_pack": builder_pack,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("audio decode error")
        raise HTTPException(500, f"audio decode error: {e}")


@router.websocket("/ws/signaling/{room}")
async def ws_signaling(ws: WebSocket, room: str):
    ip = ws.client.host if ws.client else "127.0.0.1"
    if not _tailscale_ip_allowed(ip, admin_only=False):
        logger.warning("Rejecting websocket connection from non-Tailnet IP %s", ip)
        await ws.close(code=1008, reason=_tailscale_violation_detail(admin_only=False))
        return
    await ws.accept()
    await _room_add(room, ws)
    try:
        while True:
            data = await ws.receive_json()
            if isinstance(data, dict) and data.get("type") == "presence":
                pid = str(data.get("from") or "")
                from geometry_bus import _room_ws_id, _room_ids
                _room_ws_id.setdefault(room, {})[ws] = pid
                ids = _room_ids.setdefault(room, [])
                if pid and pid not in ids:
                    ids.append(pid)
                await _room_broadcast_roster(room)
                continue
            await _room_broadcast(room, {"room": room, "relay": data}, skip=ws)
    except WebSocketDisconnect:
        _room_remove(room, ws)
        await _room_broadcast_roster(room)
    except Exception:
        _room_remove(room, ws)
        try:
            await ws.close()
        except Exception:
            pass
        try:
            await _room_broadcast_roster(room)
        except Exception:
            pass


@router.post("/mesh/handshake")
def mesh_handshake(body: Dict[str, Any], _=Depends(require_admin_tailscale)):
    """Publish a shape-capsule to NATS mesh subject."""
    capsule = body.get("capsule")
    if not isinstance(capsule, dict):
        raise HTTPException(400, "capsule required")
    payload = {"type": "shape-capsule", "capsule": capsule}
    try:
        import nats as _nats

        async def _pub():
            nc = await _nats.connect(servers=[NATS_URL])
            await nc.publish("mesh.shape.handshake.v1", json.dumps(payload).encode())
            await nc.flush(); await nc.drain()
        anyio.from_thread.run(_pub)
        return {"ok": True}
    except Exception as e:
        logger.exception("mesh publish failed")
        raise HTTPException(500, f"mesh publish failed: {e}")


@router.post("/geometry/import_db")
def import_db(body: Dict[str, Any], _=Depends(require_admin_tailscale)):
    """Persist a CGP directly into Postgres, update ShapeStore, and broadcast."""
    payload = body.get("data")
    if not isinstance(payload, dict):
        cap = body.get("capsule") or {}
        if isinstance(cap, dict) and isinstance(cap.get("data"), dict):
            payload = cap.get("data")
    if not isinstance(payload, dict):
        raise HTTPException(400, "missing CGP data")
    shape_store.on_geometry_event({"type": "geometry.cgp.v1", "data": payload})
    try:
        _persist_cgp_to_db(payload)
    except Exception:
        logger.exception("import_db persist failed")
        raise HTTPException(500, "persist failed (check DB creds / RLS)")
    try:
        import anyio

        async def _notify():
            await _room_broadcast("geometry", {"type": "geometry.cgp.v1", "data": payload})
        anyio.from_thread.run(_notify)
    except Exception:
        pass
    return {"ok": True}
