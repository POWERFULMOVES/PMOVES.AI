"""VRAM tracking using pynvml for GPU metrics."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

from models import GpuMetrics, ProcessInfo

logger = logging.getLogger(__name__)


class VramTracker:
    """Tracks GPU VRAM usage using NVIDIA Management Library (pynvml)."""

    def __init__(self, gpu_index: int = 0):
        self.gpu_index = gpu_index
        self._initialized = False
        self._handle = None
        self._container_cache: Dict[int, Tuple[str, str]] = {}

        if PYNVML_AVAILABLE:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize pynvml and get GPU handle."""
        if not PYNVML_AVAILABLE:
            logger.warning("pynvml not available - running in mock mode")
            return

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if self.gpu_index >= device_count:
                logger.error(f"GPU index {self.gpu_index} not found. Available: {device_count}")
                return

            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            self._initialized = True
            logger.info(f"Initialized VramTracker for GPU {self.gpu_index}")
        except pynvml.NVMLError as e:
            logger.error(f"Failed to initialize pynvml: {e}")

    def shutdown(self) -> None:
        """Shutdown pynvml cleanly."""
        if PYNVML_AVAILABLE and self._initialized:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass

    def get_metrics(self) -> GpuMetrics:
        """Get current GPU metrics."""
        if not self._initialized:
            return self._mock_metrics()

        try:
            # GPU name
            name = pynvml.nvmlDeviceGetName(self._handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            # Memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            total_mb = mem_info.total // (1024 * 1024)
            used_mb = mem_info.used // (1024 * 1024)
            free_mb = mem_info.free // (1024 * 1024)

            # Temperature
            temp = pynvml.nvmlDeviceGetTemperature(
                self._handle, pynvml.NVML_TEMPERATURE_GPU
            )

            # Utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)

            # Power (if available)
            try:
                power_draw = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000  # mW to W
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(self._handle) / 1000
            except pynvml.NVMLError:
                power_draw = None
                power_limit = None

            return GpuMetrics(
                gpu_index=self.gpu_index,
                name=name,
                total_vram_mb=total_mb,
                used_vram_mb=used_mb,
                free_vram_mb=free_mb,
                temperature_c=temp,
                utilization_percent=util.gpu,
                power_draw_w=power_draw,
                power_limit_w=power_limit,
            )
        except pynvml.NVMLError as e:
            logger.error(f"Error getting GPU metrics: {e}")
            return self._mock_metrics()

    def _mock_metrics(self) -> GpuMetrics:
        """Return mock metrics when pynvml is unavailable."""
        return GpuMetrics(
            gpu_index=self.gpu_index,
            name="Mock GPU (pynvml unavailable)",
            total_vram_mb=32768,
            used_vram_mb=0,
            free_vram_mb=32768,
            temperature_c=0,
            utilization_percent=0,
        )

    def get_processes(self) -> List[ProcessInfo]:
        """Get list of processes using the GPU."""
        if not self._initialized:
            return []

        processes = []
        try:
            # Get compute processes
            compute_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self._handle)
            for proc in compute_procs:
                proc_info = self._build_process_info(proc)
                if proc_info:
                    processes.append(proc_info)

            # Get graphics processes (if supported)
            try:
                graphics_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(self._handle)
                for proc in graphics_procs:
                    # Avoid duplicates
                    if not any(p.pid == proc.pid for p in processes):
                        proc_info = self._build_process_info(proc)
                        if proc_info:
                            processes.append(proc_info)
            except pynvml.NVMLError:
                pass  # Graphics processes not supported on all GPUs

        except pynvml.NVMLError as e:
            logger.error(f"Error getting GPU processes: {e}")

        return processes

    def _build_process_info(self, proc) -> Optional[ProcessInfo]:
        """Build ProcessInfo from pynvml process object."""
        try:
            pid = proc.pid
            vram_mb = proc.usedGpuMemory // (1024 * 1024) if proc.usedGpuMemory else 0

            # Get process name
            name = self._get_process_name(pid)

            # Get container info
            container_id, container_name = self._get_container_info(pid)

            return ProcessInfo(
                pid=pid,
                name=name,
                vram_mb=vram_mb,
                container_id=container_id,
                container_name=container_name,
            )
        except Exception as e:
            logger.debug(f"Error building process info for PID {proc.pid}: {e}")
            return None

    def _get_process_name(self, pid: int) -> str:
        """Get process name from /proc/{pid}/comm."""
        try:
            comm_path = Path(f"/proc/{pid}/comm")
            if comm_path.exists():
                return comm_path.read_text().strip()
        except (OSError, PermissionError):
            pass
        return f"pid-{pid}"

    def _get_container_info(self, pid: int) -> Tuple[Optional[str], Optional[str]]:
        """Get container ID and name from process cgroup."""
        # Check cache first
        if pid in self._container_cache:
            return self._container_cache[pid]

        container_id = None
        container_name = None

        try:
            cgroup_path = Path(f"/proc/{pid}/cgroup")
            if cgroup_path.exists():
                content = cgroup_path.read_text()

                # Look for Docker container ID patterns
                # Docker cgroup v2: 0::/system.slice/docker-{container_id}.scope
                # Docker cgroup v1: various patterns with /docker/{container_id}
                patterns = [
                    r"/docker[/-]([a-f0-9]{64})",
                    r"/docker/([a-f0-9]{12,64})",
                    r"docker-([a-f0-9]{64})\.scope",
                ]

                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        container_id = match.group(1)[:12]  # Short ID
                        break

                # Try to get container name from Docker
                if container_id:
                    container_name = self._get_docker_container_name(container_id)

        except (OSError, PermissionError):
            pass

        result = (container_id, container_name)
        self._container_cache[pid] = result
        return result

    def _get_docker_container_name(self, container_id: str) -> Optional[str]:
        """Get Docker container name from container ID."""
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.Name}}", container_id],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                name = result.stdout.strip().lstrip("/")
                return name if name else None
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return None

    def get_available_vram(self, reserve_mb: int = 2048) -> int:
        """Get available VRAM after reserving system memory."""
        metrics = self.get_metrics()
        available = metrics.free_vram_mb - reserve_mb
        return max(0, available)

    def can_fit_model(self, vram_required_mb: int, reserve_mb: int = 2048) -> bool:
        """Check if a model can fit in available VRAM."""
        return self.get_available_vram(reserve_mb) >= vram_required_mb

    def clear_container_cache(self) -> None:
        """Clear the container info cache."""
        self._container_cache.clear()
