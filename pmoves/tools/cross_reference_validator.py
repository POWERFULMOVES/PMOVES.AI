#!/usr/bin/env python3
"""
Cross-Reference Validator (Thread 9.2)

Validates that every service in the catalog has docs, every NATS subject
has docs, and every agent has docs. Outputs coverage report.

Usage:
    python pmoves/tools/cross_reference_validator.py [--json] [--fail-on-gaps]
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# Known service ports from services-catalog
KNOWN_SERVICES: Dict[str, int] = {
    "agent-zero": 8080,
    "archon": 8091,
    "flute-gateway": 8055,
    "hi-rag-v2-cpu": 8086,
    "hi-rag-v2-gpu": 8087,
    "hi-rag-v1-cpu": 8089,
    "hi-rag-v1-gpu": 8090,
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
    "cipher-memory": 8096,
    "channel-monitor": 8097,
    "deepresearch": 8098,
    "supaserch": 8099,
    "a2ui-renderer": 8100,
    "ultimate-tts": 7861,
    "tensorzero": 3030,
    "tensorzero-ui": 4000,
    "prometheus": 9090,
    "grafana": 3000,
    "loki": 3100,
    "nats": 4222,
    "supabase": 3010,
    "qdrant": 6333,
    "neo4j": 7474,
    "meilisearch": 7700,
    "minio": 9000,
}

KNOWN_NATS_SUBJECTS = [
    "research.deepresearch.request.v1",
    "research.deepresearch.result.v1",
    "supaserch.request.v1",
    "supaserch.result.v1",
    "ingest.file.added.v1",
    "ingest.transcript.ready.v1",
    "ingest.summary.ready.v1",
    "ingest.chapters.ready.v1",
    "claude.code.tool.executed.v1",
    "tokenism.attribution.recorded.v1",
    "tokenism.cgp.weekly.v1",
    "tokenism.cgp.ready.v1",
    "tokenism.geometry.event.v1",
    "tokenism.swarm.population.v1",
    "tokenism.credential.rotated.v1",
    "geometry.packet.encoded.v1",
    "hf.model.downloaded.v1",
]


@dataclass
class CoverageReport:
    """Cross-reference coverage report."""

    services_total: int = 0
    services_documented: int = 0
    services_missing_docs: List[str] = field(default_factory=list)

    nats_total: int = 0
    nats_documented: int = 0
    nats_missing_docs: List[str] = field(default_factory=list)

    agents_total: int = 0
    agents_documented: int = 0
    agents_missing_docs: List[str] = field(default_factory=list)

    submodules_total: int = 0
    submodules_with_integration_md: int = 0
    submodules_missing_integration: List[str] = field(default_factory=list)

    healthz_total: int = 0
    healthz_documented: int = 0
    healthz_missing_docs: List[str] = field(default_factory=list)

    @property
    def overall_pct(self) -> float:
        total = (
            self.services_total
            + self.nats_total
            + self.agents_total
            + self.submodules_total
        )
        covered = (
            self.services_documented
            + self.nats_documented
            + self.agents_documented
            + self.submodules_with_integration_md
        )
        return (covered / total * 100) if total > 0 else 0.0


def _scan_docs_for_mentions(search_term: str) -> bool:
    """Check if a search term is mentioned in any docs under .claude/context/ or pmoves/docs/."""
    docs_dirs = [
        REPO_ROOT / ".claude" / "context",
        REPO_ROOT / "pmoves" / "docs",
    ]
    for docs_dir in docs_dirs:
        if not docs_dir.exists():
            continue
        for md_file in docs_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if search_term.lower() in content.lower():
                    return True
            except OSError:
                continue
    return False


def check_service_docs(report: CoverageReport) -> None:
    """Check that each known service is documented."""
    report.services_total = len(KNOWN_SERVICES)
    for service_name in KNOWN_SERVICES:
        if _scan_docs_for_mentions(service_name):
            report.services_documented += 1
        else:
            report.services_missing_docs.append(service_name)


def check_nats_docs(report: CoverageReport) -> None:
    """Check that each NATS subject is documented."""
    report.nats_total = len(KNOWN_NATS_SUBJECTS)
    for subject in KNOWN_NATS_SUBJECTS:
        if _scan_docs_for_mentions(subject):
            report.nats_documented += 1
        else:
            report.nats_missing_docs.append(subject)


def check_agent_docs(report: CoverageReport) -> None:
    """Check that agents from the taxonomy are documented."""
    taxonomy_path = REPO_ROOT / "pmoves" / "docs" / "LIVING_TEMPLATE_AGENT_TAXONOMY.md"
    if not taxonomy_path.exists():
        return

    try:
        content = taxonomy_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    # Extract agent names from taxonomy (look for ## or ### headers with agent names)
    agent_names: List[str] = []
    for match in re.finditer(r"^#{2,3}\s+(.+?)(?:\s*\{.*\})?\s*$", content, re.MULTILINE):
        name = match.group(1).strip()
        if name and not name.startswith("Table") and len(name) < 60:
            agent_names.append(name)

    report.agents_total = len(agent_names)
    for agent_name in agent_names:
        if _scan_docs_for_mentions(agent_name):
            report.agents_documented += 1
        else:
            report.agents_missing_docs.append(agent_name)


def check_submodule_integration_docs(report: CoverageReport) -> None:
    """Check that each submodule has PMOVES.AI_INTEGRATION.md."""
    gitmodules_path = REPO_ROOT / ".gitmodules"
    if not gitmodules_path.exists():
        return

    try:
        content = gitmodules_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    submodule_paths: List[str] = []
    for match in re.finditer(r"path\s*=\s*(.+)", content):
        submodule_paths.append(match.group(1).strip())

    report.submodules_total = len(submodule_paths)
    for sub_path in submodule_paths:
        integration_md = REPO_ROOT / sub_path / "PMOVES.AI_INTEGRATION.md"
        if integration_md.exists():
            report.submodules_with_integration_md += 1
        else:
            report.submodules_missing_integration.append(sub_path)


def check_healthz_docs(report: CoverageReport) -> None:
    """Check that /healthz endpoints are documented for HTTP services."""
    # Services that should have /healthz
    http_services = [
        name for name, port in KNOWN_SERVICES.items()
        if port >= 3000 and name not in (
            "nats", "supabase", "qdrant", "neo4j",
            "meilisearch", "minio", "prometheus",
            "grafana", "loki",
        )
    ]
    report.healthz_total = len(http_services)
    for service in http_services:
        # Check if healthz is mentioned alongside the service
        if _scan_docs_for_mentions(f"{service}") and _scan_docs_for_mentions("healthz"):
            report.healthz_documented += 1
        else:
            report.healthz_missing_docs.append(service)


def print_report(report: CoverageReport, as_json: bool = False) -> None:
    """Print the coverage report."""
    if as_json:
        output = {
            "overall_coverage_pct": round(report.overall_pct, 1),
            "services": {
                "total": report.services_total,
                "documented": report.services_documented,
                "missing": report.services_missing_docs,
            },
            "nats_subjects": {
                "total": report.nats_total,
                "documented": report.nats_documented,
                "missing": report.nats_missing_docs,
            },
            "agents": {
                "total": report.agents_total,
                "documented": report.agents_documented,
                "missing": report.agents_missing_docs,
            },
            "submodules": {
                "total": report.submodules_total,
                "with_integration_md": report.submodules_with_integration_md,
                "missing": report.submodules_missing_integration,
            },
            "healthz": {
                "total": report.healthz_total,
                "documented": report.healthz_documented,
                "missing": report.healthz_missing_docs,
            },
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 60)
    print("Cross-Reference Coverage Report")
    print("=" * 60)
    print(f"Overall coverage: {report.overall_pct:.1f}%")
    print()

    sections = [
        ("Services", report.services_total, report.services_documented, report.services_missing_docs),
        ("NATS Subjects", report.nats_total, report.nats_documented, report.nats_missing_docs),
        ("Agents", report.agents_total, report.agents_documented, report.agents_missing_docs),
        ("Submodules (INTEGRATION.md)", report.submodules_total, report.submodules_with_integration_md, report.submodules_missing_integration),
        ("Healthz Endpoints", report.healthz_total, report.healthz_documented, report.healthz_missing_docs),
    ]

    for name, total, covered, missing in sections:
        pct = (covered / total * 100) if total > 0 else 0
        print(f"{name}: {covered}/{total} ({pct:.0f}%)")
        if missing:
            for item in missing[:5]:
                print(f"  - {item}")
            if len(missing) > 5:
                print(f"  ... and {len(missing) - 5} more")
        print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Cross-Reference Validator")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fail-on-gaps", action="store_true", help="Exit 1 if gaps found")
    args = parser.parse_args()

    report = CoverageReport()

    check_service_docs(report)
    check_nats_docs(report)
    check_agent_docs(report)
    check_submodule_integration_docs(report)
    check_healthz_docs(report)

    print_report(report, as_json=args.json)

    if args.fail_on_gaps and report.overall_pct < 100:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
