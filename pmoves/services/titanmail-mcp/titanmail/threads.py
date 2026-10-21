"""Thread grouping. Provider thread ids win; otherwise RFC 5322 In-Reply-To/References
are unioned. Subject similarity is NOT used -- "Re: Invoice" from two customers is two
threads, and merging them is the false-merge this service is built to avoid."""
from __future__ import annotations

from typing import Iterable

from .models import EmailMessage, normalize_message_id, references_list
from .timewindow import iso_z


class _UF:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def group_threads(messages: Iterable[EmailMessage]) -> list[dict]:
    msgs = list(messages)
    uf = _UF()
    for m in msgs:
        node = f"msg:{m.id}"
        uf.find(node)
        if m.thread_id:
            uf.union(node, f"thr:{m.thread_id}")
            continue
        mid = normalize_message_id(m.message_id)
        if mid:
            uf.union(node, f"mid:{mid}")
        for ref in references_list(m.in_reply_to) + references_list(m.references):
            if ref:
                uf.union(node, f"mid:{ref}")
    groups: dict[str, list[EmailMessage]] = {}
    for m in msgs:
        groups.setdefault(uf.find(f"msg:{m.id}"), []).append(m)
    out = []
    for root, ms in groups.items():
        ms.sort(key=lambda m: (m.date_utc, m.id))
        out.append({"thread_key": root, "message_count": len(ms), "subject": ms[0].subject,
                    "first_utc": iso_z(ms[0].date), "last_utc": iso_z(ms[-1].date),
                    "participants": sorted({a.lower() for m in ms for a in [m.from_addr, *m.to] if a}),
                    "message_ids": [m.id for m in ms]})
    out.sort(key=lambda t: (t["last_utc"], t["thread_key"]), reverse=True)
    return out
