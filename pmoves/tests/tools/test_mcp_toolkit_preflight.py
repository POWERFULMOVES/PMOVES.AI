"""Offline tests for the MCP Toolkit gateway preflight.

Docker is stubbed so these run on a runner with no daemon and on any arch; what
is under test is the verdict logic and — most importantly — that an
unmeasurable gateway exits 3 rather than 0.

Context: mcp-toolkit-gateway-listen.sh checked Docker and the profile, then
started a gateway. It never checked the SECRET RESOLVER. On 2026-08-28 the
resolver was wedged (`ResolverService/GetSecrets: deadline_exceeded`, surviving
a Docker Desktop restart) and the gateway started regardless, serving
`github-official` with an empty token. Every call returned 401, and nothing at
start time explained why.

Stubbing `_docker` rather than PATH follows docker_host_policy_check.py, and is
required on Windows besides: Git Bash resolves `docker` to `docker.exe` and
never sees an extensionless stub, so a PATH stub silently exercises the REAL
daemon — which is exactly how an earlier draft of this file "passed" against
live profiles instead of its fixture.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "mcp_toolkit_preflight.py"
LISTENER = REPO_ROOT / "pmoves" / "scripts" / "mcp-toolkit-gateway-listen.sh"

spec = importlib.util.spec_from_file_location("mcp_toolkit_preflight", MODULE)
assert spec and spec.loader
pf = importlib.util.module_from_spec(spec)
sys.modules["mcp_toolkit_preflight"] = pf
spec.loader.exec_module(pf)


PROFILE_LS = "ID\tName\ndefault\tDefault\npmoves_5090_web\tPMOVES-5090-web\n"
PROFILE_SHOW = """
version: 1
id: pmoves_5090_web
servers:
    - type: image
      snapshot:
        server:
            name: github-official
            secrets:
                - name: github.personal_access_token
                  env: GITHUB_PERSONAL_ACCESS_TOKEN
    - type: image
      snapshot:
        server:
            name: context7
"""
WEDGED = (
    'deadline_exceeded: Post "http://unix/resolver.v1.ResolverService/GetSecrets": '
    "net/http: timeout awaiting response headers"
)

# Plain `docker mcp secret ls` prints a HEADERLESS, per-column-TRUNCATED table
# of `ID  PROVIDER` — vendor source cmd/docker-mcp/commands/secret.go calls
# `formatting.PrettyPrintTable(rows, []int{40, 120})` with no header argument,
# and the IDs are namespace-qualified. Both properties make that form unusable
# for a name comparison, which is why the coverage check uses --json. Kept
# accurate here so a fixture cannot flatter the parser.
SECRETS_TABLE = "docker/mcp/e2b.api_key                    docker-pass\n"

# `docker mcp secret ls --json`, from the same writer: a list of
# {"name": ..., "provider": ...}. There is no value field in the emitted struct
# at all, at either verbosity.
SECRETS_JSON_WITH_GITHUB = (
    '[\n  {\n    "name": "github.personal_access_token",\n'
    '    "provider": "docker-pass"\n  }\n]\n'
)
SECRETS_JSON_WITHOUT_GITHUB = (
    '[\n  {\n    "name": "e2b.api_key",\n    "provider": "docker-pass"\n  }\n]\n'
)


def _fake_docker(
    monkeypatch,
    *,
    secrets,
    profiles: str = PROFILE_LS,
    secrets_json: str | None = SECRETS_JSON_WITH_GITHUB,
):
    """Stub `_docker`. `secrets_json=None` means `--json` could not be run."""

    def fake(*args: str, timeout: int = 45) -> str:
        joined = " ".join(args)
        if joined.startswith("mcp profile ls"):
            return profiles
        if joined.startswith("mcp secret ls --json"):
            if secrets_json is None:
                raise pf.Unmeasured("docker mcp secret ls --json failed: unknown flag")
            return secrets_json
        if joined.startswith("mcp secret ls"):
            if secrets is None:
                raise pf.Unmeasured("docker mcp secret ls failed: resolver down")
            return secrets
        if joined.startswith("mcp profile show"):
            return PROFILE_SHOW
        return ""

    monkeypatch.setattr(pf, "_docker", fake)


def test_a_healthy_gateway_passes(monkeypatch):
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE)
    assert pf.main(["--profile", "pmoves_5090_web"]) == 0


def test_a_wedged_resolver_exits_1(monkeypatch):
    """A measured failure, distinct from an unmeasurable one."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    assert pf.main(["--profile", "pmoves_5090_web"]) == 1


