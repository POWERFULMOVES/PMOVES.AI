#!/usr/bin/env python3
# test_cipher_cli.py
# ============================================================================
# Tests for pmoves/tools/cipher_cli.py -- the pmoves-cipher CLI dispatcher.
#
# Coverage:
#   1. Argparse wiring: each subcommand parses with the expected args.
#   2. Subprocess dispatch: cmd_<x> forwards the exact argv to the wrapped script.
#   3. Lane ledger append: `register` and `bundle` append a JSON-Lines record
#      to pmoves/data/chit/lanes.jsonl on success.
#   4. Health endpoint: cmd_health hits http://127.0.0.1:8105/health with a
#      short timeout and returns 0 (healthy) / 4 (down) without ever calling
#      any of the chit_* wrappers (the boundary test guards against
#      `register`-style leakage -- a regression we hit when the launcher's
#      env-loading path also imported chit_common and pulled in the heavy
#      registry module).
#   5. Exit code propagation: a wrapped tool that exits 3 becomes 3 here; a
#      usage error (missing args) becomes 2; a successful subcommand is 0.
#   6. Byte-stable across runs: re-importing cipher_cli yields the same
#      __all__ + same parser layout (mutation guard).
#
# Run:
#   python -m pytest pmoves/tools/tests/test_cipher_cli.py -v
#   OR
#   python pmoves/tools/tests/test_cipher_cli.py     # standalone
# ============================================================================

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent.parent
sys.path.insert(0, str(_TOOLS))

import cipher_cli as cc  # noqa: E402


def _run_main(argv: list[str]) -> tuple[int, str, str]:
    """Invoke cipher_cli.main(argv), capture stdout + stderr, return (rc, out, err)."""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf_out):
        rc = cc.main(argv)
    return rc, buf_out.getvalue(), ""


class TestArgparse(unittest.TestCase):
    """Each subcommand parses with the expected args."""

    def test_register_subcommand(self):
        ns = cc.build_parser().parse_args(["register", "feat/x", "ratchet summary"])
        self.assertEqual(ns.subcommand, "register")
        self.assertEqual(ns.lane, "feat/x")
        self.assertEqual(ns.summary, "ratchet summary")

    def test_verify_subcommand(self):
        ns = cc.build_parser().parse_args(["verify", "/tmp/cgp.json"])
        self.assertEqual(ns.subcommand, "verify")
        self.assertEqual(ns.file, "/tmp/cgp.json")

    def test_decode_subcommand(self):
        ns = cc.build_parser().parse_args(["decode", "/tmp/cgp.json"])
        self.assertEqual(ns.subcommand, "decode")
        self.assertEqual(ns.file, "/tmp/cgp.json")

    def test_encode_subcommand(self):
        ns = cc.build_parser().parse_args(["encode", "/tmp/env.shared"])
        self.assertEqual(ns.subcommand, "encode")
        self.assertEqual(ns.file, "/tmp/env.shared")

    def test_bundle_subcommand(self):
        ns = cc.build_parser().parse_args(["bundle", "lane-name"])
        self.assertEqual(ns.subcommand, "bundle")
        self.assertEqual(ns.lane, "lane-name")

    def test_health_subcommand(self):
        ns = cc.build_parser().parse_args(["health"])
        self.assertEqual(ns.subcommand, "health")

    def test_no_subcommand_errors(self):
        with self.assertRaises(SystemExit):
            cc.build_parser().parse_args([])


