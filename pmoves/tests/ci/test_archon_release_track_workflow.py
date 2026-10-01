"""archon-release-track.yml resolve step, executed the way GitHub runs it.

GitHub's default `run:` shell is `bash --noprofile --norc -eo pipefail`. The
resolver's exit 1 ("fork lacks the release") is DATA for this step, so the step
must survive it and write `rc` exactly once. The resolver is replaced by a stub
`python3` on PATH; nothing touches the network.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

WF = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "archon-release-track.yml"

GOOD = """COMPONENT=archon
UPSTREAM=coleam00/Archon
FORK=POWERFULMOVES/PMOVES-Archon
FORK_BRANCH=PMOVES.AI-Edition-Hardened
RELEASE_TAG=v0.11.1
RELEASE_VERSION=0.11.1
RELEASE_SHA={a}
FORK_SHA={b}
FORK_SHA8={b8}
COMPARE={cmp}
CONTAINS_RELEASE={contains}
""".format(a="a" * 40, b="b" * 40, b8="b" * 8, cmp="{cmp}", contains="{contains}")


def resolve_script() -> str:
    wf = yaml.safe_load(WF.read_text())
    steps = wf["jobs"]["resolve"]["steps"]
    return next(s["run"] for s in steps if s.get("id") == "r")


def run_step(tmp_path, stdout: str, rc: int):
    stub = tmp_path / "bin"
    stub.mkdir()
    (tmp_path / "out.txt").write_text(stdout)
    py = stub / "python3"
    py.write_text(f'#!/bin/sh\ncat "{tmp_path / "out.txt"}"\nexit {rc}\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "gh_output"
    summ = tmp_path / "gh_summary"
    out.write_text("")
    summ.write_text("")
    script = tmp_path / "step.sh"
    script.write_text(resolve_script())
    env = dict(os.environ, PATH=f"{stub}{os.pathsep}{os.environ['PATH']}",
               GITHUB_OUTPUT=str(out), GITHUB_STEP_SUMMARY=str(summ))
    r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
                       env=env, capture_output=True, text=True, timeout=30)
    lines = out.read_text().splitlines()
    return r, lines


@pytest.mark.parametrize("rc,cmp,contains", [(0, "ahead", "yes"), (1, "diverged", "no")])
def test_step_survives_resolver_rc_and_writes_rc_once(tmp_path, rc, cmp, contains):
    r, lines = run_step(tmp_path, GOOD.format(cmp=cmp, contains=contains), rc)
    assert r.returncode == 0, r.stderr
    rcs = [l for l in lines if l.startswith("rc=")]
    assert rcs == [f"rc={rc}"]
    assert f"fork_sha={'b' * 40}" in lines and "release_version=0.11.1" in lines


def test_could_not_measure_writes_rc3_once(tmp_path):
    r, lines = run_step(tmp_path, "", 3)
    assert r.returncode == 0
    assert [l for l in lines if l.startswith("rc=")] == ["rc=3"]


def test_bad_value_is_could_not_measure_not_a_second_rc(tmp_path):
    bad = GOOD.format(cmp="ahead", contains="yes").replace("FORK=POWERFULMOVES/PMOVES-Archon", "FORK=evil/repo")
    r, lines = run_step(tmp_path, bad, 0)
    assert [l for l in lines if l.startswith("rc=")] == ["rc=3"]
    assert not any(l.startswith("fork=") for l in lines)
