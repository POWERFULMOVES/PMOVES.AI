#!/usr/bin/env python3
"""
PMOVES.AI Living Document Reconciliation Tool

Checks and updates living document metadata (dashboard commit SHA, dates)
and flags stale tracker items whose submodules have advanced.

Usage:
    python pmoves/tools/docs_reconcile.py --check          # read-only, CI-safe
    python pmoves/tools/docs_reconcile.py --update         # write corrected metadata
    python pmoves/tools/docs_reconcile.py --check --json   # machine-readable output

Make targets:
    make -C pmoves docs-reconcile-check   # read-only
    make -C pmoves docs-reconcile         # update metadata
    make -C pmoves docs-reconcile-json    # JSON report

Exit codes:
    0 = fresh (no stale findings)
    1 = stale findings detected
    2 = error (missing files, git failure)
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# ── Paths (relative to pmoves/) ─────────────────────────────────────

DASHBOARD_REL = "docs/PRODUCTION_AUDIT_DASHBOARD.md"
TRACKER_REL = "docs/security/P2_SUBMODULE_TRACKER.md"
REGISTRY_REL = "configs/living_docs_registry.yaml"


# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class DashboardMeta:
    """Parsed metadata from dashboard header."""

    last_updated: str = ""
    branch: str = ""
    commit: str = ""
    file_path: str = ""


@dataclass
class TrackerItem:
    """A single row from the P2 tracker table."""

    number: str = ""
    submodule: str = ""
    issue: str = ""
    severity: str = ""
    status: str = ""
    section: str = ""


@dataclass
class GitState:
    """Current git repository state."""

    branch: str = ""
    short_sha: str = ""
    full_sha: str = ""
    utc_date: str = ""
    commits_since: int = 0  # commits since dashboard SHA


@dataclass
class Finding:
    """A reconciliation finding."""

    category: str  # stale_commit, stale_date, stale_tracker, submodule_drift, stale_doc
    severity: str  # P1, P2, INFO
    message: str
    current: str = ""
    expected: str = ""


@dataclass
class TrackedDoc:
    """A registry entry from living_docs_registry.yaml."""

    path: str
    freshness_days: int = 30
    severity: str = "P2"
    description: str = ""


@dataclass
class ReconcileReport:
    """Complete reconciliation report."""

    findings: List[Finding] = field(default_factory=list)
    dashboard_meta: Optional[DashboardMeta] = None
    git_state: Optional[GitState] = None
    tracker_items_total: int = 0
    tracker_items_open: int = 0
    updated: bool = False

    @property
    def stale_count(self) -> int:
        return sum(1 for f in self.findings if f.severity in ("P1", "P2"))

    @property
    def p1_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P1")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "INFO")


# ── Git helpers ──────────────────────────────────────────────────────


def _run_git(*args: str, cwd: Optional[Path] = None) -> Optional[str]:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_git_state(repo_root: Path, dashboard_sha: str) -> GitState:
    """Get current git branch, SHA, and commit distance from dashboard SHA."""
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root) or "unknown"
    short_sha = _run_git("rev-parse", "--short", "HEAD", cwd=repo_root) or "unknown"
    full_sha = _run_git("rev-parse", "HEAD", cwd=repo_root) or "unknown"

    # UTC date of HEAD
    date_raw = _run_git("log", "-1", "--format=%aI", cwd=repo_root) or ""
    utc_date = date_raw[:10] if date_raw else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Count commits since dashboard SHA
    commits_since = 0
    if dashboard_sha and dashboard_sha != "unknown":
        count_str = _run_git(
            "rev-list", "--count", f"{dashboard_sha}..HEAD", cwd=repo_root
        )
        if count_str and count_str.isdigit():
            commits_since = int(count_str)

    return GitState(
        branch=branch,
        short_sha=short_sha,
        full_sha=full_sha,
        utc_date=utc_date,
        commits_since=commits_since,
    )


def get_file_last_commit_date(repo_root: Path, rel_path: str) -> Optional[str]:
    """Return the date (YYYY-MM-DD) of the last commit that touched rel_path.

    Falls back to filesystem mtime if the file is untracked, returns None
    if the file does not exist (deleted docs must not appear fresh via git history).
    """
    fs_path = repo_root / rel_path
    if not fs_path.is_file():
        return None
    raw = _run_git("log", "-1", "--format=%aI", "--", rel_path, cwd=repo_root)
    if raw and len(raw) >= 10:
        return raw[:10]
    # Fallback: filesystem mtime (handles untracked / new files)
    mtime = datetime.fromtimestamp(fs_path.stat().st_mtime, tz=timezone.utc)
    return mtime.strftime("%Y-%m-%d")


def get_submodule_status(repo_root: Path) -> Dict[str, str]:
    """Return dict of submodule name -> current SHA."""
    raw = _run_git("submodule", "status", cwd=repo_root)
    if not raw:
        return {}
    result = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: " <sha> <path> (<describe>)" or "+<sha> <path> (<describe>)"
        parts = line.lstrip("+-").split()
        if len(parts) >= 2:
            sha, path = parts[0], parts[1]
            name = Path(path).name
            result[name] = sha[:8]
    return result


# ── Parsers ──────────────────────────────────────────────────────────

# Regex patterns for dashboard header metadata
_RE_LAST_UPDATED = re.compile(r"^\*\*Last Updated:\*\*\s*(.+)$", re.MULTILINE)
_RE_BRANCH = re.compile(r"^\*\*Branch:\*\*\s*`([^`]+)`", re.MULTILINE)
_RE_COMMIT = re.compile(r"^\*\*Commit:\*\*\s*`([^`]+)`", re.MULTILINE)


def parse_dashboard_metadata(path: Path) -> Optional[DashboardMeta]:
    """Extract Last Updated, Commit, Branch from dashboard header."""
    if not path.is_file():
        return None
    # Only need first 15 lines
    lines = path.read_text(encoding="utf-8").splitlines()[:15]
    header = "\n".join(lines)

    meta = DashboardMeta(file_path=str(path))
    m = _RE_LAST_UPDATED.search(header)
    if m:
        meta.last_updated = m.group(1).strip()
    m = _RE_BRANCH.search(header)
    if m:
        meta.branch = m.group(1).strip()
    m = _RE_COMMIT.search(header)
    if m:
        meta.commit = m.group(1).strip()
    return meta


# Regex for tracker table rows
_RE_TABLE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|",
    re.MULTILINE,
)


def parse_tracker_items(path: Path) -> List[TrackerItem]:
    """Parse P2 tracker markdown tables, extract issue rows."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    items = []
    current_section = "unknown"
    for line in text.splitlines():
        # Track section headers
        if line.startswith("### "):
            current_section = line.strip("# ").strip()
        m = _RE_TABLE_ROW.match(line)
        if m:
            items.append(
                TrackerItem(
                    number=m.group(1).strip(),
                    submodule=m.group(2).strip(),
                    issue=m.group(3).strip(),
                    severity=m.group(5).strip(),
                    status=m.group(6).strip(),
                    section=current_section,
                )
            )
    return items


