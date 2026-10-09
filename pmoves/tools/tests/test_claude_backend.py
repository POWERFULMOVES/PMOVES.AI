"""Unit tests for pmoves.tools.claude_backend.

Six test classes pin:
1. ParseBackendFlagTests — argv parsing
2. AutoDetectHijackTests — ANTHROPIC_BASE_URL host detection
3. ApplyBackendTests — env mutation per backend
4. BackupRestoreTests — backup/restore semantics
5. TemplateTests — anthropic.json / minimax.json shape
6. TwinParityTests — bash + PowerShell launcher surface parity

Mirror docs: pmoves/docs/AGENTS/claude_backend_switch_LEARNINGS.md
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from pmoves.tools import claude_backend as cb


REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_PMOVES_SH = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh"
CLAUDE_PMOVES_PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"
TEMPLATES_DIR = REPO_ROOT / "pmoves" / "configs" / "claude_settings"


# ---------------------------------------------------------------------------
# 1. ParseBackendFlagTests
# ---------------------------------------------------------------------------
class ParseBackendFlagTests(unittest.TestCase):
    def test_parses_equals_form(self):
        self.assertEqual(cb.parse_backend_argv(["--backend=anthropic", "rest"]), "anthropic")

    def test_parses_space_form(self):
        self.assertEqual(cb.parse_backend_argv(["--backend", "anthropic", "rest"]), "anthropic")

    def test_lowercases_value(self):
        self.assertEqual(cb.parse_backend_argv(["--backend=ANTHROPIC"]), "anthropic")
        self.assertEqual(cb.parse_backend_argv(["--backend", "Auto"]), "auto")

    def test_rejects_invalid_value(self):
        with self.assertRaises(ValueError) as cm:
            cb.parse_backend_argv(["--backend=garbage"])
        self.assertIn("garbage", str(cm.exception))
        self.assertIn("auto", str(cm.exception))
        self.assertIn("anthropic", str(cm.exception))
        self.assertIn("minimax", str(cm.exception))

    def test_rejects_space_form_with_no_value(self):
        with self.assertRaises(ValueError):
            cb.parse_backend_argv(["--backend"])

    def test_no_flag_returns_none(self):
        self.assertIsNone(cb.parse_backend_argv(["hello", "world"]))
        self.assertIsNone(cb.parse_backend_argv([]))


# ---------------------------------------------------------------------------
# 2. AutoDetectHijackTests
# ---------------------------------------------------------------------------
class AutoDetectHijackTests(unittest.TestCase):
    def test_anthropic_api_host_not_hijacked(self):
        self.assertFalse(cb.is_hijacked({"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}))

    def test_anthropic_api_host_with_path_not_hijacked(self):
        self.assertFalse(
            cb.is_hijacked({"ANTHROPIC_BASE_URL": "https://api.anthropic.com/v1/messages"})
        )

    def test_empty_base_url_not_hijacked(self):
        self.assertFalse(cb.is_hijacked({}))
        self.assertFalse(cb.is_hijacked({"ANTHROPIC_BASE_URL": ""}))

    def test_minimax_chat_hijacked(self):
        self.assertTrue(cb.is_hijacked({"ANTHROPIC_BASE_URL": "https://api.minimax.chat/v1"}))

    def test_host_comparison_case_insensitive(self):
        self.assertTrue(cb.is_hijacked({"ANTHROPIC_BASE_URL": "https://API.Minimax.AI/v1"}))

    def test_local_proxy_hijacked(self):
        # The plan deliberately treats any non-Anthropic host as hijack; the
        # operator can override with --backend=minimax when running a LiteLLM
        # proxy.
        self.assertTrue(cb.is_hijacked({"ANTHROPIC_BASE_URL": "http://10.0.0.5:8080/v1"}))


# ---------------------------------------------------------------------------
# 3. ApplyBackendTests
# ---------------------------------------------------------------------------
class ApplyBackendTests(unittest.TestCase):
    def _fresh_env(self, base: str = "", model: str = "") -> dict:
        e: dict = {}
        if base:
            e["ANTHROPIC_BASE_URL"] = base
        if model:
            e["ANTHROPIC_MODEL"] = model
        return e

    def test_auto_hijack_strips_and_preserves(self):
        e = {
            "ANTHROPIC_BASE_URL": "https://api.minimax.chat/v1",
            "ANTHROPIC_MODEL": "MiniMax-M3[1m]",
        }
        stripped, warn = cb.apply_backend("auto", e)
        self.assertIn("ANTHROPIC_BASE_URL", stripped)
        self.assertIn("ANTHROPIC_MODEL", stripped)
        self.assertNotIn("ANTHROPIC_BASE_URL", e)
        self.assertEqual(e["PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL"], "https://api.minimax.chat/v1")
        self.assertEqual(e["PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_MODEL"], "MiniMax-M3[1m]")
        self.assertIsNotNone(warn)
        self.assertIn(cb.WARN_PHRASE, warn)

    def test_auto_clean_passes_through(self):
        e = self._fresh_env(base="https://api.anthropic.com")
        stripped, warn = cb.apply_backend("auto", e)
        self.assertEqual(stripped, [])
        self.assertIsNone(warn)
        self.assertEqual(e["ANTHROPIC_BASE_URL"], "https://api.anthropic.com")

    def test_auto_no_base_url_with_model_only_passes_through(self):
        # Plan Risk #2: model-only override is the operator's prerogative.
        e = self._fresh_env(model="claude-opus-4-5")
        stripped, warn = cb.apply_backend("auto", e)
        self.assertEqual(stripped, [])
        self.assertIsNone(warn)
        self.assertEqual(e["ANTHROPIC_MODEL"], "claude-opus-4-5")

    def test_minimax_preserves_everything(self):
        e = {
            "ANTHROPIC_BASE_URL": "https://api.minimax.chat/v1",
            "ANTHROPIC_MODEL": "MiniMax-M3[1m]",
        }
        stripped, warn = cb.apply_backend("minimax", e)
        self.assertEqual(stripped, [])
        self.assertIsNone(warn)
        self.assertEqual(e["ANTHROPIC_BASE_URL"], "https://api.minimax.chat/v1")
        self.assertEqual(e["ANTHROPIC_MODEL"], "MiniMax-M3[1m]")
        # No prefixed copy under the strip prefix.
        self.assertFalse(any(k.startswith(cb.STRIPPED_PREFIX) for k in e))

    def test_anthropic_forces_strip_even_when_clean(self):
        e = self._fresh_env(base="https://api.anthropic.com")
        stripped, warn = cb.apply_backend("anthropic", e)
        self.assertIn("ANTHROPIC_BASE_URL", stripped)
        self.assertIsNotNone(warn)
        self.assertNotIn("ANTHROPIC_BASE_URL", e)
        self.assertEqual(
            e["PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL"], "https://api.anthropic.com"
        )

    def test_apply_backend_rejects_unknown(self):
        with self.assertRaises(ValueError):
            cb.apply_backend("garbage", {})


# ---------------------------------------------------------------------------
# 4. BackupRestoreTests
# ---------------------------------------------------------------------------
class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="claude-backend-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_creates_backup_before_write(self):
        target = Path(self.tmp) / "settings.json"
        original = {"env": {"MCP_TIMEOUT": "120000"}, "model": "fable[1m]"}
        target.write_text(json.dumps(original), encoding="utf-8")
        backup = cb.write_settings_atomic(target, {"env": {}, "model": "anthropic-direct"}, backup=True)
        self.assertIsNotNone(backup)
        self.assertTrue(backup.exists())
        self.assertTrue(backup.name.startswith("settings.json.bak."))
        # backup holds the original
        backup_data = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual(backup_data["model"], "fable[1m]")
        # target holds the new data
        new_data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(new_data["model"], "anthropic-direct")

    def test_set_with_no_existing_file_no_backup(self):
        target = Path(self.tmp) / "settings.json"
        backup = cb.write_settings_atomic(target, {"env": {}}, backup=True)
        self.assertIsNone(backup)
        self.assertTrue(target.exists())

    def test_idempotency_two_consecutive_sets_create_two_backups(self):
        target = Path(self.tmp) / "settings.json"
        target.write_text(json.dumps({"v": 1}), encoding="utf-8")
        b1 = cb.write_settings_atomic(target, {"v": 2}, backup=True)
        b2 = cb.write_settings_atomic(target, {"v": 3}, backup=True)
        self.assertIsNotNone(b1)
        self.assertIsNotNone(b2)
        self.assertNotEqual(b1, b2)
        self.assertEqual(json.loads(b1.read_text(encoding="utf-8"))["v"], 1)
        self.assertEqual(json.loads(b2.read_text(encoding="utf-8"))["v"], 2)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["v"], 3)

    def test_restore_from_backup_replaces_target(self):
        target = Path(self.tmp) / "settings.json"
        target.write_text(json.dumps({"v": "current"}), encoding="utf-8")
        backup = target.with_name("settings.json.bak.2026-09-10T09-44-30Z")
        backup.write_text(json.dumps({"v": "old"}), encoding="utf-8")
        written = cb.restore_from_backup(backup, target)
        self.assertEqual(written, target)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["v"], "old")

    def test_restore_missing_backup_raises(self):
        target = Path(self.tmp) / "settings.json"
        target.write_text("{}", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            cb.restore_from_backup(Path(self.tmp) / "missing.bak", target)

    def test_list_backups_newest_first(self):
        target_dir = Path(self.tmp)
        files = [
            "settings.json.bak.2026-09-10T09-44-30Z",
            "settings.json.bak.2026-09-15T12-00-00Z",
            "settings.json.bak.2026-09-25T13-21-34Z",
            "unrelated.txt",
        ]
        for name in files:
            (target_dir / name).write_text("{}", encoding="utf-8")
        backups = cb.list_backups(target_dir)
        names = [b.name for b in backups]
        self.assertEqual(
            names,
            [
                "settings.json.bak.2026-09-25T13-21-34Z",
                "settings.json.bak.2026-09-15T12-00-00Z",
                "settings.json.bak.2026-09-10T09-44-30Z",
            ],
        )

    def test_backup_name_format(self):
        # backup_name() returns YYYY-MM-DDTHH-MM-SSZ (filesystem-safe).
        name = cb.backup_name()
        self.assertRegex(name, r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")


# ---------------------------------------------------------------------------
# 5. TemplateTests
# ---------------------------------------------------------------------------
class TemplateTests(unittest.TestCase):
    def test_anthropic_template_exists_and_parses(self):
        path = TEMPLATES_DIR / "anthropic.json"
        self.assertTrue(path.exists(), f"missing template: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("env", data)
        # No hijack: ANTHROPIC_BASE_URL not pointing at MiniMax.
        env = data["env"]
        bad = env.get("ANTHROPIC_BASE_URL", "")
        if bad:
            self.assertEqual(cb._host_of(bad), cb.ANTHROPIC_API_HOST)
        bad = env.get("ANTHROPIC_MODEL", "")
        self.assertFalse(
            "minimax" in bad.lower() or "MiniMax" in bad,
            f"anthropic template has MiniMax model: {bad!r}",
        )

    def test_minimax_template_exists_and_parses(self):
        path = TEMPLATES_DIR / "minimax.json"
        self.assertTrue(path.exists(), f"missing template: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("env", data)
        self.assertIn("modelPicker", data)
        # MiniMax template IS the hijack — at minimum, ANTHROPIC_MODEL set.
        self.assertIn("ANTHROPIC_MODEL", data["env"])
        self.assertIn("minimax", data["env"]["ANTHROPIC_MODEL"].lower())

    def test_templates_preserve_plugins_and_automode(self):
        for name in ("anthropic.json", "minimax.json"):
            data = json.loads((TEMPLATES_DIR / name).read_text(encoding="utf-8"))
            self.assertIn("enabledPlugins", data, f"{name}: missing enabledPlugins")
            self.assertIn("autoMode", data, f"{name}: missing autoMode")
            self.assertIn("effortLevel", data, f"{name}: missing effortLevel")


# ---------------------------------------------------------------------------
# 6. TwinParityTests — bash + PowerShell launcher surface parity
# ---------------------------------------------------------------------------
class TwinParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sh_text = CLAUDE_PMOVES_SH.read_text(encoding="utf-8")
        cls.ps1_text = CLAUDE_PMOVES_PS1.read_text(encoding="utf-8")

    def test_both_twins_reference_backend_flag(self):
        for label, text in (("bash", self.sh_text), ("ps1", self.ps1_text)):
            self.assertIn(
                "--backend=",
                text,
                f"{label} twin missing --backend= flag surface",
            )

    def test_both_twins_reference_pmoves_claude_backend_env_var(self):
        for label, text in (("bash", self.sh_text), ("ps1", self.ps1_text)):
            self.assertIn(
                "PMOVES_CLAUDE_BACKEND",
                text,
                f"{label} twin missing PMOVES_CLAUDE_BACKEND env-var reference",
            )

    def test_both_twins_reference_persistent_switch_hint(self):
        # The plan calls for the launchers to mention the persistent switch
        # (`pmoves-mini claude-backend ...`) so the operator finds it from
        # either surface.
        for label, text in (("bash", self.sh_text), ("ps1", self.ps1_text)):
            self.assertIn(
                "pmoves-mini claude-backend",
                text,
                f"{label} twin missing persistent-switch hint",
            )

    def test_both_twins_reference_warn_phrase_substring(self):
        # The python module pins WARN_PHRASE; both twins should mention it so
        # grep for "Mavis SDK hijack" finds the WARN line in both contexts.
        for label, text in (("bash", self.sh_text), ("ps1", self.ps1_text)):
            self.assertIn(
                "Mavis SDK hijack",
                text,
                f"{label} twin missing 'Mavis SDK hijack' phrase",
            )

    def test_both_twins_help_block_lists_all_three_backends(self):
        for label, text in (("bash", self.sh_text), ("ps1", self.ps1_text)):
            for v in ("auto", "anthropic", "minimax"):
                self.assertIn(v, text, f"{label} twin help block missing backend {v}")


if __name__ == "__main__":
    unittest.main()
