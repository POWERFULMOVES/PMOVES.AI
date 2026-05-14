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
    """compose domain: pmoves docker-compose*.yml only."""
    basename = os.path.basename(normalized_fwd).lower()
    if not (basename.startswith("docker-compose") and basename.endswith(".yml")):
        return False
    return "/pmoves/" in normalized_fwd or normalized_fwd.startswith("pmoves/")


# domain name -> predicate(normalized_forward_slash_path) -> bool
# Extend here to open a new readOnlyPath class to Known Roads.
DOMAIN_PATTERNS: Dict[str, Callable[[str], bool]] = {
    "compose": _is_compose_target,
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


def evaluate_known_road(tool: str, file_path: str, normalized_fwd: str) -> Tuple[bool, str]:
    """Evaluate the KNOWN_ROAD env var for this edit/write.

    Returns (allowed, detail):
      (True,  detail)  bypass granted — caller should allow the operation
      (False, "")      KNOWN_ROAD does not apply here — caller proceeds with normal checks
      (False, detail)  the file IS in the declared domain but the Known Road is invalid —
                       caller should block, surfacing `detail` as the reason
    """
    raw = os.environ.get("KNOWN_ROAD", "").strip()
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
