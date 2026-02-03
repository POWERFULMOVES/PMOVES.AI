from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set
import json, secrets

router = APIRouter(tags=["Signaling"])

ROOMS: Dict[str, Set[WebSocket]] = {}

@router.websocket("/ws/signaling")
async def signaling(ws: WebSocket, room: str = Query(...), peer: str = Query(None)):
    await ws.accept()
    peer_id = peer or secrets.token_hex(4)
    if room not in ROOMS: ROOMS[room] = set()
    ROOMS[room].add(ws)
    await _broadcast(room, {"type":"peer-join","peer":peer_id}, exclude=ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data); msg.setdefault("peer", peer_id)
            await _broadcast(room, msg, exclude=ws if msg.get("broadcast", True) else None)
    except WebSocketDisconnect:
        pass
    finally:
        ROOMS[room].discard(ws)
        await _broadcast(room, {"type":"peer-leave","peer":peer_id})

async def _broadcast(room: str, msg: dict, exclude: WebSocket=None):
    dead=[]
    # Snapshot clients to avoid 'set changed size during iteration' when peers join/leave
    clients = list(ROOMS.get(room, set()))
    for client in clients:
        if exclude is not None and client is exclude: continue
        try: await client.send_text(json.dumps(msg))
        except Exception: dead.append(client)
    if dead:
        room_set = ROOMS.get(room)
        if room_set is not None:
            for d in dead:
                room_set.discard(d)
            if not room_set:
                ROOMS.pop(room, None)
