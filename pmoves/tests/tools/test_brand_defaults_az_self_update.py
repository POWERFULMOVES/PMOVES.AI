"""Codex P1 on #1906: the A0_SELF_UPDATE_REMOTE_URL footgun guard must reach
EXISTING installs, not just fresh env.shared copies. _ensure_agent_zero_defaults
is the managed upsert path that runs on every brand-defaults apply.
"""
import unittest

import pmoves.tools.brand_defaults as bd

FORK = "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git"


class TestAzSelfUpdateRemoteUpsert(unittest.TestCase):
    def test_blank_install_gets_fork_pin(self) -> None:
        out = bd._ensure_agent_zero_defaults("AGENTZERO_JETSTREAM=true\n")
        self.assertIn(f"A0_SELF_UPDATE_REMOTE_URL={FORK}", out)

    def test_existing_install_without_key_gets_pin(self) -> None:
        # Simulates an already-provisioned env.shared that predates the guard.
        existing = "A0_SET_chat_model=tensorzero::model_name::chat_default\nMCP_CLIENT_SECRET=abc\n"
        out = bd._ensure_agent_zero_defaults(existing)
        self.assertIn(f"A0_SELF_UPDATE_REMOTE_URL={FORK}", out)

    def test_operator_custom_value_preserved(self) -> None:
        custom = "A0_SELF_UPDATE_REMOTE_URL=https://example.com/x.git\n"
        out = bd._ensure_agent_zero_defaults(custom)
        self.assertIn("example.com/x.git", out)
        self.assertNotIn("POWERFULMOVES/PMOVES-Agent-Zero", out)


if __name__ == "__main__":
    unittest.main()
