"""pmoves/tools/branch_protection.py

The PMOVES ruleset tool. Single source of truth for the RULESETS
that the tool writes on every PMOVES org repo. The tool reads a
canonical spec (pmoves/configs/branch_protection/pmoves_standard.json),
audits the current rulesets via the GitHub REST API, diffs against
the spec, and can apply the spec to bring the rulesets into compliance.

The tool does NOT write classic branch protection. That is the
sole responsibility of .github/workflows/branch-protection-sync.yml.
Per the operator's 2026-08-10 ratification (recorded in
.pmoves/tools/LEARNINGS/branch-protection-v0_LEARNINGS.md) and
GitHub's "About rulesets" docs (the most-restrictive-version-of-
the-rule applies when classic + rulesets layer), the two
writers coexist: the workflow owns classic, the tool owns rulesets,
neither knows the other exists. Additive adoption is monotonic —
the tool can only make a branch stricter, never weaker.

Three public functions, all stdlib-only (urllib.request + json):

    audit(repo: str, profile: str) -> AuditResult
        Reads the current rulesets for <repo>'s gitlink-tracked
        branch + diffs against the named profile. Returns a
        structured drift report (deep diff: rules, conditions,
        bypass_actors — not just names).

    apply(repo: str, profile: str, dry_run: bool = True) -> ApplyResult
        Ensures the named profile's rulesets exist on <repo>'s
        branch with the right content. dry_run=True is the default
        and the safe mode; the tool prints the would-be API calls
        and exits. dry_run=False issues the calls. Existing rulesets
        with matching names are UPDATED to match the spec; missing
        rulesets are CREATED. (Classic branch protection is never
        touched by this tool.)

    drift_check(org: str) -> list[DriftReport]
        Scans every repo in <org> that has a per_repo_overrides
        entry in the spec, audits each, and returns the union of
        drift reports. Use this from the Mavis cron to surface
        drift on pmoves.branch_protection.drift.v1.

Branch resolution: for each repo, the tool resolves the target
branch by (in order) per_repo_overrides[repo].branch, then
.gitmodules[submodule.<name>].branch (matching the repo's
canonical-name slug), then the spec's "branch" default. The
default-default is main. This matches the workflow's behavior in
.github/workflows/branch-protection-sync.yml (55 of 60 submodules
track PMOVES.AI-Edition-Hardened, not main) — without this
resolution, the tool would write to the wrong branch on most forks
(N4 from the 4090 review).

NATS integration: the cron that calls drift_check() publishes the
result to pmoves.branch_protection.drift.v1 (canonical
<category>.<service>.<event>.<version> family per
.claude/context/nats-subjects.md). The orchestrator (from the
harness v0 slice) consumes the drift and dispatches a remediation
session.

GH auth: the tool shells out to `gh api` for the actual HTTP calls
because the PMOVES GitHub App token + operator PAT both flow
through gh's auth. Wrapping `gh api` gives the operator free
auth-state inspection. Tradeoff: the tool requires `gh` installed
and authenticated. Documented in BRANCH_PROTECTION_BASELINE.md.

Spec validation: the spec is validated on load — every profile
+ per_repo_overrides entry is type-checked against a strict
schema. A typo in a profile key fails the validator before the
tool hits the network. The PMOVES standard tool owns this
contract; classic protection is out of scope.

Tests: pmoves/tools/tests/test_branch_protection.py covers the spec
parser, the diff logic (deep ruleset diff), the branch resolution,
and the apply function's call sequence (with mocked gh api).
"""
from __future__ import annotations

import argparse
import configparser
import copy
import dataclasses
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


# --- Errors ---

class BranchProtectionError(Exception):
    """Raised for any tool-level error (missing spec, missing gh, invalid
    spec, etc.). Distinct from generic exceptions so the orchestrator
    can catch + decide: retry, fall back to a default profile, or
    refuse to start the session.
    """


# --- Result dataclasses ---

@dataclasses.dataclass
class DriftItem:
    field: str           # e.g. "rulesets[[ main ]].rules[3].parameters.required_approving_review_count"
    expected: Any
    actual: Any
    severity: str         # "block" (required gate missing) | "warn" (advisory drift)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AuditResult:
    repo: str
    profile: str
    branch: str           # the resolved branch (from override or .gitmodules or main)
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
            "branch": self.branch,
            "compliant": self.is_compliant,
            "drift": [d.to_dict() for d in self.drift],
            "checked_at": self.checked_at,
            "source_url": self.source_url,
        }


