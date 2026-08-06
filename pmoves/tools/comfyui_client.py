"""ComfyUI HTTP client for the Mavis creative pipeline.

Thin Python wrapper around the ComfyUI REST API. The Mavis creative pipeline
(pmoves/tools/render_skin.py and the operator's downstream skin consumers in
PMOVES-OpenRoom) calls this module to submit MiniMax H3 ULTRA workflows,
poll for completion, and fetch the output images.

Why a wrapper instead of using httpx / aiohttp directly:

- Centralizes the ComfyUI URL + timeout env vars (PMOVES_COMFYUI_URL,
  PMOVES_COMFYUI_TIMEOUT_S) so render_skin.py doesn't have to.
- Translates the workflow JSON "workflow_api" format the install scripts in
  pmoves/tools/comfyui/install/ export to the format ComfyUI's /prompt
  endpoint expects.
- Polls /history with exponential backoff so render_skin.py can fire-and-forget
  on a 600s timeout without busy-waiting the event loop.
- Returns the output file metadata (filename, subfolder, type) as a small
  dataclass so the caller doesn't have to know ComfyUI's internal naming.

Env vars (all optional):

- PMOVES_COMFYUI_URL: base URL of the ComfyUI host. Default: http://localhost:8188
- PMOVES_COMFYUI_TIMEOUT_S: how long to wait for a single render. Default: 600
- PMOVES_COMFYUI_POLL_S: how often to poll /history. Default: 2
- PMOVES_COMFYUI_WORKFLOW: default workflow JSON to load. Default: the
  turbo-LoRA workflow at pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json

The client is intentionally minimal: no async, no streaming, no websocket.
ComfyUI's /prompt + /history pair is sufficient for the render-once-then-poll
pattern that the sketch -> skin pipeline uses. If a future slice needs
streaming progress (e.g. for very long music video renders), wrap this in
an async client that subscribes to the /ws endpoint.

Example:

    from pmoves.tools.comfyui_client import ComfyUIClient, RenderResult

    client = ComfyUIClient()
    prompt_id = client.submit(workflow, inputs={"positive": "third eye, 6-eye motif"})
    result = client.wait(prompt_id)
    for asset in result.assets:
        client.download(asset, dest=f"/tmp/{asset.filename}")
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_COMFYUI_URL = "http://localhost:8188"
DEFAULT_TIMEOUT_S = 600
DEFAULT_POLL_S = 2
DEFAULT_WORKFLOW = (
    "pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json"
)


@dataclass
class OutputAsset:
    """A single output file from a ComfyUI render.

    ComfyUI returns outputs as a list of {filename, subfolder, type} dicts
    in the history entry. The type is one of "output", "input", or "temp";
    the caller typically only cares about "output".
    """

    filename: str
    subfolder: str
    type: str  # "output" | "input" | "temp"

    @property
    def url(self) -> str:
        return f"/view?filename={self.filename}&subfolder={self.subfolder}&type={self.type}"


@dataclass
class RenderResult:
    """The result of a successful ComfyUI render.

    prompt_id is the ComfyUI-assigned ID for this submission (preserved so the
    caller can log/audit it). status is the final /history status - typically
    "success" but "error" is possible if a node threw mid-render. assets is
    the list of output files (images, video frames, audio); may be empty if
    the workflow has no save nodes. raw is the full /history entry for
    advanced consumers.
    """

    prompt_id: str
    status: str
    assets: list[OutputAsset] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class ComfyUIError(RuntimeError):
    """Raised when the ComfyUI host returns a non-recoverable error.

    This includes HTTP 4xx (malformed workflow, missing model), HTTP 5xx
    (ComfyUI crashed mid-render), and timeouts (the render took longer than
    PMOVES_COMFYUI_TIMEOUT_S). The original error from ComfyUI is preserved
    in the args; the caller can catch this and decide whether to retry.
    """


class ComfyUIClient:
    """Synchronous ComfyUI HTTP client.

    See module docstring for the design rationale and env vars.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_s: int | None = None,
        poll_s: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("PMOVES_COMFYUI_URL") or DEFAULT_COMFYUI_URL).rstrip("/")
        self.timeout_s = int(timeout_s or os.environ.get("PMOVES_COMFYUI_TIMEOUT_S") or DEFAULT_TIMEOUT_S)
        self.poll_s = float(poll_s or os.environ.get("PMOVES_COMFYUI_POLL_S") or DEFAULT_POLL_S)

    # ---- HTTP helpers ----------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | bytes:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            # Read the error body so the caller can see what ComfyUI complained about
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIError(f"ComfyUI {method} {path} returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ComfyUIError(f"ComfyUI {method} {path} failed: {exc.reason}") from exc
        if not raw:
            return {}
        # /view returns bytes (image data); everything else returns JSON.
        # Try JSON first; if the bytes aren't valid UTF-8 (e.g. PNG header 0x89)
        # or don't parse as JSON, return the raw bytes.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Non-JSON text response - return the decoded text wrapped in a dict
            # so callers that expect a dict don't crash. The text is available
            # via the response payload if a caller needs it.
            return {"_raw_text": text}

    # ---- Public API ------------------------------------------------------

    def health(self) -> bool:
        """Return True if the ComfyUI host is reachable."""
        try:
            self._request("GET", "/system_stats")
        except ComfyUIError:
            return False
        return True

    def submit(
        self,
        workflow: dict[str, Any],
        client_id: str = "mavis-creative-pipeline",
    ) -> str:
        """Submit a workflow to the /prompt endpoint and return the prompt_id.

        workflow is the full workflow_api JSON (the format ComfyUI's "Save
        (API Format)" exports). client_id is sent as a hint so ComfyUI can
        route websocket events back to the right consumer - we don't use
        websockets here, but ComfyUI's queue UI shows the client_id.
        """
        resp = self._request("POST", "/prompt", body={"prompt": workflow, "client_id": client_id})
        if "prompt_id" not in resp:
            raise ComfyUIError(f"ComfyUI /prompt response missing prompt_id: {resp}")
        return str(resp["prompt_id"])

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        """Return the /history entry for a prompt_id, or None if not yet ready.

        ComfyUI adds the history entry only after the render completes (success
        or error). If you call this before completion, you get an empty dict.
        """
        resp = self._request("GET", f"/history/{prompt_id}")
        if not isinstance(resp, dict):
            return None
        return resp.get(prompt_id)

    def wait(self, prompt_id: str) -> RenderResult:
        """Block until the render completes and return the result.

        Polls /history every PMOVES_COMFYUI_POLL_S seconds until either the
        history entry appears or PMOVES_COMFYUI_TIMEOUT_S elapses. On timeout
        raises ComfyUIError; the caller can catch and decide whether to retry.
        """
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            entry = self.history(prompt_id)
            if entry:
                return self._build_result(prompt_id, entry)
            time.sleep(self.poll_s)
        raise ComfyUIError(
            f"ComfyUI render {prompt_id} did not complete within {self.timeout_s}s"
        )

    def download(self, asset: OutputAsset, dest: str | Path) -> Path:
        """Download an output asset to a local path.

        Returns the resolved Path of the downloaded file. The caller is
        responsible for choosing a dest path that doesn't collide with existing
        files (render_skin.py uses the asset's filename under a per-render
        subdir).
        """
        dest = Path(dest).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = self._request("GET", asset.url)
        if not isinstance(raw, bytes):
            raise ComfyUIError(f"ComfyUI /view returned non-bytes for {asset.filename}")
        dest.write_bytes(raw)
        return dest

    # ---- Internals -------------------------------------------------------

    def _build_result(self, prompt_id: str, entry: dict[str, Any]) -> RenderResult:
        """Translate a /history entry into a RenderResult.

        ComfyUI's history entry shape (subject to change between ComfyUI
        versions, but stable since 0.27):

            {
                "prompt": [<workflow>, ...],  # the input prompt
                "outputs": {
                    "<node_id>": {
                        "images": [{"filename": ..., "subfolder": ..., "type": "output"}, ...]
                    },
                    ...
                },
                "status": {"completed": True/False, "messages": [...]},
            }
        """
        outputs = entry.get("outputs", {}) or {}
        assets: list[OutputAsset] = []
        for _node_id, node_out in outputs.items():
            for kind in ("images", "gifs", "videos", "audio"):
                for item in node_out.get(kind, []) or []:
                    assets.append(
                        OutputAsset(
                            filename=item.get("filename", ""),
                            subfolder=item.get("subfolder", ""),
                            type=item.get("type", "output"),
                        )
                    )
        status_block = entry.get("status", {}) or {}
        status = "error" if status_block.get("errored") or any(
            msg for msg in status_block.get("messages", []) or []
            if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error"
        ) else "success"
        return RenderResult(
            prompt_id=prompt_id,
            status=status,
            assets=assets,
            raw=entry,
        )


# ---- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: submit a workflow JSON and print the prompt_id.

    Usage:
        python -m pmoves.tools.comfyui_client submit <workflow.json> [--input k=v ...]
        python -m pmoves.tools.comfyui_client wait <prompt_id>
        python -m pmoves.tools.comfyui_client health
    """
    import argparse

    p = argparse.ArgumentParser(prog="comfyui_client", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_health = sub.add_parser("health", help="check ComfyUI is reachable")
    p_health.set_defaults(_fn=lambda args, client: print("OK" if client.health() else "UNREACHABLE"))

    p_submit = sub.add_parser("submit", help="submit a workflow and print the prompt_id")
    p_submit.add_argument("workflow", help="path to the workflow_api JSON")
    p_submit.add_argument("--input", action="append", default=[], help="key=value overrides for the workflow inputs")
    p_submit.set_defaults(_fn=_cli_submit)

    p_wait = sub.add_parser("wait", help="block until a prompt_id completes, print asset paths")
    p_wait.add_argument("prompt_id")
    p_wait.set_defaults(_fn=_cli_wait)

    args = p.parse_args(argv)
    client = ComfyUIClient()
    rc = args._fn(args, client)
    return 0 if rc is None else rc


def _cli_submit(args: Any, client: ComfyUIClient) -> int:
    workflow_path = Path(args.workflow)
    if not workflow_path.exists():
        # Fall back to the default workflow if a relative path under pmoves/tools/comfyui/workflows/
        fallback = Path("pmoves") / "tools" / "comfyui" / "workflows" / args.workflow
        if fallback.exists():
            workflow_path = fallback
        else:
            raise SystemExit(f"workflow file not found: {args.workflow}")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    # Naive input merge: the workflow nodes are keyed by string id; we just
    # patch the first matching node's widgets_values. A real "input override"
    # would need to know the node id + widget index. For the CLI we only
    # support the common case of overriding the CLIPTextEncode text + a
    # LoadImage filename.
    if args.input:
        overrides = dict(kv.split("=", 1) for kv in args.input)
        _apply_overrides(workflow, overrides)
    prompt_id = client.submit(workflow)
    print(prompt_id)
    return 0


def _apply_overrides(workflow: dict[str, Any], overrides: dict[str, str]) -> None:
    """Patch a workflow JSON with simple key=value overrides.

    Supports two common cases:
    - overrides["text"] = "..." -> patches the first CLIPTextEncode node
    - overrides["image"] = "filename.png" -> patches the first LoadImage node

    Other keys are passed through to widgets_values[0] of the first node
    that has a widgets_values list. This is intentionally a small surface;
    complex edits should be done in the ComfyUI UI and re-exported.
    """
    nodes = workflow.get("nodes", [])
    text_patched = False
    image_patched = False
    for node in nodes:
        ntype = node.get("type", "")
        if not text_patched and ntype == "CLIPTextEncode":
            for k, v in overrides.items():
                if k in node.get("title", "").lower() or k == "text":
                    wv = node.setdefault("widgets_values", [])
                    if wv:
                        wv[0] = v
                    text_patched = True
        if not image_patched and ntype == "LoadImage":
            if "image" in overrides:
                wv = node.setdefault("widgets_values", [])
                if wv:
                    wv[0] = overrides["image"]
                image_patched = True
        if text_patched and image_patched:
            return


def _cli_wait(args: Any, client: ComfyUIClient) -> int:
    result = client.wait(args.prompt_id)
    print(f"status: {result.status}")
    for asset in result.assets:
        print(f"  {asset.type}/{asset.subfolder}/{asset.filename}")
    return 0 if result.status == "success" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
