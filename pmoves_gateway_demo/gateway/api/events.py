from fastapi import APIRouter
from starlette.responses import StreamingResponse
import asyncio
import json
from typing import AsyncIterator, Dict, Any

router = APIRouter(prefix="/events", tags=["Events"])

_QUEUE: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)


def emit_event(evt: Dict[str, Any]) -> None:
    try:
        _QUEUE.put_nowait(evt)
    except asyncio.QueueFull:  # drop oldest
        try:
            _QUEUE.get_nowait()
        except Exception:
            pass
        try:
            _QUEUE.put_nowait(evt)
        except Exception:
            pass


async def _sse() -> AsyncIterator[bytes]:
    # send a hello
    yield b"event: hello\n\n"
    while True:
        evt = await _QUEUE.get()
        data = json.dumps(evt).encode()
        yield b"event: message\n"
        yield b"data: " + data + b"\n\n"


@router.get("/stream")
async def stream():
    return StreamingResponse(_sse(), media_type="text/event-stream")