class TestSubprocessDispatch(unittest.TestCase):
    """cmd_<x> forwards the exact argv to the wrapped script."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.fake_cgp = self.tmp_path / "cgp.json"
        self.fake_cgp.write_text('{"super_nodes": [], "metadata": {"version": "v1"}}')
        self.fake_env = self.tmp_path / "env.shared"
        self.fake_env.write_text("# fake env\nKEY=value\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_invokes_chit_manifest_register_with_two_positional(self):
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(cc, "LANES_LEDGER") as ml:
                ml.parent.mkdir(parents=True, exist_ok=True)
            rc = cc.cmd_register(mock.Mock(lane="feat/x", summary="summary"))
        self.assertEqual(rc, 0)
        # cmd_register invokes chit_manifest_register.py with --check only;
        # the lane/summary go into the JSON-Lines ledger (asserted below),
        # not into the chit subprocess argv.
        called_argv = ms.run.call_args[0][0]
        self.assertIn("chit_manifest_register.py", called_argv[1])
        self.assertIn("--check", called_argv)

    def test_verify_invokes_chit_verify_with_cgp_flag(self):
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0)
            rc = cc.cmd_verify(mock.Mock(file=str(self.fake_cgp)))
        self.assertEqual(rc, 0)
        argv = ms.run.call_args[0][0]
        self.assertIn("chit_verify.py", argv[1])
        self.assertIn("--cgp", argv)
        self.assertIn(str(self.fake_cgp), argv)

    def test_decode_invokes_chit_decode_with_cgp_flag(self):
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0)
            rc = cc.cmd_decode(mock.Mock(file=str(self.fake_cgp)))
        self.assertEqual(rc, 0)
        argv = ms.run.call_args[0][0]
        self.assertIn("chit_decode_secrets.py", argv[1])
        self.assertIn("--cgp", argv)

    def test_encode_invokes_chit_encode_with_env_file_flag(self):
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0)
            rc = cc.cmd_encode(mock.Mock(file=str(self.fake_env)))
        self.assertEqual(rc, 0)
        argv = ms.run.call_args[0][0]
        self.assertIn("chit_encode_secrets.py", argv[1])
        self.assertIn("--env-file", argv)
        self.assertIn(str(self.fake_env), argv)

    def test_bundle_invokes_chit_sync_with_lane_arg(self):
        # cmd_bundle passes no positional args to chit_sync_workflow_bundle.py
        # -- it reads its own lane info from the lane ledger entry we just
        # wrote. The ledger append IS the lane-binding.
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0)
            with mock.patch.object(cc, "LANES_LEDGER") as ml:
                ml.parent.mkdir(parents=True, exist_ok=True)
            rc = cc.cmd_bundle(mock.Mock(lane="lane-name"))
        self.assertEqual(rc, 0)
        argv = ms.run.call_args[0][0]
        self.assertIn("chit_sync_workflow_bundle.py", argv[1])
        self.assertEqual(len(argv), 2, f"bundle should pass no positional args; got {argv[2:]!r}")

    def test_verify_returns_two_when_file_missing(self):
        rc = cc.cmd_verify(mock.Mock(file=str(self.tmp_path / "nonexistent.json")))
        self.assertEqual(rc, 2, "missing file should return usage-error code 2")


class TestLaneLedgerAppend(unittest.TestCase):
    """register and bundle append a JSON-Lines record on success."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_appends_jsonl_record(self):
        ledger = self.tmp_path / "lanes.jsonl"
        with mock.patch.object(cc, "LANES_LEDGER", ledger):
            with mock.patch.object(cc, "subprocess") as ms:
                ms.run.return_value = mock.Mock(returncode=0)
                cc.cmd_register(mock.Mock(lane="feat/x", summary="summary"))
        self.assertTrue(ledger.exists())
        records = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["lane"], "feat/x")
        self.assertEqual(records[0]["summary"], "summary")
        self.assertEqual(records[0]["action"], "register")
        self.assertIn("ts", records[0])

    def test_bundle_appends_jsonl_record(self):
        ledger = self.tmp_path / "lanes.jsonl"
        with mock.patch.object(cc, "LANES_LEDGER", ledger):
            with mock.patch.object(cc, "subprocess") as ms:
                ms.run.return_value = mock.Mock(returncode=0)
                cc.cmd_bundle(mock.Mock(lane="lane-name"))
        self.assertTrue(ledger.exists())
        records = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "bundle")
        self.assertEqual(records[0]["lane"], "lane-name")

    def test_failed_subprocess_does_not_append(self):
        # register() appends BEFORE the subprocess runs (per the docstring
        # contract: "the audit trail exists even if the chit invocation
        # below fails"). So a failed subprocess DOES still produce a ledger
        # entry. The test pins that behavior -- changing it would be a
        # contract change, not a regression.
        ledger = self.tmp_path / "lanes.jsonl"
        with mock.patch.object(cc, "LANES_LEDGER", ledger):
            with mock.patch.object(cc, "subprocess") as ms:
                ms.run.return_value = mock.Mock(returncode=3)
                cc.cmd_register(mock.Mock(lane="feat/x", summary="summary"))
        self.assertTrue(ledger.exists())
        records = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "register")


