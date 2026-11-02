"""Mutation-kill harness: the GitHub App installation audit's gates must BITE
when the defect is put back.

THE DEFECT CLASS
----------------
The audit exists because a coverage question was answered with a 401 and,
before that, with an unverified assumption. The failure modes this harness
pins are the ones that make the tool LIE:

  * a failed audit that exits 0, or prints something a reader could take for
    "zero repos missing";
  * a universe that is not derived from the registry (a baked-in number, or a
    section silently dropped);
  * bucket arithmetic that does not close, so a repo can vanish between the
    universe and the report;
  * a repo that could not be resolved being reported as a finding
    ("not installed") instead of an absence of knowledge;
  * a pagination walk that cannot be proven complete being treated as
    complete;
  * a credential leaking into the report.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
The house budget model charges a mutation-kill harness by its WALL CLOCK: a
file that costs more than ``FALLBACK_FILE_TIMEOUT`` (60s) is killed when the
ratchet isolates it, and a healthy-but-slow file is then reported as a broken
one (see ``pmoves/configs/pytest_ratchet/_slow_files.yaml``). Every phase
here spawns a full ``python -m pytest`` child, and one child startup is
~1.6s on this host — irreducible.

So the GREEN phases are run ONCE for the whole session, over every target
test, instead of once per mutation:

  * GREEN BEFORE runs once, before any mutation, over ALL the target tests;
  * RED AFTER runs per mutation, over the ONE named test (this is the only
    phase that has to be per-mutation: the source under test differs);
  * GREEN AFTER runs once, after every mutation has been restored.

That is the same three phases with the same assertions. It is NOT the same
wall clock: ~20s instead of ~70s, which is the difference between a file the
ratchet MEASURES and a file it kills.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it. A harness may
only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below rewrites the CALL the production path makes, or removes a
rule the production path relies on. None of them re-types the fix's own
expression: each one is a defect a reviewer could plausibly introduce, and
each is killed by a test that exercises the production path.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_gh_app_installation_audit_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
one file in this repo and restores it.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "gh_app_installation_audit.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_gh_app_installation_audit.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "gh-app-installation-audit.yml"
REGISTRY_FILE = REPO_ROOT / "pmoves" / "config" / "fork_registry.json"

_PYTEST_TIMEOUT_SECONDS = 600.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-gh-app-audit-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it.

    ``target_file`` is the file the rewrite is applied to. It defaults to the
    audit TOOL, which is where every defect the tool could make lives. A
    mutation that lives in the WIRING -- the workflow, the registry -- names
    its own file, because a harness that could only ever rewrite the tool
    could not prove that the CI wiring is load-bearing.
    """

    name: str
    old: str
    new: str
    target_test: str
    rationale: str
    target_file: Path | None = None

    @property
    def path(self) -> Path:
        return self.target_file or TOOL


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_api_error_exit_code_downgraded",
        old="""        print(
            "AUDIT FAILED: no coverage verdict was produced. "
            "This is NOT 'zero repos missing'.",
            file=sys.stderr,
        )
        return error.exit_code""",
        new="""        print(
            "AUDIT FAILED: no coverage verdict was produced. "
            "This is NOT 'zero repos missing'.",
            file=sys.stderr,
        )
        return 0""",
        target_test="test_an_api_error_exits_non_zero",
        rationale=(
            "A GitHub API failure must fail the run. If the error path exits 0, "
            "a broken audit reads as a clean one -- the exact failure the "
            "operator's 401 was."
        ),
    ),
    Mutation(
        name="M2_failure_disclaimer_removed",
        old="""        print(
            "AUDIT FAILED: no coverage verdict was produced. "
            "This is NOT 'zero repos missing'.",
            file=sys.stderr,
        )
        return error.exit_code""",
        new="""        print(
            "AUDIT OK: 0 repos missing (complete).",
            file=sys.stderr,
        )
        return error.exit_code""",
        target_test="test_a_failed_audit_never_prints_a_reassuring_summary",
        rationale=(
            "A failed audit that says '0 repos missing' manufactures a green "
            "light out of a broken instrument. The disclaimer is the gate."
        ),
    ),
    Mutation(
        name="M3_bucket_arithmetic_assertion_removed",
        old="""    if total != universe.size:
        raise InvariantError(""",
        new="""    if total != universe.size and False:
        raise InvariantError(""",
        target_test="test_the_bucket_arithmetic_assertion_rejects_a_mismatched_count",
        rationale=(
            "The bucket counts must sum to the universe. Without the "
            "assertion a repo can drop out of the report entirely and the "
            "totals still look tidy."
        ),
    ),
    Mutation(
        name="M4_first_party_dropped_from_the_universe",
        old="""    first_party = _record_names(registry.get("_first_party"), "_first_party")""",
        new="""    first_party = ()""",
        target_test="test_the_derived_universe_contains_the_first_party_members",
        rationale=(
            "The PMOVES-built repos live in `_first_party`. Dropping that "
            "section silently shrinks the universe and every coverage verdict "
            "computed against it."
        ),
    ),
    Mutation(
        name="M5_unresolved_repo_reported_as_not_installed",
        old="""        else:
            statuses.append(
                RepoStatus(
                    name,
                    BUCKET_UNKNOWN,
                    reasons.get(
                        name, "repo name did not resolve; no claim is made either way"
                    ),
                )
            )""",
        new="""        else:
            statuses.append(
                RepoStatus(
                    name,
                    BUCKET_NOT_INSTALLED,
                    reasons.get(
                        name, "repo name did not resolve; no claim is made either way"
                    ),
                )
            )""",
        target_test="test_a_repo_that_cannot_be_resolved_is_unknown_not_not_installed",
        rationale=(
            "A repo that could not be resolved is an absence of knowledge. "
            "Reporting it as 'not installed' is a claim the audit cannot "
            "support -- and it is the finding the operator would act on."
        ),
    ),
    Mutation(
        name="M6_pagination_incompleteness_ignored",
        old="""        if total is not None and len(items) != total:
            raise ApiError(""",
        new="""        if total is not None and len(items) != total and False:
            raise ApiError(""",
        target_test="test_an_incomplete_pagination_fails_closed",
        rationale=(
            "If the endpoint says there are more items than the walk "
            "collected, the walk is incomplete. Reading that as 'those repos "
            "are simply not covered' fabricates findings."
        ),
    ),
    Mutation(
        name="M7_report_leaks_the_installation_token",
        old="""        report = audit_installation(
            mode="token",
            universe=universe,
            client=client,
            coverage_path=INSTALLATION_REPOSITORIES_PATH,
            installation=installation,
            generated_at=generated_at,
        )""",
        new="""        report = audit_installation(
            mode="token",
            universe=universe,
            client=client,
            coverage_path=INSTALLATION_REPOSITORIES_PATH,
            installation=installation,
            generated_at=generated_at,
        )
        report["token"] = token""",
        target_test="test_the_installation_token_never_appears_in_the_report_or_the_output",
        rationale=(
            "The installation token is a credential. It must never reach the "
            "report, the artifact, or the terminal -- not even in a "
            "masked-but-partial form. 'Let me add it for debugging' is how it "
            "gets there."
        ),
    ),
    Mutation(
        name="M8_complete_flag_forced_true",
        old="""    complete = not unknown""",
        new="""    complete = True""",
        target_test="test_an_unknown_repo_makes_the_report_incomplete",
        rationale=(
            "`complete` is what CI reads to decide whether a verdict is a "
            "verdict. Forcing it true hides every unresolved repo behind a "
            "green check."
        ),
    ),
    Mutation(
        name="M9_unreadable_registry_tolerated",
        old="""    except OSError as error:
        raise RegistryError(f"cannot read the fork registry {path}: {error}") from error""",
        new="""    except OSError as error:
        return {"org": "UNKNOWN", "forks": {}, "_first_party": [], "_excluded": {}}""",
        target_test="test_an_unreadable_registry_fails_closed",
        rationale=(
            "A registry the tool cannot read must fail the run. An empty "
            "universe reads downstream as 'nothing is missing' -- the most "
            "reassuring possible wrong answer."
        ),
    ),
    Mutation(
        name="M10_membership_assertion_removed",
        old="""    if len(set(named)) != len(named) or set(named) != set(universe.members):
        raise InvariantError(""",
        new="""    if len(set(named)) != len(named) or set(named) != set(universe.members):
        pass
    if False:
        raise InvariantError(""",
        target_test="test_the_bucket_arithmetic_assertion_rejects_a_duplicate_member",
        rationale=(
            "Each universe member must appear EXACTLY once in the buckets. "
            "Without the membership check a repo can be counted twice while "
            "the totals still add up."
        ),
    ),
    Mutation(
        name="M11_workflow_token_moved_back_across_a_job_boundary",
        old="""          GH_TOKEN: ${{ steps.app-token.outputs.token }}""",
        new="""          GH_TOKEN: ${{ needs.mint.outputs.token }}""",
        target_test="test_the_workflow_mints_the_token_inline_in_the_auditing_job",
        rationale=(
            "GitHub Actions SKIPS a job output whose value 'may contain "
            "secret', so a cross-job token arrives EMPTY. The audit then runs "
            "with no credential and the coverage question is never answered. "
            "This workflow's FIRST run did exactly this and the mint job's "
            "log says it verbatim."
        ),
        target_file=WORKFLOW_FILE,
    ),
    Mutation(
        name="M12_registry_path_alias_not_failing_the_run",
        old="""    problems, paths_checked = check_registry_names(path, names)
    if problems:
        raise RegistryError(
            "the fork registry names a checkout path instead of a repo name: "
            + "; ".join(problems)
        )""",
        new="""    problems, paths_checked = check_registry_names(path, names)""",
        target_test="test_a_registry_key_that_is_a_checkout_path_fails_closed",
        rationale=(
            "A registry key that is a checkout PATH names no repo in the org, "
            "so the audit could never resolve it and the verdict could never "
            "be complete. Detecting it and then NOT failing on it turns a "
            "known defect back into an INCOMPLETE verdict."
        ),
    ),
    Mutation(
        name="M13_the_repo_name_exemption_dropped",
        old="""        if key in repo_names:
            continue""",
        new="""        if False:
            continue""",
        target_test="test_a_registry_key_that_is_a_repo_at_a_different_path_is_not_a_defect",
        rationale=(
            "The exemption is what keeps the case aliases honest: "
            "`PMOVES-N8N` is a real repo (checked out at the path "
            "`PMOVES-N8N-Auto`) whose checkout path `PMOVES-n8n` belongs to a "
            "DIFFERENT repo. Without the exemption a legitimate entry is "
            "flagged and the gate cries wolf on every run."
        ),
    ),
    Mutation(
        name="M14_the_phantom_registry_key_reintroduced",
        old="""    "PM-Spark-video-search-and-summarization": {
      "upstream": "NVIDIA-AI-Blueprints/video-search-and-summarization",
      "sync": false,""",
        new="""    "PMOVES-Spark-VSS": {
      "upstream": "NVIDIA-AI-Blueprints/video-search-and-summarization",
      "sync": false,
      "branch": "PMOVES.AI-Edition-Hardened",
      "reason": "the phantom the audit caught on 2026-11-01"
    },
    "PM-Spark-video-search-and-summarization": {
      "upstream": "NVIDIA-AI-Blueprints/video-search-and-summarization",
      "sync": false,""",
        target_test="test_the_real_registry_passes_the_gitmodules_cross_check",
        rationale=(
            "This is the EXACT defect the audit found in production: the "
            "registry carried a second entry keyed on the checkout path "
            "`PMOVES-Spark-VSS` instead of the repo name, so the org had no "
            "repo by that name and the audit's 94th repo came back HTTP 404. "
            "Reintroducing it must turn the real-registry check red."
        ),
        target_file=REGISTRY_FILE,
    ),
    Mutation(
        name="M15_the_installation_list_read_as_an_object_instead_of_an_array",
        old="""    installations = client.get_paginated(APP_INSTALLATIONS_PATH)""",
        new="""    installations = client.get_paginated(
        APP_INSTALLATIONS_PATH, collection="installations"
    )""",
        target_test=(
            "test_the_app_jwt_mode_reads_the_array_shaped_installations_and_exchanges_the_jwt"
        ),
        rationale=(
            "GET /app/installations answers with a TOP-LEVEL ARRAY. Reading it "
            "as an object carrying an 'installations' field raises before any "
            "installation can be selected -- the advertised --app-jwt mode "
            "could never run at all."
        ),
    ),
    Mutation(
        name="M16_the_coverage_listing_read_from_an_endpoint_that_does_not_exist",
        old="""        coverage_path=INSTALLATION_REPOSITORIES_PATH,
        installation=_installation_metadata(installation, source="app-jwt"),""",
        new="""        coverage_path=f"{APP_INSTALLATIONS_PATH}/{installation_id}/repositories",
        installation=_installation_metadata(installation, source="app-jwt"),""",
        target_test=(
            "test_the_app_jwt_mode_reads_the_array_shaped_installations_and_exchanges_the_jwt"
        ),
        rationale=(
            "GitHub exposes the installation's repository list at "
            "GET /installation/repositories, for an installation token. "
            "/app/installations/{id}/repositories is not a route that exists, "
            "so the advertised mode would always die on a 404."
        ),
    ),
    Mutation(
        name="M17_the_coverage_listing_read_with_the_app_jwt",
        old="""    installation_client = GitHubClient(
        installation_token, fetch=fetch, timeout=args.timeout
    )""",
        new="""    installation_client = GitHubClient(
        app_jwt, fetch=fetch, timeout=args.timeout
    )""",
        target_test=(
            "test_the_app_jwt_mode_reads_the_array_shaped_installations_and_exchanges_the_jwt"
        ),
        rationale=(
            "The repository listing takes an INSTALLATION token. Reading it "
            "with the App JWT asks GitHub for something it will not serve, and "
            "the report would claim a coverage it never observed."
        ),
    ),
    Mutation(
        name="M18_the_app_private_key_not_registered_with_the_redactor",
        old="""    redactor.add(raw_private_key)
    redactor.add(private_key)""",
        new="""    pass  # the private key is not registered with the redactor""",
        target_test="test_the_app_private_key_is_redacted_when_the_jwt_mint_fails",
        rationale=(
            "The private key is the credential that can mint every other one. "
            "Unregistered, a third-party failure that quotes the key carries "
            "it straight to stderr and into the report -- which is exactly "
            "what this tool's own doctrine forbids."
        ),
    ),
    Mutation(
        name="M19_the_malformed_account_guard_removed",
        old="""    account = installation.get("account")
    if account is not None and not isinstance(account, Mapping):
        raise ApiError(
            "the installation's 'account' field is not an object; the API "
            f"response is malformed: {account!r}"
        )
    return {
        "id": str(installation.get("id")) if installation.get("id") is not None else None,
        "account": _account_login(installation) or None,""",
        new="""    return {
        "id": str(installation.get("id")) if installation.get("id") is not None else None,
        "account": (installation.get("account") or {}).get("login"),""",
        target_test=(
            "test_an_installation_with_a_string_account_fails_closed_without_crashing"
        ),
        rationale=(
            "A plain STRING where an OBJECT is expected is a malformed API "
            "response. Reading it with .get() raises an unhandled "
            "AttributeError -- exit 1 with a traceback -- instead of the "
            "fail-closed ApiError the tool promises."
        ),
    ),
    Mutation(
        name="M20_the_token_mode_fabricates_the_installation_account",
        old="""        installation = _unverified_installation_metadata(
            installation_id=wanted_id,
            source="installation-token",
        )""",
        new="""        installation = _unverified_installation_metadata(
            installation_id=wanted_id,
            source="installation-token",
        )
        installation["account"] = universe.org""",
        target_test=(
            "test_the_token_mode_reports_the_installation_as_given_and_never_as_observed"
        ),
        rationale=(
            "An installation token proves neither which installation nor "
            "which account it belongs to. Filling the account in from the "
            "registry asserts what the tool never checked -- the finding a "
            "coverage report is read for."
        ),
    ),
    Mutation(
        name="M21_the_mint_gate_removed_so_a_pull_request_mints_a_token",
        old="""        if: steps.mode.outputs.mode == 'audit'
        with:
          client-id: ${{ secrets.GH_APP_CLIENT_ID }}""",
        new="""        with:
          client-id: ${{ secrets.GH_APP_CLIENT_ID }}""",
        target_test=(
            "test_the_token_is_minted_only_on_the_default_branch_and_never_on_a_pull_request"
        ),
        rationale=(
            "The rule is that the token is minted ONLY on the default branch. "
            "Remove the gate and the mint runs on every event -- including a "
            "pull_request, whose workflow FILE is PR-controlled. That hands an "
            "owner-wide token to exactly the code the PR is trying to change."
        ),
        target_file=WORKFLOW_FILE,
    ),
    Mutation(
        name="M22_the_token_hoisted_into_the_job_environment",
        old="""jobs:
  audit:
    runs-on: ubuntu-24.04""",
        new="""jobs:
  audit:
    env:
      GH_TOKEN: ${{ steps.app-token.outputs.token }}
    runs-on: ubuntu-24.04""",
        target_test=(
            "test_the_token_is_minted_only_on_the_default_branch_and_never_on_a_pull_request"
        ),
        rationale=(
            "A job-level GH_TOKEN puts the credential in the environment of "
            "EVERY step -- including the steps that run the PR's own code. "
            "The token belongs to the audit step and to nothing else."
        ),
        target_file=WORKFLOW_FILE,
    ),
]


