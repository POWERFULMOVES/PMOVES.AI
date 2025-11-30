"""Generate per-service update notes from git metadata and version files.

This helper scans ``pmoves/services`` for directories that have a matching
documentation folder under ``pmoves/docs/services``. For each match we capture
the most recent commits that touched the service and any discovered version
metadata. Results are written to ``UPDATE_NOTES.md`` inside the service's
documentation directory.

Usage examples::

    python pmoves/scripts/update_service_logs.py --dry-run
    python pmoves/scripts/update_service_logs.py --limit 3
    python pmoves/scripts/update_service_logs.py --services agent-zero render-webhook

The script is idempotent and safe to run in CI. Combine with the repository
Makefile target ``make update-service-docs`` for convenience.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    tomllib = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_ROOT = REPO_ROOT / "pmoves" / "services"
DOCS_ROOT = REPO_ROOT / "pmoves" / "docs" / "services"


@dataclass
class Commit:
    sha: str
    date: str
    author: str
    summary: str

    @property
    def short_sha(self) -> str:
        return self.sha[:7]


@dataclass
class VersionMetadata:
    source: str
    value: str


def run_git_log(path: Path, limit: int) -> List[Commit]:
    """Return the most recent commits for ``path`` (relative to repo root)."""

    rel_path = path.relative_to(REPO_ROOT)
    fmt = "%H\x1f%ad\x1f%an\x1f%s"
    cmd = [
        "git",
        "log",
        f"-{limit}",
        "--date=iso",
        f"--pretty=format:{fmt}",
        str(rel_path),
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        benign_errors = (
            "fatal: your current branch",
            "fatal: ambiguous argument",
            "fatal: no such path",
            "fatal: not a git repository",
        )
        if any(msg in stderr for msg in benign_errors):
            return []
        raise RuntimeError(f"git log failed for {rel_path}: {stderr or result.returncode}")

    commits: List[Commit] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        sha, date, author, summary = line.split("\x1f", maxsplit=3)
        commits.append(Commit(sha=sha, date=date, author=author, summary=summary))
    return commits


def sanitize_summary(summary: str) -> str:
    return summary.replace("|", "\\|")


def load_version_files(service_path: Path) -> List[VersionMetadata]:
    """Attempt to read version metadata from well-known files."""

    metadata: List[VersionMetadata] = []
    candidates: List[Path] = []
    for candidate in ["VERSION", "version.txt", "VERSION.txt"]:
        path = service_path / candidate
        if path.is_file():
            candidates.append(path)

    for path in candidates:
        value = path.read_text(encoding="utf-8").strip()
        if value:
            metadata.append(VersionMetadata(source=path.name, value=value))

    package_json = service_path / "package.json"
    if package_json.is_file():
        try:
            pkg_data = json.loads(package_json.read_text(encoding="utf-8"))
            version = pkg_data.get("version")
            if isinstance(version, str) and version.strip():
                metadata.append(VersionMetadata(source="package.json", value=version.strip()))
        except json.JSONDecodeError:
            metadata.append(
                VersionMetadata(
                    source="package.json",
                    value="<invalid JSON>",
                )
            )

    pyproject = service_path / "pyproject.toml"
    if tomllib and pyproject.is_file():
        try:
            toml_data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, ValueError):  # type: ignore[attr-defined]
            metadata.append(
                VersionMetadata(
                    source="pyproject.toml",
                    value="<invalid TOML>",
                )
            )
        else:
            version = None
            if "project" in toml_data:
                version = toml_data["project"].get("version")
            if not version and "tool" in toml_data:
                tool_section = toml_data["tool"]
                poetry_cfg = tool_section.get("poetry") if isinstance(tool_section, dict) else None
                if isinstance(poetry_cfg, dict):
                    version = poetry_cfg.get("version")
            if isinstance(version, str) and version.strip():
                metadata.append(VersionMetadata(source="pyproject.toml", value=version.strip()))

    init_py = service_path / "__init__.py"
    if init_py.is_file():
        for line in init_py.read_text(encoding="utf-8").splitlines():
            if "__version__" in line:
                parts = line.split("=", maxsplit=1)
                if len(parts) == 2:
                    value = parts[1].strip().strip("\"'")
                    if value:
                        metadata.append(VersionMetadata(source="__init__.py", value=value))
                break

    return metadata


def render_markdown(
    service_name: str,
    commits: Iterable[Commit],
    versions: Iterable[VersionMetadata],
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = service_name.replace("_", " ")
    lines = [f"# {title} — Update Notes", "", f"_Last synced: {timestamp}_", ""]

    commits_list = list(commits)
    if commits_list:
        lines.extend(["## Recent Commits", "", "| Hash | Date | Author | Summary |", "| --- | --- | --- | --- |"])
        for commit in commits_list:
            lines.append(
                f"| `{commit.short_sha}` | {commit.date} | {commit.author} | {sanitize_summary(commit.summary)} |"
            )
        lines.append("")
    else:
        lines.extend(["## Recent Commits", "", "No commits found for this service.", ""])

    version_list = list(versions)
    lines.append("## Version Metadata")
    lines.append("")
    if version_list:
        for item in version_list:
            lines.append(f"- **{item.source}** → `{item.value}`")
    else:
        lines.append("- None discovered")

    lines.append("")
    lines.append(
        "> Generated by `pmoves/scripts/update_service_logs.py`. Do not edit manually; "
        "rerun the helper after landing new commits or version bumps."
    )
    lines.append("")
    return "\n".join(lines)


def collect_services(filter_names: Optional[List[str]] = None) -> List[Path]:
    if not SERVICES_ROOT.exists():
        raise FileNotFoundError(f"Services directory not found: {SERVICES_ROOT}")

    candidates = [path for path in SERVICES_ROOT.iterdir() if path.is_dir()]
    candidates.sort(key=lambda p: p.name.lower())

    if filter_names:
        filter_set = {name.strip() for name in filter_names}
        candidates = [path for path in candidates if path.name in filter_set]

    return candidates


def update_service(service_path: Path, limit: int, dry_run: bool) -> Optional[Path]:
    doc_dir = DOCS_ROOT / service_path.name
    if not doc_dir.exists():
        return None

    commits = run_git_log(service_path, limit)
    versions = load_version_files(service_path)
    markdown = render_markdown(service_path.name, commits, versions)

    update_path = doc_dir / "UPDATE_NOTES.md"
    if not dry_run:
        update_path.write_text(markdown, encoding="utf-8")
    return update_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update service documentation with recent git activity.")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of recent commits to include for each service (default: 5)",
    )
    parser.add_argument(
        "--services",
        nargs="*",
        help="Optional list of service directory names to update. Defaults to all services with docs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be updated without writing to disk.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    services = collect_services(args.services)
    if not services:
        print("No matching services found.")
        return

    updated: List[Path] = []
    skipped: List[str] = []

    for service_path in services:
        result = update_service(service_path, args.limit, args.dry_run)
        if result is None:
            skipped.append(service_path.name)
        else:
            updated.append(result)

    if updated:
        prefix = "Would update" if args.dry_run else "Updated"
        for path in updated:
            print(f"{prefix}: {path.relative_to(REPO_ROOT)}")

    if skipped:
        print(
            "Skipped (no matching docs): " + ", ".join(sorted(skipped))
        )


if __name__ == "__main__":
    main()
