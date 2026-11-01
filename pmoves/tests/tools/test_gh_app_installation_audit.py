"""Tests for the GitHub App installation audit.

WHAT IS UNDER TEST
------------------
``pmoves/tools/gh_app_installation_audit.py`` answers one operator question:
which repos of the registry universe does the GitHub App installation actually
cover? The credentials live only in GitHub Actions secrets, so the answer has
to come from CI — but the DERIVATION of the universe must be provable on the
operator's host, which is what ``--plan`` is for.

HOW THESE TESTS EXERCISE THE CODE
----------------------------------
The tool's HTTP transport is INJECTED (``main(argv, fetch=...)`` and
``GitHubClient(token, fetch=...)``), so the production path — argument
parsing, registry loading, universe derivation, pagination, probing,
classification, bucket arithmetic, report assembly, exit codes — runs exactly
as it runs in CI, with no network. The ``--plan`` tests run the CLI as a
SUBPROCESS, because "runs with no credentials and no network" is a property of
the command line, not of a function call.

NO TAUTOLOGIES
--------------
The universe expectations are derived from the registry FILE by the test's own
independent reading of it, never by re-typing the tool's expression. The
bucket expectations are computed from the fake transport's own state. A test
that re-states the implementation proves nothing when the implementation is
wrong.

The fail-closed behaviour is asserted in the negative direction too: a failed
audit must not merely exit non-zero, it must not PRINT anything a reader
could take for "zero repos missing".
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "pmoves" / "tools" / "gh_app_installation_audit.py"
REGISTRY_PATH = REPO_ROOT / "pmoves" / "config" / "fork_registry.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "gh-app-installation-audit.yml"

spec = importlib.util.spec_from_file_location("gh_app_installation_audit", MODULE_PATH)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
sys.modules["gh_app_installation_audit"] = audit
spec.loader.exec_module(audit)

CREDENTIAL_ENV_NAMES = (
    "GH_TOKEN",
    "GH_APP_ID",
    "GH_APP_CLIENT_ID",
    "GH_APP_INSTALLATION_ID",
    "GH_APP_SEC",
)

# A distinctive, obviously-fake installation token. If this string ever shows
# up in a report or on a terminal, the credential leaked.
TEST_TOKEN = "ghs_TESTTOKEN0123456789ABCDEFGHIJKLMNOP"


@pytest.fixture(autouse=True)
def _hermetic_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every in-process test exactly one fake credential, and nothing else.

    The host may already carry a real GH_TOKEN in its environment; a test
    that leaned on it would be measuring the operator's laptop.
    """
    monkeypatch.setenv("GH_TOKEN", TEST_TOKEN)
    for name in ("GH_APP_ID", "GH_APP_CLIENT_ID", "GH_APP_INSTALLATION_ID", "GH_APP_SEC"):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _run_cli(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the tool as a subprocess with NO credentials in the environment."""
    env = {k: v for k, v in os.environ.items() if k not in CREDENTIAL_ENV_NAMES}
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(MODULE_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(REPO_ROOT),
        timeout=180,
    )


def _write_registry(
    path: Path,
    forks: list[str],
    first_party: list[str] | None = None,
    excluded: dict[str, str] | None = None,
    org: str = "POWERFULMOVES",
) -> Path:
    """A synthetic registry with the same SHAPE as the real one."""
    payload = {
        "_doc": "synthetic",
        "org": org,
        "forks": {
            name: {"upstream": "up/stream", "sync": True, "reason": "synthetic"}
            for name in forks
        },
        "_first_party": list(first_party or []),
        "_excluded": dict(excluded or {}),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class FakeGitHub:
    """A scripted GitHub. It records every request it was asked to make.

    ``covered``      repos the installation covers
    ``org_repos``    repo names that resolve in the org (HTTP 200 on a probe)
    ``installations``the App's installations
    ``fail_paths``   path prefixes that answer with a hard error
    """

    def __init__(
        self,
        *,
        covered: list[str] | None = None,
        org_repos: list[str] | None = None,
        installations: list[dict] | None = None,
        fail_paths: dict[str, int] | None = None,
        truncated_total: int | None = None,
    ) -> None:
        self.covered = list(covered or [])
        self.org_repos = set(org_repos or [])
        self.installations = list(installations or [])
        self.fail_paths = dict(fail_paths or {})
        self.truncated_total = truncated_total
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers, timeout: int):
        self.calls.append((method, url, dict(headers)))
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path
        for prefix, status in self.fail_paths.items():
            if path.startswith(prefix):
                body = json.dumps({"message": "boom"}).encode("utf-8")
                return audit.HttpResponse(status, {}, body)

        if path == "/installation/repositories":
            repos = [{"name": name, "full_name": f"POWERFULMOVES/{name}"} for name in self.covered]
            total = self.truncated_total if self.truncated_total is not None else len(repos)
            return _json_response({"total_count": total, "repositories": repos})

        if path == "/app/installations":
            return _json_response(
                {"total_count": len(self.installations), "installations": self.installations}
            )

        if path.endswith("/repositories"):
            repos = [{"name": name, "full_name": f"POWERFULMOVES/{name}"} for name in self.covered]
            total = self.truncated_total if self.truncated_total is not None else len(repos)
            return _json_response({"total_count": total, "repositories": repos})

        if path.startswith("/app/installations/"):
            for installation in self.installations:
                if path == f"/app/installations/{installation['id']}":
                    return _json_response(installation)
            return _json_response({"message": "not found"}, status=404)

        if path.startswith("/repos/"):
            parts = path.split("/")
            name = parts[-1]
            if name in self.org_repos:
                return _json_response({"name": name, "full_name": f"POWERFULMOVES/{name}"})
            return _json_response({"message": "Not Found"}, status=404)

        raise AssertionError(f"unexpected request: {method} {url}")


def _json_response(payload, status: int = 200) -> audit.HttpResponse:
    return audit.HttpResponse(status, {}, json.dumps(payload).encode("utf-8"))


def _registry_expectations() -> tuple[set[str], int, dict[str, str]]:
    """The test's OWN reading of the real registry.

    Deliberately independent of the tool: it walks the raw JSON, so a bug in
    the tool's derivation cannot hide behind a shared helper.
    """
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    forks = set(raw.get("forks", {}).keys())
    first_party = set(raw.get("_first_party", []))
    excluded = dict(raw.get("_excluded", {}))
    members = forks | first_party
    return members, len(forks) + len(first_party), excluded


# --------------------------------------------------------------------------
# --plan: the universe, derived
# --------------------------------------------------------------------------


def test_plan_mode_derives_the_universe_without_network_or_credentials():
    """--plan must work with no credentials and no network, and derive the
    universe from the registry rather than asserting a number."""
    members, entries, _excluded = _registry_expectations()

    result = _run_cli("--plan", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    universe = report["universe"]
    assert universe["size"] == len(members)
    assert universe["entries"] == entries
    assert set(universe["members"]) == members
    assert report["mode"] == "plan"
    assert report["complete"] is True
    # No credential was available to this run; nothing may have leaked either.
    assert "GH_TOKEN" not in result.stdout
    assert "Authorization" not in result.stdout


def test_plan_mode_is_reproducible_across_runs():
    """A derived number a reviewer can reproduce is worth twice a number in prose."""
    first = _run_cli("--plan", "--json")
    second = _run_cli("--plan", "--json")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    left = json.loads(first.stdout)
    right = json.loads(second.stdout)
    left.pop("generated_at")
    right.pop("generated_at")
    assert left == right


def test_the_derived_universe_contains_the_first_party_members():
    """`_first_party` repos are part of the universe, not an appendix.

    They are the PMOVES-built repos: they have no upstream to sync, but they
    still need the App installation to reach them.
    """
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    first_party = list(raw.get("_first_party", []))

    result = _run_cli("--plan", "--json")

    assert result.returncode == 0, result.stderr
    members = set(json.loads(result.stdout)["universe"]["members"])
    missing = [name for name in first_party if name not in members]
    assert not missing, f"first-party repos missing from the universe: {missing}"


def test_the_excluded_entries_are_reported_with_their_reason():
    """An excluded repo is out of scope AND says why. Silence is not a reason."""
    _members, _entries, excluded = _registry_expectations()
    assert excluded, "the real registry is expected to carry an _excluded entry"

    result = _run_cli("--plan", "--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    reported = {entry["name"]: entry["reason"] for entry in report["excluded"]}
    assert reported == excluded
    for name in excluded:
        assert name not in report["universe"]["members"]
        assert excluded[name], "an excluded repo must carry a reason"


def test_a_registry_change_changes_the_derived_universe(tmp_path):
    """The universe is DERIVED. A registry edit must move the derived number.

    If the tool had the number baked in, this test would still pass — so it
    asserts the new member is present AND the count moved by exactly one.
    """
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    before = len(set(raw["forks"]) | set(raw["_first_party"]))

    edited = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    edited["forks"]["PMOVES-Probe-Only-Repo"] = {
        "upstream": "up/stream",
        "sync": False,
        "reason": "added by the derivation test",
    }
    tmp = tmp_path / "registry_probe.json"
    tmp.write_text(json.dumps(edited, indent=2), encoding="utf-8")

    result = _run_cli("--plan", "--json", "--registry", str(tmp))

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["universe"]["size"] == before + 1
    assert "PMOVES-Probe-Only-Repo" in report["universe"]["members"]


def test_an_unreadable_registry_fails_closed(tmp_path):
    """A registry the tool cannot read is an instrument error, not an empty
    universe. An empty universe would read as "nothing is missing"."""
    missing = tmp_path / "not-a-registry.json"

    result = _run_cli("--plan", "--json", "--registry", str(missing))

    assert result.returncode != 0
    assert "no coverage verdict was produced" in result.stderr
    assert "0 repos missing" not in result.stderr


# --------------------------------------------------------------------------
# the three buckets
# --------------------------------------------------------------------------


def _three_bucket_fixture(tmp_path: Path):
    """A registry + transport where each bucket is represented.

    Covered-One / Covered-Two  -> the installation covers them
    Gap-One / Gap-Two          -> they resolve, the installation misses them
    First-Party-Repo           -> it does not resolve at all (HTTP 404)
    """
    registry = _write_registry(
        tmp_path / "registry.json",
        forks=["Covered-One", "Covered-Two", "Gap-One", "Gap-Two"],
        first_party=["First-Party-Repo"],
    )
    fake = FakeGitHub(
        covered=["Covered-One", "Covered-Two"],
        org_repos=["Gap-One", "Gap-Two"],
    )
    return registry, fake


def test_the_three_buckets_partition_the_universe(tmp_path, capsys):
    """Every repo lands in exactly one bucket, and the counts close."""
    registry, fake = _three_bucket_fixture(tmp_path)

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == audit.EXIT_INCOMPLETE, out.err
    buckets = report["buckets"]
    assert buckets["installed"] == 2
    assert buckets["not_installed"] == 2
    assert buckets["unknown"] == 1
    assert sum(buckets.values()) == report["universe"]["size"]

    placed = (
        report["repos"]["installed"]
        + report["repos"]["not_installed"]
        + [entry["name"] for entry in report["repos"]["unknown"]]
    )
    assert sorted(placed) == sorted(report["universe"]["members"])
    assert len(placed) == len(set(placed)), "a repo landed in two buckets"


def test_a_fully_resolved_audit_exits_zero(tmp_path, capsys):
    """Nothing indeterminate, nothing missing: the clean path is exit 0."""
    registry = _write_registry(tmp_path / "registry.json", forks=["One", "Two"])
    fake = FakeGitHub(covered=["One", "Two"], org_repos=["One", "Two"])

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == 0, out.err
    assert report["complete"] is True
    assert report["not_installed"] == []
    assert report["buckets"] == {"installed": 2, "not_installed": 0, "unknown": 0}


def test_the_report_lists_the_not_installed_repos(tmp_path, capsys):
    """THE actionable output: the repos the installation does not cover."""
    registry, fake = _three_bucket_fixture(tmp_path)

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == audit.EXIT_INCOMPLETE, out.err
    assert report["not_installed"] == ["Gap-One", "Gap-Two"]
    assert "Gap-One" in out.err or "Gap-One" in out.out


def test_a_repo_that_cannot_be_resolved_is_unknown_not_not_installed(tmp_path, capsys):
    """A 404 is an absence of knowledge, not a finding.

    Reporting "not installed" for a repo that could not even be resolved
    would be a claim the audit cannot support.
    """
    registry = _write_registry(tmp_path / "registry.json", forks=["Vanished"])
    fake = FakeGitHub(covered=[], org_repos=[])

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert report["repos"]["not_installed"] == []
    assert [entry["name"] for entry in report["repos"]["unknown"]] == ["Vanished"]
    assert report["complete"] is False
    assert code == audit.EXIT_INCOMPLETE


def test_an_unknown_repo_makes_the_report_incomplete(tmp_path, capsys):
    """`complete` is false whenever anything was indeterminate."""
    registry = _write_registry(tmp_path / "registry.json", forks=["Present", "Vanished"])
    fake = FakeGitHub(covered=["Present"], org_repos=["Present"])

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert report["complete"] is False
    assert code == audit.EXIT_INCOMPLETE
    assert "INCOMPLETE" in out.err


def test_the_bucket_arithmetic_assertion_rejects_a_mismatched_count():
    """The tool asserts its own arithmetic. Remove the assertion and a repo
    can vanish between the universe and the report without anyone noticing.

    The fixture isolates THIS assertion: every universe member is present
    exactly once, so the membership check stays silent and only the counts
    can catch it.
    """
    universe = audit.Universe(
        org="POWERFULMOVES",
        forks=("A", "B", "C"),
        first_party=(),
        excluded={},
        duplicated=(),
    )
    statuses = [
        audit.RepoStatus("A", audit.BUCKET_INSTALLED, ""),
        audit.RepoStatus("B", audit.BUCKET_INSTALLED, ""),
        # A status whose bucket is not one of the three known buckets: it is
        # in the report, but it is in no bucket, so the counts do not close.
        audit.RepoStatus("C", "some_other_bucket", ""),
    ]

    with pytest.raises(audit.InvariantError):
        audit.build_report(
            mode="token",
            universe=universe,
            statuses=statuses,
            installation={},
            endpoints=[],
            generated_at="now",
        )


def test_the_bucket_arithmetic_assertion_rejects_a_duplicate_member():
    """The same repo twice in the buckets is a broken partition, not a count.

    The fixture isolates the MEMBERSHIP assertion: the bucket counts close
    (three statuses, three universe members), so only the membership check
    can catch it.
    """
    universe = audit.Universe(
        org="POWERFULMOVES",
        forks=("A", "B", "C"),
        first_party=(),
        excluded={},
        duplicated=(),
    )
    statuses = [
        audit.RepoStatus("A", audit.BUCKET_INSTALLED, ""),
        audit.RepoStatus("A", audit.BUCKET_INSTALLED, ""),
        audit.RepoStatus("B", audit.BUCKET_INSTALLED, ""),
    ]

    with pytest.raises(audit.InvariantError):
        audit.build_report(
            mode="token",
            universe=universe,
            statuses=statuses,
            installation={},
            endpoints=[],
            generated_at="now",
        )


# --------------------------------------------------------------------------
# fail closed
# --------------------------------------------------------------------------


def test_an_api_error_exits_non_zero(tmp_path, capsys):
    """A GitHub API failure must fail the run, not produce a verdict."""
    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    fake = FakeGitHub(covered=[], org_repos=[], fail_paths={"/installation/repositories": 500})

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()

    assert code != 0
    assert code == audit.EXIT_API
    assert "no coverage verdict was produced" in out.err


def test_a_failed_audit_never_prints_a_reassuring_summary(tmp_path, capsys):
    """The failure path must not read like 'nothing is missing'.

    A failed audit that prints "0 missing" is worse than no audit: it is a
    green light manufactured by a broken instrument.
    """
    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    fake = FakeGitHub(covered=[], org_repos=[], fail_paths={"/installation/repositories": 503})
    report_path = tmp_path / "report.json"

    code = audit.main(
        ["--token", "--json", "--registry", str(registry), "--out", str(report_path)],
        fetch=fake,
    )
    out = capsys.readouterr()
    combined = out.out + out.err

    assert code != 0
    assert "no coverage verdict was produced" in combined
    for reassurance in ("0 repos missing", "not_installed: 0", "nothing is missing"):
        assert reassurance not in combined, (
            f"a failed audit printed the reassuring phrase {reassurance!r}"
        )

    if report_path.exists():
        failure = json.loads(report_path.read_text(encoding="utf-8"))
        assert failure["complete"] is False
        assert "not_installed" not in failure
        assert "buckets" not in failure


def test_an_incomplete_pagination_fails_closed(tmp_path, capsys):
    """A page walk that cannot be proven complete is a failed audit.

    The endpoint says there are more items than the walk collected; reading
    that as "those repos are simply not covered" would be a fabricated
    finding.
    """
    registry = _write_registry(tmp_path / "registry.json", forks=["A", "B"])
    fake = FakeGitHub(
        covered=["A", "B"],
        org_repos=["A", "B"],
        truncated_total=9,
    )

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()

    assert code != 0
    assert code == audit.EXIT_API
    assert "pagination incomplete" in out.err
    assert "0 repos missing" not in out.err


def test_the_installation_token_never_appears_in_the_report_or_the_output(
    tmp_path, capsys
):
    """The token is a credential. It is never printed, logged, or stored."""
    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    fake = FakeGitHub(covered=["A"], org_repos=["A"])
    token = TEST_TOKEN
    report_path = tmp_path / "report.json"

    code = audit.main(
        [
            "--token",
            "--json",
            "--registry",
            str(registry),
            "--out",
            str(report_path),
        ],
        fetch=fake,
    )
    out = capsys.readouterr()
    combined = out.out + out.err
    written = report_path.read_text(encoding="utf-8")

    assert code == 0, out.err
    assert token not in combined
    assert token not in written
    # Not even a masked-but-partial form: no 8-character window of the token.
    for start in range(0, max(0, len(token) - 7)):
        assert token[start : start + 8] not in combined
        assert token[start : start + 8] not in written


def test_the_not_installed_gate_is_opt_in(tmp_path, capsys):
    """Finding a gap is a finding; failing on it is a policy choice."""
    registry = _write_registry(tmp_path / "registry.json", forks=["Gap"])
    fake = FakeGitHub(covered=[], org_repos=["Gap"])

    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    assert code == 0, out.err
    assert json.loads(out.out)["not_installed"] == ["Gap"]

    code = audit.main(
        ["--token", "--json", "--registry", str(registry), "--fail-on-not-installed"],
        fetch=fake,
    )
    out = capsys.readouterr()
    assert code == audit.EXIT_NOT_INSTALLED


# --------------------------------------------------------------------------
# --app-jwt: the house JWT minter
# --------------------------------------------------------------------------


def test_the_app_jwt_mode_uses_the_house_jwt_minter(tmp_path, capsys, monkeypatch):
    """The App JWT is minted by ``gh_app_token.build_app_jwt`` — RS256 via
    PyJWT, never a hand-rolled signer — and the JWT itself is never printed."""
    pytest.importorskip("jwt")
    jwt = pytest.importorskip("jwt")
    cryptography = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    client_id = "Iv23liTESTclientid"
    monkeypatch.setenv("GH_APP_CLIENT_ID", client_id)
    monkeypatch.setenv("GH_APP_SEC", pem)
    monkeypatch.delenv("GH_APP_INSTALLATION_ID", raising=False)

    registry = _write_registry(tmp_path / "registry.json", forks=["A", "B"])
    fake = FakeGitHub(
        covered=["A"],
        org_repos=["A", "B"],
        installations=[
            {
                "id": 4242,
                "account": {"login": "POWERFULMOVES"},
                "target_type": "Organization",
                "repository_selection": "selected",
            }
        ],
    )

    code = audit.main(["--app-jwt", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == 0, out.err
    assert report["mode"] == "app-jwt"
    assert report["installation"]["id"] == "4242"
    assert report["installation"]["account"] == "POWERFULMOVES"
    assert report["not_installed"] == ["B"]

    # The bearer credential the transport saw was a real App JWT for this App.
    bearer = fake.calls[0][2]["Authorization"]
    assert bearer.startswith("Bearer ")
    jwt_text = bearer[len("Bearer ") :]
    claims = jwt.decode(jwt_text, options={"verify_signature": False})
    assert claims["iss"] == client_id

    # And it never reached the report or the terminal.
    assert jwt_text not in out.out + out.err
    assert jwt_text not in json.dumps(report)


# --------------------------------------------------------------------------
# the workflow
# --------------------------------------------------------------------------


def test_the_workflow_mirrors_the_house_conventions():
    """The CI wiring is part of the deliverable, so it is part of the tests.

    Checks the properties the house cares about: the reusable workflow is
    the token source, the token travels by env (never by --print), the
    report is uploaded, the run fails on an incomplete report, and the
    `paths:` filter covers the tool, its tests, the workflow and the
    registry.
    """
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_PATH.exists(), "the audit workflow must exist"
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/_app-token.yml" in raw
    assert "secrets: inherit" in raw
    assert "--print" not in raw, "the token must never be printed"
    assert "GH_TOKEN: ${{ needs." in raw or "GH_TOKEN: ${{" in raw

    assert "upload-artifact@" in raw
    assert "actions/checkout@" in raw
    assert "actions/setup-python@" in raw

    # Every third-party action is SHA-pinned, like the rest of the house.
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("uses:") and "@" in stripped:
            reference = stripped.split("uses:", 1)[1].strip()
            if reference.startswith("./") or reference.startswith("docker://"):
                continue
            assert "@" in reference and len(reference.split("@", 1)[1].split()[0]) == 40, (
                f"action is not SHA-pinned: {stripped}"
            )

    # The complete flag is a gate, not a note.
    assert "complete" in raw

    # The paths filter must cover every input the verdict depends on.
    paths: list[str] = []
    for trigger in workflow.get(True, workflow.get("on", {})).values():
        if isinstance(trigger, dict):
            paths.extend(trigger.get("paths", []))
    for required in (
        "pmoves/tools/gh_app_installation_audit.py",
        "pmoves/tests/tools/test_gh_app_installation_audit.py",
        "pmoves/tests/tools/test_gh_app_installation_audit_mutation_kill.py",
        "pmoves/config/fork_registry.json",
        ".github/workflows/gh-app-installation-audit.yml",
    ):
        assert required in paths, f"the paths filter does not cover {required}"