def test_a_wedged_resolver_names_the_servers_at_risk(monkeypatch, capsys):
    """A generic warning is not actionable; the operator needs the server list."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    pf.main(["--profile", "pmoves_5090_web"])
    err = capsys.readouterr().err
    assert "github-official" in err, err
    assert "github.personal_access_token" in err, err


def test_a_server_with_no_secret_is_not_reported(monkeypatch):
    """context7 declares none, so it is not 'at risk' and must not be listed."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    rows = pf.servers_requiring_secrets("pmoves_5090_web")
    assert [r["server"] for r in rows] == ["github-official"]


def test_a_secret_ls_failure_is_a_finding_not_an_absence(monkeypatch):
    """`secret ls` failing IS the resolver reporting itself down.

    Docker ran; the answer was "broken". Treating that as unmeasurable would
    downgrade a real finding into a shrug.
    """
    _fake_docker(monkeypatch, secrets=None)
    assert pf.resolver_healthy() is False


def test_a_missing_profile_is_unmeasured_not_a_pass(monkeypatch):
    """Exit 3. The gateway's readiness was never established."""
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, profiles="ID\tName\ndefault\tD\n")
    assert pf.main(["--profile", "pmoves_5090_web"]) == 3


def test_no_docker_at_all_is_unmeasured(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda _: None)
    assert pf.main(["--profile", "pmoves_5090_web"]) == 3


def test_json_mode_says_whether_it_measured(monkeypatch, capsys):
    """Machine-readable callers must be able to tell 3 from 0 without the code."""
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, profiles="ID\tName\ndefault\tD\n")
    pf.main(["--profile", "pmoves_5090_web", "--json"])
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["measured"] is False
    assert "not imported" in payload["reason"]


def test_the_listener_actually_invokes_the_preflight():
    """Wiring assertion: a gate nothing calls is decoration.

    The listener is what `make -C pmoves mcp-toolkit-gateway-start` runs, so the
    preflight has to be on that path or it protects nothing.
    """
    body = LISTENER.read_text(encoding="utf-8")
    assert "mcp_toolkit_preflight" in body, (
        "mcp-toolkit-gateway-listen.sh does not call the preflight"
    )


# ---------------------------------------------------------------------------
# Codex P1 (#2806): `ok` was `resolver_healthy()` alone. The function computed
# `servers_requiring_secrets(profile)` — exactly the list that matters — and
# then never consulted it. A resolver that answers over a store missing a
# required secret reported ok:true, strict startup and CI passed, and the
# server still came up uncredentialed and 401'd at call time. That is the
# precise failure the module's own docstring says it exists to catch.
# ---------------------------------------------------------------------------


def test_a_healthy_resolver_missing_a_required_secret_is_NOT_ok(monkeypatch):
    """The regression test for the P1. Resolver up, github secret absent.

    Against the pre-fix code this returns ok=True, because `ok` never looked at
    the at-risk list it had just built.
    """
    _fake_docker(
        monkeypatch,
        secrets=SECRETS_TABLE,
        secrets_json=SECRETS_JSON_WITHOUT_GITHUB,
    )
    verdict = pf.check("pmoves_5090_web")
    assert verdict["ok"] is False, verdict
    assert verdict["resolver_healthy"] is True, verdict
    assert [
        (r["server"], r["secret"]) for r in verdict["missing_secrets"]
    ] == [("github-official", "github.personal_access_token")]


def test_a_missing_required_secret_exits_1(monkeypatch):
    """Measured failure, so exit 1 — not 3, and emphatically not 0."""
    _fake_docker(
        monkeypatch,
        secrets=SECRETS_TABLE,
        secrets_json=SECRETS_JSON_WITHOUT_GITHUB,
    )
    assert pf.main(["--profile", "pmoves_5090_web"]) == 1


def test_a_missing_required_secret_names_the_server_and_the_secret_NAME(
    monkeypatch, capsys
):
    """Same actionability bar as the wedged-resolver path."""
    _fake_docker(
        monkeypatch,
        secrets=SECRETS_TABLE,
        secrets_json=SECRETS_JSON_WITHOUT_GITHUB,
    )
    pf.main(["--profile", "pmoves_5090_web"])
    err = capsys.readouterr().err
    assert "github-official" in err, err
    assert "github.personal_access_token" in err, err


def test_unenumerable_secret_store_is_unmeasured_not_nothing_missing(monkeypatch):
    """`secret ls --json` erroring must not collapse into "nothing is missing".

    This is the shape of the original defect one level down: an enumeration
    that fails, read as an empty set of problems. Exit 3 — NOT a pass.
    """
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, secrets_json=None)
    with pytest.raises(pf.Unmeasured):
        pf.check("pmoves_5090_web")
    assert pf.main(["--profile", "pmoves_5090_web"]) == 3


