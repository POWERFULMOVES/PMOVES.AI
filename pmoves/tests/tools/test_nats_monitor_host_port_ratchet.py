"""No new host-side NATS monitor URLs on port 8222 in docs or configs.

WHY THIS EXISTS
---------------
8222 is the NATS monitor port INSIDE the container. Base compose publishes it
on the host as ``${NATS_MONITORING_PORT:-9223}:8222``; only the Z890 leaf
(docker-compose.z890.yml) and scripts/start-cipher-stack.sh publish host 8222.
So on most nodes ``curl localhost:8222`` is refused while NATS is perfectly
healthy.

That trap has now been paid for twice. The 2026-08-31 4090 handoff fixed six
`.claude` skills that each carried their own copy of the literal, and
`.claude/scripts/nats-endpoint.sh` became the one place that asks Docker for
the real mapping. The prose and config layer underneath kept handing out the
literal, and on 2026-11-23 a delivery agent read one of those docs, probed
8222, got refused, and concluded mid-incident that it could not enumerate NATS
subscribers at all. A refused connection was read as a measurement.

This guard fails on any NEW loopback-8222 literal under pmoves/docs/ and
pmoves/configs/. Docs should derive the URL (`bash .claude/scripts/nats-endpoint.sh`)
or cite the per-node value from pmoves/configs/ports.yaml. See the
"NATS monitor port" section of pmoves/docs/NATS_CONFIGURATION.md.

Out of scope by design: archive/, handoffs/ and reviews/ are dated history,
and the claim register is an append-only ledger whose rows quote the trap.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# `(?!\d)` so a hypothetical :82220 is not a false hit.
HOST_8222 = re.compile(r"(?:localhost|127\.0\.0\.1):8222(?!\d)")

# Per-root floors: a broken pathspec or wrong REPO_ROOT scans nothing and
# passes. A union floor cannot detect ONE root silently going empty.
SCAN_ROOTS = {
    "pmoves/docs": 1000,
    "pmoves/configs": 100,
}

EXCLUDED_PREFIXES = (
    "pmoves/docs/archive/",
    "pmoves/docs/handoffs/",
    "pmoves/docs/reviews/",
)

# Whole files excluded, each with the reason.
EXCLUDED_FILES = {
    "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md": (
        "append-only claim register; CLAIM/UPDATE rows quote the trap as "
        "history and are written through make register-*, not edited"
    ),
}

# (path, needle) -> reason. The needle must occur on exactly ONE line of the
# file and that line must contain the 8222 literal; otherwise the entry is
# stale or over-broad and test_allowlist_entries_are_live fails.
ALLOWLIST = {
    (
        "pmoves/docs/NATS_CONFIGURATION.md",
        "The in-container healthcheck dials `wget http://localhost:8222/varz`",
    ): "quotes the compose healthcheck, which runs inside the container",
    (
        "pmoves/docs/operations/DHI_MIGRATION_MANIFEST.md",
        "`wget --spider http://localhost:8222/varz`",
    ): "compose healthcheck row; the command runs inside the container",
    (
        "pmoves/configs/pinokio-network-inventory.yaml",
        'health_endpoint: "http://localhost:8222/varz"',
    ): "pmoves-z890 block; the Z890 leaf publishes host 8222 (ports.yaml NATS_LEAF_8222_PORT)",
    (
        "pmoves/configs/tac_trees/node-z890-coordinator.tac.yaml",
        'url: "http://localhost:8222/varz"',
    ): "Z890 node tree; the Z890 leaf publishes host 8222 (docker-compose.z890.yml)",
    (
        "pmoves/configs/tac_trees/node-z890-coordinator.tac.yaml",
        'url: "http://localhost:8222/jsz"',
    ): "Z890 node tree; the Z890 leaf publishes host 8222 (docker-compose.z890.yml)",
    (
        "pmoves/docs/specs/mesh-live-collaboration-layer-plan-2026-08-08.md",
        "z890 could not reach `localhost:8222`",
    ): "dated plan quoting a 2026-08-08 observation; history, not instruction",
}


def _tracked(root: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", root],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [
        rel for rel in out.stdout.splitlines()
        if rel
        and not rel.startswith(EXCLUDED_PREFIXES)
        and rel not in EXCLUDED_FILES
    ]


def _lines(rel: str) -> list[str]:
    try:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()


def _allowed(rel: str, line: str) -> bool:
    return any(path == rel and needle in line for (path, needle) in ALLOWLIST)


def _offenders() -> list[str]:
    hits = []
    for root in SCAN_ROOTS:
        for rel in _tracked(root):
            for lineno, line in enumerate(_lines(rel), 1):
                if HOST_8222.search(line) and not _allowed(rel, line):
                    hits.append(f"{rel}:{lineno}: {line.strip()[:160]}")
    return hits


def test_each_scan_root_matches_files():
    """Control: a silently empty corpus makes the guard pass by scanning nothing.

    Production change that would make this fail: a typo'd root, a wrong
    REPO_ROOT, or an exclusion that swallows a whole tree.
    """
    for root, floor in SCAN_ROOTS.items():
        count = len(_tracked(root))
        assert count >= floor, f"{root!r} matched {count} files, expected >= {floor}"


def test_pattern_catches_the_shipped_trap():
    """Control: the regex must catch the exact forms that shipped, and must not
    flag the corrected forms.

    Production change that would make this fail: narrowing HOST_8222 so it no
    longer sees the literals this sweep removed.
    """
    shipped = [
        "curl http://localhost:8222/varz",
        "curl -s http://127.0.0.1:8222/connz",
        '        health_endpoint: "http://localhost:8222/varz"',
        '            os.getenv("SPARK_NATS_URL", "http://localhost:8222/healthz"),',
    ]
    for line in shipped:
        assert HOST_8222.search(line), line
    corrected = [
        'curl -s "$NATS_MONITOR_URL/varz"',
        '        health_endpoint: "http://localhost:9223/varz"',
        "      - ${NATS_MONITORING_BIND:-127.0.0.1}:${NATS_MONITORING_PORT:-9223}:8222",
        "http://localhost:82220/varz",
    ]
    for line in corrected:
        assert not HOST_8222.search(line), line


def test_no_new_host_side_8222_literals():
    """Production change that would make this fail: adding a loopback URL on
    8222 to any doc or config outside the allowlist. Derive it with
    `bash .claude/scripts/nats-endpoint.sh` or use the per-node port from
    pmoves/configs/ports.yaml instead; if the use is genuinely in-container or
    Z890-specific, add it to ALLOWLIST with a reason."""
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} host-side NATS monitor literal(s) on 8222. 8222 is the "
        "container-side port; on a default node the host port is 9223:\n  "
        + "\n  ".join(offenders[:25])
        + ("\n  ..." if len(offenders) > 25 else "")
    )


def test_allowlist_entries_are_live():
    """The allowlist must shrink, not rot. An entry whose needle no longer
    matches, or matches more than one line, would hide the next regression."""
    problems = []
    for (rel, needle), reason in ALLOWLIST.items():
        assert reason.strip(), f"{rel}: allowlist entry without a reason"
        matching = [line for line in _lines(rel) if needle in line]
        if len(matching) != 1:
            problems.append(f"{rel}: needle {needle!r} matched {len(matching)} lines")
        elif not HOST_8222.search(matching[0]):
            problems.append(f"{rel}: needle {needle!r} no longer carries the 8222 literal")
    assert not problems, "stale allowlist entries:\n  " + "\n  ".join(problems)


def test_excluded_files_exist():
    """A whole-file exclusion for a file that moved is a blind spot with no owner."""
    missing = [rel for rel in EXCLUDED_FILES if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"excluded files no longer exist: {missing}"
