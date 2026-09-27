"""Producers vs consumers in the Pattern-B secrets funnel.

2026-09 incident: sync-secrets-local.yml only ever succeeded on the Linux
ai-lab runners (spark, b850). On the Windows runners (4090, 5090) its
``shell: bash`` steps ran under WSL bash and died on the mangled script path
(``/bin/bash: C:actions-runner-win_work_temp....sh: No such file or
directory``), while the consumer script's recovery hint pointed at a single
producer. These tests pin:

* the recovery hints in ``pull_chit_bundle.sh`` name the ordered producer list
  (default ``spark,b850``), honouring the list override and the legacy
  singular override -- exercised by RUNNING the script against a fake ``gh``;
* the workflow's resolve-targets step refuses a consumer target before any
  job is scheduled -- exercised by RUNNING the step's own script;
* the matrix job's first step is a Windows fail-fast guard;
* the three places that name the producers cannot drift apart;
* a root-owned (here: read-only) provenance marker left by a producer-node
  runner no longer defeats the consumer's marker write.

No network, no real credential: ``gh`` is a stub on PATH.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_PULL = _ROOT / "pmoves" / "scripts" / "pull_chit_bundle.sh"
_WORKFLOW = _ROOT / ".github" / "workflows" / "sync-secrets-local.yml"
_CHECK = _ROOT / "pmoves" / "tools" / "chit_provenance_check.py"

_SECRET_SENTINEL = "SENTINEL-VALUE-MUST-NOT-PRINT"


# --------------------------------------------------------------------------
# pull_chit_bundle.sh, run for real against a stub gh
# --------------------------------------------------------------------------

def _stub_bin(tmp_path: Path, *, run_id: str, artifact: str) -> Path:
    """A fake ``gh`` + ``python`` shim. ``run_id``/``artifact`` empty => the
    corresponding query returns nothing (no runs / no unexpired artifact)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    bundle = json.dumps({"version": "cgp-1", "points": [
        {"label": "A_KEY", "value": _SECRET_SENTINEL, "anchor": 0, "encoding": "hex"}]})
    gh = bindir / "gh"
    gh.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        case "$1 $2" in
          "run list") printf '%s\\n' '{run_id}' ;;
          "run download")
            dir=""; while [ $# -gt 0 ]; do [ "$1" = "--dir" ] && dir="$2"; shift; done
            mkdir -p "$dir/x"; printf '%s' '{bundle}' > "$dir/x/env.cgp.json" ;;
          api*) printf '%s\\n' '{artifact}' ;;
          *) echo "unexpected gh $*" >&2; exit 9 ;;
        esac
        """), encoding="utf-8")
    py = bindir / "python"
    py.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    for f in (gh, py):
        f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_pull(tmp_path: Path, extra_env: dict | None = None, *, umask: int | None = None,
              extra_stubs: dict | None = None, **stub) -> subprocess.CompletedProcess:
    bindir = _stub_bin(tmp_path, **stub)
    for name, body in (extra_stubs or {}).items():
        _write_exec(bindir / name, body)
    env = {
        k: v for k, v in os.environ.items()
        if k not in {"PMOVES_BUNDLE_PRODUCERS", "PMOVES_BUNDLE_PRODUCER",
                     "CHIT_EXPORT_PATH", "APPDATA", "PMOVES_REPO"}
    }
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["CHIT_EXPORT_PATH"] = str(tmp_path / "cfg" / "chit" / "env.cgp.json")
    env["PMOVES_NODE"] = "b850"
    env.update(extra_env or {})
    preexec = (lambda: os.umask(umask)) if umask is not None else None
    return subprocess.run(["bash", str(_PULL)], env=env, capture_output=True,
                          text=True, timeout=60, preexec_fn=preexec)


@pytest.mark.parametrize("stub", [
    {"run_id": "", "artifact": ""},          # no successful run at all
    {"run_id": "123", "artifact": ""},       # run exists, artifact expired
])
def test_recovery_hint_names_the_default_producer_list(tmp_path, stub):
    r = _run_pull(tmp_path, **stub)
    assert r.returncode == 1
    assert "-f targets=spark,b850" in r.stdout
    assert "Linux producers (spark,b850)" in r.stdout
    assert "targets=5090" not in r.stdout and "targets=4090" not in r.stdout


@pytest.mark.parametrize("env,expected", [
    ({"PMOVES_BUNDLE_PRODUCERS": "b850"}, "b850"),
    ({"PMOVES_BUNDLE_PRODUCER": "spark"}, "spark"),  # legacy singular override
    ({"PMOVES_BUNDLE_PRODUCERS": "b850,spark", "PMOVES_BUNDLE_PRODUCER": "x"}, "b850,spark"),
])
def test_recovery_hint_honours_the_overrides(tmp_path, env, expected):
    r = _run_pull(tmp_path, env, run_id="", artifact="")
    assert r.returncode == 1
    assert f"-f targets={expected}\n" in r.stdout


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root ignores the read-only bit this test relies on")
def test_a_read_only_provenance_marker_is_replaced_not_refused(tmp_path):
    """On B850 the runner container (root) left env.cgp.json.provenance
    root-owned 0600, and `secrets-pull` printed 'Permission denied' while
    the marker kept naming the runner's artifact. A read-only file in a
    user-owned directory reproduces the same refusal without root."""
    dest = tmp_path / "cfg" / "chit" / "env.cgp.json"
    dest.parent.mkdir(parents=True)
    marker = Path(str(dest) + ".provenance")
    marker.write_text("source=ci\nartifact=chit-bundle-b850-OLD\n", encoding="utf-8")
    marker.chmod(0o400)
    dest.write_text("{}", encoding="utf-8")
    dest.chmod(0o400)  # a read-only old bundle must be replaced too

    r = _run_pull(tmp_path, run_id="123", artifact="chit-bundle-b850-123")

    assert r.returncode == 0, r.stdout + r.stderr
    assert "Permission denied" not in r.stdout + r.stderr
    assert "artifact=chit-bundle-b850-123" in marker.read_text(encoding="utf-8")
    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert _SECRET_SENTINEL not in r.stdout + r.stderr, "payload printed"
    assert not list(dest.parent.glob("*.tmp.*")), "staging file left behind"


# --------------------------------------------------------------------------
# sync-secrets-local.yml
# --------------------------------------------------------------------------

def _workflow() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_resolve_targets(tmp_path: Path, targets: str,
                         producers: str | None = None) -> tuple[subprocess.CompletedProcess, str]:
    wf = _workflow()
    step = next(s for s in wf["jobs"]["resolve-targets"]["steps"] if s.get("id") == "set")
    script = step["run"].replace("${{ runner.debug }}", "0")
    assert "${{" not in script, "unhandled expression in the resolve step"
    out = tmp_path / "github_output"
    out.write_text("", encoding="utf-8")
    env = {**os.environ, "INPUT_TARGETS": targets,
           "PRODUCER_TARGETS": (wf["env"]["PRODUCER_TARGETS"]
                                if producers is None else producers),
           "GITHUB_OUTPUT": str(out)}
    r = subprocess.run(["bash", "-c", script], env=env, capture_output=True,
                       text=True, timeout=60)
    return r, out.read_text(encoding="utf-8")


def test_producers_resolve_to_a_matrix(tmp_path):
    r, out = _run_resolve_targets(tmp_path, "spark, b850")
    assert r.returncode == 0, r.stderr
    assert out.strip() == 'matrix={"target": ["spark", "b850"]}'


@pytest.mark.parametrize("targets", ["5090", "4090", "spark,5090", "z890"])
def test_a_consumer_target_is_refused_before_scheduling(tmp_path, targets):
    r, out = _run_resolve_targets(tmp_path, targets)
    assert r.returncode != 0
    assert out == "", "a matrix was emitted for a consumer target"
    assert "::error" in r.stderr
    assert "targets=spark,b850" in r.stderr
    assert "make -C pmoves secrets-pull" in r.stderr


@pytest.mark.parametrize("targets", ['spark";id;"', "$(id)", "Spark"])
def test_the_injection_safe_label_check_still_runs_first(tmp_path, targets):
    r, out = _run_resolve_targets(tmp_path, targets)
    assert r.returncode != 0 and out == ""
    assert "invalid target labels" in r.stderr


def test_the_first_matrix_step_fails_fast_on_windows():
    steps = _workflow()["jobs"]["sync-secrets"]["steps"]
    first = steps[0]
    assert first.get("if") == "runner.os == 'Windows'"
    # cmd.exe is the one shell every Windows runner is guaranteed to have.
    assert first.get("shell") == "cmd"
    assert "::error" in first["run"] and "secrets-pull" in first["run"]
    assert re.search(r"exit /b 1\s*$", first["run"])
    # No other step may run before it, and nothing after it may be Windows-only.
    assert steps[1]["name"] == "Checkout"


def test_the_producer_lists_cannot_drift():
    """Workflow allowlist, puller default and provenance-check default are the
    same ordered list. If one moves alone, a hint names a target the
    workflow refuses. Enrolling a new Linux producer means editing all three."""
    wf_list = _workflow()["env"]["PRODUCER_TARGETS"]
    pull_src = _PULL.read_text(encoding="utf-8")
    m = re.search(r'^KNOWN_PRODUCERS="([^"]*)"$', pull_src, re.M)
    assert m, "pull_chit_bundle.sh no longer declares KNOWN_PRODUCERS"
    assert ('PRODUCERS="${PMOVES_BUNDLE_PRODUCERS:-${PMOVES_BUNDLE_PRODUCER:-$KNOWN_PRODUCERS}}"'
            in pull_src), "the puller default no longer derives from KNOWN_PRODUCERS"
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cpc_drift", _CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "or KNOWN_PRODUCERS)" in _CHECK.read_text(encoding="utf-8")
    assert m.group(1) == wf_list == mod.KNOWN_PRODUCERS == "spark,b850"


# --------------------------------------------------------------------------
# Review round 1 (#3186): stage perms, cleanup, dedupe, fail-closed, warnings
# --------------------------------------------------------------------------

_linux_stat = pytest.mark.skipif(
    not sys.platform.startswith("linux") or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="uses GNU stat -c; root ignores modes")


@_linux_stat
def test_stage_files_are_created_0600_even_under_umask_022(tmp_path):
    """A stubbed chmod records each stage file's mode BEFORE it changes it,
    i.e. the mode it was created with. Under umask 022 a plain cp creates
    0644 -- briefly world-readable cleartext, since CGP is not encryption."""
    real_chmod = shutil.which("chmod")
    log = tmp_path / "chmod.log"
    stub = (f'#!/usr/bin/env bash\n'
            f'for a in "$@"; do case "$a" in *.tmp.*) '
            f'printf "%s %s\\n" "$a" "$(stat -c %a -- "$a")" >> "{log}";; esac; done\n'
            f'exec "{real_chmod}" "$@"\n')
    r = _run_pull(tmp_path, umask=0o022, extra_stubs={"chmod": stub},
                  run_id="123", artifact="chit-bundle-b850-123")
    assert r.returncode == 0, r.stdout + r.stderr
    seen = [ln.rsplit(" ", 1) for ln in log.read_text(encoding="utf-8").splitlines()]
    names = {Path(p).name.split(".tmp.")[0] for p, _ in seen}
    assert names == {"env.cgp.json", "env.cgp.json.provenance"}, seen
    assert all(mode == "600" for _, mode in seen), seen


def test_a_failed_rename_leaves_no_stage_file(tmp_path):
    """mv of the bundle fails -> set -e aborts -> the EXIT trap must remove
    the staged copy, and the old bundle must be untouched."""
    dest = tmp_path / "cfg" / "chit" / "env.cgp.json"
    dest.parent.mkdir(parents=True)
    dest.write_text('{"old": 1}', encoding="utf-8")
    r = _run_pull(tmp_path, extra_stubs={"mv": "#!/usr/bin/env bash\nexit 1\n"},
                  run_id="123", artifact="chit-bundle-b850-123")
    assert r.returncode != 0
    assert not list(dest.parent.glob("*.tmp.*")), list(dest.parent.iterdir())
    assert dest.read_text(encoding="utf-8") == '{"old": 1}'
    assert _SECRET_SENTINEL not in r.stdout + r.stderr


def test_duplicate_targets_schedule_one_job(tmp_path):
    r, out = _run_resolve_targets(tmp_path, "b850,b850")
    assert r.returncode == 0, r.stderr
    assert out.strip() == 'matrix={"target": ["b850"]}'
    r, out = _run_resolve_targets(tmp_path, "b850,spark,b850")
    assert out.strip() == 'matrix={"target": ["b850", "spark"]}'


@pytest.mark.parametrize("producers", ["", ",,", " ", "spark;id", "SPARK", "spark b850"])
def test_an_unreadable_allowlist_fails_closed(tmp_path, producers):
    r, out = _run_resolve_targets(tmp_path, "spark", producers=producers)
    assert r.returncode != 0
    assert out == "", "a matrix was emitted without a readable allowlist"


@pytest.mark.parametrize("env", [
    {"PMOVES_BUNDLE_PRODUCER": "5090"},
    {"PMOVES_BUNDLE_PRODUCERS": "spark,4090"},
])
def test_the_puller_warns_on_an_unknown_producer_label(tmp_path, env):
    r = _run_pull(tmp_path, env, run_id="", artifact="")
    assert "is not a known Linux producer" in r.stderr
    bad = (env.get("PMOVES_BUNDLE_PRODUCERS") or env["PMOVES_BUNDLE_PRODUCER"]).split(",")[-1]
    assert f"'{bad}'" in r.stderr
    # Non-fatal: the script still reaches its normal recovery hint.
    assert "gh workflow run" in r.stdout


def test_the_puller_is_silent_for_known_producers(tmp_path):
    r = _run_pull(tmp_path, run_id="", artifact="")
    assert "not a known Linux producer" not in r.stderr


# --------------------------------------------------------------------------
# infra.mk gha-runner-up: pull before up, RUNNER_SKIP_PULL escape hatch
# --------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("skip", ["", "1"])
def test_gha_runner_up_pulls_first_or_skips_on_request(tmp_path, skip):
    """Stub docker (pull fails) and gh (no credential), so nothing real is
    touched. Without the hatch the target must stop at the failed pull and
    name RUNNER_SKIP_PULL; with it, it must not pull and must warn."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "docker.log"
    _write_exec(bindir / "docker",
                f'#!/usr/bin/env bash\necho "$*" >> "{log}"\n'
                'case "$*" in *" pull"*) exit 1;; esac\nexit 0\n')
    _write_exec(bindir / "gh", "#!/usr/bin/env bash\nexit 1\n")
    (tmp_path / "home").mkdir()
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
           "HOME": str(tmp_path / "home"), "GITHUB_PAT": ""}
    r = subprocess.run(
        ["make", "-f", "mk/infra.mk", "gha-runner-up", "RUNNER_NODE=stubnode",
         f"RUNNER_SKIP_PULL={skip}"],
        cwd=_ROOT / "pmoves", env=env, capture_output=True, text=True, timeout=60)
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    assert r.returncode != 0  # stub gh never yields a credential
    assert " up " not in calls + " ", calls
    if skip:
        assert " pull" not in calls
        assert "RUNNER_SKIP_PULL=1: starting on the CACHED image" in r.stdout
    else:
        assert calls.strip().endswith("pull")
        assert "runner image pull failed" in r.stdout
        assert "RUNNER_SKIP_PULL=1" in r.stdout
        assert "Resolving runner credential" not in r.stdout, "continued past a failed pull"
