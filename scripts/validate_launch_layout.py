#!/usr/bin/env python3
"""Validate PMOVES.AI launch-readiness layout against the TAC tree.

Reads pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml and verifies
every node's action.expect according to action.type. Outputs a markdown report
to pmoves/docs/launch/LAYOUT_VALIDATION_REPORT.md.

Action types supported in this version:
  - file_exists       expect: <relative_path>
  - file_or           expect: [<path1>, <path2>, ...] (at least one must exist)
  - manual            expect: <description> (always passes; surfaced for human)
  - gh_issue          expect: <title_substring> (uses `gh issue list`)
  - pytest            expect: <test_path> (file must exist; pass requires CI)
  - script            expect: <script_path> (file must exist)
  - nats_subject      expect: <subject> (deferred — requires running NATS)
  - pr_state          expect: {number, state} (uses `gh pr view`)
  - supabase_migration expect: <version_prefix> (file under pmoves/supabase/migrations/)
  - nats_messages_seen expect: {subject, min_count} (deferred — requires NATS history)

Exit code: 0 if all blocking nodes pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TAC_TREE_PATH = REPO_ROOT / "pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml"
REPORT_PATH = REPO_ROOT / "pmoves/docs/launch/LAYOUT_VALIDATION_REPORT.md"


@dataclass
class CheckResult:
    node_id: str
    task: str
    check_type: str
    passed: bool
    detail: str = ""
    blocking: bool = True


@dataclass
class ValidationContext:
    results: list[CheckResult] = field(default_factory=list)
    blocking_stages: set[str] = field(default_factory=set)


def load_tac_tree(path: Path) -> dict[str, Any]:
    """
    Load and parse a TAC tree YAML file from the given filesystem path.
    
    Parameters:
        path (Path): Path to the TAC YAML file to read.
    
    Returns:
        dict[str, Any]: Parsed TAC tree mapping as returned by yaml.safe_load.
    """
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_blocking_stages(tac: dict[str, Any]) -> set[str]:
    """
    Return the set of stage IDs required by the TAC tree's launch-blocking gate.
    
    Parameters:
        tac (dict): Parsed TAC YAML structure that may contain a `gates` mapping.
    
    Returns:
        set[str]: Stage IDs from `gates["launch-blocking"]["requires"]` as a set; empty set if the gate or requires list is missing.
    """
    gates = tac.get("gates") or {}
    blocking = gates.get("launch-blocking") or {}
    return set(blocking.get("requires") or [])


def repo_relative(path_str: str) -> Path:
    """
    Resolve a repository-relative path into a Path under the repository root.
    
    Parameters:
        path_str (str): A path string relative to the repository root.
    
    Returns:
        Path: The path obtained by joining the repository root and `path_str`.
    """
    return REPO_ROOT / path_str


def check_file_exists(expect: str) -> tuple[bool, str]:
    """
    Check that a repository-relative file path exists.
    
    Parameters:
        expect (str): Path relative to the repository root to verify.
    
    Returns:
        tuple[bool, str]: `True` and an "OK: <path>" message if the file exists, `False` and a "MISSING: <path>" message otherwise.
    """
    path = repo_relative(expect)
    if path.exists():
        return True, f"OK: {expect}"
    return False, f"MISSING: {expect}"


def check_file_or(expect: list[str]) -> tuple[bool, str]:
    """
    Return success if any of the given repository-relative paths exists.
    
    Parameters:
        expect (list[str]): List of repository-relative path strings to check.
    
    Returns:
        tuple[bool, str]: `True` and a message listing matched paths if any path exists; `False` and a message listing all provided paths if none exist.
    """
    found = [p for p in expect if repo_relative(p).exists()]
    if found:
        return True, f"OK (matched): {', '.join(found)}"
    return False, f"MISSING all of: {', '.join(expect)}"


def check_manual(expect: str) -> tuple[bool, str]:
    """
    Mark a node as manually satisfied and surface the provided instruction.
    
    Parameters:
    	expect (str): Manual instruction or note to display for the node.
    
    Returns:
    	tuple[bool, str]: `True` and a human-readable status message that includes the provided instruction.
    """
    return True, f"MANUAL (surfaced): {expect}"


def check_gh_issue(expect: str) -> tuple[bool, str]:
    """
    Check whether an open GitHub issue title contains a given substring.
    
    Parameters:
        expect (str): Substring to search for in the titles of open issues for POWERFULMOVES/PMOVES.AI (case-insensitive).
    
    Returns:
        tuple[bool, str]: 
            passed: `True` if any open issue title contains `expect`, `False` otherwise.
            detail: Human-readable message describing the match (`OK: issue #...`), a missing-notice (`MISSING: ...`), or a deferred error message when the `gh` CLI is unavailable or fails.
    """
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--repo", "POWERFULMOVES/PMOVES.AI",
             "--state", "open", "--limit", "100",
             "--json", "number,title"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        issues = json.loads(out.stdout or "[]")
        for issue in issues:
            if expect.lower() in (issue.get("title") or "").lower():
                return True, f"OK: issue #{issue['number']} matches '{expect}'"
        return False, f"MISSING: no open issue with title containing '{expect}'"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"DEFERRED (gh CLI unavailable or failed): {exc}"


def check_pytest_file(expect: str) -> tuple[bool, str]:
    """
    Determine whether a pytest file exists at the given repository-relative path.
    
    Parameters:
        expect (str): Repository-relative path or filename expected for the pytest file.
    
    Returns:
        tuple[bool, str]: `true` if a file exists at the given path, `false` otherwise; second element is a human-readable detail message.
    """
    return check_file_exists(expect)


def check_script(expect: str) -> tuple[bool, str]:
    """
    Check that a script file exists at the repository-relative path given by `expect`.
    
    Parameters:
        expect (str): Path to the script file relative to the repository root.
    
    Returns:
        tuple[bool, str]: `(True, detail)` if the file exists, `(False, detail)` otherwise. `detail` is a human-readable message describing the check result.
    """
    return check_file_exists(expect)


def check_nats_subject(expect: str) -> tuple[bool, str]:
    """
    Marks verification of a NATS subject as deferred because runtime access to a NATS server is required.
    
    Parameters:
        expect (str): NATS subject (or subject pattern) that would be verified.
    
    Returns:
        tuple[bool, str]: `False` to indicate the check is deferred, and a human-readable detail message explaining the deferred status and including the provided subject.
    """
    return False, f"DEFERRED (requires running NATS to verify subject): {expect}"


def check_pr_state(expect: dict[str, Any]) -> tuple[bool, str]:
    """
    Check that a GitHub pull request has the expected state.
    
    Parameters:
        expect (dict[str, Any]): Must contain `"number"` (PR number) and `"state"` (expected state string).
    
    Returns:
        tuple[bool, str]: `True` and an OK message if the PR's state matches `expect["state"]`, `False` and a descriptive message otherwise.
            - Returns `False` with "INVALID expect: ..." if required fields are missing.
            - Returns `False` with "MISMATCH: ..." when the PR state differs from the expected state.
            - Returns `False` with "DEFERRED (gh CLI unavailable or failed): ..." if the `gh` CLI is missing, exits non-zero, or times out.
    """
    number = expect.get("number")
    target_state = expect.get("state")
    if not number or not target_state:
        return False, f"INVALID expect: {expect}"
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "--repo", "POWERFULMOVES/PMOVES.AI",
             "--json", "state"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        data = json.loads(out.stdout)
        actual_state = (data.get("state") or "").lower()
        if actual_state == target_state.lower():
            return True, f"OK: PR #{number} is {actual_state}"
        return False, f"MISMATCH: PR #{number} is {actual_state}, expected {target_state}"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"DEFERRED (gh CLI unavailable or failed): {exc}"


def check_supabase_migration(expect: str) -> tuple[bool, str]:
    """
    Verify a Supabase migration file exists with the given filename prefix.
    
    Searches the repository's pmoves/supabase/migrations directory for files whose names start with `expect` and end with `.sql`. If the migrations directory is missing or no matching files are found the check fails; if one or more matches are found the check passes and returns their names.
    
    Parameters:
        expect (str): Filename prefix to search for among migration `.sql` files.
    
    Returns:
        tuple[bool, str]: `(True, message)` when matching migration files are found (message lists filenames);
                          `(False, message)` when the migrations directory is missing or no files match (message explains the reason).
    """
    migrations_dir = REPO_ROOT / "pmoves/supabase/migrations"
    if not migrations_dir.is_dir():
        return False, f"MISSING migrations directory at {migrations_dir}"
    matches = sorted(migrations_dir.glob(f"{expect}*.sql"))
    if matches:
        names = ", ".join(m.name for m in matches)
        return True, f"OK: migration(s) {names}"
    return False, f"MISSING migration prefixed {expect}*.sql"


def check_nats_messages_seen(expect: dict[str, Any]) -> tuple[bool, str]:
    """
    Marks a NATS "messages seen" check as deferred pending a JetStream history query.
    
    Parameters:
        expect (dict): Criteria for the NATS history query (e.g., subject, time range); the contents are included verbatim in the returned detail.
    
    Returns:
        tuple[bool, str]: `False` and a detail string indicating the check is deferred and echoing `expect`.
    """
    return False, f"DEFERRED (requires NATS JetStream history query): {expect}"


CHECK_DISPATCH = {
    "file_exists": check_file_exists,
    "file_or": check_file_or,
    "manual": check_manual,
    "gh_issue": check_gh_issue,
    "pytest": check_pytest_file,
    "script": check_script,
    "nats_subject": check_nats_subject,
    "pr_state": check_pr_state,
    "supabase_migration": check_supabase_migration,
    "nats_messages_seen": check_nats_messages_seen,
}


def walk_nodes(node: dict[str, Any], stage_id: str | None,
               ctx: ValidationContext) -> None:
    """
               Recursively traverse a TAC node tree and record validation results for any node actions.
               
               Walks `node` and its children, determining the current stage id (first ancestor whose id starts with "stage-") and, for nodes with an `action` dict, dispatching the action's `type` to the configured check handler. Appends a CheckResult to `ctx.results` for each checked node; the result's `blocking` flag is set when the active stage id is listed in `ctx.blocking_stages`.
               
               Parameters:
                   node (dict[str, Any]): A TAC node object; may contain keys `id`, `task`, `action`, and `children`.
                   stage_id (str | None): The current stage id inherited from parent calls; if None and the current node id starts with "stage-", the stage id is set to this node's id.
                   ctx (ValidationContext): Accumulator for check results and the set of blocking stage ids. 
               """
               node_id = node.get("id") or "<unknown>"
    if stage_id is None and node_id.startswith("stage-"):
        stage_id = node_id

    action = node.get("action")
    if action and isinstance(action, dict):
        check_type = action.get("type")
        expect = action.get("expect")
        handler = CHECK_DISPATCH.get(check_type or "")
        if handler is None:
            ctx.results.append(CheckResult(
                node_id=node_id,
                task=node.get("task", ""),
                check_type=str(check_type),
                passed=False,
                detail=f"UNKNOWN check type: {check_type}",
                blocking=stage_id in ctx.blocking_stages if stage_id else False,
            ))
        else:
            try:
                passed, detail = handler(expect)
            except Exception as exc:
                passed, detail = False, f"ERROR running check: {exc}"
            ctx.results.append(CheckResult(
                node_id=node_id,
                task=node.get("task", ""),
                check_type=str(check_type),
                passed=passed,
                detail=detail,
                blocking=stage_id in ctx.blocking_stages if stage_id else False,
            ))

    for child in node.get("children") or []:
        walk_nodes(child, stage_id, ctx)


def write_report(ctx: ValidationContext, path: Path) -> None:
    """
    Write a Markdown validation report of the collected check results to the given path.
    
    The report includes summary metrics for blocking and optional nodes, an overall gate status
    (`PASS` when there are no failing blocking nodes, `FAIL` otherwise), and a results table
    with one row per `CheckResult`. The function ensures the report's parent directory exists
    and escapes pipe characters in result details.
    
    Parameters:
        ctx (ValidationContext): Validation context containing collected `CheckResult` entries.
        path (Path): Filesystem path where the Markdown report will be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# PMOVES.AI Launch Layout Validation Report")
    lines.append("")
    lines.append("Generated by `scripts/validate_launch_layout.py`")
    lines.append("")
    blocking_total = sum(1 for r in ctx.results if r.blocking)
    blocking_pass = sum(1 for r in ctx.results if r.blocking and r.passed)
    blocking_fail = blocking_total - blocking_pass
    optional_total = sum(1 for r in ctx.results if not r.blocking)
    optional_pass = sum(1 for r in ctx.results if not r.blocking and r.passed)

    lines.append(f"- **Blocking nodes:** {blocking_pass}/{blocking_total} pass")
    lines.append(f"- **Optional (v1.1) nodes:** {optional_pass}/{optional_total} pass")
    lines.append(f"- **Overall gate:** {'PASS' if blocking_fail == 0 else 'FAIL'}")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Node | Type | Blocking | Status | Detail |")
    lines.append("|------|------|----------|--------|--------|")
    for r in ctx.results:
        status = "✅" if r.passed else "❌"
        blocking_marker = "yes" if r.blocking else "v1.1"
        detail = r.detail.replace("|", "\\|")
        lines.append(f"| `{r.node_id}` | {r.check_type} | {blocking_marker} | {status} | {detail} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """
    Validate a TAC launch-readiness layout and write a Markdown report.
    
    Parses command-line arguments, loads the TAC YAML, collects blocking stages, runs checks for each node, writes a validation report to the specified path, and prints a brief summary.
    
    Returns:
        int: Exit code where `0` means all blocking nodes passed, `1` means at least one blocking node failed, and `2` indicates a missing or invalid TAC input (missing file or missing `root`).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tac", default=str(TAC_TREE_PATH),
                        help="Path to TAC tree YAML")
    parser.add_argument("--report", default=str(REPORT_PATH),
                        help="Path to write validation report")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero on any non-passing blocking node "
                             "(default behavior is the same; flag retained for clarity)")
    args = parser.parse_args()

    tac_path = Path(args.tac)
    if not tac_path.is_file():
        print(f"ERROR: TAC tree not found at {tac_path}", file=sys.stderr)
        return 2

    tac = load_tac_tree(tac_path)
    ctx = ValidationContext(blocking_stages=collect_blocking_stages(tac))

    root = tac.get("root")
    if not root:
        print("ERROR: TAC tree has no 'root'", file=sys.stderr)
        return 2

    walk_nodes(root, None, ctx)
    write_report(ctx, Path(args.report))

    blocking_fail = sum(1 for r in ctx.results if r.blocking and not r.passed)
    blocking_pass = sum(1 for r in ctx.results if r.blocking and r.passed)
    blocking_total = blocking_pass + blocking_fail
    print(f"Layout validation: {blocking_pass}/{blocking_total} blocking nodes pass")
    print(f"Report: {args.report}")
    return 0 if blocking_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
