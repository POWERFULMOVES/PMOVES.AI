"""Known Roads — contextualized, provable bypass for damage-control readOnlyPaths.

A Known Road is an operator-authorized exception to a readOnlyPath block. Unlike a
blanket on/off flag, it must carry a *provable reason* tied to the specific change:

    KNOWN_ROAD=<domain>:<reason>

  <domain>  one of the keys in DOMAIN_PATTERNS — which readOnlyPath class is opened
  <reason>  why, in a form the hook can verify:
              handoff:<filename>  the brief at pmoves/docs/handoffs/<filename> must
                                  exist AND be tracked by git
              pr:<number>         a pull request that is still OPEN
              issue:<number>      an issue that is still OPEN
            optionally suffixed `!offline` (pr:/issue: only) — see OFFLINE_SUFFIX

Every granted bypass is appended to known-roads.jsonl (append-only, git-tracked,
machine-parseable). A bypass that cannot be recorded is not provable, so it is denied.

A grant EXPIRES. Well-formed is not enough: a `pr:`/`issue:` grant is honoured only
while that PR/issue is OPEN on the canonical repo, and a file grant only while the
file is younger than GRANT_MAX_AGE_SECONDS. See "Grant liveness" below.

The mechanism is domain-general: `compose` is the first domain, but the parse,
provability, and trail-logging logic is shared. Open a new readOnlyPath class by
adding a predicate to DOMAIN_PATTERNS — nothing else changes.

Canonical reference: .claude/PATTERNS.md § Known Roads — Protected-File Edits.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple


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
        rel = f"pmoves/docs/handoffs/{name}"
        brief = _project_dir() / rel
        if not brief.is_file():
            return False, f"handoff brief not found: {rel}"
        # Existence alone let a brief written seconds ago, by the same session
        # that wants the road, serve as its own authority. A referent has to be
        # something a reviewer can see, so it must be in git (the index is
        # enough: an operator can `git add` a fresh brief without committing).
        if brief.is_symlink():
            return False, f"handoff brief is a symlink, not a brief: {rel}"
        tracked, why = _git_tracks(rel)
        if not tracked:
            return False, f"handoff brief is not tracked by git ({why}): {rel}"
    return True, ""


def _git_tracks(rel: str) -> Tuple[bool, str]:
    """(tracked, detail) for a repo-relative path. Fails closed on any error."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(_project_dir()), "ls-files", "--error-unmatch", "--", rel],
            capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"git could not be run: {exc.__class__.__name__}"
    if proc.returncode != 0:
        return False, "untracked"
    return True, ""


# --- Grant liveness: a grant expires with the job it was issued for ----------
#
# MEASURED DEFECT (2026-09-23). A reason was "provable" by regex alone, so a grant
# never expired. `compose:pr:3101` stayed in .known-road-active after PR #3101
# merged on 2026-09-20 and silently authorised compose edits made for PR #3143
# three days later -- rows that name the wrong PR, which is the one thing the
# trail exists to get right. The earlier pr:2656 rows (see trail_states.py) are
# the same shape. The operator's direction: nothing expired the grant when its PR
# merged; make it.
#
# Three bounds, each closing a different way a grant outlives its job:
#
#   1. REFERENT STATE. `pr:N` / `issue:N` is honoured only while N is OPEN on
#      CANONICAL_REPO. Merged or closed -> VOID. Cannot be checked -> REFUSED
#      ("grant not verifiable"), because a guard that allows when it cannot look
#      is a guard that allows whenever the network is down.
#   2. AGE. A FILE grant older than GRANT_MAX_AGE_SECONDS is void whatever the PR
#      state: a long-lived PR must not turn a one-job grant into an ambient one.
#      A file mtime in the future is void too, or `touch -d 2099` would be a
#      permanent grant.
#   3. The env grant (KNOWN_ROAD) has no mtime. It is read from the hook's own
#      environment, which the harness fixes at launch, so it lives exactly as long
#      as the session that was launched with it -- UNLESS it is placed in a
#      settings file's `env`, in which case it rides every session and only
#      bound 1 limits it. PATTERNS.md says never to do that; this is why.
#
# OFFLINE. `!offline` appended to a pr:/issue: grant skips bound 1 only (never
# bound 2), and the trail row says `grant_state: offline-override`. A per-GRANT
# suffix, not a KNOWN_ROAD_OFFLINE=1 env switch: an env switch is an ambient
# flag that would exempt every grant for the life of the session, which is the
# on/off shape Known Roads was built to replace; the suffix is written by the
# same operator act that opens the grant, is visible in it, and dies with it.

