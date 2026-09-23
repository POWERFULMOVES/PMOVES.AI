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
def _is_launcher_target(path: str) -> bool:
    """launcher domain: a PMOVES agent launcher or one of its shared fragments.

    WHY THESE ARE PROTECTED AT ALL. The shared env file is a zeroAccessPath --
    no operation, no road. The launchers READ it and export 410 variables into
    a process they then exec a harness inside. Measured 2026-09-16: the secret
    was sealed and every script that opens it was covered by nothing in
    patterns.yaml. Defense in depth says the reader of a secret inherits the
    secret's classification; here the reader was the one unguarded hop.

    They also decide WHO an agent is (node_identity) and whether cipher records
    its memories as itself (pm-cipher-identity), so an edit here is an identity
    and credential change wearing a shell script's clothes.

    readOnly, not zeroAccess: reading a launcher is how an agent learns the
    sanctioned bring-up, and sealing that would push people back to guessing.
    """
    norm = path.replace(chr(92), "/")
    tail = norm.rsplit("/", 1)[-1]
    if "/pmoves/scripts/pm-" in norm and tail.endswith(".sh"):
        return True
    return ("/pmoves/scripts/" in norm or "/deploy/provision/" in norm) and "-pmoves" in tail


DOMAIN_PATTERNS: Dict[str, Callable[[str], bool]] = {
    "compose": _is_compose_target,
    "schema": _is_schema_target,
    "topic": _is_topic_target,
    "dockerfile": _is_dockerfile_target,
    "migrations": _is_migrations_target,
    "launcher": _is_launcher_target,
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


# --- Actor attribution: which BODY took the road ----------------------------
#
# Before this, every row's `agent` was AGENT_ID or PMOVES_NODE_ID or "unknown",
# so a delivery-agent subagent, a code-review subagent and the steward that
# spawned them all recorded as the node (or as "unknown" where no env was set).
#
# Measured against claude 2.1.280 with a throwaway PreToolUse hook that dumped
# its stdin (scratch settings via `claude --print --settings`), 2026-09-23:
#   parent session, no --agent  -> no `agent_type`, no `agent_id`
#   subagent (Agent tool)       -> `agent_type: <frontmatter name>`,
#                                  `agent_id: <per-instance hex>`
#   main thread with --agent X  -> `agent_type: X`, no `agent_id`
# `session_id` is present in all three, while CLAUDE_SESSION_ID was unset in the
# hook env -- which is why every existing row reads `"session": "unknown"`.
#
# The hook callers hand their parsed stdin to set_hook_input(); _record() reads
# it back. ATTRIBUTION, NOT AUTHENTICATION: `agent_type` is the definition the
# harness loaded, not a credential. It is only recorded as a registered body when
# its kebab name maps onto an agent_registry.yaml key by the registry's own rule
# (validate_agent_registry.py: runtime spelling = key.replace("_", "-")). An
# unregistered type is still recorded, under `unregistered_agent_type`, so an
# anonymous subagent taking a road is visible rather than folded into the node.

_HOOK_INPUT: Dict[str, object] = {}
_REGISTRY_KEYS: "set[str] | None" = None


def set_hook_input(data: object) -> None:
    """Remember the hook's parsed stdin so trail rows can attribute the actor.

    Callers pass whatever json.load(sys.stdin) returned; anything that is not a
    dict is ignored. Never raises -- attribution must not be able to break a guard.
    """
    global _HOOK_INPUT
    _HOOK_INPUT = dict(data) if isinstance(data, dict) else {}


def _registry_path() -> Path:
    return _project_dir() / "pmoves" / "config" / "agent_registry.yaml"


def _registry_keys() -> "set[str]":
    """Keys under `agents:` in agent_registry.yaml. Empty set when unreadable.

    An unreadable registry means no body can be CERTIFIED as registered, so every
    agent_type falls through to `unregistered_agent_type` -- fail toward
    under-claiming, never toward naming a body we could not check.
    """
    global _REGISTRY_KEYS
    if _REGISTRY_KEYS is not None:
        return _REGISTRY_KEYS
    keys: "set[str]" = set()
    try:
        import yaml  # the guard callers already depend on PyYAML

        doc = yaml.safe_load(_registry_path().read_text(encoding="utf-8")) or {}
        agents = doc.get("agents") if isinstance(doc, dict) else None
        if isinstance(agents, dict):
            keys = {str(k) for k in agents}
    except Exception:  # noqa: BLE001 -- unreadable/unparseable -> certify nothing
        keys = set()
    _REGISTRY_KEYS = keys
    return keys


def _registered_body(agent_type: str) -> str:
    """The registered runtime name for a hook `agent_type`, or "" if unregistered.

    Exact match only -- no strip(), no case folding. The harness emits the
    frontmatter name verbatim, so anything that needs normalising to match was
    not produced by the harness and is not certified.
    """
    name = agent_type
    if not name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return ""
    return name if name.replace("-", "_") in _registry_keys() else ""


def _actor_fields() -> Dict[str, str]:
    """`agent` / `session` plus optional attribution fields for one trail row.

    `agent` keeps its old value (AGENT_ID, else PMOVES_NODE_ID, else "unknown")
    unless a REGISTERED body is acting, in which case the body takes `agent` and
    the old value moves to `node`, so node attribution is never lost.
    """
    node = os.environ.get("AGENT_ID") or os.environ.get("PMOVES_NODE_ID") or "unknown"
    raw_type = _HOOK_INPUT.get("agent_type")
    raw_type = raw_type if isinstance(raw_type, str) else ""
    hook_session = _HOOK_INPUT.get("session_id")
    fields: Dict[str, str] = {
        "agent": node,
        "session": (
            os.environ.get("CLAUDE_SESSION_ID")
            or os.environ.get("SESSION_ID")
            or (hook_session if isinstance(hook_session, str) and hook_session else "")
            or "unknown"
        ),
    }
    body = _registered_body(raw_type) if raw_type else ""
    if body:
        fields["agent"] = body
        fields["node"] = node
    elif raw_type:
        fields["unregistered_agent_type"] = raw_type[:128]
    instance = _HOOK_INPUT.get("agent_id")
    if isinstance(instance, str) and instance:
        fields["agent_instance"] = instance[:64]
    return fields


def _record(tool: str, file_path: str, domain: str, reason: str,
            note: str = "") -> bool:
    """Append one provable trail line. Returns False if it could not be written.

    `note` is free text describing HOW the use was observed. It is optional and
    omitted when empty, so existing rows and existing readers are unaffected --
    rows carrying a note already exist in the trail. The PostToolUse effect check
    uses it to distinguish a use it observed AFTER the fact (the command text
    never named the path) from a grant consulted BEFORE the write.

    Actor fields come from _actor_fields(); `node`, `agent_instance` and
    `unregistered_agent_type` are additive and omitted when they do not apply,
    so a row written outside any hook is byte-identical in shape to before.
    """
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "file": os.path.normpath(file_path).replace("\\", "/"),
        "domain": domain,
        "reason": reason,
    }
    try:
        # Inside the try: attribution runs on the grant path, and a PreToolUse
        # hook that crashes is non-blocking -- an escaped exception here would
        # turn this fail-closed bypass into fail-OPEN. Any failure to build or
        # write the row is "could not be recorded", so the caller denies.
        entry.update(_actor_fields())
        if note:
            entry["note"] = note
        path = _trail_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return True
    except Exception:  # noqa: BLE001 -- surfaced by the caller as a denial
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


