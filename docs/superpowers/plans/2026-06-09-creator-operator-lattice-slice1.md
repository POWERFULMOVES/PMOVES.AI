# Creator Operator Lattice — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the Creator Operator Lattice contract end-to-end on the 4090 with the image (Ideogram-Ultra) workflow: a computer-use agent drives the real ComfyUI UI from a tutorial skill, narrates the knobs, produces an artifact, and harvests the API-format prompt — with a real Archon work-order → capacity router → result fan-out (NATS + CGP + Notebook + Discord notify + single-node n8n export).

**Architecture:** A small FastAPI/NATS Python service (`pmoves/services/creator-operator/`) owns the **plumbing** — contract validation, capacity routing + license gate, and result fan-out. The **UI-driving** is a Claude computer-use run guided by an `.claude/skills/comfy-operate-image/SKILL.md`, using the chrome-devtools MCP; it assembles an `operator-result` (artifact + harvested `/prompt` payload + teaching transcript) and hands it back to the service. A Pinokio launcher (L0) brings ComfyUI + the workflow up. Pure logic is TDD-tested; the live UI run is an integration test gated `@requires_ui`.

**Tech Stack:** Python 3.11, FastAPI, `nats-py`, `jsonschema`, `PyYAML`, pytest; chrome-devtools MCP (operator); Pinokio (`pinokio.js`/`install.js`/`start.js`); PMOVES-Creator (ComfyUI fork) `/prompt`/`/history` API.

**Spec:** `docs/superpowers/specs/2026-06-09-creator-operator-lattice-design.md`

---

## File Structure

```
pmoves/services/creator-operator/
  __init__.py
  config.py                 # Config: NATS_URL, paths, ports (env-driven)
  contracts/
    creator_workorder.schema.json
    creator_operator_result.schema.json
  schemas.py                # validate_workorder / validate_result (jsonschema)
  models.py                 # load_models / lookup_model / requires_ack
  router.py                 # load_nodes / select_node / route (capacity + license gate)
  attribution.py            # build_cgp_point / summarize_transcript
  n8n_export.py             # to_n8n_workflow
  fanout.py                 # emit_result(result, sinks)  (async, injectable sinks)
  operator_helpers.py       # parse_workorder / assemble_result  (agent-side helpers; avoid stdlib 'operator' clash)
  dispatcher.py             # handle_workorder (route + assign/park/refuse) + run_responder
  app.py                    # create_app(): /healthz /metrics + startup subscribe
  requirements.txt
  README.md                 # service doc + NATS subjects (catalog registration is an operator action)
  tests/
    fixtures.py             # valid/invalid work-order + result dicts
    test_schemas.py
    test_models.py
    test_router.py
    test_attribution.py
    test_n8n_export.py
    test_fanout.py
    test_operator.py
    test_dispatcher.py
    test_integration_ui.py  # @requires_ui (skipped in CI)

pmoves/config/
  operator_nodes.yaml       # capacity registry (slice 1: one node = 4090)
  creator_models.yaml       # model + license registry (ideogram-ultra + clean swaps)

.claude/skills/comfy-operate-image/
  SKILL.md                  # L2: tutorial-distilled in-UI steps + knob glossary
  tests/test_knob_glossary.py

PMOVES-Creator/installs/pinokio/image-ideogram/
  pinokio.js install.js start.js icon.png   # L0 launcher
```

**Test invocation (all tasks):** from repo root —
`PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/<file> -v`
(the service package imports its own modules flatly, matching clap-embed.)

**Data shapes (consistent across all tasks):**
- **WorkOrder:** `{workorder_id, workflow_id, knobs{}, node_caps{min_vram_gb,int; needs[]}, teach:bool, creator_ref, license_ack{model, mode, ack:bool}}`
- **OperatorResult:** `{workorder_id, status:"ok"|"error", artifact{kind,path,preview_url}|null, api_prompt:obj|null, transcript:[{step,knob,teaches}], cgp_point:obj|null, error:str|null}`
- **Node:** `{node_id, vram_gb:int, caps:[str], reach:str}`
- **Model:** `{model_id, provider, license, mode, requires_ack:bool, swap_for|null}`

---

## Task 1: Service scaffold + config

**Files:**
- Create: `pmoves/services/creator-operator/__init__.py` (empty)
- Create: `pmoves/services/creator-operator/config.py`
- Create: `pmoves/services/creator-operator/requirements.txt`
- Create: `pmoves/services/creator-operator/tests/__init__.py` (empty)

- [ ] **Step 1: Write config.py**

```python
"""creator-operator service config (env-driven, no secrets in code)."""
import os
from pathlib import Path


class Config:
    SERVICE_SLUG = "creator-operator"
    PORT = int(os.getenv("CREATOR_OPERATOR_PORT", "8120"))
    NATS_URL = os.getenv("NATS_URL", "")
    SUBJECT_WORKORDER = "archon.workorder.creator.v1"
    SUBJECT_RESULT = "creator.operator.result.v1"
    SUBJECT_ASSIGNED = "creator.operator.assigned.v1"
    # Registries (repo-relative; overridable for tests)
    REPO_ROOT = Path(os.getenv("PMOVES_REPO_ROOT", Path(__file__).resolve().parents[3]))
    NODES_PATH = Path(os.getenv("CREATOR_NODES_PATH", REPO_ROOT / "pmoves/config/operator_nodes.yaml"))
    MODELS_PATH = Path(os.getenv("CREATOR_MODELS_PATH", REPO_ROOT / "pmoves/config/creator_models.yaml"))
    PENDING_DIR = Path(os.getenv("CREATOR_PENDING_DIR", REPO_ROOT / "pmoves/services/creator-operator/.pending"))
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi>=0.110
uvicorn>=0.29
nats-py>=2.6
jsonschema>=4.21
PyYAML>=6.0
```

