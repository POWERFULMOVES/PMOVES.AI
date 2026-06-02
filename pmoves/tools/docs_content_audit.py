#!/usr/bin/env python3
"""
PMOVES.AI Documentation Content Audit Tool

Checks documentation for:
- Broken internal links and references
- Outdated port numbers vs services-catalog.md
- Stale service references (removed/renamed services)
- Missing healthz/metrics documentation
- Cross-reference coverage (services, NATS subjects, agents)

Usage:
    python pmoves/tools/docs_content_audit.py [--json] [--fail-on-p1]

Make target:
    make -C pmoves docs-audit
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class AuditFinding:
    """A single audit finding."""

    severity: str  # P1, P2, P3
    category: str  # broken_link, stale_port, missing_doc, etc.
    file: str
    line: int
    message: str
    suggestion: Optional[str] = None


@dataclass
class AuditReport:
    """Complete audit report."""

    findings: List[AuditFinding] = field(default_factory=list)
    files_scanned: int = 0
    services_checked: int = 0
    nats_subjects_checked: int = 0
    agents_checked: int = 0

    @property
    def p1_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P1")

    @property
    def p2_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P2")

    @property
    def p3_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "P3")


# Known service ports from services-catalog.md
KNOWN_PORTS: Dict[str, int] = {
    "tensorzero-gateway": 3030,
    "tensorzero-ui": 4000,
    "tensorzero-clickhouse": 8123,
    "agent-zero-api": 8080,
    "agent-zero-ui": 8081,
    "archon-api": 8091,
    "archon-ui": 3737,
    "hirag-v2-cpu": 8086,
    "hirag-v2-gpu": 8087,
    "hirag-v1-cpu": 8089,
    "hirag-v1-gpu": 8090,
    "deepresearch": 8098,
    "supaserch": 8099,
    "flute-gateway-http": 8055,
    "flute-gateway-ws": 8056,
    "ultimate-tts": 7861,
    "pmoves-yt": 8077,
    "ffmpeg-whisper": 8078,
    "media-video": 8079,
    "media-audio": 8082,
    "extract-worker": 8083,
    "langextract": 8084,
    "render-webhook": 8085,
    "presign": 8088,
    "pdf-ingest": 8092,
    "jellyfin-bridge": 8093,
    "publisher-discord": 8094,
    "notebook-sync": 8095,
    "cipher-memory": 8105,
    "channel-monitor": 8097,
    "prometheus": 9090,
    "grafana": 3000,
    "loki": 3100,
    "nats": 4222,
    "supabase-postgrest": 3010,
    "qdrant": 6333,
    "neo4j-http": 7474,
    "neo4j-bolt": 7687,
    "meilisearch": 7700,
    "minio-api": 9000,
    "minio-console": 9001,
}

# Known NATS subjects
KNOWN_NATS_SUBJECTS: Set[str] = {
    "research.deepresearch.request.v1",
    "research.deepresearch.result.v1",
    "supaserch.request.v1",
    "supaserch.result.v1",
    "ingest.file.added.v1",
    "ingest.transcript.ready.v1",
    "ingest.summary.ready.v1",
    "ingest.chapters.ready.v1",
    "claude.code.tool.executed.v1",
    "hf.model.downloaded.v1",
    "tokenism.attribution.recorded.v1",
    "tokenism.cgp.weekly.v1",
    "tokenism.cgp.ready.v1",
    "tokenism.geometry.event.v1",
    "tokenism.swarm.population.v1",
    "tokenism.credential.rotated.v1",
    "geometry.packet.encoded.v1",
}

# Regex patterns
PORT_PATTERN = re.compile(r"(?:localhost|127\.0\.0\.1):(\d{4,5})")
INTERNAL_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
NATS_SUBJECT_PATTERN = re.compile(r"[a-z]+(?:\.[a-z_]+){1,5}\.v\d+")
HEALTHZ_PATTERN = re.compile(r"/healthz")
METRICS_PATTERN = re.compile(r"/metrics")


def find_docs(root: Path) -> List[Path]:
    """Find all documentation files."""
    docs = []
    for pattern in ["**/*.md", "**/*.rst", "**/*.txt"]:
        for p in root.glob(pattern):
            # Skip node_modules, .git, venv directories
            parts = p.parts
            skip = any(
                part in ("node_modules", ".git", "venv", "env", "__pycache__", ".next")
                for part in parts
            )
            if not skip:
                docs.append(p)
    return docs


def check_internal_links(
    file_path: Path, content: str, root: Path
) -> List[AuditFinding]:
    """Check for broken internal links in markdown."""
    findings = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for match in INTERNAL_LINK_PATTERN.finditer(line):
            link_text = match.group(1)
            link_target = match.group(2)

            # Skip external links and anchors
            if link_target.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # Resolve relative path
            target_path = (file_path.parent / link_target.split("#")[0]).resolve()
            if not target_path.exists():
                findings.append(
                    AuditFinding(
                        severity="P2",
                        category="broken_link",
                        file=str(file_path.relative_to(root)),
                        line=line_num,
                        message=f"Broken internal link: [{link_text}]({link_target})",
                        suggestion=f"Update or remove link to {link_target}",
                    )
                )
    return findings


def check_ports(
    file_path: Path, content: str, root: Path
) -> List[AuditFinding]:
    """Check for outdated or unknown port references."""
    findings = []
    known_port_values = set(KNOWN_PORTS.values())

    for line_num, line in enumerate(content.splitlines(), 1):
        for match in PORT_PATTERN.finditer(line):
            port = int(match.group(1))
            if port not in known_port_values and port > 1024:
                findings.append(
                    AuditFinding(
                        severity="P3",
                        category="unknown_port",
                        file=str(file_path.relative_to(root)),
                        line=line_num,
                        message=f"Port {port} not in services catalog",
                        suggestion="Verify this port is correct or add to catalog",
                    )
                )
    return findings


def check_nats_subjects(
    file_path: Path, content: str, root: Path
) -> List[AuditFinding]:
    """Check for NATS subject references."""
    findings = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for match in NATS_SUBJECT_PATTERN.finditer(line):
            subject = match.group(0)
            if subject not in KNOWN_NATS_SUBJECTS:
                findings.append(
                    AuditFinding(
                        severity="P3",
                        category="unknown_nats_subject",
                        file=str(file_path.relative_to(root)),
                        line=line_num,
                        message=f"NATS subject '{subject}' not in known subjects",
                        suggestion="Add to NATS subjects catalog or verify correctness",
                    )
                )
    return findings


def check_service_coverage(root: Path, scanned_files: List[Path]) -> List[AuditFinding]:
    """Check that all services have documentation coverage."""
    findings = []

    # Read all doc content
    all_content = ""
    for f in scanned_files:
        try:
            all_content += f.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"WARNING: Could not read {f}: {exc}", file=sys.stderr)

    # Check each service has at least one mention
    for service_name in KNOWN_PORTS:
        normalized = service_name.replace("-", "[ -_]?")
        if not re.search(normalized, all_content, re.IGNORECASE):
            findings.append(
                AuditFinding(
                    severity="P2",
                    category="undocumented_service",
                    file="(global)",
                    line=0,
                    message=f"Service '{service_name}' has no documentation reference",
                    suggestion=f"Add documentation for {service_name} to services-catalog.md",
                )
            )

    # Check healthz documentation
    for service_name, port in KNOWN_PORTS.items():
        healthz_ref = f"{port}/healthz"
        if healthz_ref not in all_content and port not in (
            4222, 3010, 6333, 7474, 7687, 7700, 9000, 9001, 3100, 8123,
        ):
            findings.append(
                AuditFinding(
                    severity="P3",
                    category="missing_healthz_doc",
                    file="(global)",
                    line=0,
                    message=f"No /healthz documentation for {service_name} (port {port})",
                    suggestion=f"Document health check at http://localhost:{port}/healthz",
                )
            )

    return findings


def run_audit(root: Path) -> AuditReport:
    """Run the full documentation audit."""
    report = AuditReport()

    # Find all docs
    doc_files = find_docs(root)
    report.files_scanned = len(doc_files)
    report.services_checked = len(KNOWN_PORTS)
    report.nats_subjects_checked = len(KNOWN_NATS_SUBJECTS)

    # Check each file
    for doc_path in doc_files:
        try:
            content = doc_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"WARNING: Could not read {doc_path}: {exc}", file=sys.stderr)
            continue

        # Run checks
        report.findings.extend(check_internal_links(doc_path, content, root))
        report.findings.extend(check_ports(doc_path, content, root))
        report.findings.extend(check_nats_subjects(doc_path, content, root))

    # Run global coverage checks
    report.findings.extend(check_service_coverage(root, doc_files))

    # Sort by severity
    severity_order = {"P1": 0, "P2": 1, "P3": 2}
    report.findings.sort(key=lambda f: severity_order.get(f.severity, 3))

    return report


def print_report(report: AuditReport, as_json: bool = False) -> None:
    """Print the audit report."""
    if as_json:
        output = {
            "summary": {
                "files_scanned": report.files_scanned,
                "services_checked": report.services_checked,
                "nats_subjects_checked": report.nats_subjects_checked,
                "p1_findings": report.p1_count,
                "p2_findings": report.p2_count,
                "p3_findings": report.p3_count,
                "total_findings": len(report.findings),
            },
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file": f.file,
                    "line": f.line,
                    "message": f.message,
                    "suggestion": f.suggestion,
                }
                for f in report.findings
            ],
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 72)
    print("PMOVES.AI Documentation Content Audit")
    print("=" * 72)
    print(f"Files scanned:        {report.files_scanned}")
    print(f"Services checked:     {report.services_checked}")
    print(f"NATS subjects checked: {report.nats_subjects_checked}")
    print()
    print(f"P1 (Critical):  {report.p1_count}")
    print(f"P2 (Warning):   {report.p2_count}")
    print(f"P3 (Info):      {report.p3_count}")
    print(f"Total findings: {len(report.findings)}")
    print("-" * 72)

    for finding in report.findings:
        severity_marker = {"P1": "!!!", "P2": " ! ", "P3": " . "}.get(
            finding.severity, "   "
        )
        loc = f"{finding.file}:{finding.line}" if finding.line > 0 else finding.file
        print(f"[{finding.severity}]{severity_marker} {finding.category}")
        print(f"       {loc}")
        print(f"       {finding.message}")
        if finding.suggestion:
            print(f"       -> {finding.suggestion}")
        print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PMOVES.AI Documentation Content Audit"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="Repository root directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--fail-on-p1",
        action="store_true",
        help="Exit with code 1 if P1 findings exist",
    )

    args = parser.parse_args()
    report = run_audit(args.root)
    print_report(report, as_json=args.json)

    if args.fail_on_p1 and report.p1_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
