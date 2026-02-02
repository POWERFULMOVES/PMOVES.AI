"""Hardware detection module for PMOVES.AI resource allocation.

Detects system resources including RAM, CPU, and GPU capabilities.
Generates appropriate docker-compose resource limits based on available hardware.
"""

import dataclasses
import enum
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Resource reservation constants
DEFAULT_RESERVE_PERCENT = 0.15  # 15% of resources reserved by default


class NodeTier(enum.Enum):
    """Node capability tier for P2P compute marshaling.

    Tiers determine the role a node can play in the distributed network:
    - AI_FACTORY: High-end training (RTX 5090/4090, 128GB+ RAM)
    - WORKER_HUB: Multi-GPU inference servers (2+ GPUs, 64GB+ RAM)
    - GPU_PEER: Single consumer GPU (24GB+ VRAM, 32GB+ RAM)
    - CPU_PEER: CPU-only nodes for embeddings/preprocessing (16GB+ RAM)
    - EDGE: Jetson/NUC for local inference (ARM64, low power)
    - DISASTER: Air-gapped fallback (minimal specs, offline mode)

    Resource thresholds are conservative to ensure headroom for
    system overhead and Docker containerization.
    """

    AI_FACTORY = "ai_factory"
    WORKER_HUB = "worker_hub"
    GPU_PEER = "gpu_peer"
    CPU_PEER = "cpu_peer"
    EDGE = "edge"
    DISASTER = "disaster"

    @classmethod
    def from_hardware(
        cls,
        gpu_vram_gb: float,
        gpu_count: int,
        ram_gb: float,
        cpu_threads: int,
        is_arm: bool = False,
        network_class: str = "unknown",
    ) -> "NodeTier":
        """Determine node tier from detected hardware.

        Args:
            gpu_vram_gb: Total VRAM across all GPUs in GB
            gpu_count: Number of GPUs detected
            ram_gb: System RAM in GB
            cpu_threads: Total CPU threads
            is_arm: True if ARM architecture (Jetson, NUC, etc.)
            network_class: Network bandwidth class (ultra, high, medium, low, very_low)

        Returns:
            Appropriate NodeTier for the hardware profile.
        """
        # Edge devices (ARM-based, low RAM)
        if is_arm or ram_gb < 16:
            return cls.EDGE

        # AI Factory: High-end training node
        # RTX 5090 (32GB) or 4090 (24GB) with 128GB+ RAM
        # High-speed network (10Gbps+) can boost tier for multi-node training
        has_high_speed_network = network_class in ("ultra", "high", "medium_high")
        is_ai_factory_gpu = gpu_count >= 1 and gpu_vram_gb >= 24 and ram_gb >= 128

        if is_ai_factory_gpu:
            # High-speed network confirms AI Factory tier
            if has_high_speed_network or gpu_count >= 2:
                return cls.AI_FACTORY
            # Single GPU with lower network is still AI Factory, but borderline
            return cls.AI_FACTORY

        # Worker Hub: Multi-GPU inference
        # Can also be achieved with single GPU + high-speed network for distributed work
        if gpu_count >= 2 and ram_gb >= 64:
            return cls.WORKER_HUB

        # GPU Peer: Single GPU for distributed inference
        if gpu_count >= 1 and gpu_vram_gb >= 16 and ram_gb >= 32:
            return cls.GPU_PEER

        # CPU Peer: CPU-only for embeddings/preprocessing
        # High-speed network can compensate for no GPU
        if ram_gb >= 16:
            return cls.CPU_PEER

        # Disaster: Minimal fallback
        return cls.DISASTER

    @property
    def priority(self) -> int:
        """Priority for work assignment (higher = preferred for heavy work)."""
        return {
            self.AI_FACTORY: 100,
            self.WORKER_HUB: 80,
            self.GPU_PEER: 60,
            self.CPU_PEER: 40,
            self.EDGE: 20,
            self.DISASTER: 10,
        }[self]

    @property
    def can_train(self) -> bool:
        """Whether this tier can handle model training."""
        return self in (self.AI_FACTORY, self.WORKER_HUB)

    @property
    def can_infer_gpu(self) -> bool:
        """Whether this tier can run GPU inference."""
        return self in (self.AI_FACTORY, self.WORKER_HUB, self.GPU_PEER)

    @property
    def can_embed(self) -> bool:
        """Whether this tier can handle embedding generation."""
        return self in (self.AI_FACTORY, self.WORKER_HUB, self.GPU_PEER, self.CPU_PEER)


