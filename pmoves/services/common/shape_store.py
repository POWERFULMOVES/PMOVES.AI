from __future__ import annotations
from __future__ import annotations

import inspect
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import json


logger = logging.getLogger(__name__)


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
    async def warm_from_db(
        self,
        db_fetch_fn=None,
        *,
        rest_url: Optional[str] = None,
        service_key: Optional[str] = None,
        limit: int = 64,
        timeout: float = 10.0,
    ) -> int:
        """Load recent CGPs from Supabase (geometry.cgp.v1 tables).

        Parameters
        ----------
        db_fetch_fn:
            Optional callable returning an iterable of CGP-like dicts. Provided
            for backwards compatibility and testing; if supplied, its results
            are ingested directly.
        rest_url:
            Supabase/PostgREST base URL (e.g., ``http://postgrest:3000`` or
            ``https://xyz.supabase.co/rest/v1``). Falls back to
            ``SUPA_REST_URL``/``SUPABASE_REST_URL`` env vars when omitted.
        service_key:
            API key used for PostgREST auth. Defaults to
            ``SUPABASE_SERVICE_ROLE_KEY``/``SUPABASE_SERVICE_KEY``/``SUPABASE_KEY``/``SUPABASE_ANON_KEY``.
        limit:
            Maximum number of recent constellations to fetch.
        timeout:
            HTTP client timeout (seconds).
        """

        # --- direct ingest path (testing/compat) ---
        if db_fetch_fn is not None:
            records: Iterable[Dict[str, Any]] = []
            try:
                result = db_fetch_fn()
                if inspect.isawaitable(result):
                    result = await result  # type: ignore[assignment]
                if isinstance(result, Iterable):
                    records = result  # type: ignore[assignment]
            except Exception:
                logger.exception("ShapeStore.warm_from_db callable failed")
                return 0

            count = 0
            for rec in records:
                try:
                    self.put_cgp(rec)
                    count += 1
                except Exception:
                    logger.exception("ShapeStore.warm_from_db ingest error", exc_info=True)
            return count

        # --- Supabase PostgREST fetch ---
        rest_url = rest_url or os.getenv("SUPA_REST_URL") or os.getenv("SUPABASE_REST_URL")
        if not rest_url:
            logger.info("ShapeStore warm skipped; SUPA_REST_URL/SUPABASE_REST_URL not configured")
            return 0

        rest_url = rest_url.rstrip("/")
        if not rest_url.endswith("/rest/v1"):
            # Allow PostgREST direct host (e.g., http://postgrest:3000)
            endpoint_base = f"{rest_url}/constellations"
        else:
            endpoint_base = f"{rest_url}/constellations"

        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed; unable to warm ShapeStore from Supabase")
            return 0

        api_key = (
            service_key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )

        headers = {"Accept": "application/json"}
        if api_key:
            headers["apikey"] = api_key
            headers["Authorization"] = f"Bearer {api_key}"

        params = {
            "select": "*,anchor:anchors(*),points:shape_points(*)",
            "order": "created_at.desc",
            "limit": str(max(1, int(limit))),
        }

        base_url = rest_url.rstrip("/")

        limit_str = str(max(1, int(limit)))

        def _coerce_payload(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            candidate: Optional[Dict[str, Any]] = None
            for key in ("payload", "data", "cgp", "packet", "body", "value"):
                if key not in rec:
                    continue
                value = rec.get(key)
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except Exception:
                        continue
                if isinstance(value, dict) and value:
                    candidate = value
                    break
            if candidate is None and "super_nodes" in rec:
                candidate = rec
            if not isinstance(candidate, dict):
                return None
            if "spec" not in candidate:
                candidate = {**candidate, "spec": "geometry.cgp.v1"}
            return candidate

        def _map_constellation(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            cid = rec.get("id")
            if not cid:
                return None
            const: Dict[str, Any] = {
                "id": str(cid),
                "summary": rec.get("summary"),
                "spectrum": rec.get("spectrum"),
            }
            radial_min = rec.get("radial_min")
            radial_max = rec.get("radial_max")
            if radial_min is not None or radial_max is not None:
                const["radial_minmax"] = [radial_min, radial_max]
            meta = rec.get("meta")
            if isinstance(meta, dict) and meta:
                const["meta"] = meta
            anchor = rec.get("anchor")
            if isinstance(anchor, dict) and anchor:
                const["anchor"] = anchor

            points: List[Dict[str, Any]] = []
            for pt in rec.get("points", []) or []:
                if not isinstance(pt, dict):
                    continue
                pid = pt.get("id")
                if not pid:
                    continue
                point: Dict[str, Any] = {
                    "id": str(pid),
                    "modality": pt.get("modality"),
                    "ref_id": pt.get("ref_id"),
                    "t_start": pt.get("t_start"),
                    "t_end": pt.get("t_end"),
                    "frame_idx": pt.get("frame_idx"),
                    "token_start": pt.get("token_start"),
                    "token_end": pt.get("token_end"),
                    "proj": pt.get("proj"),
                    "conf": pt.get("conf"),
                }
                meta_pt = pt.get("meta")
                if isinstance(meta_pt, dict) and meta_pt:
                    point["meta"] = meta_pt
                points.append(point)
            const["points"] = points
            return {
                "spec": "geometry.cgp.v1",
                "source": "supabase",
                "super_nodes": [{"constellations": [const]}],
            }

        fetch_plan: List[tuple[str, Dict[str, str], Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]]] = [
            (
                "geometry_cgp_packets",
                {"select": "payload,created_at", "order": "created_at.desc", "limit": limit_str},
                _coerce_payload,
            ),
            (
                "geometry_cgp_v1",
                {"select": "payload,created_at", "order": "created_at.desc", "limit": limit_str},
                _coerce_payload,
            ),
            (
                "constellations",
                {
                    "select": "*,anchor:anchors(*),points:shape_points(*)",
                    "order": "created_at.desc",
                    "limit": limit_str,
                },
                _map_constellation,
            ),
        ]

        cgps: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            for path, query, mapper in fetch_plan:
                url = f"{base_url}/{path}"
                try:
                    resp = await client.get(url, params=query, headers=headers)
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    records = resp.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        continue
                    logger.exception("ShapeStore warm fetch failed for %s", path)
                    continue
                except Exception:
                    logger.exception("ShapeStore warm fetch error for %s", path)
                    continue

                if not isinstance(records, list):
                    logger.warning(
                        "Unexpected Supabase response for %s: %s", path, type(records)
                    )
                    continue

                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    try:
                        cgp = mapper(rec)
                    except Exception:
                        logger.exception("ShapeStore warm mapping error for %s", path)
                        continue
                    if cgp:
                        cgps.append(cgp)
                if cgps:
                    break

        if not cgps:
            return 0

        count = 0
        for cgp in cgps:
            try:
                self.put_cgp(cgp)
                count += 1
            except Exception:
                logger.exception("ShapeStore warm ingest error", exc_info=True)
        return count

    # ---- event hook (stub) ----
    def on_geometry_event(self, event: Dict[str, Any]) -> None:
        """Handle `geometry.cgp.v1` bus messages."""
        if event.get("type") == "geometry.cgp.v1":
            payload = event.get("data") or {}
            if isinstance(payload, dict):
                self.put_cgp(payload)