@dataclasses.dataclass
class ApplyResult:
    repo: str
    profile: str
    branch: str
    dry_run: bool
    calls: list[dict]   # each = {"method", "path", "body"}
    applied: list[str]  # paths that were called (empty in dry-run)
    skipped: list[str]  # rulesets that were already in sync (no-op)

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


# --- Spec loading + validation ---

DEFAULT_SPEC_PATH = (
    Path(__file__).parent.parent / "configs" / "branch_protection" / "pmoves_standard.json"
)

DEFAULT_BRANCH = "main"

# Valid top-level ruleset rule types as of 2026-08 per
# https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
VALID_RULESET_RULE_TYPES = frozenset({
    "creation", "update", "deletion", "required_linear_history", "non_fast_forward",
    "required_signatures", "required_conversation_resolution", "pull_request",
    "required_status_checks", "required_workflows",
    "required_code_scanning", "required_codeql", "required_secret_scanning",
    "required_deployments", "required_deployment_environments", "copilot_code_review",
    "file_path_restriction", "max_file_size", "max_file_path_length", "workflow_restrictions",
    "metadata_restrictions", "update_restrictions", "tag_name_pattern",
    "branch_name_pattern", "creation_time_limit",
})


class SpecValidator:
    """Strict validator for pmoves.rulesets spec shape.

    The validator enforces:
      - profiles is a dict with at least one entry
      - each profile has rulesets (list) and an optional branch
      - each ruleset has name, target, enforcement, rules, bypass_actors
      - each rules entry has a valid type from VALID_RULESET_RULE_TYPES
      - per_repo_overrides is a dict, each entry has profile + optional branch
    """

    def __init__(self, spec: dict):
        self.spec = spec
        self.errors: list[str] = []

    def validate(self) -> None:
        """Run all validations. Raises BranchProtectionError on the first
        hard error; collects all warnings.
        """
        self._validate_top_level()
        for name, profile in self.spec.get("profiles", {}).items():
            self._validate_profile(name, profile)
        for repo, override in self.spec.get("per_repo_overrides", {}).items():
            self._validate_override(repo, override)
        if self.errors:
            raise BranchProtectionError(
                f"spec validation failed ({len(self.errors)} error(s)):\n  "
                + "\n  ".join(self.errors)
            )

    def _validate_top_level(self) -> None:
        if "spec" not in self.spec:
            self.errors.append("missing top-level 'spec' key")
        if "profiles" not in self.spec or not isinstance(self.spec["profiles"], dict):
            self.errors.append("missing or non-dict 'profiles'")
        if "per_repo_overrides" not in self.spec or not isinstance(
            self.spec["per_repo_overrides"], dict
        ):
            self.errors.append("missing or non-dict 'per_repo_overrides'")
        if not self.spec.get("profiles"):
            self.errors.append("'profiles' is empty — at least one profile is required")
        if not self.spec.get("per_repo_overrides"):
            self.errors.append(
                "'per_repo_overrides' is empty — add at least one entry to cover a repo"
            )

    def _validate_profile(self, name: str, profile: dict) -> None:
        if not isinstance(profile, dict):
            self.errors.append(f"profile {name!r} is not a dict")
            return
        if "rulesets" not in profile or not isinstance(profile["rulesets"], list):
            self.errors.append(f"profile {name!r}: missing or non-list 'rulesets'")
        if not profile.get("rulesets"):
            self.errors.append(f"profile {name!r}: 'rulesets' is empty")
        for i, rs in enumerate(profile.get("rulesets", []) or []):
            self._validate_ruleset(f"profile {name!r}.rulesets[{i}]", rs)

    def _validate_ruleset(self, where: str, rs: Any) -> None:
        if not isinstance(rs, dict):
            self.errors.append(f"{where}: ruleset is not a dict")
            return
        if not rs.get("name"):
            self.errors.append(f"{where}: missing 'name'")
        if rs.get("target") not in ("branch", "tag", "push"):
            self.errors.append(
                f"{where}.target: {rs.get('target')!r} not in (branch, tag, push)"
            )
        if rs.get("enforcement") not in ("active", "disabled", "evaluate"):
            self.errors.append(
                f"{where}.enforcement: {rs.get('enforcement')!r} not in (active, disabled, evaluate)"
            )
        if not isinstance(rs.get("rules", []), list):
            self.errors.append(f"{where}: 'rules' is not a list")
        for j, rule in enumerate(rs.get("rules", []) or []):
            if not isinstance(rule, dict):
                self.errors.append(f"{where}.rules[{j}]: rule is not a dict")
                continue
            rtype = rule.get("type")
            if rtype not in VALID_RULESET_RULE_TYPES:
                self.errors.append(
                    f"{where}.rules[{j}].type: {rtype!r} not in VALID_RULESET_RULE_TYPES"
                )
        if not isinstance(rs.get("bypass_actors", []), list):
            self.errors.append(f"{where}: 'bypass_actors' is not a list")

    def _validate_override(self, repo: str, override: Any) -> None:
        if not isinstance(override, dict):
            self.errors.append(f"per_repo_overrides[{repo!r}]: not a dict")
            return
        if "profile" not in override:
            self.errors.append(f"per_repo_overrides[{repo!r}]: missing 'profile'")
        elif override["profile"] not in self.spec.get("profiles", {}):
            self.errors.append(
                f"per_repo_overrides[{repo!r}].profile: {override['profile']!r} "
                f"not in spec.profiles"
            )
        if "ruleset_overrides" in override and not isinstance(
            override["ruleset_overrides"], dict
        ):
            self.errors.append(
                f"per_repo_overrides[{repo!r}].ruleset_overrides: not a dict"
            )


