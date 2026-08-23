from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from helpers.print_style import PrintStyle

try:
    from flaredantic import FlareConfig, FlareTunnel, ServeoConfig, ServeoTunnel
    _FLARE_CORE_AVAILABLE = True
except Exception:
    FlareConfig = None  # type: ignore[assignment]
    FlareTunnel = None  # type: ignore[assignment]
    ServeoConfig = None  # type: ignore[assignment]
    ServeoTunnel = None  # type: ignore[assignment]
    _FLARE_CORE_AVAILABLE = False

try:
    from flaredantic import MicrosoftConfig, MicrosoftTunnel
    _MICROSOFT_TUNNEL_AVAILABLE = True
except Exception:
    MicrosoftConfig = None  # type: ignore[assignment]
    MicrosoftTunnel = None  # type: ignore[assignment]
    _MICROSOFT_TUNNEL_AVAILABLE = False


class NotifyEvent(str, Enum):
    ERROR = "error"
    INFO = "info"


@dataclass
class NotifyData:
    event: NotifyEvent
    message: str
    data: Any = None


class _NoopNotifier:
    def subscribe(self, _callback: Callable[[NotifyData], None]) -> None:
        return None


try:
    from flaredantic import NotifyData as _FlareNotifyData
    from flaredantic import NotifyEvent as _FlareNotifyEvent
    from flaredantic import notifier as _flare_notifier

    NotifyData = _FlareNotifyData  # type: ignore[assignment]
    NotifyEvent = _FlareNotifyEvent  # type: ignore[assignment]
    notifier = _flare_notifier
except Exception:
    notifier = _NoopNotifier()


class TunnelManager:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.tunnel = None
        self.tunnel_url = None
        self.is_running = False
        self.provider = None
        self.notifications = deque(maxlen=50)
        self._subscribed = False

    def _on_notify(self, data: NotifyData):
        event_value = getattr(getattr(data, "event", None), "value", NotifyEvent.INFO.value)
        self.notifications.append(
            {
                "event": event_value,
                "message": getattr(data, "message", ""),
                "data": getattr(data, "data", None),
            }
        )

    def _ensure_subscribed(self):
        if not self._subscribed:
            notifier.subscribe(self._on_notify)
            self._subscribed = True

    def _notify_error(self, message: str) -> None:
        PrintStyle.error(message)
        self.notifications.append(
            {"event": NotifyEvent.ERROR.value, "message": message, "data": None}
        )

    def get_notifications(self):
        notifications = list(self.notifications)
        self.notifications.clear()
        return notifications

    def get_last_error(self):
        for n in reversed(list(self.notifications)):
            if n["event"] == NotifyEvent.ERROR.value:
                return n["message"]
        return None

    def start_tunnel(self, port=80, provider="serveo"):
        if self.is_running and self.tunnel_url:
            return self.tunnel_url

        self.provider = provider
        self._ensure_subscribed()
        self.notifications.clear()

        if not _FLARE_CORE_AVAILABLE:
            self._notify_error("Tunnel provider unavailable: flaredantic core classes are missing")
            return None

        if provider == "microsoft" and not _MICROSOFT_TUNNEL_AVAILABLE:
            self._notify_error(
                "Tunnel provider 'microsoft' unavailable in current flaredantic build"
            )
            return None

        try:
            def run_tunnel():
                try:
                    if self.provider == "cloudflared":
                        config = FlareConfig(port=port, verbose=True)  # type: ignore[misc]
                        self.tunnel = FlareTunnel(config)
                    elif self.provider == "microsoft":
                        config = MicrosoftConfig(port=port, verbose=True)  # type: ignore[misc]
                        self.tunnel = MicrosoftTunnel(config)
                    else:
                        config = ServeoConfig(port=port)  # type: ignore[misc]
                        self.tunnel = ServeoTunnel(config)

                    self.tunnel.start()
                    self.tunnel_url = self.tunnel.tunnel_url
                    self.is_running = True
                except Exception as exc:
                    self._notify_error(f"Error in tunnel thread: {exc}")

            tunnel_thread = threading.Thread(target=run_tunnel)
            tunnel_thread.daemon = True
            tunnel_thread.start()

            import time

            while True:
                if self.tunnel_url:
                    break
                if any(n["event"] == NotifyEvent.ERROR.value for n in self.notifications):
                    break
                if not tunnel_thread.is_alive():
                    break
                time.sleep(0.1)

            return self.tunnel_url
        except Exception as exc:
            self._notify_error(f"Error starting tunnel: {exc}")
            return None

    def stop_tunnel(self):
        if self.tunnel and self.is_running:
            try:
                self.tunnel.stop()
                self.is_running = False
                self.tunnel_url = None
                self.provider = None
                return True
            except Exception:
                return False
        return False

    def get_tunnel_url(self):
        return self.tunnel_url if self.is_running else None
