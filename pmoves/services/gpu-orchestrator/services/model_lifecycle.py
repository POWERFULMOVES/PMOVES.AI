"""Model lifecycle management - orchestrates loading and unloading of models."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from config import get_settings
from models import GpuStatus, LoadedModel, ModelRegistry, ModelState
from .ollama_client import OllamaClient
from .priority_queue import LoadRequest, Priority, PriorityQueue
from .session_manager import SessionManager
from .tts_client import TtsClient
from .vllm_client import VllmClient
from .vram_tracker import VramTracker

logger = logging.getLogger(__name__)


class ModelLifecycleManager:
    """Orchestrates model loading and unloading across providers.

    Features:
    - Priority-based load queue
    - Session-based lifecycle tracking
    - Automatic idle model unloading
    - VRAM-aware loading (auto-evict if needed)
    """

    def __init__(
        self,
        vram_tracker: VramTracker,
        model_registry: ModelRegistry,
        ollama_client: OllamaClient,
        vllm_client: VllmClient,
        tts_client: TtsClient,
    ):
        self.vram_tracker = vram_tracker
        self.registry = model_registry
        self.ollama = ollama_client
        self.vllm = vllm_client
        self.tts = tts_client

        settings = get_settings()
        self.idle_timeout = settings.idle_timeout_seconds
        self.vram_reserve = settings.system_vram_reserve_mb

        self.loaded_models: Dict[str, LoadedModel] = {}
        self.load_queue = PriorityQueue()
        self.session_manager = SessionManager(self.idle_timeout)

        self._load_worker_task: Optional[asyncio.Task] = None
        self._on_load_callback: Optional[Callable] = None
        self._on_unload_callback: Optional[Callable] = None

    async def start(self) -> None:
        """Start the lifecycle manager."""
        await self.session_manager.start()
        self.session_manager.set_on_idle_callback(self._handle_idle_model)
        self._load_worker_task = asyncio.create_task(self._load_worker())
        logger.info("Model lifecycle manager started")

    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        if self._load_worker_task:
            self._load_worker_task.cancel()
            try:
                await self._load_worker_task
            except asyncio.CancelledError:
                pass
        await self.session_manager.stop()
        logger.info("Model lifecycle manager stopped")

    def set_on_load_callback(self, callback: Callable) -> None:
        """Set callback for model load events."""
        self._on_load_callback = callback

    def set_on_unload_callback(self, callback: Callable) -> None:
        """Set callback for model unload events."""
        self._on_unload_callback = callback

    async def request_load(
        self,
        model_id: str,
        provider: str,
        priority: int = Priority.NORMAL,
        session_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """Request a model to be loaded.

        Returns (request_id, is_already_loaded)
        """
        model_key = f"{provider}/{model_id}"

        # Check if already loaded
        if model_key in self.loaded_models:
            model = self.loaded_models[model_key]
            if model.state == ModelState.LOADED:
                model.touch()
                if session_id:
                    self.session_manager.add_model_to_session(session_id, model_key)
                return model_key, True

        # Queue for loading
        request = LoadRequest(
            priority=priority,
            timestamp=datetime.now().timestamp(),
            model_id=model_id,
            provider=provider,
            session_id=session_id,
        )
        request_id = await self.load_queue.push(request)
        return request_id, False

    async def unload_model(
        self,
        model_id: str,
        provider: str,
        force: bool = False,
    ) -> bool:
        """Unload a model from GPU memory.

        Args:
            model_id: Model identifier
            provider: Provider (ollama, vllm, tts)
            force: If True, unload even if in active session

        Returns:
            True if model was unloaded successfully
        """
        model_key = f"{provider}/{model_id}"

        if model_key not in self.loaded_models:
            logger.warning(f"Model {model_key} is not loaded")
            return False

        model = self.loaded_models[model_key]

        # Check if in active session
        session_id = self.session_manager.get_model_session(model_key)
        if session_id and not force:
            session = self.session_manager.get_session(session_id)
            if session and not session.is_idle(self.idle_timeout):
                logger.warning(
                    f"Cannot unload {model_key} - active session {session_id}"
                )
                return False

        # Update state
        model.state = ModelState.UNLOADING

        # Call provider-specific unload
        success = await self._unload_from_provider(model_id, provider)

        if success:
            del self.loaded_models[model_key]
            self.session_manager.remove_model_from_session(model_key)
            logger.info(f"Unloaded model {model_key}")

            if self._on_unload_callback:
                await self._on_unload_callback(model_key)
        else:
            model.state = ModelState.LOADED
            logger.error(f"Failed to unload model {model_key}")

        return success

    async def optimize(self) -> Dict:
        """Optimize GPU usage by unloading idle models.

        Returns dict with actions taken.
        """
        actions = {"unloaded": [], "errors": []}

        # Get idle models
        idle_models = self.session_manager.get_idle_models(self.loaded_models)

        for model_key in idle_models:
            model = self.loaded_models.get(model_key)
            if model and model.provider == "ollama":  # Only Ollama supports dynamic unload
                try:
                    success = await self.unload_model(
                        model.model_id, model.provider, force=True
                    )
                    if success:
                        actions["unloaded"].append(model_key)
                    else:
                        actions["errors"].append(model_key)
                except Exception as e:
                    logger.error(f"Error unloading {model_key}: {e}")
                    actions["errors"].append(model_key)

        return actions

    async def get_status(self) -> GpuStatus:
        """Get complete GPU status including loaded models."""
        metrics = self.vram_tracker.get_metrics()
        processes = self.vram_tracker.get_processes()

        return GpuStatus(
            metrics=metrics,
            processes=processes,
            loaded_models=self.loaded_models,
            timestamp=datetime.now(),
        )

    def get_loaded_models(self) -> List[Dict]:
        """Get list of loaded models."""
        return [m.to_dict() for m in self.loaded_models.values()]

    def get_queue_status(self) -> Dict:
        """Get load queue status."""
        return self.load_queue.to_dict()

    async def _load_worker(self) -> None:
        """Worker that processes the load queue."""
        while True:
            try:
                request = await self.load_queue.pop()
                if request is None:
                    break

                await self._process_load_request(request)
                await self.load_queue.complete(request.request_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in load worker: {e}")
                # Still complete the request to avoid queue exhaustion
                if request:
                    try:
                        await self.load_queue.complete(request.request_id)
                    except Exception as complete_err:
                        logger.error(f"Error completing queue request {request.request_id}: {complete_err}")

    async def _process_load_request(self, request: LoadRequest) -> None:
        """Process a single load request."""
        model_key = request.model_key
        logger.info(f"Processing load request for {model_key}")

        # Check VRAM availability
        vram_needed = self.registry.get_vram_estimate(request.provider, request.model_id)
        available = self.vram_tracker.get_available_vram(self.vram_reserve)

        if vram_needed > available:
            # Try to free up VRAM by unloading idle models
            freed = await self._free_vram(vram_needed - available)
            available = self.vram_tracker.get_available_vram(self.vram_reserve)

            if vram_needed > available:
                error_msg = (
                    f"Insufficient VRAM for {model_key}: "
                    f"need {vram_needed}MB, have {available}MB"
                )
                logger.error(error_msg)

                # Create error model record for tracking
                model = LoadedModel(
                    model_id=request.model_id,
                    provider=request.provider,
                    vram_mb=vram_needed,
                    state=ModelState.ERROR,
                    loaded_at=datetime.now(),
                    last_used=datetime.now(),
                    idle_timeout_seconds=self.idle_timeout,
                    error_message=error_msg,
                )
                self.loaded_models[model_key] = model

                # Notify callback of failure
                if request.callback:
                    try:
                        await request.callback(False, model_key)
                    except Exception as callback_err:
                        logger.error(
                            f"Load callback error for {model_key} "
                            f"(request_id: {request.request_id}): {callback_err}"
                        )
                return

        # Create loaded model record
        model = LoadedModel(
            model_id=request.model_id,
            provider=request.provider,
            vram_mb=vram_needed,
            state=ModelState.LOADING,
            loaded_at=datetime.now(),
            last_used=datetime.now(),
            idle_timeout_seconds=self.idle_timeout,
            session_id=request.session_id,
        )
        self.loaded_models[model_key] = model

        # Load via provider
        success = await self._load_via_provider(request.model_id, request.provider)

        if success:
            model.state = ModelState.LOADED
            logger.info(f"Successfully loaded {model_key}")

            if request.session_id:
                self.session_manager.add_model_to_session(request.session_id, model_key)

            if self._on_load_callback:
                await self._on_load_callback(model_key)

            if request.callback:
                try:
                    await request.callback(True, model_key)
                except Exception as callback_err:
                    logger.error(
                        f"Load callback error for {model_key} "
                        f"(request_id: {request.request_id}): {callback_err}"
                    )
        else:
            model.state = ModelState.ERROR
            model.error_message = "Failed to load model"
            logger.error(f"Failed to load {model_key}")

            if request.callback:
                try:
                    await request.callback(False, model_key)
                except Exception as callback_err:
                    logger.error(
                        f"Load callback error for {model_key} "
                        f"(request_id: {request.request_id}): {callback_err}"
                    )

    async def _load_via_provider(self, model_id: str, provider: str) -> bool:
        """Load model using the appropriate provider."""
        if provider == "ollama":
            return await self.ollama.load_model(model_id)
        elif provider == "vllm":
            return await self.vllm.load_model(model_id)
        elif provider == "tts":
            return await self.tts.load_engine(model_id)
        else:
            logger.error(f"Unknown provider: {provider}")
            return False

    async def _unload_from_provider(self, model_id: str, provider: str) -> bool:
        """Unload model using the appropriate provider."""
        if provider == "ollama":
            return await self.ollama.unload_model(model_id)
        elif provider == "vllm":
            return await self.vllm.unload_model(model_id)
        elif provider == "tts":
            return await self.tts.unload_engine(model_id)
        else:
            logger.error(f"Unknown provider: {provider}")
            return False

    async def _free_vram(self, needed_mb: int) -> int:
        """Try to free up VRAM by unloading idle models.

        Returns amount of VRAM freed in MB.
        """
        freed = 0
        idle_models = self.session_manager.get_idle_models(self.loaded_models)

        # Sort by idle time (oldest first)
        sorted_idle = sorted(
            [(k, self.loaded_models[k]) for k in idle_models],
            key=lambda x: x[1].idle_seconds,
            reverse=True,
        )

        for model_key, model in sorted_idle:
            if freed >= needed_mb:
                break

            # Only Ollama supports dynamic unload
            if model.provider == "ollama":
                success = await self.unload_model(
                    model.model_id, model.provider, force=True
                )
                if success:
                    freed += model.vram_mb

        return freed

    async def _handle_idle_model(self, model_key: str) -> None:
        """Handle notification of an idle model."""
        logger.debug(f"Model {model_key} is idle")
        # Could trigger auto-unload here based on policy
