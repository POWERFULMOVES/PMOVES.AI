"""
MAI-UI Agent — OpenAI-compatible serving service for GUI grounding + screenshot understanding.

Serves Tongyi-MAI/MAI-UI-2B (Qwen3-VL) on the SPARK GB10 GPU.
Provides:
  - POST /v1/chat/completions (OpenAI-compatible — drop-in for any agent)
  - POST /v1/gui/ground (structured GUI grounding — returns click coordinates)
  - POST /v1/gui/describe (screenshot OCR/description)
  - GET /healthz
  - GET /metrics

The model stays loaded in GPU memory across requests (singleton).
"""

import asyncio
import base64
import binascii
import io
import logging
import os
import re
import time
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from PIL import Image
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mai-ui-agent")

MODEL_PATH = os.environ.get(
    "MAI_UI_MODEL_PATH",
    os.path.expanduser("~/.cache/huggingface/hub/models--Tongyi-MAI--MAI-UI-2B/snapshots/503050934809558c8dfd2ddedaf9621fa74ac2de"),
)
PORT = int(os.environ.get("MAI_UI_PORT", "8220"))
HOST = os.environ.get("MAI_UI_HOST", "0.0.0.0")
MAX_TOKENS = int(os.environ.get("MAI_UI_MAX_TOKENS", "512"))

