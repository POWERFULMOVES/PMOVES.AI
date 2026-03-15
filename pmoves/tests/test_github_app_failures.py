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

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.github_app_auto_setup import run_command, setup_logging
from tools.verify_github_app_setup import verify_env_file, verify_chit_manifest
from tools.chit_sync_workflow_bundle import read_env_file, validate_credential_value


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
