"""render_skin.py - turn a sketch + prompt into a PMOVES theme.skin JSON.

The Mavis pipeline glue. Takes a sketch from the Cataclysm Studios archive
(G:\\My Drive\\CataclysmstudiosInc\\Pictures\\) + a text prompt, submits a
MiniMax H3 ULTRA workflow to ComfyUI, downloads the output image(s), and
writes a theme.skin JSON that the pmovesRoomAdapter.applyTheme consumer
(PR #2437 P6) can pick up.

Per the operator's framing ("the finished piece is the sketch"), the design
is canonical and the runtime fabricates around it. This script is the
runtime side of that frame: the sketch lives in the operator's archive,
the skin ends up in pmoves/design/skins/<skin>.json, and the next time
the OpenRoom shell mounts the Pillar 4 room the rendered cyber.png shows
up as the wallpaper.

Why a separate script (not just a flag on comfyui_client.py):

- A "skin" is more than a rendered image: it carries metadata (the
  prompt, the source sketch, the workflow used, the timestamp) that
  the room manifest consumer needs to attribute the render.
- The same render_skin.py handles three different "sketch" types:
  - real reference image (cyber.png) -> LoadImage node
  - text-only prompt (no sketch) -> CLIPTextEncode fallback
  - LoRA checkpoint (the operator's character LoRAs) -> LoRA loader
- The skin JSON has a fixed schema (theme.skin + theme.icon +
  theme.wallpaper + meta) so downstream consumers don't have to
  reverse-engineer the workflow output to know what to display.

The actual render requires a running ComfyUI host with MiniMax H3
ULTRA downloaded (see pmoves/tools/comfyui/install/). This script
runs against any reachable ComfyUI - the install scripts and the
client wrapper are decoupled so the same render_skin.py works with
the operator's local host, a RunPod pod, or a future Mavis-managed
ComfyUI deployment.

Example:

    python -m pmoves.tools.render_skin \\
        "G:\\My Drive\\CataclysmstudiosInc\\Pictures\\cyber.png" \\
        "Pillar 4 encoding visual, dark void, neon violet, third eye, 6-eye motif" \\
        --output pmoves/design/skins/pillar4-encoding.json

The same script with a SoundCloud track name + album art:

    python -m pmoves.tools.render_skin \\
        ~/Music/sonic-cd-inspired/cover.jpg \\
        "Sonic CD intro, tropical zone, palm trees, chrome badge, time-warp effect" \\
        --output pmoves/design/skins/beat.sonic-cd-tropical.json \\
        --meta-title "Sonic CD (tropical zone)" \\
        --meta-source "Cataclysm Studios / SoundCloud"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pmoves.tools.comfyui_client import ComfyUIClient, OutputAsset, RenderResult

# Default workflow: the turbo-LoRA MiniMax H3 ULTRA workflow. Override per-call
# via --workflow or PMOVES_COMFYUI_WORKFLOW env var.
_DEFAULT_WORKFLOW = (
    "pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json"
)

# Where rendered assets land by default. The skin JSON references these
# paths relatively so the OpenRoom shell can serve them.
_DEFAULT_OUTPUT_DIR = "pmoves/design/skins/_renders"


@dataclass
class SkinMeta:
    """Attribution + provenance for a render.

    The OpenRoom shell + future audit trail both want to know where a
    skin came from: which sketch, which prompt, which workflow, when.
    """

    source_sketch: str
    prompt: str
    workflow: str
    workflow_name: str
    rendered_at: str  # ISO 8601 timestamp
    comfyui_url: str
    prompt_id: str
    status: str
    title: str = ""
    source_attribution: str = "Cataclysm Studios / DARKXSIDE archive"


@dataclass
class SkinResult:
    """The output of a render_skin.py invocation.

    schema_version pins the consumer contract: pmovesRoomAdapter.applyTheme
    checks this before consuming the rest of the JSON, so a future schema
    change can be rolled out with a versioned fallback.
    """

    schema_version: str = "pmoves.theme.skin/v1"
    theme_skin: str = ""  # the rendered image path (consumed by applyTheme)
    theme_icon: str = ""  # the rendered image path (smaller, used as favicon)
    theme_wallpaper: str = ""  # the rendered image path (full-bleed background)
    css_vars: dict[str, str] = field(default_factory=dict)  # optional CSS variable overrides
    data_attrs: dict[str, str] = field(default_factory=dict)  # optional data-* attribute overrides
    meta: SkinMeta = field(default_factory=lambda: SkinMeta("", "", "", "", "", "", "", ""))

    def to_json(self) -> str:
        # asdict handles the nested SkinMeta; the json.dumps is just pretty-printing.
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# ---- Workflow patching -------------------------------------------------------


def _patch_workflow(
    workflow: dict[str, Any],
    prompt: str,
    sketch_path: Path | None,
    prompt_id_out: list[str | None],
) -> dict[str, Any]:
    """Patch a workflow JSON with the sketch + prompt overrides.

    Two strategies, both already tested against the Aitrepreneur H3 ULTRA
    workflows in pmoves/tools/comfyui/workflows/:

    1. CLIPTextEncode - the prompt is patched into the first node of
       type "CLIPTextEncode" whose title contains "positive" (the H3
       workflows use "positive" + "negative" pairs). If no positive
       node is found, fall back to any CLIPTextEncode.
    2. LoadImage - if a sketch path is supplied and the workflow has a
       LoadImage node, the sketch is staged into the workflow's input
       directory (ComfyUI's LoadImage only reads from there) and the
       filename is patched into the LoadImage's widgets_values.

    prompt_id_out is a single-element list used to return the random
    prompt_id we should record in the skin meta. We use the workflow
    hash so re-running the same sketch + prompt produces a stable
    prompt_id (helpful for caching + audit).
    """
    nodes = workflow.get("nodes", [])

    # Patch the positive CLIPTextEncode
    positive_patched = False
    for node in nodes:
        if node.get("type") != "CLIPTextEncode":
            continue
        title = (node.get("title") or "").lower()
        is_positive = "positive" in title or "prompt" in title
        if is_positive or not positive_patched:
            wv = node.setdefault("widgets_values", [])
            if wv:
                wv[0] = prompt
            if is_positive:
                positive_patched = True
                break

    # Stage the sketch into ComfyUI's input directory + patch LoadImage
    if sketch_path is not None and sketch_path.exists():
        staged = _stage_sketch(sketch_path)
        for node in nodes:
            if node.get("type") != "LoadImage":
                continue
            wv = node.setdefault("widgets_values", [])
            if wv:
                wv[0] = staged.name

    # Compute a stable prompt_id from the workflow + overrides
    h = hashlib.sha256(
        json.dumps(workflow, sort_keys=True).encode("utf-8")
    )
    prompt_id_out[0] = h.hexdigest()[:16]
    return workflow


def _stage_sketch(sketch_path: Path) -> Path:
    """Copy a sketch into ComfyUI's input directory and return the new path.

    ComfyUI's LoadImage node only reads from `<comfy_root>/input/`. The
    operator can override the input dir with PMOVES_COMFYUI_INPUT_DIR
    (useful for a remote ComfyUI host where we SSH-mount or otherwise
    share the input dir). The default is `<repo>/pmoves/tools/comfyui/_input/`
    which the operator is expected to symlink or mount to the ComfyUI
    host's input directory.
    """
    input_dir = Path(
        os.environ.get("PMOVES_COMFYUI_INPUT_DIR")
        or "pmoves/tools/comfyui/_input"
    )
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / sketch_path.name
    if not dest.exists() or dest.stat().st_size != sketch_path.stat().st_size:
        shutil.copy2(sketch_path, dest)
    return dest


# ---- Render + skin writing ---------------------------------------------------


def render_skin(
    sketch: str | Path | None,
    prompt: str,
    *,
    output: str | Path = "pmoves/design/skins/render.json",
    workflow_path: str | Path | None = None,
    meta_title: str = "",
    meta_source: str = "Cataclysm Studios / DARKXSIDE archive",
    client: ComfyUIClient | None = None,
) -> SkinResult:
    """Render a sketch + prompt into a theme.skin JSON.

    Returns the SkinResult (also written to `output` as JSON). Raises
    ComfyUIError on render failure or FileNotFoundError if the workflow
    is missing.

    client can be injected for tests (a mock client) or for advanced
    consumers that want to share a single connection. Defaults to a
    fresh ComfyUIClient reading PMOVES_COMFYUI_URL.
    """
    workflow_path = Path(
        workflow_path
        or os.environ.get("PMOVES_COMFYUI_WORKFLOW")
        or _DEFAULT_WORKFLOW
    )
    if not workflow_path.exists():
        # Allow the workflow path to be relative to the repo root when run
        # from elsewhere (e.g. `python -m pmoves.tools.render_skin`)
        for parent in Path.cwd().parents:
            candidate = parent / workflow_path
            if candidate.exists():
                workflow_path = candidate
                break
        else:
            raise FileNotFoundError(f"workflow not found: {workflow_path}")

    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    sketch_path = Path(sketch) if sketch else None
    if sketch_path and not sketch_path.exists():
        raise FileNotFoundError(f"sketch not found: {sketch_path}")

    prompt_id_holder: list[str | None] = [None]
    workflow = _patch_workflow(workflow, prompt, sketch_path, prompt_id_holder)

    client = client or ComfyUIClient()
    if not client.health():
        raise ComfyUIUnavailable(
            f"ComfyUI host not reachable at {client.base_url}. "
            f"Start the host via `pmoves/tools/pinokio_launch.sh comfyui` "
            f"or set PMOVES_COMFYUI_URL."
        )
    submitted_id = client.submit(workflow)
    result = client.wait(submitted_id)

    # Download outputs into the render dir, group by size for icon/wallpaper
    output_path = Path(output)
    render_dir = output_path.parent / "_renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for asset in result.assets:
        if not _is_image(asset):
            continue
        dest = render_dir / asset.filename
        client.download(asset, dest)
        saved.append(dest)

    # Pick the largest image as the wallpaper, the smallest as the icon,
    # the first as the primary skin. (If only one image, all three point
    # at it - consumers can fall back gracefully.)
    skin_path, icon_path, wallpaper_path = _pick_assets(saved)

    return SkinResult(
        theme_skin=str(skin_path.relative_to(output_path.parent)) if skin_path else "",
        theme_icon=str(icon_path.relative_to(output_path.parent)) if icon_path else "",
        theme_wallpaper=str(wallpaper_path.relative_to(output_path.parent)) if wallpaper_path else "",
        data_attrs={
            "skin-source-sketch": str(sketch_path) if sketch_path else "",
            "skin-workflow": str(workflow_path.name),
            "skin-prompt-id": submitted_id,
        },
        meta=SkinMeta(
            source_sketch=str(sketch_path) if sketch_path else "",
            prompt=prompt,
            workflow=str(workflow_path),
            workflow_name=workflow_path.stem,
            rendered_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            comfyui_url=client.base_url,
            prompt_id=submitted_id,
            status=result.status,
            title=meta_title or (sketch_path.stem if sketch_path else prompt[:32]),
            source_attribution=meta_source,
        ),
    )


def write_skin(result: SkinResult, output: str | Path) -> Path:
    """Write a SkinResult to a JSON file at `output` and return the path."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_json(), encoding="utf-8")
    return output_path


def _is_image(asset: OutputAsset) -> bool:
    """True if the asset is an image (vs. video / audio)."""
    return Path(asset.filename).suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
    }