def load_spec(path: Optional[Path] = None, validate: bool = True) -> dict:
    """Load + optionally validate the canonical spec. Pure-function for
    testability. A spec that fails validation raises BranchProtectionError
    BEFORE the tool hits the network.
    """
    p = path or DEFAULT_SPEC_PATH
    if not p.exists():
        raise BranchProtectionError(f"spec not found at {p}")
    spec = json.loads(p.read_text(encoding="utf-8"))
    if validate:
        SpecValidator(spec).validate()
    return spec


def resolve_repo_profile(spec: dict, repo: str) -> tuple[str, dict]:
    """Look up the named profile + per-repo overrides for a given repo.

    Returns (profile_name, merged_profile_dict). The merged dict has
    the profile defaults overridden by per_repo_overrides[repo]
    (specifically: branch and ruleset_overrides).
    """
    if repo not in spec.get("per_repo_overrides", {}):
        raise BranchProtectionError(
            f"no per_repo_overrides entry for {repo}; "
            f"add one to the spec"
        )
    override = spec["per_repo_overrides"][repo]
    profile_name = override.get("profile")
    if profile_name not in spec.get("profiles", {}):
        raise BranchProtectionError(f"profile {profile_name!r} not found in spec")
    profile = copy.deepcopy(spec["profiles"][profile_name])
    # Apply per-repo ruleset overrides. For the `rules` list specifically,
    # merge by `type` so an override for `required_status_checks` extends
    # the base ruleset (rather than replacing it). For all other keys
    # (name, target, enforcement, conditions, bypass_actors), the override
    # fully replaces the base value.
    for rs_name, rs_override in override.get("ruleset_overrides", {}).items():
        target = next((r for r in profile["rulesets"] if r.get("name") == rs_name), None)
        if target is None:
            profile["rulesets"].append(copy.deepcopy(rs_override))
            continue
        for key, value in rs_override.items():
            if key == "rules" and isinstance(value, list) and isinstance(target.get("rules"), list):
                base_by_type = {r.get("type"): r for r in target["rules"]}
                override_by_type = {r.get("type"): r for r in value}
                # Rules in the override replace rules of the same type in
                # the base; rules in the base but not the override are
                # kept. Result: base + override deltas.
                merged_types = []
                for t in base_by_type:
                    if t in override_by_type:
                        merged_types.append(copy.deepcopy(override_by_type[t]))
                    else:
                        merged_types.append(copy.deepcopy(base_by_type[t]))
                for t in override_by_type:
                    if t not in base_by_type:
                        merged_types.append(copy.deepcopy(override_by_type[t]))
                target["rules"] = merged_types
            else:
                target[key] = copy.deepcopy(value)
    return profile_name, profile


# --- Branch resolution ---