def test_unenumerable_secret_store_json_mode_reports_unmeasured(monkeypatch, capsys):
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, secrets_json=None)
    assert pf.main(["--profile", "pmoves_5090_web", "--json"]) == 3
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["measured"] is False


def test_namespaced_store_names_match_bare_profile_names(monkeypatch):
    """The store may report `docker/mcp/github.personal_access_token`.

    `docker mcp secret ls --json` runs the ID through `secret.StripNamespace`,
    but the table form does not, and the realm prefix has changed shape before.
    Comparing on the trailing segment keeps a namespaced store from reading as
    a store missing everything.
    """
    _fake_docker(
        monkeypatch,
        secrets=SECRETS_TABLE,
        secrets_json=(
            '[{"name": "docker/mcp/github.personal_access_token", '
            '"provider": "docker-pass"}]'
        ),
    )
    verdict = pf.check("pmoves_5090_web")
    assert verdict["ok"] is True, verdict
    assert verdict["missing_secrets"] == []


def test_an_empty_secret_store_is_a_real_answer_not_an_error(monkeypatch):
    """`[]` is a legitimate enumeration: the store is empty, so all are missing."""
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, secrets_json="[]\n")
    verdict = pf.check("pmoves_5090_web")
    assert verdict["ok"] is False, verdict
    assert len(verdict["missing_secrets"]) == 1


def test_unparseable_secret_ls_json_is_unmeasured(monkeypatch):
    """A CLI whose --json output we cannot read is an absence of measurement.

    Silently parsing zero names out of it would report every required secret as
    missing — a confident, wrong, and unactionable verdict.
    """
    _fake_docker(monkeypatch, secrets=SECRETS_TABLE, secrets_json="not json at all")
    with pytest.raises(pf.Unmeasured):
        pf.check("pmoves_5090_web")


def test_a_wedged_resolver_does_not_also_claim_secrets_are_missing(monkeypatch):
    """One finding, not two.

    The store cannot be enumerated through a wedged resolver, so reporting
    "github.personal_access_token is missing" would be a guess dressed as a
    measurement.
    """
    _fake_docker(monkeypatch, secrets=WEDGED)
    verdict = pf.check("pmoves_5090_web")
    assert verdict["ok"] is False
    assert verdict["resolver_healthy"] is False
    assert verdict["missing_secrets"] is None, verdict


# ---------------------------------------------------------------------------
# CodeQL alert 376 (#2806): the at-risk report prints `row['secret']`, which is
# a secret NAME read from the profile. Vendor pkg/catalog/types.go defines
# `Secret{Name, Env}` with no value field, so a value structurally cannot reach
# this sink through `docker mcp profile show`. The guard below is not a
# rename-to-dodge — it is a runtime barrier for the one input the vendor schema
# does not constrain: a hand-authored profile.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "github.personal_access_token",
        "hostinger-mcp-server.api_token",
        "docker/mcp/dockerhub.pat_token",
        "e2b.api_key",
    ],
)
def test_real_secret_names_survive_the_report_guard(name):
    """The guard must not mangle the names operators actually have to act on."""
    assert pf._reportable_secret_name(name) == name


@pytest.mark.parametrize(
    "value",
    [
        "ghp_" + "A" * 90,                      # long: a PAT, not a name
        "-----BEGIN OPENSSH PRIVATE KEY-----",  # whitespace + non-name charset
        "eyJhbGciOi.JIUzI1NiIs InR5cCI6",       # embedded space
        "",
    ],
)
def test_value_shaped_input_is_not_echoed(value):
    """Anything not provably name-shaped is replaced rather than printed."""
    assert pf._reportable_secret_name(value) == "<non-conforming-secret-name>"


def test_a_value_shaped_profile_entry_is_redacted_in_the_report(monkeypatch, capsys):
    """End-to-end: a profile carrying a value where a name belongs must not
    print it, no matter how it got there."""
    leaked = "ghp_" + "B" * 90
    profile_show = PROFILE_SHOW.replace("github.personal_access_token", leaked)

    def fake(*args: str, timeout: int = 45) -> str:
        joined = " ".join(args)
        if joined.startswith("mcp profile ls"):
            return PROFILE_LS
        if joined.startswith("mcp secret ls --json"):
            return SECRETS_JSON_WITHOUT_GITHUB
        if joined.startswith("mcp secret ls"):
            return WEDGED
        if joined.startswith("mcp profile show"):
            return profile_show
        return ""

    monkeypatch.setattr(pf, "_docker", fake)
    pf.main(["--profile", "pmoves_5090_web"])
    out = capsys.readouterr()
    assert leaked not in out.err, out.err
    assert leaked not in out.out, out.out
    assert "<non-conforming-secret-name>" in out.err, out.err


