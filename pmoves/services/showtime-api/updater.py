"""Showtime updater — CHIT+OAuth-gated, blast-radius-scoped self-update logic.

This module is the readiness-oracle's update brain. It is intentionally
dependency-light (stdlib only) so it can be imported by:

  * ``app.py`` (FastAPI lifespan + ``GET /updater/gate``),
  * ``pmoves/tools/showtime_trigger_update.py`` (CLI / make target), and
  * ``pmoves/tests/unit/test_showtime_updater.py`` (pure-logic unit tests,
    runnable with ``--noconftest``).

Safety model
------------
* **Fail closed.** The gate is locked unless BOTH a non-placeholder CHIT
  passphrase AND a Google session token are present. Any error -> locked.
* **Blast radius.** ``run_update`` only acts on services inside an explicit
  allowlist. The :data:`SAFE_DEFAULT_BLAST_RADIUS` (data-tier only) is used
  when no room context supplies one. Agent-tier services are *never* updated,
  even if explicitly requested, and a global/"all"/"*" radius is rejected.
* **Never global pull.** Updates are per-service image refreshes; we never run
  a repo-wide ``git pull``. ``check_git_rev`` is read-only (``ls-remote``).
* **Dirty-worktree guard.** ``run_update`` aborts if any git worktree has
  uncommitted changes.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Placeholder detection — mirrors pmoves/tools/topology_chit_gate.py
# ---------------------------------------------------------------------------
PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "placeholder",
    "your_auth_token_here",
    "your_client_secret_here",
    "placeholder_db_password_here_generate_with_generate-keys.sh",
}

# Env keys that may carry a Google / Supabase OAuth session token.
GOOGLE_SESSION_ENV_KEYS = (
    "GOOGLE_SESSION_TOKEN",
    "GOOGLE_OAUTH_TOKEN",
    "GOOGLE_ID_TOKEN",
    "GOOGLE_ACCESS_TOKEN",
    "SUPABASE_SESSION",
    "SUPABASE_GOOGLE_TOKEN",
    "SUPABASE_ACCESS_TOKEN",
)

SKIP_CHIT_ENV_KEY = "SHOWTIME_UPDATER_SKIP_CHIT"

# ---------------------------------------------------------------------------
# Blast-radius definitions (service names, not container names)
# ---------------------------------------------------------------------------
# Data-tier services are the only ones touched by the SAFE DEFAULT radius:
# stateless-ish caches/stores whose restart does not cascade into running
# agents. NEVER includes agent-tier or anything global.
SAFE_DEFAULT_BLAST_RADIUS: tuple[str, ...] = (
    "loki",
    "open-notebook",
    "cipher-memory",
    "supabase-rest",
)

# Agent-tier services are hard-forbidden from any update radius. Restarting an
# agent mid-flight loses in-flight reasoning state, so the updater refuses.
AGENT_TIER_SERVICES: frozenset[str] = frozenset(
    {
        "agent-zero",
        "archon",
        "archon-ui",
        "botz-gateway",
        "supaserch",
        "evo-controller",
    }
)

# Tokens that mean "everything" — rejected outright (never global pull).
GLOBAL_TOKENS: frozenset[str] = frozenset({"all", "global", "*", "everything"})

# Superset of services the updater knows how to refresh. ``run_update`` acts on
# the intersection of this set with the supplied blast radius.
KNOWN_UPDATABLE_SERVICES: tuple[str, ...] = (
    "loki",
    "open-notebook",
    "cipher-memory",
    "supabase-rest",
    "tensorzero-gateway",
    "channel-monitor",
    "showtime-api",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def is_placeholder(value: str | None) -> bool:
    """True when a value is missing or a known placeholder (case-insensitive)."""
    return (value or "").strip().lower() in PLACEHOLDER_VALUES


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _run(cmd: Sequence[str], *, cwd: Path | None = None, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Gate — both factors must hold (fail closed)
# ---------------------------------------------------------------------------
def chit_passphrase_present(env: Mapping[str, str] | None = None) -> bool:
    """True when CHIT_PASSPHRASE is set and not a placeholder."""
    return not is_placeholder(_env(env).get("CHIT_PASSPHRASE"))


def google_session_present(env: Mapping[str, str] | None = None) -> bool:
    """True when any Google/Supabase OAuth session token is present and real."""
    e = _env(env)
    for key in GOOGLE_SESSION_ENV_KEYS:
        if not is_placeholder(e.get(key)):
            return True
    return False


def evaluate_gate(
    env: Mapping[str, str] | None = None,
    *,
    skip_chit: bool = False,
) -> dict[str, object]:
    """Evaluate the two-factor updater gate. Fail closed on any error.

    Unlocked iff BOTH:
      (a) a non-placeholder CHIT passphrase is present
          (auto-satisfied when ``skip_chit`` or ``SHOWTIME_UPDATER_SKIP_CHIT``),
      (b) a Google session token is present.

    Returns ``{"unlocked": bool, "reason": str, "chit_ok": bool,
    "google_ok": bool, "skip_chit": bool}``.
    """
    try:
        e = _env(env)
        skip = bool(skip_chit) or _is_true(e.get(SKIP_CHIT_ENV_KEY))
        chit_present = chit_passphrase_present(e)
        chit_ok = chit_present or skip
        google_ok = google_session_present(e)
        unlocked = bool(chit_ok and google_ok)

        if unlocked:
            if skip and not chit_present:
                reason = "unlocked (CHIT skipped via escape hatch; Google session present)"
            else:
                reason = "unlocked (CHIT passphrase + Google session present)"
        else:
            missing = []
            if not chit_ok:
                missing.append("CHIT passphrase missing/placeholder")
            if not google_ok:
                missing.append("Google session token missing")
            reason = "locked: " + "; ".join(missing)

        return {
            "unlocked": unlocked,
            "reason": reason,
            "chit_ok": bool(chit_ok),
            "google_ok": bool(google_ok),
            "skip_chit": bool(skip),
        }
    except Exception as exc:  # fail closed — never raise out of the gate
        return {
            "unlocked": False,
            "reason": f"locked: gate evaluation error ({type(exc).__name__})",
            "chit_ok": False,
            "google_ok": False,
            "skip_chit": bool(skip_chit),
        }


# ---------------------------------------------------------------------------
# Read-only revision / image checks
# ---------------------------------------------------------------------------
def check_git_rev(repo_root: Path | None = None) -> dict[str, object]:
    """Compare local HEAD against the remote tracking ref (read-only).

    Uses ``git rev-parse HEAD`` and ``git ls-remote`` — no fetch, no side
    effects on the working tree.
    """
    root = repo_root or Path(__file__).resolve().parents[3]
    out: dict[str, object] = {
        "local": None,
        "remote": None,
        "behind": None,
        "branch": None,
        "ok": False,
        "error": "",
    }
    try:
        head = _run(["git", "rev-parse", "HEAD"], cwd=root)
        if head.returncode != 0:
            out["error"] = "git rev-parse failed"
            return out
        out["local"] = head.stdout.strip()

        branch_res = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "HEAD"
        out["branch"] = branch

        ref = f"refs/heads/{branch}" if branch and branch != "HEAD" else "HEAD"
        remote = _run(["git", "ls-remote", "origin", ref], cwd=root)
        if remote.returncode != 0:
            out["error"] = "git ls-remote failed"
            return out
        first = remote.stdout.strip().split("\n")[0] if remote.stdout.strip() else ""
        remote_sha = first.split("\t")[0].strip() if first else ""
        out["remote"] = remote_sha or None
        out["behind"] = bool(remote_sha and remote_sha != out["local"])
        out["ok"] = True
        return out
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out


def check_image_digests(
    services: Iterable[str],
    *,
    expected: Mapping[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Best-effort local docker image digest inspection.

    Tolerates docker being absent: each service result carries an ``error``
    instead of raising. ``expected`` maps service -> expected digest/ref.
    """
    expected = expected or {}
    results: dict[str, dict[str, object]] = {}
    for svc in services:
        entry: dict[str, object] = {"digest": None, "expected": expected.get(svc), "match": None, "error": ""}
        try:
            res = _run(
                ["docker", "image", "inspect", svc, "--format", "{{index .RepoDigests 0}}"],
                timeout=15.0,
            )
            if res.returncode != 0:
                entry["error"] = (res.stderr or "docker image inspect failed").strip().splitlines()[0] if (res.stderr or "").strip() else "docker image inspect failed"
            else:
                digest = res.stdout.strip()
                entry["digest"] = digest or None
                exp = expected.get(svc)
                if exp:
                    entry["match"] = bool(digest and digest == exp)
        except FileNotFoundError:
            entry["error"] = "docker not available"
        except (OSError, subprocess.SubprocessError) as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results[svc] = entry
    return results


