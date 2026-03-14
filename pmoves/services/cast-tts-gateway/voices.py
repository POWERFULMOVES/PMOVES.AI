"""
Voice Profile Management

Manage voice profiles for devices and groups with context-aware switching.
"""

import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class VoiceProfile:
    """Voice profile for device/group."""

    name: str
    voice: str = "default"
    speed: float = 1.0
    pitch: float = 1.0
    device: Optional[str] = None
    group: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    description: str = ""
    context_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return {
            "name": self.name,
            "voice": self.voice,
            "speed": self.speed,
            "pitch": self.pitch,
            "device": self.device,
            "group": self.group,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
            "description": self.description,
            "context_tags": self.context_tags,
        }


class VoiceProfileManager:
    """Manage voice profiles for devices and groups."""

    def __init__(self):
        """Initialize voice profile manager."""
        self.profiles: dict[str, VoiceProfile] = {}

        # Create default profile
        default_profile = VoiceProfile(
            name="default",
            voice="default",
            speed=1.0,
            pitch=1.0,
            description="Default voice profile",
        )
        self.profiles["default"] = default_profile

    def create_profile(
        self,
        name: str,
        voice: str = "default",
        speed: float = 1.0,
        pitch: float = 1.0,
        device: Optional[str] = None,
        group: Optional[str] = None,
        description: str = "",
        context_tags: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a new voice profile.

        Args:
            name: Profile name
            voice: Voice identifier
            speed: Speech speed multiplier
            pitch: Pitch multiplier
            device: Device name (optional)
            group: Group name (optional)
            description: Profile description
            context_tags: Tags for context-aware switching

        Returns:
            Result dict with success/error info
        """
        if not name:
            return {
                "success": False,
                "error": "Profile name is required",
            }

        if name in self.profiles:
            return {
                "success": False,
                "error": f"Profile '{name}' already exists",
            }

        if speed < 0.5 or speed > 2.0:
            return {
                "success": False,
                "error": "Speed must be between 0.5 and 2.0",
            }

        if pitch < 0.5 or pitch > 2.0:
            return {
                "success": False,
                "error": "Pitch must be between 0.5 and 2.0",
            }

        profile = VoiceProfile(
            name=name,
            voice=voice,
            speed=speed,
            pitch=pitch,
            device=device,
            group=group,
            description=description,
            context_tags=context_tags or [],
        )
        self.profiles[name] = profile

        return {
            "success": True,
            "profile": profile.to_dict(),
            "message": f"Created voice profile '{name}'",
        }

    def get_profile(self, name: str) -> Optional[VoiceProfile]:
        """
        Get profile by name.

        Args:
            name: Profile name

        Returns:
            Profile if found, None otherwise
        """
        return self.profiles.get(name)

    def list_profiles(self) -> list[VoiceProfile]:
        """
        List all profiles.

        Returns:
            List of profiles
        """
        return list(self.profiles.values())

    def update_profile(
        self,
        name: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        description: Optional[str] = None,
        context_tags: Optional[list[str]] = None,
    ) -> dict:
        """
        Update an existing profile.

        Args:
            name: Profile name
            voice: New voice (optional)
            speed: New speed (optional)
            pitch: New pitch (optional)
            description: New description (optional)
            context_tags: New context tags (optional)

        Returns:
            Result dict
        """
        profile = self.profiles.get(name)
        if not profile:
            return {
                "success": False,
                "error": f"Profile '{name}' not found",
            }

        if voice is not None:
            profile.voice = voice

        if speed is not None:
            if speed < 0.5 or speed > 2.0:
                return {
                    "success": False,
                    "error": "Speed must be between 0.5 and 2.0",
                }
            profile.speed = speed

        if pitch is not None:
            if pitch < 0.5 or pitch > 2.0:
                return {
                    "success": False,
                    "error": "Pitch must be between 0.5 and 2.0",
                }
            profile.pitch = pitch

        if description is not None:
            profile.description = description

        if context_tags is not None:
            profile.context_tags = context_tags

        return {
            "success": True,
            "profile": profile.to_dict(),
            "message": f"Updated profile '{name}'",
        }

    def delete_profile(self, name: str) -> dict:
        """
        Delete a profile.

        Args:
            name: Profile name

        Returns:
            Result dict
        """
        if name not in self.profiles:
            return {
                "success": False,
                "error": f"Profile '{name}' not found",
            }

        if name == "default":
            return {
                "success": False,
                "error": "Cannot delete default profile",
            }

        del self.profiles[name]
        return {
            "success": True,
            "message": f"Deleted profile '{name}'",
        }

    def find_profile_for_device(self, device: str) -> Optional[VoiceProfile]:
        """
        Find best profile for a device.

        Args:
            device: Device name

        Returns:
            Best matching profile or default
        """
        # Look for device-specific profile
        for profile in self.profiles.values():
            if profile.device == device:
                return profile

        # Return default
        return self.profiles.get("default")

    def find_profile_for_group(self, group: str) -> Optional[VoiceProfile]:
        """
        Find best profile for a group.

        Args:
            group: Group name

        Returns:
            Best matching profile or default
        """
        # Look for group-specific profile
        for profile in self.profiles.values():
            if profile.group == group:
                return profile

        # Return default
        return self.profiles.get("default")

    def find_profile_by_context(self, context: str) -> Optional[VoiceProfile]:
        """
        Find profile by context tag.

        Args:
            context: Context tag

        Returns:
            First matching profile or None
        """
        for profile in self.profiles.values():
            if context in profile.context_tags:
                return profile

        return None