# The repo name slug for .gitmodules lookup. The PMOVES fork naming is
# sometimes "PMOVES-foo", sometimes "Pmoves-foo", but .gitmodules
# always uses the repo's display name verbatim.
def _gitmodules_path() -> Path:
    """Return the .gitmodules path. Walks up from CWD until it finds one,
    falls back to a default-relative path. Cached per process.
    """
    cwd = Path.cwd()
    for p in [cwd, *cwd.parents]:
        candidate = p / ".gitmodules"
        if candidate.exists():
            return candidate
    return Path(".gitmodules")


def resolve_branch(repo: str, override_branch: Optional[str], spec: dict) -> str:
    """Resolve the target branch for a repo, in order:

      1. override_branch (from per_repo_overrides[repo].branch)
      2. .gitmodules[submodule.<slug>].branch
      3. spec.profiles[profile].branch (if set)
      4. DEFAULT_BRANCH = "main"

    The first non-empty wins. The .gitmodules lookup matches the
    workflow's logic in branch-protection-sync.yml (the canonical
    writer of classic protection) — so the two writers agree on
    which branch to target for each fork.
    """
    if override_branch:
        return override_branch

    # 2. .gitmodules
    slug = repo.split("/", 1)[-1]  # "POWERFULMOVES/PMOVES.AI" -> "PMOVES.AI"
    try:
        cfg = configparser.ConfigParser()
        cfg.read(_gitmodules_path())
        for section in cfg.sections():
            if cfg.get(section, "url", fallback="") and slug in section:
                branch = cfg.get(section, "branch", fallback=None)
                if branch:
                    return branch
    except (configparser.Error, OSError):
        pass  # no .gitmodules or unreadable; fall through

    # 3. spec default (rarely used; the fork profile omits branch)
    for profile in spec.get("profiles", {}).values():
        b = profile.get("branch")
        if b:
            return b

    return DEFAULT_BRANCH


# --- GitHub REST API access via `gh` ---

GH_TIMEOUT_SECONDS = 30


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
            timeout=GH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        raise BranchProtectionError(f"gh subprocess failed: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise BranchProtectionError(
            f"gh api {method} {path} timed out after {GH_TIMEOUT_SECONDS}s"
        ) from e
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

def _list_rulesets(repo: str) -> list[dict]:
    """Returns the list of rulesets for the repo (may be empty).
    The list endpoint returns a SUMMARY without bypass_actors +
    full rule bodies — re-fetch the per-ruleset body for each.
    """
    data = _gh_api("GET", f"repos/{repo}/rulesets")
    if not data:
        return []
    full = []
    for rs in data:
        rs_id = rs.get("id")
        if not rs_id:
            continue
        # Re-fetch the per-ruleset body to get bypass_actors + full rules.
        body = _gh_api("GET", f"repos/{repo}/rulesets/{rs_id}")
        if body:
            full.append(body)
    return full


# --- Diff logic ---

