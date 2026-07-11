import importlib.util
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
