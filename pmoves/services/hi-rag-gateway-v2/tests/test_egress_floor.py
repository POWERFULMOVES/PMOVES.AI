import importlib.util
import json
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "egress_floor", Path(__file__).resolve().parents[1] / "egress_floor.py"
)
egress_floor = importlib.util.module_from_spec(_spec)
# Register in sys.modules before exec: `from __future__ import annotations` +
# @dataclass needs sys.modules[cls.__module__] to resolve stringified
# annotations (e.g. List[str]) when detecting ClassVar/InitVar. Without this,
# exec_module raises AttributeError on any Python version (3.11-3.14 verified).
sys.modules[_spec.name] = egress_floor
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


def test_unknown_rule_holds_fail_closed():
    floor = BlockAndHoldFloor(rules=["some-future-rule-we-dont-implement"], protected_terms=[])
    v = floor.check({"title": "totally clean public text"})
    assert v.clean is False
    assert "some-future-rule-we-dont-implement" in v.tripped


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


def test_namespace_with_lan_or_tailscale_ip_trips():
    v = _floor([]).check({"title": "x", "namespace": "tailnet-100.101.7.9"})
    assert v.clean is False
    assert "no-literal-lan-or-tailscale-ips" in v.tripped


def test_namespace_with_protected_term_trips():
    v = _floor(["shaela"]).check({"title": "x", "namespace": "shaela-private"})
    assert v.clean is False


def test_nested_meta_dict_with_lan_ip_trips():
    v = _floor([]).check({"title": "x", "meta": {"contact": {"ip": "192.168.1.5"}}})
    assert v.clean is False


def test_nested_meta_dict_with_protected_term_trips():
    v = _floor(["shaela"]).check({"title": "x", "meta": {"contact": {"name": "shaela"}}})
    assert v.clean is False


def test_clean_item_with_benign_namespace_and_nested_meta_passes():
    v = _floor([]).check({"title": "Public update", "namespace": "public", "meta": {"k": {"v": "all clear"}}})
    assert v.clean is True
    assert v.tripped == []
