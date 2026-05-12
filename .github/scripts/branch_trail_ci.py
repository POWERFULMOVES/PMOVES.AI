"""GitHub Actions shim for AGNOTE4482 §9.4 branch lifecycle CHIT trail.

Maps a GitHub Actions event (push/pull_request/delete) onto the lifecycle
enum understood by ``pmoves.services.common.branch_trail.emit()`` and
publishes the trail entry to NATS subject ``branch.<segments>.trail.v1``.

Pure parsing logic lives in :func:`parse_github_event` for unit testing.
The main coroutine is the only surface that touches NATS.

Best-effort by design: a NATS publish failure logs and exits 0 so
the workflow does not block branch operations.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("branch_trail_ci")

CI_AGENT_ID = "pmoves-ci-bot"
ZERO_SHA = "0" * 40


def _strip_refs_heads(ref: str) -> str:
    """Return the branch name from a ``refs/heads/<name>`` ref string."""
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else ref


def parse_github_event(
    event_name: str,
    event_data: dict[str, Any],
    ref: str,
    sha: str,
    repository: str,
    runner: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Translate a GitHub Actions event into ``emit()`` keyword args.

    Returns ``None`` when the event has no §9.4 lifecycle mapping (for
    example, ``pull_request closed`` without ``merged=true``, or pushes
    to existing branches).

    The four lifecycle events are mapped as follows:

    * ``push`` with ``before == 0x0`` → ``create``
    * ``pull_request opened`` → ``link_pr``
    * ``pull_request closed`` with ``merged == true`` → ``merge``
    * ``delete`` of a branch ref → ``delete``
    """
    base_pr_url = f"https://github.com/{repository}/pull"

    if event_name == "push":
        before = event_data.get("before") or ""
        if before != ZERO_SHA:
            return None
        branch = _strip_refs_heads(ref)
        if not branch or branch == "main":
            return None
        head_commit = event_data.get("head_commit") or {}
        committer = (
            (head_commit.get("author") or {}).get("name")
            or event_data.get("pusher", {}).get("name")
        )
        return {
            "branch": branch,
            "event": "create",
            "sha": sha,
            "committer": committer,
            "runner": runner,
        }

    if event_name == "pull_request":
        pr = event_data.get("pull_request") or {}
        action = event_data.get("action")
        head_ref = (pr.get("head") or {}).get("ref")
        if not head_ref:
            return None
        pr_number = pr.get("number")
        pr_url = f"{base_pr_url}/{pr_number}" if pr_number else pr.get("html_url")
        head_sha = (pr.get("head") or {}).get("sha") or sha
        author = (pr.get("user") or {}).get("login")

        if action == "opened":
            return {
                "branch": head_ref,
                "event": "link_pr",
                "pr_url": pr_url,
                "sha": head_sha,
                "committer": author,
                "runner": runner,
            }
        if action == "closed" and pr.get("merged") is True:
            merged_by = (pr.get("merged_by") or {}).get("login") or author
            merge_sha = pr.get("merge_commit_sha") or head_sha
            return {
                "branch": head_ref,
                "event": "merge",
                "pr_url": pr_url,
                "sha": merge_sha,
                "committer": merged_by,
                "runner": runner,
            }
        return None

    if event_name == "create":
        if event_data.get("ref_type") != "branch":
            return None
        branch = event_data.get("ref") or ""
        if not branch or branch == "main":
            return None
        sender = (event_data.get("sender") or {}).get("login")
        return {
            "branch": branch,
            "event": "create",
            "sha": sha,
            "committer": sender,
            "runner": runner,
        }

    if event_name == "delete":
        if event_data.get("ref_type") != "branch":
            return None
        branch = event_data.get("ref") or ""
        if not branch or branch == "main":
            return None
        sender = (event_data.get("sender") or {}).get("login")
        return {
            "branch": branch,
            "event": "delete",
            "committer": sender,
            "runner": runner,
        }

    return None


def _load_event_payload() -> dict[str, Any]:
    """Read ``GITHUB_EVENT_PATH`` JSON, or empty dict if missing."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def main() -> int:
    """Workflow entrypoint. Returns shell exit code (always 0 for best-effort)."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    sha = os.environ.get("GITHUB_SHA", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    runner = os.environ.get("RUNNER_NAME") or os.environ.get("GITHUB_RUN_ID")

    try:
        event_data = _load_event_payload()
    except Exception:
        logger.exception("failed to load GitHub event payload; continuing best-effort")
        return 0

    kwargs = parse_github_event(
        event_name=event_name,
        event_data=event_data,
        ref=ref,
        sha=sha,
        repository=repository,
        runner=runner,
    )
    if kwargs is None:
        logger.info(
            "no lifecycle mapping for event=%s action=%s ref=%s — skipping",
            event_name,
            event_data.get("action"),
            ref,
        )
        return 0

    if os.environ.get("BRANCH_TRAIL_DRY_RUN") == "1":
        logger.info("DRY_RUN — would emit: %s", kwargs)
        return 0

    from pmoves.services.common.branch_trail import emit

    try:
        ok = await emit(agent_id=CI_AGENT_ID, ecosystem="github", **kwargs)
    except Exception:
        logger.exception("branch_trail.emit raised; continuing best-effort")
        return 0
    if not ok:
        logger.warning(
            "branch_trail.emit returned False (NATS publish best-effort "
            "failure) — workflow continues, exit 0"
        )
    else:
        logger.info(
            "emitted %s on branch %s (sha=%s)",
            kwargs["event"],
            kwargs["branch"],
            kwargs.get("sha", "")[:7],
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