def _ruleset_matches(expected: dict, actual: dict) -> list[DriftItem]:
    """Deep-diff a single ruleset. Returns [] if the actual ruleset
    matches the spec; otherwise a list of drift items identifying
    which fields differ.
    """
    drift: list[DriftItem] = []
    name = expected.get("name", "?")

    if actual.get("target") != expected.get("target"):
        drift.append(DriftItem(
            field=f"rulesets[{name}].target",
            expected=expected.get("target"),
            actual=actual.get("target"),
            severity="warn",
        ))
    if actual.get("enforcement") != expected.get("enforcement"):
        drift.append(DriftItem(
            field=f"rulesets[{name}].enforcement",
            expected=expected.get("enforcement"),
            actual=actual.get("enforcement"),
            severity="block",
        ))

    # Conditions: the API returns {ref_name: {include: [...], exclude: [...]}}
    # (different shape than the spec's {ref_name: {include: ["~DEFAULT_BRANCH"], exclude: []}}).
    # Normalize "~DEFAULT_BRANCH" to the actual default branch before comparing.
    actual_conditions = actual.get("conditions", {}).get("ref_name", {})
    expected_conditions = copy.deepcopy(expected.get("conditions", {}).get("ref_name", {}))
    expected_includes = expected_conditions.get("include", [])
    if "~DEFAULT_BRANCH" in expected_includes:
        # The spec's "~DEFAULT_BRANCH" is a sentinel; the actual conditions
        # carry the literal branch name. The diff cannot compare without
        # knowing the actual default branch, so skip the include check
        # entirely (the spec author already declared the target as
        # "the default branch" by using the sentinel).
        pass
    else:
        actual_includes = sorted(actual_conditions.get("include", []))
        expected_includes_sorted = sorted(expected_includes)
        if actual_includes != expected_includes_sorted:
            drift.append(DriftItem(
                field=f"rulesets[{name}].conditions.ref_name.include",
                expected=expected_includes_sorted,
                actual=actual_includes,
                severity="warn",
            ))

    # Rules: compare by type + parameters
    actual_rules = {r.get("type"): r for r in actual.get("rules", [])}
    for exp_rule in expected.get("rules", []):
        rtype = exp_rule.get("type")
        if rtype not in actual_rules:
            drift.append(DriftItem(
                field=f"rulesets[{name}].rules[type={rtype}]",
                expected="present",
                actual="missing",
                severity="block",
            ))
            continue
        act_rule = actual_rules[rtype]
        if exp_rule.get("parameters", {}) != act_rule.get("parameters", {}):
            drift.append(DriftItem(
                field=f"rulesets[{name}].rules[type={rtype}].parameters",
                expected=exp_rule.get("parameters"),
                actual=act_rule.get("parameters"),
                severity="block",
            ))

    # Extra rules not in spec — warn
    expected_types = {r.get("type") for r in expected.get("rules", [])}
    for rtype in actual_rules:
        if rtype not in expected_types:
            drift.append(DriftItem(
                field=f"rulesets[{name}].rules[type={rtype}]",
                expected="not in spec",
                actual="present",
                severity="warn",
            ))

    # Bypass actors: compare by (actor_id, actor_type, bypass_mode)
    actual_actors = actual.get("bypass_actors", [])
    expected_actors = expected.get("bypass_actors", [])
    actual_set = {(a.get("actor_id"), a.get("actor_type"), a.get("bypass_mode")) for a in actual_actors}
    expected_set = {(a.get("actor_id"), a.get("actor_type"), a.get("bypass_mode")) for a in expected_actors}
    if actual_set != expected_set:
        drift.append(DriftItem(
            field=f"rulesets[{name}].bypass_actors",
            expected=sorted(expected_actors, key=str),
            actual=sorted(actual_actors, key=str),
            severity="block",
        ))

    return drift


# --- Public API ---