def active_grant() -> Tuple[str, str, bool]:
    """(domain, reason, provable) for the grant currently in force.

    ("", "", False) when none is active.

    Public because the opaque-write tripwire in the Bash guard has to decide with
    NO TARGET PATH IN HAND: it fires on a verb that can write a path the command
    never spells, which is precisely why evaluate_known_road() -- whose whole
    contract is a per-file domain predicate -- has nothing to test against there.
    A caller using this is asserting less than one using evaluate_known_road: it
    learns that SOME grant is open, not that this grant covers this file. It must
    therefore never be used to allow an operation on a NAMED protected path; that
    decision stays with evaluate_known_road.
    """
    raw = _active_grant()
    if not raw or ":" not in raw:
        return "", "", False
    domain, reason = raw.split(":", 1)
    domain = domain.strip().lower()
    reason = reason.strip()
    if domain not in DOMAIN_PATTERNS:
        return domain, reason, False
    provable, _detail = _reason_is_provable(reason)
    return domain, reason, provable


def record_use(tool: str, file_path: str, domain: str, reason: str,
               note: str = "") -> bool:
    """Append one row to the trail. Public entry point for callers that have
    already made their own authorization decision (the opaque-write tripwire,
    the PostToolUse effect check). Returns False if it could not be written."""
    return _record(tool, file_path, domain, reason, note)


def evaluate_known_road(tool: str, file_path: str, normalized_fwd: str,
                        note: str = "") -> Tuple[bool, str]:
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

    if not _record(tool, file_path, domain, reason, note):
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
