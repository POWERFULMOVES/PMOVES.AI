"""Platform integrations for messaging gateway."""

from .discord import DiscordPlatform
from .telegram import TelegramPlatform
from .whatsapp import WhatsAppPlatform

__all__ = ["DiscordPlatform", "TelegramPlatform", "WhatsAppPlatform"]