- [ ] **Step 3: Commit**

```bash
git add pmoves/services/creator-operator/__init__.py pmoves/services/creator-operator/config.py \
        pmoves/services/creator-operator/requirements.txt pmoves/services/creator-operator/tests/__init__.py
git commit -m "feat(creator-operator): service scaffold + config"
```

---

## Task 2: Contract schemas + validators

**Files:**
- Create: `pmoves/services/creator-operator/contracts/creator_workorder.schema.json`
- Create: `pmoves/services/creator-operator/contracts/creator_operator_result.schema.json`
- Create: `pmoves/services/creator-operator/schemas.py`
- Create: `pmoves/services/creator-operator/tests/fixtures.py`
- Test: `pmoves/services/creator-operator/tests/test_schemas.py`

- [ ] **Step 1: Write the work-order schema**

`contracts/creator_workorder.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "creator_workorder",
  "type": "object",
  "required": ["workorder_id", "workflow_id", "knobs", "node_caps", "license_ack"],
  "additionalProperties": false,
  "properties": {
    "workorder_id": {"type": "string", "minLength": 1},
    "workflow_id": {"type": "string", "minLength": 1},
    "knobs": {"type": "object"},
    "node_caps": {
      "type": "object",
      "required": ["min_vram_gb", "needs"],
      "properties": {
        "min_vram_gb": {"type": "integer", "minimum": 0},
        "needs": {"type": "array", "items": {"type": "string"}}
      }
    },
    "teach": {"type": "boolean"},
    "creator_ref": {"type": "string"},
    "license_ack": {
      "type": "object",
      "required": ["model", "mode", "ack"],
      "properties": {
        "model": {"type": "string"},
        "mode": {"type": "string"},
        "ack": {"type": "boolean"}
      }
    }
  }
}
```

- [ ] **Step 2: Write the operator-result schema**

`contracts/creator_operator_result.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "creator_operator_result",
  "type": "object",
  "required": ["workorder_id", "status", "transcript"],
  "additionalProperties": false,
  "properties": {
    "workorder_id": {"type": "string", "minLength": 1},
    "status": {"type": "string", "enum": ["ok", "error"]},
    "artifact": {
      "type": ["object", "null"],
      "properties": {
        "kind": {"type": "string"},
        "path": {"type": "string"},
        "preview_url": {"type": ["string", "null"]}
      }
    },
    "api_prompt": {"type": ["object", "null"]},
    "transcript": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step"],
        "properties": {
          "step": {"type": "string"},
          "knob": {"type": ["string", "null"]},
          "teaches": {"type": ["string", "null"]}
        }
      }
    },
    "cgp_point": {"type": ["object", "null"]},
    "error": {"type": ["string", "null"]}
  }
}
```

- [ ] **Step 3: Write fixtures.py**

```python
"""Shared test fixtures for creator-operator."""

VALID_WORKORDER = {
    "workorder_id": "wo_test1",
    "workflow_id": "image.ideogram-ultra",
    "knobs": {"prompt": "a neon city", "seed": 42, "input_image": None},
    "node_caps": {"min_vram_gb": 8, "needs": ["comfyui", "browser"]},
    "teach": True,
    "creator_ref": "creator_demo",
    "license_ack": {"model": "ideogram-ultra", "mode": "byo-api-key", "ack": True},
}

VALID_RESULT = {
    "workorder_id": "wo_test1",
    "status": "ok",
    "artifact": {"kind": "image", "path": "/out/x.png", "preview_url": None},
    "api_prompt": {"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
    "transcript": [{"step": "set seed", "knob": "seed", "teaches": "determinism"}],
    "cgp_point": None,
    "error": None,
}
```

- [ ] **Step 4: Write the failing test**

`tests/test_schemas.py`:
```python
import copy
import pytest
from schemas import validate_workorder, validate_result
from fixtures import VALID_WORKORDER, VALID_RESULT


def test_valid_workorder_passes():
    validate_workorder(VALID_WORKORDER)  # no raise


def test_workorder_missing_license_ack_raises():
    bad = copy.deepcopy(VALID_WORKORDER)
    del bad["license_ack"]
    with pytest.raises(Exception):
        validate_workorder(bad)


def test_valid_result_passes():
    validate_result(VALID_RESULT)  # no raise


def test_result_bad_status_raises():
    bad = copy.deepcopy(VALID_RESULT)
    bad["status"] = "maybe"
    with pytest.raises(Exception):
        validate_result(bad)
```

- [ ] **Step 5: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_schemas.py -v`
Expected: FAIL (`ModuleNotFoundError: schemas`).

- [ ] **Step 6: Write schemas.py**

```python
"""JSON-schema validation for creator-operator contracts."""
import json
from pathlib import Path
from jsonschema import validate

_DIR = Path(__file__).resolve().parent / "contracts"
_WORKORDER = json.loads((_DIR / "creator_workorder.schema.json").read_text(encoding="utf-8"))
_RESULT = json.loads((_DIR / "creator_operator_result.schema.json").read_text(encoding="utf-8"))


def validate_workorder(d: dict) -> None:
    validate(instance=d, schema=_WORKORDER)


def validate_result(d: dict) -> None:
    validate(instance=d, schema=_RESULT)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_schemas.py -v`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add pmoves/services/creator-operator/contracts pmoves/services/creator-operator/schemas.py \
        pmoves/services/creator-operator/tests/fixtures.py pmoves/services/creator-operator/tests/test_schemas.py
git commit -m "feat(creator-operator): work-order + operator-result contract schemas"
```

---

## Task 3: Model registry + license gate data

**Files:**
- Create: `pmoves/config/creator_models.yaml`
- Create: `pmoves/services/creator-operator/models.py`
- Test: `pmoves/services/creator-operator/tests/test_models.py`

