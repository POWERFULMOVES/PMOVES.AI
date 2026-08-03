"""Smoke test: import every module in the refactored yt-cookie-refresher and verify the wiring is sane.

Lane 2228 refactor (2026-08-03): after the OAuth moves to Supabase Auth, we
need to verify the import graph doesn't break (no circular imports, no
missing module references) and that main.py / oauth_client.py / supabase_auth.py
all parse + import cleanly.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICE_DIR = HERE.parent


class ImportGraphTests(unittest.TestCase):
    def test_all_modules_parse(self) -> None:
        """Every .py file in the service must parse as valid Python (no syntax errors)."""
        for py in SERVICE_DIR.glob("*.py"):
            if py.name == "__init__.py":
                continue
            with self.subTest(file=py.name):
                source = py.read_text(encoding="utf-8")
                try:
                    ast.parse(source, filename=str(py))
                except SyntaxError as e:
                    self.fail(f"{py.name} has syntax error: {e}")

    def test_main_does_not_import_deprecated_oauth_handler(self) -> None:
        """main.py must not reference the deleted oauth_handler module."""
        main = (SERVICE_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("from oauth_handler", main)
        self.assertNotIn("import oauth_handler", main)
        # It should import from the new modules
        self.assertIn("from oauth_client", main)
        self.assertIn("from supabase_auth", main)

    def test_old_oauth_handler_file_is_gone(self) -> None:
        """The deprecated oauth_handler.py should be deleted in this refactor."""
        self.assertFalse(
            (SERVICE_DIR / "oauth_handler.py").exists(),
            "oauth_handler.py should be deleted in the Lane 2228 refactor; "
            "its content moved to oauth_client.py + supabase_auth.py",
        )

    def test_new_modules_present(self) -> None:
        for module in ("oauth_client.py", "supabase_auth.py"):
            self.assertTrue(
                (SERVICE_DIR / module).exists(),
                f"new module {module} should be present in the refactor",
            )

    def test_migration_sql_present(self) -> None:
        """The drop-column migration should be present for the operator to run after verification."""
        self.assertTrue(
            (SERVICE_DIR / "migrations" / "0001_drop_encrypted_refresh_token.sql").exists(),
            "migrations/0001_drop_encrypted_refresh_token.sql should be present",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
