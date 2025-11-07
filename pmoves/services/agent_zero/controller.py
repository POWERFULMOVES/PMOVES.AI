import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

try:
    from nats.aio.client import Client as NATS
    from nats.aio.msg import Msg
    from nats.js.api import (
        AckPolicy,
        DeliverPolicy,
        RetentionPolicy,
        StreamConfig,
        ConsumerConfig,
    )
    from nats.js.errors import APIError, NotFoundError
    from nats.errors import TimeoutError as NATSTimeoutError
except ModuleNotFoundError:  # pragma: no cover - optional dependency for tests
    NATS = None  # type: ignore[assignment]
    Msg = Any  # type: ignore[assignment]
    NATSTimeoutError = TimeoutError  # type: ignore[assignment]

    class _StubError(Exception):
        pass

    class AckPolicy:  # type: ignore[no-redef]
        EXPLICIT = "explicit"

    class DeliverPolicy:  # type: ignore[no-redef]
        NEW = "new"
        ALL = "all"

    class RetentionPolicy:  # type: ignore[no-redef]
        WORKQUEUE = "workqueue"
        WORK_QUEUE = "workqueue"
        LIMITS = "limits"
        INTEREST = "interest"

    @dataclass
    class ConsumerConfig:  # type: ignore[no-redef]
        durable_name: str
        ack_policy: str
        ack_wait: float
        max_deliver: int
        deliver_policy: str
        deliver_group: Optional[str] = None
        deliver_subject: Optional[str] = None
        filter_subject: Optional[str] = None

    @dataclass
    @dataclass
    class StreamConfig:  # type: ignore[no-redef]
        name: str
        subjects: List[str]
        retention: str

    class APIError(_StubError):
        def __init__(self, err_code: int) -> None:
            super().__init__(f"NATS unavailable (err_code={err_code})")
            self.err_code = err_code

    class NotFoundError(_StubError):
        pass


try:
    from services.common.events import envelope
except Exception:  # pragma: no cover - optional dependency for unit tests
    import datetime
    import uuid

    def envelope(
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "agent",
    ) -> Dict[str, Any]:
        event: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "v1",
            "source": source,
            "payload": payload,
        }
        if correlation_id:
            event["correlation_id"] = correlation_id
        if parent_id:
            event["parent_id"] = parent_id
        return event


logger = logging.getLogger(__name__)

WORK_QUEUE_POLICY = getattr(
    RetentionPolicy,
    "WORKQUEUE",
    getattr(RetentionPolicy, "WORK_QUEUE", getattr(RetentionPolicy, "LIMITS", RetentionPolicy.INTEREST)),
)


class RetryableSessionError(Exception):
    """Raised when a session operation should be retried."""


class TerminalSessionError(Exception):
    """Raised when a session operation should not be retried."""


@dataclass
class SubscriptionConfig:
    subject: str
    durable: str
    queue: Optional[str]
    max_deliver: int
    ack_wait: float


