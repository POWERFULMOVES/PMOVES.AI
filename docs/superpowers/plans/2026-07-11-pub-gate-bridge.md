# Pub-Gate → Publish Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a geometry-plane gate-open (`geometry.publish.gate.v1`) into a fail-closed, egress-floored publish approval (`content.publish.approved.v1`) via one dedicated NATS subscriber in hi-rag-gateway-v2.

**Architecture:** A pluggable `Floor` (default `BlockAndHoldFloor`, detector-only, never transforms) is the plug-point for future redactors (PR D). A pure `handle_gate_event()` core validates the gate event, runs the floor, and returns an approval payload or `None` (hold). A NATS worker (mirroring the existing `_content_provenance_worker`) wraps the core, env-gated by `PUBLISH_GATE_BRIDGE`, behavior-identical when unset.

**Tech Stack:** Python 3.11+, `nats-py`, FastAPI lifespan, `pytest` + `pytest-asyncio`. Tests run with `uv run --with pytest --with pytest-asyncio python -m pytest`.

## Global Constraints

- Fail-closed: `content.publish.approved.v1` is emitted ONLY on a positive clean verdict. Any missing field, bad `artifact_uri`, floor exception, or rule match → HOLD (log-only), never an approval.
- `content.publish.approved.v1` payload MUST satisfy the existing schema: required `artifact_uri` (matches `^s3://`) + `title`; `approved_by` allowed at top level (schema is not `additionalProperties:false`).
- The floor's PII rules read a protected-terms denylist from operator config (`EGRESS_PROTECTED_TERMS` / `EGRESS_PROTECTED_TERMS_FILE`) — the denylist is PII and MUST NOT be committed. Denylist unconfigured → fail-closed HOLD (cannot prove clean).
- `egress_floor.py` and `gate_bridge.py` core (`handle_gate_event`) MUST NOT import `geometry_bus` or `nats` — keep them pure so tests stay light and the worker is the only NATS surface.
- Contract paths (`pmoves/contracts/schemas/`, `pmoves/contracts/topics.json`) are readOnly gated — Task 4 requires a recorded Known Road.
- Env gate name: `PUBLISH_GATE_BRIDGE` (truthy = on). Unset → worker never starts; gateway behavior identical to today.

---

### Task 1: Egress floor — Verdict, detectors, BlockAndHoldFloor

**Files:**
- Create: `pmoves/services/hi-rag-gateway-v2/egress_floor.py`
- Test: `pmoves/services/hi-rag-gateway-v2/tests/test_egress_floor.py`

**Interfaces:**
- Produces: `Verdict(clean: bool, tripped: list[str])`; `Floor` (Protocol with `check(item: dict) -> Verdict`); `BlockAndHoldFloor(rules: list[str], protected_terms: list[str] | None)`; `_item_text(item: dict) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_egress_floor.py
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "egress_floor", Path(__file__).resolve().parents[1] / "egress_floor.py"
)
egress_floor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(egress_floor)

BlockAndHoldFloor = egress_floor.BlockAndHoldFloor

RULES = ["operator-pii-protected", "collaborator-pii-protected", "no-literal-lan-or-tailscale-ips"]


def _floor(terms):
    return BlockAndHoldFloor(rules=RULES, protected_terms=terms)


def test_literal_lan_ip_trips():
    v = _floor([]).check({"title": "deploy", "description": "ssh to 192.168.1.42 then run"})
    assert v.clean is False
    assert "no-literal-lan-or-tailscale-ips" in v.tripped


def test_tailscale_cgnat_ip_trips():
    v = _floor([]).check({"title": "node", "description": "reachable at 100.101.7.9"})
    assert v.clean is False
    assert "no-literal-lan-or-tailscale-ips" in v.tripped


def test_protected_term_trips():
    v = _floor(["shaela", "hunnibear"]).check({"title": "note", "description": "call with hunnibear"})
    assert v.clean is False
    assert "collaborator-pii-protected" in v.tripped or "operator-pii-protected" in v.tripped


def test_clean_item_with_configured_empty_denylist_passes():
    v = _floor([]).check({"title": "Open-source mesh update", "description": "All public, no IPs."})
    assert v.clean is True
    assert v.tripped == []


def test_unconfigured_denylist_holds_fail_closed():
    v = BlockAndHoldFloor(rules=RULES, protected_terms=None).check({"title": "anything"})
    assert v.clean is False
    assert any("pii" in t for t in v.tripped)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_egress_floor.py -v`
