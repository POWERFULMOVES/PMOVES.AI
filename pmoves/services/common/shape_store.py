from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ShapePoint:
    id: str
    constellation_id: str
    modality: str
    ref_id: str
    t_start: Optional[float] = None
    t_end: Optional[float] = None
    frame_idx: Optional[int] = None
    token_start: Optional[int] = None
    token_end: Optional[int] = None
    proj: Optional[float] = None
    conf: Optional[float] = None
    meta: Dict[str, Any] = None


class ShapeStore:
    """In-memory LRU cache for geometry packets and lookups.

    - Stores anchors, constellations, and points keyed by id.
    - Minimal API to support sub-100ms cross-modal jumps.
    - Thread-safe for simple multi-worker usage.
    """

    def __init__(self, capacity: int = 10_000):
        self.capacity = capacity
        self._lock = threading.RLock()
        self._anchors: Dict[str, Dict[str, Any]] = {}
        self._constellations: Dict[str, Dict[str, Any]] = {}
        self._points: Dict[str, ShapePoint] = {}
        self._lru: "OrderedDict[str, None]" = OrderedDict()

    # ---- basic LRU bookkeeping ----
    def _touch(self, key: str) -> None:
        if key in self._lru:
            self._lru.move_to_end(key)
        else:
            self._lru[key] = None
        if len(self._lru) > self.capacity:
            old_key, _ = self._lru.popitem(last=False)
            self._evict(old_key)

    def _evict(self, key: str) -> None:
        self._anchors.pop(key, None)
        self._constellations.pop(key, None)
        self._points.pop(key, None)

    # ---- CGP ingest ----
    def put_cgp(self, cgp: Dict[str, Any]) -> None:
        """Ingest a CGP (chit.cgp.v0.1) blob into the store.

        Expected shape (subset):
        {
          "spec": "chit.cgp.v0.1",
          "super_nodes": [
            { "constellations": [ { "id": str, "points": [ {...} ] } ] }
          ]
        }
        """
        with self._lock:
            for sn in cgp.get("super_nodes", []) or []:
                for const in sn.get("constellations", []) or []:
                    cid = const.get("id")
                    if not cid:
                        continue
                    self._constellations[cid] = const
                    self._touch(cid)
                    for p in const.get("points", []) or []:
                        pid = str(p.get("id"))
                        if not pid:
                            continue
                        sp = ShapePoint(
                            id=pid,
                            constellation_id=cid,
                            modality=p.get("modality") or p.get("mod", "text"),
                            ref_id=
                                p.get("ref_id")
                                or p.get("video_id")
                                or p.get("doc_id")
                                or p.get("source_ref")
                                or "",
                            t_start=p.get("t_start"),
                            t_end=p.get("t_end"),
                            frame_idx=p.get("frame_idx"),
                            token_start=p.get("token_start"),
                            token_end=p.get("token_end"),
                            proj=p.get("proj"),
                            conf=p.get("conf"),
                            meta={k: v for k, v in p.items() if k not in {
                                "id","modality","mod","ref_id","video_id","doc_id",
                                "t_start","t_end","frame_idx","token_start","token_end",
                                "proj","conf"
                            }}
                        )
                        self._points[pid] = sp
                        self._touch(pid)

    # ---- lookups ----
    def get_constellation(self, constellation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            c = self._constellations.get(constellation_id)
            if c:
                self._touch(constellation_id)
            return c

    def get_point(self, point_id: str) -> Optional[ShapePoint]:
        with self._lock:
            sp = self._points.get(point_id)
            if sp:
                self._touch(point_id)
            return sp

    # ---- cross-modal jumps ----
    def jump_locator(self, point_id: str) -> Optional[Dict[str, Any]]:
        """Return a compact locator for UI/agents to jump to the data.

        Example outputs:
        - { "modality": "video", "ref_id": "yt123", "t": 31.25, "frame": 750 }
        - { "modality": "audio", "ref_id": "aud456", "t": 12.0 }
        - { "modality": "text",  "ref_id": "doc789", "token_start": 120, "token_end": 160 }
        """
        sp = self.get_point(point_id)
        if not sp:
            return None
        loc: Dict[str, Any] = {"modality": sp.modality, "ref_id": sp.ref_id}
        if sp.modality == "video":
            if sp.t_start is not None:
                loc["t"] = float(sp.t_start)
            if sp.frame_idx is not None:
                loc["frame"] = int(sp.frame_idx)
        elif sp.modality == "audio":
            if sp.t_start is not None:
                loc["t"] = float(sp.t_start)
        elif sp.modality == "text":
            if sp.token_start is not None:
                loc["token_start"] = int(sp.token_start)
            if sp.token_end is not None:
                loc["token_end"] = int(sp.token_end)
        return loc

    # ---- warmers (stubs) ----
    def warm_from_db(self, db_fetch_fn) -> int:
        """Load recent constellations/points via a user-supplied fetch function.

        The callable should return an iterable of CGP-like dicts or records that
        can be mapped into put_cgp(). Returns number of CGPs ingested.
        """
        count = 0
        for rec in db_fetch_fn():
            try:
                self.put_cgp(rec)
                count += 1
            except Exception:
                continue
        return count

    # ---- event hook (stub) ----
    def on_geometry_event(self, event: Dict[str, Any]) -> None:
        """Handle `geometry.cgp.v1` bus messages."""
        if event.get("type") == "geometry.cgp.v1":
            payload = event.get("data") or {}
            if isinstance(payload, dict):
                self.put_cgp(payload)