def test_json_mode_also_redacts_a_value_shaped_entry(monkeypatch, capsys):
    """--json is consumed by CI logs too; the guard cannot be text-mode only."""
    leaked = "ghp_" + "C" * 90
    profile_show = PROFILE_SHOW.replace("github.personal_access_token", leaked)

    def fake(*args: str, timeout: int = 45) -> str:
        joined = " ".join(args)
        if joined.startswith("mcp profile ls"):
            return PROFILE_LS
        if joined.startswith("mcp secret ls --json"):
            return SECRETS_JSON_WITHOUT_GITHUB
        if joined.startswith("mcp secret ls"):
            return SECRETS_TABLE
        if joined.startswith("mcp profile show"):
            return profile_show
        return ""

    monkeypatch.setattr(pf, "_docker", fake)
    pf.main(["--profile", "pmoves_5090_web", "--json"])
    out = capsys.readouterr().out
    assert leaked not in out, out


# ---------------------------------------------------------------------------
# Codex P1 (#2806): the listener invoked bare `python3`, which exits 127 on
# nodes where Python is `py -3` or lives only in .venv-pmoves, and fails on
# hosts whose system Python lacks PyYAML although the canonical venv has it.
# ---------------------------------------------------------------------------


def test_the_listener_uses_the_canonical_python_discovery():
    """Not a second convention. pm-python.sh is the ONE discovery."""
    body = LISTENER.read_text(encoding="utf-8")
    assert "pm-python.sh" in body, "listener does not source pm-python.sh"
    assert "pm_pick_python yaml" in body, (
        "listener must probe for PyYAML — the preflight imports yaml, so an "
        "interpreter without it is unequipped, not a preflight failure"
    )
    assert 'python3 "${PREFLIGHT_PY}"' not in body, (
        "bare python3 is the defect: exits 127 on Windows/py-3 nodes"
    )


def test_the_listener_maps_an_unrunnable_preflight_to_exit_3():
    """'Could not run the preflight at all' is exit-3 territory.

    Not a pass, and not the same bucket as a measured resolver failure — which
    is what a bare 127 landed in.
    """
    body = LISTENER.read_text(encoding="utf-8")
    assert "preflight_rc=3" in body, (
        "no interpreter must be mapped to the could-not-measure code, not to 1"
    )


# ---------------------------------------------------------------------------
# Behavioural tests for the listener, not just text assertions.
#
# The two above grep the script body, which is the pattern this file already
# had -- and it is a weak one: it proves the string is present, not that the
# branch runs. Given this whole PR is about checks that report success while
# doing nothing, the exit-code contract deserves to be executed.
#
# Linux/macOS only: the module docstring explains why a PATH stub for `docker`
# is not viable on Windows (Git Bash resolves `docker` to `docker.exe` and
# never sees an extensionless stub, so the stub would be bypassed and the REAL
# daemon exercised). Skipping is honest; a silently-bypassed stub would not be.
# ---------------------------------------------------------------------------

import os
import shutil as _shutil
import subprocess

_DOCKER_STUB = """#!/usr/bin/env bash
# Enough of `docker mcp` for the listener AND the preflight to reach a real
# verdict. A stub that only answered `version`/`profile ls` would leave the
# preflight unmeasured, and an unmeasured run cannot demonstrate the equipped
# path works.
case "$1 $2 $3 $4" in
  "mcp secret ls --json")
    printf '[{\\"name\\":\\"github.personal_access_token\\",\\"provider\\":\\"docker-pass\\"}]\\n'
    exit 0 ;;
esac
case "$1 $2 $3" in
  "mcp profile ls") printf 'ID\\tNAME\\npmoves_5090_web\\tPMOVES\\n'; exit 0 ;;
  "mcp secret ls") printf 'docker/mcp/github.personal_access_token  docker-pass\\n'; exit 0 ;;
  "mcp profile show") cat "$STUB_PROFILE_YAML"; exit 0 ;;
esac
case "$1 $2" in
  "mcp version") exit 0 ;;
esac
exit 0
"""


