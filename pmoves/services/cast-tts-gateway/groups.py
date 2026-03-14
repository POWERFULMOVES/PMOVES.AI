"""
Cast Device Groups

Device grouping for multi-room audio support.
"""

import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class CastDeviceGroup:
    """Google Cast device group."""

    name: str
    devices: list[str]
    created_at: float = field(default_factory=time.time)
    description: str = ""

    def to_dict(self) -> dict:
        """Convert group to dictionary."""
        return {
            "name": self.name,
            "devices": self.devices,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
            "description": self.description,
            "device_count": len(self.devices),
        }


class CastGroupManager:
    """Manage Cast device groups."""

    def __init__(self):
        """Initialize group manager."""
        self.groups: dict[str, CastDeviceGroup] = {}

    def create_group(
        self,
        name: str,
        devices: list[str],
        description: str = "",
    ) -> dict:
        """
        Create a new device group.

        Args:
            name: Group name
            devices: List of device names
            description: Optional description

        Returns:
            Result dict with success/error info
        """
        if not name:
            return {
                "success": False,
                "error": "Group name is required",
            }

        if not devices:
            return {
                "success": False,
                "error": "At least one device is required",
            }

        if name in self.groups:
            return {
                "success": False,
                "error": f"Group '{name}' already exists",
            }

        group = CastDeviceGroup(
            name=name,
            devices=devices,
            description=description,
        )
        self.groups[name] = group

        return {
            "success": True,
            "group": group.to_dict(),
            "message": f"Created group '{name}' with {len(devices)} device(s)",
        }

    def get_group(self, name: str) -> Optional[CastDeviceGroup]:
        """
        Get group by name.

        Args:
            name: Group name

        Returns:
            Group if found, None otherwise
        """
        return self.groups.get(name)

    def list_groups(self) -> list[CastDeviceGroup]:
        """
        List all groups.

        Returns:
            List of groups
        """
        return list(self.groups.values())

    def delete_group(self, name: str) -> dict:
        """
        Delete a group.

        Args:
            name: Group name

        Returns:
            Result dict
        """
        if name not in self.groups:
            return {
                "success": False,
                "error": f"Group '{name}' not found",
            }

        del self.groups[name]
        return {
            "success": True,
            "message": f"Deleted group '{name}'",
        }

    def update_group(
        self,
        name: str,
        devices: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        Update an existing group.

        Args:
            name: Group name
            devices: New device list (optional)
            description: New description (optional)

        Returns:
            Result dict
        """
        group = self.groups.get(name)
        if not group:
            return {
                "success": False,
                "error": f"Group '{name}' not found",
            }

        if devices is not None:
            if not devices:
                return {
                    "success": False,
                    "error": "At least one device is required",
                }
            group.devices = devices

        if description is not None:
            group.description = description

        return {
            "success": True,
            "group": group.to_dict(),
            "message": f"Updated group '{name}'",
        }

    def validate_group_devices(self, name: str, available_devices: list[str]) -> dict:
        """
        Validate that all devices in a group are available.

        Args:
            name: Group name
            available_devices: List of available device names

        Returns:
            Validation result with missing devices
        """
        group = self.groups.get(name)
        if not group:
            return {
                "valid": False,
                "error": f"Group '{name}' not found",
            }

        available_set = set(available_devices)
        missing = [d for d in group.devices if d not in available_set]

        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "available": len(group.devices) - len(missing),
            "total": len(group.devices),
        }
