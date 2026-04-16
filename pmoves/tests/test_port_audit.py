"""Tests for pmoves/tools/port_audit.py.

Covers audit_ports() classification logic, print_report() output and exit
codes, and the MESH_ALLOWED_SERVICES policy enforced by this PR.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module loading helper
# ---------------------------------------------------------------------------

_PORT_AUDIT_PATH = Path(__file__).resolve().parents[1] / "tools" / "port_audit.py"


def _load_port_audit() -> ModuleType:
    """Load port_audit as a module without executing __main__ guard."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("port_audit", _PORT_AUDIT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def port_audit() -> ModuleType:
    return _load_port_audit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**svc_ports: list[Any]) -> dict:
    """Build a minimal compose-config dict with the given service→ports map."""
    return {"services": {svc: {"ports": ports} for svc, ports in svc_ports.items()}}


# ---------------------------------------------------------------------------
# audit_ports — dict-format port entries
# ---------------------------------------------------------------------------


class TestAuditPortsDictFormat:
    """Port entries supplied as dicts (docker compose config --format json)."""

    def test_localhost_binding_is_ok(self, port_audit: ModuleType) -> None:
        """A non-mesh service bound to 127.0.0.1 should be OK."""
        config = _make_config(my_service=[{"host_ip": "127.0.0.1", "published": "8080", "target": "8080"}])
        findings = port_audit.audit_ports(config)
        assert len(findings) == 1
        assert findings[0]["status"] == "OK"
        assert findings[0]["bind"] == "127.0.0.1"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_mesh_binding_is_violation_when_not_in_allowlist(self, port_audit: ModuleType) -> None:
        """A service not in MESH_ALLOWED_SERVICES bound to 0.0.0.0 should be a VIOLATION."""
        config = _make_config(my_service=[{"host_ip": "0.0.0.0", "published": "8080", "target": "8080"}])
        findings = port_audit.audit_ports(config)
        assert len(findings) == 1
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_missing_host_ip_defaults_to_mesh_violation(self, port_audit: ModuleType) -> None:
        """When host_ip is absent the entry defaults to 0.0.0.0 → VIOLATION."""
        config = _make_config(my_service=[{"published": "9000", "target": "9000"}])
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_empty_host_ip_defaults_to_mesh_violation(self, port_audit: ModuleType) -> None:
        """An empty host_ip string is normalised to 0.0.0.0 → VIOLATION."""
        config = _make_config(my_service=[{"host_ip": "", "published": "9000", "target": "9000"}])
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_multiple_ports_on_same_service(self, port_audit: ModuleType) -> None:
        """All ports for a service are evaluated independently."""
        config = _make_config(svc=[
            {"host_ip": "127.0.0.1", "published": "8080", "target": "8080"},
            {"host_ip": "0.0.0.0", "published": "8081", "target": "8081"},
        ])
        findings = port_audit.audit_ports(config)
        assert len(findings) == 2
        statuses = {f["host_port"]: f["status"] for f in findings}
        assert statuses["8080"] == "OK"
        assert statuses["8081"] == "VIOLATION"

    def test_returned_fields_are_complete(self, port_audit: ModuleType) -> None:
        """Each finding must carry all required keys."""
        config = _make_config(svc=[{"host_ip": "127.0.0.1", "published": "3000", "target": "3000"}])
        finding = port_audit.audit_ports(config)[0]
        for key in ("service", "host_port", "container_port", "bind", "expected", "status"):
            assert key in finding, f"Missing key: {key}"

    def test_services_sorted_alphabetically(self, port_audit: ModuleType) -> None:
        """audit_ports iterates services in sorted order."""
        config = _make_config(
            zzz_svc=[{"host_ip": "127.0.0.1", "published": "9001", "target": "9001"}],
            aaa_svc=[{"host_ip": "127.0.0.1", "published": "9002", "target": "9002"}],
        )
        findings = port_audit.audit_ports(config)
        assert findings[0]["service"] == "aaa_svc"
        assert findings[1]["service"] == "zzz_svc"


# ---------------------------------------------------------------------------
# audit_ports — string-format port entries
# ---------------------------------------------------------------------------