- [ ] **Step 1: Write creator_models.yaml**

```yaml
# Creator-pipeline model registry (license-tagged). Gate: non-commercial models
# are try-locally / BYO at the user's edge ONLY; never server-side/commercial.
models:
  image.ideogram-ultra:
    model_id: ideogram-4
    provider: api
    license: non-commercial        # commercial use = the user's own paid API account
    mode: byo-api-key
    requires_ack: true
    swap_for: Qwen/Qwen-Image      # license-clean (Apache-2.0) server-side swap
  image.qwen:
    model_id: Qwen/Qwen-Image
    provider: hf
    license: apache-2.0
    mode: local
    requires_ack: false
    swap_for: null
```

- [ ] **Step 2: Write the failing test**

`tests/test_models.py`:
```python
import pytest
from pathlib import Path
from models import load_models, lookup_model, requires_ack

MODELS = Path(__file__).resolve().parents[3] / "config/creator_models.yaml"


def test_lookup_ideogram_requires_ack():
    m = lookup_model(load_models(MODELS), "image.ideogram-ultra")
    assert m["model_id"] == "ideogram-4"
    assert requires_ack(m) is True
    assert m["swap_for"] == "Qwen/Qwen-Image"


def test_lookup_qwen_no_ack():
    m = lookup_model(load_models(MODELS), "image.qwen")
    assert requires_ack(m) is False


def test_unknown_workflow_raises():
    with pytest.raises(KeyError):
        lookup_model(load_models(MODELS), "image.nope")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: models`).

- [ ] **Step 4: Write models.py**

```python
"""Creator model registry + license-gate helpers."""
from pathlib import Path
import yaml


def load_models(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data.get("models", {})


def lookup_model(models: dict, workflow_id: str) -> dict:
    if workflow_id not in models:
        raise KeyError(f"no model registered for workflow {workflow_id!r}")
    return models[workflow_id]


def requires_ack(model: dict) -> bool:
    return bool(model.get("requires_ack", False))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pmoves/config/creator_models.yaml pmoves/services/creator-operator/models.py \
        pmoves/services/creator-operator/tests/test_models.py
git commit -m "feat(creator-operator): model + license registry"
```

---

## Task 4: Node registry + capacity router + license gate

**Files:**
- Create: `pmoves/config/operator_nodes.yaml`
- Create: `pmoves/services/creator-operator/router.py`
- Test: `pmoves/services/creator-operator/tests/test_router.py`

- [ ] **Step 1: Write operator_nodes.yaml**

```yaml
# Capacity registry. Slice 1: one node (4090). Add Jetson/SPARK/fleet as entries
# (no code change) — the router impedance-matches by lowest-capacity satisfying node.
nodes:
  - node_id: "4090"
    vram_gb: 24
    caps: ["comfyui", "browser"]
    reach: "pmoves-laptop"     # Tailscale hostname (no raw IPs)
```

- [ ] **Step 2: Write the failing test**

`tests/test_router.py`:
```python
import copy
from router import select_node, route
from fixtures import VALID_WORKORDER

NODES = [
    {"node_id": "jetson", "vram_gb": 8, "caps": ["comfyui", "browser"], "reach": "pmoves-jetson"},
    {"node_id": "4090", "vram_gb": 24, "caps": ["comfyui", "browser"], "reach": "pmoves-laptop"},
]
MODELS = {"image.ideogram-ultra": {"model_id": "ideogram-4", "requires_ack": True}}


def test_select_node_impedance_picks_lowest_capacity():
    n = select_node({"min_vram_gb": 6, "needs": ["comfyui"]}, NODES)
    assert n["node_id"] == "jetson"  # lowest VRAM that satisfies


def test_select_node_respects_min_vram():
    n = select_node({"min_vram_gb": 16, "needs": ["comfyui"]}, NODES)
    assert n["node_id"] == "4090"


def test_select_node_missing_cap_returns_none():
    assert select_node({"min_vram_gb": 6, "needs": ["tpu"]}, NODES) is None


def test_route_ok():
    r = route(VALID_WORKORDER, NODES, MODELS)
    assert r["ok"] is True and r["node_id"] in {"jetson", "4090"}


def test_route_refuses_unacked_nc_model():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["license_ack"]["ack"] = False
    r = route(bad, NODES, MODELS)
    assert r["ok"] is False and r["reason"] == "license-not-acked"


def test_route_parks_when_no_capacity():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["node_caps"] = {"min_vram_gb": 999, "needs": ["comfyui"]}
    r = route(bad, NODES, MODELS)
    assert r["ok"] is False and r["reason"] == "no-capacity"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_router.py -v`
Expected: FAIL (`ModuleNotFoundError: router`).

- [ ] **Step 4: Write router.py**

```python
"""Capacity routing + license gate for creator work-orders."""
from pathlib import Path
import yaml
from models import lookup_model, requires_ack


def load_nodes(path: Path) -> list:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data.get("nodes", [])


def select_node(node_caps: dict, nodes: list):
    """Lowest-VRAM node that satisfies min_vram_gb and all required caps."""
    need = set(node_caps.get("needs", []))
    min_vram = node_caps.get("min_vram_gb", 0)
    candidates = [
        n for n in nodes
        if n.get("vram_gb", 0) >= min_vram and need.issubset(set(n.get("caps", [])))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda n: n.get("vram_gb", 0))


def route(workorder: dict, nodes: list, models: dict) -> dict:
    """License gate first, then capacity match. Returns a RouteResult dict."""
    model = lookup_model(models, workorder["workflow_id"])
    ack = workorder.get("license_ack", {})
    if requires_ack(model) and not ack.get("ack", False):
        return {"ok": False, "node_id": None, "reason": "license-not-acked"}
    node = select_node(workorder["node_caps"], nodes)
    if node is None:
        return {"ok": False, "node_id": None, "reason": "no-capacity"}
    return {"ok": True, "node_id": node["node_id"], "reason": "routed", "reach": node["reach"]}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_router.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add pmoves/config/operator_nodes.yaml pmoves/services/creator-operator/router.py \
        pmoves/services/creator-operator/tests/test_router.py
git commit -m "feat(creator-operator): capacity router + license gate"
```