Expected: FAIL — `egress_floor.py` does not exist / `BlockAndHoldFloor` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# egress_floor.py
"""Fail-closed egress floor for the publish gate (PR B).

Detector-only default (BlockAndHoldFloor): NEVER transforms content — it only
answers clean / not-clean. Richer transformers (the flute translator, PR D)
plug in by implementing the Floor protocol.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Protocol

# Private LAN + Tailscale CGNAT (100.64.0.0/10) + *.ts.net
_IP_RE = re.compile(
    r"\b("
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"
    r")\b"
)
_TSNET_RE = re.compile(r"\b[\w-]+\.ts\.net\b", re.IGNORECASE)

_PII_RULES = ("operator-pii-protected", "collaborator-pii-protected")


@dataclass
class Verdict:
    clean: bool
    tripped: List[str] = field(default_factory=list)


class Floor(Protocol):
    def check(self, item: dict) -> Verdict: ...


def _item_text(item: dict) -> str:
    parts: List[str] = []
    for key in ("title", "description", "text"):
        val = item.get(key)
        if isinstance(val, str):
            parts.append(val)
    tags = item.get("tags")
    if isinstance(tags, (list, tuple)):
        parts.extend(str(t) for t in tags)
    meta = item.get("meta")
    if isinstance(meta, dict):
        parts.extend(str(v) for v in meta.values() if isinstance(v, (str, int, float)))
    return "\n".join(parts)


class BlockAndHoldFloor:
    """Default floor: detect-and-hold, never transform.

    protected_terms=None means the operator denylist is UNCONFIGURED — the PII
    rules cannot prove the item clean, so they fail closed (hold).
    """

    def __init__(self, rules: Iterable[str], protected_terms: Optional[Iterable[str]]):
        self.rules = list(rules)
        self.protected_terms = None if protected_terms is None else [t.lower() for t in protected_terms if t]

    def check(self, item: dict) -> Verdict:
        text = _item_text(item)
        low = text.lower()
        tripped: List[str] = []
        for rule in self.rules:
            if rule == "no-literal-lan-or-tailscale-ips":
                if _IP_RE.search(text) or _TSNET_RE.search(text):
                    tripped.append(rule)
            elif rule in _PII_RULES:
                if self.protected_terms is None:
                    tripped.append(rule)  # fail-closed: cannot verify
                elif any(term in low for term in self.protected_terms):
                    tripped.append(rule)
            # unknown rules are ignored (forward-compatible); add detectors as needed
        return Verdict(clean=(len(tripped) == 0), tripped=tripped)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_egress_floor.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/hi-rag-gateway-v2/egress_floor.py pmoves/services/hi-rag-gateway-v2/tests/test_egress_floor.py
git commit -m "feat(pub-gate): fail-closed egress floor (block-and-hold detector)"
```

---

### Task 2: Floor loader — read rules from room manifest + terms from config

**Files:**
- Modify: `pmoves/services/hi-rag-gateway-v2/egress_floor.py` (append loader)
- Test: `pmoves/services/hi-rag-gateway-v2/tests/test_egress_floor.py` (append)

**Interfaces:**
- Consumes: `BlockAndHoldFloor` (Task 1).
- Produces: `load_floor(manifest_path: str, terms_env: str = "EGRESS_PROTECTED_TERMS", terms_file_env: str = "EGRESS_PROTECTED_TERMS_FILE") -> BlockAndHoldFloor`; `_read_rules(manifest_path) -> list[str]`; `_read_terms(...) -> list[str] | None`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_egress_floor.py
import json
import os


def test_load_floor_reads_rules_and_terms(tmp_path, monkeypatch):
    manifest = tmp_path / "room.json"
    manifest.write_text(json.dumps({
        "policies": {"publish": {"egress_redaction_floor": {
            "rules": ["operator-pii-protected", "no-literal-lan-or-tailscale-ips"]}}}
    }), encoding="utf-8")
    monkeypatch.setenv("EGRESS_PROTECTED_TERMS", "shaela, hunnibear")
    monkeypatch.delenv("EGRESS_PROTECTED_TERMS_FILE", raising=False)

    floor = egress_floor.load_floor(str(manifest))
    assert floor.rules == ["operator-pii-protected", "no-literal-lan-or-tailscale-ips"]
    v = floor.check({"title": "ping shaela"})
    assert v.clean is False


def test_load_floor_unconfigured_terms_is_none(tmp_path, monkeypatch):
    manifest = tmp_path / "room.json"
    manifest.write_text(json.dumps({"policies": {"publish": {"egress_redaction_floor": {"rules": []}}}}), encoding="utf-8")
    monkeypatch.delenv("EGRESS_PROTECTED_TERMS", raising=False)
    monkeypatch.delenv("EGRESS_PROTECTED_TERMS_FILE", raising=False)
    floor = egress_floor.load_floor(str(manifest))
    assert floor.protected_terms is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_egress_floor.py -k load_floor -v`
Expected: FAIL — `load_floor` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# append to egress_floor.py
import json
import os


def _read_rules(manifest_path: str) -> List[str]:
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    floor = (
        manifest.get("policies", {}).get("publish", {}).get("egress_redaction_floor", {})
    )
    rules = floor.get("rules")
    return list(rules) if isinstance(rules, list) else []


def _read_terms(terms_env: str, terms_file_env: str) -> Optional[List[str]]:
    raw = os.environ.get(terms_env)
    if raw is None:
        path = os.environ.get(terms_file_env)
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
    if raw is None:
        return None  # unconfigured -> fail-closed
    return [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]


def load_floor(
    manifest_path: str,
    terms_env: str = "EGRESS_PROTECTED_TERMS",
    terms_file_env: str = "EGRESS_PROTECTED_TERMS_FILE",
) -> BlockAndHoldFloor:
    return BlockAndHoldFloor(
        rules=_read_rules(manifest_path),
        protected_terms=_read_terms(terms_env, terms_file_env),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_egress_floor.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/hi-rag-gateway-v2/egress_floor.py pmoves/services/hi-rag-gateway-v2/tests/test_egress_floor.py
git commit -m "feat(pub-gate): load floor rules from room manifest + operator denylist"
```

---

### Task 3: Gate bridge core — handle_gate_event (pure)

**Files:**
- Create: `pmoves/services/hi-rag-gateway-v2/gate_bridge.py`
- Test: `pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py`

**Interfaces:**
- Consumes: `Floor`/`Verdict` (Task 1).
- Produces: `handle_gate_event(payload: dict, floor) -> Optional[dict]` — returns the `content.publish.approved.v1` payload dict on a clean verdict, else `None` (hold). Never raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gate_bridge.py
import importlib.util
from pathlib import Path

_base = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _base / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


egress_floor = _load("egress_floor")
gate_bridge = _load("gate_bridge")

RULES = ["operator-pii-protected", "no-literal-lan-or-tailscale-ips"]


def _floor(terms=None):
    return egress_floor.BlockAndHoldFloor(rules=RULES, protected_terms=[] if terms is None else terms)


def _event(**over):
    ev = {"artifact_uri": "s3://pmoves/reports/r1.md", "title": "Report 1", "approved_by": "operator", "mode": "manual"}
    ev.update(over)
    return ev


def test_clean_event_returns_approval():
    out = gate_bridge.handle_gate_event(_event(), _floor())
    assert out is not None
    assert out["artifact_uri"] == "s3://pmoves/reports/r1.md"
    assert out["title"] == "Report 1"
    assert out["approved_by"] == "operator"


def test_missing_artifact_uri_holds():
    ev = _event(); ev.pop("artifact_uri")
    assert gate_bridge.handle_gate_event(ev, _floor()) is None


def test_non_s3_artifact_uri_holds():
    assert gate_bridge.handle_gate_event(_event(artifact_uri="https://x/y"), _floor()) is None


def test_floor_trip_holds():
    ev = _event(description="ssh 192.168.1.9")
    assert gate_bridge.handle_gate_event(ev, _floor()) is None


def test_floor_exception_holds_fail_closed():
    class Boom:
        def check(self, item):
            raise RuntimeError("detector blew up")
    assert gate_bridge.handle_gate_event(_event(), Boom()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_gate_bridge.py -v`
Expected: FAIL — `gate_bridge.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# gate_bridge.py
"""Gate -> publish bridge core (PR B). Pure: no NATS, no geometry_bus imports.