class TestAuditPortsStringFormat:
    """Port entries as plain strings (older docker compose output)."""

    def test_three_part_localhost_string_is_ok(self, port_audit: ModuleType) -> None:
        """host_ip:host_port:container_port format with 127.0.0.1 → OK."""
        config = _make_config(svc=["127.0.0.1:8080:8080"])
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "127.0.0.1"
        assert findings[0]["status"] == "OK"

    def test_three_part_mesh_string_is_violation(self, port_audit: ModuleType) -> None:
        """host_ip:host_port:container_port with 0.0.0.0 → VIOLATION."""
        config = _make_config(svc=["0.0.0.0:8080:8080"])
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_two_part_string_defaults_to_mesh_violation(self, port_audit: ModuleType) -> None:
        """host_port:container_port (no IP) defaults to 0.0.0.0 → VIOLATION."""
        config = _make_config(svc=["8080:8080"])
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_single_part_string_skipped(self, port_audit: ModuleType) -> None:
        """A bare port number (no colon) cannot be parsed → no finding produced."""
        config = _make_config(svc=["8080"])
        findings = port_audit.audit_ports(config)
        assert findings == []

    def test_non_string_non_dict_entry_skipped(self, port_audit: ModuleType) -> None:
        """Unknown port entry types (e.g. int) are silently skipped."""
        config = _make_config(svc=[42])
        findings = port_audit.audit_ports(config)
        assert findings == []


# ---------------------------------------------------------------------------
# audit_ports — Kong admin special case
# ---------------------------------------------------------------------------


class TestAuditPortsKongAdmin:
    """Kong admin port 8001 is always expected on 127.0.0.1."""

    def test_kong_admin_on_localhost_is_ok(self, port_audit: ModuleType) -> None:
        config = _make_config(**{"supabase-kong": [{"host_ip": "127.0.0.1", "published": "8001", "target": "8001"}]})
        findings = port_audit.audit_ports(config)
        assert findings[0]["expected"] == "127.0.0.1"
        assert findings[0]["status"] == "OK"

    def test_kong_admin_on_mesh_is_violation(self, port_audit: ModuleType) -> None:
        config = _make_config(**{"supabase-kong": [{"host_ip": "0.0.0.0", "published": "8001", "target": "8001"}]})
        findings = port_audit.audit_ports(config)
        assert findings[0]["expected"] == "127.0.0.1"
        assert findings[0]["status"] == "VIOLATION"

    def test_kong_proxy_port_not_treated_as_admin(self, port_audit: ModuleType) -> None:
        """Port 8000 (Kong proxy) for supabase-kong is NOT the admin port."""
        config = _make_config(**{"supabase-kong": [{"host_ip": "0.0.0.0", "published": "8000", "target": "8000"}]})
        findings = port_audit.audit_ports(config)
        # 8000 is not in KONG_ADMIN_PORTS so it follows the normal policy
        assert findings[0]["expected"] == "127.0.0.1"

    def test_other_service_port_8001_not_admin_locked(self, port_audit: ModuleType) -> None:
        """Only 'supabase-kong' triggers the admin-port special case."""
        config = _make_config(other_svc=[{"host_ip": "0.0.0.0", "published": "8001", "target": "8001"}])
        findings = port_audit.audit_ports(config)
        # is_kong_admin=False → expected follows normal mesh rules
        assert findings[0]["expected"] == "127.0.0.1"
        assert findings[0]["status"] == "VIOLATION"


# ---------------------------------------------------------------------------
# audit_ports — MESH_ALLOWED_SERVICES allowlist
# ---------------------------------------------------------------------------


