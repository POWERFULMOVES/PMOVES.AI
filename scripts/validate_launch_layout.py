#!/usr/bin/env python3
"""Validate PMOVES.AI launch-readiness layout against the TAC tree.

Reads pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml and verifies
every node's action.expect according to action.type. Outputs a markdown report
to pmoves/docs/launch/LAYOUT_VALIDATION_REPORT.md.

Action types supported in this version:
  - file_exists       expect: <relative_path>
  - file_or           expect: [<path1>, <path2>, ...] (at least one must exist)
  - manual            expect: <description> (UNVERIFIED; surfaced for a human witness)
  - gh_issue          expect: <title_substring> (uses `gh issue list`)
  - pytest            expect: <test_path> (missing = FAIL, present = UNVERIFIED; not run)
  - script            expect: <script_path> (missing = FAIL, present = UNVERIFIED; not run)
  - make_target       expect: <target> | {target, timeout, vars} (runs `make -C pmoves <target>`)
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


# Three verdicts, not two. "Could not measure is NOT a pass" is this repo's
# doctrine (0 clean / 1 findings / 3 could not measure), and until 2026-11-27
# this validator broke it in two ways: every `manual` node returned True, and
# `pytest` / `script` nodes returned True when the file merely EXISTED. That
# put seven unverified ticks and four never-run test files on the launch gate
# as green. A node is now PASS only when something was actually measured.
PASS = "pass"
UNVERIFIED = "unverified"
FAIL = "fail"


@dataclass
class CheckResult:
    node_id: str
    task: str
    check_type: str
    verdict: str
    detail: str = ""
    blocking: bool = True

    @property
    def passed(self) -> bool:
        return self.verdict == PASS


@dataclass
class ValidationContext:
    results: list[CheckResult] = field(default_factory=list)
    blocking_stages: set[str] = field(default_factory=set)


def load_tac_tree(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_blocking_stages(tac: dict[str, Any]) -> set[str]:
    gates = tac.get("gates") or {}
    blocking = gates.get("launch-blocking") or {}
    return set(blocking.get("requires") or [])


def repo_relative(path_str: str) -> Path:
    return REPO_ROOT / path_str


def check_file_exists(expect: str) -> tuple[str, str]:
    path = repo_relative(expect)
    if path.exists():
        return PASS, f"OK: {expect}"
    return FAIL, f"MISSING: {expect}"


def check_file_or(expect: list[str]) -> tuple[str, str]:
    found = [p for p in expect if repo_relative(p).exists()]
    if found:
        return PASS, f"OK (matched): {', '.join(found)}"
    return FAIL, f"MISSING all of: {', '.join(expect)}"


def check_manual(expect: str) -> tuple[str, str]:
    return UNVERIFIED, f"MANUAL (needs a human witness): {expect}"


def check_gh_issue(expect: str) -> tuple[str, str]:
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
                return PASS, f"OK: issue #{issue['number']} matches '{expect}'"
        return FAIL, f"MISSING: no open issue with title containing '{expect}'"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return UNVERIFIED, f"DEFERRED (gh CLI unavailable or failed): {exc}"


def _present_not_run(expect: str, what: str) -> tuple[str, str]:
    verdict, detail = check_file_exists(expect)
    if verdict != PASS:
        return verdict, detail
    return UNVERIFIED, f"PRESENT, NOT RUN ({what} existing is not {what} passing): {expect}"


def check_pytest_file(expect: str) -> tuple[str, str]:
    return _present_not_run(expect, "a test file")


def check_script(expect: str) -> tuple[str, str]:
    return _present_not_run(expect, "a script")


def check_nats_subject(expect: str) -> tuple[str, str]:
    return UNVERIFIED, f"DEFERRED (requires running NATS to verify subject): {expect}"


# Set by main(); --no-run turns every make_target node into UNVERIFIED so a
# quick layout pass never spends minutes in submodule or docs audits.
RUN_MAKE_TARGETS = True


def check_make_target(expect: Any) -> tuple[str, str]:
    """Run `make -C pmoves <target>` and take its exit code as the measure.

    `make` collapses every nonzero recipe exit to 2, so a target's own
    "3 = could not measure" is indistinguishable from "1 = findings" here.
    Both read as FAIL, with the output tail kept so a human can tell which.
    """
    if isinstance(expect, str):
        target, timeout, make_vars = expect, 300, {}
    else:
        target = expect.get("target")
        timeout = int(expect.get("timeout", 300))
        make_vars = expect.get("vars") or {}
    if not target:
        return FAIL, f"INVALID expect: {expect}"
    # Each var is ONE argv element (`ARGS=--strict`), never shell text.
    var_args = [f"{k}={v}" for k, v in make_vars.items()]
    if not RUN_MAKE_TARGETS:
        return UNVERIFIED, f"NOT RUN (--no-run): make -C pmoves {target}"
    try:
        out = subprocess.run(
            ["make", "-s", "-C", str(REPO_ROOT / "pmoves"), target, *var_args],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return UNVERIFIED, "DEFERRED (make not on PATH)"
    except subprocess.TimeoutExpired:
        return UNVERIFIED, f"DEFERRED (make {target} exceeded {timeout}s)"
    tail = " / ".join(
        line.strip() for line in (out.stdout + out.stderr).strip().splitlines()[-2:]
    )[:240]
    if out.returncode == 0:
        return PASS, f"OK: make {target} rc=0"
    return FAIL, f"make {target} rc={out.returncode}: {tail}"


def check_pr_state(expect: dict[str, Any]) -> tuple[str, str]:
    number = expect.get("number")
    target_state = expect.get("state")
    if not number or not target_state:
        return FAIL, f"INVALID expect: {expect}"
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "--repo", "POWERFULMOVES/PMOVES.AI",
             "--json", "state"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        data = json.loads(out.stdout)
        actual_state = (data.get("state") or "").lower()
        if actual_state == target_state.lower():
            return PASS, f"OK: PR #{number} is {actual_state}"
        return FAIL, f"MISMATCH: PR #{number} is {actual_state}, expected {target_state}"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return UNVERIFIED, f"DEFERRED (gh CLI unavailable or failed): {exc}"


def check_supabase_migration(expect: str) -> tuple[str, str]:
    migrations_dir = REPO_ROOT / "pmoves/supabase/migrations"
    if not migrations_dir.is_dir():
        return FAIL, f"MISSING migrations directory at {migrations_dir}"
    matches = sorted(migrations_dir.glob(f"{expect}*.sql"))
    if matches:
        names = ", ".join(m.name for m in matches)
        return PASS, f"OK: migration file(s) {names} (file present; applied-state not checked)"
    return FAIL, f"MISSING migration prefixed {expect}*.sql"


def check_nats_messages_seen(expect: dict[str, Any]) -> tuple[str, str]:
    return UNVERIFIED, f"DEFERRED (requires NATS JetStream history query): {expect}"


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
    "make_target": check_make_target,
}


def walk_nodes(node: dict[str, Any], stage_id: str | None,
               ctx: ValidationContext) -> None:
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
                verdict=FAIL,
                detail=f"UNKNOWN check type: {check_type}",
                blocking=stage_id in ctx.blocking_stages if stage_id else False,
            ))
        else:
            try:
                verdict, detail = handler(expect)
            except Exception as exc:
                verdict, detail = FAIL, f"ERROR running check: {exc}"
            ctx.results.append(CheckResult(
                node_id=node_id,
                task=node.get("task", ""),
                check_type=str(check_type),
                verdict=verdict,
                detail=detail,
                blocking=stage_id in ctx.blocking_stages if stage_id else False,
            ))

    for child in node.get("children") or []:
        walk_nodes(child, stage_id, ctx)


def tally(ctx: ValidationContext, blocking: bool) -> dict[str, int]:
    rows = [r for r in ctx.results if r.blocking == blocking]
    counts = {v: sum(1 for r in rows if r.verdict == v) for v in (PASS, UNVERIFIED, FAIL)}
    counts["total"] = len(rows)
    return counts


def summary_line(c: dict[str, int]) -> str:
    return (f"{c[PASS]}/{c['total']} pass · {c[UNVERIFIED]} unverified · "
            f"{c[FAIL]} fail")


def write_report(ctx: ValidationContext, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# PMOVES.AI Launch Layout Validation Report")
    lines.append("")
    lines.append("Generated by `scripts/validate_launch_layout.py`")
    lines.append("")
    b = tally(ctx, blocking=True)
    o = tally(ctx, blocking=False)

    lines.append(f"- **Blocking nodes:** {summary_line(b)}")
    lines.append(f"- **Optional (v1.1) nodes:** {summary_line(o)}")
    lines.append(f"- **Overall gate:** {'PASS' if b[PASS] == b['total'] else 'FAIL'}"
                 " (only a measured PASS counts; UNVERIFIED is not a pass)")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Node | Type | Blocking | Status | Detail |")
    lines.append("|------|------|----------|--------|--------|")
    icon = {PASS: "✅", UNVERIFIED: "⚪", FAIL: "❌"}
    for r in ctx.results:
        status = icon[r.verdict]
        blocking_marker = "yes" if r.blocking else "v1.1"
        detail = r.detail.replace("|", "\\|")
        lines.append(f"| `{r.node_id}` | {r.check_type} | {blocking_marker} | {status} | {detail} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tac", default=str(TAC_TREE_PATH),
                        help="Path to TAC tree YAML")
    parser.add_argument("--report", default=str(REPORT_PATH),
                        help="Path to write validation report")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero on any non-passing blocking node "
                             "(default behavior is the same; flag retained for clarity)")
    parser.add_argument("--no-run", action="store_true",
                        help="Do not run make_target checks; report them UNVERIFIED")
    args = parser.parse_args()
    global RUN_MAKE_TARGETS
    RUN_MAKE_TARGETS = not args.no_run

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

    b = tally(ctx, blocking=True)
    print(f"Layout validation, blocking nodes: {summary_line(b)}")
    print(f"Report: {args.report}")
    return 0 if b[PASS] == b["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