On a gate-open event, enforce the fail-closed egress floor, and only on a clean
verdict return the content.publish.approved.v1 payload. Any problem -> None (hold).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("hirag.gate_bridge")

_PASSTHROUGH = ("namespace", "tags", "description", "meta", "studio_board_id")


def handle_gate_event(payload: dict, floor) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    artifact_uri = payload.get("artifact_uri")
    title = payload.get("title")
    if not isinstance(artifact_uri, str) or not artifact_uri.startswith("s3://"):
        logger.warning("gate-hold: missing/invalid artifact_uri")
        return None
    if not isinstance(title, str) or not title.strip():
        logger.warning("gate-hold: missing title")
        return None

    try:
        verdict = floor.check(payload)
    except Exception:
        logger.exception("gate-hold: floor raised (fail-closed)")
        return None

    if not verdict.clean:
        logger.warning("gate-hold: egress floor tripped %s for %s", verdict.tripped, artifact_uri)
        return None

    approval = {"artifact_uri": artifact_uri, "title": title}
    for key in _PASSTHROUGH:
        if key in payload and payload[key] is not None:
            approval[key] = payload[key]
    approved_by = payload.get("approved_by")
    if isinstance(approved_by, str) and approved_by:
        approval["approved_by"] = approved_by
    return approval
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_gate_bridge.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pmoves/services/hi-rag-gateway-v2/gate_bridge.py pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py
git commit -m "feat(pub-gate): gate->publish bridge core (fail-closed handle_gate_event)"
```

---

### Task 4: Contract registration (GATED — needs a recorded Known Road)

**Files:**
- Create: `pmoves/contracts/schemas/geometry/publish.gate.v1.schema.json`
- Modify: `pmoves/contracts/topics.json` (add one entry)
- Test: `pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py` (append schema-conformance test)

**Interfaces:**
- Consumes: `handle_gate_event` output (Task 3).
- Produces: registered subject `geometry.publish.gate.v1`.

**PRE-STEP (Known Road):** `pmoves/contracts/` and `pmoves/contracts/schemas/` are readOnly gated. The `.schema.json` file is covered by the `schema` Known-Road domain; `topics.json` is NOT a `.schema.json`, so it needs the operator's file-grant (`KNOWN_ROAD=schema:handoff:<file>` via the grant channel) or an operator out-of-band edit. Do not proceed with Step 3/4 edits until the grant is active. Record the road in the handoff doc.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_gate_bridge.py — schema conformance
import json as _json


def test_approval_and_gate_event_conform_to_schemas():
    # test file: pmoves/services/hi-rag-gateway-v2/tests/ -> parents[3] == pmoves
    contracts = Path(__file__).resolve().parents[3] / "contracts"
    gate_schema = _json.loads((contracts / "schemas/geometry/publish.gate.v1.schema.json").read_text(encoding="utf-8"))
    approved_schema = _json.loads((contracts / "schemas/content/publish.approved.v1.schema.json").read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        import pytest; pytest.skip("jsonschema not installed")
    gate_event = _event()
    jsonschema.validate(gate_event, gate_schema)
    approval = gate_bridge.handle_gate_event(gate_event, _floor())
    jsonschema.validate(approval, approved_schema)
    topics = _json.loads((contracts / "topics.json").read_text(encoding="utf-8"))
    assert "geometry.publish.gate.v1" in _json.dumps(topics)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest --with jsonschema python -m pytest tests/test_gate_bridge.py -k conform -v`
