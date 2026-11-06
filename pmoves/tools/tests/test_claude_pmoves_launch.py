#!/usr/bin/env python3
# test_claude_pmoves_launch.py
# ============================================================================
# EXECUTES the hand-written claude-pmoves launchers end-to-end, with a stub
# `claude` first on PATH, and asserts the launcher actually reaches it.
#
# Why this exists (issue #3356): the only launcher coverage was "the .ps1
# parses" / "the .sh passes bash -n". claude-pmoves.ps1 parsed fine while
# crashing on every launch -- a method call on $null at line 33, and a helper
# called ~190 lines before its definition. Parsing cannot see either; running
# can.
#
# Hermetic: PMOVES_ENV_SHARED -> an empty temp file (no fleet secrets loaded),
# PMOVES_ROSTER_FROM_TREE=1 (no `git fetch`), PMOVES_PYTHON -> this interpreter
# (deterministic python ladder). The stub prints what it received; nothing is
# launched.
#
# Platform: the .ps1 twin runs on Windows (where claude-pmoves.cmd targets it),
# the .sh twin on POSIX. On Windows `bash` may resolve to WSL, whose paths do
# not line up with this checkout, so the .sh twin is skipped there.
#
# Run:
#   python -m pytest pmoves/tools/tests/test_claude_pmoves_launch.py -v
# ============================================================================

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "pmoves" / "tools"))
from bash_resolver import find_bash, resolve_bash  # noqa: E402  never System32's WSL stub

_PS1 = _REPO / "deploy" / "provision" / "claude-pmoves.ps1"
_SH = _REPO / "deploy" / "provision" / "claude-pmoves.sh"

# The stubs never echo a credential: only whether the auth token is the local
# backend's fixed placeholder, and whether an API key is present at all.
_STUB_CMD = (
    "@echo off\r\n"
    "echo STUB_ARGV: %*\r\n"
    "echo STUB_BASE_URL=[%ANTHROPIC_BASE_URL%]\r\n"
    "echo STUB_MODEL=[%ANTHROPIC_MODEL%]\r\n"
    "echo STUB_HAIKU=[%ANTHROPIC_DEFAULT_HAIKU_MODEL%]\r\n"
    'if "%ANTHROPIC_AUTH_TOKEN%"=="ollama" echo STUB_AUTH=placeholder\r\n'
    "if defined ANTHROPIC_API_KEY echo STUB_API_KEY=present\r\n"
    "exit /b 0\r\n"
)
_STUB_SH = (
    "#!/bin/sh\n"
    'echo "STUB_ARGV: $*"\n'
    'echo "STUB_BASE_URL=[${ANTHROPIC_BASE_URL:-}]"\n'
    'echo "STUB_MODEL=[${ANTHROPIC_MODEL:-}]"\n'
    'echo "STUB_HAIKU=[${ANTHROPIC_DEFAULT_HAIKU_MODEL:-}]"\n'
    '[ "${ANTHROPIC_AUTH_TOKEN:-}" = ollama ] && echo "STUB_AUTH=placeholder"\n'
    '[ -n "${ANTHROPIC_API_KEY+x}" ] && echo "STUB_API_KEY=present"\n'
    "exit 0\n"
)


