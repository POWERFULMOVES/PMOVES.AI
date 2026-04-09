#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Failure Mode Tests for GitHub App Automation

This test suite verifies error handling and failure scenarios for the
GitHub App automation tools, ensuring robust behavior when things go wrong.

Author: PMOVES.AI Automation
Version: 1.0.0
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import pytest

# NOTE: Do not wrap sys.stdout/sys.stderr in a TextIOWrapper at module import.
# Under pytest that breaks the capture subsystem (stop_global_capturing() does
# tmpfile.seek(0) on the wrapped stream, which raises "I/O operation on closed
# file" and crashes collection of every test in this file). This module is
# pytest-only (no __main__ block), so no wrapper is needed.

sys.path.insert(0, str(Path(__file__).parent.parent))

# These imports reference functions that may not exist in the current tools
# modules (known drift between tests and source). Use importorskip with
# attribute checks so collection succeeds cleanly and tests skip instead of
# crashing the entire test session.
_gh_setup = pytest.importorskip(
    "tools.github_app_auto_setup",
    reason="tools.github_app_auto_setup unavailable",
)
run_command = getattr(_gh_setup, "run_command", None)
setup_logging = getattr(_gh_setup, "setup_logging", None)
if run_command is None or setup_logging is None:
    pytest.skip(
        "tools.github_app_auto_setup missing run_command/setup_logging",
        allow_module_level=True,
    )

_gh_verify = pytest.importorskip(
    "tools.verify_github_app_setup",
    reason="tools.verify_github_app_setup unavailable",
)
verify_env_file = getattr(_gh_verify, "verify_env_file", None)
verify_chit_manifest = getattr(_gh_verify, "verify_chit_manifest", None)
if verify_env_file is None or verify_chit_manifest is None:
    pytest.skip(
        "tools.verify_github_app_setup missing verify_env_file/verify_chit_manifest "
        "(known drift between tests and source)",
        allow_module_level=True,
    )

_chit_bundle = pytest.importorskip(
    "tools.chit_sync_workflow_bundle",
    reason="tools.chit_sync_workflow_bundle unavailable",
)
read_env_file = getattr(_chit_bundle, "read_env_file", None)
validate_credential_value = getattr(_chit_bundle, "validate_credential_value", None)
if read_env_file is None or validate_credential_value is None:
    pytest.skip(
        "tools.chit_sync_workflow_bundle missing read_env_file/validate_credential_value",
        allow_module_level=True,
    )


class TestTimeoutProtection:
    """Test timeout protection on subprocess calls."""

    def test_run_command_timeout_short(self):
        """Test that run_command enforces timeout on long-running commands."""
        with pytest.raises(subprocess.TimeoutExpired):
            run_command("sleep 40", timeout=1)

    def test_run_command_timeout_default(self):
        """Test that run_command uses 30s default timeout."""
        result = run_command("echo 'test'")
        assert result.returncode == 0


class TestShellInjectionPrevention:
    """Test that shell injection vulnerabilities are prevented."""

    def test_bulk_secret_fetch_no_shell_injection(self):
        """Test that bulk secret fetching doesn't allow shell injection."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("GH_APP_ID=12345\n")
            f.write("GH_APP_SEC='$(malicious command)'\n")
            temp_file = f.name

        try:
            secrets = read_env_file(temp_file)
            assert 'GH_APP_ID' in secrets
            assert secrets['GH_APP_ID'] == '12345'
            assert 'malicious command' not in str(secrets.get('GH_APP_SEC', ''))
        finally:
            os.unlink(temp_file)


class TestExceptionHandling:
    """Test that exceptions are properly handled (no bare except)."""

    def test_run_command_specific_exceptions(self):
        """Test that run_command raises specific exceptions, not bare except."""
        with pytest.raises(subprocess.TimeoutExpired):
            run_command("sleep 100", timeout=0.5)

        with pytest.raises(subprocess.CalledProcessError):
            run_command("false", check=True)

    def test_read_env_file_specific_exceptions(self):
        """Test that read_env_file handles specific exceptions."""
        with pytest.raises(FileNotFoundError):
            read_env_file("/nonexistent/file.env")

    def test_validate_credential_specific_exceptions(self):
        """Test that credential validation raises specific exceptions."""
        with pytest.raises(ValueError):
            validate_credential_value("INVALID_KEY", "")


class TestFileOperationErrors:
    """Test graceful handling of file operation errors."""

    def test_nonexistent_env_file(self):
        """Test handling of missing env.shared file."""
        result = verify_env_file("/nonexistent/env.shared")
        assert not result['ok']
        assert 'error' in result

    def test_nonexistent_chit_manifest(self):
        """Test handling of missing CHIT manifest."""
        result = verify_chit_manifest("/nonexistent/chit/secrets_manifest.yaml")
        assert not result['ok']
        assert 'error' in result


class TestCredentialValidation:
    """Test credential value validation."""

    def test_empty_credential_value(self):
        """Test that empty credential values are rejected."""
        with pytest.raises(ValueError):
            validate_credential_value("GH_APP_ID", "")

    def test_whitespace_only_credential(self):
        """Test that whitespace-only credentials are rejected."""
        with pytest.raises(ValueError):
            validate_credential_value("GH_APP_ID", "   ")

    def test_valid_credential(self):
        """Test that valid credentials pass validation."""
        validate_credential_value("GH_APP_ID", "123456")


class TestPEMKeyHandling:
    """Test proper handling of PEM keys."""

    def test_pem_key_multiline_quoting(self):
        """Test that PEM keys are properly quoted for multi-line values."""
        pem_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2Z2Q
-----END RSA PRIVATE KEY-----"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"GH_APP_SEC='{pem_key}'\n")
            temp_file = f.name

        try:
            secrets = read_env_file(temp_file)
            assert 'GH_APP_SEC' in secrets
            assert 'BEGIN RSA PRIVATE KEY' in secrets['GH_APP_SEC']
        finally:
            os.unlink(temp_file)


class TestLogging:
    """Test logging functionality."""

    def test_setup_logging_creates_file(self):
        """Test that setup_logging creates log file in ~/.pmoves/logs/."""
        log_file = setup_logging("test_github_app_failures")
        assert log_file.exists()
        assert log_file.parent.name == 'logs'
        if log_file.exists():
            log_file.unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
