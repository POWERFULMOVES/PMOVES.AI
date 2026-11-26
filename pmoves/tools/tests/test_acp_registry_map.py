#!/usr/bin/env python3
"""acp_registry_map.py fails closed on an empty registry and detects drift.

Regression for the crush-acp drop in PR #3347: the generator defaulted to a
repo-root SIBLING clone (stale on z890) and treated an uninitialized
submodule -- an existing, empty directory -- as a registry with zero entries,
writing ``acp_entries: {}`` with exit 0.

Run:
  python -m pytest pmoves/tools/tests/test_acp_registry_map.py -v
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS))

import acp_registry_map as arm  # noqa: E402


def _run(*argv: str) -> tuple[int, str]:
    err = io.StringIO()
    with mock.patch.object(sys, "argv", ["acp_registry_map.py", *argv]), \
            redirect_stdout(io.StringIO()), redirect_stderr(err):
        rc = arm.main()
    return rc, err.getvalue()


class TestAcpRegistryMap(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="acp-map-")
        self.dir = Path(self._tmp.name)
        self.registry = self.dir / "registry"
        self.registry.mkdir()
        self.out = self.dir / "map.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _add_entry(self, acp_id: str, version: str = "1.0.0") -> None:
        entry = self.registry / acp_id
        entry.mkdir()
        (entry / "agent.json").write_text(json.dumps({
            "name": acp_id, "version": version,
            "repository": f"https://github.com/example/{acp_id}-agent",
        }), encoding="utf-8")

    def test_default_registry_is_the_pinned_submodule(self):
        self.assertEqual(arm.DEFAULT_REGISTRY, arm.REPO_ROOT / "PMOVES-registry")

    def test_missing_registry_fails_closed(self):
        rc, err = _run("--registry", str(self.dir / "absent"), "--out", str(self.out), "--write")
        self.assertEqual(rc, 2)
        self.assertIn("submodule update --init PMOVES-registry", err)
        self.assertFalse(self.out.exists())

    def test_empty_registry_fails_closed(self):
        # An uninitialized submodule is an existing, empty directory.
        rc, err = _run("--registry", str(self.registry), "--out", str(self.out), "--write")
        self.assertEqual(rc, 2)
        self.assertIn("refusing to emit an empty mapping", err)
        self.assertFalse(self.out.exists())

    def test_write_then_check_is_clean_and_lf(self):
        self._add_entry("alpha")
        self.assertEqual(_run("--registry", str(self.registry), "--out", str(self.out), "--write")[0], 0)
        self.assertNotIn(b"\r\n", self.out.read_bytes())
        self.assertEqual(_run("--registry", str(self.registry), "--out", str(self.out), "--check")[0], 0)

    def test_check_detects_a_dropped_entry(self):
        self._add_entry("alpha")
        self._add_entry("beta")
        _run("--registry", str(self.registry), "--out", str(self.out), "--write")
        # Regenerating from a checkout that lacks an entry must show as drift.
        stale = self.dir / "stale"
        stale.mkdir()
        (stale / "alpha").mkdir()
        (stale / "alpha" / "agent.json").write_text(
            (self.registry / "alpha" / "agent.json").read_text(encoding="utf-8"), encoding="utf-8")
        rc, err = _run("--registry", str(stale), "--out", str(self.out), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("DRIFT", err)

    def test_check_passes_a_crlf_working_copy(self):
        # A CRLF working copy (autocrlf checkout, or a Windows regeneration
        # before the write path forced LF) has the same content as the LF
        # blob git commits under `*.json text eol=lf`; it is not drift.
        self._add_entry("alpha")
        _run("--registry", str(self.registry), "--out", str(self.out), "--write")
        lf = self.out.read_bytes()
        self.out.write_bytes(lf.replace(b"\n", b"\r\n"))
        self.assertIn(b"\r\n", self.out.read_bytes())
        rc, err = _run("--registry", str(self.registry), "--out", str(self.out), "--check")
        self.assertEqual(rc, 0, err)

    def test_check_still_detects_content_drift_in_a_crlf_copy(self):
        # Newline normalisation must not launder a real content change.
        self._add_entry("alpha")
        _run("--registry", str(self.registry), "--out", str(self.out), "--write")
        crlf = self.out.read_bytes().replace(b"\n", b"\r\n")
        self.out.write_bytes(crlf.replace(b'"alpha"', b'"alphX"', 1))
        rc, err = _run("--registry", str(self.registry), "--out", str(self.out), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("DRIFT", err)

    def _git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
             "-c", "commit.gpgsign=false", *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def test_commit_not_stamped_from_an_enclosing_repo(self):
        # `git -C <dir> rev-parse HEAD` walks up to the parent repo when the
        # registry dir is a plain directory (e.g. an uninitialized submodule
        # inside this repo) -- that must NOT stamp the parent's commit.
        self._git(self.dir, "init", "-q")
        self._add_entry("alpha")
        self._git(self.dir, "add", "-A")
        self._git(self.dir, "commit", "-q", "-m", "outer")
        self.assertTrue(self._git(self.dir, "rev-parse", "HEAD"))
        self.assertIsNone(arm._registry_commit(self.registry))
        artifact, _ = arm.build_map(self.registry)
        self.assertNotIn("registry_commit", artifact)

    def test_commit_stamped_when_registry_is_its_own_checkout(self):
        self._add_entry("alpha")
        self._git(self.registry, "init", "-q")
        self._git(self.registry, "add", "-A")
        self._git(self.registry, "commit", "-q", "-m", "registry")
        head = self._git(self.registry, "rev-parse", "HEAD")
        self.assertEqual(arm._registry_commit(self.registry), head)

    def test_check_and_write_are_exclusive(self):
        self._add_entry("alpha")
        with self.assertRaises(SystemExit):
            _run("--registry", str(self.registry), "--out", str(self.out), "--write", "--check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
