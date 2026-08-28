"""
Hand-written pytest suite for pmoves.tools.port_audit.

Closes #1282. Replaces closed #1264 (CodeRabbit auto-tests, 27 failures).
Tests current API post-PR #1261 (compose-bind-policy-review).

Coverage target: >= 80% line coverage.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from pmoves.tools.port_audit import (
    BIND_VAR_TO_SERVICES,
    KONG_ADMIN_PORTS,
    PORT_AUDIT_BIND_FILE_ENV,
    audit_ports,
    load_mesh_allowed_services,
    main,
    parse_compose_config,
    print_report,
)


# ============================================================================
# audit_ports — dict port format
# ============================================================================


class TestAuditPortsDictFormat:
    """audit_ports with long-form dict port entries."""

    def test_dict_port_localhost_binding_ok(self) -> None:
        """Non-mesh service bound to 127.0.0.1 is OK."""
        config = {"services": {"web": {"ports": [{"host_ip": "127.0.0.1", "published": "8080", "target": "80"}]}}}
        findings = audit_ports(config, set())
        assert len(findings) == 1
        assert findings[0]["status"] == "OK"
        assert findings[0]["bind"] == "127.0.0.1"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_dict_port_violation_when_non_mesh_exposed(self) -> None:
        """Non-mesh service bound to 0.0.0.0 is a VIOLATION."""
        config = {"services": {"web": {"ports": [{"host_ip": "0.0.0.0", "published": "8080", "target": "80"}]}}}
        findings = audit_ports(config, set())
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_dict_port_mesh_allowed_service_ok(self) -> None:
        """Mesh-allowed service bound to 0.0.0.0 is OK."""
        config = {"services": {"nats": {"ports": [{"host_ip": "0.0.0.0", "published": "4222", "target": "4222"}]}}}
        findings = audit_ports(config, {"nats"})
        assert findings[0]["status"] == "OK"
        assert findings[0]["expected"] == "0.0.0.0"

    def test_dict_port_mesh_allowed_but_localhost_is_violation(self) -> None:
        """Mesh-allowed service bound to 127.0.0.1 when 0.0.0.0 expected is VIOLATION."""
        config = {"services": {"nats": {"ports": [{"host_ip": "127.0.0.1", "published": "4222", "target": "4222"}]}}}
        findings = audit_ports(config, {"nats"})
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["expected"] == "0.0.0.0"

    def test_dict_port_missing_host_ip_defaults_to_0_0_0_0(self) -> None:
        """Dict port entry without host_ip defaults to 0.0.0.0."""
        config = {"services": {"web": {"ports": [{"published": "8080", "target": "80"}]}}}
        findings = audit_ports(config, set())
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_dict_port_empty_string_host_ip_defaults_to_0_0_0_0(self) -> None:
        """Dict port entry with host_ip='' defaults to 0.0.0.0."""
        config = {"services": {"web": {"ports": [{"host_ip": "", "published": "8080", "target": "80"}]}}}
        findings = audit_ports(config, set())
        assert findings[0]["bind"] == "0.0.0.0"

    def test_dict_port_fields_copied_correctly(self) -> None:
        """All fields in the finding dict match the port entry."""
        config = {"services": {"api": {"ports": [{"host_ip": "127.0.0.1", "published": "3000", "target": "3000"}]}}}
        findings = audit_ports(config, set())
        f = findings[0]
        assert f["service"] == "api"
        assert f["host_port"] == "3000"
        assert f["container_port"] == "3000"
        assert f["bind"] == "127.0.0.1"
        assert f["expected"] == "127.0.0.1"
        assert f["status"] == "OK"


# ============================================================================
# audit_ports — string port format
# ============================================================================


class TestAuditPortsStringFormat:
    """audit_ports with string-format port entries."""

    def test_string_three_part_localhost(self) -> None:
        """'127.0.0.1:8080:80' parses correctly."""
        config = {"services": {"web": {"ports": ["127.0.0.1:8080:80"]}}}
        findings = audit_ports(config, set())
        assert findings[0]["bind"] == "127.0.0.1"
        assert findings[0]["host_port"] == "8080"
        assert findings[0]["container_port"] == "80"
        assert findings[0]["status"] == "OK"

    def test_string_three_part_zero_zero(self) -> None:
        """'0.0.0.0:4222:4222' for non-mesh is VIOLATION."""
        config = {"services": {"web": {"ports": ["0.0.0.0:4222:4222"]}}}
        findings = audit_ports(config, set())
        assert findings[0]["status"] == "VIOLATION"

    def test_string_two_part_defaults_to_0_0_0_0(self) -> None:
        """'8080:80' (two parts) defaults host_ip to 0.0.0.0."""
        config = {"services": {"web": {"ports": ["8080:80"]}}}
        findings = audit_ports(config, set())
        assert findings[0]["bind"] == "0.0.0.0"
        assert findings[0]["status"] == "VIOLATION"

    def test_string_two_part_mesh_allowed_ok(self) -> None:
        """'4222:4222' for mesh-allowed service is OK."""
        config = {"services": {"nats": {"ports": ["4222:4222"]}}}
        findings = audit_ports(config, {"nats"})
        assert findings[0]["status"] == "OK"
        assert findings[0]["expected"] == "0.0.0.0"

    def test_string_single_part_skipped(self) -> None:
        """Malformed string '8080' (single part) is skipped."""
        config = {"services": {"web": {"ports": ["8080"]}}}
        findings = audit_ports(config, set())
        assert len(findings) == 0

    def test_string_empty_string_skipped(self) -> None:
        """Empty string port entry is skipped."""
        config = {"services": {"web": {"ports": [""]}}}
        findings = audit_ports(config, set())
        assert len(findings) == 0


# ============================================================================
# audit_ports — Kong admin ports
# ============================================================================


class TestAuditPortsKongAdmin:
    """Kong admin port 8001 always expects 127.0.0.1 regardless of mesh."""

    def test_kong_admin_8001_localhost_ok(self) -> None:
        """Kong admin port on 127.0.0.1 is OK."""
        config = {"services": {"supabase-kong": {"ports": [{"host_ip": "127.0.0.1", "published": "8001", "target": "8001"}]}}}
        findings = audit_ports(config, {"supabase-kong"})
        assert findings[0]["status"] == "OK"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_kong_admin_8001_exposed_is_violation(self) -> None:
        """Kong admin port on 0.0.0.0 is VIOLATION even if mesh-allowed."""
        config = {"services": {"supabase-kong": {"ports": [{"host_ip": "0.0.0.0", "published": "8001", "target": "8001"}]}}}
        findings = audit_ports(config, {"supabase-kong"})
        assert findings[0]["status"] == "VIOLATION"
        assert findings[0]["expected"] == "127.0.0.1"

    def test_kong_non_admin_port_follows_mesh_policy(self) -> None:
        """Kong non-admin port (e.g. 8000) follows normal mesh policy."""
        config = {"services": {"supabase-kong": {"ports": [{"host_ip": "0.0.0.0", "published": "8000", "target": "8000"}]}}}
        findings = audit_ports(config, {"supabase-kong"})
        assert findings[0]["status"] == "OK"
        assert findings[0]["expected"] == "0.0.0.0"


# ============================================================================
# audit_ports — edge cases
# ============================================================================


class TestAuditPortsEdgeCases:
    """Edge cases for audit_ports."""

    def test_empty_services_dict(self) -> None:
        """No services returns empty findings list."""
        config = {"services": {}}
        findings = audit_ports(config, set())
        assert findings == []

    def test_missing_services_key(self) -> None:
        """Config without 'services' key returns empty list."""
        config = {}
        findings = audit_ports(config, set())
        assert findings == []

    def test_service_without_ports_key(self) -> None:
        """Service with no 'ports' key produces no findings."""
        config = {"services": {"web": {"image": "nginx"}}}
        findings = audit_ports(config, set())
        assert findings == []

    def test_service_with_empty_ports_list(self) -> None:
        """Service with ports=[] produces no findings."""
        config = {"services": {"web": {"ports": []}}}
        findings = audit_ports(config, set())
        assert findings == []

    def test_non_dict_non_string_port_entry_skipped(self) -> None:
        """Integer port entry is skipped."""
        config = {"services": {"web": {"ports": [8080]}}}
        findings = audit_ports(config, set())
        assert len(findings) == 0

    def test_none_port_entry_skipped(self) -> None:
        """None port entry is skipped."""
        config = {"services": {"web": {"ports": [None]}}}
        findings = audit_ports(config, set())
        assert len(findings) == 0

    def test_multiple_ports_single_service(self) -> None:
        """Service with multiple port entries produces multiple findings."""
        config = {
            "services": {
                "web": {
                    "ports": [
                        {"host_ip": "127.0.0.1", "published": "8080", "target": "80"},
                        {"host_ip": "127.0.0.1", "published": "8443", "target": "443"},
                    ]
                }
            }
        }
        findings = audit_ports(config, set())
        assert len(findings) == 2
        assert all(f["status"] == "OK" for f in findings)

    def test_services_sorted_alphabetically(self) -> None:
        """Findings are sorted by service name."""
        config = {
            "services": {
                "zebra": {"ports": [{"host_ip": "127.0.0.1", "published": "1", "target": "1"}]},
                "alpha": {"ports": [{"host_ip": "127.0.0.1", "published": "2", "target": "2"}]},
            }
        }
        findings = audit_ports(config, set())
        assert findings[0]["service"] == "alpha"
        assert findings[1]["service"] == "zebra"

    def test_published_and_target_coerced_to_string(self) -> None:
        """Integer published/target values are stringified."""
        config = {"services": {"web": {"ports": [{"host_ip": "127.0.0.1", "published": 8080, "target": 80}]}}}
        findings = audit_ports(config, set())
        assert findings[0]["host_port"] == "8080"
        assert findings[0]["container_port"] == "80"


# ============================================================================
# print_report — return codes
# ============================================================================


class TestPrintReportReturnCodes:
    """print_report exit code behavior."""

    def test_returns_zero_when_no_violations(self, capsys: pytest.CaptureFixture) -> None:
        """Clean findings return exit code 0."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        rc = print_report(findings, Path("/nonexistent"), set(), set())
        assert rc == 0

    def test_returns_one_when_violations_present(self, capsys: pytest.CaptureFixture) -> None:
        """Findings with violations return exit code 1."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        rc = print_report(findings, Path("/nonexistent"), set(), set())
        assert rc == 1

    def test_returns_zero_for_empty_findings(self, capsys: pytest.CaptureFixture) -> None:
        """Empty findings list returns 0 (no ports, no violations)."""
        rc = print_report([], Path("/nonexistent"), set(), set())
        assert rc == 0


# ============================================================================
# print_report — output rendering
# ============================================================================


class TestPrintReportOutput:
    """print_report stdout content."""

    def test_header_line_printed(self, capsys: pytest.CaptureFixture) -> None:
        """Table header with SERVICE, HOST_PORT, BIND, EXPECTED, STATUS."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "SERVICE" in out
        assert "HOST_PORT" in out
        assert "BIND" in out
        assert "EXPECTED" in out
        assert "STATUS" in out

    def test_separator_line_printed(self, capsys: pytest.CaptureFixture) -> None:
        """Dashed separator line after header."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "---" in out

    def test_summary_line_with_totals(self, capsys: pytest.CaptureFixture) -> None:
        """Summary shows total ports and violation count."""
        findings = [
            {"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"},
            {"service": "api", "host_port": "3000", "container_port": "3000", "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"},
        ]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "Total: 2 ports" in out
        assert "Violations: 1" in out

    def test_ok_finding_printed_without_marker(self, capsys: pytest.CaptureFixture) -> None:
        """OK findings have spaces instead of !! marker."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "!!" not in out
        assert "web" in out

    def test_violation_finding_printed_with_marker(self, capsys: pytest.CaptureFixture) -> None:
        """VIOLATION findings have !! marker."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "!!" in out

    def test_clean_message_when_no_violations(self, capsys: pytest.CaptureFixture) -> None:
        """'All port bindings match security policy.' printed when clean."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "All port bindings match security policy" in out

    def test_violation_details_printed(self, capsys: pytest.CaptureFixture) -> None:
        """Violation details show service, port, bind, and expected."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "0.0.0.0", "expected": "127.0.0.1", "status": "VIOLATION"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "web:8080" in out
        assert "0.0.0.0" in out
        assert "127.0.0.1" in out
        assert "VIOLATIONS" in out

    def test_no_violation_details_when_clean(self, capsys: pytest.CaptureFixture) -> None:
        """No violation section printed when all OK."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent"), set(), set())
        out = capsys.readouterr().out
        assert "VIOLATIONS" not in out