---

## Task 5: Attribution (CGP point + teaching summary)

**Files:**
- Create: `pmoves/services/creator-operator/attribution.py`
- Test: `pmoves/services/creator-operator/tests/test_attribution.py`

- [ ] **Step 1: Write the failing test**

`tests/test_attribution.py`:
```python
from attribution import build_cgp_point, summarize_transcript
from fixtures import VALID_RESULT, VALID_WORKORDER


def test_build_cgp_point_carries_provenance():
    p = build_cgp_point(VALID_RESULT, VALID_WORKORDER, model_id="ideogram-4", license="non-commercial")
    assert p["meta"]["model"] == "ideogram-4"
    assert p["meta"]["license"] == "non-commercial"
    assert p["meta"]["workflow_id"] == "image.ideogram-ultra"
    assert p["meta"]["has_api_prompt"] is True
    assert p["meta"]["knobs"]["seed"] == 42


def test_summarize_transcript_short():
    s = summarize_transcript(VALID_RESULT["transcript"])
    assert "seed" in s
    assert len(s) <= 280
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_attribution.py -v`
Expected: FAIL (`ModuleNotFoundError: attribution`).

- [ ] **Step 3: Write attribution.py**

```python
"""CGP attribution + teaching-summary helpers."""


def build_cgp_point(result: dict, workorder: dict, *, model_id: str, license: str) -> dict:
    """A CGP point whose meta carries full provenance + a ref to the harvested recipe."""
    return {
        "meta": {
            "source": "creator-operator",
            "workflow_id": workorder["workflow_id"],
            "model": model_id,
            "license": license,
            "knobs": workorder.get("knobs", {}),
            "has_api_prompt": result.get("api_prompt") is not None,
            "workorder_id": result["workorder_id"],
        }
    }


def summarize_transcript(transcript: list) -> str:
    """One short teaching line per knob, truncated for Discord (<=280 chars)."""
    parts = []
    for entry in transcript:
        knob = entry.get("knob")
        teaches = entry.get("teaches")
        if knob and teaches:
            parts.append(f"{knob}: {teaches}")
    text = " · ".join(parts) if parts else "run complete"
    return text[:280]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_attribution.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/attribution.py pmoves/services/creator-operator/tests/test_attribution.py
git commit -m "feat(creator-operator): CGP point + teaching summary"
```

---

## Task 6: n8n export serializer

**Files:**
- Create: `pmoves/services/creator-operator/n8n_export.py`
- Test: `pmoves/services/creator-operator/tests/test_n8n_export.py`

- [ ] **Step 1: Write the failing test**

`tests/test_n8n_export.py`:
```python
from n8n_export import to_n8n_workflow
from fixtures import VALID_RESULT


def test_to_n8n_workflow_minimal_importable():
    wf = to_n8n_workflow(VALID_RESULT, workflow_id="image.ideogram-ultra")
    assert wf["name"].startswith("creator-run-")
    assert isinstance(wf["nodes"], list) and len(wf["nodes"]) == 1
    node = wf["nodes"][0]
    assert node["type"] == "n8n-nodes-base.noOp"
    assert node["parameters"]["workorder_id"] == "wo_test1"
    assert node["parameters"]["artifact_path"] == "/out/x.png"
    assert wf["connections"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_n8n_export.py -v`
Expected: FAIL (`ModuleNotFoundError: n8n_export`).

- [ ] **Step 3: Write n8n_export.py**

```python
"""Serialize one operator run as a minimal importable n8n workflow (single node).
The capacity seam: real but single-node; a fleet pipeline is a later slice."""


def to_n8n_workflow(result: dict, *, workflow_id: str) -> dict:
    wo = result["workorder_id"]
    artifact = result.get("artifact") or {}
    return {
        "name": f"creator-run-{wo}",
        "nodes": [
            {
                "id": "run",
                "name": "creator-operator-run",
                "type": "n8n-nodes-base.noOp",
                "typeVersion": 1,
                "position": [0, 0],
                "parameters": {
                    "workorder_id": wo,
                    "workflow_id": workflow_id,
                    "status": result.get("status"),
                    "artifact_path": artifact.get("path"),
                    "has_api_prompt": result.get("api_prompt") is not None,
                },
            }
        ],
        "connections": {},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_n8n_export.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/n8n_export.py pmoves/services/creator-operator/tests/test_n8n_export.py
git commit -m "feat(creator-operator): single-node n8n export"
```

---

## Task 7: Result fan-out (injectable sinks)

**Files:**
- Create: `pmoves/services/creator-operator/fanout.py`
- Test: `pmoves/services/creator-operator/tests/test_fanout.py`

- [ ] **Step 1: Write the failing test**

