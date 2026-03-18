"""
Cast Device Manager

Device discovery, caching, and health monitoring for Google Cast devices.
"""

import asyncio
import time
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class CastDevice:
    """Google Cast device information."""

    name: str
    ip: str
    address: str
    last_seen: float
    online: bool = True


class CastDeviceManager:
    """Google Cast device discovery and management."""

    def __init__(
        self,
        discovery_interval: float = 300,
        on_discovery: Optional[Callable] = None,
    ):
        """
        Initialize device manager.

        Args:
            discovery_interval: Seconds between device discoveries (default: 5 min)
            on_discovery: Optional async callback(devices, new_names, lost_names, forced)
        """
        self.discovery_interval = discovery_interval
        self.devices: dict[str, CastDevice] = {}
        self._last_discovery: Optional[float] = None
        self._previous_names: set[str] = set()
        self._on_discovery = on_discovery

    async def discover(self, force: bool = False) -> list[CastDevice]:
        """
        Discover Cast devices on LAN.

        Args:
            force: Force rediscovery even if cache is fresh

        Returns:
            List of discovered devices
        """
        current_time = time.time()

        # Use cache if fresh
        if not force and self._last_discovery:
            if (current_time - self._last_discovery) < self.discovery_interval:
                return list(self.devices.values())

        try:
            # Run catt scan
            proc = await asyncio.create_subprocess_exec(
                "catt", "scan",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return []

            # Parse output
            # Format: "Device Name - 192.168.1.x:port"
            discovered = {}
            for line in stdout.decode().strip().split("\n"):
                if " - " in line and ":" in line:
                    parts = line.split(" - ")
                    if len(parts) == 2:
                        name = parts[0].strip()
                        addr_port = parts[1].strip()
                        ip = addr_port.split(":")[0] if ":" in addr_port else addr_port

                        device = CastDevice(
                            name=name,
                            ip=ip,
                            address=addr_port,
                            last_seen=current_time,
                        )
                        discovered[name] = device

            # Update device cache
            self.devices = discovered
            self._last_discovery = current_time

            # Compute diff and invoke callback
            current_names = set(discovered.keys())
            new_names = current_names - self._previous_names
            lost_names = self._previous_names - current_names
            self._previous_names = current_names

            if self._on_discovery:
                try:
                    await self._on_discovery(
                        list(self.devices.values()),
                        new_names,
                        lost_names,
                        force,
                    )
                except Exception as e:
                    print(f"Discovery callback error: {e}")

            return list(self.devices.values())

        except FileNotFoundError:
            # catt not installed
            return []
        except Exception as e:
            print(f"Discovery error: {e}")
            return []

    def get_device(self, name: str) -> Optional[CastDevice]:
        """
        Get device by name.

        Args:
            name: Device name

        Returns:
            Device if found, None otherwise
        """
        return self.devices.get(name)

    def list_devices(self) -> list[CastDevice]:
        """
        List all discovered devices.

        Returns:
            List of devices
        """
        return list(self.devices.values())

    async def cast_audio(
        self,
        audio_path: str,
        device: Optional[str] = None,
    ) -> dict:
        """
        Cast audio file to device.

        Args:
            audio_path: Path to audio file
            device: Device name (None for default)

        Returns:
            Result dict with success/error info
        """
        try:
            cmd = ["catt", "cast", audio_path]
            if device:
                cmd.extend(["-d", device])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                device_name = device or "default device"
                return {
                    "success": True,
                    "device": device_name,
                    "message": f"Casted to {device_name}",
                }
            else:
                error_msg = stderr.decode().strip() or "Unknown error"
                return {
                    "success": False,
                    "device": device,
                    "error": error_msg,
                }

        except Exception as e:
            return {
                "success": False,
                "device": device,
                "error": str(e),
            }

    async def stop_cast(self, device: Optional[str] = None) -> dict:
        """
        Stop playback on device.

        Args:
            device: Device name (None for default)

        Returns:
            Result dict
        """
        try:
            cmd = ["catt", "stop"]
            if device:
                cmd.extend(["-d", device])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                device_name = device or "default device"
                return {
                    "success": True,
                    "device": device_name,
                    "message": f"Stopped playback on {device_name}",
                }
            else:
                error_msg = stderr.decode().strip() or "Unknown error"
                return {
                    "success": False,
                    "device": device,
                    "error": error_msg,
                }

        except Exception as e:
            return {
                "success": False,
                "device": device,
                "error": str(e),
            }