# ============================================================================
# print_report — bind_file context
# ============================================================================


class TestPrintReportBindFileContext:
    """print_report output when bind file exists."""

    def test_bind_file_path_printed_when_exists(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """Existing bind file path is printed in report header."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("# test\n")
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, bind_file, set(), set())
        out = capsys.readouterr().out
        assert str(bind_file) in out
        assert "Local mesh allowlist file" in out

    def test_mesh_allowed_services_listed(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """Mesh-allowed service names are listed in report header."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=0.0.0.0\n")
        findings = []
        print_report(findings, bind_file, {"nats"}, set())
        out = capsys.readouterr().out
        assert "nats" in out
        assert "Reviewed mesh exceptions loaded" in out

    def test_none_services_shows_none_label(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """Empty mesh allowed services shows 'none'."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("# empty\n")
        print_report([], bind_file, set(), set())
        out = capsys.readouterr().out
        assert "none" in out

    def test_no_bind_file_context_when_missing(self, capsys: pytest.CaptureFixture) -> None:
        """No bind file context printed when file doesn't exist."""
        findings = [{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}]
        print_report(findings, Path("/nonexistent/path/bind"), set(), set())
        out = capsys.readouterr().out
        assert "Local mesh allowlist file" not in out


# ============================================================================
# print_report — unmapped vars
# ============================================================================


class TestPrintReportUnmappedVars:
    """print_report handling of unmapped *_BIND variables."""

    def test_unmapped_vars_warning_printed(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """Unmapped BIND vars trigger WARNING line."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("UNKNOWN_BIND=0.0.0.0\n")
        findings = []
        print_report(findings, bind_file, set(), {"UNKNOWN_BIND"})
        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "UNKNOWN_BIND" in out
        assert "Unmapped" in out

    def test_no_unmapped_warning_when_empty(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """No WARNING when unmapped_vars is empty."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=0.0.0.0\n")
        print_report([], bind_file, {"nats"}, set())
        out = capsys.readouterr().out
        assert "WARNING" not in out
        assert "Unmapped" not in out

    def test_multiple_unmapped_vars_sorted(self, capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
        """Multiple unmapped vars are sorted alphabetically in output."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("# test\n")
        print_report([], bind_file, set(), {"ZETA_BIND", "ALPHA_BIND"})
        out = capsys.readouterr().out
        # Should appear as 'ALPHA_BIND, ZETA_BIND' (sorted)
        alpha_pos = out.index("ALPHA_BIND")
        zeta_pos = out.index("ZETA_BIND")
        assert alpha_pos < zeta_pos


# ============================================================================
# load_mesh_allowed_services
# ============================================================================


class TestLoadMeshAllowedServices:
    """load_mesh_allowed_services file parsing.

    Isolation note: load_mesh_allowed_services() in port_audit.py reads
    the env var PORT_AUDIT_BIND_FILE FIRST, falling back to the module
    constant DEFAULT_BIND_FILE only when the env var is unset. Tests that
    want deterministic behaviour must:
      1. Clear PORT_AUDIT_BIND_FILE (monkeypatch.delenv), OR override it
         with the target path, and
      2. Patch DEFAULT_BIND_FILE to a tmp-path target.
    Skipping either step makes the test depend on the developer's shell
    state (CI-only passes, local developer hits stale path, etc.).

    "Missing file" tests use `tmp_path / "definitely-missing-<uuid>"`
    instead of the repo-relative default, because `env.mesh-bind.local`
    is gitignored but may exist on developer machines — a local copy
    would cause a false negative on the missing-file branch.
    """

    @pytest.fixture(autouse=True)
    def _isolate_bind_file_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clear PORT_AUDIT_BIND_FILE for every test so DEFAULT_BIND_FILE
        patches actually take effect. Runs before each test in this class."""
        monkeypatch.delenv(PORT_AUDIT_BIND_FILE_ENV, raising=False)

    def test_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        """Missing bind file returns empty sets — guaranteed absent path."""
        import uuid
        missing = tmp_path / f"bind-file-{uuid.uuid4().hex}.missing"
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", missing):
            bind_file, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()
        assert unmapped == set()

    def test_parses_known_bind_var(self, tmp_path: Path) -> None:
        """NATS_BIND=0.0.0.0 maps to {'nats'} via BIND_VAR_TO_SERVICES."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert "nats" in allowed
        assert unmapped == set()

    def test_parses_multiple_known_vars(self, tmp_path: Path) -> None:
        """Multiple known BIND vars all map to their services."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=0.0.0.0\nAGENT_ZERO_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert "nats" in allowed
        assert "agent-zero" in allowed

    def test_multivalue_bind_var_maps_all_services(self, tmp_path: Path) -> None:
        """HIRAG_BIND maps to both hi-rag-gateway-v2 and hi-rag-gateway-v2-gpu."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("HIRAG_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, _ = load_mesh_allowed_services()
        assert "hi-rag-gateway-v2" in allowed
        assert "hi-rag-gateway-v2-gpu" in allowed

    def test_unknown_bind_var_goes_to_unmapped(self, tmp_path: Path) -> None:
        """Unknown *_BIND var with 0.0.0.0 goes to unmapped_vars."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("FUTURE_SERVICE_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()
        assert "FUTURE_SERVICE_BIND" in unmapped

    def test_non_0_0_0_0_value_skipped(self, tmp_path: Path) -> None:
        """BIND var set to 127.0.0.1 is skipped entirely."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=127.0.0.1\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()
        assert unmapped == set()

    def test_comments_and_blank_lines_skipped(self, tmp_path: Path) -> None:
        """Lines starting with # and empty lines are ignored."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("# This is a comment\n\n  \n# Another comment\nNATS_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert "nats" in allowed
        assert unmapped == set()

    def test_line_without_equals_skipped(self, tmp_path: Path) -> None:
        """Lines without '=' are skipped."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND 0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()

    def test_quoted_values_stripped(self, tmp_path: Path) -> None:
        """Double-quoted and single-quoted 0.0.0.0 values are parsed."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text('NATS_BIND="0.0.0.0"\nAGENT_ZERO_BIND=\'0.0.0.0\'\n')
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert "nats" in allowed
        assert "agent-zero" in allowed

    def test_env_var_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """PORT_AUDIT_BIND_FILE_ENV overrides default bind file path."""
        bind_file = tmp_path / "custom-bind.env"
        bind_file.write_text("NATS_BIND=0.0.0.0\n")
        monkeypatch.setenv(PORT_AUDIT_BIND_FILE_ENV, str(bind_file))
        try:
            _, allowed, unmapped = load_mesh_allowed_services()
            assert "nats" in allowed
        finally:
            monkeypatch.delenv(PORT_AUDIT_BIND_FILE_ENV, raising=False)

    def test_oserror_returns_empty_sets(self, tmp_path: Path) -> None:
        """OSError during file read returns empty sets (warning printed to stderr)."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("NATS_BIND=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file), \
             patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()
        assert unmapped == set()

    def test_unknown_var_not_ending_in_bind_ignored(self, tmp_path: Path) -> None:
        """Unknown var NOT ending in _BIND is not added to unmapped."""
        bind_file = tmp_path / "env.mesh-bind.local"
        bind_file.write_text("SOME_RANDOM_VAR=0.0.0.0\n")
        with patch("pmoves.tools.port_audit.DEFAULT_BIND_FILE", bind_file):
            _, allowed, unmapped = load_mesh_allowed_services()
        assert allowed == set()
        assert unmapped == set()


# ============================================================================
# main — CLI entry point
# ============================================================================


class TestMain:
    """main() fail-closed behavior and orchestration."""

    def test_returns_1_when_compose_config_fails(self) -> None:
        """main returns 1 when parse_compose_config returns None."""
        with patch("pmoves.tools.port_audit.parse_compose_config", return_value=None), \
             patch("pmoves.tools.port_audit.load_mesh_allowed_services", return_value=(Path("/x"), set(), set())):
            rc = main()
        assert rc == 1

    def test_returns_1_when_no_services_in_config(self) -> None:
        """main returns 1 when compose config has empty services."""
        with patch("pmoves.tools.port_audit.parse_compose_config", return_value={"services": {}}), \
             patch("pmoves.tools.port_audit.load_mesh_allowed_services", return_value=(Path("/x"), set(), set())):
            rc = main()
        assert rc == 1

    def test_returns_0_when_all_clean(self) -> None:
        """main returns 0 when audit passes with no violations."""
        config = {"services": {"web": {"ports": [{"host_ip": "127.0.0.1", "published": "8080", "target": "80"}]}}}
        with patch("pmoves.tools.port_audit.parse_compose_config", return_value=config), \
             patch("pmoves.tools.port_audit.load_mesh_allowed_services", return_value=(Path("/nonexistent"), set(), set())):
            rc = main()
        assert rc == 0

    def test_returns_1_when_violations_found(self) -> None:
        """main returns 1 when audit finds violations."""
        config = {"services": {"web": {"ports": [{"host_ip": "0.0.0.0", "published": "8080", "target": "80"}]}}}
        with patch("pmoves.tools.port_audit.parse_compose_config", return_value=config), \
             patch("pmoves.tools.port_audit.load_mesh_allowed_services", return_value=(Path("/nonexistent"), set(), set())):
            rc = main()
        assert rc == 1

    def test_fail_closed_prints_error_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        """Fail-closed message goes to stderr, not stdout."""
        with patch("pmoves.tools.port_audit.parse_compose_config", return_value=None), \
             patch("pmoves.tools.port_audit.load_mesh_allowed_services", return_value=(Path("/x"), set(), set())):
            main()
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "failing closed" in err


# ============================================================================
# parse_compose_config — subprocess failures (light coverage)
# ============================================================================


class TestParseComposeConfig:
    """parse_compose_config error handling."""

    def test_returns_none_on_timeout(self) -> None:
        """TimeoutExpired returns None."""
        import subprocess
        with patch("pmoves.tools.port_audit.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            result = parse_compose_config()
        assert result is None

    def test_returns_none_on_file_not_found(self) -> None:
        """FileNotFoundError (docker not installed) returns None."""
        with patch("pmoves.tools.port_audit.subprocess.run", side_effect=FileNotFoundError("docker")):
            result = parse_compose_config()
        assert result is None

    def test_returns_none_on_nonzero_exit(self) -> None:
        """docker compose config non-zero returncode returns None."""
        with patch("pmoves.tools.port_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error: missing compose file"
            result = parse_compose_config()
        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Invalid JSON from docker compose config returns None."""
        with patch("pmoves.tools.port_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "not json {{"
            result = parse_compose_config()
        assert result is None

    def test_returns_parsed_dict_on_success(self) -> None:
        """Valid JSON output is parsed and returned."""
        import json
        expected = {"services": {"web": {"ports": []}}}
        with patch("pmoves.tools.port_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps(expected)
            result = parse_compose_config()
        assert result == expected
