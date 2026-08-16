#!/usr/bin/env python3
"""Assert the three Docker-cleanup implementations have not drifted apart.

There are three of them, and that is **deliberate** — do not "helpfully" collapse
them, because each is load-bearing for a different reason:

  pmoves/scripts/pmoves-disk-cleanup.sh
      Operator/host remediation. Removes ALL build cache (no age filter) and
      installs logrotate. Aggressive by design; run when a node is already sick.

  deploy/provision/docker-fleet-cleanup.sh
      A **deployed artifact**. `make docker-fleet-cleanup-install` copies it to
      /usr/local/bin/ and a systemd timer runs it daily (see
      docker-fleet-cleanup.service/.timer). On the node it executes on, this
      repository does not exist -- so it cannot source a shared library, and it
      cannot be replaced by a symlink into pmoves/scripts/.

  pmoves/mk/infra.mk :: docker-prune-all
      Make target. Deliberately narrower than the canonical script: `until=72h`
      filters and no logrotate side effect. Someone typing `make docker-prune-all`
      is asking to reclaim space, not to have their logging reconfigured.

So the real hazard was never the duplication -- it was **drift**. In 2026-08 the
make target was the only one of the three missing the buildx-builder reclaim, and
it leaked 40G/28G on the KVMs for weeks while `docker system df` reported
"Build Cache: 0B" (the cache lives inside each builder's *_state volume, which
`docker builder prune` does not touch). Two copies had the fix; one did not; and
nothing in the repository could tell.

This check closes that gap without breaking either constraint above: it asserts
every implementation still carries the reclaim invariants, and that none of them
has acquired the banned blanket volume prune.

Run:  python pmoves/tools/check_cleanup_parity.py
Exit: 0 = parity, 1 = drift
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Each implementation, with the reason it may not be merged into the others.
IMPLEMENTATIONS = {
    "pmoves/scripts/pmoves-disk-cleanup.sh": "operator/host remediation (all cache + logrotate)",
    "deploy/provision/docker-fleet-cleanup.sh": "deployed to /usr/local/bin via systemd timer; runs where this repo does not exist",
    "pmoves/mk/infra.mk": "make target docker-prune-all (until=72h, no logrotate)",
}

# Invariants every implementation must carry. Regexes, because the make target
# escapes `$` as `$$` and quoting differs between shell and make.
REQUIRED = {
    "buildx --all-inactive reclaim": re.compile(
        r"docker\s+buildx\s+rm\s+--all-inactive"
    ),
    "name-filtered buildkit state-volume sweep": re.compile(
        r"docker\s+volume\s+ls\s+-q\s+--filter\s+dangling=true\s+--filter\s+name=buildx_buildkit_"
    ),
}

# Patterns that must NEVER appear: they destroy co-hosted fleet data volumes.
# `docker volume rm <name>` is fine and is what the sweep above uses -- only the
# blanket forms are banned.
BANNED = {
    "blanket volume prune": re.compile(r"docker\s+volume\s+prune"),
    "system prune with volumes": re.compile(r"docker\s+system\s+prune[^\n]*--volumes"),
}

# Lines that only *mention* a banned pattern (comments, guard text, help strings)
# are not violations -- several of these files deliberately warn about it.
COMMENT = re.compile(r"^\s*(@?#|//)")


def read(rel: str) -> list[str]:
    path = REPO_ROOT / rel
    if not path.is_file():
        print(f"FAIL: missing implementation {rel}", file=sys.stderr)
        sys.exit(1)
    return io.open(path, encoding="utf-8").read().splitlines()


def executable(lines: list[str]) -> str:
    """Only the lines that actually run.

    Load-bearing: all three implementations *describe* the buildx reclaim in
    prose comments right above the command. Matching the whole file therefore
    finds the invariant even when the command itself has been deleted -- which
    is precisely the historical leak this check exists to catch. The first cut
    of this file made that mistake and passed its own falsification test.
    """
    return "\n".join(line for line in lines if not COMMENT.match(line))


def main() -> int:
    problems: list[str] = []

    for rel, why in IMPLEMENTATIONS.items():
        lines = read(rel)
        body = executable(lines)

        for name, pattern in REQUIRED.items():
            if not pattern.search(body):
                problems.append(
                    f"{rel}: missing '{name}'.\n"
                    f"    This implementation exists because: {why}\n"
                    f"    All three must carry the reclaim, or one of them leaks silently -- "
                    f"that is the 2026-08 KVM failure, reproduced."
                )

        for name, pattern in BANNED.items():
            for i, line in enumerate(lines, 1):
                if COMMENT.match(line):
                    continue
                if pattern.search(line):
                    problems.append(
                        f"{rel}:{i}: banned pattern '{name}' in an executable line.\n"
                        f"    {line.strip()}\n"
                        f"    Fleet data volumes are co-hosted. Use "
                        f"`make -C pmoves volume-reset SERVICE=<name>` for a targeted reset."
                    )

    if problems:
        print("FAIL: Docker-cleanup implementations have drifted.\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}\n", file=sys.stderr)
        print(
            "These three are intentionally separate (see this file's docstring for why\n"
            "each one cannot be merged into the others). Parity is enforced here instead.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {len(IMPLEMENTATIONS)} cleanup implementations at parity "
        f"({len(REQUIRED)} invariants each, {len(BANNED)} banned patterns absent)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
