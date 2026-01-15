"""Session management for model lifecycle."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from models import LoadedModel, ModelState

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages sessions for model lifecycle tracking.

    A session represents a period of active use for one or more models.
    When a session ends, associated models may be unloaded after idle timeout.
    """

    def __init__(self, idle_timeout_seconds: int = 300):
        self.idle_timeout = idle_timeout_seconds
        self._sessions: Dict[str, "Session"] = {}
        self._model_sessions: Dict[str, str] = {}  # model_key -> session_id
        self._idle_check_task: Optional[asyncio.Task] = None
        self._on_idle_callback: Optional[Callable] = None

    async def start(self) -> None:
        """Start the session manager's idle check loop."""
        if self._idle_check_task is None:
            self._idle_check_task = asyncio.create_task(self._idle_check_loop())
            logger.info("Session manager started")

    async def stop(self) -> None:
        """Stop the session manager."""
        if self._idle_check_task:
            self._idle_check_task.cancel()
            try:
                await self._idle_check_task
            except asyncio.CancelledError:
                pass
            self._idle_check_task = None
            logger.info("Session manager stopped")

    def set_on_idle_callback(self, callback: Callable) -> None:
        """Set callback to be called when a model becomes idle."""
        self._on_idle_callback = callback

    def create_session(
        self,
        models: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Create a new session.

        Args:
            models: List of model keys (provider/model_id) to associate
            metadata: Optional metadata for the session

        Returns:
            Session ID
        """
        session_id = str(uuid4())
        session = Session(
            session_id=session_id,
            models=models or [],
            metadata=metadata or {},
        )
        self._sessions[session_id] = session

        # Associate models with session
        for model_key in session.models:
            self._model_sessions[model_key] = session_id

        logger.info(f"Created session {session_id} with models: {session.models}")
        return session_id

    def touch_session(self, session_id: str) -> bool:
        """Update session's last activity timestamp.

        Returns True if session exists, False otherwise.
        """
        session = self._sessions.get(session_id)
        if session:
            session.touch()
            return True
        return False

    def touch_model(self, model_key: str) -> bool:
        """Update model's last activity via its session.

        Returns True if model has an active session.
        """
        session_id = self._model_sessions.get(model_key)
        if session_id:
            return self.touch_session(session_id)
        return False

    def end_session(self, session_id: str) -> List[str]:
        """End a session and return list of orphaned model keys.

        Orphaned models may be candidates for unloading.
        """
        session = self._sessions.pop(session_id, None)
        if not session:
            return []

        orphaned = []
        for model_key in session.models:
            if self._model_sessions.get(model_key) == session_id:
                del self._model_sessions[model_key]
                orphaned.append(model_key)

        logger.info(f"Ended session {session_id}, orphaned models: {orphaned}")
        return orphaned

    def add_model_to_session(self, session_id: str, model_key: str) -> bool:
        """Add a model to an existing session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if model_key not in session.models:
            session.models.append(model_key)
            self._model_sessions[model_key] = session_id
            logger.debug(f"Added model {model_key} to session {session_id}")

        return True

    def remove_model_from_session(self, model_key: str) -> Optional[str]:
        """Remove a model from its session.

        Returns the session ID if model was in a session.
        """
        session_id = self._model_sessions.pop(model_key, None)
        if session_id:
            session = self._sessions.get(session_id)
            if session and model_key in session.models:
                session.models.remove(model_key)
        return session_id

    def get_session(self, session_id: str) -> Optional["Session"]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_model_session(self, model_key: str) -> Optional[str]:
        """Get session ID for a model."""
        return self._model_sessions.get(model_key)

    def get_idle_models(self, loaded_models: Dict[str, LoadedModel]) -> List[str]:
        """Get list of model keys that are idle (no active session or session idle)."""
        idle = []
        for model_key, model in loaded_models.items():
            if model.state != ModelState.LOADED:
                continue

            session_id = self._model_sessions.get(model_key)
            if not session_id:
                # No session - check model's own idle time
                if model.idle_seconds > self.idle_timeout:
                    idle.append(model_key)
            else:
                # Has session - check session idle time
                session = self._sessions.get(session_id)
                if session and session.is_idle(self.idle_timeout):
                    idle.append(model_key)

        return idle

    def list_sessions(self) -> List[Dict]:
        """List all active sessions."""
        return [s.to_dict() for s in self._sessions.values()]

    async def _idle_check_loop(self) -> None:
        """Periodically check for idle models."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Find idle sessions
                idle_sessions = [
                    s for s in self._sessions.values()
                    if s.is_idle(self.idle_timeout)
                ]

                for session in idle_sessions:
                    logger.debug(f"Session {session.session_id} is idle")
                    if self._on_idle_callback:
                        for model_key in session.models:
                            await self._on_idle_callback(model_key)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle check loop: {e}")


class Session:
    """Represents an active model session."""

    def __init__(
        self,
        session_id: str,
        models: List[str],
        metadata: Dict,
    ):
        self.session_id = session_id
        self.models = models
        self.metadata = metadata
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_idle(self, timeout_seconds: int) -> bool:
        """Check if session has been idle beyond timeout."""
        return (datetime.now() - self.last_activity).total_seconds() > timeout_seconds

    @property
    def idle_seconds(self) -> float:
        """Get seconds since last activity."""
        return (datetime.now() - self.last_activity).total_seconds()

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "models": self.models,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "idle_seconds": self.idle_seconds,
        }