def audit(repo: str, profile: Optional[str] = None, spec: Optional[dict] = None) -> AuditResult:
    """Read the current rulesets for <repo>'s gitlink-tracked branch +
    diff against the named profile. If profile is None, the
    per_repo_overrides entry is used.
    """
    spec = spec or load_spec()
    if profile is None:
        profile, expected_profile = resolve_repo_profile(spec, repo)
    else:
        if profile not in spec["profiles"]:
            raise BranchProtectionError(f"profile {profile!r} not found in spec")
        expected_profile = copy.deepcopy(spec["profiles"][profile])

    override = spec.get("per_repo_overrides", {}).get(repo, {})
    branch = resolve_branch(repo, override.get("branch"), spec)

    actual = _list_rulesets(repo)
    expected_by_name = {r.get("name"): r for r in expected_profile.get("rulesets", [])}
    actual_by_name = {r.get("name"): r for r in actual}

    drift: list[DriftItem] = []
    for name, expected_rs in expected_by_name.items():
        if name not in actual_by_name:
            drift.append(DriftItem(
                field=f"rulesets[{name}]",
                expected="present",
                actual="missing",
                severity="block",
            ))
            continue
        drift.extend(_ruleset_matches(expected_rs, actual_by_name[name]))

    for name in actual_by_name:
        if name not in expected_by_name:
            drift.append(DriftItem(
                field=f"rulesets[{name}]",
                expected="not in spec",
                actual="present",
                severity="warn",
            ))

    return AuditResult(
        repo=repo,
        profile=profile,
        branch=branch,
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
    """Ensure the named profile's rulesets exist on <repo>'s branch
    with the right content. dry_run=True (default) prints the
    would-be API calls and exits. dry_run=False issues the calls.

    The apply sequence:
      1. List existing rulesets for the repo.
      2. For each expected ruleset:
         - If missing: POST /repos/{repo}/rulesets
         - If present but drift: PUT /repos/{repo}/rulesets/{id}
         - If present and no drift: skip (idempotent)

    Classic branch protection is never touched by this tool.
    """
    spec = spec or load_spec()
    if profile is None:
        profile, expected_profile = resolve_repo_profile(spec, repo)
    else:
        if profile not in spec["profiles"]:
            raise BranchProtectionError(f"profile {profile!r} not found in spec")
        expected_profile = copy.deepcopy(spec["profiles"][profile])

    override = spec.get("per_repo_overrides", {}).get(repo, {})
    branch = resolve_branch(repo, override.get("branch"), spec)

    calls: list[dict] = []
    applied: list[str] = []
    skipped: list[str] = []

    # Always dry-run fetches the existing rulesets (for drift detection).
    # The read is in both modes; only the writes differ.
    actual = _list_rulesets(repo)
    actual_by_name = {r.get("name"): r for r in actual}
    expected_by_name = {r.get("name"): r for r in expected_profile.get("rulesets", [])}

    for name, expected_rs in expected_by_name.items():
        if name not in actual_by_name:
            # CREATE
            body = _build_ruleset_body(expected_rs)
            calls.append({
                "method": "POST",
                "path": f"repos/{repo}/rulesets",
                "body": body,
            })
            if not dry_run:
                created = _gh_api("POST", f"repos/{repo}/rulesets", body)
                applied.append(f"repos/{repo}/rulesets/{created.get('id', '?')}")
        else:
            # UPDATE if drift
            existing = actual_by_name[name]
            drift = _ruleset_matches(expected_rs, existing)
            if not drift:
                skipped.append(f"repos/{repo}/rulesets/{existing.get('id', '?')} (in sync)")
                continue
            body = _build_ruleset_body(expected_rs)
            calls.append({
                "method": "PUT",
                "path": f"repos/{repo}/rulesets/{existing.get('id')}",
                "body": body,
            })
            if not dry_run:
                _gh_api("PUT", f"repos/{repo}/rulesets/{existing.get('id')}", body)
                applied.append(f"repos/{repo}/rulesets/{existing.get('id')}")

    return ApplyResult(
        repo=repo,
        profile=profile,
        branch=branch,
        dry_run=dry_run,
        calls=calls,
        applied=applied,
        skipped=skipped,
    )


def _build_ruleset_body(rs: dict) -> dict:
    """Build the body for POST /rulesets (or PUT /rulesets/{id}) from
    a ruleset spec. Strips the local sentinel `~DEFAULT_BRANCH` from
    conditions.ref_name.include (the GitHub API takes the literal
    default-branch name, not the sentinel).
    """
    body = {
        "name": rs["name"],
        "target": rs.get("target", "branch"),
        "enforcement": rs.get("enforcement", "active"),
        "conditions": copy.deepcopy(rs.get("conditions", {"ref_name": {}})),
        "rules": copy.deepcopy(rs.get("rules", [])),
        "bypass_actors": copy.deepcopy(rs.get("bypass_actors", [])),
    }
    includes = body.get("conditions", {}).get("ref_name", {}).get("include", [])
    if "~DEFAULT_BRANCH" in includes:
        body["conditions"]["ref_name"]["include"] = [
            c for c in includes if c != "~DEFAULT_BRANCH"
        ]
    return body


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
            results.append(
                AuditResult(
                    repo=repo,
                    profile="?",
                    branch="?",
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
            "PMOVES ruleset tool. "
            "Audit, apply, or drift-check the ruleset spec against a repo. "
            "The tool writes RULESETS only; classic branch protection is "
            "the responsibility of .github/workflows/branch-protection-sync.yml."
        ),
    )
    p.add_argument(
        "--spec",
        type=Path,
        default=DEFAULT_SPEC_PATH,
        help="path to pmoves_standard.json (default: %(default)s)",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="skip spec validation (debugging only)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="audit a single repo")
    p_audit.add_argument("--repo", required=True, help="org/repo (e.g. POWERFULMOVES/PMOVES.AI)")
    p_audit.add_argument("--profile", default=None, help="profile name (default: per_repo_overrides)")

    p_apply = sub.add_parser("apply", help="apply a profile to a repo (writes RULESETS only)")
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
    spec = load_spec(args.spec, validate=not args.no_validate)
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