class TestMeshAllowedServices:
    """Tests for MESH_ALLOWED_SERVICES behaviour introduced by the PR comment change."""

    def test_mesh_allowed_services_is_empty_by_default(self, port_audit: ModuleType) -> None:
        """PR enforces that MESH_ALLOWED_SERVICES starts as an empty set.

        The PR comment explicitly changed the description to say the set
        should remain empty unless overridden for intentional mesh exposure.
        """
        assert port_audit.MESH_ALLOWED_SERVICES == set()

    def test_service_in_allowlist_expects_mesh_binding(self, port_audit: ModuleType, monkeypatch) -> None:
        """A service added to MESH_ALLOWED_SERVICES should expect 0.0.0.0."""
        monkeypatch.setattr(port_audit, "MESH_ALLOWED_SERVICES", {"my_mesh_svc"})
        config = _make_config(my_mesh_svc=[{"host_ip": "0.0.0.0", "published": "8080", "target": "8080"}])
        findings = port_audit.audit_ports(config)
        assert findings[0]["expected"] == "0.0.0.0"
        assert findings[0]["status"] == "OK"

    def test_service_in_allowlist_localhost_is_violation(self, port_audit: ModuleType, monkeypatch) -> None:
        """A mesh-allowed service bound to 127.0.0.1 is also a VIOLATION."""
        monkeypatch.setattr(port_audit, "MESH_ALLOWED_SERVICES", {"my_mesh_svc"})
        config = _make_config(my_mesh_svc=[{"host_ip": "127.0.0.1", "published": "8080", "target": "8080"}])
        findings = port_audit.audit_ports(config)
        assert findings[0]["expected"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"


# ---------------------------------------------------------------------------
# audit_ports — edge cases
# ---------------------------------------------------------------------------


class TestAuditPortsEdgeCases:
    def test_empty_services_returns_empty_list(self, port_audit: ModuleType) -> None:
        findings = port_audit.audit_ports({"services": {}})
        assert findings == []

    def test_service_with_no_ports_returns_no_findings(self, port_audit: ModuleType) -> None:
        findings = port_audit.audit_ports({"services": {"svc": {}}})
        assert findings == []

    def test_service_with_empty_ports_list(self, port_audit: ModuleType) -> None:
        findings = port_audit.audit_ports({"services": {"svc": {"ports": []}}})
        assert findings == []

    def test_host_port_and_container_port_preserved(self, port_audit: ModuleType) -> None:
        config = _make_config(svc=[{"host_ip": "127.0.0.1", "published": "1234", "target": "5678"}])
        finding = port_audit.audit_ports(config)[0]
        assert finding["host_port"] == "1234"
        assert finding["container_port"] == "5678"

    def test_service_name_preserved_in_finding(self, port_audit: ModuleType) -> None:
        config = _make_config(my_unique_service=[{"host_ip": "127.0.0.1", "published": "1000", "target": "1000"}])
        finding = port_audit.audit_ports(config)[0]
        assert finding["service"] == "my_unique_service"


# ---------------------------------------------------------------------------
# print_report
# ---------------------------------------------------------------------------


class TestPrintReport:
    def test_no_violations_returns_exit_code_0(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "8080", "container_port": "8080",
                     "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        rc = port_audit.print_report(findings)
        assert rc == 0

    def test_with_violations_returns_exit_code_1(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "8080", "container_port": "8080",
                     "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        rc = port_audit.print_report(findings)
        assert rc == 1

    def test_ok_finding_printed_without_bang(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "8080", "container_port": "8080",
                     "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "!!" not in out
        assert "OK" in out

    def test_violation_finding_printed_with_bang(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "8080", "container_port": "8080",
                     "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "!!" in out
        assert "VIOLATION" in out

    def test_violation_details_printed(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "bad_svc", "host_port": "9999", "container_port": "9999",
                     "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "bad_svc" in out
        assert "9999" in out
        assert "0.0.0.0" in out

    def test_total_count_in_output(self, port_audit: ModuleType, capsys) -> None:
        findings = [
            {"service": "s1", "host_port": "1", "container_port": "1",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
            {"service": "s2", "host_port": "2", "container_port": "2",
             "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "2" in out  # total count
        assert "1" in out  # violation count reported

    def test_empty_findings_returns_exit_code_0(self, port_audit: ModuleType, capsys) -> None:
        rc = port_audit.print_report([])
        assert rc == 0

    def test_all_ok_message_printed(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "80", "container_port": "80",
                     "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "All port bindings match security policy" in out

    def test_violation_message_not_printed_when_all_ok(self, port_audit: ModuleType, capsys) -> None:
        findings = [{"service": "svc", "host_port": "80", "container_port": "80",
                     "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        port_audit.print_report(findings)
        out = capsys.readouterr().out
        assert "VIOLATIONS" not in out


# ---------------------------------------------------------------------------
# main() — integration (no docker dependency)
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_returns_1_when_compose_unavailable(self, port_audit: ModuleType, monkeypatch, capsys) -> None:
        """main() fails closed (returns 1) when docker compose is unreachable."""
        monkeypatch.setattr(port_audit, "parse_compose_config", lambda: None)
        rc = port_audit.main()
        assert rc == 1

    def test_main_returns_1_when_services_empty(self, port_audit: ModuleType, monkeypatch, capsys) -> None:
        """main() fails closed when compose returns no services."""
        monkeypatch.setattr(port_audit, "parse_compose_config", lambda: {"services": {}})
        rc = port_audit.main()
        assert rc == 1

    def test_main_returns_0_for_clean_config(self, port_audit: ModuleType, monkeypatch, capsys) -> None:
        """main() returns 0 when all ports comply with policy."""
        config = {"services": {"svc": {"ports": [{"host_ip": "127.0.0.1", "published": "8080", "target": "8080"}]}}}
        monkeypatch.setattr(port_audit, "parse_compose_config", lambda: config)
        rc = port_audit.main()
        assert rc == 0

    def test_main_returns_1_for_violating_config(self, port_audit: ModuleType, monkeypatch, capsys) -> None:
        """main() returns 1 when any port violates policy."""
        config = {"services": {"svc": {"ports": [{"host_ip": "0.0.0.0", "published": "8080", "target": "8080"}]}}}
        monkeypatch.setattr(port_audit, "parse_compose_config", lambda: config)
        rc = port_audit.main()
        assert rc == 1