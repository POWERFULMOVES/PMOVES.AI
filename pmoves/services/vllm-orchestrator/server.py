"""vLLM Orchestrator Server.

Provides API for managing vLLM instances with dynamic parallelism configuration.
Integrates with node registry to discover available GPU resources.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional

from .config import (
    VLLMConfig,
    MODEL_CONFIGS,
    create_vllm_config,
    ParallelismStrategy,
)

logger = logging.getLogger(__name__)


class VLLMOrchestrator:
    """Orchestrator for vLLM service instances.

    Manages vLLM container lifecycle, configuration generation,
    and integration with node registry for resource discovery.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        model_path: str = "/models",
        compose_dir: str = "/tmp/vllm-compose",
    ):
        """Initialize vLLM orchestrator.

        Args:
            nats_url: NATS server URL for node registry communication
            model_path: Path to model weights
            compose_dir: Directory for generated docker-compose files
        """
        self.nats_url = nats_url
        self.model_path = model_path
        self.compose_dir = compose_dir
        self._instances: Dict[str, VLLMConfig] = {}
        self._nc = None
        self._js = None

    async def start(self):
        """Start the orchestrator.

        Connects to NATS for node registry communication.
        """
        try:
            import nats

            self._nc = await nats.connect(self.nats_url)
            self._js = self._nc.jetstream()

            logger.info(f"Connected to NATS at {self.nats_url}")

            # Subscribe to work requests
            await self._subscribe_work_requests()

        except ImportError:
            logger.error("nats-py not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to start orchestrator: {e}")
            raise

    async def stop(self):
        """Stop the orchestrator."""
        if self._nc:
            await self._nc.close()
        logger.info("Orchestrator stopped")

    async def _subscribe_work_requests(self):
        """Subscribe to vLLM work requests."""
        import nats
        import json

        async def on_request(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                model_name = payload.get("model_name")
                if not model_name:
                    await self._send_error(msg.reply, "Missing model_name")
                    return

                # Create configuration
                config = await self._create_config_for_request(payload)

                if config is None:
                    await self._send_error(msg.reply, "No suitable nodes available")
                    return

                # Generate and send response
                response = {
                    "request_id": payload.get("request_id"),
                    "model_name": model_name,
                    "tensor_parallel_size": config.tensor_parallel_size,
                    "pipeline_parallel_size": config.pipeline_parallel_size,
                    "strategy": config.strategy.value,
                    "docker_compose": config.to_docker_compose(),
                    "endpoints": {
                        "api": f"http://localhost:{config.port}",
                        "metrics": f"http://localhost:{config.metrics_port}",
                    },
                }

                await self._nc.publish(msg.reply, json.dumps(response).encode())
                logger.info(f"Generated config for {model_name}")

            except Exception as e:
                logger.error(f"Error processing work request: {e}")
                await self._send_error(msg.reply, str(e))

        await self._nc.subscribe("compute.vllm.request.v1", cb=on_request)
        logger.info("Subscribed to compute.vllm.request.v1")

    async def _send_error(self, subject: str, message: str):
        """Send error response.

        Args:
            subject: Reply subject
            message: Error message
        """
        if not subject:
            return

        import json

        error_response = {
            "error": True,
            "message": message,
        }

        await self._nc.publish(subject, json.dumps(error_response).encode())

    async def _create_config_for_request(self, payload: Dict) -> Optional[VLLMConfig]:
        """Create vLLM configuration for a work request.

        Args:
            payload: Work request payload

        Returns:
            VLLMConfig if resources available, None otherwise
        """
        model_name = payload["model_name"]

        # Query node registry for available resources
        available_nodes = await self._query_node_registry(
            requires_gpu=True,
            min_tier="gpu_peer",
        )

        if not available_nodes:
            logger.warning("No GPU nodes available")
            return None

        # Aggregate resources
        total_gpus = sum(n.get("gpu_count", 0) for n in available_nodes)
        avg_vram = sum(n.get("gpu_vram_gb", 0) for n in available_nodes) / max(1, len(available_nodes))
        node_count = len(available_nodes)

        # Calculate optimal configuration
        try:
            config = create_vllm_config(
                model_name=model_name,
                available_gpus=total_gpus,
                vram_per_gpu_mb=int(avg_vram * 1024),
                available_nodes=node_count,
                gpus_per_node=total_gpus // node_count if node_count > 0 else 1,
            )
            return config

        except ValueError as e:
            logger.error(f"Failed to create config: {e}")
            return None

    async def _query_node_registry(
        self,
        requires_gpu: bool = False,
        min_tier: Optional[str] = None,
    ) -> List[Dict]:
        """Query node registry for available nodes.

        Args:
            requires_gpu: Filter for GPU nodes
            min_tier: Minimum tier required

        Returns:
            List of node capability dictionaries
        """
        import json

        query = {
            "query_id": f"vllm-orchestrator-{asyncio.get_event_loop().time()}",
            "requires_gpu": requires_gpu,
            "min_tier": min_tier,
            "online_only": True,
        }

        # Use NATS request-response pattern with timeout
        try:
            response = await self._nc.request(
                "compute.nodes.query.v1",
                json.dumps(query).encode(),
                timeout=5,  # 5 second timeout
            )

            if response:
                data = response.data.decode()
                payload = json.loads(data)
                return payload.get("nodes", [])

        except asyncio.TimeoutError:
            logger.warning("Node registry query timed out")
        except Exception as e:
            logger.error(f"Error querying node registry: {e}")

        return []

    def generate_compose_file(self, config: VLLMConfig) -> str:
        """Generate docker-compose.yml file content.

        Args:
            config: vLLM configuration

        Returns:
            YAML content for docker-compose file
        """
        compose_dict = config.to_docker_compose()

        # Add header
        lines = [
            "# Auto-generated by vllm-orchestrator",
            f"# Model: {config.model_name}",
            f"# TP: {config.tensor_parallel_size}, PP: {config.pipeline_parallel_size}",
            f"# Total GPUs: {config.total_parallel_size}",
            "",
            "version: '3.8'",
            "",
        ]

        # Convert to YAML
        lines.append(self._dict_to_yaml(compose_dict))

        return "\n".join(lines)

    def _dict_to_yaml(self, d: Dict, indent: int = 0) -> str:
        """Convert dict to YAML string (simple implementation).

        Args:
            d: Dictionary to convert
            indent: Indentation level

        Returns:
            YAML string
        """
        lines = []
        prefix = "  " * indent

        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  -")
                        for k, v in item.items():
                            lines.append(f"{prefix}    {k}: {v}")
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")

        return "\n".join(lines)

    async def deploy_instance(
        self,
        model_name: str,
        instance_name: Optional[str] = None,
    ) -> Optional[VLLMConfig]:
        """Deploy a vLLM instance.

        Args:
            model_name: Name of the model to deploy
            instance_name: Optional instance name (defaults to model name)

        Returns:
            VLLMConfig if deployed, None otherwise
        """
        instance_name = instance_name or f"vllm-{model_name}"

        if instance_name in self._instances:
            logger.warning(f"Instance {instance_name} already exists")
            return self._instances[instance_name]

        # Query available resources and create config
        payload = {"model_name": model_name}
        config = await self._create_config_for_request(payload)

        if config is None:
            logger.error(f"Failed to deploy {model_name}: no suitable nodes")
            return None

        # Generate compose file
        compose_content = self.generate_compose_file(config)
        compose_path = os.path.join(self.compose_dir, f"{instance_name}.yml")

        os.makedirs(self.compose_dir, exist_ok=True)
        with open(compose_path, "w") as f:
            f.write(compose_content)

        logger.info(f"Generated compose file: {compose_path}")

        # Deploy using docker compose (would require subprocess call)
        # For now, just track the instance
        self._instances[instance_name] = config

        return config

    async def stop_instance(self, instance_name: str) -> bool:
        """Stop a vLLM instance.

        Args:
            instance_name: Name of instance to stop

        Returns:
            True if stopped, False if not found
        """
        if instance_name not in self._instances:
            return False

        # Remove from tracking
        del self._instances[instance_name]

        # Remove compose file
        compose_path = os.path.join(self.compose_dir, f"{instance_name}.yml")
        if os.path.exists(compose_path):
            os.remove(compose_path)

        logger.info(f"Stopped instance: {instance_name}")
        return True

    def list_instances(self) -> Dict[str, VLLMConfig]:
        """List all managed instances.

        Returns:
            Dict mapping instance names to configs
        """
        return self._instances.copy()

    def get_instance(self, instance_name: str) -> Optional[VLLMConfig]:
        """Get instance configuration.

        Args:
            instance_name: Name of instance

        Returns:
            VLLMConfig if found, None otherwise
        """
        return self._instances.get(instance_name)


async def run_orchestrator(
    nats_url: str = "nats://localhost:4222",
    model_path: str = "/models",
    compose_dir: str = "/tmp/vllm-compose",
):
    """Run the vLLM orchestrator service.

    Args:
        nats_url: NATS server URL
        model_path: Path to model weights
        compose_dir: Directory for compose files
    """
    orchestrator = VLLMOrchestrator(
        nats_url=nats_url,
        model_path=model_path,
        compose_dir=compose_dir,
    )

    await orchestrator.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    model_path = os.environ.get("MODEL_PATH", "/models")

    try:
        asyncio.run(run_orchestrator(nats_url, model_path))
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")
