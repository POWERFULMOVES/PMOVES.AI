# pmoves/tools/tests/test_smoke_silent_bind_cache.py
"""The smoke suite's silent-bind map must be built ONCE, in the shell that
needs it -- not once per probe.

THE DEFECT
----------
``pmoves/scripts/smoke-tests.sh`` looks up the owner of a silent bind with
command substitution::

    _owner="$(_silent_bind_owner "$_port")"

Command substitution runs in a SUBSHELL. When the map was built inside the
lookup function, the assignment to ``_SILENT_BIND_MAP`` landed in that
subshell and was thrown away when the substitution ended. The next refused
probe therefore started with an empty map and paid the whole cost again:
``docker ps`` plus a batched ``docker inspect`` over every container in the
project. With many inactive profiles that is exactly the timeout the cache
was written to prevent -- the first version of this map inspected every
container per failed probe, 63 exec calls per test on this node.

So the build and the lookup are separate functions: ``_silent_bind_map_init``
fills the variable in the PARENT shell, and ``_silent_bind_owner`` only
reads it. The callers call the init first.

This file pins BOTH halves, because either one alone is not the fix:

  * the runtime half -- with the init called first, any number of lookups
    costs exactly one ``docker ps`` and one ``docker inspect``;
  * the structural half -- every call site in the house script initialises
    the map in the parent shell BEFORE the substitution.

The functions are EXTRACTED from the house script rather than copied, so
this file cannot drift from the code it claims to verify.

THE BASH IS THE HOUSE'S
-----------------------
argv[0] comes from ``pmoves.tools.bash_resolver.find_bash()``, never from
``shutil.which("bash")`` and never from a hand-rolled helper: on Windows a
bare "bash" resolves to the WSL launcher before PATH is consulted, so the
child would silently run in a different OS. ``pmoves/tests/
test_no_bare_bash_argv.py`` fails this file for exactly that shape.

Hermetic: no network, no real docker. The fake ``docker`` is a shell script
on PATH that counts its own invocations.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import find_bash

SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "smoke-tests.sh"

#: An ABSOLUTE path to a usable bash, or None. Never the WSL stub.
BASH = find_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no usable bash on this host")

FUNCTIONS = ("_silent_bind_map_init", "_silent_bind_owner")

# A container that REQUESTED 8084 and never got it: the requested list
# contains the port, the activated list does not. That is the silent-bind
# shape, and the lookup must report the container.
FAKE_INSPECT_LINE = "/pmoves-langextract-1|8084,|"


def _extract(tmp_path: Path, names=FUNCTIONS) -> Path:
    """Pull the named functions out of the house script."""
    source = SMOKE.read_text(encoding="utf-8").splitlines()
    chunks = []
    for name in names:
        try:
            start = next(i for i, l in enumerate(source) if l.startswith(f"{name}() {{"))
        except StopIteration:  # pragma: no cover - the function was removed
            pytest.fail(f"{name} is missing from {SMOKE}")
        end = next(i for i in range(start + 1, len(source)) if source[i] == "}")
        chunks.append("\n".join(source[start:end + 1]))
    out = tmp_path / "funcs.sh"
    out.write_text("\n\n".join(chunks) + "\n", encoding="utf-8", newline="\n")
    return out


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    """A `docker` on PATH that counts its invocations and fakes one container."""
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    counter = tmp_path / "docker.calls"
    fake = bindir / "docker"
    fake.write_text(
        "#!/bin/bash\n"
        'echo "$*" >> "$COUNTER_FILE"\n'
        'case "$1" in\n'
        '  ps) echo "cid0001" ;;\n'
        f"  inspect) echo '{FAKE_INSPECT_LINE}' ;;\n"
        "esac\n",
        encoding="utf-8", newline="\n",
    )
    fake.chmod(0o755)
    return bindir, counter


def _run(script: str, bindir: Path, counter: Path):
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    env["COUNTER_FILE"] = str(counter)
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, env=env,
    )


def test_the_cache_is_built_once_and_reused_across_lookups(tmp_path):
    """With the init called first, N lookups cost ONE ps and ONE inspect."""
    fn = _extract(tmp_path)
    bindir, counter = _fake_docker(tmp_path)
    proc = _run(
        f'. "{fn}"\n'
        "_silent_bind_map_init\n"
        'o1="$(_silent_bind_owner 8084)"\n'
        'o2="$(_silent_bind_owner 9999)"\n'
        'o3="$(_silent_bind_owner 7777)"\n'
        'echo "owners=$o1|$o2|$o3"\n',
        bindir, counter,
    )
    assert proc.returncode == 0, proc.stderr
    # The first lookup finds the silent bind; the other two find nothing.
    assert proc.stdout.strip() == "owners=pmoves-langextract-1||"
    calls = [c for c in counter.read_text(encoding="utf-8").splitlines() if c.strip()]
    assert len(calls) == 2, f"expected one docker ps and one docker inspect, got {calls}"
    assert calls[0].startswith("ps")
    assert calls[1].startswith("inspect")


def test_without_the_parent_shell_init_the_map_is_rebuilt_per_lookup(tmp_path):
    """The regression this fix closes, measured.

    When the lookup is the only thing that builds the map, the assignment
    happens inside the substitution subshell and is discarded -- so every
    lookup pays the full cost again. This test pins THAT as the broken
    shape, so the fix cannot be quietly reverted to it.
    """
    fn = _extract(tmp_path)
    bindir, counter = _fake_docker(tmp_path)
    proc = _run(
        f'. "{fn}"\n'
        'o1="$(_silent_bind_owner 8084)"\n'
        'o2="$(_silent_bind_owner 9999)"\n',
        bindir, counter,
    )
    assert proc.returncode == 0, proc.stderr
    calls = [c for c in counter.read_text(encoding="utf-8").splitlines() if c.strip()]
    # Two lookups, each rebuilding: 2 x (ps + inspect).
    assert len(calls) == 4, (
        "expected the un-inited shape to rebuild the map per lookup "
        f"(4 docker calls), got {calls}"
    )


def test_every_call_site_initializes_the_map_before_the_substitution():
    """The structural half: the house script's own call sites must build the
    map in the parent shell. A runtime test of the functions alone would
    still pass if the script stopped calling the init."""
    source = SMOKE.read_text(encoding="utf-8").splitlines()
    sites = [
        i for i, line in enumerate(source)
        if "$(_silent_bind_owner" in line and not line.lstrip().startswith("#")
    ]
    assert sites, "the house script no longer looks up a silent-bind owner"
    for i in sites:
        window = source[max(0, i - 12):i]
        assert any("_silent_bind_map_init" in w for w in window), (
            "a call site reads the owner without building the map in the "
            f"parent shell first (smoke-tests.sh line {i + 1}):\n"
            + "\n".join(window)
        )


def test_the_smoke_script_still_parses():
    """The house script must remain valid bash after the edit."""
    proc = subprocess.run([BASH, "-n", str(SMOKE)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
