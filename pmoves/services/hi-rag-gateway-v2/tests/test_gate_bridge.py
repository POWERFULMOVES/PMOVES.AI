import importlib.util
import json as _json
import sys
from pathlib import Path

_base = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _base / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
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


def test_malformed_verdict_holds_fail_closed():
    class BadFloor:
        def check(self, item):
            return object()  # no .clean attribute
    assert gate_bridge.handle_gate_event(_event(), BadFloor()) is None


def test_none_verdict_holds_fail_closed():
    class NoneFloor:
        def check(self, item):
            return None
    assert gate_bridge.handle_gate_event(_event(), NoneFloor()) is None


def test_approval_and_gate_event_conform_to_schemas():
    import json

    # test file: pmoves/services/hi-rag-gateway-v2/tests/ -> parents[3] == pmoves
    contracts = Path(__file__).resolve().parents[3] / "contracts"
    gate_schema = json.loads(
        (contracts / "schemas/geometry/publish.gate.v1.schema.json").read_text(encoding="utf-8")
    )
    approved_schema = json.loads(
        (contracts / "schemas/content/publish.approved.v1.schema.json").read_text(encoding="utf-8")
    )
    try:
        import jsonschema
    except ImportError:
        import pytest

        pytest.skip("jsonschema not installed")

    gate_event = _event()
    jsonschema.validate(gate_event, gate_schema)  # the emitted intent conforms

    approval = gate_bridge.handle_gate_event(gate_event, _floor())
    assert approval is not None
    jsonschema.validate(approval, approved_schema)  # the bridge output conforms

    topics = json.loads((contracts / "topics.json").read_text(encoding="utf-8"))
    assert "geometry.publish.gate.v1" in json.dumps(topics)


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
