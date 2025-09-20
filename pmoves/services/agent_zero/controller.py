import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from nats.aio.client import Client as NATS
from nats.aio.msg import Msg
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DeliverPolicy,
    RetentionPolicy,
    StreamConfig,
)
from nats.js.errors import APIError, NotFoundError

from services.common.events import envelope


logger = logging.getLogger(__name__)


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
    queue_name: Optional[str] = os.environ.get("AGENTZERO_QUEUE", "agentzero-workers")
    ack_wait_seconds: float = float(os.environ.get("AGENTZERO_ACK_WAIT_SECONDS", "30"))
    max_deliver: int = int(os.environ.get("AGENTZERO_MAX_DELIVER", "5"))
    subjects: Tuple[str, ...] = field(default_factory=lambda: tuple(
        s.strip() for s in os.environ.get(
            "AGENTZERO_SUBJECTS", "agentzero.task.v1,agentzero.memory.update"
        ).split(",")
        if s.strip()
    ))


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

    async def handle(self, session_id: str, event: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
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

    async def _worker(self, session_id: str, queue: "asyncio.Queue[SessionJob]") -> None:
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
        await asyncio.gather(*(state.task for _, state in sessions), return_exceptions=True)
        async with self._lock:
            self._sessions.clear()


class AgentZeroController:
    def __init__(self, settings: Optional[ControllerSettings] = None):
        self.settings = settings or ControllerSettings()
        self._nc: Optional[NATS] = None
        self._js = None
        self._session_manager = AgentZeroSessionManager(AgentZeroRuntime(self._publish_enveloped))
        self._subscriptions: List[Any] = []
        self._metrics = {
            "received": defaultdict(int),
            "acked": defaultdict(int),
            "nacked": defaultdict(int),
            "errors": defaultdict(int),
        }
        self._started = False

    @property
    def metrics(self) -> Dict[str, Dict[str, int]]:
        return {
            name: dict(counter)
            for name, counter in self._metrics.items()
        }

    async def start(self) -> None:
        if self._started:
            return
        logger.info("Connecting to NATS at %s", self.settings.nats_url)
        self._nc = NATS()
        await self._nc.connect(servers=[self.settings.nats_url])
        self._js = self._nc.jetstream()
        await self._ensure_stream()
        await self._create_subscriptions()
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        logger.info("Shutting down Agent Zero controller")
        await self._session_manager.shutdown()
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        if self._nc:
            await self._nc.drain()
            await self._nc.close()
        self._nc = None
        self._js = None
        self._started = False

    async def publish(self, topic: str, payload: Dict[str, Any], *, correlation_id: Optional[str] = None, parent_id: Optional[str] = None, source: str = "agent-zero") -> Dict[str, Any]:
        if not self._nc:
            raise RuntimeError("Controller not started")
        env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
        await self._nc.publish(topic.encode(), json.dumps(env).encode())
        return env

    async def _publish_enveloped(self, topic: str, payload: Dict[str, Any], *, correlation_id: Optional[str] = None, parent_id: Optional[str] = None) -> None:
        await self.publish(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source="agent-zero")

    async def _ensure_stream(self) -> None:
        assert self._js is not None
        stream_config = StreamConfig(
            name=self.settings.stream_name,
            subjects=list(self.settings.subjects),
            retention=RetentionPolicy.WORKQUEUE,
        )
        try:
            await self._js.add_stream(stream_config)
            logger.info("Created stream %s for subjects %s", self.settings.stream_name, stream_config.subjects)
        except APIError as exc:
            if exc.err_code == 10058:  # stream name already in use
                logger.debug("Stream %s already exists", self.settings.stream_name)
            else:
                logger.debug("Stream creation failed (may already exist): %s", exc)
                try:
                    await self._js.update_stream(stream_config)
                except Exception:  # noqa: BLE001
                    logger.warning("Unable to update stream %s", self.settings.stream_name, exc_info=exc)

    async def _create_subscriptions(self) -> None:
        assert self._js is not None
        for subject in self.settings.subjects:
            durable = f"{self.settings.durable_prefix}-{subject.replace('.', '-')}"
            config = SubscriptionConfig(
                subject=subject,
                durable=durable,
                queue=self.settings.queue_name,
                max_deliver=self.settings.max_deliver,
                ack_wait=self.settings.ack_wait_seconds,
            )
            await self._ensure_consumer(config)
            sub = await self._js.subscribe(
                subject,
                durable=config.durable,
                queue=config.queue,
                manual_ack=True,
                cb=self._wrap_handler(config),
            )
            self._subscriptions.append(sub)
            logger.info("Subscribed to %s with durable %s", subject, durable)

    async def _ensure_consumer(self, config: SubscriptionConfig) -> None:
        assert self._js is not None
        try:
            await self._js.consumer_info(self.settings.stream_name, config.durable)
            return
        except NotFoundError:
            pass
        consumer = ConsumerConfig(
            durable_name=config.durable,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=config.ack_wait,
            max_deliver=config.max_deliver,
            deliver_policy=DeliverPolicy.NEW,
        )
        await self._js.add_consumer(self.settings.stream_name, consumer)

    def _wrap_handler(self, config: SubscriptionConfig) -> Callable[[Msg], Awaitable[None]]:
        async def handler(msg: Msg) -> None:
            subject = msg.subject
            self._metrics["received"][subject] += 1
            try:
                data = json.loads(msg.data.decode())
            except json.JSONDecodeError as exc:
                logger.exception("Invalid JSON on %s", subject, exc_info=exc)
                self._metrics["errors"][subject] += 1
                await msg.term()
                return

            try:
                await self._session_manager.enqueue(data)
            except RetryableSessionError:
                self._metrics["nacked"][subject] += 1
                await msg.nak()
                return
            except TerminalSessionError as exc:
                logger.warning("Terminal session error on %s: %s", subject, exc)
                self._metrics["errors"][subject] += 1
                await msg.term()
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unhandled error for %s", subject, exc_info=exc)
                self._metrics["errors"][subject] += 1
                await msg.term()
                return

            await msg.ack()
            self._metrics["acked"][subject] += 1

        return handler


controller = AgentZeroController()
