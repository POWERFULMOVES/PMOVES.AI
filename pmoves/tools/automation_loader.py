"""n8n automation discovery for pmoves mini CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

FLOW_DIR = Path(__file__).resolve().parents[1] / "n8n" / "flows"


@dataclass
class Webhook:
    name: str
    path: str
    method: str


@dataclass
class Automation:
    id: str
    name: str
    active: bool
    filename: Path
    channels: List[str] = field(default_factory=list)
    webhooks: List[Webhook] = field(default_factory=list)


def load_automations(directory: Path | None = None) -> Dict[str, Automation]:
    directory = directory or FLOW_DIR
    automations: Dict[str, Automation] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        name = data.get("name") or path.stem
        automation_id = data.get("id") or name
        active = bool(data.get("active"))
        nodes = data.get("nodes", [])
        channels = _infer_channels(name, nodes)
        webhooks = _extract_webhooks(nodes)
        automations[automation_id] = Automation(
            id=automation_id,
            name=name,
            active=active,
            filename=path,
            channels=channels,
            webhooks=webhooks,
        )
    return automations


def _infer_channels(name: str, nodes: Iterable[dict]) -> List[str]:
    tokens = {name.lower()}
    for node in nodes:
        for value in node.values():
            if isinstance(value, str):
                tokens.add(value.lower())
    channels = []
    mapping = {
        "discord": "discord",
        "telegram": "telegram",
        "whatsapp": "whatsapp",
        "webhook": "webhook",
        "slack": "slack",
        "web rtc": "webrtc",
        "signal": "signal",
        "twilio": "twilio",
    }
    for needle, label in mapping.items():
        if any(needle in token for token in tokens):
            channels.append(label)
    return sorted(set(channels))


def _extract_webhooks(nodes: Iterable[dict]) -> List[Webhook]:
    webhooks: List[Webhook] = []
    for node in nodes:
        if node.get("type") != "n8n-nodes-base.webhook":
            continue
        params = node.get("parameters", {})
        path = params.get("path") or params.get("pathSegment")
        method = (params.get("httpMethod") or "GET").upper()
        name = node.get("name", "Webhook")
        if path:
            webhooks.append(Webhook(name=name, path=path, method=method))
    return webhooks
