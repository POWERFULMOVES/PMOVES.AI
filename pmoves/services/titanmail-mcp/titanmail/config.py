"""Build the service from environment variables. Secrets are read, never echoed."""
from __future__ import annotations

import os
from typing import Mapping, Optional

from .service import TitanMailService
from .timewindow import load_tz
from .transports import ComposioTransport, MailpitTransport


def _bool(v: Optional[str]) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def build_transport(env: Mapping[str, str]):
    kind = (env.get("TITANMAIL_TRANSPORT") or "mailpit").strip().lower()
    if kind == "mailpit":
        return MailpitTransport(
            env.get("TITANMAIL_MAILPIT_URL") or "http://mailpit:8025",
            scope_query=env.get("TITANMAIL_MAILPIT_SCOPE_QUERY", ""),
            use_message_dates=_bool(env.get("TITANMAIL_MAILPIT_USE_MESSAGE_DATES")),
            ignore_synthetic_message_ids=not _bool(env.get("TITANMAIL_MAILPIT_KEEP_SYNTHETIC_MESSAGE_IDS")),
            max_scan=int(env.get("TITANMAIL_MAILPIT_MAX_SCAN") or 5000),
        )
    if kind in ("composio-gmail", "composio-outlook", "gmail", "outlook"):
        provider = kind.split("-")[-1]
        up = provider.upper()
        slugs = {k: env[f"TITANMAIL_COMPOSIO_{up}_{k.upper()}_SLUG"]
                 for k in ("search", "get") if env.get(f"TITANMAIL_COMPOSIO_{up}_{k.upper()}_SLUG")}
        return ComposioTransport(
            provider,
            api_key=env.get("COMPOSIO_API_KEY", ""),
            user_id=env.get("TITANMAIL_COMPOSIO_USER_ID", ""),
            connected_account_id=env.get(f"TITANMAIL_COMPOSIO_{up}_CONNECTED_ACCOUNT_ID", ""),
            base_url=env.get("TITANMAIL_COMPOSIO_BASE_URL") or "https://backend.composio.dev/api/v3.1",
            toolkit_version=env.get(f"TITANMAIL_COMPOSIO_{up}_TOOLKIT_VERSION", ""),
            slugs=slugs,
        )
    raise ValueError(f"TITANMAIL_TRANSPORT={kind!r}: expected mailpit | composio-gmail | composio-outlook")


def build_service(env: Optional[Mapping[str, str]] = None) -> TitanMailService:
    env = os.environ if env is None else env
    return TitanMailService(
        build_transport(env),
        tz=load_tz(env.get("TITANMAIL_TZ") or "UTC"),
        max_window_days=int(env.get("TITANMAIL_MAX_WINDOW_DAYS") or 3660),
        dedup_window_seconds=int(env.get("TITANMAIL_DEDUP_WINDOW_SECONDS") or 120),
    )