CANONICAL_REPO = "POWERFULMOVES/PMOVES.AI"
GRANT_MAX_AGE_SECONDS = 24 * 3600
GRANT_FUTURE_SKEW_SECONDS = 300
# 120s: long enough that a burst of edits in one job (11 edits to one compose file
# is the largest burst in the trail) costs ONE API call instead of one per edit;
# short enough that a merge takes effect within two minutes, against the three
# days the stale pr:3101 grant ran. Only a SUCCESSFUL lookup is cached; failures
# are retried on the next call, so fixing the network needs no cache flush.
STATE_CACHE_TTL_SECONDS = 120
# 8s, measured: `gh api` for one PR on B850 took 0.82-4.46s over six runs
# (gh itself starts in 0.02s; the spread is the API round trip). A 5s timeout
# refused real calls in that tail. The hook's own timeout is 15s
# (.claude/settings.json), and _MEMO below caps a hook process at ONE lookup per
# referent, so 8s + interpreter start-up stays inside it. If the harness killed
# the hook instead, a PreToolUse error is non-blocking -- the guard would fail
# OPEN -- which is why this must stay well under the hook timeout.
GH_TIMEOUT_SECONDS = 8
OFFLINE_SUFFIX = "!offline"


class GrantUnverifiable(Exception):
    """The referent's state could not be established. Always a refusal."""


# Per-PROCESS memo of every outcome, failures included. A hook process lives for
# one tool call, so this cannot make an answer outlive the call; what it prevents
# is the effect check (one process, N changed paths) paying N timeouts during a
# GitHub stall and being killed by the harness before it can report.
_MEMO: Dict[str, object] = {}


def _cache_path() -> Path:
    """Git-ignored, and readOnly in patterns.yaml: a forged `open` entry would
    revive a merged PR's grant, so agents may not write it any more than they
    may write .known-road-active. Only this module writes it (not a tool call)."""
    return _project_dir() / ".claude" / "hooks" / "damage-control" / ".grant-state-cache.json"


def _gh_api_raw(api_path: str) -> str:
    """stdout of `gh api <api_path>`. Raises GrantUnverifiable on any failure.

    The single network seam: tests replace THIS, never the parsing below it, so a
    malformed-response test exercises the real parser.
    """
    gh = shutil.which("gh")
    if not gh:
        raise GrantUnverifiable("gh CLI not found on PATH")
    env = dict(os.environ, GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1",
               NO_COLOR="1")
    try:
        proc = subprocess.run(
            [gh, "api", api_path], capture_output=True, text=True,
            timeout=GH_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL, env=env,
        )
    except subprocess.TimeoutExpired:
        raise GrantUnverifiable(f"gh api timed out after {GH_TIMEOUT_SECONDS}s")
    except OSError as exc:
        raise GrantUnverifiable(f"gh could not be run: {exc}")
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        first = lines[0][:200] if lines else "no output"
        raise GrantUnverifiable(f"gh api {api_path} exited {proc.returncode}: {first}")
    return proc.stdout


def _parse_state(kind: str, number: int, raw: str) -> Dict[str, str]:
    """{"state": open|closed|merged, "at": iso-or-""} from a GitHub API body.

    Anything that is not exactly the documented shape is GrantUnverifiable: a
    parser that guesses turns a changed API, an HTML error page, or a proxy's
    login screen into a verdict.
    """
    try:
        doc = json.loads(raw)
    except ValueError:
        raise GrantUnverifiable("malformed API response: not JSON")
    if not isinstance(doc, dict):
        raise GrantUnverifiable("malformed API response: not a JSON object")
    if doc.get("number") != number:
        raise GrantUnverifiable(
            f"malformed API response: asked for #{number}, got number={doc.get('number')!r}")
    state = doc.get("state")
    if state not in ("open", "closed"):
        raise GrantUnverifiable(f"malformed API response: state={state!r}")
    if kind == "pr":
        merged = doc.get("merged")
        if not isinstance(merged, bool):
            raise GrantUnverifiable(f"malformed API response: merged={merged!r}")
        if merged and state == "open":
            raise GrantUnverifiable("malformed API response: open AND merged")
        label = "merged" if merged else state
        when = doc.get("merged_at") if merged else doc.get("closed_at")
    else:
        label = state
        when = doc.get("closed_at")
    return {"state": label, "at": when if isinstance(when, str) else ""}


