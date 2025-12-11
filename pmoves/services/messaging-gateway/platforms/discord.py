"""
Discord platform integration with interactive buttons.
Uses Discord interactions API for button components.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

logger = logging.getLogger("discord_platform")


class DiscordPlatform:
    """Handle Discord webhook and interactions."""

    def __init__(self, webhook_url: str, application_id: str, public_key: str):
        self.webhook_url = webhook_url
        self.application_id = application_id
        self.public_key = public_key
        self._verify_key: Optional[VerifyKey] = None
        if public_key:
            try:
                self._verify_key = VerifyKey(bytes.fromhex(public_key))
            except Exception:
                logger.exception("Failed to initialize Discord verify key")
        self._client: Optional[httpx.AsyncClient] = None

    def is_configured(self) -> bool:
        """Check if Discord is properly configured."""
        return bool(self.webhook_url)

    async def initialize(self):
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(timeout=15)

    def verify_signature(self, signature: str, timestamp: str, body: bytes) -> bool:
        """
        Verify Discord interaction signature using Ed25519.

        Discord requires signature verification for all interaction endpoints.
        See: https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization

        Args:
            signature: X-Signature-Ed25519 header value
            timestamp: X-Signature-Timestamp header value
            body: Raw request body bytes

        Returns:
            True if signature is valid, False otherwise
        """
        if not self._verify_key:
            logger.error("Discord signature verification failed: no verify key configured")
            return False

        try:
            message = timestamp.encode() + body
            self._verify_key.verify(message, bytes.fromhex(signature))
            return True
        except BadSignatureError:
            logger.warning("Discord signature verification failed: invalid signature")
            return False
        except Exception:
            logger.exception("Discord signature verification error")
            return False

    async def send(
        self,
        content: str,
        embeds: Optional[List[Dict]] = None,
        buttons: Optional[List[Dict]] = None,
    ) -> bool:
        """
        Send message to Discord via webhook.

        Args:
            content: Message text
            embeds: Discord embeds (optional)
            buttons: Button definitions (optional)
                Format: [{"id": "btn_id", "label": "Click me", "style": "primary"}]
        """
        if not self.is_configured():
            logger.warning("Discord not configured, skipping send")
            return False

        payload = {"username": "PMOVES Gateway"}

        if content:
            payload["content"] = content

        if embeds:
            payload["embeds"] = embeds

        # Add button components if provided
        if buttons:
            components = self._build_button_components(buttons)
            payload["components"] = components

        try:
            r = await self._client.post(self.webhook_url, json=payload)
            if r.status_code in (200, 204):
                logger.info("Discord message sent successfully")
                return True
            else:
                logger.warning(f"Discord send failed: {r.status_code} - {r.text[:200]}")
                return False
        except Exception:
            logger.exception("Discord send exception")
            return False

    def _build_button_components(self, buttons: List[Dict]) -> List[Dict]:
        """
        Build Discord button components from platform-agnostic button definitions.

        Discord button styles:
        - 1: primary (blurple)
        - 2: secondary (gray)
        - 3: success (green)
        - 4: danger (red)
        - 5: link (external URL)
        """
        style_map = {
            "primary": 1,
            "secondary": 2,
            "success": 3,
            "danger": 4,
            "link": 5,
        }

        button_row = []
        for btn in buttons[:5]:  # Discord max 5 buttons per row
            button_row.append({
                "type": 2,  # Button component type
                "style": style_map.get(btn.get("style", "secondary"), 2),
                "label": btn.get("label", "Button"),
                "custom_id": btn.get("id", "unknown"),
            })

        return [{"type": 1, "components": button_row}]  # Action row

    async def handle_interaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Discord interaction callbacks (button clicks).

        Discord sends interaction payloads when users click buttons.
        We need to respond with type 4 (channel message with source).
        """
        interaction_type = payload.get("type")
        interaction_data = payload.get("data", {})
        custom_id = interaction_data.get("custom_id")

        logger.info(f"Discord interaction received: {custom_id}")

        # Parse custom_id to determine action
        # Format: "approve_<item_id>" or "reject_<item_id>"
        if custom_id and "_" in custom_id:
            action, item_id = custom_id.split("_", 1)

            if action == "approve":
                # TODO: Call approval RPC function
                response_content = f"✅ Approved item {item_id}"
            elif action == "reject":
                # TODO: Call rejection RPC function
                response_content = f"❌ Rejected item {item_id}"
            else:
                response_content = f"Unknown action: {action}"
        else:
            response_content = "Button clicked"

        # Respond to interaction (required by Discord)
        return {
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {
                "content": response_content,
                "flags": 64,  # Ephemeral (only visible to user who clicked)
            }
        }
