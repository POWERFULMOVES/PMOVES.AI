"""Fail-closed egress floor for the publish gate (PR B).

Detector-only default (BlockAndHoldFloor): NEVER transforms content — it only
answers clean / not-clean. Richer transformers (the flute translator, PR D)
plug in by implementing the Floor protocol.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Protocol

# Private LAN + Tailscale CGNAT (100.64.0.0/10) + *.ts.net
_IP_RE = re.compile(
    r"\b("
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}"
    r")\b"
)
_TSNET_RE = re.compile(r"\b[\w-]+\.ts\.net\b", re.IGNORECASE)

_PII_RULES = ("operator-pii-protected", "collaborator-pii-protected")


@dataclass
class Verdict:
    clean: bool
    tripped: List[str] = field(default_factory=list)


class Floor(Protocol):
    def check(self, item: dict) -> Verdict: ...


def _item_text(item: dict) -> str:
    parts: List[str] = []
    for key in ("title", "description", "text"):
        val = item.get(key)
        if isinstance(val, str):
            parts.append(val)
    tags = item.get("tags")
    if isinstance(tags, (list, tuple)):
        parts.extend(str(t) for t in tags)
    meta = item.get("meta")
    if isinstance(meta, dict):
        parts.extend(str(v) for v in meta.values() if isinstance(v, (str, int, float)))
    return "\n".join(parts)


class BlockAndHoldFloor:
    """Default floor: detect-and-hold, never transform.

    protected_terms=None means the operator denylist is UNCONFIGURED — the PII
    rules cannot prove the item clean, so they fail closed (hold).
    """

    def __init__(self, rules: Iterable[str], protected_terms: Optional[Iterable[str]]):
        self.rules = list(rules)
        self.protected_terms = None if protected_terms is None else [t.lower() for t in protected_terms if t]

    def check(self, item: dict) -> Verdict:
        text = _item_text(item)
        low = text.lower()
        tripped: List[str] = []
        for rule in self.rules:
            if rule == "no-literal-lan-or-tailscale-ips":
                if _IP_RE.search(text) or _TSNET_RE.search(text):
                    tripped.append(rule)
            elif rule in _PII_RULES:
                if self.protected_terms is None:
                    tripped.append(rule)  # fail-closed: cannot verify
                elif any(term in low for term in self.protected_terms):
                    tripped.append(rule)
            else:
                # Unknown rule: no detector can prove the item clean against it,
                # so HOLD. rules are config-driven (room manifest, Task 2) — a
                # typo'd or not-yet-implemented rule name must fail closed, never
                # silently pass. Add a detector branch above to make it live.
                tripped.append(rule)
        return Verdict(clean=(len(tripped) == 0), tripped=tripped)


def _read_rules(manifest_path: str) -> List[str]:
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    floor = (
        manifest.get("policies", {}).get("publish", {}).get("egress_redaction_floor", {})
    )
    rules = floor.get("rules")
    return list(rules) if isinstance(rules, list) else []


def _read_terms(terms_env: str, terms_file_env: str) -> Optional[List[str]]:
    raw = os.environ.get(terms_env)
    if raw is None:
        path = os.environ.get(terms_file_env)
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
    if raw is None:
        return None  # unconfigured -> fail-closed
    return [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]


def load_floor(
    manifest_path: str,
    terms_env: str = "EGRESS_PROTECTED_TERMS",
    terms_file_env: str = "EGRESS_PROTECTED_TERMS_FILE",
) -> BlockAndHoldFloor:
    return BlockAndHoldFloor(
        rules=_read_rules(manifest_path),
        protected_terms=_read_terms(terms_env, terms_file_env),
    )