def _cache_key(kind: str, number: int) -> str:
    return f"{CANONICAL_REPO}#{kind}:{number}"


def _cache_load() -> Dict[str, object]:
    try:
        doc = json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _cache_get(key: str, now: float) -> Optional[Dict[str, str]]:
    """A fresh, well-formed cache entry, else None (-> ask the API)."""
    entry = _cache_load().get(key)
    if not isinstance(entry, dict):
        return None
    checked = entry.get("checked")
    if isinstance(checked, bool) or not isinstance(checked, (int, float)):
        return None
    # A future-dated entry is not fresh, it is wrong: refuse to extend its life.
    if not 0 <= now - checked <= STATE_CACHE_TTL_SECONDS:
        return None
    state = entry.get("state")
    if state not in ("open", "closed", "merged"):
        return None
    at = entry.get("at")
    return {"state": state, "at": at if isinstance(at, str) else ""}


def _cache_put(key: str, result: Dict[str, str], now: float) -> None:
    """Best effort. A cache that cannot be written costs one API call per use; it
    can never change a verdict, which is why failing here is not reported."""
    try:
        doc = {k: v for k, v in _cache_load().items()
               if isinstance(v, dict) and isinstance(v.get("checked"), (int, float))
               and 0 <= now - v["checked"] <= STATE_CACHE_TTL_SECONDS}
        doc[key] = {"state": result["state"], "at": result.get("at", ""),
                    "checked": now}
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".grant-state-cache.",
                                   suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, sort_keys=True)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except Exception:  # noqa: BLE001 -- see docstring: latency only, never a verdict
        pass


def _referent_state(kind: str, number: int) -> Dict[str, str]:
    """State of pr/issue `number` on CANONICAL_REPO, via the cache or the API.

    CANONICAL_REPO, not `git remote get-url origin`: a grant's number means the
    canonical tracker's number, and a clone whose origin is a fork would resolve
    it against the wrong repository. It also saves a git subprocess per check.
    """
    now = time.time()
    key = _cache_key(kind, number)
    memo = _MEMO.get(key)
    if isinstance(memo, GrantUnverifiable):
        raise memo
    if isinstance(memo, dict):
        return dict(memo)
    hit = _cache_get(key, now)
    if hit is not None:
        hit["cached"] = "yes"
        _MEMO[key] = dict(hit)
        return hit
    endpoint = "pulls" if kind == "pr" else "issues"
    try:
        result = _parse_state(kind, number,
                              _gh_api_raw(f"repos/{CANONICAL_REPO}/{endpoint}/{number}"))
    except GrantUnverifiable as exc:
        _MEMO[key] = exc
        raise
    _MEMO[key] = dict(result)
    _cache_put(key, result, now)
    return result


def _split_offline(reason: str) -> Tuple[str, bool]:
    if reason.endswith(OFFLINE_SUFFIX):
        return reason[: -len(OFFLINE_SUFFIX)].strip(), True
    return reason, False


