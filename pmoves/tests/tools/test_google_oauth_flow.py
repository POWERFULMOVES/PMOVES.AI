"""Unit tests for the Google OAuth acquire helpers."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pmoves.tools.yt_oauth_flow as oauth


class TestBuildFlow(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
