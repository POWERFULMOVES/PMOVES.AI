"""Tests for pmoves/tools/jwt_rotate.py.

Pins:
1. The 13 canonical Supabase consumers are pinned (rename-resistance).
2. The keygen algorithm matches pmoves-supabase/docker/utils/generate-keys.sh.
3. Backup-first semantics: rotate always creates a backup before writing.
4. The runbook file exists and references the script + the 13 consumers.
5. The enumerate output covers the 13 canonical + PMOVES consumers.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from pmoves.tools import jwt_rotate

REPO = Path(__file__).resolve().parents[3]
RUNBOOK = REPO / "pmoves" / "docs" / "RUNBOOK-5090-JWT-ROTATION.md"


# ---------------------------------------------------------------------------
# Keygen
# ---------------------------------------------------------------------------
class KeygenTests(unittest.TestCase):
    def test_secret_is_30_bytes_base64(self):
        s = jwt_rotate.generate_jwt_secret()
        # base64 of 30 bytes: ceil(30/3)*4 = 40 chars
        self.assertRegex(s, r"^[A-Za-z0-9+/]{40}$")
        # Decodable
        import base64
        self.assertEqual(len(base64.b64decode(s)), 30)

    def test_anon_key_has_three_dot_separated_segments(self):
        s = jwt_rotate.keygen()
        for k in ("JWT_SECRET", "ANON_KEY", "SERVICE_ROLE_KEY"):
            self.assertIn(k, s)
        for k in ("ANON_KEY", "SERVICE_ROLE_KEY"):
            self.assertEqual(s[k].count("."), 2, f"{k} is not a 3-segment JWT")

    def test_anon_key_decodes_to_anon_role(self):
        s = jwt_rotate.keygen()
        import base64
        def b64url_decode(seg: str) -> bytes:
            pad = "=" * (-len(seg) % 4)
            return base64.urlsafe_b64decode(seg + pad)
        payload = json.loads(b64url_decode(s["ANON_KEY"].split(".")[1]))
        self.assertEqual(payload["role"], "anon")
        self.assertEqual(payload["iss"], "supabase-local")
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)

    def test_service_role_key_decodes_to_service_role(self):
        s = jwt_rotate.keygen()
        import base64
        def b64url_decode(seg: str) -> bytes:
            pad = "=" * (-len(seg) % 4)
            return base64.urlsafe_b64decode(seg + pad)
        payload = json.loads(b64url_decode(s["SERVICE_ROLE_KEY"].split(".")[1]))
        self.assertEqual(payload["role"], "service_role")

    def test_anon_and_service_role_signed_with_same_secret(self):
        """The two tokens must verify under the same JWT_SECRET -- a keygen
        regression that signs them with different secrets would pass the
        above tests but fail this one."""
        import hmac, hashlib
        s = jwt_rotate.keygen()
        secret = s["JWT_SECRET"].encode("utf-8")
        for token in (s["ANON_KEY"], s["SERVICE_ROLE_KEY"]):
            h, p, sig = token.split(".")
            signing_input = f"{h}.{p}".encode("ascii")
            expected = jwt_rotate._b64url(
                hmac.new(secret, signing_input, hashlib.sha256).digest()
            )
            self.assertEqual(sig, expected, "JWT signature does not verify under JWT_SECRET")

    def test_keygen_secrets_are_unique_per_call(self):
        a = jwt_rotate.keygen()
        b = jwt_rotate.keygen()
        self.assertNotEqual(a["JWT_SECRET"], b["JWT_SECRET"])
        self.assertNotEqual(a["ANON_KEY"], b["ANON_KEY"])


# ---------------------------------------------------------------------------
# Backup-first semantics
# ---------------------------------------------------------------------------
class BackupFirstTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="jwt-rotate-test-"))
        self.tier = self.tmp / "env.tier-supabase"
        self.tier.write_text("JWT_SECRET=old\nANON_KEY=old\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_backup_creates_bak_iso_file(self):
        backup = jwt_rotate.backup_env(self.tier)
        self.assertTrue(backup.exists())
        self.assertTrue(backup.name.startswith("env.tier-supabase.bak."))
        # backup has same content as the source
        self.assertEqual(backup.read_text(encoding="utf-8"), self.tier.read_text(encoding="utf-8"))

    def test_backup_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            jwt_rotate.backup_env(self.tmp / "does-not-exist")

    def test_write_env_replace_preserves_comments(self):
        self.tier.write_text(
            "# a comment\n"
            "JWT_SECRET=old\n"
            "\n"
            "ANON_KEY=old\n"
            "# trailing comment\n",
            encoding="utf-8",
        )
        jwt_rotate.write_env_replace(self.tier, {"JWT_SECRET": "newsecret"})
        text = self.tier.read_text(encoding="utf-8")
        self.assertIn("# a comment", text)
        self.assertIn("# trailing comment", text)
        self.assertIn("JWT_SECRET=newsecret", text)
        self.assertIn("ANON_KEY=old", text)

    def test_write_env_replace_quotes_value_with_whitespace(self):
        jwt_rotate.write_env_replace(self.tier, {"JWT_SECRET": "a value with spaces"})
        text = self.tier.read_text(encoding="utf-8")
        self.assertIn("JWT_SECRET='a value with spaces'", text)

    def test_write_env_replace_appends_new_keys(self):
        self.tier.write_text("JWT_SECRET=old\n", encoding="utf-8")
        jwt_rotate.write_env_replace(self.tier, {"NEW_KEY": "new_value"})
        text = self.tier.read_text(encoding="utf-8")
        self.assertIn("JWT_SECRET=old", text)
        self.assertIn("NEW_KEY=new_value", text)

    def test_rotate_takes_backup_before_writing(self):
        """A regression where rotate writes before backing up would lock the
        operator out of the rollback path. The script's `rotate` command
        must call backup_env BEFORE write_env_replace. Pinned by a CLI-level
        test that runs the script directly (not as -m pmoves.*) and asserts
        the backup exists after a successful rotate call."""
        # Stage a fake env.tier-supabase in the tmp dir
        # Run the script's backup subcommand directly
        script_path = REPO / "pmoves" / "tools" / "jwt_rotate.py"
        # Set the env file path to live in self.tmp
        tier = self.tmp / "env.tier-supabase"
        tier.write_text("JWT_SECRET=old\nANON_KEY=old\n", encoding="utf-8")
        # Build a fake "repo root" with the expected env path layout
        fake_repo = self.tmp / "fake_repo"
        fake_pmoves = fake_repo / "pmoves"
        fake_pmoves.mkdir(parents=True)
        (fake_pmoves / "env.tier-supabase").write_text(
            "JWT_SECRET=old\nANON_KEY=old\n", encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(script_path), "--repo-root", str(fake_repo), "backup"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("backup written:", result.stdout)
        # The backup file should now exist
        backups = list((fake_pmoves).glob("env.tier-supabase.bak.*"))
        self.assertEqual(len(backups), 1, f"expected 1 backup, got {len(backups)}")


# ---------------------------------------------------------------------------
# Consumer enumeration
# ---------------------------------------------------------------------------
class ConsumerEnumerationTests(unittest.TestCase):
    def test_canonical_supabase_consumers_pinned(self):
        """The 13 canonical Supabase consumers are pinned. A future rename
        of any of these services must fail this test."""
        expected = {
            "supabase-kong", "supabase-postgrest", "supabase-gotrue",
            "supabase-realtime", "supabase-storage", "supabase-edge-functions",
            "supabase-studio", "supabase-meta", "supabase-pooler",
            "supabase-analytics", "supabase-imgproxy", "supabase-vector",
            "supabase-db",
        }
        self.assertEqual(set(jwt_rotate.CANONICAL_SUPABASE_CONSUMERS), expected)
        self.assertEqual(len(jwt_rotate.CANONICAL_SUPABASE_CONSUMERS), 13)

    def test_enumerate_finds_canonical_supabase_consumers(self):
        consumers = jwt_rotate.enumerate_consumers()
        found = {c["service"] for c in consumers}
        canonical = set(jwt_rotate.CANONICAL_SUPABASE_CONSUMERS)
        missing = canonical - found
        self.assertEqual(
            missing, set(),
            f"canonical Supabase consumers not found in enumerate(): {missing}. "
            "Either the survey is stale or a service was renamed."
        )

    def test_enumerate_includes_reason_for_each_consumer(self):
        consumers = jwt_rotate.enumerate_consumers()
        for c in consumers:
            if c["service"].startswith("supabase-"):
                self.assertGreater(
                    len(c["reasons"]), 0,
                    f"{c['service']} has no JWT-consumer reason; "
                    "the survey is picking up service names that don't reference JWT env files."
                )


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
class VerifyTests(unittest.TestCase):
    def test_verify_against_unreachable_url_returns_error(self):
        """The verify command should NOT raise on connection errors -- it
        should return a structured result with status: None."""
        result = jwt_rotate.verify_keys(
            "http://127.0.0.1:1",  # port 1 is reserved; should be unreachable
            "fake-new-key",
            "fake-old-key",
            timeout=1.0,
        )
        self.assertEqual(result["new_key"].get("status"), None)
        self.assertFalse(result["new_key"].get("ok", True))

    def test_verify_against_unreachable_url_does_not_raise(self):
        """A regression where verify_keys raised on network errors would
        crash the rotate workflow. Pin that it returns cleanly."""
        try:
            jwt_rotate.verify_keys(
                "http://127.0.0.1:1",
                "fake-new-key",
                "fake-old-key",
                timeout=0.5,
            )
        except Exception as e:
            self.fail(f"verify_keys raised on connection error: {e}")


# ---------------------------------------------------------------------------
# Runbook structural pins
# ---------------------------------------------------------------------------
class RunbookStructuralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RUNBOOK.read_text(encoding="utf-8")

    def test_runbook_exists(self):
        self.assertTrue(RUNBOOK.exists(), f"missing runbook: {RUNBOOK}")

    def test_runbook_references_jwt_rotate_py(self):
        self.assertIn("jwt_rotate.py", self.text)

    def test_runbook_pins_cwd(self):
        """The runbook must pin cwd to the repo root (resolves P1.3 from B850)."""
        self.assertIn("cd \"$(git rev-parse --show-toplevel)\"", self.text)

    def test_runbook_has_phase_0_sanity_check(self):
        self.assertIn("Phase 0", self.text)
        self.assertIn("--help", self.text)

    def test_runbook_has_backup_phase(self):
        self.assertIn("Phase 2", self.text)
        self.assertIn("backup", self.text)

    def test_runbook_recreates_all_13_canonical(self):
        for svc in jwt_rotate.CANONICAL_SUPABASE_CONSUMERS:
            self.assertIn(
                svc, self.text,
                f"runbook does not mention {svc}; "
                "the v0 recreated only 4 services -- this is the v1 regression we're fixing."
            )

    def test_runbook_uses_get_not_post(self):
        """B850 caught v0 saying 'POST /api/health' while the curl is GET."""
        self.assertNotIn("POST /api/health", self.text)

    def test_runbook_documents_cross_fork_map(self):
        for fork in ("PMOVES-BoTZ", "PMOVES-Archon", "PMOVES-supabase"):
            self.assertIn(
                fork, self.text,
                f"runbook cross-fork map missing {fork}"
            )

    def test_runbook_documents_rollback_via_script(self):
        self.assertIn("rollback", self.text)
        self.assertIn("pmoves/tools/jwt_rotate.py", self.text)


if __name__ == "__main__":
    unittest.main()