`tests/test_fanout.py`:
```python
import asyncio
from fanout import emit_result
from fixtures import VALID_RESULT, VALID_WORKORDER


class FakeSinks:
    def __init__(self):
        self.nats = []
        self.notebook = []
        self.discord = []
        self.n8n = []

    async def publish_nats(self, subject, payload):
        self.nats.append((subject, payload))

    async def write_notebook(self, transcript):
        self.notebook.append(transcript)

    async def notify_discord(self, summary, artifact):
        self.discord.append((summary, artifact))

    async def save_n8n(self, workflow):
        self.n8n.append(workflow)


def test_emit_result_fans_out_all_sinks():
    sinks = FakeSinks()
    asyncio.run(emit_result(VALID_RESULT, VALID_WORKORDER, sinks,
                            model_id="ideogram-4", license="non-commercial"))
    assert sinks.nats and sinks.nats[0][0] == "creator.operator.result.v1"
    assert sinks.notebook and sinks.notebook[0] == VALID_RESULT["transcript"]
    assert sinks.discord and "seed" in sinks.discord[0][0]
    assert sinks.n8n and sinks.n8n[0]["nodes"][0]["parameters"]["workorder_id"] == "wo_test1"


def test_emit_result_validates_before_fanout():
    sinks = FakeSinks()
    bad = dict(VALID_RESULT, status="maybe")
    try:
        asyncio.run(emit_result(bad, VALID_WORKORDER, sinks, model_id="x", license="y"))
        assert False, "should have raised on invalid result"
    except Exception:
        assert sinks.nats == []  # nothing emitted on invalid result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_fanout.py -v`
Expected: FAIL (`ModuleNotFoundError: fanout`).

- [ ] **Step 3: Write fanout.py**

```python
"""Fan a validated operator-result out to all sinks. Sinks are injected so the
orchestration is unit-testable with fakes; production sinks wrap NATS/Notebook/
Discord/n8n. Validate-before-emit: an invalid result reaches no sink."""
from schemas import validate_result
from attribution import build_cgp_point, summarize_transcript
from n8n_export import to_n8n_workflow


async def emit_result(result: dict, workorder: dict, sinks, *, model_id: str, license: str) -> dict:
    validate_result(result)  # raises before any sink sees it
    cgp = build_cgp_point(result, workorder, model_id=model_id, license=license)
    result = dict(result, cgp_point=cgp)
    summary = summarize_transcript(result["transcript"])
    n8n_wf = to_n8n_workflow(result, workflow_id=workorder["workflow_id"])

    await sinks.publish_nats("creator.operator.result.v1", result)
    await sinks.write_notebook(result["transcript"])
    await sinks.notify_discord(summary, result.get("artifact"))
    await sinks.save_n8n(n8n_wf)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_fanout.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/fanout.py pmoves/services/creator-operator/tests/test_fanout.py
git commit -m "feat(creator-operator): result fan-out (NATS/Notebook/Discord/n8n)"
```

---

## Task 8: Operator-side helpers (agent assembles the result)

**Files:**
- Create: `pmoves/services/creator-operator/operator_helpers.py`
- Test: `pmoves/services/creator-operator/tests/test_operator.py`

- [ ] **Step 1: Write the failing test**

`tests/test_operator.py`:
```python
import pytest
from operator_helpers import parse_workorder, assemble_result
from fixtures import VALID_WORKORDER


def test_parse_workorder_validates():
    wo = parse_workorder(VALID_WORKORDER)
    assert wo["workflow_id"] == "image.ideogram-ultra"


def test_parse_workorder_rejects_bad():
    with pytest.raises(Exception):
        parse_workorder({"workorder_id": "x"})


def test_assemble_result_ok():
    r = assemble_result(
        "wo_test1",
        artifact={"kind": "image", "path": "/out/x.png", "preview_url": None},
        api_prompt={"3": {"class_type": "KSampler", "inputs": {"seed": 42}}},
        transcript=[{"step": "set seed", "knob": "seed", "teaches": "determinism"}],
    )
    assert r["status"] == "ok" and r["error"] is None
    assert r["api_prompt"]["3"]["class_type"] == "KSampler"


def test_assemble_result_error_path():
    r = assemble_result("wo_test1", artifact=None, api_prompt=None,
                        transcript=[{"step": "load workflow"}], error="node missing")
    assert r["status"] == "error" and r["artifact"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_operator.py -v`
Expected: FAIL (`ModuleNotFoundError: operator`).

- [ ] **Step 3: Write operator_helpers.py**

```python
"""Agent-side helpers used by the chrome-devtools operator run. The agent drives
the ComfyUI UI per the comfy-operate-image SKILL, records steps, captures the
harvested /prompt payload, then calls assemble_result and hands it to the service."""
from schemas import validate_workorder, validate_result


def parse_workorder(raw: dict) -> dict:
    validate_workorder(raw)
    return raw


def assemble_result(workorder_id: str, *, artifact, api_prompt, transcript, error=None) -> dict:
    status = "error" if error else "ok"
    result = {
        "workorder_id": workorder_id,
        "status": status,
        "artifact": artifact if status == "ok" else None,
        "api_prompt": api_prompt,
        "transcript": transcript,
        "cgp_point": None,        # filled by fanout
        "error": error,
    }
    validate_result(result)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_operator.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/operator_helpers.py pmoves/services/creator-operator/tests/test_operator.py
git commit -m "feat(creator-operator): agent-side parse/assemble helpers"
```

---

## Task 9: Dispatcher (route + assign/park/refuse)

**Files:**
- Create: `pmoves/services/creator-operator/dispatcher.py`
- Test: `pmoves/services/creator-operator/tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

`tests/test_dispatcher.py`:
```python
import copy
from dispatcher import handle_workorder
from fixtures import VALID_WORKORDER

NODES = [{"node_id": "4090", "vram_gb": 24, "caps": ["comfyui", "browser"], "reach": "pmoves-laptop"}]
MODELS = {"image.ideogram-ultra": {"model_id": "ideogram-4", "requires_ack": True}}


def test_handle_workorder_assigns():
    out = handle_workorder(VALID_WORKORDER, NODES, MODELS)
    assert out["decision"] == "assigned"
    assert out["node_id"] == "4090"
    assert out["subject"] == "creator.operator.assigned.v1"


