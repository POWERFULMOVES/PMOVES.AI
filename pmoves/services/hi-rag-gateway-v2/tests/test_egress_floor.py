import importlib.util
import sys
from pathlib import Path

import pytest

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