class _FakeOllama:
    """Loopback stub of the three Ollama endpoints the local preflight reads."""

    TAGS = ("qwen3:30b-a3b-gpu", "qwen3:8b-gpu")
    PARAMS = "num_ctx                        32768\nnum_gpu                        999"

    def __init__(self) -> None:
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep test output clean
                pass

            def _send(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/version":
                    return self._send({"version": "0.30.0"})
                if self.path == "/api/tags":
                    return self._send({"models": [{"name": t, "model": t} for t in outer.TAGS]})
                self.send_error(404)

            def do_POST(self):
                if self.path == "/api/show":
                    self.rfile.read(int(self.headers.get("Content-Length") or 0))
                    return self._send({"parameters": outer.PARAMS})
                self.send_error(404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._t = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._t.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _closed_port_url() -> str:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"


class _LauncherHarness:
    """Temp bin dir holding the stub + an empty env.shared."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="claude-pmoves-launch-")
        self.dir = Path(self._tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        if sys.platform == "win32":
            (self.bin / "claude.cmd").write_text(_STUB_CMD, encoding="ascii")
        else:
            stub = self.bin / "claude"
            stub.write_text(_STUB_SH, encoding="ascii")
            stub.chmod(0o755)
        self.env_shared = self.dir / "env.shared"
        self.env_shared.write_text("", encoding="ascii")

    def env(self, **overrides: str) -> dict:
        env = dict(os.environ)
        # The last three are the tracked roster's ${VAR}s (.claude/mcp.json).
        # Stripping them means every case runs as a node WITHOUT the fleet env:
        # the normalizer then drops/degrades servers with WARN lines on stderr,
        # which must not trip the launcher's fail-closed roster gate.
        for name in ("PMOVES_CLAUDE_BACKEND", "ANTHROPIC_BASE_URL",
                     "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
                     "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                     "PMOVES_LOCAL_ANTHROPIC_URL", "PMOVES_LOCAL_CLAUDE_MODEL",
                     "PMOVES_LOCAL_CLAUDE_SMALL_MODEL", "PMOVES_LOCAL_CLAUDE_SETTINGS",
                     "PMOVES_ALLOW_RAW_ROSTER",
                     "TS_Z890", "CIPHER_API_TOKEN", "AGENT_ZERO_MCP_TOKEN"):
            env.pop(name, None)
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        env["PMOVES_ENV_SHARED"] = str(self.env_shared)
        env["PMOVES_ROSTER_FROM_TREE"] = "1"
        env["PMOVES_PYTHON"] = sys.executable
        env.update(overrides)
        return env

    def close(self) -> None:
        self._tmp.cleanup()


class _LaunchCases:
    """Shared cases; subclasses supply `_run`."""

    harness: _LauncherHarness

    def _run(self, args: list, **env: str) -> subprocess.CompletedProcess:
        raise NotImplementedError

    def _assert_reached_claude(self, proc: subprocess.CompletedProcess) -> str:
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out[-3000:])
        self.assertIn("STUB_ARGV:", out, "launcher never invoked claude:\n" + out[-3000:])
        return out

    def test_default_backend_reaches_claude_with_args(self):
        out = self._assert_reached_claude(self._run(["--resume", "DRYRUN-ID"]))
        argv = next(l for l in out.splitlines() if "STUB_ARGV:" in l)
        self.assertIn("--resume DRYRUN-ID", argv)
        self.assertIn("--mcp-config=", argv)
        self.assertNotIn("--backend", argv)

    def test_backend_flag_is_consumed(self):
        out = self._assert_reached_claude(
            self._run(["--backend=anthropic", "--resume", "DRYRUN-ID"]))
        argv = next(l for l in out.splitlines() if "STUB_ARGV:" in l)
        self.assertNotIn("--backend", argv)
        self.assertIn("--resume DRYRUN-ID", argv)

    def test_anthropic_backend_strips_hijacked_base_url(self):
        out = self._assert_reached_claude(self._run(
            ["--backend=anthropic"],
            ANTHROPIC_BASE_URL="https://hijack.invalid/anthropic"))
        self.assertIn("STUB_BASE_URL=[]", out)

    def test_identity_failure_is_fail_open(self):
        # `-S` drops site-packages, so node_identity.py dies on `import yaml`
        # with a traceback on stderr -- what a node falling back to a bare
        # system python (`py -3`) sees. The resolver is documented FAIL-OPEN:
        # it must warn and still launch, not turn stderr into a fatal error.
        out = self._assert_reached_claude(self._run(
            ["--resume", "DRYRUN-ID"], PMOVES_PYTHON=f"{sys.executable} -S"))
        self.assertIn("--resume DRYRUN-ID", out)

    def test_multi_word_interpreter_runs_the_tools(self):
        # A two-word vector like `py -3`. PowerShell used to splat the one-element
        # tail as characters (`- 3`), so python ran a script read from stdin and
        # the roster normalizer silently did nothing. Prove it ran: claude must
        # get the NORMALIZED roster, not the raw .claude/mcp.json.
        out = self._assert_reached_claude(self._run(
            ["--resume", "DRYRUN-ID"], PMOVES_PYTHON=f"{sys.executable} -E"))
        argv = next(l for l in out.splitlines() if "STUB_ARGV:" in l)
        self.assertIn("claude-pmoves-mcp-roster", argv)

    def test_invalid_backend_refuses_without_launching(self):
        proc = self._run(["--backend=bogus"])
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out[-3000:])
        self.assertNotIn("STUB_ARGV:", out)

    # --- --backend=local ---------------------------------------------------
    def test_local_backend_sets_env_settings_and_keeps_roster(self):
        fake = _FakeOllama()
        try:
            out = self._assert_reached_claude(self._run(
                ["--backend=local", "-p", "say ok"],
                PMOVES_LOCAL_ANTHROPIC_URL=fake.url,
                # A key in the parent env must NOT reach the local session.
                ANTHROPIC_API_KEY="sk-test-not-a-real-key"))
        finally:
            fake.close()
        argv = next(l for l in out.splitlines() if "STUB_ARGV:" in l)
        self.assertIn(f"STUB_BASE_URL=[{fake.url}]", out)
        self.assertIn("STUB_MODEL=[qwen3:30b-a3b-gpu]", out)
        self.assertIn("STUB_HAIKU=[qwen3:8b-gpu]", out)
        self.assertIn("STUB_AUTH=placeholder", out)
        self.assertNotIn("STUB_API_KEY=present", out)
        self.assertNotIn("sk-test-not-a-real-key", out)
        # Same roster wiring as every other backend.
        self.assertIn("--mcp-config=", argv)
        self.assertIn("claude-pmoves-mcp-roster", argv)
        # Per-launch --settings carries the routing (beats a settings.json env block).
        self.assertIn("--settings=", argv)
        self.assertIn("ANTHROPIC_DEFAULT_HAIKU_MODEL", argv)
        self.assertNotIn("--backend", argv)
        self.assertIn("-p say ok", argv)

    def test_local_backend_model_override(self):
        fake = _FakeOllama()
        try:
            out = self._assert_reached_claude(self._run(
                ["--backend=local"], PMOVES_LOCAL_ANTHROPIC_URL=fake.url,
                PMOVES_LOCAL_CLAUDE_MODEL="qwen3:8b-gpu"))
        finally:
            fake.close()
        self.assertIn("STUB_MODEL=[qwen3:8b-gpu]", out)

    def test_local_backend_refuses_when_endpoint_down(self):
        proc = self._run(["--backend=local"], PMOVES_LOCAL_ANTHROPIC_URL=_closed_port_url())
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out[-3000:])
        self.assertNotIn("STUB_ARGV:", out)
        self.assertIn("local backend refused", out)
        self.assertIn("/api/version", out)

    def test_local_backend_refuses_unknown_model(self):
        fake = _FakeOllama()
        try:
            proc = self._run(["--backend=local"], PMOVES_LOCAL_ANTHROPIC_URL=fake.url,
                             PMOVES_LOCAL_CLAUDE_MODEL="not-pulled:70b")
        finally:
            fake.close()
        out = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, out[-3000:])
        self.assertNotIn("STUB_ARGV:", out)
        self.assertIn("not-pulled:70b", out)
        self.assertIn("PMOVES_LOCAL_CLAUDE_MODEL", out)


@unittest.skipUnless(sys.platform == "win32" and shutil.which("powershell"),
                     "the .ps1 twin runs under Windows PowerShell")
class TestClaudePmovesPs1Launch(_LaunchCases, unittest.TestCase):
    def setUp(self):
        self.harness = _LauncherHarness()

    def tearDown(self):
        self.harness.close()

    def _run(self, args, **env):
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(_PS1), *args],
            env=self.harness.env(**env), capture_output=True, text=True,
            stdin=subprocess.DEVNULL,
            encoding="utf-8", errors="replace", timeout=300)


@unittest.skipIf(sys.platform == "win32" or not find_bash(),
                 "the .sh twin runs under POSIX bash")
class TestClaudePmovesShLaunch(_LaunchCases, unittest.TestCase):
    def setUp(self):
        self.harness = _LauncherHarness()

    def tearDown(self):
        self.harness.close()

    def _run(self, args, **env):
        return subprocess.run(
            [resolve_bash(), str(_SH), *args],
            env=self.harness.env(**env), capture_output=True, text=True,
            stdin=subprocess.DEVNULL,
            encoding="utf-8", errors="replace", timeout=300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
