#!/usr/bin/env python3
"""
GEOMETRY BUS Health Checker

Checks which GEOMETRY BUS NATS subjects have active publishers/subscribers.
Reports on the health of the CHIT event-driven architecture.

Usage:
    python pmoves/tools/geometry_bus_health.py [--json] [--verbose]

Make target:
    make -C pmoves geometry-bus-status
"""

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional


NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@localhost:4222")

# All known GEOMETRY BUS subjects organized by domain
GEOMETRY_BUS_SUBJECTS: Dict[str, List[str]] = {
    "tokenism.attribution": [
        "tokenism.attribution.recorded.v1",
    ],
    "tokenism.cgp": [
        "tokenism.cgp.weekly.v1",
        "tokenism.cgp.ready.v1",
    ],
    "tokenism.geometry": [
        "tokenism.geometry.event.v1",
    ],
    "tokenism.swarm": [
        "tokenism.swarm.population.v1",
    ],
    "tokenism.credential": [
        "tokenism.credential.rotated.v1",
    ],
    "geometry.packet": [
        "geometry.packet.encoded.v1",
    ],
    "hf.model": [
        "hf.model.downloaded.v1",
    ],
    "research": [
        "research.deepresearch.request.v1",
        "research.deepresearch.result.v1",
    ],
    "supaserch": [
        "supaserch.request.v1",
        "supaserch.result.v1",
    ],
    "ingest": [
        "ingest.file.added.v1",
        "ingest.transcript.ready.v1",
        "ingest.summary.ready.v1",
        "ingest.chapters.ready.v1",
    ],
    "claude.code": [
        "claude.code.tool.executed.v1",
    ],
    "skills.pipeline": [
        "skills.pipeline.model-benchmark-viz.v1",
        "skills.pipeline.ingest-chit-index.v1",
        "skills.pipeline.research-render.v1",
        "skills.pipeline.chit-3d-viz.v1",
        "skills.pipeline.voice-synthesis.v1",
        "skills.pipeline.agent-card-gen.v1",
    ],
}


@dataclass
class SubjectHealth:
    """Health status for a single NATS subject."""

    subject: str
    domain: str
    has_stream: bool = False
    consumer_count: int = 0
    message_count: int = 0
    last_seq: int = 0
    status: str = "unknown"  # active, idle, no_stream, error


@dataclass
class BusHealth:
    """Overall GEOMETRY BUS health."""

    connected: bool = False
    server_id: Optional[str] = None
    jetstream_enabled: bool = False
    subjects: List[SubjectHealth] = field(default_factory=list)
    total_subjects: int = 0
    active_subjects: int = 0
    idle_subjects: int = 0
    missing_subjects: int = 0

    @property
    def health_pct(self) -> float:
        if self.total_subjects == 0:
            return 0.0
        return (self.active_subjects / self.total_subjects) * 100


async def check_bus_health(nats_url: str = "", verbose: bool = False) -> BusHealth:
    """Check GEOMETRY BUS health by querying NATS JetStream."""
    health = BusHealth()
    url = nats_url or NATS_URL

    all_subjects = []
    for domain, subjects in GEOMETRY_BUS_SUBJECTS.items():
        for subj in subjects:
            all_subjects.append((domain, subj))
    health.total_subjects = len(all_subjects)

    try:
        import nats
        from nats.js.api import StreamInfo

        nc = nats.NATS()
        await nc.connect(url)
        health.connected = True
        # Redact userinfo (user:pass@) from connected URL to avoid leaking credentials
        raw_url = nc.connected_url or ""
        health.server_id = re.sub(r"://[^@]+@", "://***@", raw_url) if raw_url else None

        # Check JetStream
        try:
            js = nc.jetstream()
            health.jetstream_enabled = True

            # List all streams
            streams: Dict[str, StreamInfo] = {}
            try:
                streams_list = await js.streams_info()
                for stream_info in streams_list:
                    for subj_pattern in stream_info.config.subjects:
                        streams[subj_pattern] = stream_info
            except Exception:
                pass

            # Check each subject
            for domain, subject in all_subjects:
                sh = SubjectHealth(subject=subject, domain=domain)

                # Check if any stream covers this subject
                for pattern, stream_info in streams.items():
                    if _subject_matches(subject, pattern):
                        sh.has_stream = True
                        sh.message_count = stream_info.state.messages
                        sh.last_seq = stream_info.state.last_seq
                        sh.consumer_count = stream_info.state.consumer_count

                        if sh.message_count > 0:
                            sh.status = "active"
                            health.active_subjects += 1
                        else:
                            sh.status = "idle"
                            health.idle_subjects += 1
                        break

                if not sh.has_stream:
                    sh.status = "no_stream"
                    health.missing_subjects += 1

                health.subjects.append(sh)

        except Exception as e:
            if verbose:
                print(f"JetStream not available: {e}", file=sys.stderr)

            # Fall back to basic subject check
            for domain, subject in all_subjects:
                sh = SubjectHealth(subject=subject, domain=domain, status="unknown")
                health.subjects.append(sh)

        await nc.close()

    except ImportError:
        print("nats-py not installed. Install with: uv pip install nats-py", file=sys.stderr)
        for domain, subject in all_subjects:
            sh = SubjectHealth(subject=subject, domain=domain, status="error")
            health.subjects.append(sh)

    except Exception as e:
        print(f"NATS connection failed: {e}", file=sys.stderr)
        for domain, subject in all_subjects:
            sh = SubjectHealth(subject=subject, domain=domain, status="error")
            health.subjects.append(sh)

    return health