@dataclasses.dataclass
class CpuInfo:
    """CPU information."""
    cores: int
    threads_per_core: int
    total_threads: int
    model_name: str
    mhz_per_cpu: float


@dataclasses.dataclass
class GpuInfo:
    """GPU information."""
    index: int
    name: str
    total_vram_mb: int
    total_vram_gb: float
    driver_version: str
    cuda_version: str
    # Multi-GPU topology fields
    nvlink_enabled: bool = False
    nvlink_version: Optional[str] = None  # e.g., "2.0", "3.0", "4.0"
    nvlink_peers: List[int] = dataclasses.field(default_factory=list)  # GPU indices connected via NVLink
    pci_bus_id: Optional[str] = None
    numa_node: Optional[int] = None  # NUMA node affinity

    @property
    def has_nvlink(self) -> bool:
        """Whether this GPU has NVLink connections."""
        return self.nvlink_enabled and len(self.nvlink_peers) > 0

    @property
    def max_nvlink_bandwidth_gbps(self) -> float:
        """Get maximum NVLink bandwidth in GB/s.

        NVLink versions:
        - 1.0: 20 GB/s per link (P100)
        - 2.0: 25 GB/s per link (V100)
        - 3.0: 50 GB/s per link (A100)
        - 4.0: 70 GB/s per link (H100)
        """
        if not self.nvlink_version:
            return 0.0

        bandwidths = {
            "1.0": 20.0,
            "2.0": 25.0,
            "3.0": 50.0,
            "4.0": 70.0,
        }

        per_link = bandwidths.get(self.nvlink_version, 0.0)
        return per_link * len(self.nvlink_peers)


@dataclasses.dataclass
class SystemMemory:
    """System memory information."""
    total_mb: int
    total_gb: float
    available_mb: int
    available_gb: float


@dataclasses.dataclass
class NetworkInterface:
    """Information about a single network interface."""
    name: str
    # Interface type classification
    is_loopback: bool = False
    is_virtual: bool = False  # Includes veth, docker, bridge interfaces
    is_wireless: bool = False
    # Speed info (may be None for virtual interfaces)
    speed_mbps: Optional[int] = None  # -1 means unknown/unplugged
    mac_address: Optional[str] = None
    ipv4_addresses: List[str] = dataclasses.field(default_factory=list)
    ipv6_addresses: List[str] = dataclasses.field(default_factory=list)
    # Driver info
    driver: Optional[str] = None
    # Statistics
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None

    @property
    def speed_gbps(self) -> Optional[float]:
        """Speed in Gb/s."""
        if self.speed_mbps is None or self.speed_mbps < 0:
            return None
        return self.speed_mbps / 1000.0

    @property
    def is_physical(self) -> bool:
        """Whether this is a physical interface."""
        return not (self.is_loopback or self.is_virtual)

    @property
    def bandwidth_class(self) -> str:
        """Classify interface by bandwidth tier."""
        if self.speed_mbps is None:
            return "unknown"
        if self.speed_mbps >= 100000:  # 100 Gbps
            return "ultra"
        elif self.speed_mbps >= 40000:  # 40 Gbps
            return "high"
        elif self.speed_mbps >= 10000:  # 10 Gbps
            return "medium_high"
        elif self.speed_mbps >= 1000:  # 1 Gbps
            return "medium"
        elif self.speed_mbps >= 100:  # 100 Mbps
            return "low"
        else:
            return "very_low"


@dataclasses.dataclass
class NetworkInfo:
    """Network capability information."""
    interfaces: List[NetworkInterface]
    # Primary interface for P2P traffic (first physical non-loopback)
    primary_interface: Optional[NetworkInterface] = None
    # Aggregated capabilities
    total_interfaces: int = 0
    physical_interfaces: int = 0
    max_speed_mbps: int = 0
    has_infiniband: bool = False
    # Network classification
    network_class: str = "unknown"  # ultra, high, medium, low, very_low

    def __post_init__(self):
        """Derive aggregated properties."""
        self.total_interfaces = len(self.interfaces)
        self.physical_interfaces = sum(1 for i in self.interfaces if i.is_physical)

        # Find primary interface (first physical with IP)
        if not self.primary_interface:
            for iface in self.interfaces:
                if iface.is_physical and iface.ipv4_addresses:
                    self.primary_interface = iface
                    break

        # Calculate max speed and check for InfiniBand
        for iface in self.interfaces:
            if iface.is_physical and iface.speed_mbps and iface.speed_mbps > self.max_speed_mbps:
                self.max_speed_mbps = iface.speed_mbps
            if iface.driver and "ib_" in iface.driver.lower():
                self.has_infiniband = True

        # Determine network class
        if self.max_speed_mbps >= 100000:
            self.network_class = "ultra"
        elif self.max_speed_mbps >= 40000:
            self.network_class = "high"
        elif self.max_speed_mbps >= 10000:
            self.network_class = "medium_high"
        elif self.max_speed_mbps >= 1000:
            self.network_class = "medium"
        elif self.max_speed_mbps >= 100:
            self.network_class = "low"
        elif self.max_speed_mbps > 0:
            self.network_class = "very_low"

    @property
    def max_speed_gbps(self) -> float:
        """Maximum interface speed in Gb/s."""
        return self.max_speed_mbps / 1000.0


