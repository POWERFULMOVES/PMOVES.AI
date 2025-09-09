import os, json
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import httpx

app = FastAPI(title="Jellyfin Bridge", version="0.1.0")

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY", "")
JELLYFIN_USER_ID = os.environ.get("JELLYFIN_USER_ID", "")
SUPA = os.environ.get("SUPA_REST_URL", "http://postgrest:3000")

@app.get("/healthz")
def healthz():
    return {"ok": True}

def _supa_patch(table: str, match: Dict[str,Any], patch: Dict[str,Any]):
    qs = []
    for k, v in match.items():
        if isinstance(v, str):
            qs.append(f"{k}=eq.{v}")
        else:
            qs.append(f"{k}=eq.{json.dumps(v)}")
    url = f"{SUPA}/{table}?" + "&".join(qs)
    r = httpx.patch(url, json=patch, timeout=10)
    r.raise_for_status()
    return r.json()

def _supa_get(table: str, match: Dict[str,Any]):
    qs = []
    for k, v in match.items():
        if isinstance(v, str):
            qs.append(f"{k}=eq.{v}")
        else:
            qs.append(f"{k}=eq.{json.dumps(v)}")
    url = f"{SUPA}/{table}?" + "&".join(qs)
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

@app.post("/jellyfin/link")
def jellyfin_link(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); item = body.get('jellyfin_item_id')
    if not vid or not item: raise HTTPException(400, 'video_id and jellyfin_item_id required')
    patch = {"meta": {"jellyfin_item_id": item}}
    _supa_patch('videos', {'video_id': vid}, patch)
    return {"ok": True}

@app.post("/jellyfin/refresh")
def jellyfin_refresh(body: Dict[str,Any] = Body({})):
    # Best-effort: call System/Info if creds provided; otherwise noop
    if not JELLYFIN_URL or not JELLYFIN_API_KEY:
        return {"ok": True, "skipped": True}
    try:
        r = httpx.get(f"{JELLYFIN_URL}/System/Info", headers={"X-Emby-Token": JELLYFIN_API_KEY}, timeout=6)
        r.raise_for_status()
        return {"ok": True, "system": r.json().get('Version')}
    except Exception as e:
        raise HTTPException(502, f"jellyfin error: {e}")

@app.post("/jellyfin/playback-url")
def jellyfin_playback_url(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); t = float(body.get('t') or 0.0)
    if not vid: raise HTTPException(400, 'video_id required')
    rows = _supa_get('videos', {'video_id': vid})
    if not rows: raise HTTPException(404, 'video not found')
    meta = rows[0].get('meta') or {}
    item = meta.get('jellyfin_item_id')
    if not item and not JELLYFIN_URL:
        # return a placeholder local URL
        return {"ok": True, "url": f"/web/player?video_id={vid}&t={t}"}
    if not (item and JELLYFIN_URL):
        raise HTTPException(412, 'missing jellyfin mapping or JELLYFIN_URL')
    # Build a simple playback URL. Jellyfin supports start time in ticks for direct stream; use seconds for web app link.
    url = f"{JELLYFIN_URL}/web/index.html#!/details?id={item}&serverId=local&startTime={int(t)}"
    return {"ok": True, "url": url}

@app.get("/jellyfin/search")
def jellyfin_search(query: str):
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        raise HTTPException(412, 'JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_USER_ID required')
    try:
        r = httpx.get(
            f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items",
            params={"searchTerm": query, "IncludeItemTypes": "Movie,Video"},
            headers={"X-Emby-Token": JELLYFIN_API_KEY}, timeout=8
        )
        r.raise_for_status()
        j = r.json()
        items = j.get('Items') or []
        out = [{"Id": it.get('Id'), "Name": it.get('Name'), "ProductionYear": it.get('ProductionYear')} for it in items]
        return {"ok": True, "items": out}
    except Exception as e:
        raise HTTPException(502, f"jellyfin search error: {e}")

@app.post("/jellyfin/map-by-title")
def jellyfin_map_by_title(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); title = body.get('title')
    if not vid: raise HTTPException(400, 'video_id required')
    if not title:
        rows = _supa_get('videos', {'video_id': vid})
        if not rows:
            raise HTTPException(404, 'video not found')
        title = rows[0].get('title')
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        raise HTTPException(412, 'JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_USER_ID required')
    # search and pick best match by simple case-insensitive inclusion
    r = httpx.get(
        f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items",
        params={"searchTerm": title, "IncludeItemTypes": "Movie,Video"},
        headers={"X-Emby-Token": JELLYFIN_API_KEY}, timeout=8
    )
    r.raise_for_status()
    items = (r.json().get('Items') or [])
    best = None
    tnorm = (title or '').lower()
    for it in items:
        name = (it.get('Name') or '').lower()
        if tnorm in name or name in tnorm:
            best = it; break
    if not best and items:
        best = items[0]
    if not best:
        raise HTTPException(404, 'no jellyfin items matched')
    _supa_patch('videos', {'video_id': vid}, {"meta": {"jellyfin_item_id": best.get('Id')}})
    return {"ok": True, "mapped": {"video_id": vid, "jellyfin_item_id": best.get('Id'), "name": best.get('Name')}}
