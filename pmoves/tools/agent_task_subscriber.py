"""agent_task_subscriber.py - node-side worker for the Mavis harness.

The consumer half of the inter-agent wire: subscribes to
pmoves.agent.task.v1, keeps only the envelopes addressed to
``--agent`` (matching either the wire target or the alias), runs them
through a handler, and publishes the result on pmoves.agent.result.v1.

The orchestrator (pmoves/tools/orchestrator.py) is the dispatcher;
this module is the worker that makes a node a real dispatch target.
Affinity entries and routing tables are hints -- nothing dispatches to
a node until a subscriber like this is running on it.

Envelope contract (produced by Orchestrator.dispatch):

    {
      "task_id":   "<uuid>",
      "target":    "glm-5.1",           # wire target from routing
      "target_alias": "kiloclaw",       # the alias the caller used
      "task":      "...",
      "context":   {...},
      "bootstrap_id": "...",
      "issued_at": 1234.5,
    }

Result envelope (this module publishes):

    {
      "task_id":   "<uuid>",
      "target":    "<wire target>",
      "target_alias": "<alias>",
      "status":    "completed" | "error",
      "output":    "<handler output>",
      "error":     "<reason, on error>",
      "node":      "<hostname>",
      "completed_at": 1234.5,
    }

Usage:

    # SPARK hosts the mavis self-target:
    bash pmoves/scripts/with-env.sh python3 -m pmoves.tools.agent_task_subscriber \
        --agent mavis

    # A node hosting KiloClaw (wire target glm-5.1, alias kiloclaw):
    bash pmoves/scripts/with-env.sh python3 -m pmoves.tools.agent_task_subscriber \
        --agent glm-5.1 --alias kiloclaw

Handlers: the default handler logs the task and acknowledges it (the
harness-loop v0). A custom handler is any ``module.path:callable`` that
takes ``(envelope: dict) -> str``; it is imported lazily so a bad
``--handler`` fails on first task, not at startup.

nats-py is an optional dependency -- same lazy-import pattern as
beats_to_cgp.py. Without it the tool exits non-zero with a one-line
install hint rather than a stack trace.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import socket
import sys
import time
from typing import Any, Callable

SUBJECT_TASK = "pmoves.agent.task.v1"
SUBJECT_RESULT = "pmoves.agent.result.v1"

DEFAULT_NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")


def _host_fallback_url(url: str) -> str:
    """Rewrite a Docker-network alias to localhost for host-side runs.

    env.shared's NATS_URL names the in-network host (``nats``); run from
    the host shell that name does not resolve. The published port is the
    same (4222), so swapping the host is the only change needed.
    """
    import re

    return re.sub(r"@nats:", "@localhost:", url)

Handler = Callable[[dict[str, Any]], str]


def default_handler(envelope: dict[str, Any]) -> str:
    """v0 loop-closer: acknowledge the task so the dispatcher merges a result.

    Real work rides a custom --handler; this keeps the wire observable
    (dispatcher stops reporting 'pending' forever) without pretending
    to execute anything.
    """
    task = str(envelope.get("task", ""))[:120]
    return f"acknowledged by default handler on {socket.gethostname()}: {task!r}"


def load_handler(spec: str | None) -> Handler:
    if not spec:
        return default_handler
    module_path, _, attr = spec.partition(":")
    if not module_path or not attr:
        raise SystemExit(f"--handler must be module.path:callable, got {spec!r}")
    fn = getattr(importlib.import_module(module_path), attr)
    return fn  # type: ignore[return-value]


class AgentTaskSubscriber:
    def __init__(self, agent: str, aliases: list[str], handler: Handler, url: str):
        self.matches = {agent, *aliases, *(a for a in aliases if a)}
        self.handler = handler
        self.url = url
        self.received = 0
        self.completed = 0

    def _addresses_me(self, envelope: dict[str, Any]) -> bool:
        return envelope.get("target") in self.matches or envelope.get(
            "target_alias"
        ) in self.matches

    async def run(self, once: bool = False, idle_timeout_s: float | None = None) -> int:
        try:
            import nats as natspy
        except ImportError:
            print(
                "nats-py is required: pip install 'nats-py>=2.7'",
                file=sys.stderr,
            )
            return 2

        async def on_task(msg: Any) -> None:
            try:
                envelope = json.loads(msg.data.decode("utf-8", errors="replace"))
            except (ValueError, UnicodeDecodeError) as exc:
                print(f"[subscriber] unparseable task payload: {exc}", file=sys.stderr)
                return
            if not self._addresses_me(envelope):
                return
            self.received += 1
            result = {
                "task_id": envelope.get("task_id"),
                "target": envelope.get("target"),
                "target_alias": envelope.get("target_alias"),
                "node": socket.gethostname(),
                "completed_at": time.time(),
            }
            try:
                result["status"] = "completed"
                result["output"] = str(self.handler(envelope))
                self.completed += 1
            except Exception as exc:  # a bad handler fails one task, not the daemon
                result["status"] = "error"
                result["error"] = f"{type(exc).__name__}: {exc}"
            # JetStream-only: acking a core-NATS delivery raises, which
            # kills the callback and swallows the result publish.
            if getattr(msg, "_ack_needed", False):
                await msg.ack()
            await nc.publish(SUBJECT_RESULT, json.dumps(result).encode())
            print(f"[subscriber] {result['status']} task {result['task_id']}")

        try:
            url = self.url
            # Pre-check DNS: nats-py retries a dead hostname for minutes
            # before raising, so decide the fallback up front instead of
            # catching after.
            from urllib.parse import urlsplit

            host = urlsplit(
                url.replace("nats://", "http://", 1)
                if url.startswith("nats://")
                else url
            ).hostname
            if host and host != "localhost":
                import socket as _socket

                try:
                    _socket.getaddrinfo(host, None)
                except _socket.gaierror:
                    fallback = _host_fallback_url(url)
                    if fallback != url:
                        print(
                            f"[subscriber] {host} does not resolve here; "
                            f"using {fallback}"
                        )
                        url = fallback
            nc = await natspy.connect(url, connect_timeout=5, max_reconnect_attempts=3)
        except Exception as exc:
            print(
                f"[subscriber] cannot reach NATS at {self.url} "
                f"(or localhost fallback): {exc}",
                file=sys.stderr,
            )
            return 2
        await nc.subscribe(SUBJECT_TASK, cb=on_task)
        print(
            f"[subscriber] {socket.gethostname()} listening on {SUBJECT_TASK} "
            f"for {sorted(self.matches)} (nats at {self.url.split('@')[-1]})"
        )
        try:
            if once:
                while self.received == 0:
                    await asyncio.sleep(0.25)
            elif idle_timeout_s is not None:
                await asyncio.sleep(idle_timeout_s)
            else:
                while True:
                    await asyncio.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            await nc.drain()
        return 0 if (not once or self.completed > 0) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--agent",
        required=True,
        help="wire target this node answers to (e.g. mavis, glm-5.1, hermes-3)",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="additional alias to match (repeatable; e.g. --alias kiloclaw)",
    )
    parser.add_argument(
        "--handler",
        help="module.path:callable(envelope) -> str; default acknowledges",
    )
    parser.add_argument("--nats-url", default=DEFAULT_NATS_URL)
    parser.add_argument(
        "--once", action="store_true", help="exit after the first matching task"
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=None,
        help="exit after N seconds regardless of traffic (smoke use)",
    )
    args = parser.parse_args(argv)
    subscriber = AgentTaskSubscriber(
        agent=args.agent,
        aliases=args.alias,
        handler=load_handler(args.handler),
        url=args.nats_url,
    )
    return asyncio.run(subscriber.run(once=args.once, idle_timeout_s=args.idle_timeout))


if __name__ == "__main__":
    raise SystemExit(main())
