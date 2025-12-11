"""
Telegram platform integration with inline keyboards.
Uses Telegram Bot API for sending messages and handling callbacks.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("telegram_platform")


class TelegramPlatform:
    """Handle Telegram bot interactions."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self._client: Optional[httpx.AsyncClient] = None
        self._admin_chat_ids: List[str] = []

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token)

    async def initialize(self):
        """Initialize HTTP client and get bot info."""
        if not self.is_configured():
            return

        self._client = httpx.AsyncClient(timeout=15)

        # Get bot info to verify token
        try:
            r = await self._client.get(
                f"https://api.telegram.org/bot{self.bot_token}/getMe"
            )
            if r.status_code == 200:
                bot_info = r.json()
                logger.info(f"Telegram bot initialized: {bot_info.get('result', {}).get('username')}")
            else:
                logger.warning(f"Failed to verify Telegram bot: {r.status_code}")
        except Exception as e:
            logger.error(f"Telegram initialization error: {e}")

    async def send(
        self,
        content: str,
        buttons: Optional[List[Dict]] = None,
        chat_id: Optional[str] = None,
    ) -> bool:
        """
        Send message to Telegram with optional inline keyboard.

        Args:
            content: Message text
            buttons: Button definitions (optional)
            chat_id: Target chat ID (if None, sends to all admin chats)
        """
        if not self.is_configured():
            logger.warning("Telegram not configured, skipping send")
            return False

        # Build inline keyboard if buttons provided
        reply_markup = None
        if buttons:
            reply_markup = self._build_inline_keyboard(buttons)

        payload = {
            "text": content,
            "parse_mode": "Markdown",
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        # Send to specified chat or all admin chats
        target_chats = [chat_id] if chat_id else self._admin_chat_ids

        if not target_chats:
            logger.warning("No target chat IDs configured for Telegram")
            return False

        if self._client is None:
            logger.error("Telegram client not initialized")
            return False

        success = False
        for chat in target_chats:
            try:
                payload["chat_id"] = chat
                r = await self._client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json=payload,
                )
                if r.status_code == 200:
                    logger.info(f"Telegram message sent to {chat}")
                    success = True
                else:
                    logger.warning(f"Telegram send failed for {chat}: {r.status_code} - {r.text[:200]}")
            except Exception as e:
                logger.error(f"Telegram send exception for {chat}: {e}")

        return success

    def _build_inline_keyboard(self, buttons: List[Dict]) -> Dict:
        """
        Build Telegram inline keyboard from platform-agnostic button definitions.

        Telegram inline keyboard format:
        {
            "inline_keyboard": [
                [{"text": "Button 1", "callback_data": "btn_1"}],
                [{"text": "Button 2", "callback_data": "btn_2"}]
            ]
        }
        """
        keyboard_rows = []

        # Group buttons into rows (max 2 buttons per row for better mobile UX)
        for i in range(0, len(buttons), 2):
            row = []
            for btn in buttons[i:i+2]:
                row.append({
                    "text": btn.get("label", "Button"),
                    "callback_data": btn.get("id", "unknown"),
                })
            keyboard_rows.append(row)

        return {"inline_keyboard": keyboard_rows}

    async def handle_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Telegram bot updates (commands, callbacks).

        Telegram sends updates for:
        - Messages (commands like /status)
        - Callback queries (button clicks)
        """
        # Handle callback query (button click)
        if "callback_query" in payload:
            callback = payload["callback_query"]
            callback_data = callback.get("data")
            chat_id = callback.get("message", {}).get("chat", {}).get("id")

            logger.info(f"Telegram callback received: {callback_data}")

            # Parse callback_data to determine action
            if callback_data and "_" in callback_data:
                action, item_id = callback_data.split("_", 1)

                if action == "approve":
                    response = f"✅ Approved item {item_id}"
                    # TODO: Call approval RPC function
                elif action == "reject":
                    response = f"❌ Rejected item {item_id}"
                    # TODO: Call rejection RPC function
                else:
                    response = f"Unknown action: {action}"
            else:
                response = "Button clicked"

            # Answer callback query (required by Telegram)
            if self._client is None:
                logger.error("Telegram client not initialized")
                return {"ok": False, "error": "client_not_initialized"}

            try:
                await self._client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback["id"],
                        "text": response,
                    }
                )
            except Exception as e:
                logger.exception(f"Failed to answer callback query: {e}")

            # Edit original message to show result
            if chat_id:
                message_id = callback.get("message", {}).get("message_id")
                try:
                    await self._client.post(
                        f"https://api.telegram.org/bot{self.bot_token}/editMessageText",
                        json={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "text": response,
                        }
                    )
                except Exception as e:
                    logger.exception(f"Failed to edit message: {e}")

            return {"ok": True}

        # Handle regular message (commands)
        elif "message" in payload:
            message = payload["message"]
            text = message.get("text", "")
            chat_id = message.get("chat", {}).get("id")

            if text == "/status":
                # Return current status
                status_text = "🤖 PMOVES Messaging Gateway\n\n✅ Active"
                await self.send(content=status_text, chat_id=str(chat_id))

            return {"ok": True}

        return {"ok": False, "error": "unknown_update_type"}
