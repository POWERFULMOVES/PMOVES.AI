"""Agent card registry.

Loads BoTZ card YAMLs from the docs directory and enriches them
with live health probe data.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger("showtime.agent_registry")

# Default cards directory — resolved relative to repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CARDS_DIR = os.environ.get(
    "BOTZ_CARDS_DIR",
    str(_REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "botz-cards"),
)

HEALTH_TIMEOUT = 2.0


def load_cards(cards_dir: str | None = None) -> list[dict[str, Any]]:
    """Load all agent card YAML files from the cards directory."""
    directory = Path(cards_dir or CARDS_DIR)
    cards: list[dict[str, Any]] = []

    if not directory.exists():
        logger.warning("Cards directory not found: %s", directory)
        return cards

    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue  # skip schema/meta files
        try:
            with open(path) as f:
                card = yaml.safe_load(f)
            if card and isinstance(card, dict):
                card["_source_file"] = path.name
                cards.append(card)
        except Exception as exc:
            logger.error("Failed to load card %s: %s", path.name, exc)

    # Sort by tier then class priority
    class_order = {"Legendary": 0, "Standard": 1, "Specialized": 2, "Utility": 3}
    cards.sort(key=lambda c: (c.get("tier", 99), class_order.get(c.get("class", ""), 9)))
    return cards


async def enrich_with_health(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add live health status to each agent card."""
    async with httpx.AsyncClient() as client:
        tasks = [_probe_agent_health(client, card) for card in cards]
        return await asyncio.gather(*tasks)


async def _probe_agent_health(client: httpx.AsyncClient, card: dict[str, Any]) -> dict[str, Any]:
    """Probe a single agent's health endpoint."""
    health_url = _build_health_url(card)
    health_ok = False
    health_code = 0
    if health_url:
        try:
            resp = await client.get(health_url, timeout=HEALTH_TIMEOUT)
            health_ok = 200 <= resp.status_code < 400
            health_code = resp.status_code
        except Exception as exc:
            logger.debug("Health check failed for %s: %s", card.get("agent_id", "unknown"), exc)
    return {
        **card,
        "health": {
            "url": health_url,
            "ok": health_ok,
            "status_code": health_code,
        },
    }


def _build_health_url(card: dict[str, Any]) -> str | None:
    """Build health URL from card ports and health_endpoint."""
    ports = card.get("ports", {})
    endpoint = card.get("health_endpoint")
    if not endpoint:
        return None
    port = ports.get("http") or ports.get("cpu")
    if not port:
        return None
    base = f"http://localhost:{port}"
    return f"{base}{endpoint}"


def get_card_by_id(cards: list[dict[str, Any]], agent_id: str) -> dict[str, Any] | None:
    """Find a card by agent_id (case-insensitive)."""
    agent_id_lower = agent_id.lower()
    for card in cards:
        if card.get("agent_id", "").lower() == agent_id_lower:
            return card
    return None