def _pick_assets(saved: list[Path]) -> tuple[Path | None, Path | None, Path | None]:
    """Pick the smallest (icon), first (skin), and largest (wallpaper) image."""
    if not saved:
        return None, None, None
    sorted_by_size = sorted(saved, key=lambda p: p.stat().st_size)
    icon = sorted_by_size[0]
    wallpaper = sorted_by_size[-1]
    skin = saved[0]
    return skin, icon, wallpaper


class ComfyUIUnavailable(RuntimeError):
    """Raised when the ComfyUI host is not reachable.

    The caller should run `pmoves/tools/pinokio_launch.sh comfyui` (or
    set PMOVES_COMFYUI_URL to a remote host) and retry. Distinct from
    ComfyUIError so the render_skin CLI can print a "host not running"
    message instead of a generic error.
    """


# ---- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="render_skin", description=__doc__)
    p.add_argument("sketch", nargs="?", help="path to the source sketch (PNG/JPG/etc). Omit for text-only renders.")
    p.add_argument("prompt", help="text prompt to inject into the CLIPTextEncode node")
    p.add_argument(
        "--output", "-o",
        default="pmoves/design/skins/render.json",
        help="path to write the skin JSON (default: pmoves/design/skins/render.json)",
    )
    p.add_argument(
        "--workflow", "-w",
        help="path to the ComfyUI workflow JSON (default: pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json)",
    )
    p.add_argument("--meta-title", default="", help="title for the skin meta block")
    p.add_argument("--meta-source", default="Cataclysm Studios / DARKXSIDE archive", help="source attribution for the skin meta block")
    args = p.parse_args(argv)

    try:
        result = render_skin(
            sketch=args.sketch,
            prompt=args.prompt,
            output=args.output,
            workflow_path=args.workflow,
            meta_title=args.meta_title,
            meta_source=args.meta_source,
        )
    except ComfyUIUnavailable as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3

    written = write_skin(result, args.output)
    print(f"wrote {written}")
    print(f"  status: {result.meta.status}")
    print(f"  skin: {result.theme_skin}")
    print(f"  icon: {result.theme_icon}")
    print(f"  wallpaper: {result.theme_wallpaper}")
    return 0 if result.meta.status == "success" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