def _check_grant(raw_reason: str, source: str,
                 mtime: Optional[float]) -> Tuple[bool, str, str, str]:
    """Full verdict on a grant's reason. Returns (ok, reason, detail, grant_state).

    `reason` is returned with any `!offline` suffix removed, so trail rows keep
    grouping by the bare reason. `grant_state` is one of:
      open | offline-override | handoff-present     (ok)
      merged | closed | unverifiable | stale | unprovable   (refused)
    """
    reason, offline = _split_offline(raw_reason)
    # Form before referent: a malformed grant is refused for its form, before
    # anything (a file, git, the network) is consulted about its referent.
    if offline and reason.startswith("handoff:"):
        return False, reason, (
            f"'{OFFLINE_SUFFIX}' applies only to pr:/issue: reasons -- a handoff "
            "is checked locally and never needs the network"), "unprovable"
    provable, detail = _reason_is_provable(reason)
    if not provable:
        return False, reason, detail, "unprovable"

    if source == "file" and mtime is not None:
        age = time.time() - mtime
        if age > GRANT_MAX_AGE_SECONDS:
            return False, reason, (
                f"grant file is {age / 3600:.1f}h old (limit "
                f"{GRANT_MAX_AGE_SECONDS // 3600}h) -- a grant is for one job. "
                "Clear .claude/hooks/damage-control/.known-road-active, or rewrite it "
                "for the job in hand"), "stale"
        if age < -GRANT_FUTURE_SKEW_SECONDS:
            return False, reason, (
                "grant file mtime is in the future -- a future-dated grant would "
                "never age out. Rewrite .known-road-active"), "stale"

    if reason.startswith("handoff:"):
        return True, reason, "", "handoff-present"
    if offline:
        return True, reason, "", "offline-override"

    kind, number = reason.split(":", 1)
    try:
        st = _referent_state(kind, int(number))
    except GrantUnverifiable as exc:
        return False, reason, (
            f"grant not verifiable: {exc}. The guard refuses when it cannot look. "
            f"For deliberate offline work the operator may append '{OFFLINE_SUFFIX}' "
            f"to the grant (e.g. compose:{reason}{OFFLINE_SUFFIX}); the use is "
            "recorded as an offline override"), "unverifiable"
    if st["state"] == "open":
        return True, reason, "", "open"
    label = "PR" if kind == "pr" else "issue"
    when = f" at {st['at']}" if st.get("at") else ""
    return False, reason, (
        f"grant VOID: {label} #{number} on {CANONICAL_REPO} is {st['state'].upper()}"
        f"{when}, so the job it authorised is over. Clear "
        ".claude/hooks/damage-control/.known-road-active (or unset KNOWN_ROAD), or "
        "replace it with a reason for the work in hand"), st["state"]


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

    The node value is AMBIGUOUS: AGENT_ID is also used by other tools for an
    agent name, and whatever it holds is recorded as the node. Row schema and
    grouping rule (`node if present else agent`):
    .claude/skills/known-roads/SKILL.md § The trail row.
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
            note: str = "", grant_state: str = "", grant_source: str = "") -> bool:
    """Append one provable trail line. Returns False if it could not be written.

    `note` is free text describing HOW the use was observed. It is optional and
    omitted when empty, so existing rows and existing readers are unaffected --
    rows carrying a note already exist in the trail. The PostToolUse effect check
    uses it to distinguish a use it observed AFTER the fact (the command text
    never named the path) from a grant consulted BEFORE the write.

    Actor fields come from _actor_fields(); `node`, `agent_instance` and
    `unregistered_agent_type` are additive and omitted when they do not apply,
    so a row written outside any hook is byte-identical in shape to before.

    `grant_state` (open | offline-override | handoff-present) and `grant_source`
    (env | file) say HOW the grant was verified at the moment of use. Additive and
    omitted when empty, like `note`. Only honoured grants are recorded, so a
    refused state (merged, closed, stale, unverifiable) never appears in a row --
    the trail is a log of roads TAKEN.
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
        if grant_state:
            entry["grant_state"] = grant_state
        if grant_source:
            entry["grant_source"] = grant_source
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


def _read_grant() -> Tuple[str, str, Optional[float]]:
    """(raw_grant, source, mtime) -- source is "env", "file" or "".

    KNOWN_ROAD env var first, else the file grant. `mtime` is the file grant's
    modification time (None for an env grant, which has none -- see "Grant
    liveness" for how its age is bounded instead).
    """
    env = os.environ.get("KNOWN_ROAD", "").strip()
    if env:
        return env, "env", None
    try:
        gf = _grant_file()
        if gf.is_file():
            mtime = gf.stat().st_mtime
            for line in gf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line, "file", mtime
    except OSError:
        pass
    return "", "", None


def _active_grant() -> str:
    """The active Known Road grant: KNOWN_ROAD env var first, else the file grant.

    The env var is fixed in the launching process env and cannot be set mid-session
    in some clients, so a file grant (operator-written, e.g.
    `echo 'schema:handoff:x.md' > .claude/hooks/damage-control/.known-road-active`)
    is honored as an equivalent, operator-controlled authorization. The SAME rules
    apply downstream: the domain predicate must match AND the reason must be provable
    AND live (see "Grant liveness"), and every granted use records to
    known-roads.jsonl."""
    return _read_grant()[0]


def grant_status() -> Dict[str, object]:
    """Everything known about the grant in force, verified. For status displays.

    Keys: raw, source, mtime, domain, reason, ok, detail, grant_state. Performs
    the same liveness check the guard does (so it may call the GitHub API).
    """
    raw, source, mtime = _read_grant()
    out: Dict[str, object] = {"raw": raw, "source": source, "mtime": mtime,
                              "domain": "", "reason": "", "ok": False,
                              "detail": "", "grant_state": ""}
    if not raw:
        return out
    if ":" not in raw:
        out["detail"] = f"grant '{raw}' is not <domain>:<reason>"
        return out
    domain, raw_reason = raw.split(":", 1)
    domain = domain.strip().lower()
    out["domain"] = domain
    if domain not in DOMAIN_PATTERNS:
        out["reason"] = raw_reason.strip()
        out["detail"] = f"unknown domain '{domain}' (known: {known_road_domains()})"
        return out
    ok, reason, detail, state = _check_grant(raw_reason.strip(), source, mtime)
    out.update(reason=reason, ok=ok, detail=detail, grant_state=state)
    return out


def active_grant() -> Tuple[str, str, bool]:
    """(domain, reason, provable) for the grant currently in force.

    ("", "", False) when none is active. `provable` now means provable AND live:
    a well-formed grant whose PR has merged, or whose file has aged out, is False.
    `reason` has any `!offline` suffix removed. For the verification outcome and
    the refusal detail, use active_grant_verified().

    Public because the opaque-write tripwire in the Bash guard has to decide with
    NO TARGET PATH IN HAND: it fires on a verb that can write a path the command
    never spells, which is precisely why evaluate_known_road() -- whose whole
    contract is a per-file domain predicate -- has nothing to test against there.
    A caller using this is asserting less than one using evaluate_known_road: it
    learns that SOME grant is open, not that this grant covers this file. It must
    therefore never be used to allow an operation on a NAMED protected path; that
    decision stays with evaluate_known_road.
    """
    domain, reason, ok, _detail, _state, _source = active_grant_verified()
    return domain, reason, ok


def active_grant_verified() -> Tuple[str, str, bool, str, str, str]:
    """(domain, reason, ok, detail, grant_state, grant_source) -- active_grant()
    plus the verification outcome, so a caller can record it and explain a refusal.
    Same caveat as active_grant(): never the basis for allowing a NAMED path."""
    st = grant_status()
    if not st["raw"] or not st["domain"]:
        return "", "", False, str(st["detail"]), "", ""
    return (str(st["domain"]), str(st["reason"]), bool(st["ok"]), str(st["detail"]),
            str(st["grant_state"]), str(st["source"]))


def record_use(tool: str, file_path: str, domain: str, reason: str,
               note: str = "", grant_state: str = "", grant_source: str = "") -> bool:
    """Append one row to the trail. Public entry point for callers that have
    already made their own authorization decision (the opaque-write tripwire,
    the PostToolUse effect check). Returns False if it could not be written."""
    return _record(tool, file_path, domain, reason, note, grant_state, grant_source)


def evaluate_known_road(tool: str, file_path: str, normalized_fwd: str,
                        note: str = "") -> Tuple[bool, str]:
    """Evaluate the active Known Road grant (KNOWN_ROAD env var or file grant) for this edit/write.

    Returns (allowed, detail):
      (True,  detail)  bypass granted — caller should allow the operation
      (False, "")      no grant applies here — caller proceeds with normal checks
      (False, detail)  the file IS in the declared domain but the Known Road is invalid
                       (unprovable, expired, or unverifiable) — caller should block,
                       surfacing `detail` as the reason

    The liveness check (and so any GitHub API call) happens only AFTER the domain
    predicate matches: a grant costs nothing on a call that touches no path in
    its domain.
    """
    raw, source, mtime = _read_grant()
    if not raw or ":" not in raw:
        return False, ""

    domain, raw_reason = raw.split(":", 1)
    domain = domain.strip().lower()
    raw_reason = raw_reason.strip()

    predicate = DOMAIN_PATTERNS.get(domain)
    if predicate is None or not predicate(normalized_fwd):
        # Unknown domain, or this file is not in the declared domain.
        # Not applicable — let the normal readOnlyPath rules decide.
        return False, ""

    # The file IS in the declared domain. From here a malformed, unprovable or
    # expired reason is a hard block — the operator asked for a bypass on this
    # exact file, and the bypass they asked for is not one we can honour.
    ok, reason, detail, state = _check_grant(raw_reason, source, mtime)
    if not ok:
        if state == "unprovable":
            return False, f"Known Road reason not provable — {detail}"
        return False, f"Known Road grant {domain}:{raw_reason} refused — {detail}"

    if not _record(tool, file_path, domain, reason, note, state, source):
        return False, (
            "Known Road bypass could not be recorded to known-roads.jsonl — "
            "an unprovable bypass is denied (fail-closed)"
        )

    return True, (f"Known Road {domain}:{reason} [{state}] "
                  "(recorded to known-roads.jsonl)")


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