def test_handle_workorder_refuses_unacked():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["license_ack"]["ack"] = False
    out = handle_workorder(bad, NODES, MODELS)
    assert out["decision"] == "refused" and out["reason"] == "license-not-acked"


def test_handle_workorder_parks_no_capacity():
    bad = copy.deepcopy(VALID_WORKORDER)
    bad["node_caps"] = {"min_vram_gb": 999, "needs": ["comfyui"]}
    out = handle_workorder(bad, NODES, MODELS)
    assert out["decision"] == "parked" and out["reason"] == "no-capacity"


def test_handle_workorder_rejects_invalid():
    out = handle_workorder({"workorder_id": "x"}, NODES, MODELS)
    assert out["decision"] == "rejected"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_dispatcher.py -v`
Expected: FAIL (`ModuleNotFoundError: dispatcher`).

- [ ] **Step 3: Write dispatcher.py**

```python
"""Work-order dispatcher: validate -> route -> decide. Pure handle_workorder is
unit-tested; run_responder wires it to NATS (live, not unit-tested)."""
from schemas import validate_workorder
from router import route
from config import Config


def handle_workorder(workorder: dict, nodes: list, models: dict) -> dict:
    try:
        validate_workorder(workorder)
    except Exception as exc:
        return {"decision": "rejected", "reason": str(exc)}

    r = route(workorder, nodes, models)
    if r["ok"]:
        return {
            "decision": "assigned",
            "node_id": r["node_id"],
            "reach": r["reach"],
            "subject": Config.SUBJECT_ASSIGNED,
            "workorder": workorder,
        }
    if r["reason"] == "license-not-acked":
        return {"decision": "refused", "reason": r["reason"]}
    return {"decision": "parked", "reason": r["reason"]}


async def run_responder():  # pragma: no cover - requires live NATS
    import json
    import nats
    from router import load_nodes
    from models import load_models

    nodes = load_nodes(Config.NODES_PATH)
    models = load_models(Config.MODELS_PATH)
    nc = await nats.connect(Config.NATS_URL)

    async def _cb(m):
        out = handle_workorder(json.loads(m.data), nodes, models)
        if out["decision"] == "assigned":
            await nc.publish(Config.SUBJECT_ASSIGNED, json.dumps(out["workorder"]).encode())

    await nc.subscribe(Config.SUBJECT_WORKORDER, cb=_cb)
    return nc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_dispatcher.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/dispatcher.py pmoves/services/creator-operator/tests/test_dispatcher.py
git commit -m "feat(creator-operator): work-order dispatcher (assign/park/refuse)"
```

---

## Task 10: FastAPI app (health/metrics + startup subscribe)

**Files:**
- Create: `pmoves/services/creator-operator/app.py`
- Modify: extend `tests/test_dispatcher.py` (app smoke) — or new `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

`tests/test_app.py`:
```python
from fastapi.testclient import TestClient
from app import create_app


def test_healthz_ok():
    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["service"] == "creator-operator"


def test_metrics_present():
    client = TestClient(create_app())
    assert client.get("/metrics").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_app.py -v`
Expected: FAIL (`ModuleNotFoundError: app`).

- [ ] **Step 3: Write app.py**

```python
"""creator-operator FastAPI service (L3 dispatcher). Port 8120."""
from fastapi import FastAPI
from config import Config


def create_app() -> FastAPI:
    app = FastAPI(title="creator-operator", version="1.0.0")

    @app.get("/healthz")
    def healthz():
        return {"service": Config.SERVICE_SLUG, "ok": True, "nats": bool(Config.NATS_URL)}

    @app.get("/metrics")
    def metrics():
        return {"service": Config.SERVICE_SLUG, "up": 1}

    @app.on_event("startup")
    async def _startup():
        # Subscribe the dispatcher only when NATS is configured (mirrors clap-embed).
        if Config.NATS_URL:
            from dispatcher import run_responder
            app.state.nc = await run_responder()

    @app.on_event("shutdown")
    async def _shutdown():
        nc = getattr(app.state, "nc", None)
        if nc is not None:
            await nc.close()

    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=Config.PORT)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_app.py -v`
