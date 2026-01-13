"""
WhatsApp Business API integration (stub).
Requires WhatsApp Business Account and API credentials.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("whatsapp_platform")


class WhatsAppPlatform:
    """Handle WhatsApp Business API interactions (stub implementation)."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client: Optional[httpx.AsyncClient] = None

    def is_configured(self) -> bool:
        """Check if WhatsApp is properly configured."""
        return bool(self.access_token)

    async def initialize(self):
        """Initialize HTTP client."""
        if not self.is_configured():
            return

        self._client = httpx.AsyncClient(timeout=15)
        logger.info("WhatsApp platform initialized (stub)")

    async def send(
        self,
        content: str,
        buttons: Optional[List[Dict]] = None,
        phone_number: Optional[str] = None,
    ) -> bool:
        """
        Send message to WhatsApp (stub implementation).

        In production, this would use the WhatsApp Business API:
        https://developers.facebook.com/docs/whatsapp/cloud-api

        Args:
            content: Message text
            buttons: Button definitions (optional)
            phone_number: Target phone number (optional)
        """
        if not self.is_configured():
            logger.warning("WhatsApp not configured, skipping send")
            return False

        logger.info(f"WhatsApp send (stub): {content[:50]}...")

        # TODO: Implement actual WhatsApp Business API integration
        # This requires:
        # 1. WhatsApp Business Account
        # 2. Phone Number ID
        # 3. Access Token
        # 4. Message templates (required by WhatsApp)

        # Example API call (commented out - requires real credentials):
        # payload = {
        #     "messaging_product": "whatsapp",
        #     "to": phone_number,
        #     "type": "text",
        #     "text": {"body": content}
        # }
        #
        # if buttons:
        #     # WhatsApp uses "interactive" type with "button" action
        #     payload["type"] = "interactive"
        #     payload["interactive"] = {
        #         "type": "button",
        #         "body": {"text": content},
        #         "action": {
        #             "buttons": [
        #                 {"type": "reply", "reply": {"id": btn["id"], "title": btn["label"]}}
        #                 for btn in buttons[:3]  # WhatsApp max 3 buttons
        #             ]
        #         }
        #     }
        #
        # r = await self._client.post(
        #     f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        #     headers={"Authorization": f"Bearer {self.access_token}"},
        #     json=payload,
        # )

        return True  # Stub returns success

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle WhatsApp webhook events (stub).

        WhatsApp sends webhook events for:
        - Message status updates
        - User responses
        - Button clicks
        """
        logger.info(f"WhatsApp webhook (stub): {payload}")

        # TODO: Implement webhook handling
        # Example structure:
        # {
        #     "object": "whatsapp_business_account",
        #     "entry": [{
        #         "changes": [{
        #             "value": {
        #                 "messages": [{
        #                     "from": "1234567890",
        #                     "type": "button",
        #                     "button": {"text": "approve_123"}
        #                 }]
        #             }
        #         }]
        #     }]
        # }

        return {"ok": True}