Expected: FAIL — schema file missing.

- [ ] **Step 3: Create the schema (under active Known Road)**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Geometry Publish Gate",
  "type": "object",
  "additionalProperties": false,
  "required": ["artifact_uri", "title", "approved_by"],
  "properties": {
    "artifact_uri": { "type": "string", "pattern": "^s3://" },
    "title": { "type": "string" },
    "namespace": { "type": "string" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "description": { "type": "string" },
    "meta": { "type": "object" },
    "studio_board_id": { "type": "integer", "minimum": 1 },
    "mode": { "type": "string", "enum": ["manual", "village-rules-auto"] },
    "approved_by": { "type": "string" }
  }
}
```

- [ ] **Step 4: Register the topic (under active Known Road)**

Add to `pmoves/contracts/topics.json`, next to the other `geometry.*` entries:

```json
    "geometry.publish.gate.v1": {
      "schema": "schemas/geometry/publish.gate.v1.schema.json",
      "description": "Gate-open intent for a queued publishable artifact; consumed by the hi-rag-gateway pub-gate bridge which enforces the egress floor and emits content.publish.approved.v1.",
      "publisher": ["hyperdimensions-ui", "pub-gate-notebook", "operator-cli"],
      "subscriber": ["hi-rag-gateway-v2"]
    },
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest --with jsonschema python -m pytest tests/test_gate_bridge.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add pmoves/contracts/schemas/geometry/publish.gate.v1.schema.json pmoves/contracts/topics.json pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py
git commit -m "feat(pub-gate): register geometry.publish.gate.v1 contract (schema + topic)"
```

---

### Task 5: NATS worker + lifespan wiring (env-gated)

**Files:**
- Modify: `pmoves/services/hi-rag-gateway-v2/gate_bridge.py` (append the worker)
- Modify: `pmoves/services/hi-rag-gateway-v2/geometry_bus.py` (wire into `lifespan`, add module globals)
- Test: `pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py` (append a fake-nc dispatch test)

**Interfaces:**
- Consumes: `handle_gate_event` (Task 3), `load_floor` (Task 2).
- Produces: `async def publish_gate_worker(nats_url, room_manifest_path)`; `async def _dispatch(msg_data: bytes, floor, publish) -> bool` (returns True if an approval was published) — testable without a real NATS connection.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_gate_bridge.py
import asyncio


def test_dispatch_publishes_approval_on_clean():
    published = []
    async def _pub(subject, data):
        published.append((subject, data))
    ev = _event()
    ok = asyncio.run(gate_bridge._dispatch(_json.dumps(ev).encode(), _floor(), _pub))
    assert ok is True
    assert published and published[0][0] == "content.publish.approved.v1"


def test_dispatch_holds_on_dirty():
    published = []
    async def _pub(subject, data):
        published.append((subject, data))
    ev = _event(description="ip 10.0.0.5")
    ok = asyncio.run(gate_bridge._dispatch(_json.dumps(ev).encode(), _floor(), _pub))
    assert ok is False
    assert published == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_gate_bridge.py -k dispatch -v`
