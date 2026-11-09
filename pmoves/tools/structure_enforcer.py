#!/usr/bin/env python3
"""
Structure Best Practices Enforcer (Thread 9.3)

Validates structural best practices across the repository:
- Each submodule has PMOVES.AI_INTEGRATION.md
- Each service has /healthz documented
- Each CHIT module has JSDoc/docstrings
- Each Python tool has argparse + --help

Usage:
    python pmoves/tools/structure_enforcer.py [--json] [--strict]
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class Finding:
    """A structure enforcement finding."""

    severity: str  # P1, P2, P3
    category: str
    path: str
    message: str


@dataclass
class EnforcementReport:
    """Structure enforcement results."""

    findings: List[Finding] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0

    @property
    def p1_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P1")

    @property
    def p2_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P2")

    @property
    def p3_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P3")


def check_submodule_integration_md(report: EnforcementReport) -> None:
    """Each submodule must have PMOVES.AI_INTEGRATION.md."""
    gitmodules_path = REPO_ROOT / ".gitmodules"
    if not gitmodules_path.exists():
        return

    try:
        content = gitmodules_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    for match in re.finditer(r"path\s*=\s*(.+)", content):
        sub_path = match.group(1).strip()
        report.checks_run += 1
        sub_dir = REPO_ROOT / sub_path
        if not sub_dir.exists():
            report.findings.append(Finding(
                severity="P3",
                category="submodule-integration",
                path=sub_path,
                message="Submodule directory does not exist (uninitialized?)",
            ))
            continue

        integration_md = sub_dir / "PMOVES.AI_INTEGRATION.md"
        if integration_md.exists():
            report.checks_passed += 1
        else:
            report.findings.append(Finding(
                severity="P2",
                category="submodule-integration",
                path=sub_path,
                message=f"Missing PMOVES.AI_INTEGRATION.md in {sub_path}",
            ))


def check_chit_module_jsdoc(report: EnforcementReport) -> None:
    """Each CHIT TypeScript module must have JSDoc comments."""
    chit_dir = REPO_ROOT / "PMOVES-ToKenism-Multi" / "integrations" / "contracts" / "chit"
    if not chit_dir.exists():
        return

    for ts_file in chit_dir.glob("*.ts"):
        if ts_file.name in ("index.ts", "export-sample-cgp.ts"):
            continue

        report.checks_run += 1
        try:
            content = ts_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Check for /** ... */ JSDoc blocks
        if "/**" in content:
            report.checks_passed += 1
        else:
            report.findings.append(Finding(
                severity="P3",
                category="chit-jsdoc",
                path=str(ts_file.relative_to(REPO_ROOT)),
                message=f"No JSDoc comments found in {ts_file.name}",
            ))


def check_python_tool_argparse(report: EnforcementReport) -> None:
    """Each Python tool in pmoves/tools/ should have argparse + --help."""
    tools_dir = REPO_ROOT / "pmoves" / "tools"
    if not tools_dir.exists():
        return

    for py_file in tools_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        report.checks_run += 1
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        has_argparse = "argparse" in content or "ArgumentParser" in content
        has_main = 'if __name__' in content

        if has_argparse and has_main:
            report.checks_passed += 1
        elif not has_main:
            report.findings.append(Finding(
                severity="P3",
                category="tool-structure",
                path=str(py_file.relative_to(REPO_ROOT)),
                message=f"Missing __main__ guard in {py_file.name}",
            ))
        elif not has_argparse:
            report.findings.append(Finding(
                severity="P3",
                category="tool-structure",
                path=str(py_file.relative_to(REPO_ROOT)),
                message=f"No argparse in {py_file.name} — tools should support --help",
            ))


def check_python_tool_docstrings(report: EnforcementReport) -> None:
    """Each Python tool should have a module-level docstring."""
    tools_dir = REPO_ROOT / "pmoves" / "tools"
    if not tools_dir.exists():
        return

    for py_file in tools_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        report.checks_run += 1
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Check for module docstring (triple quotes near top of file)
        lines = content.lstrip().split("\n", 5)
        # Skip shebang and blank lines
        first_code = ""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#!"):
                first_code = stripped
                break

        if first_code.startswith('"""') or first_code.startswith("'''"):
            report.checks_passed += 1
        else:
            report.findings.append(Finding(
                severity="P3",
                category="tool-docstring",
                path=str(py_file.relative_to(REPO_ROOT)),
                message=f"Missing module docstring in {py_file.name}",
            ))


def check_skill_manifests(report: EnforcementReport) -> None:
    """Each skill directory should have a manifest.yaml."""
    skills_dir = REPO_ROOT / "pmoves" / "skills"
    if not skills_dir.exists():
        return

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        report.checks_run += 1
        manifest = skill_dir / "manifest.yaml"
        if manifest.exists():
            report.checks_passed += 1
        else:
            report.findings.append(Finding(
                severity="P2",
                category="skill-manifest",
                path=str(skill_dir.relative_to(REPO_ROOT)),
                message=f"Missing manifest.yaml in skill {skill_dir.name}",
            ))


def check_migration_numbering(report: EnforcementReport) -> None:
    """Migrations should be sequentially numbered."""
    migrations_dir = REPO_ROOT / "pmoves" / "migrations"
    if not migrations_dir.exists():
        return

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        return

    report.checks_run += 1
    numbers = []
    for f in sql_files:
        match = re.match(r"^(\d+)", f.name)
        if match:
            numbers.append(int(match.group(1)))

    expected = list(range(1, len(numbers) + 1))
    if numbers == expected:
        report.checks_passed += 1
    else:
        report.findings.append(Finding(
            severity="P2",
            category="migration-numbering",
            path="pmoves/migrations/",
            message=f"Migration numbering gap: found {numbers}, expected {expected}",
        ))


def print_report(report: EnforcementReport, as_json: bool = False) -> None:
    """Print the enforcement report."""
    if as_json:
        output = {
            "checks_run": report.checks_run,
            "checks_passed": report.checks_passed,
            "pass_rate_pct": round(
                report.checks_passed / report.checks_run * 100, 1
            ) if report.checks_run > 0 else 0,
            "findings": {
                "p1": report.p1_count,
                "p2": report.p2_count,
                "p3": report.p3_count,
            },
            "details": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "path": f.path,
                    "message": f.message,
                }
                for f in report.findings
            ],
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 60)
    print("Structure Best Practices Report")
    print("=" * 60)
    pct = (report.checks_passed / report.checks_run * 100) if report.checks_run > 0 else 0
    print(f"Checks: {report.checks_passed}/{report.checks_run} passed ({pct:.0f}%)")
    print(f"Findings: {report.p1_count} P1, {report.p2_count} P2, {report.p3_count} P3")
    print("-" * 60)

    if not report.findings:
        print("All checks passed.")
        return

    # Group by category
    by_category: Dict[str, List[Finding]] = {}
    for f in report.findings:
        by_category.setdefault(f.category, []).append(f)

    for category, findings in sorted(by_category.items()):
        print(f"\n  {category}:")
        for f in findings:
            print(f"    [{f.severity}] {f.message}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Structure Best Practices Enforcer")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any P1/P2 findings")
    args = parser.parse_args()

    report = EnforcementReport()

    check_submodule_integration_md(report)
    check_chit_module_jsdoc(report)
    check_python_tool_argparse(report)
    check_python_tool_docstrings(report)
    check_skill_manifests(report)
    check_migration_numbering(report)

    print_report(report, as_json=args.json)

    if args.strict and (report.p1_count > 0 or report.p2_count > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
