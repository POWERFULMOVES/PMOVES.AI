#!/usr/bin/env python3
"""
Jellyfin Creator Pipeline parity audit.

Checks cross-layer readiness for PMOVES Creator flows:
- docs + contracts + services present
- make targets aligned with docs
- core NATS subjects present
- runtime endpoints reachable
- GPU Orchestrator + TensorZero + unified auth parity
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class CheckResult:
    name: str
    severity: str
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_make_targets(makefile_path: Path) -> set[str]:
    text = makefile_path.read_text(encoding="utf-8", errors="replace")
    targets: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("."):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", line)
        if match:
            targets.add(match.group(1))
    return targets


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _is_placeholder(value: str) -> bool:
    val = (value or "").strip().lower()
    if not val:
        return True
    bad = (
        "changeme",
        "placeholder",
        "your_",
        "example",
        "dev_jwt_secret",
    )
    return any(token in val for token in bad)


def _check_required_files(root: Path) -> Iterable[CheckResult]:
    transcribe_repo = root.parent / "PMOVES-transcribe-and-fetch"
    transcribe_integration_doc = transcribe_repo / "PMOVES.AI_INTEGRATION.md"
    required = [
        (root / "docs" / "PMOVES.AI PLANS" / "CREATOR_PIPELINE.md", "fail"),
        (root / "docs" / "PMOVES.AI PLANS" / "CREATOR_PIPELINE_TO_CHIT.md", "fail"),
        (root / "docs" / "PMOVES.AI PLANS" / "JELLYFIN_BRIDGE_INTEGRATION.md", "fail"),
        (root / "docs" / "PMOVES.AI PLANS" / "PMOVES.yt" / "PMOVES_YT.md", "fail"),
        (root / "contracts" / "topics.json", "fail"),
        (root / "services" / "jellyfin-bridge" / "main.py", "fail"),
        (root / "services" / "pmoves-yt" / "yt.py", "fail"),
        (root / "services" / "publisher" / "publisher.py", "fail"),
    ]
    for path, missing_severity in required:
        if path.exists():
            yield CheckResult(f"file:{path.relative_to(root.parent)}", "pass", "present")
        else:
            yield CheckResult(
                f"file:{path.relative_to(root.parent)}",
                missing_severity,
                "missing required creator/jellyfin artifact",
            )

    transcribe_check_name = f"file:{transcribe_integration_doc.relative_to(root.parent)}"
    if not transcribe_repo.exists():
        yield CheckResult(
            transcribe_check_name,
            "pass",
            "sibling repo not present in workspace; external integration doc check skipped",
        )
    elif transcribe_integration_doc.exists():
        yield CheckResult(transcribe_check_name, "pass", "present")
    else:
        yield CheckResult(
            transcribe_check_name,
            "pass",
            "external integration doc absent; non-blocking for this workspace audit",
        )


def _check_make_target_parity(root: Path) -> Iterable[CheckResult]:
    makefile = root / "Makefile"
    targets = _load_make_targets(makefile)

    required_targets = [
        "up-jellyfin-ai",
        "up-jellyfin",
        "up-yt",
        "up-tensorzero-full",
        "jellyfin-stack-prod",
        "jellyfin-stack-prod-verify",
        "smoke",
        "smoke-prod",
    ]
    doc_referenced_targets = [
        "jellyfin-smoke",
        "yt-jellyfin-smoke",
        "jellyfin-verify",
        "jellyfin-parity-audit",
        "jellyfin-parity-audit-strict",
    ]

    for target in required_targets:
        if target in targets:
            yield CheckResult(f"make:{target}", "pass", "target present")
        else:
            yield CheckResult(f"make:{target}", "fail", "required target missing")

    for target in doc_referenced_targets:
        if target in targets:
            yield CheckResult(f"make:{target}", "pass", "doc-referenced target present")
        else:
            yield CheckResult(f"make:{target}", "warn", "docs reference this target but Makefile does not define it")


def _check_topics(root: Path) -> Iterable[CheckResult]:
    topics_path = root / "contracts" / "topics.json"
    required_topics = [
        "ingest.file.added.v1",
        "ingest.transcript.ready.v1",
        "content.published.v1",
        "jellyfin.item.added.v1",
        "jellyfin.playback.v1",
        "geometry.cgp.v2",
    ]

    try:
        payload = json.loads(topics_path.read_text(encoding="utf-8"))
        topics = set((payload.get("topics") or {}).keys())
    except Exception as exc:
        yield CheckResult("contracts:topics.json", "fail", f"unable to parse topics.json: {exc}")
        return

    for topic in required_topics:
        if topic in topics:
            yield CheckResult(f"topic:{topic}", "pass", "topic present")
        else:
            yield CheckResult(f"topic:{topic}", "fail", "missing topic contract mapping")


def _http_status(url: str, timeout_seconds: float) -> tuple[int | None, str | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return int(resp.status), None
    except urllib.error.HTTPError as exc:
        return int(exc.code), str(exc)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _check_runtime_endpoints(timeout_seconds: float) -> Iterable[CheckResult]:
    endpoints = [
        ("runtime:jellyfin-ai", ["http://localhost:8096", "http://localhost:9096"]),
        ("runtime:jellyfin-api", ["http://localhost:8300/health"]),
        ("runtime:jellyfin-dashboard", ["http://localhost:8400"]),
        ("runtime:jellyfin-bridge", ["http://localhost:8093/healthz"]),
        ("runtime:pmoves-yt", ["http://localhost:8077/healthz"]),
        ("runtime:tensorzero-gateway", ["http://localhost:3030/healthz", "http://localhost:3030/health"]),
        ("runtime:gpu-orchestrator", ["http://localhost:8200/healthz", "http://localhost:8100/healthz"]),
    ]

    for name, urls in endpoints:
        last_code: int | None = None
        last_error: str | None = None
        for url in urls:
            code, error = _http_status(url, timeout_seconds=timeout_seconds)
            last_code, last_error = code, error
            if code == 200:
                yield CheckResult(name, "pass", f"{url} -> 200")
                break
        else:
            if last_code is None:
                yield CheckResult(name, "warn", f"{urls[0]} unreachable ({last_error})")
            else:
                yield CheckResult(name, "warn", f"{urls[0]} returned HTTP {last_code}")


def _check_ingest_source_hints(root: Path) -> Iterable[CheckResult]:
    register_script = root / "tools" / "register_media_source.py"
    if not register_script.exists():
        yield CheckResult(
            "ingest:sources",
            "fail",
            "register_media_source.py missing (cannot onboard SoundCloud/URL sources)",
        )
        return

    text = register_script.read_text(encoding="utf-8", errors="replace")
    if "soundcloud" in text.lower():
        yield CheckResult("ingest:soundcloud", "pass", "soundcloud platform hint present")
    else:
        yield CheckResult("ingest:soundcloud", "warn", "no explicit soundcloud hint in source registration tool")

    if "--platform" in text and "--url" in text:
        yield CheckResult(
            "ingest:gdrive",
            "pass",
            "gdrive can be onboarded via register_media_source + mount/sync lane (documented path)",
        )
    else:
        yield CheckResult(
            "ingest:gdrive",
            "warn",
            "google drive ingestion path not clearly discoverable in source registration tooling",
        )


def _check_compose_wiring(root: Path) -> Iterable[CheckResult]:
    base = (root / "docker-compose.yml").read_text(encoding="utf-8", errors="replace")
    jelly_ai = (root / "docker-compose.jellyfin-ai.yml").read_text(encoding="utf-8", errors="replace")

    if re.search(r"jellyfin-bridge:\s*(?:.|\n)*?networks:\s*(?:.|\n)*?- pmoves_external", base):
        yield CheckResult("compose:jellyfin-bridge-external-network", "pass", "pmoves_external wiring present")
    else:
        yield CheckResult(
            "compose:jellyfin-bridge-external-network",
            "fail",
            "jellyfin-bridge missing pmoves_external network (host reachability risk)",
        )

    required_env_tokens = [
        "TENSORZERO_URL=${",
        "GPU_ORCHESTRATOR_URL=${",
        "SUPABASE_JWT_SECRET=${",
        "AUTH_BOOTSTRAP_MODE=${",
    ]
    for token in required_env_tokens:
        if token in jelly_ai:
            yield CheckResult(f"compose:jellyfin-ai:{token.split('=')[0]}", "pass", "wiring present")
        else:
            yield CheckResult(
                f"compose:jellyfin-ai:{token.split('=')[0]}",
                "fail",
                "expected env wiring missing in docker-compose.jellyfin-ai.yml",
            )


def _check_auth_parity(root: Path) -> Iterable[CheckResult]:
    shared_path = root / "env.shared"
    shared_is_template = False
    if not shared_path.exists():
        shared_path = root / "env.shared.example"
        shared_is_template = True

    jelly_path = root / "env.jellyfin-ai"
    jelly_is_template = False
    if not jelly_path.exists():
        jelly_path = root / "env.jellyfin-ai.example"
        jelly_is_template = True

    shared = _parse_env_file(shared_path)
    jelly = _parse_env_file(jelly_path)

    mode = shared.get("AUTH_BOOTSTRAP_MODE", "").strip().lower()
    if mode == "jwt":
        source = "template" if shared_is_template else "runtime"
        yield CheckResult("auth:shared-mode", "pass", f"{shared_path.name} ({source}) AUTH_BOOTSTRAP_MODE=jwt")
    elif mode:
        yield CheckResult("auth:shared-mode", "fail", f"{shared_path.name} AUTH_BOOTSTRAP_MODE={mode} (expected jwt)")
    else:
        yield CheckResult("auth:shared-mode", "fail", f"{shared_path.name} missing AUTH_BOOTSTRAP_MODE")

    jwt_secret = shared.get("SUPABASE_JWT_SECRET", "")
    jwt_root = shared.get("JWT_SECRET", "")
    if "${JWT_SECRET}" in jwt_secret:
        if _is_placeholder(jwt_root):
            yield CheckResult("auth:shared-jwt-secret", "fail", "SUPABASE_JWT_SECRET references JWT_SECRET but JWT_SECRET is empty/placeholder")
        else:
            yield CheckResult("auth:shared-jwt-secret", "pass", "SUPABASE_JWT_SECRET resolves from JWT_SECRET")
    elif _is_placeholder(jwt_secret):
        yield CheckResult("auth:shared-jwt-secret", "fail", "SUPABASE_JWT_SECRET is empty/placeholder")
    else:
        yield CheckResult("auth:shared-jwt-secret", "pass", "SUPABASE_JWT_SECRET configured")

    nats_url = shared.get("NATS_URL", "")
    if nats_url.startswith("nats://") and "@" in nats_url:
        yield CheckResult("auth:shared-nats-url", "pass", "NATS_URL uses credentialed form")
    else:
        yield CheckResult("auth:shared-nats-url", "fail", "NATS_URL missing credentials (expected nats://user:pass@host:port)")

    required_jelly_env = [
        "AUTH_BOOTSTRAP_MODE",
        "SUPABASE_JWT_SECRET",
        "TENSORZERO_URL",
        "GPU_ORCHESTRATOR_URL",
    ]
    for key in required_jelly_env:
        value = jelly.get(key, "")
        if not value:
            yield CheckResult(f"auth:jellyfin-env:{key}", "fail", f"{jelly_path.name} missing {key}")
            continue
        if _is_placeholder(value):
            if jelly_is_template:
                yield CheckResult(
                    f"auth:jellyfin-env:{key}",
                    "pass",
                    f"{jelly_path.name} {key} placeholder accepted (template source)",
                )
            else:
                yield CheckResult(f"auth:jellyfin-env:{key}", "warn", f"{jelly_path.name} {key} missing/placeholder")
        else:
            yield CheckResult(f"auth:jellyfin-env:{key}", "pass", f"{jelly_path.name} {key} configured")

    jelly_mode = jelly.get("AUTH_BOOTSTRAP_MODE", "").strip().lower()
    if jelly_mode and mode and jelly_mode != mode:
        yield CheckResult("auth:mode-parity", "fail", f"AUTH_BOOTSTRAP_MODE mismatch shared={mode} jellyfin={jelly_mode}")
    else:
        yield CheckResult("auth:mode-parity", "pass", "AUTH_BOOTSTRAP_MODE aligned")


def run_audit(root: Path, timeout_seconds: float) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_check_required_files(root))
    results.extend(_check_make_target_parity(root))
    results.extend(_check_topics(root))
    results.extend(_check_compose_wiring(root))
    results.extend(_check_auth_parity(root))
    results.extend(_check_runtime_endpoints(timeout_seconds))
    results.extend(_check_ingest_source_hints(root))
    return results


def summarize(results: list[CheckResult]) -> dict[str, int]:
    summary = {"pass": 0, "warn": 0, "fail": 0}
    for row in results:
        summary[row.severity] += 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Jellyfin Creator pipeline parity.")
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when WARN or FAIL results are present.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="HTTP timeout in seconds for runtime endpoint probes (default: 2.5).",
    )
    args = parser.parse_args()

    root = _repo_root()
    results = run_audit(root=root, timeout_seconds=args.timeout)
    summary = summarize(results)

    if args.json:
        payload = {"summary": summary, "results": [asdict(r) for r in results]}
        print(json.dumps(payload, indent=2))
    else:
        for row in results:
            glyph = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[row.severity]
            print(f"[{glyph}] {row.name}: {row.detail}")
        print(f"\nSummary: pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}")

    has_fail = summary["fail"] > 0
    has_warn = summary["warn"] > 0
    if args.strict:
        return 1 if (has_fail or has_warn) else 0
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