# ── Request-shaped resource bounds ───────────────────────────────────────────
# Every image input here is caller-controlled: the base64 length, the pixel
# dimensions inside it, and the resize target. Unbounded, one request can make a
# worker allocate gigabytes and take the node down for every other caller — so cap
# all three independently and answer 422 rather than dying.
MAX_IMAGE_BYTES = int(os.environ.get("MAI_UI_MAX_IMAGE_BYTES", str(16 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.environ.get("MAI_UI_MAX_IMAGE_PIXELS", str(64_000_000)))
MAX_RESIZE_DIM = int(os.environ.get("MAI_UI_MAX_RESIZE_DIM", "8192"))
# Pillow's own decompression-bomb guard, aligned to the same ceiling.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# Inference blocks (weights on GPU, or a synchronous HTTP proxy). It runs in a
# threadpool so /healthz and /metrics stay answerable, behind a semaphore so a burst
# of callers cannot queue unbounded generations against one GPU.
MAX_CONCURRENCY = max(1, int(os.environ.get("MAI_UI_MAX_CONCURRENCY", "2")))

# ── Backend selection ────────────────────────────────────────────────────────
# The fleet is heterogeneous: SPARK GB10 (arm64, unified memory) can hold the 2.1B
# weights resident, while other nodes should point at an OpenAI-compatible endpoint
# instead of pulling ~4GB of bfloat16 they will use intermittently.
#
# MAI_UI_MODEL_PATH alone cannot express that — it only swaps WHICH LOCAL snapshot
# loads. Without this switch, "cloud variant on the 4090, resident on SPARK" has
# nothing to configure.
#
#   MAI_UI_BACKEND=local  (default)  load weights, GPU singleton
#   MAI_UI_BACKEND=remote            proxy to MAI_UI_BASE_URL (OpenAI-compatible)
#
# The point is that /v1/gui/ground and /v1/gui/describe keep their SHAPE either way.
# Callers — Archon workflows, a browser-driving agent — never learn where inference
# happened, so node placement stays a deployment decision rather than a code path.
#
# MAI_UI_BASE_URL takes any OpenAI-compatible endpoint, so pointing a node's remote
# backend at TensorZero is a configuration choice rather than a code change.
BACKEND = os.environ.get("MAI_UI_BACKEND", "local").strip().lower()
BASE_URL = os.environ.get("MAI_UI_BASE_URL", "").rstrip("/")
REMOTE_MODEL = os.environ.get("MAI_UI_REMOTE_MODEL", "MAI-UI-2B")
# Optional; local runtimes (Ollama, LM Studio, llama.cpp) generally need no key.
REMOTE_API_KEY = os.environ.get("MAI_UI_API_KEY", "")
REMOTE_TIMEOUT = float(os.environ.get("MAI_UI_REMOTE_TIMEOUT", "120"))

# Roles the local chat template and the remote backend both understand. Anything
# else is rejected rather than dropped — a discarded system turn changes policy.
ALLOWED_ROLES = ("system", "user", "assistant")

if BACKEND not in ("local", "remote"):
    raise SystemExit(f"MAI_UI_BACKEND must be 'local' or 'remote', got {BACKEND!r}")
if BACKEND == "remote" and not BASE_URL:
    # Fail at import, not on first request: a misconfigured remote backend that only
    # surfaces when an agent is mid-workflow is far more expensive to diagnose.
    raise SystemExit("MAI_UI_BACKEND=remote requires MAI_UI_BASE_URL (OpenAI-compatible endpoint)")

# ── Model singleton ──────────────────────────────────────────────────────────

_model = None
_processor = None


def get_model():
    """Load MAI-UI once and keep it resident; returns the (model, processor) pair."""
    global _model, _processor
    if _model is None:
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        # torch.cuda.get_device_name(0) RAISES on a machine with no CUDA device, and
        # it sits inside the log call — so an un-guarded version dies here, before the
        # model load, with a CUDA error rather than a legible "no GPU" message. The
        # /healthz probe below already guards the same call; match it.
        device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        log.info(f"Loading MAI-UI-2B from {MODEL_PATH} on {device_name}...")
        t0 = time.time()
        _processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        _model = Qwen3VLForConditionalGeneration.from_pretrained(
            MODEL_PATH,
            dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        dt = time.time() - t0
        params = sum(p.numel() for p in _model.parameters()) / 1e9
        log.info(f"MAI-UI-2B loaded: {params:.1f}B params in {dt:.1f}s")
    return _model, _processor


# ── Helpers ──────────────────────────────────────────────────────────────────

def decode_image(image_data: str) -> Image.Image:
    """Decode a base64 / data-URI image, rejecting malformed or oversized input with 422."""
    if image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[1]
    # Data URIs are sometimes line-wrapped; strip whitespace so validate=True only
    # rejects genuinely malformed payloads.
    image_data = "".join(image_data.split())

    # Check the ENCODED length first — base64 is 4/3 of the decoded size, so an
    # oversized payload is refused before the decoded bytes are ever allocated.
    if len(image_data) > (MAX_IMAGE_BYTES * 4 // 3) + 4:
        raise HTTPException(status_code=422, detail=f"image exceeds {MAX_IMAGE_BYTES} bytes")
    try:
        raw = base64.b64decode(image_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="image is not valid base64") from exc
    if not raw:
        raise HTTPException(status_code=422, detail="image is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail=f"image exceeds {MAX_IMAGE_BYTES} bytes")

    try:
        img = Image.open(io.BytesIO(raw))
        width, height = img.size
        # Image.open reads the header only — check the pixel count BEFORE convert("RGB")
        # forces the full decode, which is where a bomb would actually allocate.
        if width * height > MAX_IMAGE_PIXELS:
            raise HTTPException(
                status_code=422, detail=f"image exceeds {MAX_IMAGE_PIXELS} pixels"
            )
        return img.convert("RGB")
    except HTTPException:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=422, detail="image could not be decoded") from exc


def resize_image(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize to a caller-requested size, rejecting non-positive or oversized targets with 422."""
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=422, detail="image_width/image_height must be positive")
    if width > MAX_RESIZE_DIM or height > MAX_RESIZE_DIM:
        raise HTTPException(
            status_code=422, detail=f"image_width/image_height must be <= {MAX_RESIZE_DIM}"
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=422, detail=f"resize exceeds {MAX_IMAGE_PIXELS} pixels")
    return img.resize((width, height))


def encode_image(img: Image.Image) -> str:
    """PNG data-URI. The OpenAI image_url contract is what every compatible runtime speaks."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# A normalized turn: {"role": str, "parts": [("text", str) | ("image", Image.Image)]}.
# Both backends render from this one shape, so multi-turn chat and single-turn
# grounding cannot drift apart as the service grows.
Turn = dict[str, Any]


def remote_content(parts: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Render normalized parts as OpenAI-style content blocks for the remote backend."""
    content: list[dict[str, Any]] = []
    for kind, value in parts:
        if kind == "image":
            content.append({"type": "image_url", "image_url": {"url": encode_image(value)}})
        else:
            content.append({"type": "text", "text": value})
    return content


def local_content(parts: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Render normalized parts as chat-template content blocks for the local processor."""
    content: list[dict[str, Any]] = []
    for kind, value in parts:
        if kind == "image":
            content.append({"type": "image", "image": value})
        else:
            content.append({"type": "text", "text": value})
    return content


def generate_remote(turns: list[Turn], max_tokens: int) -> str:
    """Proxy inference to an OpenAI-compatible endpoint (MAI_UI_BACKEND=remote)."""
    import requests

    headers = {"Content-Type": "application/json"}
    if REMOTE_API_KEY:
        headers["Authorization"] = f"Bearer {REMOTE_API_KEY}"

    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json={
            "model": REMOTE_MODEL,
            # Full chronological history: collapsing it into a single user message
            # would change both the system policy and the conversation being asked about.
            "messages": [
                {"role": turn["role"], "content": remote_content(turn["parts"])} for turn in turns
            ],
            "max_tokens": max_tokens,
            # Grounding must be reproducible: the same screenshot has to yield the same
            # click coordinates, or a retry lands somewhere else on the page.
            "temperature": 0,
        },
        timeout=REMOTE_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        # Surface the shape we actually got — a silently-empty grounding result is
        # worse than a loud failure, because the caller would click at (0,0).
        raise RuntimeError(f"unexpected response from {BASE_URL}: {str(data)[:200]}") from exc


def generate_local(turns: list[Turn], max_tokens: int) -> str:
    """Run inference against the resident weights (MAI_UI_BACKEND=local)."""
    model, processor = get_model()

    messages = [{"role": turn["role"], "content": local_content(turn["parts"])} for turn in turns]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    images = [value for turn in turns for kind, value in turn["parts"] if kind == "image"]

    inputs = processor(text=text, images=images or None, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)

    response = processor.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response.strip()


def generate_chat(turns: list[Turn], max_tokens: int = MAX_TOKENS) -> str:
    """Dispatch a normalized conversation to the configured backend. Blocking — call off-loop."""
    if BACKEND == "remote":
        return generate_remote(turns, max_tokens)
    return generate_local(turns, max_tokens)


def generate_response(images: list[Image.Image], prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    """Single-turn convenience wrapper: one user turn of images followed by prompt text."""
    parts: list[tuple[str, Any]] = [("image", img) for img in images]
    parts.append(("text", prompt))
    return generate_chat([{"role": "user", "parts": parts}], max_tokens)


_inference_slots = asyncio.Semaphore(MAX_CONCURRENCY)


async def run_inference(turns: list[Turn], max_tokens: int) -> str:
    """Await blocking inference on a worker thread, bounded by MAI_UI_MAX_CONCURRENCY."""
    async with _inference_slots:
        return await run_in_threadpool(generate_chat, turns, max_tokens)


def parse_grounding(text: str) -> dict[str, Any]:
    """Parse MAI-UI grounding output into structured coordinate."""
    result: dict[str, Any] = {"thinking": None, "coordinate": None, "raw": text}

    think_match = re.search(r"<grounding_think>(.*?)</grounding_think>", text, re.DOTALL)
    if think_match:
        result["thinking"] = think_match.group(1).strip()

    answer_match = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)
    if answer_match:
        answer_text = answer_match.group(1).strip()
        coord_match = re.search(r"\[([\d.]+),\s*([\d.]+)\]", answer_text)
        if coord_match:
            result["coordinate"] = [float(coord_match.group(1)), float(coord_match.group(2))]
        else:
            result["answer"] = answer_text

    return result


# ── API models ───────────────────────────────────────────────────────────────

class GroundRequest(BaseModel):
    image: str
    instruction: str
    image_width: int | None = None
    image_height: int | None = None


class DescribeRequest(BaseModel):
    image: str
    question: str = "Describe what you see in this screenshot. List any text, buttons, and UI elements."


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatRequest(BaseModel):
    model: str = "mai-ui-2b"
    messages: list[ChatMessage]
    max_tokens: int | None = MAX_TOKENS
    temperature: float = 0.0
    stream: bool = False


def normalize_messages(messages: list[ChatMessage]) -> list[Turn]:
    """Normalize OpenAI-shaped chat messages into Turns, rejecting unsupported roles with 422."""
    turns: list[Turn] = []
    for msg in messages:
        if msg.role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=422,
                detail=f"unsupported role {msg.role!r}; expected one of {list(ALLOWED_ROLES)}",
            )
        parts: list[tuple[str, Any]] = []
        content = msg.content
        if isinstance(content, str):
            parts.append(("text", content))
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    raise HTTPException(status_code=422, detail="content parts must be objects")
                part_type = part.get("type")
                if part_type == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    parts.append(("image", decode_image(url)))
                elif part_type == "text":
                    parts.append(("text", part.get("text", "")))
                else:
                    raise HTTPException(
                        status_code=422, detail=f"unsupported content part type {part_type!r}"
                    )
        else:
            raise HTTPException(status_code=422, detail="content must be a string or a list")
        if parts:
            turns.append({"role": msg.role, "parts": parts})
    if not turns:
        raise HTTPException(status_code=422, detail="messages must contain at least one turn")
    return turns


# ── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI(title="MAI-UI Agent", description="GUI grounding + screenshot understanding via MAI-UI-2B")
_request_count = 0


@app.get("/healthz")
async def health():
    """Liveness probe — reports backend mode and whether weights are resident."""
    # Report the backend, so an operator can tell WHY a node has no model resident.
    # Under remote, model_loaded is legitimately False and gpu is legitimately absent —
    # without this a proxying node looks broken rather than correctly configured.
    if BACKEND == "remote":
        return {
            "status": "healthy",
            "backend": "remote",
            "model_loaded": False,
            "upstream": BASE_URL,
            "model": REMOTE_MODEL,
        }
    model_loaded = _model is not None
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    return {
        "status": "healthy",
        "backend": "local",
        "model_loaded": model_loaded,
        "gpu": gpu_name,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus text exposition of the service request counter."""
    return PlainTextResponse(
        f"# HELP mai_ui_requests_total Total requests\n"
        f"# TYPE mai_ui_requests_total counter\n"
        f"mai_ui_requests_total {_request_count}\n"
    )


@app.post("/v1/gui/ground")
async def gui_ground(req: GroundRequest):
    """GUI grounding — find where to click given an instruction."""
    global _request_count
    _request_count += 1

    img = decode_image(req.image)
    if req.image_width and req.image_height:
        img = resize_image(img, req.image_width, req.image_height)

    prompt = f"Find the UI element for: {req.instruction}. Return the click coordinates."
    turns: list[Turn] = [{"role": "user", "parts": [("image", img), ("text", prompt)]}]
    raw = await run_inference(turns, MAX_TOKENS)
    parsed = parse_grounding(raw)

    if parsed.get("coordinate"):
        x_norm, y_norm = parsed["coordinate"]
        px_x = int(x_norm * img.width)
        px_y = int(y_norm * img.height)
        return {"pixel_x": px_x, "pixel_y": px_y, "normalized": [x_norm, y_norm], "thinking": parsed.get("thinking"), "raw": raw}
    return {"coordinate": None, "raw": raw, "error": "Could not parse coordinates"}


@app.post("/v1/gui/describe")
async def gui_describe(req: DescribeRequest):
    """Screenshot OCR / description."""
    global _request_count
    _request_count += 1

    img = decode_image(req.image)
    turns: list[Turn] = [{"role": "user", "parts": [("image", img), ("text", req.question)]}]
    response = await run_inference(turns, MAX_TOKENS)
    return {"description": response}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """OpenAI-compatible chat endpoint — accepts images in content arrays."""
    global _request_count
    _request_count += 1

    # Chronological and role-preserving: the caller's system prompt and prior assistant
    # turns reach the backend intact instead of being flattened into one user string.
    turns = normalize_messages(req.messages)
    response_text = await run_inference(turns, req.max_tokens or MAX_TOKENS)

    return JSONResponse({
        "id": f"mai-ui-{int(time.time())}",
        "object": "chat.completion",
        "model": "mai-ui-2b",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": response_text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