Expected: PASS (2 passed). (Requires `httpx` for TestClient — `pip install httpx` if missing.)

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/app.py pmoves/services/creator-operator/tests/test_app.py
git commit -m "feat(creator-operator): FastAPI app (health/metrics + startup subscribe)"
```

---

## Task 11: L2 operator skill + knob-glossary completeness test

**Files:**
- Create: `.claude/skills/comfy-operate-image/SKILL.md`
- Create: `.claude/skills/comfy-operate-image/knobs.json`
- Test: `.claude/skills/comfy-operate-image/tests/test_knob_glossary.py`

- [ ] **Step 1: Write knobs.json (the exposed-knob glossary — single source of truth)**

`.claude/skills/comfy-operate-image/knobs.json`:
```json
{
  "exposed_knobs": {
    "prompt": "the text describing the image you want — the most important knob",
    "seed": "fixes randomness; the same seed + prompt reproduces the same image",
    "input_image": "optional reference/inpaint source; leave empty for text-to-image"
  }
}
```

- [ ] **Step 2: Write SKILL.md**

`.claude/skills/comfy-operate-image/SKILL.md`:
````markdown
---
name: comfy-operate-image
description: >
  Drive the real ComfyUI UI to run the Ideogram-Ultra image workflow via the
  chrome-devtools MCP, narrating each knob to teach the user, and harvest the
  POST /prompt API-format payload. Used by the creator-operator (L1). The end
  user never touches the node graph.
---

# comfy-operate-image — Computer-Use ComfyUI Operator (image)

Drives a Pinokio-launched PMOVES-Creator ComfyUI to run **image.ideogram-ultra**.
Teaching is the feature: narrate what each knob does as you set it.

## Inputs (from the work-order)
`knobs`: `prompt` (str), `seed` (int), `input_image` (path|null). The exposed
knobs + their teaching sentences are in `knobs.json` (the single source of truth;
the completeness test asserts every exposed knob has a sentence).

## Run-book (chrome-devtools MCP)
1. `navigate_page` to the ComfyUI URL captured by the Pinokio `start.js`.
2. `take_snapshot` to anchor the UI; load the Ideogram-Ultra workflow (drag the
   saved JSON, or use the Workflow menu → Open).
3. For each exposed knob, set its widget (`fill`/`evaluate_script`) and **narrate**
   the matching `knobs.json` sentence into the transcript (`record_step`).
4. Click **Queue Prompt**.
5. `list_network_requests` → find `POST /prompt`; `get_network_request` → save the
   request body as `api_prompt` (the harvested API-format graph).
6. Poll `GET /history/{prompt_id}` until the output node reports an image; fetch it.
7. Call `assemble_result(workorder_id, artifact=..., api_prompt=..., transcript=...)`
   and hand the result to the creator-operator fan-out.

## Failure handling
- Selector/node missing → `assemble_result(..., artifact=None, api_prompt=None,
  error="<step>: <what was expected>")`. Fail closed — no partial artifact.
- ComfyUI `/history` reports a node error → surface the Comfy error text in `error`.
- `POST /prompt` not captured → still return the artifact; set `api_prompt=None`
  (the fan-out flags `has_api_prompt:false`). The run is valid; replay isn't.

## License
`image.ideogram-ultra` is BYO-API-key (the user's own paid Ideogram account). The
creator-operator L3 gate refuses to dispatch unless `license_ack.ack` is true.
For server-side/commercial use, swap to `Qwen/Qwen-Image` (`creator_models.yaml`).
````

- [ ] **Step 3: Write the failing test**

`.claude/skills/comfy-operate-image/tests/test_knob_glossary.py`:
```python
import json
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
# Exposed knobs the work-order knobs{} may carry for this workflow.
WORKORDER_KNOBS = {"prompt", "seed", "input_image"}


def test_every_exposed_knob_has_a_teaching_sentence():
    glossary = json.loads((SKILL / "knobs.json").read_text(encoding="utf-8"))["exposed_knobs"]
    for knob in WORKORDER_KNOBS:
        assert knob in glossary, f"knob {knob!r} has no teaching sentence"
        assert glossary[knob].strip(), f"knob {knob!r} has an empty sentence"


def test_skill_has_frontmatter_name():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "name: comfy-operate-image" in text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest .claude/skills/comfy-operate-image/tests/test_knob_glossary.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/comfy-operate-image
git commit -m "feat(skill): comfy-operate-image L2 operator + knob glossary"
```

---

## Task 12: Pinokio launcher (L0) + service README

**Files:**
- Create: `PMOVES-Creator/installs/pinokio/image-ideogram/pinokio.js`
- Create: `PMOVES-Creator/installs/pinokio/image-ideogram/install.js`
- Create: `PMOVES-Creator/installs/pinokio/image-ideogram/start.js`
- Create: `pmoves/services/creator-operator/README.md`

> NOTE: `PMOVES-Creator` is a submodule — make these changes on a branch *inside*
> the submodule and open a PR there; the gitlink bump is a separate follow-up.
> Load `.claude/PINOKIO_LAUNCHER_GUIDE.md` before writing the launcher.

- [ ] **Step 1: Write pinokio.js (menu)**

```javascript
module.exports = {
  version: "1.0",
  title: "PMOVES Creator — Image (Ideogram-Ultra)",
  description: "1-click ComfyUI + Ideogram-Ultra workflow for the creator-operator.",
  icon: "icon.png",
  menu: async (kernel) => {
    const installed = kernel.exists(__dirname, "ComfyUI");
    return [
      { text: installed ? "Start" : "Install",
        href: installed ? "start.js" : "install.js" },
    ];
  },
};
```

- [ ] **Step 2: Write install.js (wraps the existing .bat install steps)**

```javascript
// Brings up PMOVES-Creator ComfyUI + installs the Ideogram-Ultra models/nodes.
// Mirrors installs/IDEOGRAM_ULTRA-MODELS-NODES_INSTALL.bat steps via Pinokio.
module.exports = {
  run: [
    { method: "shell.run", params: { message: "git clone https://github.com/POWERFULMOVES/PMOVES-Creator ComfyUI" } },
    { method: "script.start", params: { uri: "torch.js", params: { venv: "ComfyUI/venv", path: "ComfyUI" } } },
    { method: "shell.run", params: { path: "ComfyUI", venv: "venv", message: "pip install -r requirements.txt" } },
    // Place the saved workflow where the operator can open it.
    { method: "fs.copy", params: { src: "../../IDEOGRAM_ULTRA_WORKFLOW-V2.json", dest: "ComfyUI/user/default/workflows/ideogram-ultra.json" } },
    { method: "json.set", params: { "ComfyUI/_pmoves_ready.json": { ready: true, workflow: "image.ideogram-ultra" } } },
  ],
};
```

- [ ] **Step 3: Write start.js (capture the ComfyUI URL — the Pinokio URL pattern)**

```javascript
// Starts ComfyUI and captures the local URL so the chrome-devtools operator
// knows where to navigate. See .claude/PINOKIO_LAUNCHER_GUIDE.md (URL capture).
module.exports = {
  daemon: true,
  run: [
    {
      method: "shell.run",
      params: {
        path: "ComfyUI",
        venv: "venv",
        message: "python main.py --listen 127.0.0.1 --port 8188",
        on: [{ event: "/http:\\/\\/[0-9.:]+/", done: true }],
      },
    },
    { method: "local.set", params: { url: "{{input.event[0]}}" } },
  ],
};
```

- [ ] **Step 4: Write the service README (with the NATS subjects)**

`pmoves/services/creator-operator/README.md`:
```markdown
# creator-operator (L3 dispatcher) — port 8120

