"""Smoke + unit tests for the refactored oauth_client module.

Lane 2228 refactor (2026-08-03): the old `oauth_handler.py` (~50 lines of direct
httpx.post to oauth2.googleapis.com) is replaced with this focused 30-line
module. We still need a direct OAuth2 client (Supabase does not auto-refresh
Google provider_token server-side), but the *storage* of the refresh_token
moves to Supabase Auth identities.

These tests:
  1. Mock httpx.post to verify the request shape (URL, form data, headers)
  2. Verify the response parsing handles both success and error paths
  3. Verify the missing-env-var guard fires when CHANNEL_MONITOR_GOOGLE_* is unset
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make the parent package importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from oauth_client import refresh_provider_token  # noqa: E402


class RefreshProviderTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        # Required env vars for the Google OAuth2 client.
        os.environ["CHANNEL_MONITOR_GOOGLE_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
        os.environ["CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET"] = "test-client-secret"

    def tearDown(self) -> None:
        os.environ.pop("CHANNEL_MONITOR_GOOGLE_CLIENT_ID", None)
        os.environ.pop("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET", None)

    def test_missing_client_id_raises(self) -> None:
        """Guard: refuse to call Google if CHANNEL_MONITOR_GOOGLE_CLIENT_ID is unset."""
        os.environ.pop("CHANNEL_MONITOR_GOOGLE_CLIENT_ID")
        with self.assertRaises(RuntimeError) as cm:
            refresh_provider_token("fake-refresh-token")
        self.assertIn("missing CHANNEL_MONITOR_GOOGLE_CLIENT_ID", str(cm.exception))

    def test_missing_client_secret_raises(self) -> None:
        """Guard: refuse to call Google if CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET is unset."""
        os.environ.pop("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET")
        with self.assertRaises(RuntimeError) as cm:
            refresh_provider_token("fake-refresh-token")
        self.assertIn("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET", str(cm.exception))

    def test_successful_refresh(self) -> None:
        """Happy path: 200 response with access_token + expires_in returns (token, expires_at)."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "access_token": "ya29.fresh-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/youtube",
        }
        with patch("oauth_client.httpx.post", return_value=fake_response) as mock_post:
            token, expires_at = refresh_provider_token("fake-refresh-token")
        self.assertEqual(token, "ya29.fresh-access-token")
        self.assertIsInstance(expires_at, datetime)
        self.assertGreater(expires_at, datetime.now(timezone.utc))
        # Verify the request shape
        call_args = mock_post.call_args
        self.assertEqual(call_args.args[0], "https://oauth2.googleapis.com/token")
        self.assertEqual(call_args.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(call_args.kwargs["data"]["refresh_token"], "fake-refresh-token")
        self.assertEqual(
            call_args.kwargs["data"]["client_id"],
            "test-client-id.apps.googleusercontent.com",
        )

    def test_invalid_grant_error_preserved(self) -> None:
        """Google's 400 invalid_grant must surface as RuntimeError with the structured error."""
        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked.",
        }
        with patch("oauth_client.httpx.post", return_value=fake_response):
            with self.assertRaises(RuntimeError) as cm:
                refresh_provider_token("expired-token")
        err_msg = str(cm.exception)
        self.assertIn("invalid_grant", err_msg)
        self.assertIn("expired or revoked", err_msg)

    def test_http_500_error_includes_status_code(self) -> None:
        """Network errors (5xx) get surfaced with the status code in the message."""
        fake_response = MagicMock()
        fake_response.status_code = 503
        fake_response.json.return_value = {}  # no JSON body
        with patch("oauth_client.httpx.post", return_value=fake_response):
            with self.assertRaises(RuntimeError) as cm:
                refresh_provider_token("fake-refresh-token")
        self.assertIn("http_503", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