@dataclasses.dataclass
class HardwareProfile:
    """Complete hardware profile."""
    cpu: CpuInfo
    memory: SystemMemory
    gpus: List[GpuInfo]
    total_gpu_vram_gb: float
    is_detected: bool
    network: Optional[NetworkInfo] = None
    tier: NodeTier = dataclasses.field(init=False)

    def __post_init__(self):
        """Determine node tier from detected hardware."""
        # Check for ARM architecture (edge devices)
        is_arm = "aarch64" in os.uname().machine or "arm" in os.uname().machine.lower()

        self.tier = NodeTier.from_hardware(
            gpu_vram_gb=self.total_gpu_vram_gb,
            gpu_count=len(self.gpus),
            ram_gb=self.memory.total_gb,
            cpu_threads=self.cpu.total_threads,
            is_arm=is_arm,
            network_class=self.network.network_class if self.network else "unknown",
        )


class HardwareDetector:
    """Detects system hardware for dynamic resource allocation."""

    def __init__(self, reserve_percent: float = DEFAULT_RESERVE_PERCENT):
        """Initialize hardware detector.

        Args:
            reserve_percent: Percentage of resources to reserve for system (default 15%)
        """
        self.reserve_percent = reserve_percent
        self._profile: Optional[HardwareProfile] = None
        # Track if actual hardware detection succeeded (vs fallback defaults)
        self._detection_succeeded = False

    def detect(self) -> HardwareProfile:
        """Detect all system hardware."""
        if self._profile is not None:
            return self._profile

        cpu = self._detect_cpu()
        memory = self._detect_memory()
        gpus = self._detect_gpus()
        network = self._detect_network()

        total_gpu_vram = sum(g.total_vram_gb for g in gpus)

        # is_detected is True only when actual detection succeeded
        # (not when we used fake/safe default values)
        self._profile = HardwareProfile(
            cpu=cpu,
            memory=memory,
            gpus=gpus,
            total_gpu_vram_gb=total_gpu_vram,
            is_detected=self._detection_succeeded,
            network=network,
        )

        logger.info(
            "Hardware detected",
            cpu_cores=cpu.cores,
            cpu_threads=cpu.total_threads,
            ram_gb=f"{memory.total_gb:.1f}",
            gpus=len(gpus),
            total_gpu_vram_gb=f"{total_gpu_vram:.1f}",
            network_class=network.network_class if network else "unknown",
            network_max_gbps=f"{network.max_speed_gbps:.1f}" if network else None,
            tier=self._profile.tier.value,
        )

        return self._profile

    def _detect_cpu(self) -> CpuInfo:
        """Detect CPU information."""
        try:
            # Try lscpu first (most detailed)
            result = subprocess.run(
                ["lscpu"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return self._parse_lscpu(result.stdout)

            # Fallback to /proc/cpuinfo
            return self._parse_proc_cpuinfo()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Could not detect CPU: {e}", exc_info=True)
            # Return safe defaults - is_detected will be False
            return CpuInfo(
                cores=1,  # Minimal, not fake
                threads_per_core=1,
                total_threads=1,
                model_name="Detection Failed",
                mhz_per_cpu=0.0,
            )

    def _parse_lscpu(self, output: str) -> CpuInfo:
        """Parse lscpu output."""
        self._detection_succeeded = True  # Mark successful detection
        data = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

        cores = int(data.get("CPU(s)", "4"))
        sockets = int(data.get("Socket(s)", "1"))
        cores_per_socket = int(data.get("Core(s) per socket", str(cores // sockets)))
        threads_per_core = int(data.get("Thread(s) per core", "1"))

        model = data.get("Model name", "Unknown CPU")
        # Clean up CPU model name
        model = re.sub(r'\s+', ' ', model).strip()

        mhz = float(data.get("CPU MHz", "0"))

        return CpuInfo(
            cores=cores_per_socket * sockets,
            threads_per_core=threads_per_core,
            total_threads=cores,
            model_name=model,
            mhz_per_cpu=mhz,
        )

    def _parse_proc_cpuinfo(self) -> CpuInfo:
        """Parse /proc/cpuinfo."""
        try:
            content = Path("/proc/cpuinfo").read_text()
            processors = content.split("\n\n")

            model = "Unknown"
            mhz = 0.0

            for proc in processors[:1]:  # First processor is enough
                for line in proc.splitlines():
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                    elif line.startswith("cpu MHz"):
                        mhz = float(line.split(":", 1)[1].strip())

            self._detection_succeeded = True  # Mark successful detection

            return CpuInfo(
                cores=len(processors),
                threads_per_core=1,
                total_threads=len(processors),
                model_name=model,
                mhz_per_cpu=mhz,
            )
        except (OSError, ValueError) as e:
            logger.error(f"Could not parse /proc/cpuinfo: {e}", exc_info=True)
            # Return safe defaults - is_detected will be False
            return CpuInfo(1, 1, 1, "Detection Failed", 0.0)

    def _detect_memory(self) -> SystemMemory:
        """Detect system memory."""
        try:
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                if len(lines) >= 2:
                    # Mem: total used free shared buff/cache available
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        total_mb = int(parts[1])
                        avail_mb = int(parts[3]) if len(parts) > 3 else total_mb
                        self._detection_succeeded = True  # Mark successful detection
                        return SystemMemory(
                            total_mb=total_mb,
                            total_gb=total_mb / 1024,
                            available_mb=avail_mb,
                            available_gb=avail_mb / 1024,
                        )
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
            logger.error(f"Could not detect memory: {e}", exc_info=True)

        # Return minimal safe defaults - is_detected will be False
        # Use 1GB minimum (not fake 16GB) so allocation doesn't OOM immediately
        return SystemMemory(
            total_mb=1024,
            total_gb=1.0,
            available_mb=1024,
            available_gb=1.0,
        )

    def _detect_gpus(self) -> List[GpuInfo]:
        """Detect GPU information including multi-GPU topology."""
        gpus: List[GpuInfo] = []

        # Try pynvml for NVIDIA GPUs (best for topology detection)
        try:
            import pynvml

            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()

            # First pass: collect basic GPU info
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_vram_mb = mem_info.total // (1024 * 1024)

                try:
                    driver_version = pynvml.nvmlSystemGetDriverVersion()
                    if isinstance(driver_version, bytes):
                        driver_version = driver_version.decode("utf-8")
                except pynvml.NVMLError:
                    driver_version = "unknown"

                try:
                    cuda_version = pynvml.nvmlSystemGetCudaDriverVersion()
                    cuda_version = f"{cuda_version // 1000}.{cuda_version % 1000}"
                except pynvml.NVMLError:
                    cuda_version = "unknown"

                # Get PCI bus ID
                pci_bus_id = None
                try:
                    pci_info = pynvml.nvmlDeviceGetPciInfo(handle)
                    pci_bus_id = pci_info.busId.decode("utf-8") if hasattr(pci_info, "busId") else None
                except (pynvml.NVMLError, AttributeError):
                    pass

                # Get NUMA node
                numa_node = None
                try:
                    numa_node = pynvml.nvmlDeviceGetNumaNode(handle)
                except (pynvml.NVMLError, AttributeError):
                    pass

                # Detect NVLink
                nvlink_enabled = False
                nvlink_version = None
                nvlink_peers = []

                try:
                    # Check NVLink availability using unit info
                    # This returns the maximum NVLink version supported
                    unit_info = pynvml.nvmlDeviceGetUnitInfo(handle)
                    if hasattr(unit_info, "nvlinkVersion"):
                        nvlink_version = str(unit_info.nvlinkVersion)
                        nvlink_enabled = True
                except (pynvml.NVMLError, AttributeError):
                    pass

                # Alternative method: check for NVLink using field values
                try:
                    # NVLink 3.0 and later
                    field_values = pynvml.nvmlDeviceGetFieldValues(handle, [pynvml.NVML_FI_DEV_NVLINK_VERSION])
                    if field_values and field_values[0].nvmlReturn == pynvml.NVML_SUCCESS:
                        nvlink_ver_int = field_values[0].value.ui
                        if nvlink_ver_int > 0:
                            nvlink_version = f"{nvlink_ver_int / 10:.1f}"
                            nvlink_enabled = True
                except (pynvml.NVMLError, AttributeError):
                    pass

                gpus.append(
                    GpuInfo(
                        index=i,
                        name=name,
                        total_vram_mb=total_vram_mb,
                        total_vram_gb=total_vram_mb / 1024,
                        driver_version=driver_version,
                        cuda_version=cuda_version,
                        nvlink_enabled=nvlink_enabled,
                        nvlink_version=nvlink_version,
                        nvlink_peers=nvlink_peers,  # Will be filled in second pass
                        pci_bus_id=pci_bus_id,
                        numa_node=numa_node,
                    )
                )

            # Second pass: detect NVLink peer connections
            for i, gpu in enumerate(gpus):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                # Get all NVLink links for this GPU
                try:
                    for link in range(pynvml.NVML_NVLINK_MAX_LINKS):  # Usually 18 links max
                        try:
                            # Get the peer device for this link
                            peer_info = pynvml.nvmlDeviceGetNvLinkRemotePciInfo(handle, link)
                            if peer_info:
                                peer_bus_id = peer_info.busId.decode("utf-8") if isinstance(peer_info.busId, bytes) else peer_info.busId

                                # Find peer GPU by bus ID
                                for peer_gpu in gpus:
                                    if peer_gpu.pci_bus_id == peer_bus_id and peer_gpu.index != i:
                                        if peer_gpu.index not in gpu.nvlink_peers:
                                            gpu.nvlink_peers.append(peer_gpu.index)
                                        break
                        except (pynvml.NVMLError, AttributeError):
                            # Link not active or not supported
                            continue

                except (pynvml.NVMLError, AttributeError):
                    pass

            pynvml.nvmlShutdown()

        except ImportError:
            logger.debug("pynvml not available")
        except Exception as e:
            logger.warning(f"Error detecting GPUs with pynvml: {e}")

        # Fallback: try nvidia-smi (limited topology info)
        if not gpus:
            try:
                # Get basic GPU info
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,cuda_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    for i, line in enumerate(result.stdout.splitlines()):
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 2:
                            name = parts[0]
                            # Parse memory like "32768 MiB"
                            mem_str = parts[1]
                            mem_mb = int(re.sub(r'[^\d]', '', mem_str))
                            driver = parts[2] if len(parts) > 2 else "unknown"
                            cuda = parts[3] if len(parts) > 3 else "unknown"

                            gpus.append(
                                GpuInfo(
                                    index=i,
                                    name=name,
                                    total_vram_mb=mem_mb,
                                    total_vram_gb=mem_mb / 1024,
                                    driver_version=driver,
                                    cuda_version=cuda,
                                )
                            )

                # Try to get NVLink info via nvidia-smi
                try:
                    nvlink_result = subprocess.run(
                        ["nvidia-smi", "nvlink", "--status"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if nvlink_result.returncode == 0 and "NVLink is enabled" in nvlink_result.stdout:
                        # Parse NVLink topology from output
                        # This is simplified - full parsing would be more complex
                        for i, gpu in enumerate(gpus):
                            gpu.nvlink_enabled = True
                            # Try to determine NVLink version from GPU name
                            if "A100" in gpu.name:
                                gpu.nvlink_version = "3.0"
                            elif "H100" in gpu.name:
                                gpu.nvlink_version = "4.0"
                            elif "V100" in gpu.name:
                                gpu.nvlink_version = "2.0"
                            elif "P100" in gpu.name:
                                gpu.nvlink_version = "1.0"

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return gpus

    def _detect_network(self) -> Optional[NetworkInfo]:
        """Detect network interfaces and capabilities.

        Returns:
            NetworkInfo with interface details, or None if detection fails
        """
        interfaces = []

        # Try to read from /sys/class/net
        net_path = Path("/sys/class/net")
        if net_path.exists():
            for iface_dir in net_path.iterdir():
                if not iface_dir.is_dir():
                    continue

                name = iface_dir.name
                iface = self._parse_network_interface(name, iface_dir)
                if iface:
                    interfaces.append(iface)

        # Fallback to ip command if /sys failed
        if not interfaces:
            interfaces = self._detect_network_ip()

        if not interfaces:
            logger.debug("Could not detect network interfaces")
            return None

        return NetworkInfo(interfaces=interfaces)

    def _parse_network_interface(self, name: str, iface_dir: Path) -> Optional[NetworkInterface]:
        """Parse a single network interface from /sys/class/net.

        Args:
            name: Interface name
            iface_dir: Path to interface directory

        Returns:
            NetworkInterface or None
        """
        # Check if interface is up
        operstate_file = iface_dir / "operstate"
        try:
            operstate = operstate_file.read_text().strip() if operstate_file.exists() else "unknown"
            if operstate == "down":
                return None
        except OSError:
            pass

        # Check for loopback
        if name == "lo":
            return NetworkInterface(name=name, is_loopback=True)

        # Check for virtual interfaces
        is_virtual = any(prefix in name for prefix in [
            "veth", "docker", "br-", "virbr", "tun", "tap",
            "vnet", "kube", "flannel", "cali", "cilium",
        ])

        # Check for wireless
        is_wireless = (iface_dir / "wireless").exists()

        # Get speed
        speed_mbps = None
        speed_file = iface_dir / "speed"
        if speed_file.exists():
            try:
                speed_str = speed_file.read_text().strip()
                if speed_str != "-1":  # -1 means unknown/unplugged
                    speed_mbps = int(speed_str) if speed_str.isdigit() else None
            except (OSError, ValueError):
                pass

        # Get MAC address
        mac_address = None
        address_file = iface_dir / "address"
        if address_file.exists():
            try:
                mac_address = address_file.read_text().strip()
            except OSError:
                pass

        # Get driver info
        driver = None
        driver_dir = iface_dir / "device" / "driver"
        if driver_dir.exists():
            try:
                driver = driver_dir.resolve().name
            except OSError:
                pass

        # Get IP addresses
        ipv4_addresses = []
        ipv6_addresses = []

        # Try to get addresses from /proc/net/route (IPv4)
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2 and parts[0] == name:
                        # Convert hex to IP
                        hex_ip = parts[1]
                        if hex_ip != "00000000":
                            try:
                                ip_bytes = bytes.fromhex(hex_ip)[::-1]
                                ipv4 = ".".join(str(b) for b in ip_bytes)
                                ipv4_addresses.append(ipv4)
                            except ValueError:
                                pass
        except OSError:
            pass

        # Get statistics
        rx_bytes = None
        tx_bytes = None
        stats_file = iface_dir / "statistics" / "rx_bytes"
        if stats_file.exists():
            try:
                rx_bytes = int(stats_file.read_text().strip())
            except (OSError, ValueError):
                pass

        tx_stats_file = iface_dir / "statistics" / "tx_bytes"
        if tx_stats_file.exists():
            try:
                tx_bytes = int(tx_stats_file.read_text().strip())
            except (OSError, ValueError):
                pass

        return NetworkInterface(
            name=name,
            is_virtual=is_virtual,
            is_wireless=is_wireless,
            speed_mbps=speed_mbps,
            mac_address=mac_address,
            ipv4_addresses=ipv4_addresses,
            ipv6_addresses=ipv6_addresses,
            driver=driver,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
        )

    def _detect_network_ip(self) -> List[NetworkInterface]:
        """Fallback network detection using ip command.

        Returns:
            List of NetworkInterface
        """
        interfaces = []

        try:
            result = subprocess.run(
                ["ip", "-o", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return interfaces

            # Parse ip output
            # Format: 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue

                # Index and name
                name = parts[1].rstrip(":")

                # Skip loopback
                if name == "lo":
                    continue

                # Check flags
                flags_str = parts[2]
                is_up = "UP" in flags_str
                if not is_up:
                    continue

                # Classify interface
                is_virtual = any(prefix in name for prefix in [
                    "veth", "docker", "br-", "virbr", "tun", "tap",
                    "vnet", "kube", "flannel", "cali", "cilium",
                ])

                # Parse IPs from remaining parts
                ipv4_addresses = []
                ipv6_addresses = []
                for part in parts[3:]:
                    if part.startswith("inet"):
                        if part == "inet6":
                            continue
                        # IPv4: inet 192.168.1.100/24 ...
                        try:
                            idx = parts.index(part)
                            if idx + 1 < len(parts):
                                ip_cidr = parts[idx + 1]
                                ipv4_addresses.append(ip_cidr.split("/")[0])
                        except (ValueError, IndexError):
                            pass

                # Try to get speed via ethtool
                speed_mbps = None
                try:
                    speed_result = subprocess.run(
                        ["ethtool", name],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    for line in speed_result.stdout.splitlines():
                        if "Speed:" in line:
                            # Speed: 1000Mb/s
                            match = re.search(r'Speed:\s*(\d+)\s*Mb/s', line)
                            if match:
                                speed_mbps = int(match.group(1))
                                break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

                interfaces.append(NetworkInterface(
                    name=name,
                    is_virtual=is_virtual,
                    speed_mbps=speed_mbps,
                    ipv4_addresses=ipv4_addresses,
                ))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return interfaces

    def get_available_memory_mb(self) -> int:
        """Get available system memory for containers."""
        profile = self.detect()
        reserve_mb = int(profile.memory.total_mb * self.reserve_percent)
        return profile.memory.total_mb - reserve_mb

    def get_available_cpu_cores(self) -> int:
        """Get available CPU cores for containers."""
        profile = self.detect()
        reserve = int(profile.cpu.total_threads * self.reserve_percent)
        return profile.cpu.total_threads - reserve


class ResourceAllocator:
    """Generates docker-compose resource limits based on hardware profile."""

    # Service categories with their resource requirements
    SERVICE_CATEGORIES = {
        # Heavy GPU services - need lots of VRAM
        "gpu_heavy": {
            "services": [
                "ffmpeg-whisper", "media-video", "media-audio",
                "hi-rag-gateway-v2-gpu", "hi-rag-gateway-gpu",
            ],
            "memory_factor": 0.15,  # Up to 15% of RAM per service
            "cpu_factor": 0.10,     # Up to 10% of CPU threads
            "min_memory_gb": 4,
            "max_memory_gb": 64,
            "min_cpu": 1.0,
            "max_cpu": 16.0,
        },
        # Agent services - moderate resources
        "agent": {
            "services": ["agent-zero", "archon", "botz-gateway", "gateway-agent"],
            "memory_factor": 0.05,
            "cpu_factor": 0.05,
            "min_memory_gb": 1,
            "max_memory_gb": 16,
            "min_cpu": 0.5,
            "max_cpu": 4.0,
        },
        # API services - lightweight
        "api": {
            "services": [
                "hi-rag-gateway-v2", "extract-worker", "langextract",
                "presign", "render-webhook", "retrieval-eval",
            ],
            "memory_factor": 0.02,
            "cpu_factor": 0.03,
            "min_memory_gb": 512,
            "max_memory_gb": 4,
            "min_cpu": 0.25,
            "max_cpu": 2.0,
        },
        # Worker services - lightweight background tasks
        "worker": {
            "services": [
                "deepresearch", "supaserch", "publisher-discord",
                "mesh-agent", "nats-echo-req", "nats-echo-res",
                "publisher", "analysis-echo", "graph-linker",
                "comfy-watcher", "grayjay-plugin-host",
            ],
            "memory_factor": 0.015,
            "cpu_factor": 0.02,
            "min_memory_gb": 256,
            "max_memory_gb": 2,
            "min_cpu": 0.1,
            "max_cpu": 1.0,
        },
        # Media ingestion - needs I/O and some CPU
        "media": {
            "services": ["pmoves-yt", "pdf-ingest", "jellyfin-bridge",
                        "invidious-companion-proxy"],
            "memory_factor": 0.03,
            "cpu_factor": 0.04,
            "min_memory_gb": 512,
            "max_memory_gb": 8,
            "min_cpu": 0.5,
            "max_cpu": 2.0,
        },
        # Voice services
        "voice": {
            "services": ["flute-gateway"],
            "memory_factor": 0.02,
            "cpu_factor": 0.03,
            "min_memory_gb": 512,
            "max_memory_gb": 4,
            "min_cpu": 0.25,
            "max_cpu": 2.0,
        },
        # Economy simulation
        "economy": {
            "services": ["tokenism-simulator"],
            "memory_factor": 0.03,
            "cpu_factor": 0.04,
            "min_memory_gb": 512,
            "max_memory_gb": 8,
            "min_cpu": 0.5,
            "max_cpu": 2.0,
        },
        # Monitoring and sync
        "monitoring": {
            "services": ["channel-monitor", "notebook-sync"],
            "memory_factor": 0.01,
            "cpu_factor": 0.02,
            "min_memory_gb": 128,
            "max_memory_gb": 1,
            "min_cpu": 0.1,
            "max_cpu": 1.0,
        },
        # UI services
        "ui": {
            "services": ["tokenism-ui"],
            "memory_factor": 0.01,
            "cpu_factor": 0.02,
            "min_memory_gb": 128,
            "max_memory_gb": 1,
            "min_cpu": 0.1,
            "max_cpu": 1.0,
        },
        # Runner control
        "runner": {
            "services": ["github-runner-ctl"],
            "memory_factor": 0.01,
            "cpu_factor": 0.02,
            "min_memory_gb": 256,
            "max_memory_gb": 2,
            "min_cpu": 0.1,
            "max_cpu": 1.0,
        },
    }

    def __init__(self, detector: Optional[HardwareDetector] = None):
        """Initialize resource allocator.

        Args:
            detector: HardwareDetector instance. If None, creates a new one.
        """
        self.detector = detector or HardwareDetector()

    def generate_resource_limits(self) -> Dict[str, Dict]:
        """Generate docker-compose resource limits for all services.

        Returns:
            Dict mapping service names to resource limit dicts.
        """
        profile = self.detector.detect()
        limits: Dict[str, Dict] = {}

        for category, config in self.SERVICE_CATEGORIES.items():
            for service in config["services"]:
                limits[service] = self._calculate_service_limits(
                    service, profile, config
                )

        return limits

    def _calculate_service_limits(
        self,
        service: str,
        profile: HardwareProfile,
        config: Dict,
    ) -> Dict:
        """Calculate resource limits for a specific service."""
        # Calculate memory limit
        memory_factor = config["memory_factor"]
        max_memory_mb = int(profile.memory.total_mb * memory_factor)

        # Clamp to min/max
        min_memory_mb = config["min_memory_gb"] * 1024
        max_memory_clamp_mb = config["max_memory_gb"] * 1024

        limit_memory_mb = max(min_memory_mb, min(max_memory_mb, max_memory_clamp_mb))
        reserve_memory_mb = max(min_memory_mb // 4, limit_memory_mb // 4)

        # Calculate CPU limit
        cpu_factor = config["cpu_factor"]
        max_cpu = profile.cpu.total_threads * cpu_factor

        # Clamp to min/max
        min_cpu = config["min_cpu"]
        max_cpu_clamp = config["max_cpu"]

        limit_cpu = max(min_cpu, min(max_cpu, max_cpu_clamp))
        reserve_cpu = max(0.1, limit_cpu / 4)

        # Format for docker-compose
        return {
            "limits": {
                "memory": f"{limit_memory_mb // 1024}G" if limit_memory_mb >= 1024
                else f"{limit_memory_mb}M",
                "cpus": f"{limit_cpu:.1f}",
            },
            "reservations": {
                "memory": f"{reserve_memory_mb // 1024}G" if reserve_memory_mb >= 1024
                else f"{reserve_memory_mb}M",
                "cpus": f"{reserve_cpu:.2f}",
            },
        }

    def generate_compose_override(
        self,
        output_path: Optional[Path] = None,
    ) -> str:
        """Generate docker-compose override file with dynamic resource limits.

        Args:
            output_path: Optional path to write the override file.

        Returns:
            YAML content of the override file.
        """
        limits = self.generate_resource_limits()
        profile = self.detector.detect()

        lines = [
            "# Auto-generated resource limits based on detected hardware",
            f"# Hardware: {profile.cpu.model_name}",
            f"# CPU: {profile.cpu.total_threads} threads, RAM: {profile.memory.total_gb:.1f}GB",
            f"# GPU: {len(profile.gpus)}x {profile.gpus[0].name if profile.gpus else 'None'} ({profile.total_gpu_vram_gb:.1f}GB VRAM)",
            "# Generated by: pmoves/services/resource-detector",
            "# To regenerate: python -m pmoves.services.resource_detector.generate",
            "",
            "services:",
        ]

        for service, resources in sorted(limits.items()):
            lines.append(f"  {service}:")
            lines.append("    deploy:")
            lines.append("      resources:")
            lines.append(f"        limits:")
            lines.append(f"          memory: {resources['limits']['memory']}")
            lines.append(f"          cpus: '{resources['limits']['cpus']}'")
            lines.append(f"        reservations:")
            lines.append(f"          memory: {resources['reservations']['memory']}")
            lines.append(f"          cpus: '{resources['reservations']['cpus']}'")
            lines.append("")

        content = "\n".join(lines)

        if output_path:
            output_path.write_text(content)
            logger.info(f"Wrote resource override to {output_path}")

        return content


def get_hardware_profile() -> HardwareProfile:
    """Get detected hardware profile (convenience function)."""
    return HardwareDetector().detect()


def generate_resource_limits() -> Dict[str, Dict]:
    """Generate resource limits for all services (convenience function)."""
    return ResourceAllocator().generate_resource_limits()