Validates creator work-orders, capacity-routes them (impedance match) with a
license gate, and fans results out (NATS / CGP / Open-Notebook / Discord / n8n).
The UI-driving is a chrome-devtools computer-use run guided by the
`comfy-operate-image` skill (L2), launched by the Pinokio image-ideogram launcher
(L0). See `docs/superpowers/specs/2026-06-09-creator-operator-lattice-design.md`.

## NATS subjects (register in the live catalog as an operator action — see below)
- `archon.workorder.creator.v1`   (in)  — work-order from Archon / Discord intake
- `creator.operator.assigned.v1`  (out) — work-order assigned to a node
- `creator.operator.result.v1`    (out) — operator-result fan-out

> `.claude/context/nats-subjects.md` is guard-protected; register these via the
> normal catalog-update Known Road, not a direct edit.

## Run
PYTHONPATH=. python app.py   # or: uvicorn app:create_app --factory --port 8120
```

- [ ] **Step 5: Commit (main repo: README; submodule: launcher on its own branch)**

```bash
# main repo
git add pmoves/services/creator-operator/README.md
git commit -m "docs(creator-operator): service README + NATS subjects"
# submodule launcher — committed inside PMOVES-Creator on its own branch (separate PR)
```

---

## Task 13: Integration test (UI-gated) — live run + harvest replay

**Files:**
- Create: `pmoves/services/creator-operator/tests/test_integration_ui.py`
- Create: `pmoves/services/creator-operator/tests/conftest.py` (registers `requires_ui` marker)

- [ ] **Step 1: Register the marker**

`tests/conftest.py`:
```python
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_ui: live ComfyUI + browser; skipped in CI")
```

- [ ] **Step 2: Write the UI-gated test (documents the live acceptance criteria)**

`tests/test_integration_ui.py`:
```python
import os
import pytest

pytestmark = pytest.mark.requires_ui

RUN = os.getenv("CREATOR_UI_TEST") == "1"


@pytest.mark.skipif(not RUN, reason="set CREATOR_UI_TEST=1 on the 4090 with ComfyUI up")
def test_live_run_produces_artifact_and_harvests_api_prompt():
    """Acceptance: a live operator run on the 4090 returns status=ok, a real
    artifact path, and a NON-null api_prompt (the harvested POST /prompt graph).
    Driven by the comfy-operate-image skill via chrome-devtools MCP."""
    from operator_helpers import assemble_result  # noqa: F401  (the agent calls this)
    pytest.skip("manual: run via the comfy-operate-image skill, assert result.api_prompt is not None")


@pytest.mark.skipif(not RUN, reason="set CREATOR_UI_TEST=1")
def test_harvested_api_prompt_replays_headless():
    """Acceptance: POSTing the harvested api_prompt back to /prompt yields an
    equivalent artifact (proves the byproduct is a real headless recipe)."""
    pytest.skip("manual: POST harvested api_prompt to /prompt; assert an image returns")
```

- [ ] **Step 3: Run to verify it collects + skips cleanly in CI**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests/test_integration_ui.py -v`
Expected: 2 skipped (no `CREATOR_UI_TEST`), no errors.

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=pmoves/services/creator-operator python -m pytest pmoves/services/creator-operator/tests -v`
Expected: all unit tests PASS, 2 skipped (UI).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/creator-operator/tests/conftest.py pmoves/services/creator-operator/tests/test_integration_ui.py
git commit -m "test(creator-operator): UI-gated live run + harvest-replay acceptance"
```

---

## Self-Review

**Spec coverage:**
- L0 substrate (Pinokio launcher) → Task 12 ✓
- L1 operator (chrome-devtools + harvest) → Task 8 (helpers) + Task 11 (skill run-book) + Task 13 (live) ✓
- L2 skill (tutorial-distilled + knob glossary) → Task 11 ✓
- L3 orchestration (work-order, capacity router, license gate, dispatcher, app) → Tasks 2,3,4,9,10 ✓
- L4 models (registry + license) → Task 3 ✓
- L5 attribution (CGP, transcript, Discord notify, NATS, n8n) → Tasks 5,6,7 ✓
- Contract (work-order → operator-result) → Tasks 2,8 ✓
- Error handling (fail-closed, no silent failure, park-not-drop, license refusal, harvest-miss) → Tasks 4,7,8,9,11 ✓
- Testing strategy (schemas, router, attribution, n8n, fanout, operator, dispatcher, knob completeness, UI-gated) → all tasks ✓
- License posture (BYO at edge, gate before dispatch, clean swap recorded) → Tasks 3,4,11 ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code. UI test is intentionally a documented manual acceptance (the live run is the agent's job), with real skip logic.

**Type/name consistency:** `validate_workorder`/`validate_result`, `lookup_model`/`requires_ack`, `select_node`/`route`, `build_cgp_point`/`summarize_transcript`, `to_n8n_workflow`, `emit_result`, `parse_workorder`/`assemble_result`, `handle_workorder`/`run_responder`, `create_app` — used consistently across tasks. RouteResult keys (`ok`/`node_id`/`reason`/`reach`) consistent in Tasks 4 & 9. OperatorResult/WorkOrder shapes match the schemas in Task 2 throughout.

**Seams NOT in this plan (later slices, per spec):** LTX/Citron/OmniVoice workflows; Jetson/SPARK/fleet registry entries; Discord *intake*; YT-monitor auto-skill ingestion; headless replay service; Unsloth LoRA; n8n fleet pipeline; gitlink bump for the PMOVES-Creator launcher.