# ---------------------------------------------------------------------------
# Worktree-dirty guard
# ---------------------------------------------------------------------------
def parse_worktree_paths(porcelain: str) -> list[str]:
    """Extract worktree paths from ``git worktree list --porcelain`` output."""
    paths: list[str] = []
    for line in porcelain.splitlines():
        line = line.strip()
        if line.startswith("worktree "):
            paths.append(line[len("worktree ") :].strip())
    return paths


def _git_worktrees_dirty(repo_root: Path | None = None) -> bool:
    """True if ANY registered git worktree has uncommitted changes.

    Parses ``git worktree list --porcelain`` for paths, then checks each with
    ``git status --porcelain``. Any tree that cannot be inspected is treated as
    dirty (fail safe).
    """
    root = repo_root or Path(__file__).resolve().parents[3]
    listing = _run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if listing.returncode != 0:
        return True  # cannot determine -> refuse to update
    for path in parse_worktree_paths(listing.stdout):
        status = _run(["git", "status", "--porcelain"], cwd=Path(path))
        if status.returncode != 0:
            return True
        if status.stdout.strip():
            return True
    return False


# ---------------------------------------------------------------------------
# Blast-radius filtering + update execution
# ---------------------------------------------------------------------------
def filter_blast_radius(
    candidates: Iterable[str],
    blast_radius: Iterable[str],
) -> list[str]:
    """Return candidates that fall inside the blast radius (order preserved)."""
    allowed = set(blast_radius)
    return [svc for svc in candidates if svc in allowed]


