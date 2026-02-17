#!/usr/bin/env python3
"""Map workflow runner lanes to host assignments and optional live runner status."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RUNS_ON_LIST_RE = re.compile(r"runs-on:\s*\[([^\]]+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class Runner:
    name: str
    status: str
    busy: bool
    labels: tuple[str, ...]

    @property
    def online(self) -> bool:
        return self.status.lower() == "online"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover self-hosted lanes from workflow files and map them to "
            "host inventory entries."
        )
    )
    parser.add_argument(
        "--workflows-dir",
        default=".github/workflows",
        help="Workflow directory (default: %(default)s)",
    )
    parser.add_argument(
        "--mapping",
        default="integrations/github-runners/compose/lane_hosts.json",
        help="Lane mapping JSON file",
    )
    parser.add_argument(
        "--repo",
        default="POWERFULMOVES/PMOVES.AI",
        help="GitHub repository (OWNER/REPO) for live runner status",
    )
    parser.add_argument(
        "--check-gh",
        action="store_true",
        help="Query GitHub Actions runner status via gh api",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on unmapped lanes or unavailable live lanes.",
    )
    parser.add_argument(
        "--emit-markdown",
        default="",
        help="Optional file path to write markdown table output.",
    )
    parser.add_argument(
        "--policy-file",
        default="integrations/github-runners/compose/runner_phase_policy.json",
        help="Runner phase policy JSON file.",
    )
    parser.add_argument(
        "--phase",
        default="",
        help="Phase name from policy file (for example: local-certification).",
    )
    parser.add_argument(
        "--enforce-phase",
        action="store_true",
        help="Enforce phase required_online/required_offline checks.",
    )
    return parser.parse_args()


def normalize_group(raw: str) -> tuple[str, ...]:
    labels_set = {part.strip().strip("'\"") for part in raw.split(",") if part.strip()}
    labels = sorted(labels_set, key=lambda item: (0 if item == "self-hosted" else 1, item))
    return tuple(labels)


def discover_groups(workflows_dir: Path) -> list[tuple[str, ...]]:
    groups: set[tuple[str, ...]] = set()
    if not workflows_dir.exists():
        return []
    for wf in sorted(workflows_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        for match in RUNS_ON_LIST_RE.finditer(text):
            group = normalize_group(match.group(1))
            if "self-hosted" in group:
                groups.add(group)
    return sorted(groups)


def normalize_key(raw: str) -> str:
    return ",".join(normalize_group(raw))


def load_mapping(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    lane_hosts = payload.get("lane_hosts", {})
    out: dict[str, dict] = {}
    for raw_key, value in lane_hosts.items():
        out[normalize_key(raw_key)] = value
    return out


def load_policy(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(raw: str, candidates: list[Path]) -> Path:
    direct = Path(raw)
    if direct.exists():
        return direct
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return direct


def load_runners(repo: str) -> list[Runner]:
    cmd = ["gh", "api", f"repos/{repo}/actions/runners?per_page=100"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "unknown gh api error"
        raise RuntimeError(msg)
    payload = json.loads(proc.stdout)
    runners: list[Runner] = []
    for item in payload.get("runners", []):
        labels = tuple(sorted(label.get("name", "") for label in item.get("labels", [])))
        runners.append(
            Runner(
                name=item.get("name", "unknown"),
                status=item.get("status", "unknown"),
                busy=bool(item.get("busy", False)),
                labels=tuple(label for label in labels if label),
            )
        )
    return runners


def lane_online(group: tuple[str, ...], runners: list[Runner]) -> tuple[bool, str]:
    wanted = set(group)
    matches = [runner for runner in runners if wanted.issubset(set(runner.labels))]
    online = [runner for runner in matches if runner.online]
    if online:
        return True, ", ".join(sorted(r.name for r in online))
    if matches:
        return False, "registered but offline"
    return False, "no matching runner"


def to_markdown(rows: list[dict[str, str]]) -> str:
    header = (
        "| Lane | Host | Runner Name | Registration Script | Live Status |\n"
        "| --- | --- | --- | --- | --- |\n"
    )
    body = "\n".join(
        f"| `{row['lane']}` | {row['host']} | `{row['runner_name']}` | `{row['script']}` | {row['status']} |"
        for row in rows
    )
    return header + body + ("\n" if body else "")


def evaluate_phase(
    phase_name: str,
    phase_cfg: dict,
    group_by_lane: dict[str, tuple[str, ...]],
    runners: list[Runner],
    check_gh: bool,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    notes: list[str] = []

    required_online = [normalize_key(item) for item in phase_cfg.get("required_online", [])]
    required_offline = [normalize_key(item) for item in phase_cfg.get("required_offline", [])]

    for lane in required_online:
        group = group_by_lane.get(lane)
        if not group:
            failures.append(f"[{phase_name}] required_online lane missing from workflows: {lane}")
            continue
        if check_gh:
            ok, detail = lane_online(group, runners)
            if not ok:
                failures.append(f"[{phase_name}] lane must be online but is offline: {lane} ({detail})")
        else:
            notes.append(f"[{phase_name}] cannot validate online state without --check-gh: {lane}")

    for lane in required_offline:
        group = group_by_lane.get(lane)
        if not group:
            notes.append(f"[{phase_name}] required_offline lane not present in workflows: {lane}")
            continue
        if check_gh:
            ok, detail = lane_online(group, runners)
            if ok:
                failures.append(f"[{phase_name}] lane must be offline but is online: {lane} ({detail})")
        else:
            notes.append(f"[{phase_name}] cannot validate offline state without --check-gh: {lane}")

    return failures, notes


def main() -> int:
    args = parse_args()
    pmoves_root = Path(__file__).resolve().parents[1]
    repo_root = pmoves_root.parent

    workflows_dir = resolve_path(
        args.workflows_dir,
        [
            pmoves_root / args.workflows_dir,
            repo_root / args.workflows_dir,
            repo_root / ".github" / "workflows",
        ],
    )
    mapping_path = resolve_path(
        args.mapping,
        [
            pmoves_root / args.mapping,
            repo_root / args.mapping,
            repo_root / "pmoves" / "integrations" / "github-runners" / "compose" / "lane_hosts.json",
        ],
    )
    policy_path = resolve_path(
        args.policy_file,
        [
            pmoves_root / args.policy_file,
            repo_root / args.policy_file,
            repo_root / "pmoves" / "integrations" / "github-runners" / "compose" / "runner_phase_policy.json",
        ],
    )

    if not workflows_dir.exists():
        print(f"ERROR: workflow directory not found: {workflows_dir}")
        return 2
    if not mapping_path.exists():
        print(f"ERROR: mapping file not found: {mapping_path}")
        return 2
    if not policy_path.exists():
        print(f"ERROR: policy file not found: {policy_path}")
        return 2

    groups = discover_groups(workflows_dir)
    repo_workflows = repo_root / ".github" / "workflows"
    if not groups and repo_workflows.exists() and repo_workflows != workflows_dir:
        groups = discover_groups(repo_workflows)
        if groups:
            workflows_dir = repo_workflows
    mapping = load_mapping(mapping_path)
    policy = load_policy(policy_path)
    runners: list[Runner] = []
    if args.check_gh:
        runners = load_runners(args.repo)

    rows: list[dict[str, str]] = []
    unmapped: list[str] = []
    unavailable: list[str] = []
    phase_failures: list[str] = []
    phase_notes: list[str] = []

    for group in groups:
        lane = ",".join(group)
        meta = mapping.get(lane)
        if not meta:
            unmapped.append(lane)
            rows.append(
                {
                    "lane": lane,
                    "host": "UNMAPPED",
                    "runner_name": "UNMAPPED",
                    "script": "UNMAPPED",
                    "status": "UNMAPPED",
                }
            )
            continue

        live_status = "not checked"
        if args.check_gh:
            ok, detail = lane_online(group, runners)
            live_status = f"online ({detail})" if ok else f"offline ({detail})"
            if not ok:
                unavailable.append(lane)

        rows.append(
            {
                "lane": lane,
                "host": meta.get("host", "UNKNOWN"),
                "runner_name": meta.get("runner_name", "UNKNOWN"),
                "script": meta.get("registration_script", "UNKNOWN"),
                "status": live_status,
            }
        )

    print("Runner lane map")
    print(f"- workflows: {workflows_dir}")
    print(f"- mapping: {mapping_path}")
    print(f"- policy: {policy_path}")
    print(f"- lanes discovered: {len(groups)}")
    if args.check_gh:
        print(f"- gh runner checks: enabled (repo={args.repo})")
    else:
        print("- gh runner checks: disabled")
    print()
    print(to_markdown(rows))

    selected_phase = args.phase.strip()
    if args.enforce_phase:
        if not selected_phase:
            selected_phase = str(policy.get("default_phase", "")).strip()
        phases = policy.get("phases", {})
        if not selected_phase:
            phase_failures.append("No phase specified and policy has no default_phase.")
        elif selected_phase not in phases:
            phase_failures.append(f"Phase not found in policy: {selected_phase}")
        else:
            group_by_lane = {",".join(group): group for group in groups}
            failures, notes = evaluate_phase(
                selected_phase, phases[selected_phase], group_by_lane, runners, args.check_gh
            )
            phase_failures.extend(failures)
            phase_notes.extend(notes)
            print(f"Phase check: {selected_phase}")
            if phases[selected_phase].get("description"):
                print(f"- {phases[selected_phase]['description']}")
            if not failures:
                print("- status: PASS")
            else:
                print("- status: FAIL")
            print()

    if args.emit_markdown:
        Path(args.emit_markdown).write_text(to_markdown(rows), encoding="utf-8")
        print(f"Wrote markdown table: {args.emit_markdown}")

    if unmapped:
        print("WARN: unmapped lanes:")
        for lane in unmapped:
            print(f"  - {lane}")
    if unavailable:
        print("WARN: unavailable lanes:")
        for lane in unavailable:
            print(f"  - {lane}")
    if phase_notes:
        print("INFO: phase notes:")
        for note in phase_notes:
            print(f"  - {note}")
    if phase_failures:
        print("ERROR: phase policy failures:")
        for failure in phase_failures:
            print(f"  - {failure}")

    strict_fail = bool(unmapped)
    if args.strict:
        if args.enforce_phase:
            strict_fail = strict_fail or bool(phase_failures)
        else:
            strict_fail = strict_fail or bool(unavailable)
    if strict_fail:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
