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
import re
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

# The --app-jwt mode is exercised with a STUBBED MINTER -- the house minter
# is the third-party boundary, and stubbing it keeps the test hermetic and
# fast. These two strings stand in for the App JWT and the App private key.
# They are distinctive on purpose: a leak of either is unmissable.
FAKE_APP_JWT = "eyJhbGciOiJSUzI1NiJ9.FAKE-APP-JWT-PAYLOAD.fake-signature"
FAKE_PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----FAKEKEYMATERIAL0123456789-----END PRIVATE KEY-----"
)


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

    THE SHAPES ARE GITHUB'S, NOT THE TEST'S
    ----------------------------------------
    ``GET /app/installations`` answers with a TOP-LEVEL JSON ARRAY -- one
    installation object per element. It is NOT an object carrying an
    ``installations`` field. A fake that served the object shape would hide a
    tool that only understands the object shape, so this fake serves the
    array and RECORDS what it served (``served``), and a test asserts the
    shape the tool was handed.

    ``POST /app/installations/{id}/access_tokens`` answers with an
    installation token, and that token is what
    ``GET /installation/repositories`` is read with.

    ``GET /app/installations/{id}/repositories`` is NOT an endpoint that
    exists -- GitHub has no such route -- so it answers 404, exactly as the
    real API does. A fake that served the covered repos there would hide a
    tool that reads an endpoint that does not exist.
    """

    INSTALLATION_TOKEN = "ghs_FAKEINSTALLATIONTOKEN0123456789ABC"

    def __init__(
        self,
        *,
        covered: list[str] | None = None,
        org_repos: list[str] | None = None,
        installations: list[dict] | None = None,
        fail_paths: dict[str, int] | None = None,
        truncated_total: int | None = None,
        installation_token: str | None = None,
    ) -> None:
        self.covered = list(covered or [])
        self.org_repos = set(org_repos or [])
        self.installations = list(installations or [])
        self.fail_paths = dict(fail_paths or {})
        self.truncated_total = truncated_total
        self.installation_token = installation_token or self.INSTALLATION_TOKEN
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.served: dict[str, object] = {}

    def _path_of(self, url: str) -> str:
        return urllib.parse.urlsplit(url).path

    def __call__(self, method: str, url: str, headers, timeout: int):
        self.calls.append((method, url, dict(headers)))
        path = self._path_of(url)
        for prefix, status in self.fail_paths.items():
            if path.startswith(prefix):
                body = json.dumps({"message": "boom"}).encode("utf-8")
                return audit.HttpResponse(status, {}, body)

        if path == "/installation/repositories":
            repos = [{"name": name, "full_name": f"POWERFULMOVES/{name}"} for name in self.covered]
            total = self.truncated_total if self.truncated_total is not None else len(repos)
            payload = {"total_count": total, "repositories": repos}
            self.served[path] = payload
            return _json_response(payload)

        if path == "/app/installations":
            # GitHub's real shape: a TOP-LEVEL ARRAY.
            payload = list(self.installations)
            self.served[path] = payload
            return _json_response(payload)

        if path.endswith("/access_tokens"):
            payload = {
                "token": self.installation_token,
                "expires_at": "2026-11-01T00:00:00Z",
            }
            self.served[path] = payload
            return _json_response(payload)

        if path.endswith("/repositories"):
            # /app/installations/{id}/repositories does not exist.
            return _json_response({"message": "Not Found"}, status=404)

        if path.startswith("/app/installations/"):
            for installation in self.installations:
                if path == f"/app/installations/{installation['id']}":
                    self.served[path] = installation
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
# --app-jwt: GitHub's actual API shapes
# --------------------------------------------------------------------------


def _stub_the_minter(monkeypatch: pytest.MonkeyPatch, jwt: str = FAKE_APP_JWT) -> None:
    """Replace the house JWT minter with a stub.

    The minter IS the third-party boundary (PyJWT plus the PEM), so the
    tests below drive the production path around it: the credentials are
    read, the JWT is minted, the installation is selected, the token is
    exchanged -- all of that is the tool's own code.
    """
    monkeypatch.setattr(
        audit, "_load_build_app_jwt", lambda: (lambda app_id, private_key: jwt)
    )


def test_the_app_jwt_mode_reads_the_array_shaped_installations_and_exchanges_the_jwt(
    tmp_path, capsys, monkeypatch
):
    """Two facts about GitHub's API that the --app-jwt mode has to get right.

    1. ``GET /app/installations`` answers with a TOP-LEVEL JSON ARRAY -- one
       installation object per element. A tool that expects an object with an
       ``installations`` field cannot select an installation at all, and a
       fake that served the OBJECT shape would hide exactly that.

    2. The repository listing lives at ``GET /installation/repositories`` and
       takes an INSTALLATION access token. The App JWT has to be EXCHANGED
       for one first; ``GET /app/installations/{id}/repositories`` is not an
       endpoint that exists.
    """
    monkeypatch.setenv("GH_APP_CLIENT_ID", "Iv23liFAKEclientid")
    monkeypatch.setenv("GH_APP_SEC", FAKE_PRIVATE_KEY)
    monkeypatch.delenv("GH_APP_INSTALLATION_ID", raising=False)
    _stub_the_minter(monkeypatch)

    registry = _write_registry(
        tmp_path / "registry.json", forks=["Covered-One", "Gap-One"]
    )
    fake = FakeGitHub(
        covered=["Covered-One"],
        org_repos=["Gap-One"],
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
    report = json.loads(out.out) if out.out.strip() else {}

    assert code == 0, out.err
    # The fixture handed the tool GitHub's ARRAY shape -- asserted here, so
    # this fake can never quietly drift back to the object shape and hide
    # the defect again.
    assert isinstance(fake.served["/app/installations"], list)
    assert fake.served["/app/installations"] == fake.installations

    assert report["mode"] == "app-jwt"
    assert report["installation"]["id"] == "4242"
    assert report["installation"]["account"] == "POWERFULMOVES"
    assert report["buckets"]["installed"] == 1
    assert report["not_installed"] == ["Gap-One"]

    # The App JWT was EXCHANGED for an installation token.
    exchange = [
        call
        for call in fake.calls
        if fake._path_of(call[1]) == "/app/installations/4242/access_tokens"
    ]
    assert len(exchange) == 1, "the App JWT must be exchanged for an installation token"
    assert exchange[0][0] == "POST"

    # The coverage listing was read from the endpoint that EXISTS...
    coverage = [
        call
        for call in fake.calls
        if fake._path_of(call[1]) == "/installation/repositories"
    ]
    assert coverage, "the coverage listing must be read from /installation/repositories"
    # ...and with the INSTALLATION token, not the App JWT.
    assert coverage[0][2]["Authorization"] == f"Bearer {fake.installation_token}"
    assert FAKE_APP_JWT not in coverage[0][2]["Authorization"]

    # The endpoint that does NOT exist was never called.
    assert not [
        call
        for call in fake.calls
        if fake._path_of(call[1]) == "/app/installations/4242/repositories"
    ]

    # And neither credential reached the report or the terminal.
    combined = out.out + out.err
    assert fake.installation_token not in combined
    assert FAKE_APP_JWT not in combined
    assert fake.installation_token not in json.dumps(report)
    assert FAKE_APP_JWT not in json.dumps(report)


def test_the_app_private_key_is_redacted_when_the_jwt_mint_fails(
    tmp_path, capsys, monkeypatch
):
    """The private key is the credential that can MINT every other one.

    It is registered with the redactor as soon as it is read, so a
    third-party failure that quotes it cannot carry it out to stderr or into
    the report. This drives the CLI: the minter (the third-party boundary)
    raises with the key embedded in the message, and the key must not
    appear in anything the tool emits.
    """
    monkeypatch.setenv("GH_APP_CLIENT_ID", "Iv23liFAKEclientid")
    monkeypatch.setenv("GH_APP_SEC", FAKE_PRIVATE_KEY)
    monkeypatch.delenv("GH_APP_INSTALLATION_ID", raising=False)

    def _explode(app_id: str, private_key: str) -> str:
        raise RuntimeError(f"the key was refused: {private_key}")

    monkeypatch.setattr(audit, "_load_build_app_jwt", lambda: _explode)

    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    report_path = tmp_path / "report.json"

    code = audit.main(
        ["--app-jwt", "--json", "--registry", str(registry), "--out", str(report_path)],
        fetch=FakeGitHub(),
    )
    out = capsys.readouterr()
    combined = out.out + out.err
    written = report_path.read_text(encoding="utf-8")

    assert code == audit.EXIT_CONFIG, combined
    assert "could not mint an App JWT" in combined
    # Not the key -- and not even an 8-character window of it.
    assert FAKE_PRIVATE_KEY not in combined
    assert FAKE_PRIVATE_KEY not in written
    marker = "FAKEKEYMATERIAL0123456789"
    for start in range(0, max(0, len(marker) - 7)):
        assert marker[start : start + 8] not in combined
        assert marker[start : start + 8] not in written


def test_an_installation_with_a_string_account_fails_closed_without_crashing(
    tmp_path, capsys, monkeypatch
):
    """``account`` as a plain STRING is a malformed API response.

    The tool promises a fail-closed ApiError for a malformed response; an
    unhandled AttributeError would be an exit 1 with a traceback instead.
    Both routes into the metadata are exercised: selecting by id (where the
    metadata is read) and selecting by org (where a string account simply
    does not match, so the run fails closed there too).
    """
    monkeypatch.setenv("GH_APP_CLIENT_ID", "Iv23liFAKEclientid")
    monkeypatch.setenv("GH_APP_SEC", FAKE_PRIVATE_KEY)
    monkeypatch.delenv("GH_APP_INSTALLATION_ID", raising=False)
    _stub_the_minter(monkeypatch)

    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    fake = FakeGitHub(
        covered=["A"],
        org_repos=["A"],
        installations=[{"id": 4242, "account": "POWERFULMOVES"}],
    )

    # (a) the id is known, so the metadata for that installation is read.
    code = audit.main(
        [
            "--app-jwt",
            "--json",
            "--registry",
            str(registry),
            "--installation-id",
            "4242",
        ],
        fetch=fake,
    )
    out = capsys.readouterr()
    assert code == audit.EXIT_API, out.err
    assert "AttributeError" not in out.err
    assert "no coverage verdict was produced" in out.err

    # (b) no id: a string account matches no org, so the run fails closed.
    code = audit.main(["--app-jwt", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    assert code == audit.EXIT_API, out.err
    assert "AttributeError" not in out.err
    assert "no coverage verdict was produced" in out.err


def test_the_token_mode_reports_the_installation_as_given_and_never_as_observed(
    tmp_path, capsys
):
    """An installation token proves neither WHICH installation it belongs to
    nor WHICH account it was issued for.

    The report must not claim an account it never observed, and the id the
    operator supplied must be reported as GIVEN. The no-id branch keeps its
    honest disclosure.
    """
    registry = _write_registry(tmp_path / "registry.json", forks=["A"])
    fake = FakeGitHub(covered=["A"], org_repos=["A"])

    code = audit.main(
        [
            "--token",
            "--json",
            "--registry",
            str(registry),
            "--installation-id",
            "4242",
        ],
        fetch=fake,
    )
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == 0, out.err
    installation = report["installation"]
    assert installation["id"] == "4242"
    assert installation["account"] is None, (
        "the account was never observed, so it must not be claimed"
    )
    assert "NOT verified" in installation["note"]
    # The human summary must not print an account either.
    assert "account=POWERFULMOVES" not in out.err

    # The no-id branch keeps its honest disclosure.
    code = audit.main(["--token", "--json", "--registry", str(registry)], fetch=fake)
    out = capsys.readouterr()
    report = json.loads(out.out)

    assert code == 0, out.err
    installation = report["installation"]
    assert installation["id"] is None
    assert installation["account"] is None
    assert "does not expose its installation id" in installation["note"]


# --------------------------------------------------------------------------
# the workflow
# --------------------------------------------------------------------------


def test_the_workflow_mints_the_token_inline_in_the_auditing_job():
    """The CI wiring is part of the deliverable, so it is part of the tests.

    MEASURED 2026-11-01: this workflow's FIRST run called the reusable
    `_app-token.yml` and consumed `needs.mint.outputs.token`. The mint job
    SUCCEEDED and the token was still EMPTY in the consuming job, because
    GitHub Actions SKIPS a job output whose value "may contain secret" --
    the mint job's log says it verbatim:

        ##[warning]Skip output 'token' since it may contain secret.

    `review-collect.yml` was the reusable's only cross-job consumer and
    failed on 100% of runs for exactly this reason; `branch-protection-sync.yml`
    and `app-pr-approve.yml` both mint INLINE for the same reason.

    The PREVIOUS version of this test asserted the reusable pattern -- the
    pattern the run proved broken. A test can enshrine a defect and still
    call it a convention; the run was what proved it. This version asserts
    the pattern that WORKS, and asserts it against the PARSED workflow rather
    than against raw text, so a comment that mentions the broken pattern
    cannot satisfy it.
    """
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_PATH.exists(), "the audit workflow must exist"
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "--print" not in raw, "the token must never be printed"

    steps = (workflow.get("jobs", {}).get("audit", {}) or {}).get("steps", []) or []
    assert steps, "the audit job must have steps"

    # The token is minted IN THIS JOB, inline, by the pinned action.
    mint_steps = [
        step
        for step in steps
        if "create-github-app-token" in str((step or {}).get("uses") or "")
    ]
    assert len(mint_steps) == 1, (
        f"the token must be minted exactly once, in the auditing job "
        f"(found {len(mint_steps)} mint steps)"
    )
    mint = mint_steps[0] or {}
    assert mint.get("id") == "app-token", (
        "the mint step must be addressable as `steps.app-token`"
    )
    mint_with = mint.get("with") or {}
    assert mint_with.get("client-id") == "${{ secrets.GH_APP_CLIENT_ID }}"
    assert mint_with.get("private-key") == "${{ secrets.GH_APP_SEC }}"
    assert mint_with.get("owner") == "${{ github.repository_owner }}"

    # NO step may delegate the mint to a reusable workflow. A job output that
    # "may contain secret" is skipped, so the token arrives empty and the
    # audit runs with no credential -- which is exactly the failure this
    # workflow's first run had.
    for step in steps:
        uses = str((step or {}).get("uses") or "")
        assert not uses.startswith("./"), (
            f"the auditing job must not delegate to a reusable workflow "
            f"(a cross-job token output is skipped as 'may contain secret'): {uses}"
        )

    # The token reaches the tool from a STEP output of THIS job.
    audit_steps = [
        step
        for step in steps
        if str((step or {}).get("name") or "") == "Audit the App installation coverage"
    ]
    assert len(audit_steps) == 1, "the audit step must exist exactly once"
    env = (audit_steps[0] or {}).get("env") or {}
    assert env.get("GH_TOKEN") == "${{ steps.app-token.outputs.token }}", (
        f"the token must come from the mint STEP output in this job: {env}"
    )
    assert "needs." not in str(env.get("GH_TOKEN")), (
        "a cross-job output is skipped by GitHub as 'may contain secret'"
    )

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
        # The registry cross-check reads .gitmodules: a registry key that is a
        # checkout path can only be caught against it.
        ".gitmodules",
        ".github/workflows/gh-app-installation-audit.yml",
    ):
        assert required in paths, f"the paths filter does not cover {required}"


def _run_commands(run: str) -> str:
    """The COMMAND lines of a step's script, with the comments dropped.

    A comment cannot leak a credential; a command can. So the credential
    checks look at what the step would actually execute.
    """
    return "\n".join(
        line for line in str(run or "").splitlines() if not line.strip().startswith("#")
    )


def test_the_pull_request_audit_runs_trusted_base_code_and_keeps_the_token_off_pr_code():
    """The audit must never run PR code with a credential in scope.

    The token minted here is owner-wide (the audit has to be able to see
    every repo in the org), so handing it to the PR's own copy of the tool
    is a pwn-request shape. The workflow therefore runs TRUSTED code -- the
    BASE ref -- and the PR's tests still run, against the PR's own code,
    with no credential in their environment.

    Asserted against the PARSED workflow, so a comment that mentions the
    wrong ref cannot satisfy it.
    """
    yaml = pytest.importorskip("yaml")
    assert WORKFLOW_PATH.exists(), "the audit workflow must exist"
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    job = workflow.get("jobs", {}).get("audit", {}) or {}
    steps = job.get("steps", []) or []
    triggers = workflow.get(True, workflow.get("on", {})) or {}

    assert "pull_request" in triggers
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers

    # (1) On a pull_request the TRUSTED code is the BASE ref, and it lives in
    #     its own directory so the PR's working tree cannot shadow it.
    base_checkouts = [
        step
        for step in steps
        if str((step or {}).get("uses") or "").startswith("actions/checkout@")
        and str((step or {}).get("if") or "").strip() == "github.event_name == 'pull_request'"
    ]
    assert len(base_checkouts) == 1, (
        f"exactly one checkout may run on a pull_request alone, found {len(base_checkouts)}"
    )
    base = base_checkouts[0] or {}
    base_with = base.get("with") or {}
    assert base_with.get("ref") == "${{ github.event.pull_request.base.sha }}"
    trusted_dir = base_with.get("path")
    assert trusted_dir and trusted_dir != ".", (
        "the trusted code needs its own directory, or the PR's tree shadows it"
    )

    # (2) The audit step runs THAT copy -- never the working tree's.
    audit_steps = [
        step
        for step in steps
        if str((step or {}).get("name") or "") == "Audit the App installation coverage"
    ]
    assert len(audit_steps) == 1, "the audit step must exist exactly once"
    audit_step = audit_steps[0] or {}
    run = str(audit_step.get("run") or "")
    tool_refs = re.findall(r"[^\s\"']*gh_app_installation_audit\.py", run)
    assert tool_refs, "the audit step must invoke the tool"
    for ref in tool_refs:
        assert ref == f"{trusted_dir}/pmoves/tools/gh_app_installation_audit.py", (
            f"the audit step must run the TRUSTED copy, not {ref!r}"
        )

    # (3) GH_TOKEN is in the audit step's environment and NOWHERE else -- not
    #     in the job environment, not in any other step's environment, and
    #     not in any other step's command.
    assert "GH_TOKEN" not in (job.get("env") or {}), (
        "a job-level GH_TOKEN would put the credential in EVERY step, "
        "including the steps that run the PR's code"
    )
    assert "GH_TOKEN" in (audit_step.get("env") or {})
    for step in steps:
        if step is audit_step:
            continue
        name = (step or {}).get("name")
        assert "GH_TOKEN" not in ((step or {}).get("env") or {}), (
            f"GH_TOKEN is in the environment of step {name!r}"
        )
        assert "GH_TOKEN" not in _run_commands((step or {}).get("run") or ""), (
            f"GH_TOKEN is referenced by step {name!r}"
        )

    # (4) The PR's tests still run -- against the PR's OWN code, with no
    #     credential in scope.
    pytest_steps = [
        step
        for step in steps
        if "python -m pytest" in _run_commands((step or {}).get("run") or "")
    ]
    assert pytest_steps, "the workflow must still run the instrument's tests"
    pytest_run = _run_commands((pytest_steps[0] or {}).get("run") or "")
    assert "pmoves/tests/tools/test_gh_app_installation_audit.py" in pytest_run
    assert f"{trusted_dir}/" not in pytest_run, (
        "the tests must run the PR's own code, not the trusted copy"
    )

    # (5) schedule / workflow_dispatch still mint INLINE, in this job, and
    #     the mint is not conditional -- so every event gets a token.
    mint_steps = [
        step
        for step in steps
        if "create-github-app-token" in str((step or {}).get("uses") or "")
    ]
    assert len(mint_steps) == 1
    mint = mint_steps[0] or {}
    assert not mint.get("if"), "the inline mint must run on every event"
    mint_with = mint.get("with") or {}
    assert mint_with.get("client-id") == "${{ secrets.GH_APP_CLIENT_ID }}"
    assert mint_with.get("private-key") == "${{ secrets.GH_APP_SEC }}"
    assert (audit_step.get("env") or {}).get("GH_TOKEN") == (
        "${{ steps.app-token.outputs.token }}"
    )


def _write_gitmodules(path: Path, sections: list[tuple[str, str]]) -> Path:
    """A .gitmodules with the given (path, url) pairs."""
    lines: list[str] = []
    for index, (sub_path, url) in enumerate(sections):
        lines.append(f'[submodule "s{index}"]')
        lines.append(f"\tpath = {sub_path}")
        lines.append(f"\turl = https://github.com/POWERFULMOVES/{url}.git")
        lines.append("\tbranch = PMOVES.AI-Edition-Hardened")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_registry_key_that_is_a_checkout_path_fails_closed(tmp_path):
    """A key that is a checkout PATH names no repo, so the run must refuse.

    MEASURED 2026-11-01: the registry carried BOTH
    `PM-Spark-video-search-and-summarization` (the repo) and `PMOVES-Spark-VSS`
    (its checkout path) -- two entries, one upstream. The audit resolved 93 of
    94 registry repos and the 94th came back HTTP 404. The cross-check names
    the cause instead of reporting an INCOMPLETE verdict nobody can act on.
    """
    gitmodules = _write_gitmodules(
        tmp_path / ".gitmodules",
        [("PMOVES-Spark-VSS", "PM-Spark-video-search-and-summarization")],
    )
    registry = _write_registry(
        tmp_path / "registry.json",
        forks=["PMOVES-Spark-VSS", "PM-Spark-video-search-and-summarization"],
    )

    code = audit.main(
        ["--plan", "--registry", str(registry), "--gitmodules", str(gitmodules)]
    )
    assert code == audit.EXIT_REGISTRY, (
        f"a registry key that is a checkout path must fail closed "
        f"(exit {audit.EXIT_REGISTRY}), got {code}"
    )


def test_a_registry_key_that_is_a_repo_at_a_different_path_is_not_a_defect(tmp_path):
    """The case alias must NOT false-fire.

    `PMOVES-N8N` is a real repo -- it is the one checked out at the path
    `PMOVES-N8N-Auto` -- while the path `PMOVES-n8n` belongs to a DIFFERENT
    repo, `PMOVES-n8n-FlooS`. The two paths casefold to the same string, so a
    rule that compared only path->repo would flag a legitimate entry.
    """
    gitmodules = _write_gitmodules(
        tmp_path / ".gitmodules",
        [
            ("PMOVES-n8n", "PMOVES-n8n-FlooS"),
            ("PMOVES-N8N-Auto", "PMOVES-N8N"),
        ],
    )
    registry = _write_registry(tmp_path / "registry.json", forks=["PMOVES-N8N"])

    code = audit.main(
        ["--plan", "--registry", str(registry), "--gitmodules", str(gitmodules)]
    )
    assert code == 0, (
        f"`PMOVES-N8N` names a real repo and must not be flagged, got exit {code}"
    )


def test_the_real_registry_passes_the_gitmodules_cross_check():
    """The registry AS IT STANDS must name repos, not checkout paths.

    This is the regression lock for the defect the audit found in production:
    if a checkout path is ever keyed into the registry again, this goes red
    before the audit can report an incomplete verdict.
    """
    code = audit.main(["--plan", "--registry", str(REGISTRY_PATH)])
    assert code == 0, (
        f"the real registry must pass the .gitmodules cross-check, got exit {code}"
    )

