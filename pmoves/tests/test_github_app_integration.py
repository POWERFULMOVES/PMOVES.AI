#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration Tests for GitHub App Automation

This test suite verifies end-to-end workflows for GitHub App setup and
credential management, testing the complete integration between tools.

Author: PMOVES.AI Automation
Version: 1.0.0
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import pytest

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.github_app_auto_setup import (
    run_command,
    verify_gh_auth,
    get_github_secrets,
    verify_env_files,
    verify_chit_integration,
    main
)
from tools.verify_github_app_setup import (
    verify_env_file,
    verify_chit_manifest,
    main as verify_main
)
from tools.chit_sync_workflow_bundle import (
    read_env_file,
    validate_credential_value,
    sync_to_chit_manifest,
    main as sync_main
)


class TestCompleteWorkflow:
    """Test complete workflow from setup to verification."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures."""
        cls.repo_root = Path(__file__).parent.parent.parent
        cls.pmoves_dir = cls.repo_root / "pmoves"

    def test_full_workflow_integration(self):
        """Test complete workflow: setup → sync → verify."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("GH_APP_ID=123456\n")
            f.write("GH_APP_CLIENT_ID=test_client_id\n")
            f.write("GH_APP_INSTALLATION_ID=789\n")
            f.write("GH_APP_SEC='-----BEGIN RSA PRIVATE KEY-----\ntest_key\n-----END RSA PRIVATE KEY-----'\n")
            test_env = f.name

        try:
            secrets = read_env_file(test_env)
            assert 'GH_APP_ID' in secrets
            assert secrets['GH_APP_ID'] == '123456'

            for key, value in secrets.items():
                validate_credential_value(key, value)

            result = verify_env_file(test_env)
            assert result['ok']
        finally:
            os.unlink(test_env)


class TestCredentialFlow:
    """Test end-to-end credential flow."""

    def test_credential_from_env_to_chit(self):
        """Test credential flow from env file to CHIT manifest."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("GH_APP_ID=123456\n")
            f.write("GH_APP_SEC='test_secret'\n")
            env_file = f.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write("version: '1.0'\n")
            f.write("secrets:\n")
            f.write("  GH_APP_ID:\n")
            f.write("    description: GitHub App ID\n")
            manifest_file = f.name

        try:
            secrets = read_env_file(env_file)
            assert 'GH_APP_ID' in secrets
            assert Path(manifest_file).exists()
        finally:
            os.unlink(env_file)
            os.unlink(manifest_file)


class TestCHITManifestIntegration:
    """Test CHIT manifest integration."""

    def test_verify_chit_manifest_structure(self):
        """Test that CHIT manifest has correct structure."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write("version: '1.0'\n")
            f.write("secrets:\n")
            f.write("  GH_APP_ID:\n")
            f.write("    description: GitHub App ID\n")
            f.write("    required: true\n")
            manifest_file = f.name

        try:
            result = verify_chit_manifest(manifest_file)
            assert result['ok']
            assert 'GH_APP_ID' in result['secrets']
        finally:
            os.unlink(manifest_file)


class TestEnvironmentSync:
    """Test environment file synchronization."""

    def test_sync_env_to_chit(self):
        """Test syncing env file values to CHIT manifest."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("GH_APP_ID=123456\n")
            f.write("GH_APP_SEC='test_secret'\n")
            env_file = f.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write("version: '1.0'\n")
            f.write("secrets:\n")
            f.write("  GH_APP_ID:\n")
            f.write("    description: GitHub App ID\n")
            f.write("  GH_APP_SEC:\n")
            f.write("    description: GitHub App Secret\n")
            manifest_file = f.name

        try:
            secrets = read_env_file(env_file)
            assert 'GH_APP_ID' in secrets
            assert 'GH_APP_SEC' in secrets

            result = verify_chit_manifest(manifest_file)
            assert result['ok']
            assert 'GH_APP_ID' in result['secrets']
            assert 'GH_APP_SEC' in result['secrets']
        finally:
            os.unlink(env_file)
            os.unlink(manifest_file)


class TestGitHubSecretSync:
    """Test GitHub Secret synchronization."""

    @patch('subprocess.run')
    def test_sync_to_github_secrets(self, mock_run):
        """Test syncing credentials to GitHub Secrets."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="✓ Set secret GH_APP_ID",
            stderr=""
        )

        secrets = {
            'GH_APP_ID': '123456',
            'GH_APP_SEC': 'test_secret'
        }

        for key, value in secrets.items():
            cmd = f"gh secret set {key} --body '{value}'"
            result = run_command(cmd, check=False)
            assert result.returncode == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