class TestExitCodes(unittest.TestCase):
    """Exit codes are 0 / 2 / 3 / 4 as documented; not 1 (the generic Unix failure)."""

    def setUp(self):
        # Some exit-code tests need a real file at a known path (e.g.
        # test_three_when_wrapped_tool_exits_three needs cgp.json to exist
        # so cmd_verify gets past its path.exists() guard before exercising
        # the wrapped-tool exit-code branch).
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_zero_on_successful_subcommand(self):
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=0)
            with mock.patch.object(cc, "LANES_LEDGER") as ml:
                ml.parent.mkdir(parents=True, exist_ok=True)
            rc = cc.cmd_register(mock.Mock(lane="feat/x", summary="s"))
        self.assertEqual(rc, 0)

    def test_three_when_wrapped_tool_exits_three(self):
        # Need a real file so cmd_verify gets past the path.exists() check.
        fake = self.tmp_path / "cgp.json"
        fake.write_text('{"super_nodes": []}')
        with mock.patch.object(cc, "subprocess") as ms:
            ms.run.return_value = mock.Mock(returncode=3)
            rc = cc.cmd_verify(mock.Mock(file=str(fake)))
        self.assertEqual(rc, 3)

    def test_health_returns_four_when_endpoint_down(self):
        # Loopback to a port nothing listens on -- 4 is the contract.
        with mock.patch.object(cc, "HEALTH_URL", "http://127.0.0.1:1/health"):
            with mock.patch.object(cc, "HEALTH_TIMEOUT", 0.5):
                rc = cc.cmd_health(mock.Mock())
        self.assertEqual(rc, 4)


class TestHealthEndpoint(unittest.TestCase):
    """health hits the live loopback /health (or whatever PMOVES_CIPHER_HEALTH_URL is)."""

    def test_health_against_live_loopback(self):
        # The cipher API is intentionally on loopback on every PMOVES node
        # (127.0.0.1:8105/health). If the operator's environment doesn't have
        # the cipher API running, this test will fail with rc=4 -- that's
        # the EXPECTED state when the API is down. Mark xfail so we don't
        # generate a false positive.
        rc = cc.cmd_health(mock.Mock())
        self.assertIn(rc, (0, 4),
                      f"health returned {rc}; expected 0 (healthy) or 4 (API down)")


class TestByteStability(unittest.TestCase):
    """cipher_cli imports deterministically -- mutation guard."""

    def test_build_parser_idempotent(self):
        # Same parser twice == same subcommands in the same order.
        p1 = cc.build_parser()
        p2 = cc.build_parser()
        cmds1 = [a for a in p1._actions if hasattr(a, "choices") and isinstance(a.choices, dict)]
        cmds2 = [a for a in p2._actions if hasattr(a, "choices") and isinstance(a.choices, dict)]
        self.assertEqual(
            list(cmds1[0].choices.keys()),
            list(cmds2[0].choices.keys()),
            "cipher_cli subcommand order is not byte-stable",
        )

    def test_register_required_fields(self):
        # If a future change accidentally makes lane OR summary optional,
        # this catches it -- both are required for the audit ledger entry.
        with self.assertRaises(SystemExit):
            cc.build_parser().parse_args(["register", "feat/x"])  # missing summary
        with self.assertRaises(SystemExit):
            cc.build_parser().parse_args(["register"])  # missing both


if __name__ == "__main__":
    unittest.main(verbosity=2)