@dataclass
class ControllerSettings:
    nats_url: str = os.environ.get("NATS_URL", "nats://nats:4222")
    stream_name: str = os.environ.get("AGENTZERO_STREAM", "AGENTZERO")
    durable_prefix: str = os.environ.get("AGENTZERO_DURABLE_PREFIX", "agentzero")
    queue_name: Optional[str] = os.environ.get(
        "AGENTZERO_QUEUE", "agentzero-workers"
    )
    use_jetstream: bool = os.environ.get("AGENTZERO_JETSTREAM", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ack_wait_seconds: float = float(os.environ.get("AGENTZERO_ACK_WAIT_SECONDS", "30"))
    max_deliver: int = int(os.environ.get("AGENTZERO_MAX_DELIVER", "5"))
    subjects: Tuple[str, ...] = field(
        default_factory=lambda: tuple(
            s.strip()
            for s in os.environ.get(
                "AGENTZERO_SUBJECTS", "agentzero.task.v1,agentzero.memory.update"
            ).split(",")
            if s.strip()
        )
    )


@dataclass
class SessionJob:
    envelope: Dict[str, Any]
    future: asyncio.Future


@dataclass
class SessionState:
    queue: "asyncio.Queue[SessionJob]"
    task: asyncio.Task


class AgentZeroRuntime:
    """Minimal runtime shim that generates synthetic Agent Zero session events."""

    def __init__(self, publisher: Callable[..., Awaitable[None]]):
        self._publish = publisher

    async def handle(
        self, session_id: str, event: Dict[str, Any]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        topic = event.get("topic")
        payload = event.get("payload", {})
        correlation_id = event.get("correlation_id")
        parent_id = event.get("id")
        outputs: List[Tuple[str, Dict[str, Any]]] = []

        if topic == "agentzero.task.v1":
            task_id = payload.get("task_id") or payload.get("id") or parent_id
            status_payload = {
                "session_id": session_id,
                "task_id": task_id,
                "status": "queued",
                "metadata": payload.get("metadata", {}),
            }
            result_payload = {
                "session_id": session_id,
                "task_id": task_id,
                "status": "completed",
                "output": payload.get("instructions") or payload.get("input"),
            }
            outputs.extend(
                [
                    ("agentzero.task.status.v1", status_payload),
                    ("agentzero.task.result.v1", result_payload),
                ]
            )
        elif topic == "agentzero.memory.update":
            outputs.append(
                (
                    "agentzero.memory.ack.v1",
                    {
                        "session_id": session_id,
                        "state": payload.get("state", {}),
                        "op": payload.get("op", "append"),
                    },
                )
            )
        else:
            outputs.append(
                (
                    "agentzero.event.log.v1",
                    {
                        "session_id": session_id,
                        "source_topic": topic,
                        "message": payload,
                    },
                )
            )

        for out_topic, out_payload in outputs:
            await self._publish(
                out_topic,
                out_payload,
                correlation_id=correlation_id,
                parent_id=parent_id,
            )
        return outputs


class AgentZeroSessionManager:
    def __init__(self, runtime: AgentZeroRuntime):
        self._runtime = runtime
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()
        self._shutdown = asyncio.Event()

    async def enqueue(self, event: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        payload = event.get("payload") or {}
        session_id = payload.get("session_id")
        if not session_id:
            raise TerminalSessionError("session_id missing from payload")

        state = await self._ensure_session(session_id)
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        job = SessionJob(event, future)
        await state.queue.put(job)
        try:
            result = await future
        except Exception:
            raise
        return result

    async def _ensure_session(self, session_id: str) -> SessionState:
        async with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            queue: "asyncio.Queue[SessionJob]" = asyncio.Queue()
            task = asyncio.create_task(self._worker(session_id, queue))
            state = SessionState(queue=queue, task=task)
            self._sessions[session_id] = state
            return state

    async def _worker(
        self, session_id: str, queue: "asyncio.Queue[SessionJob]"
    ) -> None:
        while True:
            job = await queue.get()
            try:
                if job.envelope.get("topic") == "__shutdown__":
                    if not job.future.done():
                        job.future.set_result([])
                    queue.task_done()
                    break
                result = await self._runtime.handle(session_id, job.envelope)
                if not job.future.done():
                    job.future.set_result(result)
            except RetryableSessionError as exc:
                logger.warning("Retryable error for session %s: %s", session_id, exc)
                if not job.future.done():
                    job.future.set_exception(exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error in session %s worker", session_id, exc_info=exc)
                if not job.future.done():
                    job.future.set_exception(exc)
            finally:
                queue.task_done()

    async def shutdown(self) -> None:
        self._shutdown.set()
        async with self._lock:
            sessions = list(self._sessions.items())
        if not sessions:
            return
        loop = asyncio.get_running_loop()
        for session_id, state in sessions:
            await state.queue.put(
                SessionJob(
                    {"topic": "__shutdown__", "payload": {"session_id": session_id}},
                    loop.create_future(),
                )
            )
        await asyncio.gather(
            *(state.task for _, state in sessions), return_exceptions=True
        )
        async with self._lock:
            self._sessions.clear()


class AgentZeroController:
    def __init__(self, settings: Optional[ControllerSettings] = None):
        self.settings = settings or ControllerSettings()
        self._nc: Optional[NATS] = None
        self._js = None
        self._session_manager = AgentZeroSessionManager(
            AgentZeroRuntime(self._publish_enveloped)
        )
        self._subscriptions: List[Any] = []
        self._metrics = {
            "received": defaultdict(int),
            "acked": defaultdict(int),
            "nacked": defaultdict(int),
            "errors": defaultdict(int),
        }
        self._started = False
        self._pull_tasks: List[asyncio.Task] = []

    @property
    def metrics(self) -> Dict[str, Dict[str, int]]:
        return {name: dict(counter) for name, counter in self._metrics.items()}

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_connected(self) -> bool:
        return bool(self._nc and self._nc.is_connected)

    async def start(self) -> None:
        if self._started:
            return
        if NATS is None:
            raise RuntimeError("nats-py is required to start the Agent Zero controller")
        logger.info("Connecting to NATS at %s", self.settings.nats_url)
        self._nc = NATS()
        await self._nc.connect(servers=[self.settings.nats_url])
        if self.settings.use_jetstream:
            self._js = self._nc.jetstream()
            await self._ensure_stream()
        else:
            self._js = None
        await self._create_subscriptions()
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        logger.info("Shutting down Agent Zero controller")
        await self._session_manager.shutdown()
        for task in self._pull_tasks:
            task.cancel()
        if self._pull_tasks:
            await asyncio.gather(*self._pull_tasks, return_exceptions=True)
        self._pull_tasks.clear()
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        if self._nc:
            await self._nc.drain()
            await self._nc.close()
        self._nc = None
        self._js = None
        self._started = False

    async def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "agent-zero",
    ) -> Dict[str, Any]:
        if not self._nc:
            raise RuntimeError("Controller not started")
        env = envelope(
            topic,
            payload,
            correlation_id=correlation_id,
            parent_id=parent_id,
            source=source,
        )
        await self._nc.publish(topic, json.dumps(env).encode())
        return env

    async def _publish_enveloped(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> None:
        await self.publish(
            topic,
            payload,
            correlation_id=correlation_id,
            parent_id=parent_id,
            source="agent-zero",
        )

    async def _ensure_stream(self) -> None:
        assert self._js is not None
        stream_config = StreamConfig(
            name=self.settings.stream_name,
            subjects=list(self.settings.subjects),
            retention=WORK_QUEUE_POLICY,
        )
        try:
            await self._js.add_stream(stream_config)
            logger.info(
                "Created stream %s for subjects %s",
                self.settings.stream_name,
                stream_config.subjects,
            )
        except APIError as exc:
            if exc.err_code == 10058:  # stream name already in use
                logger.debug("Stream %s already exists", self.settings.stream_name)
            else:
                logger.debug("Stream creation failed (may already exist): %s", exc)
                try:
                    await self._js.update_stream(stream_config)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Unable to update stream %s",
                        self.settings.stream_name,
                        exc_info=exc,
                    )

    async def _create_subscriptions(self) -> None:
        subjects = tuple(self.settings.subjects)
        if not subjects:
            logger.warning("No Agent Zero subjects configured; controller idle")
            return
        if not self.settings.use_jetstream or self._js is None:
            assert self._nc is not None
            for subject in subjects:
                durable = f"{self.settings.durable_prefix}-{subject.replace('.', '-')}"
                config = SubscriptionConfig(
                    subject=subject,
                    durable=durable,
                    queue=self.settings.queue_name,
                    max_deliver=self.settings.max_deliver,
                    ack_wait=self.settings.ack_wait_seconds,
                )
                sub = await self._nc.subscribe(
                    subject,
                    queue=self.settings.queue_name,
                    cb=self._wrap_handler(config),
                )
                self._subscriptions.append(sub)
                logger.info("Subscribed to %s (core NATS)", subject)
            return

        assert self._js is not None
        for subject in subjects:
            durable = f"{self.settings.durable_prefix}-{subject.replace('.', '-')}"
            config = SubscriptionConfig(
                subject=subject,
                durable=durable,
                queue=None,
                max_deliver=self.settings.max_deliver,
                ack_wait=self.settings.ack_wait_seconds,
            )
            consumer_cfg = ConsumerConfig(
                durable_name=durable,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=self.settings.ack_wait_seconds,
                max_deliver=self.settings.max_deliver,
                deliver_policy=getattr(DeliverPolicy, "ALL", DeliverPolicy.NEW),
                filter_subject=subject,
            )
            should_create = False
            try:
                info = await self._js.consumer_info(
                    self.settings.stream_name, durable
                )
                existing_filter = getattr(info.config, "filter_subject", None)
                deliver_subject = getattr(info.config, "deliver_subject", None)
                deliver_group = getattr(info.config, "deliver_group", None)

                if deliver_subject or deliver_group:
                    logger.info(
                        "Recreating JetStream consumer %s (legacy push delivery)",
                        durable,
                    )
                    await self._js.delete_consumer(
                        self.settings.stream_name, durable
                    )
                    should_create = True
                elif existing_filter != subject:
                    logger.info(
                        "Recreating JetStream consumer %s (filter mismatch: %s -> %s)",
                        durable,
                        existing_filter,
                        subject,
                    )
                    await self._js.delete_consumer(
                        self.settings.stream_name, durable
                    )
                    should_create = True
                else:
                    deliver_subject = getattr(info.config, "deliver_subject", None)
                    deliver_group = getattr(info.config, "deliver_group", None)
                    push_fields = []
                    if deliver_subject:
                        push_fields.append(f"deliver_subject={deliver_subject}")
                    if deliver_group:
                        push_fields.append(f"deliver_group={deliver_group}")
                    if push_fields:
                        logger.info(
                            "Recreating JetStream consumer %s to drop push delivery (%s)",
                            durable,
                            ", ".join(push_fields),
                        )
                        await self._js.delete_consumer(
                            self.settings.stream_name, durable
                        )
                        should_create = True
            except NotFoundError:
                should_create = True

            if should_create:
                try:
                    await self._js.add_consumer(
                        self.settings.stream_name, consumer_cfg
                    )
                    logger.info(
                        "Created JetStream consumer %s for %s",
                        durable,
                        subject,
                    )
                except APIError as exc:
                    logger.warning(
                        "JetStream consumer add failed (%s): %s",
                        durable,
                        exc,
                    )
            sub = await self._js.pull_subscribe(
                subject,
                stream=self.settings.stream_name,
                durable=durable,
            )
            handler = self._wrap_handler(config)
            task = asyncio.create_task(
                self._pull_worker(sub, handler, subject, durable)
            )
            self._pull_tasks.append(task)
            self._subscriptions.append(sub)
            logger.info(
                "Subscribed to %s with JetStream durable %s (pull mode)", subject, durable
            )

    async def _pull_worker(
        self,
        sub: Any,
        handler: Callable[[Msg], Awaitable[None]],
        subject: str,
        durable: str,
    ) -> None:
        """Continuously fetch batches from a JetStream pull subscription."""
        batch_size = 10
        consecutive_unavailable = 0
        fallback_threshold = int(os.environ.get("AGENTZERO_JS_UNAVAILABLE_THRESHOLD", "3"))
        while True:
            try:
                messages = await sub.fetch(batch=batch_size, timeout=1)
            except NATSTimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "JetStream pull loop error for %s (%s): %s",
                    subject,
                    durable,
                    exc,
                )
                # If JetStream is temporarily unavailable, fall back to core NATS after a few tries.
                if type(exc).__name__ == "ServiceUnavailableError":
                    consecutive_unavailable += 1
                    if consecutive_unavailable >= fallback_threshold:
                        try:
                            logger.warning(
                                "Falling back to core NATS subscription for %s after repeated ServiceUnavailable",
                                subject,
                            )
                            await self._fallback_to_core_nats()
                        except Exception:
                            logger.exception("Fallback to core NATS failed")
                        return
                await asyncio.sleep(1)
                continue

            for msg in messages:
                try:
                    await handler(msg)
                except asyncio.CancelledError:
                    raise
                except Exception:  # pragma: no cover - handler logs errors
                    logger.exception(
                        "Handler error for %s (%s)", subject, durable, exc_info=True
                    )

    def _wrap_handler(
        self, config: SubscriptionConfig
    ) -> Callable[[Msg], Awaitable[None]]:
        async def handler(msg: Msg) -> None:
            subject = msg.subject
            self._metrics["received"][subject] += 1
            try:
                data = json.loads(msg.data.decode())
            except json.JSONDecodeError as exc:
                logger.exception("Invalid JSON on %s", subject, exc_info=exc)
                self._metrics["errors"][subject] += 1
                if hasattr(msg, "term"):
                    await msg.term()
                return

            try:
                await self._session_manager.enqueue(data)
            except RetryableSessionError:
                self._metrics["nacked"][subject] += 1
                if hasattr(msg, "nak"):
                    await msg.nak()
                return
            except TerminalSessionError as exc:
                logger.warning("Terminal session error on %s: %s", subject, exc)
                self._metrics["errors"][subject] += 1
                if hasattr(msg, "term"):
                    await msg.term()
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unhandled error for %s", subject, exc_info=exc)
                self._metrics["errors"][subject] += 1
                if hasattr(msg, "term"):
                    await msg.term()
                return

            if hasattr(msg, "ack"):
                await msg.ack()
            self._metrics["acked"][subject] += 1

        return handler

    async def _fallback_to_core_nats(self) -> None:
        """Tear down JetStream pull subscriptions and re-subscribe using core NATS queue subs.

        This keeps Agent Zero functional when JetStream is temporarily unavailable.
        """
        if not self._nc:
            return
        # Cancel pull tasks and unsubscribe from JS
        for task in self._pull_tasks:
            task.cancel()
        if self._pull_tasks:
            await asyncio.gather(*self._pull_tasks, return_exceptions=True)
        self._pull_tasks.clear()
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        self._subscriptions.clear()
        # Disable JS for this controller and create core subscriptions
        self.settings.use_jetstream = False
        await self._create_subscriptions()


controller = AgentZeroController()