def _subject_matches(subject: str, pattern: str) -> bool:
    """Check if a NATS subject matches a pattern (with wildcards)."""
    if pattern == subject:
        return True
    if pattern.endswith(".>"):
        prefix = pattern[:-2]
        return subject.startswith(prefix)
    if ".*" in pattern:
        parts_p = pattern.split(".")
        parts_s = subject.split(".")
        if len(parts_p) != len(parts_s):
            return False
        return all(
            pp == "*" or pp == ps for pp, ps in zip(parts_p, parts_s)
        )
    return False


def print_health(health: BusHealth, as_json: bool = False, verbose: bool = False) -> None:
    """Print the health report."""
    if as_json:
        output = {
            "connected": health.connected,
            "server_id": health.server_id,
            "jetstream_enabled": health.jetstream_enabled,
            "summary": {
                "total_subjects": health.total_subjects,
                "active": health.active_subjects,
                "idle": health.idle_subjects,
                "missing": health.missing_subjects,
                "health_pct": round(health.health_pct, 1),
            },
            "subjects": [
                {
                    "subject": s.subject,
                    "domain": s.domain,
                    "status": s.status,
                    "has_stream": s.has_stream,
                    "consumer_count": s.consumer_count,
                    "message_count": s.message_count,
                }
                for s in health.subjects
            ],
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 60)
    print("GEOMETRY BUS Health Report")
    print("=" * 60)
    print(f"Connected:    {'yes' if health.connected else 'NO'}")
    print(f"JetStream:    {'yes' if health.jetstream_enabled else 'NO'}")
    print(f"Server:       {health.server_id or 'N/A'}")
    print()
    print(f"Total subjects:  {health.total_subjects}")
    print(f"Active:          {health.active_subjects}")
    print(f"Idle:            {health.idle_subjects}")
    print(f"No stream:       {health.missing_subjects}")
    print(f"Health:          {health.health_pct:.1f}%")
    print("-" * 60)

    # Group by domain
    by_domain: Dict[str, List[SubjectHealth]] = {}
    for s in health.subjects:
        by_domain.setdefault(s.domain, []).append(s)

    for domain, subjects in sorted(by_domain.items()):
        print(f"\n  {domain}:")
        for s in subjects:
            icon = {
                "active": "+",
                "idle": "~",
                "no_stream": "-",
                "unknown": "?",
                "error": "!",
            }.get(s.status, "?")
            line = f"    [{icon}] {s.subject}"
            if verbose and s.has_stream:
                line += f"  (msgs={s.message_count}, consumers={s.consumer_count})"
            print(line)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GEOMETRY BUS Health Checker")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--nats-url", default=NATS_URL, help="NATS server URL"
    )

    args = parser.parse_args()

    health = asyncio.run(check_bus_health(nats_url=args.nats_url, verbose=args.verbose))
    print_health(health, as_json=args.json, verbose=args.verbose)

    return 0 if health.connected else 1


if __name__ == "__main__":
    sys.exit(main())