Expected: FAIL — `_dispatch` undefined.

- [ ] **Step 3: Append the worker + dispatch to gate_bridge.py**

```python
# append to gate_bridge.py
import json
import os

APPROVED_SUBJECT = "content.publish.approved.v1"
GATE_SUBJECT = "geometry.publish.gate.v1"


async def _dispatch(msg_data: bytes, floor, publish) -> bool:
    """Decode a gate event, run the core, publish approval if clean. Returns True
    iff an approval was published. `publish` is an async callable(subject, bytes)."""
    try:
        decoded = json.loads(msg_data.decode())
    except Exception:
        logger.warning("gate-hold: invalid geometry.publish.gate.v1 payload")
        return False
    payload = decoded.get("payload") if isinstance(decoded, dict) and isinstance(decoded.get("payload"), dict) else decoded
    approval = handle_gate_event(payload, floor)
    if approval is None:
        return False
    await publish(APPROVED_SUBJECT, json.dumps(approval).encode())
    logger.info("gate-open: published %s for %s", APPROVED_SUBJECT, approval.get("artifact_uri"))
    return True


async def publish_gate_worker(nats_url: str, room_manifest_path: str, backoff: float = 5.0) -> None:
    """Mirror of _content_provenance_worker: subscribe GATE_SUBJECT, run _dispatch."""
    import nats  # local import keeps module NATS-free for tests
    from egress_floor import load_floor

    floor = load_floor(room_manifest_path)
    while True:
        try:
            nc = await nats.connect(servers=[nats_url])

            async def _handler(msg):
                await _dispatch(msg.data, floor, nc.publish)

            await nc.subscribe(GATE_SUBJECT, cb=_handler)
            logger.info("pub-gate bridge listening on %s", GATE_SUBJECT)
            # keep the task alive
            import asyncio as _asyncio
            await _asyncio.Event().wait()
        except Exception:
            logger.exception("pub-gate bridge error; retry in %.1fs", backoff)
            import asyncio as _asyncio
            await _asyncio.sleep(backoff)
```

- [ ] **Step 4: Run the dispatch test to verify it passes**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with pytest python -m pytest tests/test_gate_bridge.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Wire into geometry_bus.py lifespan (env-gated)**

Add near the other module globals (by line ~154, next to `_geometry_cgp_task`):

```python
_pub_gate_task: Optional[asyncio.Task] = None
```

In `lifespan()`, after the CGP subscriber block (after line ~1020, before `yield`):

```python
    # Pub-gate bridge — env-gated; behavior-identical when PUBLISH_GATE_BRIDGE unset.
    if (
        _pub_gate_task is None
        and os.environ.get("PUBLISH_GATE_BRIDGE", "").lower() in ("1", "true", "yes", "on")
        and NATS_URL
        and hasattr(nats, "connect")
    ):
        from gate_bridge import publish_gate_worker
        # geometry_bus.py: pmoves/services/hi-rag-gateway-v2/ -> parents[2] == pmoves
        room_manifest = os.environ.get(
            "PUB_GATE_ROOM_MANIFEST",
            str(Path(__file__).resolve().parents[2] / "config/rooms/darkxsides.room.json"),
        )
        _pub_gate_task = asyncio.create_task(publish_gate_worker(NATS_URL, room_manifest))
        logger.info("pub-gate bridge started (subject=geometry.publish.gate.v1)")
```