@pytest.fixture()
def listener_env(tmp_path):
    """PATH with a stubbed `docker`, and a token already set.

    MCP_GATEWAY_AUTH_TOKEN is pre-set on purpose: without it the script
    generates one and APPENDS it to the repo's shared env file, which a test
    must never write to.
    """
    if sys.platform.startswith("win"):
        pytest.skip("PATH stubs for `docker` are bypassed under Git Bash")
    if not _shutil.which("bash"):
        pytest.skip("bash not available")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "docker"
    stub.write_text(_DOCKER_STUB, encoding="utf-8")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["MCP_GATEWAY_AUTH_TOKEN"] = "test-token-not-a-real-credential"
    env["PMOVES_MCP_PROFILE_ID"] = "pmoves_5090_web"
    profile_yaml = tmp_path / "profile.yaml"
    profile_yaml.write_text(PROFILE_SHOW, encoding="utf-8")
    env["STUB_PROFILE_YAML"] = str(profile_yaml)
    return env


def _run_listener(env, extra=None):
    return subprocess.run(
        ["bash", str(LISTENER), "--foreground"],
        env={**env, **(extra or {})},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_no_pyyaml_interpreter_is_reported_as_unmeasured_not_as_a_failure(
    listener_env,
):
    """The 127 case, end to end.

    PMOVES_PYTHON pinned to something that cannot `import yaml` is exactly the
    documented node class the bare `python3` call broke on. It must surface as
    exit 3 ("could not measure"), not as exit 1 alongside a real resolver
    outage.
    """
    proc = _run_listener(listener_env, {"PMOVES_PYTHON": "/bin/false"})
    assert "preflight exit 3" in proc.stderr, proc.stderr
    assert "no python with PyYAML" in proc.stderr, proc.stderr
    assert "NOT a pass" in proc.stderr, proc.stderr


def test_strict_mode_refuses_to_start_when_the_preflight_could_not_run(
    listener_env,
):
    """Non-strict start-anyway is deliberate; strict must actually refuse.

    Before this change an interpreter-less node produced a bare 127 that
    strict mode rejected as though the gateway were unhealthy, while non-strict
    launched the gateway unchecked. Both halves are now named.
    """
    proc = _run_listener(
        listener_env, {"PMOVES_PYTHON": "/bin/false", "PMOVES_MCP_STRICT": "1"}
    )
    assert proc.returncode == 1, (proc.returncode, proc.stderr)
    assert "refusing to start" in proc.stderr, proc.stderr
    assert "preflight exit 3" in proc.stderr, proc.stderr
    # The REASON, not just the code: the pre-fix listener ignores
    # PMOVES_PYTHON entirely, so a returncode-only assertion would pass
    # against it and prove nothing.
    assert "no python with PyYAML" in proc.stderr, proc.stderr


def test_a_missing_preflight_tool_is_also_unmeasured_under_strict(
    listener_env, tmp_path
):
    """A gate that is absent is an unmeasured gateway, not a clean one.

    This branch used to warn and start unchecked even under
    PMOVES_MCP_STRICT=1 — the same "no measurement read as a pass" shape.
    """
    fake_root = tmp_path / "pmoves"
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "tools").mkdir()
    copied = fake_root / "scripts" / LISTENER.name
    copied.write_text(LISTENER.read_text(encoding="utf-8"), encoding="utf-8")
    _shutil.copy(LISTENER.parent / "pm-python.sh", fake_root / "scripts")
    # tools/mcp_toolkit_preflight.py deliberately absent.
    proc = subprocess.run(
        ["bash", str(copied), "--foreground"],
        env={**listener_env, "PMOVES_MCP_STRICT": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1, (proc.returncode, proc.stderr)
    assert "preflight exit 3" in proc.stderr, proc.stderr
    assert "preflight tool missing" in proc.stderr, proc.stderr


def test_an_equipped_interpreter_actually_runs_the_preflight(listener_env):
    """pm-python.sh order is load-bearing, so assert the listener inherits it.

    A host whose system python lacks PyYAML while the canonical venv has it is
    one of the two node classes the bare `python3` call broke. Pin
    PMOVES_PYTHON to the running interpreter (which has yaml) and the preflight
    must actually execute — reaching a docker-measured verdict rather than the
    could-not-measure branch.
    """
    proc = _run_listener(listener_env, {"PMOVES_PYTHON": sys.executable})
    combined = proc.stdout + proc.stderr
    assert "no python with PyYAML" not in combined, combined
    assert "preflight tool missing" not in combined, combined
    # Reached a real verdict against the stub, rather than skipping the gate.
    assert "secret resolver responds" in combined, combined
    assert "preflight clean" in combined, combined
    assert "preflight exit" not in combined, combined
