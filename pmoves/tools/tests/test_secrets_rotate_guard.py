"""Tests for pmoves/tools/secrets_rotate_guard.py.

The guard exists because `secrets-rotate` mints a random_urlsafe value, which is
destructive for anything Supabase signs. These are fixture tests against a small
inline manifest - they never read the real env or the live container.
"""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from pmoves.tools import secrets_rotate_guard as guard

MANIFEST = textwrap.dedent(
    """
    secrets:
      - id: supabase_jwt_secret
        source:
          type: cgp
          label: SUPABASE_JWT_SECRET
        targets:
          - file: env.shared.generated
            key: SUPABASE_JWT_SECRET
      - id: supabase_service_key
        source:
          type: cgp
          label: SUPABASE_SERVICE_KEY
          aliases:
            - SUPABASE_SERVICE_ROLE_KEY
            - SERVICE_ROLE_KEY
        targets:
          - file: env.tier-agent
            key: SUPABASE_SERVICE_KEY
      - id: supabase_realtime_secret
        source:
          type: cgp
          label: SUPABASE_REALTIME_SECRET
          aliases:
            - JWT_SECRET
      - id: postgres_password
        source:
          type: cgp
          label: POSTGRES_PASSWORD
    """
)


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.manifest = Path(cls.tmp.name) / "secrets_manifest.yaml"
        cls.manifest.write_text(MANIFEST, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, key: str) -> int:
        return guard.check(key, self.manifest)

    def test_service_role_refused_by_alias(self):
        self.assertEqual(self.check("SERVICE_ROLE_KEY"), 3)

    def test_signing_secret_refused(self):
        self.assertEqual(self.check("SUPABASE_JWT_SECRET"), 3)

    def test_signing_alias_refused_and_cited_correctly(self):
        # JWT_SECRET is an alias of supabase_realtime_secret in this fixture, but
        # the refusal must still fire - aliasing JWT_SECRET anywhere is disqualifying.
        self.assertEqual(self.check("JWT_SECRET"), 3)

    def test_plain_password_allowed(self):
        self.assertEqual(self.check("POSTGRES_PASSWORD"), 0)

    def test_unmanaged_key_allowed_with_warning(self):
        self.assertEqual(self.check("SOMETHING_NOT_IN_MANIFEST"), 0)

    def test_missing_manifest_is_an_error_not_a_pass(self):
        self.assertEqual(guard.check("ANY", Path(tempfile.gettempdir()) / "nope.yaml"), 4)

    def test_refuse_reason_names_jwt_rotate(self):
        entries = guard.load_entries(self.manifest)
        match = guard.find_entries(entries, "SUPABASE_SERVICE_KEY")[0]
        reason = guard.refuse_reason(match)
        self.assertIsNotNone(reason)
        self.assertIn("jwt_rotate", reason)


if __name__ == "__main__":
    unittest.main()