# ── Freshness checks ────────────────────────────────────────────────


def check_freshness(
    meta: DashboardMeta,
    git: GitState,
    max_age_days: int,
    max_commits_behind: int,
) -> List[Finding]:
    """Check if dashboard metadata is stale."""
    findings = []

    # Check commit SHA drift
    if git.commits_since > max_commits_behind:
        findings.append(
            Finding(
                category="stale_commit",
                severity="P1",
                message=f"Dashboard commit `{meta.commit}` is {git.commits_since} commits behind HEAD",
                current=meta.commit,
                expected=git.short_sha,
            )
        )
    elif git.commits_since > 0 and meta.commit != git.short_sha:
        findings.append(
            Finding(
                category="stale_commit",
                severity="P2",
                message=f"Dashboard commit `{meta.commit}` is {git.commits_since} commits behind HEAD",
                current=meta.commit,
                expected=git.short_sha,
            )
        )

    # Check date staleness
    if meta.last_updated:
        # Extract date portion (YYYY-MM-DD) from the Last Updated field
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", meta.last_updated)
        if date_match:
            try:
                last_dt = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                now = datetime.now(timezone.utc)
                age_days = (now - last_dt).days
                if age_days > max_age_days:
                    findings.append(
                        Finding(
                            category="stale_date",
                            severity="P2",
                            message=f"Dashboard last updated {age_days} days ago (threshold: {max_age_days})",
                            current=date_match.group(1),
                            expected=git.utc_date,
                        )
                    )
            except ValueError:
                pass

    return findings


