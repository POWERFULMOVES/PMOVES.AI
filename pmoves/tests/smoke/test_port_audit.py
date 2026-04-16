"""Tests for pmoves/tools/port_audit.py — port binding security audit.

Validates the audit_ports() classification logic, print_report() return codes,
and main() failure-closed behaviour introduced/updated in this PR.
"""

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

import port_audit  # noqa: E402  (after sys.path manipulation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(services: dict) -> dict:
    return {"services": services}


def _dict_port(host_ip: str, published: str, target: str) -> dict:
    return {"host_ip": host_ip, "published": published, "target": target}


def _str_port_3(host_ip: str, published: str, target: str) -> str:
    return f"{host_ip}:{published}:{target}"


def _str_port_2(published: str, target: str) -> str:
    """Two-part string format — host_ip defaults to 0.0.0.0."""
    return f"{published}:{target}"


# ---------------------------------------------------------------------------
# audit_ports — dict-format port entries
# ---------------------------------------------------------------------------


class TestAuditPortsDictFormat:
    """audit_ports() with dict-style port entries (docker compose config --format json)."""

    def test_localhost_bind_non_mesh_service_is_ok(self):
        config = _make_config({
            "my-service": {"ports": [_dict_port("127.0.0.1", "8080", "8080")]}
        })
        findings = port_audit.audit_ports(config)
        assert len(findings) == 1
        assert findings[0]["status"] == "OK"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_wide_open_bind_non_mesh_service_is_violation(self):
        config = _make_config({
            "my-service": {"ports": [_dict_port("0.0.0.0", "8080", "8080")]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["expected"] == "127.0.0.1"
        assert findings[0]["bind"] == "0.0.0.0"

    def test_empty_host_ip_defaults_to_wide_open_violation(self):
        """An empty host_ip string must be treated as 0.0.0.0."""
        config = _make_config({
            "my-service": {"ports": [{"host_ip": "", "published": "9000", "target": "9000"}]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_missing_host_ip_key_defaults_to_wide_open_violation(self):
        """A port entry with no host_ip key must default to 0.0.0.0."""
        config = _make_config({
            "my-service": {"ports": [{"published": "9001", "target": "9001"}]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_kong_admin_port_always_expects_localhost(self):
        """Port 8001 on supabase-kong must always expect 127.0.0.1 regardless of MESH_ALLOWED_SERVICES."""
        # Even if supabase-kong is somehow in MESH_ALLOWED_SERVICES, admin port stays localhost
        original = port_audit.MESH_ALLOWED_SERVICES
        try:
            port_audit.MESH_ALLOWED_SERVICES = {"supabase-kong"}
            config = _make_config({
                "supabase-kong": {"ports": [_dict_port("127.0.0.1", "8001", "8001")]}
            })
            findings = port_audit.audit_ports(config)
            assert findings[0]["expected"] == "127.0.0.1"
            assert findings[0]["status"] == "OK"
        finally:
            port_audit.MESH_ALLOWED_SERVICES = original

    def test_kong_admin_wide_open_is_violation(self):
        """Kong admin port bound to 0.0.0.0 must be flagged as a VIOLATION."""
        config = _make_config({
            "supabase-kong": {"ports": [_dict_port("0.0.0.0", "8001", "8001")]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["status"] == "VIOLATION"

    def test_mesh_allowed_service_wide_open_is_ok(self):
        """A service in MESH_ALLOWED_SERVICES may bind 0.0.0.0 without violation."""
        original = port_audit.MESH_ALLOWED_SERVICES
        try:
            port_audit.MESH_ALLOWED_SERVICES = {"agent-zero"}
            config = _make_config({
                "agent-zero": {"ports": [_dict_port("0.0.0.0", "8080", "8080")]}
            })
            findings = port_audit.audit_ports(config)
            assert findings[0]["status"] == "OK"
            assert findings[0]["expected"] == "0.0.0.0"
        finally:
            port_audit.MESH_ALLOWED_SERVICES = original

    def test_mesh_allowed_service_localhost_bind_is_violation(self):
        """A mesh-allowed service bound to 127.0.0.1 is flagged (expected 0.0.0.0)."""
        original = port_audit.MESH_ALLOWED_SERVICES
        try:
            port_audit.MESH_ALLOWED_SERVICES = {"agent-zero"}
            config = _make_config({
                "agent-zero": {"ports": [_dict_port("127.0.0.1", "8080", "8080")]}
            })
            findings = port_audit.audit_ports(config)
            assert findings[0]["status"] == "VIOLATION"
            assert findings[0]["expected"] == "0.0.0.0"
        finally:
            port_audit.MESH_ALLOWED_SERVICES = original

    def test_finding_contains_all_required_fields(self):
        config = _make_config({
            "svc": {"ports": [_dict_port("127.0.0.1", "8200", "8200")]}
        })
        findings = port_audit.audit_ports(config)
        assert len(findings) == 1
        f = findings[0]
        for key in ("service", "host_port", "container_port", "bind", "expected", "status"):
            assert key in f, f"Missing field: {key}"

    def test_multiple_services_returned_sorted(self):
        config = _make_config({
            "zebra-svc": {"ports": [_dict_port("127.0.0.1", "9000", "9000")]},
            "alpha-svc": {"ports": [_dict_port("127.0.0.1", "8000", "8000")]},
        })
        findings = port_audit.audit_ports(config)
        services = [f["service"] for f in findings]
        assert services == sorted(services), "audit_ports should return findings in alphabetical service order"

    def test_service_with_no_ports_contributes_no_findings(self):
        config = _make_config({
            "internal-svc": {},  # no 'ports' key
        })
        findings = port_audit.audit_ports(config)
        assert findings == []

    def test_empty_ports_list_contributes_no_findings(self):
        config = _make_config({
            "internal-svc": {"ports": []},
        })
        findings = port_audit.audit_ports(config)
        assert findings == []


# ---------------------------------------------------------------------------
# audit_ports — string-format port entries
# ---------------------------------------------------------------------------


class TestAuditPortsStringFormat:
    """audit_ports() with string-format port entries."""

    def test_three_part_string_localhost_is_ok(self):
        config = _make_config({
            "svc": {"ports": [_str_port_3("127.0.0.1", "8080", "8080")]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["status"] == "OK"
        assert findings[0]["bind"] == "127.0.0.1"

    def test_three_part_string_wide_open_is_violation(self):
        config = _make_config({
            "svc": {"ports": [_str_port_3("0.0.0.0", "8080", "8080")]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["bind"] == "0.0.0.0"

    def test_two_part_string_defaults_to_wide_open(self):
        """Two-part string (no host_ip) must default host_ip to 0.0.0.0, causing a VIOLATION."""
        config = _make_config({
            "svc": {"ports": [_str_port_2("8080", "8080")]}
        })
        findings = port_audit.audit_ports(config)
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_one_part_string_is_skipped(self):
        """A port entry that is not parse-able (only 1 part) should be skipped."""
        config = _make_config({
            "svc": {"ports": ["8080"]}
        })
        findings = port_audit.audit_ports(config)
        assert findings == []

    def test_non_dict_non_string_port_entry_is_skipped(self):
        """A port entry that is neither dict nor string should be skipped gracefully."""
        config = _make_config({
            "svc": {"ports": [12345]}
        })
        findings = port_audit.audit_ports(config)
        assert findings == []


# ---------------------------------------------------------------------------
# audit_ports — MESH_ALLOWED_SERVICES currently empty (PR policy)
# ---------------------------------------------------------------------------


class TestMeshAllowedServicesEmpty:
    """Verify the PR policy: MESH_ALLOWED_SERVICES defaults to empty set."""

    def test_mesh_allowed_services_is_empty_by_default(self):
        """The PR changed the comment but kept MESH_ALLOWED_SERVICES = set()."""
        assert port_audit.MESH_ALLOWED_SERVICES == set(), (
            "MESH_ALLOWED_SERVICES must be empty — all services default to loopback"
        )

    def test_kong_admin_ports_contains_8001(self):
        assert "8001" in port_audit.KONG_ADMIN_PORTS


# ---------------------------------------------------------------------------
# print_report
# ---------------------------------------------------------------------------


class TestPrintReport:
    """print_report() return codes and output."""

    def _capture(self, findings):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = port_audit.print_report(findings)
        return code, buf.getvalue()

    def test_no_findings_returns_zero(self):
        code, _ = self._capture([])
        assert code == 0

    def test_all_ok_findings_returns_zero(self):
        findings = [
            {"service": "svc-a", "host_port": "8080", "container_port": "8080",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
            {"service": "svc-b", "host_port": "9090", "container_port": "9090",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
        ]
        code, output = self._capture(findings)
        assert code == 0
        assert "Violations: 0" in output or "violations: 0" in output.lower() or "Violations: 0" in output

    def test_single_violation_returns_one(self):
        findings = [
            {"service": "bad-svc", "host_port": "8080", "container_port": "8080",
             "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        code, output = self._capture(findings)
        assert code == 1
        assert "VIOLATION" in output

    def test_mixed_ok_and_violation_returns_one(self):
        findings = [
            {"service": "good-svc", "host_port": "8000", "container_port": "8000",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
            {"service": "bad-svc", "host_port": "8080", "container_port": "8080",
             "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        code, _ = self._capture(findings)
        assert code == 1

    def test_report_includes_violation_marker(self):
        findings = [
            {"service": "bad-svc", "host_port": "8080", "container_port": "8080",
             "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        _, output = self._capture(findings)
        assert "!!" in output, "VIOLATION rows should be prefixed with '!!'"

    def test_ok_rows_not_marked_with_violation_prefix(self):
        findings = [
            {"service": "good-svc", "host_port": "8080", "container_port": "8080",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
        ]
        _, output = self._capture(findings)
        assert "!!" not in output

    def test_report_header_always_present(self):
        _, output = self._capture([])
        assert "SERVICE" in output
        assert "BIND" in output
        assert "STATUS" in output

    def test_violation_summary_lists_service(self):
        findings = [
            {"service": "leaky-svc", "host_port": "9000", "container_port": "9000",
             "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        _, output = self._capture(findings)
        assert "leaky-svc" in output

    def test_port_count_summary_appears(self):
        findings = [
            {"service": "svc", "host_port": "8080", "container_port": "8080",
             "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
        ]
        _, output = self._capture(findings)
        assert "1" in output  # "Total: 1 ports"


# ---------------------------------------------------------------------------
# main() — failure-closed behaviour
# ---------------------------------------------------------------------------


class TestMainFailClosed:
    """main() returns 1 when compose parsing fails (fail-closed security posture)."""

    def test_main_returns_1_when_config_is_none(self):
        with patch.object(port_audit, "parse_compose_config", return_value=None):
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                result = port_audit.main()
            assert result == 1

    def test_main_returns_1_when_no_services(self):
        with patch.object(port_audit, "parse_compose_config", return_value={"services": {}}):
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                result = port_audit.main()
            assert result == 1

    def test_main_returns_1_when_services_key_missing(self):
        with patch.object(port_audit, "parse_compose_config", return_value={}):
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                result = port_audit.main()
            assert result == 1

    def test_main_returns_0_when_all_ports_compliant(self):
        cfg = _make_config({
            "clean-svc": {"ports": [_dict_port("127.0.0.1", "8080", "8080")]}
        })
        with patch.object(port_audit, "parse_compose_config", return_value=cfg):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                result = port_audit.main()
            assert result == 0

    def test_main_returns_1_when_violation_present(self):
        cfg = _make_config({
            "bad-svc": {"ports": [_dict_port("0.0.0.0", "8080", "8080")]}
        })
        with patch.object(port_audit, "parse_compose_config", return_value=cfg):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                result = port_audit.main()
            assert result == 1