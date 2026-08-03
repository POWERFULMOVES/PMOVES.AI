"""Smoke + unit tests for the new supabase_auth module.

Lane 2228 refactor (2026-08-03): the Google OAuth refresh_token now lives in
`auth.identities` for the `darkxside@pmoves.ai` user, managed by Supabase.
This module reads it via the Supabase Management API (admin endpoint with the
service_role key).

These tests:
  1. Mock httpx.get to verify the request shape (URL, headers, email query)
  2. Verify the response parsing handles missing user, missing identity, success
  3. Verify the SERVICE_ROLE_KEY preference (Supabase-secrets-sync name > legacy)
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make the parent package importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from supabase_auth import get_google_identity, get_provider_refresh_token  # noqa: E402


class GetGoogleIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SUPABASE_URL"] = "https://test.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
        # Clear the legacy name so we test the canonical path.
        os.environ.pop("SERVICE_ROLE_KEY", None)

    def tearDown(self) -> None:
        for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY"):
            os.environ.pop(var, None)

    def test_user_not_found_returns_none(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"users": []}
        with patch("supabase_auth.httpx.get", return_value=fake_response):
            result = get_google_identity("nonexistent@pmoves.ai")
        self.assertIsNone(result)

    def test_user_with_no_google_identity_returns_none(self) -> None:
        """User exists but signed in via password (no Google identity yet)."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "users": [
                {
                    "id": "user-uuid",
                    "email": "darkxside@pmoves.ai",
                    "identities": [
                        {"provider": "email", "identity_data": {}},
                    ],
                }
            ]
        }
        with patch("supabase_auth.httpx.get", return_value=fake_response):
            result = get_google_identity("darkxside@pmoves.ai")
        self.assertIsNone(result)

    def test_user_with_google_identity_returns_identity(self) -> None:
        """Happy path: user has a Google identity with provider_refresh_token."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "users": [
                {
                    "id": "user-uuid",
                    "email": "darkxside@pmoves.ai",
                    "identities": [
                        {
                            "provider": "google",
                            "identity_id": "google-uuid",
                            "identity_data": {
                                "provider_token": "ya29.current-access",
                                "provider_refresh_token": "1//refresh-token-here",
                                "email": "cataclysmstudios@gmail.com",
                                "sub": "google-sub-id",
                            },
                        },
                    ],
                }
            ]
        }
        with patch("supabase_auth.httpx.get", return_value=fake_response) as mock_get:
            result = get_google_identity("darkxside@pmoves.ai")
        self.assertIsNotNone(result)
        self.assertEqual(result["provider"], "google")
        self.assertEqual(
            result["identity_data"]["provider_refresh_token"],
            "1//refresh-token-here",
        )
        # Verify the request shape
        call_args = mock_get.call_args
        # The URL is passed as the first positional arg without query string
        # (the email is passed via params= so httpx percent-encodes it).
        self.assertEqual(call_args.args[0], "https://test.supabase.co/auth/v1/admin/users")
        self.assertEqual(
            call_args.kwargs["params"],
            {"email": "darkxside@pmoves.ai"},
            "email must be passed via params= so httpx percent-encodes it",
        )
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"], "Bearer test-service-role-key"
        )

    def test_legacy_service_role_key_fallback(self) -> None:
        """If SUPABASE_SERVICE_ROLE_KEY is unset but SERVICE_ROLE_KEY is set, use the legacy name."""
        os.environ.pop("SUPABASE_SERVICE_ROLE_KEY")
        os.environ["SERVICE_ROLE_KEY"] = "legacy-service-role-key"
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"users": []}
        with patch("supabase_auth.httpx.get", return_value=fake_response) as mock_get:
            get_google_identity("darkxside@pmoves.ai")
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer legacy-service-role-key",
        )

    def test_admin_endpoint_failure_logs_and_returns_none(self) -> None:
        """5xx from the Supabase admin endpoint should not crash the cookie refresh."""
        fake_response = MagicMock()
        fake_response.status_code = 500
        fake_response.text = "internal server error"
        with patch("supabase_auth.httpx.get", return_value=fake_response):
            result = get_google_identity("darkxside@pmoves.ai")
        self.assertIsNone(result)


class GetProviderRefreshTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SUPABASE_URL"] = "https://test.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-key"

    def test_returns_none_when_no_identity(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"users": []}
        with patch("supabase_auth.httpx.get", return_value=fake_response):
            result = get_provider_refresh_token()
        self.assertIsNone(result)

    def test_returns_refresh_token_from_identity(self) -> None:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "users": [
                {
                    "identities": [
                        {
                            "provider": "google",
                            "identity_data": {
                                "provider_refresh_token": "1//expected-token"
                            },
                        }
                    ]
                }
            ]
        }
        with patch("supabase_auth.httpx.get", return_value=fake_response):
            result = get_provider_refresh_token()
        self.assertEqual(result, "1//expected-token")


if __name__ == "__main__":
    unittest.main(verbosity=2)
