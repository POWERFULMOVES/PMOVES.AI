#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["nats-py>=2.7"]
# ///
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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Make the repo root importable so canonical helpers under pmoves/ resolve regardless
# of cwd or PYTHONPATH. The Make target ran this from pmoves/ with neither set, so an
# import like the one below would have failed there — the script knows where it lives,
# so it should not depend on the caller getting this right.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pmoves.services.common.nats_client import _redact_url  # noqa: E402

# No credential-bearing default. The previous default embedded user:pass, which is the
# same class of leak this file's redactor exists to prevent — and it meant a bare run
# silently pointed at a guessed host with guessed creds.
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")

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
    "geometry.cgp": [
        # The subject beats_to_cgp.py actually publishes to, and the one
        # .claude/context/geometry-nats-subjects.md declares — it was missing here, so
        # this checker reported a healthy, populated stream as absent. Three sources
        # (producer, catalogue, this list) disagreed about which geometry subject
        # exists; wiring the first producer end-to-end is what surfaced it.
        "geometry.cgp.v1",
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
    # What actually went wrong, carried into the report. Without this the NOT MEASURED
    # block could only offer a list of GUESSES — and on the first real host run those
    # guesses were wrong: the failure was 'Authorization Violation' while the hints
    # said "use localhost:4222", which is exactly what had been used. A diagnostic
    # that speculates instead of reporting is the same defect this file documents.
    error: Optional[str] = None
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

    # nats-py surfaces server-side rejections (notably 'Authorization Violation') through
    # error_cb and keeps retrying; the asyncio.wait_for below then fires and the only
    # exception the caller sees is TimeoutError. Reported alone that reads as a NETWORK
    # problem and sends the operator to check the host and port — which on the first real
    # host run were both already correct. Capture what the server actually said.
    server_errors: List[str] = []

    async def _error_cb(exc: BaseException) -> None:
        server_errors.append(f"{type(exc).__name__}: {exc}")

    try:
        import nats
        from nats.js.api import StreamInfo

        nc = nats.NATS()
        # Bounded via asyncio.wait_for, and no reconnect retries. nats-py's own
        # connect_timeout does NOT bound DNS resolution: with an unresolvable host
        # (e.g. the fleet NATS_URL naming the container DNS "nats:4222" while this runs
        # on the host) it retried for a minute before raising. A health checker that
        # hangs is worse than one that fails — measured, not assumed.
        await asyncio.wait_for(
            nc.connect(
                url,
                connect_timeout=5,
                max_reconnect_attempts=0,
                error_cb=_error_cb,
            ),
            timeout=5,
        )
        health.connected = True
        # Redact userinfo via the CANONICAL helper, not a local regex.
        # pmoves.services.common.nats_client._redact_url parses with urlsplit/urlunsplit
        # (handles IPv6 bracketing) and FAILS CLOSED — any exception returns
        # "<redacted>". It is covered by test_redact_url_strips_userinfo.
        #
        # Two bugs lived on this line before, both from hand-rolling it:
        #   1. `re.sub(...)` was handed nc.connected_url, a urllib.parse.ParseResult,
        #      raising "expected string or bytes-like object". The generic handler
        #      caught it and reported "NATS connection failed", so this checker has
        #      reported a dead bus ever since the redaction was added — for a reason
        #      that had nothing to do with the bus.
        #   2. Casting with str() then made the pattern miss the repr, printing
        #      user:pass@host in the clear. A redactor that FAILS OPEN when confused is
        #      worse than none; the canonical one fails closed.
        raw_url = nc.connected_url.geturl() if nc.connected_url else ""
        health.server_id = _redact_url(raw_url) if raw_url else None

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

    except ImportError as e:
        health.error = f"nats-py not importable: {e}"
        print("nats-py not installed. Install with: uv pip install nats-py", file=sys.stderr)
        for domain, subject in all_subjects:
            sh = SubjectHealth(subject=subject, domain=domain, status="error")
            health.subjects.append(sh)

    except asyncio.TimeoutError:
        detail = f" — last server error: {server_errors[-1]}" if server_errors else ""
        health.error = f"timed out after 5s connecting to {_redact_url(url)}{detail}"
        print(f"NATS connection timed out: {_redact_url(url)}{detail}", file=sys.stderr)
        for domain, subject in all_subjects:
            sh = SubjectHealth(subject=subject, domain=domain, status="error")
            health.subjects.append(sh)

    except Exception as e:
        health.error = f"{type(e).__name__}: {e}"
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
            "error": health.error,
            "measured": health.connected,
            "jetstream_enabled": health.jetstream_enabled,
            "summary": {
                "total_subjects": health.total_subjects,
                "active": health.active_subjects,
                "idle": health.idle_subjects,
                "missing": health.missing_subjects,
                # null, NOT 0.0, when the bus was never contacted. The human-readable
                # branch already refused to print an unmeasured percentage; this one
                # still emitted `"health_pct": 0.0`, so any dashboard or alert consuming
                # the JSON kept receiving the exact false negative the text output had
                # been fixed to stop telling. Same defect, machine-readable half.
                "health_pct": round(health.health_pct, 1) if health.connected else None,
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

    # NOT MEASURED != MEASURED AND DEAD.
    # This previously rendered the full report — "Health: 0.0%", every subject [!] —
    # when it had failed to connect (or when nats-py was missing, which it silently
    # was). That is indistinguishable from a genuinely dead bus, and it is worse than
    # no output: it is a confident negative about something never inspected. Refuse to
    # print a health percentage we did not measure.
    if not health.connected:
        print("  *** NOT MEASURED — could not reach NATS ***")
        print(f"  {health.total_subjects} catalogued subjects were NOT checked.")
        print("  This is not a health reading. Do not read 0% as 'the bus is dead'.")
        print()
        # Report what happened before offering guesses about what might have.
        print(f"  Reason: {health.error or 'unknown'}")
        print()
        print("  Common causes:")
        print("    - 'Authorization Violation': the server requires credentials and")
        print("      NATS_URL has none. Supply them from the environment; this tool")
        print("      deliberately ships no credential-bearing default.")
        print("    - NATS_URL points at a container DNS name (nats:4222) but you are")
        print("      running on the host — use the published address (localhost:4222).")
        print("    - nats-py missing: run via `uv run` so the inline deps resolve.")
        print("=" * 60)
        return

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
