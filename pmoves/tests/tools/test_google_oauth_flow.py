"""Unit tests for the Google OAuth acquire helpers."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pmoves.tools.yt_oauth_flow as oauth


class TestBuildFlow(unittest.TestCase):
    # _build_flow is a thin wrapper over google_auth_oauthlib.InstalledAppFlow
    # and exits when the library is absent, so these assertions cannot be
    # measured without it. It is a [dev] optional dependency
    # (pmoves/pyproject.toml) that CI installs via .github/requirements-tests.txt
    # for merge-gate's pytest_ratchet run, so CI still executes these; only an
    # interpreter without the dev extra skips them.
    def setUp(self):
        pytest.importorskip(
            "google_auth_oauthlib",
            reason="google-auth-oauthlib ([dev] extra) not installed; "
            "_build_flow requires it",
        )

    def test_build_flow_sets_client_and_scopes(self):
        flow = oauth._build_flow(
            "cid", "csec", "https://www.googleapis.com/auth/youtube.readonly"
        )
        self.assertEqual(flow.client_config["client_id"], "cid")
        self.assertEqual(flow.client_config["client_secret"], "csec")
        self.assertIn(
            "https://www.googleapis.com/auth/youtube.readonly",
            flow.oauth2session.scope,
        )

    def test_build_flow_splits_multiple_scopes(self):
        flow = oauth._build_flow("cid", "csec", "scope-a scope-b")
        self.assertIn("scope-a", flow.oauth2session.scope)
        self.assertIn("scope-b", flow.oauth2session.scope)


class TestClientCreds(unittest.TestCase):
    def test_prefers_google_oauth_vars(self):
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "desktop-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "desktop-secret",
            "GOOGLE_CLIENT_ID": "ws-id",
            "GOOGLE_CLIENT_SECRET": "ws-secret",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_ID": "legacy-id",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET": "legacy-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._client_creds(), ("desktop-id", "desktop-secret"))

    def test_falls_back_to_workspace_google_client(self):
        # GOOGLE_CLIENT_ID/SECRET = the existing google-workspace MCP Desktop
        # client; reuse it before the channel-monitor legacy names.
        env = {
            "GOOGLE_CLIENT_ID": "ws-id",
            "GOOGLE_CLIENT_SECRET": "ws-secret",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_ID": "legacy-id",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET": "legacy-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._client_creds(), ("ws-id", "ws-secret"))

    def test_falls_back_to_channel_monitor_vars(self):
        env = {
            "CHANNEL_MONITOR_GOOGLE_CLIENT_ID": "legacy-id",
            "CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET": "legacy-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._client_creds(), ("legacy-id", "legacy-secret"))

    def test_exits_when_neither_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                oauth._client_creds()


class TestServiceRoleKey(unittest.TestCase):
    def test_prefers_supabase_service_role_key(self):
        # Precedence was deliberately swapped in f2f6d28c4 (#2333): the
        # secrets-sync name is refreshed by the funnel every run, while the
        # legacy SERVICE_ROLE_KEY was observed carrying a key signed by a
        # retired JWT secret (PostgREST 401 on upsert).
        env = {"SERVICE_ROLE_KEY": "srk", "SUPABASE_SERVICE_ROLE_KEY": "supa-srk"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._service_role_key(), "supa-srk")

    def test_falls_back_to_legacy_service_role_key(self):
        env = {"SERVICE_ROLE_KEY": "srk"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(oauth._service_role_key(), "srk")

    def test_exits_when_neither_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                oauth._service_role_key()


class TestArgParsing(unittest.TestCase):
    def test_defaults(self):
        ns = oauth._parse_args(["status"])
        self.assertEqual(ns.command, "status")
        self.assertEqual(ns.user_id, oauth.DEFAULT_USER_ID)
        self.assertEqual(ns.scopes, oauth.OAUTH_SCOPES)

    def test_overrides(self):
        ns = oauth._parse_args(["auth", "--user-id", "u2", "--scopes", "s1 s2"])
        self.assertEqual(ns.user_id, "u2")
        self.assertEqual(ns.scopes, "s1 s2")


class TestRequireEncryption(unittest.TestCase):
    """Fail-closed guard: never silently persist a plaintext OAuth refresh token."""

    def test_passes_when_fernet_present(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            oauth._require_encryption(object())  # no exception, no opt-in needed

    def test_aborts_when_fernet_none_and_no_optin(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                oauth._require_encryption(None)

    def test_allows_plaintext_with_explicit_optin(self):
        with mock.patch.dict(os.environ, {"YT_OAUTH_ALLOW_PLAINTEXT": "1"}, clear=True):
            oauth._require_encryption(None)  # opted in → warns but does not abort

    def test_optin_is_falsey_by_default(self):
        with mock.patch.dict(os.environ, {"YT_OAUTH_ALLOW_PLAINTEXT": "0"}, clear=True):
            self.assertFalse(oauth._allow_plaintext())
        with mock.patch.dict(os.environ, {"YT_OAUTH_ALLOW_PLAINTEXT": "yes"}, clear=True):
            self.assertTrue(oauth._allow_plaintext())


if __name__ == "__main__":
    unittest.main()