def _default_executor(service: str) -> dict[str, object]:
    """Refresh a single service image via docker compose pull (best-effort).

    Per-service only — NEVER a repo-wide git pull.
    """
    res = _run(["docker", "compose", "pull", service], timeout=120.0)
    return {
        "service": service,
        "ok": res.returncode == 0,
        "detail": (res.stderr or res.stdout or "").strip().splitlines()[-1:] or [""],
    }


def run_update(
    blast_radius: Sequence[str] | None = None,
    *,
    candidates: Iterable[str] | None = None,
    dirty_check: Callable[[], bool] | None = None,
    executor: Callable[[str], object] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Run a blast-radius-scoped update.

    * ``blast_radius=None`` -> :data:`SAFE_DEFAULT_BLAST_RADIUS` (data-tier).
    * Rejects global radii and any agent-tier service (never agent-tier).
    * Aborts if any worktree is dirty.
    * Acts only on ``candidates ∩ blast_radius``. Never a global git pull.

    Returns a summary dict with ``status`` in
    {``ok``, ``aborted``, ``noop``}.
    """
    used_default = blast_radius is None
    radius = list(SAFE_DEFAULT_BLAST_RADIUS) if used_default else list(blast_radius)

    base = {
        "blast_radius": radius,
        "used_default_radius": used_default,
        "acted_on": [],
        "skipped": [],
    }

    # Guard 1: never global.
    global_hits = [s for s in radius if s.strip().lower() in GLOBAL_TOKENS]
    if global_hits:
        return {**base, "status": "aborted", "reason": f"global blast radius forbidden: {global_hits}"}

    # Guard 2: never agent-tier.
    agent_hits = [s for s in radius if s in AGENT_TIER_SERVICES]
    if agent_hits:
        return {**base, "status": "aborted", "reason": f"agent-tier services forbidden in radius: {agent_hits}"}

    # Guard 3: dirty worktree.
    is_dirty = dirty_check() if dirty_check is not None else _git_worktrees_dirty()
    if is_dirty:
        return {**base, "status": "aborted", "reason": "dirty worktree(s) detected; refusing to update"}

    pool = list(candidates) if candidates is not None else list(KNOWN_UPDATABLE_SERVICES)
    targets = filter_blast_radius(pool, radius)
    skipped = [s for s in radius if s not in targets]

    if not targets:
        return {**base, "status": "noop", "reason": "no known updatable services in blast radius", "skipped": skipped}

    exec_fn = executor or _default_executor
    acted: list[object] = []
    for svc in targets:
        if dry_run:
            acted.append({"service": svc, "ok": True, "detail": ["dry-run"]})
            continue
        try:
            acted.append(exec_fn(svc))
        except Exception as exc:  # one bad service must not nuke the rest
            acted.append({"service": svc, "ok": False, "detail": [f"{type(exc).__name__}: {exc}"]})

    return {
        **base,
        "status": "ok",
        "reason": f"updated {len(targets)} service(s) within blast radius",
        "acted_on": acted,
        "skipped": skipped,
    }
