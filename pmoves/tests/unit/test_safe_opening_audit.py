"""
Hand-written pytest suite for pmoves.tools.safe_opening_audit.

Covers Clause 3 of the Safe-Activation Contract: the bind -> auth coupling
layered on top of port_audit's bind-scope check. The pure functions
(is_reachable, audit_auth_coupling, print_report) are tested with fixtures so
the suite needs no docker.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pmoves.tools.safe_opening_audit import (
    AUTH_GATES,
    UNSAFE_STATUSES,
    audit_auth_coupling,
    is_reachable,
    main,
    print_report,
)


def _finding(service: str, bind: str, host_port: str = "8080") -> dict:
    """Build a port_audit-shaped finding dict."""
    return {
        "service": service,
        "host_port": host_port,
        "container_port": "80",
        "bind": bind,
        "expected": "127.0.0.1",
        "status": "OK",
    }


# ============================================================================
# is_reachable
# ============================================================================


class TestIsReachable:
    def test_loopback_not_reachable(self) -> None:
        assert is_reachable("127.0.0.1") is False

    def test_all_interfaces_reachable(self) -> None:
        assert is_reachable("0.0.0.0") is True

    def test_specific_lan_ip_reachable(self) -> None:
        assert is_reachable("10.0.0.5") is True


# ============================================================================
# audit_auth_coupling
# ============================================================================


class TestAuditAuthCoupling:
    def test_loopback_findings_skipped(self) -> None:
        """Host-local (127.0.0.1) surfaces are out of scope."""
        findings = [_finding("supabase-db", "127.0.0.1")]
        results = audit_auth_coupling(findings, AUTH_GATES)
        assert results == []

    def test_reachable_gated_service_is_gated(self) -> None:
        findings = [_finding("agent-zero", "0.0.0.0")]
        results = audit_auth_coupling(findings, AUTH_GATES)
        assert len(results) == 1
        assert results[0]["auth_status"] == "GATED"
        assert results[0]["gate"] == "basic-auth"
        assert results[0]["evidence"]

    def test_reachable_unregistered_service_is_unverified(self) -> None:
        findings = [_finding("mystery-svc", "0.0.0.0")]
        results = audit_auth_coupling(findings, AUTH_GATES)
        assert results[0]["auth_status"] == "UNVERIFIED"

    def test_explicit_none_gate_is_ungated(self) -> None:
        gates = {"open-svc": {"gate": "none", "evidence": "intentionally checked"}}
        findings = [_finding("open-svc", "0.0.0.0")]
        results = audit_auth_coupling(findings, gates)
        assert results[0]["auth_status"] == "UNGATED"

    def test_empty_gate_string_is_ungated(self) -> None:
        gates = {"blank-svc": {"gate": "", "evidence": "x"}}
        results = audit_auth_coupling([_finding("blank-svc", "0.0.0.0")], gates)
        assert results[0]["auth_status"] == "UNGATED"

    def test_public_reviewed_surface_is_gated(self) -> None:
        """gate=='public' is a reviewed/accepted surface — treated as safe."""
        gates = {"landing": {"gate": "public", "evidence": "reviewed public page"}}
        results = audit_auth_coupling([_finding("landing", "0.0.0.0")], gates)
        assert results[0]["auth_status"] == "GATED"

    def test_missing_bind_defaults_to_reachable(self) -> None:
        """A finding without an explicit loopback bind is treated as reachable."""
        f = _finding("svc", "0.0.0.0")
        del f["bind"]
        results = audit_auth_coupling([f], {})
        assert len(results) == 1
        assert results[0]["auth_status"] == "UNVERIFIED"

    def test_mixed_findings_only_reachable_returned(self) -> None:
        findings = [
            _finding("agent-zero", "0.0.0.0"),
            _finding("supabase-db", "127.0.0.1"),
            _finding("mystery", "0.0.0.0"),
        ]
        results = audit_auth_coupling(findings, AUTH_GATES)
        services = {r["service"] for r in results}
        assert services == {"agent-zero", "mystery"}


# ============================================================================
# print_report — return codes
# ============================================================================


class TestPrintReportReturnCodes:
    def test_returns_zero_when_all_gated(self, capsys: pytest.CaptureFixture) -> None:
        results = audit_auth_coupling([_finding("agent-zero", "0.0.0.0")], AUTH_GATES)
        assert print_report(results) == 0

    def test_returns_one_when_unverified_present(self, capsys: pytest.CaptureFixture) -> None:
        results = audit_auth_coupling([_finding("mystery", "0.0.0.0")], AUTH_GATES)
        assert print_report(results) == 1

    def test_returns_zero_for_no_reachable_surfaces(self, capsys: pytest.CaptureFixture) -> None:
        assert print_report([]) == 0

    def test_unsafe_statuses_constant(self) -> None:
        assert UNSAFE_STATUSES == {"UNVERIFIED", "UNGATED"}


# ============================================================================
# print_report — output
# ============================================================================


class TestPrintReportOutput:
    def test_unsafe_marker_and_section(self, capsys: pytest.CaptureFixture) -> None:
        results = audit_auth_coupling([_finding("mystery", "0.0.0.0", "9000")], AUTH_GATES)
        print_report(results)
        out = capsys.readouterr().out
        assert "!!" in out
        assert "mystery:9000" in out
        assert "REACHABLE WITHOUT VERIFIED AUTH" in out
        assert "Funnel, don't expose" in out

    def test_clean_report_lists_gates(self, capsys: pytest.CaptureFixture) -> None:
        results = audit_auth_coupling([_finding("agent-zero", "0.0.0.0")], AUTH_GATES)
        print_report(results)
        out = capsys.readouterr().out
        assert "All reachable surfaces are auth-gated" in out
        assert "basic-auth" in out
        assert "!!" not in out

    def test_empty_report_message(self, capsys: pytest.CaptureFixture) -> None:
        print_report([])
        out = capsys.readouterr().out
        assert "No reachable surfaces published" in out


# ============================================================================
# main — fail-closed orchestration
# ============================================================================


class TestMain:
    def test_returns_1_when_compose_fails(self) -> None:
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value=None):
            assert main() == 1

    def test_returns_1_when_no_services(self) -> None:
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value={"services": {}}):
            assert main() == 1

    def test_returns_0_when_all_reachable_gated(self) -> None:
        config = {"services": {"agent-zero": {"ports": [{"host_ip": "0.0.0.0", "published": "8080", "target": "80"}]}}}
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value=config), \
             patch("pmoves.tools.safe_opening_audit.load_mesh_allowed_services",
                   return_value=(Path("/nonexistent"), {"agent-zero"}, set())):
            assert main() == 0

    def test_returns_1_when_reachable_unverified(self) -> None:
        config = {"services": {"mystery": {"ports": [{"host_ip": "0.0.0.0", "published": "8080", "target": "80"}]}}}
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value=config), \
             patch("pmoves.tools.safe_opening_audit.load_mesh_allowed_services",
                   return_value=(Path("/nonexistent"), {"mystery"}, set())):
            assert main() == 1

    def test_returns_0_when_only_loopback(self) -> None:
        """A loopback-only stack has no reachable surfaces — passes."""
        config = {"services": {"supabase-db": {"ports": [{"host_ip": "127.0.0.1", "published": "5432", "target": "5432"}]}}}
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value=config), \
             patch("pmoves.tools.safe_opening_audit.load_mesh_allowed_services",
                   return_value=(Path("/nonexistent"), set(), set())):
            assert main() == 0

    def test_fail_closed_prints_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        with patch("pmoves.tools.safe_opening_audit.parse_compose_config", return_value=None):
            main()
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "failing closed" in err


def _finding_port(service: str, bind: str, container_port: str, host_port: str = "8080") -> dict:
    """port_audit-shaped finding with an explicit container_port."""
    return {
        "service": service,
        "host_port": host_port,
        "container_port": container_port,
        "bind": bind,
        "expected": "127.0.0.1",
        "status": "OK",
    }


class TestPortScopedGate:
    """A gate with a 'ports' list covers only those container ports (NATS monitoring fix)."""

    def test_gated_port_is_gated(self) -> None:
        # nats gate covers 4222 (client) → reachable 4222 is GATED.
        r = audit_auth_coupling([_finding_port("nats", "0.0.0.0", "4222")], AUTH_GATES)
        assert r[0]["auth_status"] == "GATED"

    def test_uncovered_port_is_unverified(self) -> None:
        # nats monitoring 8222 is NOT in the gate's ports → UNVERIFIED, not a false GATED.
        r = audit_auth_coupling([_finding_port("nats", "0.0.0.0", "8222")], AUTH_GATES)
        assert r[0]["auth_status"] == "UNVERIFIED"
        assert r[0]["gate"] == ""  # don't attribute the client-port gate to the monitoring port

    def test_no_ports_key_covers_all_ports(self) -> None:
        # agent-zero has no 'ports' scope → any reachable port stays GATED (back-compat).
        r = audit_auth_coupling([_finding_port("agent-zero", "0.0.0.0", "55555")], AUTH_GATES)
        assert r[0]["auth_status"] == "GATED"


class TestImportShim:
    """The module imports under both run styles (package + cwd=pmoves/tools)."""

    def test_port_audit_symbols_imported(self) -> None:
        import pmoves.tools.safe_opening_audit as m
        assert callable(m.audit_ports)
        assert callable(m.parse_compose_config)
        assert callable(m.load_mesh_allowed_services)