def _run_pytest(node_ids: list[str], timeout: float = _PYTEST_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *node_ids,
            "-q",
            "-p",
            "no:warnings",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def _node_id(target_test: str) -> str:
    return f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{target_test}"


_GREEN_BEFORE: list[subprocess.CompletedProcess] = []


def _green_before() -> list[subprocess.CompletedProcess]:
    """GREEN BEFORE, once for the whole session: the pristine source must pass
    EVERY target test."""
    if not _GREEN_BEFORE:
        node_ids = [_node_id(mutation.target_test) for mutation in MUTATIONS]
        _GREEN_BEFORE.append(_run_pytest(node_ids))
    return _GREEN_BEFORE


def _named_test_failed(proc: subprocess.CompletedProcess, test_name: str) -> bool:
    """True only if pytest's own short summary names THIS test as failed.

    A collection error, a timeout, or an unrelated failure also makes pytest
    exit non-zero; none of those is a kill.
    """
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
            if line.startswith("FAILED ") and test_name in line:
                return True
    return False


@contextlib.contextmanager
def _file_lock(path: Path):
    """Cross-process lock so two harnesses cannot mutate the tree at once."""
    handle = path.open("a+", encoding="utf-8")
    acquired = False
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(0.2)
        if not acquired:
            raise TimeoutError(f"could not acquire {path}")
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _apply_mutation(mutation: Mutation, original: str) -> str:
    """Return the mutated source, or raise if the anchor does not match.

    A mutation whose anchor has drifted must FAIL LOUDLY. Silently mutating
    nothing would produce a green harness that proves nothing.
    """
    if mutation.old not in original:
        raise AssertionError(
            f"mutation {mutation.name}: anchor not found in {mutation.path.name}. "
            "The source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def _read_source(path: Path) -> tuple[str, bool]:
    """(text, uses_crlf) for a source file.

    The text is normalised to ``\\n`` so a mutation anchor is line-ending
    independent; the flag records the file's OWN convention so the restore
    can put it back exactly as it was. Reading with ``read_text`` and
    writing back with ``write_text`` silently rewrote a CRLF file as LF --
    the restore was not byte-exact, and the working tree's line endings
    changed under the harness.
    """
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def _write_source(path: Path, text: str, crlf: bool) -> None:
    """Write a source file back in its own line-ending convention."""
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original, _crlf = _read_source(mutation.path)
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.path.name} -- the source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED, with a byte-exact restore. GREEN is batched (see the
    module docstring): it runs once before any mutation and once after the
    last restore, over every target test."""
    node_id = _node_id(mutation.target_test)
    target = mutation.path
    original, crlf = _read_source(target)
    original_bytes = target.read_bytes()

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH):
        # 1. GREEN BEFORE (batched over every target test)
        before = _green_before()[0]
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        try:
            _write_source(target, mutated, crlf)

            # 2. RED AFTER -- the NAMED test must die
            after = _run_pytest([node_id])
            assert after.returncode != 0, (
                f"{mutation.name}: the mutation SURVIVED -- "
                f"{mutation.target_test} still passed\n{after.stdout[-4000:]}"
            )
            assert _named_test_failed(after, mutation.target_test), (
                f"{mutation.name}: pytest failed, but NOT the named test "
                f"{mutation.target_test}\n{after.stdout[-4000:]}\n{after.stderr[-2000:]}"
            )
        finally:
            # 3. restore -- byte-exact, line endings included
            _write_source(target, original, crlf)
            restored = target.read_bytes()
            assert restored == original_bytes, (
                f"{mutation.name}: the restore was not byte-exact"
            )


def test_the_tool_source_is_intact_after_the_mutation_suite():
    """GREEN AFTER: after every mutation has been restored, every target test
    must pass again -- and the source must be byte-identical to the original."""
    original = TOOL.read_text(encoding="utf-8")
    assert "if total != universe.size:" in original
    assert "first_party = _record_names(registry.get(\"_first_party\"), \"_first_party\")" in original
    assert "complete = not unknown" in original
    assert "if total is not None and len(items) != total:" in original
    assert "raise RegistryError(f\"cannot read the fork registry {path}: {error}\") from error" in original

    # The wiring files the new mutations touched must be byte-identical too.
    assert "GH_TOKEN: ${{ steps.app-token.outputs.token }}" in WORKFLOW_FILE.read_text(
        encoding="utf-8"
    )
    # The phantom must not be a KEY. The registry's `reason` text NAMES it --
    # that is the record of why it was removed -- so the assertion is on the
    # parsed keys, not on the raw text.
    registry_data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    assert "PMOVES-Spark-VSS" not in (registry_data.get("forks") or {})
    assert "PM-Spark-video-search-and-summarization" in (registry_data.get("forks") or {})

    node_ids = [_node_id(mutation.target_test) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