Add `global _pub_gate_task` to the `lifespan` globals line, and in Shutdown cancel it:

```python
    if _pub_gate_task is not None:
        _pub_gate_task.cancel()
        with contextlib.suppress(Exception):
            await _pub_gate_task
        _pub_gate_task = None
```

Confirm `os` and `Path` are already imported at the top of geometry_bus.py (they are used elsewhere; if `Path` is not imported, add `from pathlib import Path`).

- [ ] **Step 6: Verify the module still imports and unset-env is a no-op**

Run: `cd pmoves/services/hi-rag-gateway-v2 && uv run --with nats-py --with fastapi python -c "import geometry_bus; print('import ok')"`
Expected: `import ok` (no worker starts without the env flag).

- [ ] **Step 7: Commit**

```bash
git add pmoves/services/hi-rag-gateway-v2/gate_bridge.py pmoves/services/hi-rag-gateway-v2/geometry_bus.py pmoves/services/hi-rag-gateway-v2/tests/test_gate_bridge.py
git commit -m "feat(pub-gate): NATS worker + env-gated lifespan wiring for the bridge"
```

---

### Task 6: Demo make target + doc

**Files:**
- Create: `pmoves/services/hi-rag-gateway-v2/PUB_GATE_BRIDGE.md`
- Modify: `pmoves/mk/*.mk` (add `gate-emit` target — find the right include per `reference_make_targets_live_in_mk_includes`)

**Interfaces:** none (operator tooling).

- [ ] **Step 1: Write the doc**

```markdown
# Pub-Gate Bridge (PR B)

`geometry.publish.gate.v1` -> egress floor (fail-closed) -> `content.publish.approved.v1`.

## Enable
Set `PUBLISH_GATE_BRIDGE=1` on hi-rag-gateway-v2. Configure the operator denylist
via `EGRESS_PROTECTED_TERMS` (comma/newline list) or `EGRESS_PROTECTED_TERMS_FILE`
(a gitignored path). Unset denylist => every publish is HELD (fail-closed).

## Demo (needs NATS)
    export NATS_URL=nats://nats:pmoves@localhost:4222 PUBLISH_GATE_BRIDGE=1 EGRESS_PROTECTED_TERMS=""
    make -C pmoves gate-emit ARTIFACT=s3://pmoves/reports/r1.md TITLE="Report 1"

A clean item publishes content.publish.approved.v1 (publisher then releases it);
a dirty item (LAN IP / protected term) is held with a log line and no approval.
```

- [ ] **Step 2: Add the `gate-emit` make target**

```make
gate-emit: ## Publish a test geometry.publish.gate.v1 event (ARTIFACT=s3://.. TITLE=..)
	@python pmoves/tools/gate_emit.py --artifact "$(ARTIFACT)" --title "$(TITLE)"
```

Create `pmoves/tools/gate_emit.py`:

```python
import argparse, asyncio, json, os
import nats

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--approved-by", default="operator")
    a = ap.parse_args()
    nc = await nats.connect(servers=[os.environ.get("NATS_URL", "nats://localhost:4222")])
    payload = {"artifact_uri": a.artifact, "title": a.title, "approved_by": a.approved_by, "mode": "manual"}
    await nc.publish("geometry.publish.gate.v1", json.dumps(payload).encode())
    await nc.drain()
    print("emitted geometry.publish.gate.v1:", payload)

asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add pmoves/services/hi-rag-gateway-v2/PUB_GATE_BRIDGE.md pmoves/tools/gate_emit.py pmoves/mk/*.mk
git commit -m "docs(pub-gate): bridge enable doc + gate-emit demo target"
```

---

## Verification checklist (before PR)
- [ ] `uv run --with pytest --with pytest-asyncio --with jsonschema python -m pytest tests/test_egress_floor.py tests/test_gate_bridge.py -v` all green.
- [ ] `import geometry_bus` succeeds; no worker starts without `PUBLISH_GATE_BRIDGE`.
- [ ] Room manifest still validates (`validate_room_manifests.py`).
- [ ] Known Road recorded for the Task 4 contract edits.
- [ ] Codex/CodeRabbit triaged — expect a schema-conformance re-check (the #2048/#2047 P2 pattern).
