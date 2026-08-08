"""pmoves/tools/branch_protection.py

The PMOVES standard branch-protection tool. Single source of truth for
how a PMOVES org repo's main branch is protected. The tool reads a
canonical spec (`pmoves/configs/branch_protection/pmoves_standard.json`),
audits the current state of a repo via the GitHub REST API, diffs against
the spec, and can apply the spec to bring the repo into compliance.

Three public functions, all stdlib-only (urllib.request + json):

    audit(repo: str, profile: str) -> AuditResult
        Reads the current state of <repo>'s main branch (classic
        protection + rulesets) and diffs it against the named profile
        in the spec. Returns a structured drift report.

    apply(repo: str, profile: str, dry_run: bool = True) -> ApplyResult
        Applies the named profile to <repo>'s main branch. dry_run=True
        is the default and the safe mode; the tool prints the would-be
        API calls and exits. dry_run=False issues the calls.

    drift_check(org: str) -> list[DriftReport]
        Scans every repo in <org> that has a per_repo_overrides entry
        in the spec, audits each, and returns the union of drift
        reports. Use this from the Mavis cron to surface drift on the
        pmoves.branch_protection.drift.v1 NATS subject.

NATS integration: the cron that calls drift_check() publishes the
result to pmoves.branch_protection.drift.v1 (canonical
<category>.<service>.<event>.<version> family per
.claude/context/nats-subjects.md). The orchestrator (from the harness
v0 slice) consumes the drift and dispatches a remediation session.

GH auth: the tool shells out to `gh api` for the actual HTTP calls
because the GitHub App token + operator PAT both flow through gh's
auth. Wrapping `gh api` is simpler than handling 2 auth schemes in
Python and gives the operator free auth-state inspection. Tradeoff:
the tool requires `gh` to be installed and authenticated. Documented
in BRANCH_PROTECTION_BASELINE.md.

Tests: pmoves/tools/tests/test_branch_protection.py covers the spec
parser, the diff logic, the dry-run output format, and the apply
function's call sequence (with a mocked gh api).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


# --- Errors ---

class BranchProtectionError(Exception):
    """Raised for any tool-level error (missing spec, missing gh, etc.).
    Distinct from generic exceptions so the orchestrator can catch +
    decide: retry, fall back to a default profile, or refuse to start.
    """


# --- Result dataclasses ---

@dataclasses.dataclass
class DriftItem:
    field: str           # e.g. "required_pull_request_reviews.required_approving_review_count"
    expected: Any
    actual: Any
    severity: str         # "block" (required check missing) | "warn" (advisory drift)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AuditResult:
    repo: str
    profile: str
    drift: list[DriftItem]
    checked_at: str
    source_url: str

    @property
    def is_compliant(self) -> bool:
        return len([d for d in self.drift if d.severity == "block"]) == 0

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "profile": self.profile,
            "compliant": self.is_compliant,
            "drift": [d.to_dict() for d in self.drift],
            "checked_at": self.checked_at,
            "source_url": self.source_url,
        }


@dataclasses.dataclass
class ApplyResult:
    repo: str
    profile: str
    dry_run: bool
    calls: list[dict]   # each = {"method", "path", "body"}
    applied: list[str]  # paths that were called (empty in dry-run)
    skipped: list[str]  # paths that were NOT called (e.g. no required status checks)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class DriftReport:
    org: str
    checked_at: str
    repos: list[AuditResult]

    def to_dict(self) -> dict:
        return {
            "org": self.org,
            "checked_at": self.checked_at,
            "repos": [r.to_dict() for r in self.repos],
        }


# --- Spec loading ---

DEFAULT_SPEC_PATH = (
    Path(__file__).parent.parent / "configs" / "branch_protection" / "pmoves_standard.json"
)


def load_spec(path: Optional[Path] = None) -> dict:
    """Load + return the canonical spec. Pure-function for testability."""
    p = path or DEFAULT_SPEC_PATH
    if not p.exists():
        raise BranchProtectionError(f"spec not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_repo_profile(spec: dict, repo: str) -> tuple[str, dict]:
    """Look up the named profile + per-repo overrides for a given repo.

    Returns (profile_name, merged_profile_dict). The merged dict has
    the profile defaults overridden by per_repo_overrides[repo].
    """
    if repo not in spec.get("per_repo_overrides", {}):
        raise BranchProtectionError(
            f"no per_repo_overrides entry for {repo}; "
            f"add one to the spec or pass --profile <name> explicitly"
        )
    override = spec["per_repo_overrides"][repo]
    profile_name = override["profile"]
    if profile_name not in spec["profiles"]:
        raise BranchProtectionError(f"profile {profile_name!r} not found in spec")
    profile = dict(spec["profiles"][profile_name])  # copy
    # Shallow-merge per_repo_overrides into the profile.
    for key, value in override.items():
        if key == "profile":
            continue
        profile[key] = value
    return profile_name, profile


# --- GitHub REST API access via `gh` ---

def _gh_api(method: str, path: str, body: Optional[dict] = None) -> Any:
    """Run `gh api <method> <path>` and return the parsed JSON.

    Uses gh's own auth (PAT or GitHub App token) so the tool doesn't
    need to handle auth schemes. Raises BranchProtectionError if gh is
    missing or the call fails.
    """
    if shutil.which("gh") is None:
        raise BranchProtectionError("gh CLI not found in PATH")
    cmd = ["gh", "api", "--method", method.upper(), path]
    if body is not None:
        cmd.extend(["--input", "-"])
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(body) if body is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise BranchProtectionError(f"gh subprocess failed: {e}") from e
    if proc.returncode != 0:
        # gh returns 404 for "Branch not protected" — that's an expected
        # state for an unprotected repo, not an error.
        if "Branch not protected" in (proc.stderr or ""):
            return None
        raise BranchProtectionError(
            f"gh api {method} {path} failed: {proc.stderr.strip()}"
        )
    if not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise BranchProtectionError(
            f"gh api {method} {path} returned non-JSON: {proc.stdout[:200]}"
        ) from e


# --- Read current state ---

def _read_classic_protection(repo: str) -> Optional[dict]:
    """Returns the classic protection object or None if not protected."""
    return _gh_api("GET", f"repos/{repo}/branches/main/protection")


def _read_rulesets(repo: str) -> list[dict]:
    """Returns the list of rulesets for the repo (may be empty)."""
    data = _gh_api("GET", f"repos/{repo}/rulesets")
    return data or []


def _read_required_status_checks(repo: str) -> Optional[dict]:
    """Returns the required_status_checks sub-object or None."""
    classic = _read_classic_protection(repo)
    if not classic:
        return None
    return classic.get("required_status_checks")


def _read_review_policy(repo: str) -> Optional[dict]:
    classic = _read_classic_protection(repo)
    if not classic:
        return None
    return classic.get("required_pull_request_reviews")


# --- Diff logic ---

def _diff_required_status_checks(
    expected: dict, actual: Optional[dict]
) -> list[DriftItem]:
    """Return the drift list comparing expected vs actual status checks."""
    if actual is None:
        return [
            DriftItem(
                field="required_status_checks",
                expected=expected,
                actual=None,
                severity="block",
            )
        ]
    drift: list[DriftItem] = []
    if actual.get("strict") != expected.get("strict"):
        drift.append(
            DriftItem(
                field="required_status_checks.strict",
                expected=expected.get("strict"),
                actual=actual.get("strict"),
                severity="block",
            )
        )
    expected_contexts = {c["context"] for c in expected.get("checks", [])}
    actual_contexts = {c.get("context") for c in actual.get("checks", [])}
    missing = expected_contexts - actual_contexts
    extra = actual_contexts - expected_contexts
    for ctx in sorted(missing):
        drift.append(
            DriftItem(
                field=f"required_status_checks.checks[{ctx}]",
                expected="required",
                actual="missing",
                severity="block",
            )
        )
    for ctx in sorted(extra):
        drift.append(
            DriftItem(
                field=f"required_status_checks.checks[{ctx}]",
                expected="not required",
                actual="present",
                severity="warn",
            )
        )
    return drift


def _diff_review_policy(
    expected: dict, actual: Optional[dict]
) -> list[DriftItem]:
    if actual is None:
        return [
            DriftItem(
                field="required_pull_request_reviews",
                expected=expected,
                actual=None,
                severity="block",
            )
        ]
    drift: list[DriftItem] = []
    for key in (
        "dismiss_stale_reviews",
        "require_code_owner_reviews",
        "require_last_push_approval",
        "required_approving_review_count",
    ):
        if actual.get(key) != expected.get(key):
            drift.append(
                DriftItem(
                    field=f"required_pull_request_reviews.{key}",
                    expected=expected.get(key),
                    actual=actual.get(key),
                    severity="block" if key == "required_approving_review_count" else "warn",
                )
            )
    return drift


def _diff_boolean_field(
    name: str, expected: Any, actual: Optional[dict]
) -> list[DriftItem]:
    """Diff a top-level boolean field. The GitHub REST API returns most
    protection booleans nested as `{"enabled": <bool>}` (e.g. required_linear_history,
    required_signatures, enforce_admins, allow_force_pushes, allow_deletions,
    required_conversation_resolution). The profile spec stores them as bare
    booleans. This helper normalizes both shapes so the diff is meaningful.
    """
    if actual is None:
        return [DriftItem(field=name, expected=expected, actual=None, severity="block")]
    raw = actual.get(name)
    if isinstance(raw, dict) and "enabled" in raw:
        actual_bool = raw["enabled"]
    else:
        actual_bool = raw
    if actual_bool != expected:
        return [DriftItem(
            field=name, expected=expected, actual=actual_bool, severity="warn"
        )]
    return []


def _diff_rulesets(
    expected: list[dict], actual: list[dict]
) -> list[DriftItem]:
    drift: list[DriftItem] = []
    expected_by_name = {r["name"]: r for r in expected}
    actual_by_name = {r["name"]: r for r in actual}
    for name in expected_by_name:
        if name not in actual_by_name:
            drift.append(
                DriftItem(
                    field=f"rulesets[{name}]",
                    expected="present",
                    actual="missing",
                    severity="block",
                )
            )
    for name in actual_by_name:
        if name not in expected_by_name:
            drift.append(
                DriftItem(
                    field=f"rulesets[{name}]",
                    expected="not in spec",
                    actual="present",
                    severity="warn",
                )
            )
    # The deep diff (rules within a ruleset) is left to a follow-up
    # — the v0 tool only checks ruleset presence, not rule structure,
    # to keep the apply sequence simple.
    return drift


# --- Public API ---

def audit(repo: str, profile: Optional[str] = None, spec: Optional[dict] = None) -> AuditResult:
    """Read the current state of <repo>'s main branch + diff against
    the named profile. If profile is None, the per_repo_overrides entry
    is used.
    """
    spec = spec or load_spec()
    if profile is None:
        profile, expected = resolve_repo_profile(spec, repo)
    else:
        if profile not in spec["profiles"]:
            raise BranchProtectionError(f"profile {profile!r} not found in spec")
        expected = dict(spec["profiles"][profile])

    classic = _read_classic_protection(repo)
    rulesets = _read_rulesets(repo)

    drift: list[DriftItem] = []
    drift.extend(
        _diff_required_status_checks(
            expected.get("required_status_checks", {}),
            _read_required_status_checks(repo) if classic else None,
        )
    )
    drift.extend(
        _diff_review_policy(
            expected.get("required_pull_request_reviews", {}),
            _read_review_policy(repo) if classic else None,
        )
    )
    for field in (
        "required_linear_history",
        "required_signatures",
        "required_conversation_resolution",
        "enforce_admins",
        "allow_force_pushes",
        "allow_deletions",
    ):
        drift.extend(
            _diff_boolean_field(field, expected.get(field), classic)
        )
    drift.extend(_diff_rulesets(expected.get("rulesets", []), rulesets))

    return AuditResult(
        repo=repo,
        profile=profile,
        drift=drift,
        checked_at=_now_iso(),
        source_url=f"https://github.com/{repo}/settings/branches",
    )


def apply(
    repo: str,
    profile: Optional[str] = None,
    dry_run: bool = True,
    spec: Optional[dict] = None,
) -> ApplyResult:
    """Apply the named profile to <repo>'s main branch.

    dry_run=True (default) prints the would-be API calls as a JSON
    list and exits. dry_run=False issues the calls via gh api.

    The apply sequence is:
      1. PUT /repos/{repo}/branches/main/protection (classic)
      2. POST /repos/{repo}/rulesets (for each ruleset in the profile)
    """
    spec = spec or load_spec()
    if profile is None:
        profile, expected = resolve_repo_profile(spec, repo)
    else:
        if profile not in spec["profiles"]:
            raise BranchProtectionError(f"profile {profile!r} not found in spec")
        expected = dict(spec["profiles"][profile])

    calls: list[dict] = []
    applied: list[str] = []
    skipped: list[str] = []

    # 1. Classic protection body.
    classic_body = _build_classic_body(expected)
    calls.append(
        {
            "method": "PUT",
            "path": f"repos/{repo}/branches/main/protection",
            "body": classic_body,
        }
    )
    if not dry_run:
        _gh_api("PUT", f"repos/{repo}/branches/main/protection", classic_body)
        applied.append(f"repos/{repo}/branches/main/protection")

    # 2. Rulesets — create if missing, leave existing alone (idempotent
    # for v0; full update is a follow-up).
    existing = {r["name"]: r for r in _read_rulesets(repo)}
    for rs in expected.get("rulesets", []):
        name = rs["name"]
        if name in existing:
            skipped.append(f"repos/{repo}/rulesets/{existing[name]['id']} (already exists)")
            continue
        rs_body = _build_ruleset_body(rs)
        calls.append(
            {"method": "POST", "path": f"repos/{repo}/rulesets", "body": rs_body}
        )
        if not dry_run:
            created = _gh_api("POST", f"repos/{repo}/rulesets", rs_body)
            applied.append(f"repos/{repo}/rulesets/{created.get('id', '?')}")

    return ApplyResult(
        repo=repo,
        profile=profile,
        dry_run=dry_run,
        calls=calls,
        applied=applied,
        skipped=skipped,
    )


def _build_classic_body(profile: dict) -> dict:
    """Build the body for PUT /branches/main/protection from a profile dict."""
    return {
        "required_status_checks": profile.get("required_status_checks"),
        "required_pull_request_reviews": profile.get("required_pull_request_reviews"),
        "required_linear_history": profile.get("required_linear_history", False),
        "required_signatures": profile.get("required_signatures", False),
        "required_conversation_resolution": profile.get(
            "required_conversation_resolution", False
        ),
        "enforce_admins": profile.get("enforce_admins", False),
        "allow_force_pushes": profile.get("allow_force_pushes", False),
        "allow_deletions": profile.get("allow_deletions", False),
        "restrictions": profile.get("restrictions"),
    }


def _build_ruleset_body(rs: dict) -> dict:
    """Build the body for POST /rulesets from a ruleset spec."""
    return {
        "name": rs["name"],
        "target": rs.get("target", "branch"),
        "enforcement": rs.get("enforcement", "active"),
        "conditions": rs.get("conditions", {"ref_name": {}}),
        "rules": rs.get("rules", []),
        "bypass_actors": rs.get("bypass_actors", []),
    }


def drift_check(
    org: str = "POWERFULMOVES", spec: Optional[dict] = None
) -> DriftReport:
    """Audit every repo in the spec's per_repo_overrides and return
    the union of drift. Use this from the Mavis cron to publish on
    pmoves.branch_protection.drift.v1.
    """
    import datetime as _dt
    spec = spec or load_spec()
    results: list[AuditResult] = []
    for repo in sorted(spec.get("per_repo_overrides", {}).keys()):
        if not repo.startswith(f"{org}/"):
            continue
        try:
            results.append(audit(repo, spec=spec))
        except BranchProtectionError as e:
            # Surface the error as a synthetic audit result so the
            # drift report still includes the repo.
            results.append(
                AuditResult(
                    repo=repo,
                    profile="?",
                    drift=[
                        DriftItem(
                            field="audit_error",
                            expected="readable",
                            actual=str(e),
                            severity="block",
                        )
                    ],
                    checked_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
                    source_url=f"https://github.com/{repo}/settings/branches",
                )
            )
    return DriftReport(
        org=org,
        checked_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        repos=results,
    )


# --- Helpers ---

def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# --- CLI ---

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="branch_protection",
        description=(
            "PMOVES standard branch-protection tool. "
            "Audit, apply, or drift-check the standard against a repo."
        ),
    )
    p.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="path to pmoves_standard.json (default: %(default)s)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="audit a single repo")
    p_audit.add_argument("--repo", required=True, help="org/repo (e.g. POWERFULMOVES/PMOVES.AI)")
    p_audit.add_argument("--profile", default=None, help="profile name (default: per_repo_overrides)")

    p_apply = sub.add_parser("apply", help="apply a profile to a repo")
    p_apply.add_argument("--repo", required=True)
    p_apply.add_argument("--profile", default=None)
    p_apply.add_argument(
        "--no-dry-run",
        action="store_true",
        help="actually issue the API calls (default: dry-run only)",
    )

    p_drift = sub.add_parser("drift-check", help="audit every repo in the spec")
    p_drift.add_argument("--org", default="POWERFULMOVES")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    spec = load_spec(args.spec)
    if args.cmd == "audit":
        result = audit(args.repo, args.profile, spec)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.is_compliant else 1
    if args.cmd == "apply":
        result = apply(args.repo, args.profile, dry_run=not args.no_dry_run, spec=spec)
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    if args.cmd == "drift-check":
        report = drift_check(args.org, spec)
        print(json.dumps(report.to_dict(), indent=2))
        non_compliant = [r for r in report.repos if not r.is_compliant]
        return 0 if not non_compliant else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
