"""Deterministic-first message dedup (Agentic CDP pattern, seed-spec mandate (c)).

Precision bar is three nines: a false merge hides a real message, which is worse
than showing a duplicate twice. So every rule below prefers NOT merging.

Pass 1 -- Message-ID. Messages sharing a normalized Message-ID are one logical
message (mirror copies, multi-folder copies, re-deliveries), PROVIDED their
normalized sender and subject agree. A shared Message-ID with a different sender
or subject is a Message-ID collision (buggy generators reuse ids); those are NOT
merged and are reported as ``conflicts`` for the tie-breaker seam.

Pass 2 -- fallback key, only for messages WITHOUT a Message-ID:
sha256(from | sorted to+cc | subject | body hash). Within one fallback key,
messages chain into a cluster only when consecutive copies are at most
``window_seconds`` apart (single linkage on time, no fixed buckets, so no bucket
boundary can split a pair). Same-key messages further apart than that but within
``ambiguous_seconds`` are reported as ``ambiguous`` -- not merged.

Messages that have a Message-ID are never fallback-merged with ones that do not;
that pairing is the most common way content-only matching goes wrong (a re-sent
newsletter is the same content, a different message).

The AI tie-breaker is a SEAM, not an implementation: :class:`TieBreaker` receives
conflicts/ambiguous groups and may return merge decisions. v1 ships
:class:`NoTieBreaker`, which never merges.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .models import (EmailMessage, body_hash, normalize_address, normalize_addresses,
                     normalize_message_id, normalize_subject)
from .timewindow import iso_z

DEFAULT_WINDOW_SECONDS = 120
DEFAULT_AMBIGUOUS_SECONDS = 24 * 3600


@dataclass
class Cluster:
    key: str
    rule: str                    # "message_id" | "fallback"
    members: list[EmailMessage]

    def to_dict(self) -> dict:
        ms = sorted(self.members, key=lambda m: (m.date_utc, m.id))
        out = {"key": self.key, "rule": self.rule, "size": len(ms), "canonical_id": ms[0].id,
               "duplicate_ids": [m.id for m in ms[1:]],
               "first_utc": iso_z(ms[0].date), "last_utc": iso_z(ms[-1].date),
               "subject": ms[0].subject}
        headers = {m.id: m.extra for m in ms if m.extra}
        if headers:
            out["member_headers"] = headers
        return out


@dataclass
class DedupResult:
    clusters: list[Cluster] = field(default_factory=list)      # size >= 2 only
    conflicts: list[dict] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    total: int = 0

    def merged_pairs(self) -> set[frozenset]:
        pairs = set()
        for c in self.clusters:
            ids = [m.id for m in c.members]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pairs.add(frozenset((ids[i], ids[j])))
        return pairs

    def canonical_of(self) -> dict[str, str]:
        out = {}
        for c in self.clusters:
            canon = min(c.members, key=lambda m: (m.date_utc, m.id)).id
            for m in c.members:
                out[m.id] = canon
        return out

    def to_dict(self) -> dict:
        dupes = sum(len(c.members) - 1 for c in self.clusters)
        return {"messages_examined": self.total, "unique_after_dedup": self.total - dupes,
                "duplicates": dupes, "clusters": [c.to_dict() for c in self.clusters],
                "conflicts_not_merged": self.conflicts, "ambiguous_not_merged": self.ambiguous}


class TieBreaker(Protocol):
    def decide(self, group: list[EmailMessage], reason: str) -> list[list[str]]:
        """Return groups of ids to merge (may be empty). Called only for unresolved cases."""


class NoTieBreaker:
    def decide(self, group: list[EmailMessage], reason: str) -> list[list[str]]:
        return []


def fallback_key(m: EmailMessage) -> str:
    parts = [normalize_address(m.from_addr), ",".join(normalize_addresses(m.to + m.cc)),
             normalize_subject(m.subject), body_hash(m.body_text or m.snippet)]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def dedup(messages: Iterable[EmailMessage], *, window_seconds: int = DEFAULT_WINDOW_SECONDS,
          ambiguous_seconds: int = DEFAULT_AMBIGUOUS_SECONDS,
          tie_breaker: TieBreaker | None = None) -> DedupResult:
    msgs = list(messages)
    res = DedupResult(total=len(msgs))
    tie_breaker = tie_breaker or NoTieBreaker()

    by_mid: dict[str, list[EmailMessage]] = {}
    no_mid: list[EmailMessage] = []
    for m in msgs:
        mid = normalize_message_id(m.message_id)
        (by_mid.setdefault(mid, []) if mid else no_mid).append(m)

    for mid, group in sorted(by_mid.items()):
        if len(group) < 2:
            continue
        identity = {(normalize_address(m.from_addr), normalize_subject(m.subject)) for m in group}
        if len(identity) == 1:
            res.clusters.append(Cluster(f"mid:{mid}", "message_id", group))
            continue
        res.conflicts.append({"message_id": mid, "ids": sorted(m.id for m in group),
                              "reason": "same Message-ID, different sender/subject"})
        for ids in tie_breaker.decide(group, "message_id_conflict"):
            members = [m for m in group if m.id in set(ids)]
            if len(members) >= 2:
                res.clusters.append(Cluster(f"mid:{mid}:tb", "tie_breaker", members))

    by_fb: dict[str, list[EmailMessage]] = {}
    for m in no_mid:
        by_fb.setdefault(fallback_key(m), []).append(m)
    for key, group in sorted(by_fb.items()):
        if len(group) < 2:
            continue
        group.sort(key=lambda m: (m.date_utc, m.id))
        chain = [group[0]]
        chains = []
        for prev, cur in zip(group, group[1:]):
            gap = (cur.date_utc - prev.date_utc).total_seconds()
            if gap <= window_seconds:
                chain.append(cur)
            else:
                chains.append(chain)
                if gap <= ambiguous_seconds:
                    res.ambiguous.append({"fallback_key": key, "ids": [prev.id, cur.id],
                                          "gap_seconds": int(gap),
                                          "reason": "same content outside the dedup window"})
                chain = [cur]
        chains.append(chain)
        for i, c in enumerate(chains):
            if len(c) >= 2:
                res.clusters.append(Cluster(f"fb:{key}:{i}", "fallback", c))
    return res