def load_living_docs_registry(registry_path: Path) -> List[TrackedDoc]:
    """Load registered docs from YAML. Empty list if file missing or invalid.

    PyYAML is preferred but optional — falls back to a tiny inline parser
    that handles the registry's flat-list-of-mappings shape.
    """
    if not registry_path.is_file():
        return []
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except ImportError:
        data = _parse_registry_yaml_minimal(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write(f"[docs_reconcile] registry parse error: {exc}\n")
        return []

    entries = data.get("tracked", []) if isinstance(data, dict) else []
    docs: List[TrackedDoc] = []
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        try:
            freshness_days = int(entry.get("freshness_days", 30))
        except (TypeError, ValueError):
            freshness_days = 30
        docs.append(
            TrackedDoc(
                path=str(entry["path"]),
                freshness_days=freshness_days,
                severity=str(entry.get("severity", "P2")).upper(),
                description=str(entry.get("description", "")),
            )
        )
    return docs


def _parse_registry_yaml_minimal(text: str) -> dict:
    """Tiny YAML subset parser for the registry's flat-list-of-mappings shape.

    Only handles `tracked:` followed by `- key: value` blocks. Anything else
    (anchors, nested mappings, multiline strings) is silently dropped.
    """
    tracked: List[dict] = []
    current: Optional[dict] = None
    in_tracked = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line == "tracked:" or line.startswith("tracked:"):
            in_tracked = True
            continue
        if not in_tracked:
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("- ") and indent <= 2:
            if current:
                tracked.append(current)
            current = {}
            stripped = stripped[2:]
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                current[k.strip()] = v.strip().strip('"').strip("'")
        elif current is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            current[k.strip()] = v.strip().strip('"').strip("'")
    if current:
        tracked.append(current)
    return {"tracked": tracked}


def check_registered_docs_freshness(
    repo_root: Path,
    docs: List[TrackedDoc],
) -> List[Finding]:
    """For each registered doc, compare last-commit date against freshness budget."""
    findings: List[Finding] = []
    now = datetime.now(timezone.utc)
    for doc in docs:
        last_date_str = get_file_last_commit_date(repo_root, doc.path)
        if not last_date_str:
            findings.append(
                Finding(
                    category="stale_doc",
                    severity="P2",
                    message=f"Tracked doc `{doc.path}` not found",
                    current="missing",
                    expected="present",
                )
            )
            continue
        try:
            last_dt = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age_days = (now - last_dt).days
        if age_days > doc.freshness_days:
            findings.append(
                Finding(
                    category="stale_doc",
                    severity=doc.severity,
                    message=f"`{doc.path}` last updated {age_days} days ago "
                    f"(budget: {doc.freshness_days}d, severity: {doc.severity})",
                    current=last_date_str,
                    expected=f"within {doc.freshness_days} days",
                )
            )
    return findings


def check_tracker_staleness(
    items: List[TrackerItem],
    submodule_shas: Dict[str, str],
) -> List[Finding]:
    """Flag OPEN tracker items whose submodule may have advanced."""
    findings = []
    open_items = [i for i in items if "OPEN" in i.status.upper()]
    for item in open_items:
        # Check if submodule name matches any known submodule
        sub_name = item.submodule.strip()
        # Try common name variants
        matched_sha = None
        for candidate in [
            f"PMOVES-{sub_name}",
            sub_name,
            f"PMOVES-{sub_name}.git",
        ]:
            if candidate in submodule_shas:
                matched_sha = submodule_shas[candidate]
                break
        if matched_sha:
            findings.append(
                Finding(
                    category="submodule_drift",
                    severity="INFO",
                    message=f"Tracker #{item.number} ({sub_name}): OPEN — submodule at {matched_sha}, verify if fix landed",
                    current=item.status,
                    expected="verify manually",
                )
            )
    return findings


# ── Reconciliation (write mode) ──────────────────────────────────────


def reconcile_dashboard(
    path: Path,
    git: GitState,
    dry_run: bool = False,
) -> Optional[str]:
    """Update Last Updated date and Commit SHA in dashboard header.

    Returns diff description or None if no changes needed.
    """
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8")
    original = text

    # Update Last Updated line — preserve parenthetical note
    today = git.utc_date
    text = re.sub(
        r"^(\*\*Last Updated:\*\*)\s*.+$",
        rf"\1 {today} (auto-reconciled)",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    # Update Commit line
    text = re.sub(
        r"^(\*\*Commit:\*\*)\s*`[^`]+`",
        rf"\1 `{git.short_sha}`",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    if text == original:
        return None

    changes = []
    for old_line, new_line in zip(original.splitlines(), text.splitlines()):
        if old_line != new_line:
            changes.append(f"  - {old_line}\n  + {new_line}")

    if not dry_run:
        path.write_text(text, encoding="utf-8")

    return "\n".join(changes) if changes else None


# ── Output formatting ────────────────────────────────────────────────


def print_report(report: ReconcileReport, json_mode: bool = False) -> None:
    """Print reconciliation report."""
    if json_mode:
        data = {
            "stale_count": report.stale_count,
            "p1_count": report.p1_count,
            "updated": report.updated,
            "dashboard": asdict(report.dashboard_meta) if report.dashboard_meta else None,
            "git": asdict(report.git_state) if report.git_state else None,
            "tracker_items_total": report.tracker_items_total,
            "tracker_items_open": report.tracker_items_open,
            "findings": [asdict(f) for f in report.findings],
        }
        print(json.dumps(data, indent=2))
        return

    # Human-readable output
    print("=" * 60)
    print("  Living Document Reconciliation Report")
    print("=" * 60)

    if report.git_state:
        g = report.git_state
        print(f"\n  Git HEAD:    {g.short_sha} ({g.branch})")
        print(f"  HEAD date:   {g.utc_date}")

    if report.dashboard_meta:
        m = report.dashboard_meta
        print(f"\n  Dashboard:")
        print(f"    Commit:      {m.commit}")
        print(f"    Updated:     {m.last_updated}")
        if report.git_state:
            print(f"    Drift:       {report.git_state.commits_since} commits behind HEAD")

    print(f"\n  Tracker: {report.tracker_items_open} open / {report.tracker_items_total} total")

    if report.findings:
        print(f"\n  Findings ({len(report.findings)}):")
        for f in report.findings:
            icon = {"P1": "!!", "P2": "! ", "INFO": "  "}
            prefix = icon.get(f.severity, "  ")
            print(f"    [{prefix}] [{f.severity}] {f.message}")
    else:
        print("\n  No staleness detected. Documents are fresh.")

    if report.updated:
        print("\n  Dashboard metadata updated.")

    print()


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile living document metadata (dashboard + P2 tracker)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read-only freshness check (CI-safe)")
    mode.add_argument("--update", action="store_true", help="Update stale dashboard metadata")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=3,
        help="Days before dashboard date is considered stale (default: 3)",
    )
    parser.add_argument(
        "--max-commits-behind",
        type=int,
        default=5,
        help="Commits behind HEAD before commit SHA is stale (default: 5)",
    )
    args = parser.parse_args()

    # Resolve paths relative to this script's parent (pmoves/)
    pmoves_root = Path(__file__).resolve().parent.parent
    repo_root = pmoves_root.parent
    dashboard_path = pmoves_root / DASHBOARD_REL
    tracker_path = pmoves_root / TRACKER_REL

    # Parse dashboard metadata
    dashboard_meta = parse_dashboard_metadata(dashboard_path)
    if not dashboard_meta:
        print(f"ERROR: Dashboard not found at {dashboard_path}", file=sys.stderr)
        return 2

    # Get git state
    git_state = get_git_state(repo_root, dashboard_meta.commit)

    # Parse tracker
    tracker_items = parse_tracker_items(tracker_path)
    open_items = [i for i in tracker_items if "OPEN" in i.status.upper()]

    # Get submodule status
    submodule_shas = get_submodule_status(repo_root)

    # Run checks
    findings: List[Finding] = []
    findings.extend(
        check_freshness(dashboard_meta, git_state, args.max_age_days, args.max_commits_behind)
    )
    findings.extend(check_tracker_staleness(tracker_items, submodule_shas))

    # Registry-based freshness check (CLAUDE.md fleet, AGENTS.md, AGNOTE family, etc.)
    registry_path = pmoves_root / REGISTRY_REL
    tracked_docs = load_living_docs_registry(registry_path)
    if tracked_docs:
        findings.extend(check_registered_docs_freshness(repo_root, tracked_docs))

    report = ReconcileReport(
        findings=findings,
        dashboard_meta=dashboard_meta,
        git_state=git_state,
        tracker_items_total=len(tracker_items),
        tracker_items_open=len(open_items),
    )

    # Update mode: write corrected metadata
    if args.update and any(f.category in ("stale_commit", "stale_date") for f in findings):
        diff = reconcile_dashboard(dashboard_path, git_state)
        if diff:
            report.updated = True
            if not args.json:
                print(f"Changes:\n{diff}\n")

    print_report(report, json_mode=args.json)

    # Exit code: 0 = fresh, 1 = stale
    if report.stale_count > 0 and not report.updated:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
