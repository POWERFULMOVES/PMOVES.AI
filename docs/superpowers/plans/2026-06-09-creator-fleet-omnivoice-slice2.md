# Creator Fleet + OmniVoice — Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the capacity router route across the real fleet (4090/5090/spark/z890/knuckles) by workflow, and add the **voice (OmniVoice)** workflow end-to-end — light, Apache-2.0, fleetwide — as the first multi-node, multi-workflow proof.

**Architecture:** Extend slice 1 (merged). Data: register the fleet in `operator_nodes.yaml` and add a per-workflow `caps` block to `creator_models.yaml`; `route()` derives `node_caps` from the workflow when the work-order omits it, and the `needs:[cuda]` tag gates AMD (`knuckles`/rocm) out of CUDA workflows. New code: an injectable **OmniVoice client** + a **voice_operator** that synthesizes audio via OmniVoice's API and returns an audio operator-result through the existing contract + fan-out.

**Tech Stack:** Python 3.11, jsonschema, PyYAML, pytest (`--import-mode=importlib`), `gradio_client` (OmniVoice transport, live only); reuses slice-1 `creator-operator` modules.

**Spec:** `docs/superpowers/specs/2026-06-09-creator-fleet-omnivoice-design.md`

---

## Conventions (from slice 1 — unchanged)
- Worktree `feat/creator-fleet-omnivoice`. Windows; commit `git -c core.autocrlf=false commit` + explicit `git add <files>` (never `-A`/`-am`).
- `--import-mode=importlib`: importable modules at the SERVICE ROOT (`pmoves/services/creator-operator/`), resolve via `PYTHONPATH=pmoves/services/creator-operator`. `tests/` holds only `test_*.py` (+ the existing `conftest.py` for markers). `fixtures.py` at service root.
- Run tests: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/<file> -v` from the worktree root.
- Avoid generic module names that shadow `pmoves/*` or stdlib (slice-1 lesson).
- NEVER put Tailscale IPs in files — `reach` is a hostname.

## File Structure
```text
pmoves/config/
  operator_nodes.yaml          # MODIFY: 1 node -> 5-node fleet (cuda/rocm caps)
  creator_models.yaml          # MODIFY: + voice/anime/video entries, + caps{} on each
pmoves/services/creator-operator/
  model_registry.py            # MODIFY: + lookup_caps(model)
  router.py                    # MODIFY: derive node_caps from workflow when omitted
  contracts/creator_workorder.v1.schema.json  # MODIFY: node_caps optional
  omnivoice_client.py          # NEW: OmniVoiceClient protocol + FakeOmniVoiceClient + RealOmniVoiceClient
  voice_operator.py            # NEW: synthesize(workorder, client) -> audio operator-result
  operator_select.py           # NEW: workflow_id -> operator kind ("comfyui" | "voice")
  README.md                    # MODIFY: + voice + fleet notes
  VOICE_ACCEPTANCE.md          # NEW: local OmniVoice live runbook
  tests/
    test_router.py             # MODIFY: + fleet routing + caps-derivation cases
    test_models.py             # MODIFY: + caps lookups
    test_omnivoice_client.py   # NEW
    test_voice_operator.py     # NEW
    test_operator_select.py    # NEW
    test_integration_voice.py  # NEW: @requires_ui, CREATOR_VOICE_TEST-gated
```

**Data shapes added this slice:**
- **Node:** `{node_id, reach, vram_gb:int, caps:[str]}` (caps now include `cuda`|`rocm` + `voice`).
- **Workflow caps (in creator_models.yaml entry):** `caps: {min_vram_gb:int, needs:[str]}`.
- **Voice work-order knobs:** `{text:str, voice_ref:str|null, voice_design:str|null}`.
- **Audio artifact:** `{kind:"audio", path:str, preview_url:null}`.

---

## Task 1: Fleet node registry + fleet routing tests

**Files:**
- Modify: `pmoves/config/operator_nodes.yaml`
- Test: `pmoves/services/creator-operator/tests/test_router.py` (append)

- [ ] **Step 1: Replace `operator_nodes.yaml` with the fleet**
```yaml
# Capacity registry — the fleet, by capacity class + GPU vendor.
# caps: gpu vendor (cuda|rocm) + workload tags (comfyui, browser, voice).
# reach = Tailscale hostname (NEVER a raw 100.x IP).
nodes:
  - node_id: "4090"
    reach: "pmoves-laptop"
    vram_gb: 16
    caps: ["cuda", "comfyui", "browser", "voice"]
  - node_id: "5090"
    reach: "pmoves-5090"
    vram_gb: 32
    caps: ["cuda", "comfyui", "browser", "voice"]
  - node_id: "spark"
    reach: "pmoves-spark"
    vram_gb: 128
    caps: ["cuda", "comfyui", "browser", "voice"]
  - node_id: "z890"
    reach: "pmoves-z890"
    vram_gb: 24
    caps: ["cuda", "comfyui", "browser", "voice"]
  - node_id: "knuckles"
    reach: "knuckles"          # AMD 9850X3D + dual R9700 (ROCm). OmniVoice-on-ROCm = seam.
    vram_gb: 32
    caps: ["rocm", "voice"]
```

- [ ] **Step 2: Append fleet routing tests to `tests/test_router.py`**
```python
FLEET = [
    {"node_id": "4090", "reach": "pmoves-laptop", "vram_gb": 16, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "5090", "reach": "pmoves-5090", "vram_gb": 32, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "spark", "reach": "pmoves-spark", "vram_gb": 128, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "z890", "reach": "pmoves-z890", "vram_gb": 24, "caps": ["cuda", "comfyui", "browser", "voice"]},
    {"node_id": "knuckles", "reach": "knuckles", "vram_gb": 32, "caps": ["rocm", "voice"]},
]


def test_voice_routes_to_lowest_vram_incl_knuckles():
    # voice needs only [voice]; lowest-vram satisfying = 4090 (16GB) among the 16s,
    # but knuckles(32) and 4090(16) both satisfy — lowest vram wins = 4090.
    n = select_node({"min_vram_gb": 4, "needs": ["voice"]}, FLEET)
    assert n["node_id"] == "4090"


def test_video_excludes_knuckles_via_cuda_and_vram():
    # video needs cuda + 24GB: knuckles(rocm) excluded by cuda; 4090(16) by vram.
    n = select_node({"min_vram_gb": 24, "needs": ["cuda", "comfyui"]}, FLEET)
    assert n["node_id"] == "z890"  # lowest cuda node with >=24GB


def test_image_excludes_knuckles():
    n = select_node({"min_vram_gb": 16, "needs": ["cuda", "comfyui"]}, FLEET)
    assert n["node_id"] in {"4090"}  # lowest cuda node with >=16GB
    assert n["node_id"] != "knuckles"


def test_cuda_workflow_never_selects_rocm_node():
    rocm_only = [{"node_id": "knuckles", "reach": "knuckles", "vram_gb": 32, "caps": ["rocm", "voice"]}]
    assert select_node({"min_vram_gb": 8, "needs": ["cuda"]}, rocm_only) is None
```

- [ ] **Step 3: Run — confirm PASS (existing + new)**
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_router.py -v`
Expected: all pass (slice-1 `select_node`/`route` already implement caps-subset + lowest-vram; these tests assert fleet behavior, no code change needed). If `load_nodes` validation rejects the fleet yaml, fix the yaml shape; do NOT loosen `load_nodes`.

- [ ] **Step 4: Commit**
```bash
git -c core.autocrlf=false add pmoves/config/operator_nodes.yaml pmoves/services/creator-operator/tests/test_router.py
git -c core.autocrlf=false commit -m "feat(creator-operator): register the fleet (cuda/rocm caps) + fleet routing tests"
```

---

## Task 2: Workflow caps in the model registry

**Files:**
- Modify: `pmoves/config/creator_models.yaml`
- Modify: `pmoves/services/creator-operator/model_registry.py`
- Test: `pmoves/services/creator-operator/tests/test_models.py` (append)

- [ ] **Step 1: Extend `creator_models.yaml`** (add caps to each + new workflows)
```yaml
# Creator-pipeline model registry (license-tagged + capacity-tagged). Gate: any
# model whose license is not confirmed commercial-OK is try-locally/BYO at the
# user's edge (requires_ack=true); never bake into the hosted/commercial path.
# caps: per-workflow default node requirements (min_vram_gb + needs[]).
models:
  voice.omnivoice:
    model_id: k2-fsa/OmniVoice
    provider: local
    license: apache-2.0
    mode: local
    requires_ack: false
    swap_for: null
    caps: {min_vram_gb: 4, needs: ["voice"]}
  image.ideogram-ultra:
    model_id: Comfy-Org/Ideogram-4
    provider: local
    license: other
    mode: local
    requires_ack: true
    swap_for: Qwen/Qwen-Image
    caps: {min_vram_gb: 16, needs: ["cuda", "comfyui"]}
  anime.anima:
    model_id: circlestone-labs/Anima
    provider: local
    license: other
    mode: local
    requires_ack: true
    swap_for: cagliostrolab/animagine-xl-4.0
    caps: {min_vram_gb: 6, needs: ["comfyui"]}
  video.ltx:
    model_id: Lightricks/LTX-Video
    provider: local
    license: other
    mode: local
    requires_ack: true
    swap_for: null
    caps: {min_vram_gb: 24, needs: ["cuda", "comfyui"]}
  image.qwen:
    model_id: Qwen/Qwen-Image
    provider: hf
    license: apache-2.0
    mode: local
    requires_ack: false
    swap_for: null
    caps: {min_vram_gb: 12, needs: ["cuda", "comfyui"]}
```

- [ ] **Step 2: Append failing test to `tests/test_models.py`**
```python
from model_registry import lookup_caps  # noqa: E402


def test_lookup_caps_voice_is_light_fleetwide():
    m = lookup_model(load_models(MODELS), "voice.omnivoice")
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] == 4 and caps["needs"] == ["voice"]
    assert requires_ack(m) is False  # OmniVoice Apache-2.0 — ungated


def test_lookup_caps_video_is_cuda_heavy():
    m = lookup_model(load_models(MODELS), "video.ltx")
    caps = lookup_caps(m)
    assert caps["min_vram_gb"] == 24 and "cuda" in caps["needs"]
    assert requires_ack(m) is True  # license:other


def test_lookup_caps_missing_returns_none():
    assert lookup_caps({"model_id": "x"}) is None
```

- [ ] **Step 3: Run — confirm FAIL** (`ImportError: cannot import name 'lookup_caps'`)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_models.py -v`

- [ ] **Step 4: Add `lookup_caps` to `model_registry.py`** (append)
```python
def lookup_caps(model: dict):
    """Per-workflow default node caps {min_vram_gb, needs[]}, or None if unset."""
    return model.get("caps")
```

- [ ] **Step 5: Run — confirm PASS** (existing test_models still green: the image entry's `model_id`/`mode`/`requires_ack`/`swap_for` are unchanged)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_models.py -v`

- [ ] **Step 6: Commit**
```bash
git -c core.autocrlf=false add pmoves/config/creator_models.yaml pmoves/services/creator-operator/model_registry.py pmoves/services/creator-operator/tests/test_models.py
git -c core.autocrlf=false commit -m "feat(creator-operator): per-workflow caps + voice/anime/video registry entries"
```

---

## Task 3: Derive node_caps from the workflow (node_caps optional)

**Files:**
- Modify: `pmoves/services/creator-operator/contracts/creator_workorder.v1.schema.json`
- Modify: `pmoves/services/creator-operator/router.py`
- Test: `pmoves/services/creator-operator/tests/test_router.py` (append)

- [ ] **Step 1: Make `node_caps` optional in the work-order schema**
In `creator_workorder.v1.schema.json`, change the top-level `"required"` from
`["workorder_id", "workflow_id", "knobs", "node_caps", "license_ack"]` to
`["workorder_id", "workflow_id", "knobs", "license_ack"]` (remove `"node_caps"`).
Leave the `node_caps` property definition in place (still validated when present).

- [ ] **Step 2: Append failing tests to `tests/test_router.py`**
```python
import copy as _copy

MODELS_CAPS = {
    "voice.omnivoice": {"model_id": "k2-fsa/OmniVoice", "requires_ack": False,
                        "caps": {"min_vram_gb": 4, "needs": ["voice"]}},
    "video.ltx": {"model_id": "Lightricks/LTX-Video", "requires_ack": True,
                  "caps": {"min_vram_gb": 24, "needs": ["cuda", "comfyui"]}},
}


def test_route_derives_caps_from_workflow_when_omitted():
    wo = {"workorder_id": "wo_v", "workflow_id": "voice.omnivoice", "knobs": {},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}  # no node_caps
    r = route(wo, FLEET, MODELS_CAPS)
    assert r["ok"] is True and r["node_id"] == "4090"  # voice -> lowest-vram


def test_route_explicit_node_caps_overrides_workflow():
    wo = {"workorder_id": "wo_v", "workflow_id": "voice.omnivoice",
          "knobs": {}, "node_caps": {"min_vram_gb": 24, "needs": ["cuda", "voice"]},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    r = route(wo, FLEET, MODELS_CAPS)
    assert r["ok"] is True and r["node_id"] == "z890"  # explicit caps win (24GB cuda)


def test_route_no_caps_anywhere_returns_no_caps():
    wo = {"workorder_id": "wo_x", "workflow_id": "voice.omnivoice", "knobs": {},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    models_nocaps = {"voice.omnivoice": {"model_id": "x", "requires_ack": False}}  # no caps
    r = route(wo, FLEET, models_nocaps)
    assert r["ok"] is False and r["reason"] == "no-caps"
```

- [ ] **Step 3: Run — confirm FAIL** (current `route` reads `workorder["node_caps"]` → KeyError, or returns wrong reason)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_router.py -k derives -v`

- [ ] **Step 4: Update `route()` in `router.py`** to derive caps
Replace the body of `route()` (keep the unknown-workflow/license logic) so the
`node_caps` line derives from the workflow:
```python
def route(workorder: dict, nodes: list, models: dict) -> dict:
    """License gate first, then capacity match. node_caps may be omitted and is
    then derived from the workflow's registry caps. Returns a RouteResult dict."""
    try:
        model = lookup_model(models, workorder["workflow_id"])
    except KeyError:
        return {"ok": False, "node_id": None, "reason": "unknown-workflow"}
    ack = workorder.get("license_ack", {})
    if requires_ack(model) and not ack.get("ack", False):
        return {"ok": False, "node_id": None, "reason": "license-not-acked"}
    node_caps = workorder.get("node_caps") or model.get("caps")
    if not node_caps:
        return {"ok": False, "node_id": None, "reason": "no-caps"}
    node = select_node(node_caps, nodes)
    if node is None:
        return {"ok": False, "node_id": None, "reason": "no-capacity"}
    # Node shape (node_id/reach present) is guaranteed by load_nodes.
    return {"ok": True, "node_id": node["node_id"], "reason": "routed", "reach": node["reach"]}
```

- [ ] **Step 5: Run — confirm PASS** (new + all existing router tests)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_router.py -v`

- [ ] **Step 6: Update the dispatcher reason mapping for `no-caps`** — in
`dispatcher.py` `handle_workorder`, the final `return {"decision": "parked", ...}`
covers `no-capacity`; add an explicit `no-caps` → rejected (a work-order whose
workflow has no caps and supplies none is malformed, not parkable):
```python
    if r["reason"] in ("unknown-workflow", "no-caps"):
        return {"decision": "rejected", "reason": r["reason"]}
```
(Place this alongside the existing `unknown-workflow` branch; keep `license-not-acked`→refused and `no-capacity`→parked.) Append a dispatcher test:
```python
def test_handle_workorder_rejects_no_caps():
    wo = {"workorder_id": "wo_x", "workflow_id": "image.ideogram-ultra", "knobs": {},
          "license_ack": {"model": "x", "mode": "local", "ack": True}}
    models_nocaps = {"image.ideogram-ultra": {"model_id": "x", "requires_ack": False}}
    out = handle_workorder(wo, NODES, models_nocaps)
    assert out["decision"] == "rejected" and out["reason"] == "no-caps"
```
(NOTE: `NODES` in test_dispatcher is the single-node list; that's fine — `no-caps` returns before capacity match.) Update `test_dispatcher.py`'s existing `import`/`VALID_WORKORDER` usage stays valid since VALID_WORKORDER still carries node_caps.

- [ ] **Step 7: Run full suite — confirm green**
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests -q`
Expected: all pass, 2 skipped (slice-1 UI test).

- [ ] **Step 8: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/contracts/creator_workorder.v1.schema.json pmoves/services/creator-operator/router.py pmoves/services/creator-operator/dispatcher.py pmoves/services/creator-operator/tests/test_router.py pmoves/services/creator-operator/tests/test_dispatcher.py
git -c core.autocrlf=false commit -m "feat(creator-operator): derive node_caps from workflow (node_caps optional)"
```

---

## Task 4: OmniVoice client (injectable)

**Files:**
- Create: `pmoves/services/creator-operator/omnivoice_client.py`
- Test: `pmoves/services/creator-operator/tests/test_omnivoice_client.py`

- [ ] **Step 1: Write the failing test**
```python
import pytest
from omnivoice_client import FakeOmniVoiceClient, OmniVoiceError


def test_fake_client_synthesizes_to_path(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    path = client.synthesize(text="hello fleet", voice_ref="bean")
    assert path.endswith(".wav")
    import os
    assert os.path.exists(path)


def test_fake_client_raises_on_empty_text(tmp_path):
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    with pytest.raises(OmniVoiceError):
        client.synthesize(text="", voice_ref="bean")
```

- [ ] **Step 2: Run — confirm FAIL** (`ModuleNotFoundError: omnivoice_client`)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_omnivoice_client.py -v`

- [ ] **Step 3: Write `omnivoice_client.py`**
```python
"""OmniVoice client abstraction. The voice operator depends on the OmniVoiceClient
interface (synthesize -> audio file path); tests inject FakeOmniVoiceClient, and
production uses RealOmniVoiceClient (gradio_client to the OmniVoice demo at :8001).
The transport is validated only at the live test (CREATOR_VOICE_TEST)."""
from pathlib import Path


class OmniVoiceError(Exception):
    """Raised when synthesis cannot be performed."""


class FakeOmniVoiceClient:
    """Deterministic, no-server client for unit tests: writes a stub .wav."""

    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)

    def synthesize(self, *, text: str, voice_ref: str = None, voice_design: str = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / "voice.wav"
        # Minimal valid WAV header (44 bytes) + no samples — enough to prove a file.
        path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                         b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        return str(path)


class RealOmniVoiceClient:  # pragma: no cover - requires live OmniVoice at :8001
    """Calls the OmniVoice demo via gradio_client. Validated only at the live test."""

    def __init__(self, base_url: str = "http://127.0.0.1:8001", out_dir: str = "."):
        self.base_url = base_url
        self.out_dir = Path(out_dir)

    def synthesize(self, *, text: str, voice_ref: str = None, voice_design: str = None) -> str:
        if not text.strip():
            raise OmniVoiceError("empty text")
        from gradio_client import Client
        client = Client(self.base_url)
        # The exact endpoint name is confirmed at the live test; assemble_result
        # records whatever path OmniVoice returns.
        result = client.predict(text, voice_ref or voice_design or "", api_name="/tts")
        return str(result)
```

- [ ] **Step 4: Run — confirm PASS** (2 passed)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_omnivoice_client.py -v`

- [ ] **Step 5: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/omnivoice_client.py pmoves/services/creator-operator/tests/test_omnivoice_client.py
git -c core.autocrlf=false commit -m "feat(creator-operator): OmniVoice client (fake + real gradio transport)"
```

---

## Task 5: Voice operator (synthesize -> audio operator-result)

**Files:**
- Create: `pmoves/services/creator-operator/voice_operator.py`
- Test: `pmoves/services/creator-operator/tests/test_voice_operator.py`

- [ ] **Step 1: Write the failing test**
```python
from omnivoice_client import FakeOmniVoiceClient
from voice_operator import run_voice
from schemas import validate_result


def test_run_voice_produces_audio_result(tmp_path):
    wo = {"workorder_id": "wo_v1", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "hello from the fleet", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    validate_result(r)  # conforms to the operator-result contract
    assert r["status"] == "ok"
    assert r["artifact"]["kind"] == "audio" and r["artifact"]["path"].endswith(".wav")
    assert r["api_prompt"] is None  # voice is not a ComfyUI graph -> no harvest
    assert any(s["step"] == "synthesize" for s in r["transcript"])


def test_run_voice_error_path(tmp_path):
    wo = {"workorder_id": "wo_v2", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    assert r["status"] == "error" and r["artifact"] is None and r["error"]
```

- [ ] **Step 2: Run — confirm FAIL** (`ModuleNotFoundError: voice_operator`)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_voice_operator.py -v`

- [ ] **Step 3: Write `voice_operator.py`**
```python
"""Voice operator (L1 for voice.omnivoice). Unlike the ComfyUI image operator,
this is an API client, not a UI-driver: it calls OmniVoice and assembles an audio
operator-result. No /prompt harvest (voice isn't a ComfyUI graph) -> api_prompt None."""
from operator_helpers import assemble_result
from omnivoice_client import OmniVoiceError


def run_voice(workorder: dict, client) -> dict:
    knobs = workorder.get("knobs", {})
    transcript = [{"step": "synthesize", "knob": "text",
                   "teaches": "OmniVoice clones a voice and reads your text"}]
    try:
        path = client.synthesize(
            text=knobs.get("text", ""),
            voice_ref=knobs.get("voice_ref"),
            voice_design=knobs.get("voice_design"),
        )
    except OmniVoiceError as exc:
        return assemble_result(workorder["workorder_id"], artifact=None,
                               api_prompt=None, transcript=transcript, error=str(exc))
    return assemble_result(
        workorder["workorder_id"],
        artifact={"kind": "audio", "path": path, "preview_url": None},
        api_prompt=None,
        transcript=transcript,
    )
```

- [ ] **Step 4: Run — confirm PASS** (2 passed)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_voice_operator.py -v`

- [ ] **Step 5: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/voice_operator.py pmoves/services/creator-operator/tests/test_voice_operator.py
git -c core.autocrlf=false commit -m "feat(creator-operator): voice operator (OmniVoice -> audio operator-result)"
```

---

## Task 6: Operator selection (workflow -> operator kind)

**Files:**
- Create: `pmoves/services/creator-operator/operator_select.py`
- Test: `pmoves/services/creator-operator/tests/test_operator_select.py`

- [ ] **Step 1: Write the failing test**
```python
from operator_select import operator_kind


def test_voice_workflow_selects_voice_operator():
    assert operator_kind("voice.omnivoice") == "voice"


def test_image_and_video_select_comfyui_operator():
    assert operator_kind("image.ideogram-ultra") == "comfyui"
    assert operator_kind("video.ltx") == "comfyui"
    assert operator_kind("anime.anima") == "comfyui"


def test_unknown_prefix_defaults_comfyui():
    assert operator_kind("misc.thing") == "comfyui"
```

- [ ] **Step 2: Run — confirm FAIL**
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_operator_select.py -v`

- [ ] **Step 3: Write `operator_select.py`**
```python
"""Map a workflow_id to its L1 operator kind. Voice uses the API-client voice
operator; everything else uses the chrome-devtools ComfyUI operator (slice 1)."""


def operator_kind(workflow_id: str) -> str:
    return "voice" if workflow_id.startswith("voice.") else "comfyui"
```

- [ ] **Step 4: Run — confirm PASS** (4 passed)
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_operator_select.py -v`

- [ ] **Step 5: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/operator_select.py pmoves/services/creator-operator/tests/test_operator_select.py
git -c core.autocrlf=false commit -m "feat(creator-operator): operator selection (voice vs comfyui)"
```

---

## Task 7: Full suite + voice fan-out integration check

**Files:**
- Test: `pmoves/services/creator-operator/tests/test_voice_operator.py` (append fan-out test)

- [ ] **Step 1: Append a fan-out integration test** (voice result fans out via slice-1 `emit_result`)
```python
import asyncio
from fanout import emit_result


class _FakeSinks:
    def __init__(self): self.nats=[]; self.notebook=[]; self.discord=[]; self.n8n=[]
    async def publish_nats(self, s, p): self.nats.append((s, p))
    async def write_notebook(self, t): self.notebook.append(t)
    async def notify_discord(self, s, a): self.discord.append((s, a))
    async def save_n8n(self, w): self.n8n.append(w)


def test_voice_result_fans_out(tmp_path):
    wo = {"workorder_id": "wo_v3", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "fleet voice", "voice_ref": "bean"},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = FakeOmniVoiceClient(out_dir=tmp_path)
    r = run_voice(wo, client)
    sinks = _FakeSinks()
    asyncio.run(emit_result(r, wo, sinks, model_id="k2-fsa/OmniVoice", license_name="apache-2.0"))
    assert sinks.nats and sinks.nats[0][0] == "creator.operator.result.v1"
    assert sinks.discord and sinks.discord[0][1]["kind"] == "audio"
    assert sinks.n8n  # exported
```

- [ ] **Step 2: Run the full suite — confirm green**
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests -q`
Expected: all pass, 2 skipped (slice-1 UI). Paste the total.

- [ ] **Step 3: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/tests/test_voice_operator.py
git -c core.autocrlf=false commit -m "test(creator-operator): voice result fans out (NATS/Discord/n8n)"
```

---

## Task 8: Live voice acceptance (hardware-gated) + runbook

**Files:**
- Create: `pmoves/services/creator-operator/tests/test_integration_voice.py`
- Create: `pmoves/services/creator-operator/VOICE_ACCEPTANCE.md`
- Modify: `pmoves/services/creator-operator/README.md`

- [ ] **Step 1: Create the gated live test** (uses the existing `requires_ui` marker from slice-1 conftest)
```python
import os
import pytest

pytestmark = pytest.mark.requires_ui
RUN = os.getenv("CREATOR_VOICE_TEST") == "1"


@pytest.mark.skipif(not RUN, reason="set CREATOR_VOICE_TEST=1 with OmniVoice up at :8001")
def test_live_omnivoice_synthesizes_audio(tmp_path):
    """Acceptance: a live OmniVoice synth returns a real audio file, and the
    voice operator assembles a valid operator-result with an audio artifact."""
    from omnivoice_client import RealOmniVoiceClient
    from voice_operator import run_voice
    from schemas import validate_result
    wo = {"workorder_id": "wo_live", "workflow_id": "voice.omnivoice",
          "knobs": {"text": "Powerful moves, fleetwide.", "voice_ref": None},
          "license_ack": {"model": "omnivoice", "mode": "local", "ack": True}}
    client = RealOmniVoiceClient(out_dir=str(tmp_path))
    r = run_voice(wo, client)
    validate_result(r)
    assert r["status"] == "ok" and r["artifact"]["kind"] == "audio"
    assert os.path.exists(r["artifact"]["path"]) and os.path.getsize(r["artifact"]["path"]) > 1000
```

- [ ] **Step 2: Confirm it collects + skips cleanly**
Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_integration_voice.py -v`
Expected: 1 skipped, no errors.

- [ ] **Step 3: Write `VOICE_ACCEPTANCE.md`**
```markdown
# OmniVoice (voice.omnivoice) — Local Live Acceptance

OmniVoice is Apache-2.0, light, fleetwide — the voice foothold. No API key.

## Bring OmniVoice up (light)
Run `PMOVES-Creator/installs/OMNIVOICE-WEBUI-INSTALLER.bat` (installs the
`omnivoice` package + launches the demo at `http://127.0.0.1:8001`; models pull
from HF on first run). Confirm the page loads at :8001.

## Assert
```bat
set CREATOR_VOICE_TEST=1
PYTHONPATH=pmoves/services/creator-operator python -m pytest ^
  pmoves/services/creator-operator/tests/test_integration_voice.py -v
```
Acceptance = a live synth returns a real `.wav` (>1 KB) and the voice operator
assembles a valid audio operator-result. If the gradio endpoint name differs from
`/tts`, adjust `RealOmniVoiceClient.synthesize`'s `api_name` (inspect the live app
via `gradio_client`'s `Client(...).view_api()`).

## Fleet / ROCm
voice.omnivoice routes fleetwide (needs:[voice]); NVIDIA nodes are confirmed.
Knuckles (AMD/ROCm) advertises `voice` but OmniVoice's CUDA-pinned installer needs
a ROCm torch swap — **TODO-validate seam** before routing live voice to knuckles.
```

- [ ] **Step 4: Add a Voice section to `README.md`** (after the Layers section)
```markdown
## Voice (slice 2)
`voice.omnivoice` is a non-ComfyUI operator: `voice_operator.run_voice(workorder, client)`
calls OmniVoice (`omnivoice_client`) and returns an audio operator-result (no
`/prompt` harvest). Apache-2.0 (ungated). Routes fleetwide via `caps {min_vram_gb:4,
needs:[voice]}`. See `VOICE_ACCEPTANCE.md`. New subjects: none (reuses
`creator.operator.result.v1`).
```

- [ ] **Step 5: Commit**
```bash
git -c core.autocrlf=false add pmoves/services/creator-operator/tests/test_integration_voice.py pmoves/services/creator-operator/VOICE_ACCEPTANCE.md pmoves/services/creator-operator/README.md
git -c core.autocrlf=false commit -m "test+docs(creator-operator): gated OmniVoice live acceptance + voice runbook"
```

---

## Self-Review

**Spec coverage:**
- Fleet node registry (cuda/rocm) → Task 1 ✓
- Workflow→caps map → Task 2 ✓
- node_caps derivation / optional → Task 3 ✓
- ROCm gate (needs:[cuda] excludes knuckles) → Task 1 tests + Task 2 caps ✓
- OmniVoice client (injectable) → Task 4 ✓
- Voice operator (audio result, api_prompt null) → Task 5 ✓
- Operator selection (voice vs comfyui) → Task 6 ✓
- Fan-out reuse for voice → Task 7 ✓
- Live voice acceptance + ROCm seam doc → Task 8 ✓
- License posture (OmniVoice ungated; others gated) → Task 2 (requires_ack) ✓

**Placeholder scan:** none; every step has real code/commands. The live test is a documented gated acceptance with real skip logic (slice-1 pattern).

**Type/name consistency:** `lookup_caps`, `operator_kind`, `run_voice`, `OmniVoiceError`/`FakeOmniVoiceClient`/`RealOmniVoiceClient`, `assemble_result` (slice 1), `emit_result(..., license_name=)` (slice-1 signature), RouteResult reasons (`unknown-workflow`/`no-caps`/`license-not-acked`/`no-capacity`/`routed`) consistent across tasks. Audio artifact shape `{kind:"audio", path, preview_url}` matches the slice-1 result schema (artifact requires kind+path).

**Seams NOT built (per spec):** OmniVoice-on-ROCm validation; anime/video ComfyUI operators (registry+routing only this slice); SPARK ARM build confirm; n8n fleet pipeline; Discord intake; YT ingestion.
