"""Known Roads — contextualized, provable bypass for damage-control readOnlyPaths.

A Known Road is an operator-authorized exception to a readOnlyPath block. Unlike a
blanket on/off flag, it must carry a *provable reason* tied to the specific change:

    KNOWN_ROAD=<domain>:<reason>

  <domain>  one of the keys in DOMAIN_PATTERNS — which readOnlyPath class is opened
  <reason>  why, in a form the hook can verify:
              handoff:<filename>  the brief at pmoves/docs/handoffs/<filename> must exist
              pr:<number>         references a tracked pull request
              issue:<number>      references a tracked issue

Every granted bypass is appended to known-roads.jsonl (append-only, git-tracked,
machine-parseable). A bypass that cannot be recorded is not provable, so it is denied.

The mechanism is domain-general: `compose` is the first domain, but the parse,
provability, and trail-logging logic is shared. Open a new readOnlyPath class by
adding a predicate to DOMAIN_PATTERNS — nothing else changes.

Canonical reference: .claude/PATTERNS.md § Known Roads — Protected-File Edits.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Callable, Dict, Tuple


def _is_compose_target(normalized_fwd: str) -> bool:
    """compose domain: any PMOVES-owned docker-compose*.yml.

    Covers the parent `pmoves/` tree AND submodule compose files
    (e.g. PMOVES-DoX/docker-compose.supabase.yml). The basename check
    already restricts to compose files; the path check scopes to the
    PMOVES.AI working tree by matching an actual PMOVES-owned path *segment*
    (`pmoves`, or any `pmoves-*` / `pmoves.*` submodule/root dir). Anchoring to
    segments rather than a bare substring avoids classifying an unrelated path
    that merely contains the bytes "pmoves" (e.g. `/tmp/evilpmoves/...`).
    The Known Road still requires a provable reason (pr:/issue:/handoff:),
    so this widens *which* compose files can be opened, not the bar to open them.
    """
    basename = os.path.basename(normalized_fwd).lower()
    if not (basename.startswith("docker-compose") and basename.endswith(".yml")):
        return False
    # Anchor to path segments — not a bare `"pmoves" in ...` substring. normalized_fwd
    # is already forward-slash normalized (os.path.normpath + backslash->slash).
    parts = normalized_fwd.lower().split("/")
    return any(
        p == "pmoves" or p.startswith("pmoves-") or p.startswith("pmoves.")
        for p in parts
    )


def _is_schema_target(normalized_fwd: str) -> bool:
    """schema domain: a PMOVES contract schema under pmoves/contracts/schemas/.

    Contract schemas are readOnly because a change ripples to every consumer;
    the guard comment on that path is "never modify without versioning". This
    domain opens ONLY *.schema.json files under a `contracts/schemas` segment in
    a PMOVES-owned tree, and — like compose — still requires a provable reason
    (pr:/issue:/handoff:). It widens *which* schema files can be opened under a
    recorded, versioned justification, not the bar to open them.
    """
    basename = os.path.basename(normalized_fwd).lower()
    if not basename.endswith(".schema.json"):
        return False
    parts = normalized_fwd.lower().split("/")
    if not any(
        p == "pmoves" or p.startswith("pmoves-") or p.startswith("pmoves.")
        for p in parts
    ):
        return False
    return "contracts" in parts and "schemas" in parts


def _is_topic_target(normalized_fwd: str) -> bool:
    """topic domain: the PMOVES NATS subject registry pmoves/contracts/topics.json.

    topics.json is readOnly because a change to the subject contract ripples to
    every publisher/subscriber and the shared `events.publish` topic validator.
    It is NOT a *.schema.json, so the schema domain does not cover it; this domain
    opens ONLY that one file under a `contracts` segment in a PMOVES-owned tree,
    and — like schema — still requires a provable reason (pr:/issue:/handoff:).
    """
    basename = os.path.basename(normalized_fwd).lower()
    if basename != "topics.json":
        return False
    parts = normalized_fwd.lower().split("/")
    if not any(
        p == "pmoves" or p.startswith("pmoves-") or p.startswith("pmoves.")
        for p in parts
    ):
        return False
    return "contracts" in parts


def _is_dockerfile_target(normalized_fwd: str) -> bool:
    """dockerfile domain: PMOVES service Dockerfiles (and .dockerignore).

    Covers files named Dockerfile / Dockerfile.* / .dockerignore anywhere in a
    PMOVES-owned tree — and ONLY those. Service source, configs, and other
    build-context files are deliberately NOT included: a dockerfile grant must
    not unlock arbitrary protected files that happen to live under services/.

    Service Dockerfiles are readOnly because they define the build contract
    between source and container; changes affect reproducibility and security
    (base image, dependencies, runtime user). This domain requires a provable
    reason (pr:/issue:/handoff:) and widens *which* Dockerfiles can be opened
    under a recorded, versioned justification, not the bar to open them.
    """
    parts = normalized_fwd.lower().split("/")
    if not any(
        p == "pmoves" or p.startswith("pmoves-") or p.startswith("pmoves.")
        for p in parts
    ):
        return False

    basename = os.path.basename(normalized_fwd).lower()
    return (
        basename == "dockerfile"
        or basename.startswith("dockerfile.")
        or basename == ".dockerignore"
    )


def _is_migrations_target(normalized_fwd: str) -> bool:
    """migrations domain: PMOVES Supabase migration/seed SQL under a
    `supabase/migrations` or `supabase/initdb` segment.

    Migration and seed SQL define the database schema-and-seed contract: a change
    ripples to every fresh `db reset` / `supabase-bootstrap` and to every node's DB,
    which is why they are readOnly. This domain opens ONLY *.sql files under a
    `supabase/migrations` or `supabase/initdb` segment in a PMOVES-owned tree, and —
    like the other domains — still requires a provable reason (pr:/issue:/handoff:).
    It widens *which* SQL files can be opened under a recorded, versioned
    justification, not the bar to open them. Non-SQL files and SQL elsewhere in the
    tree are deliberately excluded.
    """
    parts = normalized_fwd.lower().split("/")
    if not any(
        p == "pmoves" or p.startswith("pmoves-") or p.startswith("pmoves.")
        for p in parts
    ):
        return False

    basename = os.path.basename(normalized_fwd).lower()
    if not basename.endswith(".sql"):
        return False
    return "supabase" in parts and ("migrations" in parts or "initdb" in parts)


# domain name -> predicate(normalized_forward_slash_path) -> bool
# Extend here to open a new readOnlyPath class to Known Roads.
DOMAIN_PATTERNS: Dict[str, Callable[[str], bool]] = {
    "compose": _is_compose_target,
    "schema": _is_schema_target,
    "topic": _is_topic_target,
    "dockerfile": _is_dockerfile_target,
    "migrations": _is_migrations_target,
}

_REASON_RE = re.compile(r"^(handoff:[^/\\]+|pr:[0-9]+|issue:[0-9]+)$")


def known_road_domains() -> str:
    """Comma-joined sorted domain names — for help/error messages."""
    return ", ".join(sorted(DOMAIN_PATTERNS))


def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def _reason_is_provable(reason: str) -> Tuple[bool, str]:
    """A reason is provable when it is well-formed AND its referent can be checked."""
    if not _REASON_RE.match(reason):
        return False, (
            f"reason '{reason}' is not a recognized form "
            "(handoff:<filename> | pr:<number> | issue:<number>)"
        )
    if reason.startswith("handoff:"):
        name = reason.split(":", 1)[1]
        if ".." in name:
            return False, f"handoff reference '{name}' must be a bare filename"
        brief = _project_dir() / "pmoves" / "docs" / "handoffs" / name
        if not brief.is_file():
            return False, f"handoff brief not found: pmoves/docs/handoffs/{name}"
    return True, ""


def _trail_path() -> Path:
    return _project_dir() / ".claude" / "hooks" / "damage-control" / "known-roads.jsonl"


def _record(tool: str, file_path: str, domain: str, reason: str) -> bool:
    """Append one provable trail line. Returns False if it could not be written."""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "file": os.path.normpath(file_path).replace("\\", "/"),
        "domain": domain,
        "reason": reason,
        "agent": os.environ.get("AGENT_ID") or os.environ.get("PMOVES_NODE_ID") or "unknown",
        "session": os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("SESSION_ID") or "unknown",
    }
    try:
        path = _trail_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return True
    except OSError:
        return False


def _grant_file() -> Path:
    """Local, git-ignored file grant path — an operator-writable equivalent of the
    KNOWN_ROAD env var for clients that cannot inject env into hook subprocesses
    mid-session. One line: `<domain>:<reason>`."""
    return _project_dir() / ".claude" / "hooks" / "damage-control" / ".known-road-active"


def _active_grant() -> str:
    """The active Known Road grant: KNOWN_ROAD env var first, else the file grant.

    The env var is fixed in the launching process env and cannot be set mid-session
    in some clients, so a file grant (operator-written, e.g.
    `echo 'schema:handoff:x.md' > .claude/hooks/damage-control/.known-road-active`)
    is honored as an equivalent, operator-controlled authorization. The SAME rules
    apply downstream: the domain predicate must match AND the reason must be provable,
    and every granted use records to known-roads.jsonl."""
    env = os.environ.get("KNOWN_ROAD", "").strip()
    if env:
        return env
    try:
        gf = _grant_file()
        if gf.is_file():
            for line in gf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        pass
    return ""


def evaluate_known_road(tool: str, file_path: str, normalized_fwd: str) -> Tuple[bool, str]:
    """Evaluate the active Known Road grant (KNOWN_ROAD env var or file grant) for this edit/write.

    Returns (allowed, detail):
      (True,  detail)  bypass granted — caller should allow the operation
      (False, "")      no grant applies here — caller proceeds with normal checks
      (False, detail)  the file IS in the declared domain but the Known Road is invalid —
                       caller should block, surfacing `detail` as the reason
    """
    raw = _active_grant()
    if not raw or ":" not in raw:
        return False, ""

    domain, reason = raw.split(":", 1)
    domain = domain.strip().lower()
    reason = reason.strip()

    predicate = DOMAIN_PATTERNS.get(domain)
    if predicate is None or not predicate(normalized_fwd):
        # Unknown domain, or this file is not in the declared domain.
        # Not applicable — let the normal readOnlyPath rules decide.
        return False, ""

    # The file IS in the declared domain. From here a malformed or unprovable
    # reason is a hard block — the operator asked for a bypass on this exact file.
    provable, detail = _reason_is_provable(reason)
    if not provable:
        return False, f"Known Road reason not provable — {detail}"

    if not _record(tool, file_path, domain, reason):
        return False, (
            "Known Road bypass could not be recorded to known-roads.jsonl — "
            "an unprovable bypass is denied (fail-closed)"
        )

    return True, f"Known Road {domain}:{reason} (recorded to known-roads.jsonl)"


def known_road_hint(normalized_fwd: str) -> str:
    """If this file sits in a Known-Road domain, return a one-line hint naming the
    road. Empty string otherwise. Used to make block messages self-documenting."""
    for domain, predicate in DOMAIN_PATTERNS.items():
        if predicate(normalized_fwd):
            return (
                f" | Known Road available: set KNOWN_ROAD={domain}:<reason> "
                "(handoff:<filename> | pr:<n> | issue:<n>) — see .claude/PATTERNS.md "
                "§ Known Roads — Protected-File Edits"
            )
    return ""
