# pmoves/tools/tests/test_smoke_http_port_parser.py
"""The smoke suite's URL -> host-port parser must resolve the SAME number the
container requested, because the silent-bind lookup is keyed by it.

WHY THIS EXISTS
---------------
``pmoves/scripts/smoke-tests.sh`` collapses a refused connection into a
warning on the HTTP path, while the TCP path separates "the service is DOWN"
from "the service is UP but Docker never activated the host port it
requested" (a silent bind -- moby/moby#36174). The HTTP path now makes the
same distinction, which means it has to know the port the URL points at.

The parser has to survive the three shapes the house's own URLs take:
a literal port, a substitution with a default, and a substitution with no
default. The default form is the trap: "${VAR:-default}" contains a colon,
so splitting the authority on the LAST colon cuts INSIDE the substitution
and yields ":-default}" instead of the port. That bug was found by this
test, not by reading the code.

The function is EXTRACTED from the house script rather than copied, so this
test cannot drift from the code it claims to verify.

Hermetic: no network, no docker. Skipped when no bash is available.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "smoke-tests.sh"


def _bash() -> str | None:
    """A bash that can see THIS machine's paths.

    On Windows, ``shutil.which("bash")`` finds the WSL bash (C:\\Windows\\System32\\bash.exe),
    which cannot open a Windows path -- it reported "No such file or directory"
    for a file that plainly exists. Git Bash can, so it is preferred here.
    """
    if os.name == "nt":
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
        ):
            if Path(candidate).is_file():
                return candidate
    found = shutil.which("bash")
    if found:
        return found
    return None


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available here")


def _msys(path: Path) -> str:
    """A path Git Bash can open.

    Git Bash is an MSYS program: a native Windows path handed to it as an
    argument is NOT converted, so "C:\\Users\\..." reads as a relative path
    with a backslash in it. The MSYS form is "/c/Users/...".
    """
    if os.name != "nt":
        return str(path)
    text = str(path).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        return "/" + text[0].lower() + text[2:]
    return text


CASES = [
    ("http://localhost:8084/healthz", "8084"),
    ("http://localhost:6333/healthz", "6333"),
    ("http://127.0.0.1:5678/rest/v1/executions", "5678"),
    ("http://host.docker.internal:4000/", "4000"),
    ("http://user:pw@localhost:8123/ping", "8123"),
    ("http://[::1]:8123/ping", "8123"),
    # No port at all -> nothing to look up.
    ("http://localhost", ""),
    ("http://localhost/", ""),
    # A substitution with a default: the colon lives INSIDE the substitution.
    ("http://localhost:${ARCHON_PORT:-3090}/api/health", "3090"),
    # A substitution with no default and no environment -> not guessed.
    ("http://localhost:${SUPABASE_POSTGREST_PORT}/", ""),
]


def _extracted(tmp_path: Path) -> Path:
    """Pull the real _http_port function out of the house script."""
    source = SMOKE.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, l in enumerate(source) if l.startswith("_http_port() {"))
    except StopIteration:  # pragma: no cover - the function was removed
        pytest.fail("_http_port is missing from pmoves/scripts/smoke-tests.sh")
    end = next(i for i in range(start + 1, len(source)) if source[i] == "}")
    out = tmp_path / "http_port.sh"
    out.write_text("\n".join(source[start:end + 1]) + "\n", encoding="utf-8", newline="\n")
    return out


@pytest.mark.parametrize("url,expected", CASES, ids=lambda c: str(c))
def test_http_port_resolves_the_requested_port(tmp_path, url, expected):
    fn = _extracted(tmp_path)
    proc = subprocess.run(
        [BASH, "-c", f'. "{_msys(fn)}"; _http_port "{url}"'],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == expected


def test_a_substitution_port_follows_the_environment(tmp_path):
    """A ${VAR} port with the variable SET resolves to the environment value,
    and with the variable UNSET it resolves to nothing -- the parser must not
    invent a number."""
    fn = _extracted(tmp_path)
    env = dict(os.environ)
    env["PMOVES_TEST_PORT"] = "3999"
    proc = subprocess.run(
        [BASH, "-c", f'. "{_msys(fn)}"; _http_port "http://localhost:${{PMOVES_TEST_PORT}}/"'],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "3999"

    env.pop("PMOVES_TEST_PORT", None)
    proc = subprocess.run(
        [BASH, "-c", f'. "{_msys(fn)}"; _http_port "http://localhost:${{PMOVES_TEST_PORT}}/"'],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""


def test_the_smoke_script_still_parses(tmp_path):
    """The house script must remain valid bash after the edit."""
    proc = subprocess.run([BASH, "-n", _msys(SMOKE)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
