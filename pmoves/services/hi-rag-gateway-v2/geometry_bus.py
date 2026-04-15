"""Geometry bus: WebSocket rooms, ShapeStore, NATS swarm, realtime worker, lifespan."""

import asyncio
import contextlib
import copy
import importlib.util
import inspect
import json
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket

from config import (
    NAMESPACE_DEFAULT,
    NATS_URL,
    SUPABASE_REST_URL,
    SUPABASE_REST_INTERNAL_URL,
    SUPABASE_SERVICE_KEY,
    SUPABASE_ANON_KEY,
    SUPABASE_REALTIME_URL,
    SUPABASE_REALTIME_KEY,
    SUPABASE_REALTIME_DISABLED,
    GEOMETRY_CACHE_WARM_LIMIT,
    GEOMETRY_REALTIME_BACKOFF,
    GEOMETRY_REALTIME_MAX_BACKOFF,
    GEOMETRY_REALTIME_STARTUP_GRACE,
    CHIT_CODEBOOK_PATH,
    GAN_SIDECAR_ENABLED,
    PGHOST,
    PGPORT,
    PGUSER,
    PGPASSWORD,
    PGDATABASE,
    logger,
)

# --- Optional heavy dependencies ---
try:
    import nats
except ImportError:
    nats = None  # type: ignore

# --- ShapeStore and geometry params ---
try:
    from services.common.shape_store import ShapeStore
    from services.common import geometry_params
    shape_store = ShapeStore(capacity=10_000)
    logging.getLogger("hirag.gateway.v2").info("ShapeStore initialized (v2)")
except Exception as _e:
    logging.getLogger("hirag.gateway.v2").exception("ShapeStore init failed: %s", _e)
    shape_store = None  # type: ignore
    geometry_params = None  # type: ignore

# --- HRM decoder controller ---
try:
    from services.common.geometry_params import get_decoder_pack
    from services.common.hrm_sidecar import HrmDecoderController
    _hrm_controller = HrmDecoderController(get_decoder_pack)
except Exception:
    _hrm_controller = None  # type: ignore

# ---------------------------------------------------------------------------
# WebSocket room management
# ---------------------------------------------------------------------------
_rooms: Dict[str, List[WebSocket]] = {}
_room_ws_id: Dict[str, Dict[WebSocket, str]] = {}
_room_ids: Dict[str, List[str]] = {}


def _room_get(name: str) -> List[WebSocket]:
    return _rooms.setdefault(name, [])


async def _room_add(name: str, ws: WebSocket):
    _room_get(name).append(ws)
    _room_ws_id.setdefault(name, {})[ws] = ""
    _room_ids.setdefault(name, [])


def _room_remove(name: str, ws: WebSocket):
    lst = _rooms.get(name, [])
    if ws in lst:
        lst.remove(ws)
    if name in _room_ws_id and ws in _room_ws_id[name]:
        pid = _room_ws_id[name].pop(ws, "")
        if pid and name in _room_ids and pid in _room_ids[name]:
            try:
                _room_ids[name].remove(pid)
            except ValueError:
                pass


async def _room_broadcast(name: str, msg: Dict[str, Any], skip: WebSocket | None = None):
    dead = []
    for ws in list(_rooms.get(name, [])):
        if skip is not None and ws is skip:
            continue
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for d in dead:
        _room_remove(name, d)


async def _room_broadcast_roster(name: str):
    peers = _room_ids.get(name, [])
    await _room_broadcast(name, {"type": "roster", "room": name, "peers": peers})


# ---------------------------------------------------------------------------
# Geometry task globals
# ---------------------------------------------------------------------------
_geometry_realtime_task: Optional[asyncio.Task] = None
_geometry_swarm_task: Optional[asyncio.Task] = None
_geometry_swarm_stop: Optional[asyncio.Event] = None
_geometry_swarm_nc = None

_builder_pack_lock = threading.RLock()
_active_builder_packs: Dict[tuple[str, str], Dict[str, Any]] = {}


def _pack_key(namespace: str, modality: Optional[str]) -> tuple[str, str]:
    ns = (namespace or "").strip().lower()
    mod = (modality or "*").strip().lower() or "*"
    return ns, mod


def _set_active_builder_pack(namespace: str, modality: Optional[str], pack: Optional[Dict[str, Any]]) -> None:
    if not namespace:
        return
    key = _pack_key(namespace, modality)
    with _builder_pack_lock:
        if pack is None:
            _active_builder_packs.pop(key, None)
        else:
            _active_builder_packs[key] = copy.deepcopy(pack)
    if shape_store is not None:
        try:
            shape_store.update_builder_pack(namespace, modality, pack)
        except Exception:
            logger.exception("Failed to propagate builder pack metadata to ShapeStore")


def _get_active_builder_pack(namespace: str, modality: Optional[str]) -> Optional[Dict[str, Any]]:
    if not namespace:
        return None
    key = _pack_key(namespace, modality)
    with _builder_pack_lock:
        pack = _active_builder_packs.get(key)
        if pack is not None:
            return copy.deepcopy(pack)
        if modality:
            fallback = _active_builder_packs.get(_pack_key(namespace, None))
            if fallback is not None:
                return copy.deepcopy(fallback)
    return None


# ---------------------------------------------------------------------------
# Geometry context helper
# ---------------------------------------------------------------------------
def _geometry_context(body: Dict[str, Any], const: Optional[Dict[str, Any]]) -> tuple[str, str]:
    namespace = (body.get("namespace") or "").strip()
    modality = (body.get("modality") or "").strip()
    if const and isinstance(const.get("meta"), dict):
        meta = const.get("meta") or {}
        if not namespace:
            namespace = str(meta.get("namespace") or "").strip()
        if not modality:
            modality = str(
                meta.get("modality")
                or meta.get("mode")
                or meta.get("mod")
                or ""
            ).strip()
    namespace = namespace or NAMESPACE_DEFAULT
    modality = modality or "geometry"
    return namespace, modality


# ---------------------------------------------------------------------------
# Geometry pack fetch from Supabase
# ---------------------------------------------------------------------------
async def _fetch_geometry_pack(
    pack_id: str,
    *,
    rest_url: Optional[str] = None,
    service_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    import requests as _requests
    base_url = (rest_url or SUPABASE_REST_URL or "").strip()
    if not base_url:
        return None
    if urlparse(base_url).scheme not in ("http", "https"):
        logger.warning("Invalid scheme in Supabase REST URL: %s", base_url[:60])
        return None
    base = base_url.rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    url = f"{base}/geometry_parameter_packs"
    params = {
        "select": "id,namespace,modality,pack_type,status,params,population_id,generation,fitness,energy,version,meta",
        "id": f"eq.{pack_id}",
        "limit": "1",
    }
    key = (service_key or SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY or "").strip()
    headers = {"Accept": "application/json"}
    if key:
        headers.update({"apikey": key, "Authorization": f"Bearer {key}"})

    def _request() -> Optional[Dict[str, Any]]:
        try:
            resp = _requests.get(url, params=params, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch geometry parameter pack %s: %s", pack_id, exc)
            return None
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict):
                return row
        return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _request)


# ---------------------------------------------------------------------------
# Swarm meta application
# ---------------------------------------------------------------------------
async def _apply_swarm_meta(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    namespace = (payload.get("namespace") or NAMESPACE_DEFAULT).strip() or NAMESPACE_DEFAULT
    modality = (payload.get("modality") or "geometry").strip() or "geometry"
    status = (payload.get("status") or "").strip().lower()
    pack_id = payload.get("pack_id")
    if not pack_id:
        logger.warning("geometry.swarm.meta payload missing pack_id: %s", payload)
        return

    try:
        geometry_params.clear_cache()
    except Exception:
        logger.exception("Failed to clear geometry parameter cache after swarm meta event")

    if status != "active":
        _set_active_builder_pack(namespace, modality, None)
        logger.info(
            "geometry.swarm.meta.v1 -> deactivated pack %s for %s/%s (status=%s)",
            pack_id,
            namespace,
            modality,
            status or "unknown",
        )
        return

    pack = await _fetch_geometry_pack(pack_id)
    if pack is None or not isinstance(pack, dict):
        pack = {}
    snapshot = copy.deepcopy(pack)
    snapshot.setdefault("id", pack_id)
    snapshot.setdefault("pack_id", pack_id)
    snapshot["status"] = payload.get("status") or pack.get("status")
    snapshot["namespace"] = namespace
    snapshot["modality"] = modality
    for key in ("version", "population_id", "best_fitness", "metrics", "ts"):
        if payload.get(key) is not None:
            snapshot[key] = payload.get(key)
        elif isinstance(pack, dict) and pack.get(key) is not None:
            snapshot.setdefault(key, pack.get(key))

    _set_active_builder_pack(namespace, modality, snapshot)
    logger.info(
        "geometry.swarm.meta.v1 -> activated pack %s for %s/%s", pack_id, namespace, modality
    )


# ---------------------------------------------------------------------------
# NATS geometry swarm worker
# ---------------------------------------------------------------------------
async def _geometry_swarm_worker() -> None:
    global _geometry_swarm_nc, _geometry_swarm_stop
    backoff = max(1.0, GEOMETRY_REALTIME_BACKOFF)
    while True:
        stop_event = asyncio.Event()
        try:
            nc = await nats.connect(servers=[NATS_URL])
            _geometry_swarm_nc = nc
            _geometry_swarm_stop = stop_event

            async def _handler(msg):
                data = msg.data
                payload: Optional[Dict[str, Any]] = None
                if isinstance(data, (bytes, bytearray)):
                    try:
                        payload = json.loads(data.decode())
                    except Exception:
                        logger.warning("Invalid geometry.swarm.meta payload received")
                        return
                elif isinstance(data, dict):
                    payload = data
                if payload is None:
                    return
                try:
                    await _apply_swarm_meta(payload)
                except Exception:
                    logger.exception("Failed to apply geometry.swarm.meta payload")

            await nc.subscribe("geometry.swarm.meta.v1", cb=_handler)
            await stop_event.wait()
            break
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception(
                "NATS geometry.swarm.meta listener error; retrying in %.1fs", backoff
            )
            await asyncio.sleep(backoff)
        finally:
            _geometry_swarm_stop = None
            if _geometry_swarm_nc is not None:
                with contextlib.suppress(Exception):
                    await _geometry_swarm_nc.drain()
                with contextlib.suppress(Exception):
                    await _geometry_swarm_nc.close()
                _geometry_swarm_nc = None
        if stop_event.is_set():
            break


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------
def _hostname_resolves(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


def _port_reachable(url: str, timeout: float = 2.0) -> bool:
    """Check if the host:port is actually reachable (not just DNS resolution)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _derive_realtime_url() -> Optional[str]:
    if SUPABASE_REALTIME_DISABLED:
        logger.info("Supabase realtime disabled via env; skipping subscription")
        return None
    if SUPABASE_REALTIME_URL:
        try:
            in_container = os.path.exists("/.dockerenv")
        except Exception:
            in_container = False

        if in_container and "api.supabase.internal" in SUPABASE_REALTIME_URL:
            rest_base = SUPABASE_REST_INTERNAL_URL or SUPABASE_REST_URL
            if rest_base:
                rb = rest_base.rstrip('/')
                if rb.endswith('/rest/v1'):
                    rb = rb[: -len('/rest/v1')]
                if rb.startswith('https://'):
                    rb = 'wss://' + rb[len('https://'):]
                elif rb.startswith('http://'):
                    rb = 'ws://' + rb[len('http://'):]
                return rb + '/realtime/v1/websocket'
            logger.warning(
                "Rewriting SUPABASE_REALTIME_URL host 'api.supabase.internal' to host-gateway failed; no REST base set"
            )
        else:
            if _port_reachable(SUPABASE_REALTIME_URL):
                return SUPABASE_REALTIME_URL
            logger.info(
                "Configured SUPABASE_REALTIME_URL port not reachable; deriving from REST base instead"
            )
    rest_base = SUPABASE_REST_INTERNAL_URL or SUPABASE_REST_URL
    if not rest_base:
        return None
    rest = (rest_base or "").rstrip("/")
    if "postgrest" in rest or rest.endswith(":3000"):
        candidate = "ws://realtime:4000/socket/websocket"
        if _port_reachable(candidate):
            return candidate
        logger.info("Supabase realtime service not available on docker network; skipping subscription")
        return None
    base = rest
    if base.endswith("/rest/v1"):
        base = base[: -len("/rest/v1")]
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base.rstrip("/") + "/realtime/v1"


# ---------------------------------------------------------------------------
# Shape warm from Supabase
# ---------------------------------------------------------------------------
async def _warm_shapes_from_supabase() -> None:
    if shape_store is None or not SUPABASE_REST_URL:
        if shape_store is not None:
            logger.info("ShapeStore warm skipped; SUPA_REST_URL not configured")
        return
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    try:
        count = await shape_store.warm_from_db(
            rest_url=SUPABASE_REST_URL,
            service_key=key,
            limit=GEOMETRY_CACHE_WARM_LIMIT,
        )
        logger.info("ShapeStore warmed with %d Supabase constellations", count)
    except Exception:
        logger.exception("ShapeStore warm_from_db failed")


# ---------------------------------------------------------------------------
# Phoenix heartbeat for Supabase realtime
# ---------------------------------------------------------------------------
async def _phoenix_heartbeat(ws, interval: float = 25.0) -> None:
    ref = 1
    try:
        while True:
            msg = {"topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": str(ref)}
            await ws.send(json.dumps(msg))
            ref += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Supabase heartbeat error")


# ---------------------------------------------------------------------------
# Supabase realtime geometry worker
# ---------------------------------------------------------------------------
async def _geometry_realtime_worker(ws_url: str, api_key: str) -> None:
    try:
        import websockets
    except ImportError:
        logger.warning("websockets not installed; skipping Supabase realtime subscription")
        return

    startup_time = time.monotonic()
    current_backoff = GEOMETRY_REALTIME_BACKOFF

    while True:
        full_url = ws_url
        if full_url.rstrip('/').endswith('/realtime/v1'):
            full_url = full_url.rstrip('/') + '/websocket'
        if "apikey=" not in full_url:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}apikey={api_key}&vsn=1.0.0"
        headers = {}
        if SUPABASE_REALTIME_KEY:
            headers["Authorization"] = f"Bearer {SUPABASE_REALTIME_KEY}"
        try:
            connect_kwargs: Dict[str, Any] = {
                "ping_interval": 20,
                "ping_timeout": 20,
                "max_queue": None,
            }
            if headers:
                try:
                    sig = inspect.signature(websockets.connect)
                    if "additional_headers" in sig.parameters:
                        connect_kwargs["additional_headers"] = headers
                    else:
                        connect_kwargs["extra_headers"] = headers
                except Exception:
                    connect_kwargs["extra_headers"] = headers
            async with websockets.connect(full_url, **connect_kwargs) as ws:
                join_payload = {
                    "topic": "realtime:geometry.cgp.v1",
                    "event": "phx_join",
                    "payload": {
                        "config": {"broadcast": {"ack": False, "self": True}},
                        "access_token": api_key,
                    },
                    "ref": "1",
                }
                await ws.send(json.dumps(join_payload))
                logger.info("Subscribed to Supabase realtime geometry.cgp.v1 channel")
                current_backoff = max(1.0, GEOMETRY_REALTIME_BACKOFF)
                heartbeat = asyncio.create_task(_phoenix_heartbeat(ws))
                try:
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError as e:
                            logger.debug("Supabase realtime: failed to parse message: %s", e)
                            continue
                        if msg.get("topic") != "realtime:geometry.cgp.v1":
                            continue
                        payload = msg.get("payload") or {}
                        event_payload: Optional[Dict[str, Any]] = None
                        if isinstance(payload, dict):
                            if payload.get("type") == "geometry.cgp.v1" and isinstance(payload.get("data"), dict):
                                event_payload = payload
                            elif payload.get("type") == "geometry.cgp.v1" and isinstance(payload.get("payload"), dict):
                                event_payload = {"type": "geometry.cgp.v1", "data": payload.get("payload")}
                            else:
                                evt = payload.get("event") or payload.get("type")
                                data = (
                                    payload.get("data")
                                    or payload.get("payload")
                                    or payload.get("record")
                                    or payload.get("new")
                                )
                                if evt == "geometry.cgp.v1" and isinstance(data, dict):
                                    event_payload = {"type": "geometry.cgp.v1", "data": data}
                        if event_payload:
                            try:
                                shape_store.on_geometry_event(event_payload)
                            except Exception:
                                logger.exception("Failed to apply Supabase geometry event")
                finally:
                    heartbeat.cancel()
                    with contextlib.suppress(Exception):
                        await heartbeat
        except asyncio.CancelledError:
            break
        except Exception as exc:
            elapsed = time.monotonic() - startup_time
            if elapsed < GEOMETRY_REALTIME_STARTUP_GRACE:
                logger.warning(
                    "Supabase realtime not ready (%s: %s); retrying in %.1fs (grace period: %.0fs remaining)",
                    type(exc).__name__,
                    str(exc)[:100],
                    current_backoff,
                    GEOMETRY_REALTIME_STARTUP_GRACE - elapsed,
                )
                logger.debug("Stack trace for startup grace period warning:", exc_info=True)
            else:
                logger.exception(
                    "Supabase realtime listener error (%s); retrying in %.1fs",
                    type(exc).__name__,
                    current_backoff,
                )
            await asyncio.sleep(current_backoff)
            current_backoff = min(current_backoff * 2, GEOMETRY_REALTIME_MAX_BACKOFF)


# ---------------------------------------------------------------------------
# CHIT codebook cache
# ---------------------------------------------------------------------------
_codebook_cache = None
_codebook_mtime = None


def _load_codebook(path: str):
    global _codebook_cache, _codebook_mtime
    try:
        st = os.stat(path)
        if _codebook_cache is not None and _codebook_mtime == st.st_mtime:
            return _codebook_cache
        items = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
        _codebook_cache = items
        _codebook_mtime = st.st_mtime
        return items
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("codebook load error")
        return []


# ---------------------------------------------------------------------------
# GAN sidecar loader
# ---------------------------------------------------------------------------
_gan_sidecar = None


def _get_gan_sidecar():
    global _gan_sidecar
    if _gan_sidecar is not None:
        return _gan_sidecar
    module_name = "hirag_gateway_v2.sidecars.gan_checker"
    module = sys.modules.get(module_name)
    if module is None:
        sidecar_path = Path(__file__).resolve().parent / "sidecars" / "gan_checker.py"
        if not sidecar_path.exists():
            logger.warning("GAN sidecar module missing at %s", sidecar_path)
            _gan_sidecar = None
            return None
        try:
            spec = importlib.util.spec_from_file_location(module_name, sidecar_path)
            if spec is None or spec.loader is None:
                raise ImportError("unable to load gan_checker spec")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            logger.exception("Failed to import GAN sidecar module")
            _gan_sidecar = None
            return None
    try:
        _gan_sidecar = module.GanSidecar()
    except Exception:
        logger.exception("GAN sidecar init failed")
        _gan_sidecar = None
    return _gan_sidecar


# ---------------------------------------------------------------------------
# CGP persistence to Postgres
# ---------------------------------------------------------------------------
def _persist_cgp_to_db(cgp: Dict[str, Any]):
    """Persist anchors, constellations, and points to Postgres.
    This is a best-effort dev helper for Supabase Realtime; RLS must allow service inserts.
    """
    import psycopg
    conn = psycopg.connect(host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname=PGDATABASE, autocommit=False)
    try:
        with conn.cursor() as cur:
            for sn in cgp.get("super_nodes", []) or []:
                for const in sn.get("constellations", []) or []:
                    raw_anchor = const.get("anchor")
                    anchor_enc = const.get("anchor_enc")
                    anchor: Optional[List[float]] = None
                    if isinstance(raw_anchor, (list, tuple)) and len(raw_anchor) > 0:
                        anchor = [float(x) for x in raw_anchor]
                    else:
                        spectrum = const.get("spectrum")
                        if isinstance(spectrum, list) and spectrum:
                            anchor = [float(x) for x in spectrum[:3]]
                            while len(anchor) < 3:
                                anchor.append(0.0)
                        else:
                            anchor = [0.0, 0.0, 0.0]
                    dim = len(anchor)
                    cur.execute(
                        """
                        INSERT INTO public.anchors(kind, dim, anchor, anchor_enc, meta)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            'multi',
                            int(dim),
                            anchor,
                            json.dumps(anchor_enc) if anchor_enc else None,
                            json.dumps({})
                        )
                    )
                    anchor_id = cur.fetchone()[0]
                    spectrum = const.get("spectrum") if isinstance(const.get("spectrum"), list) else None
                    radial = const.get("radial_minmax") if isinstance(const.get("radial_minmax"), list) else [None, None]
                    summary = const.get("summary")
                    # insert constellation (preserve CGP/meta provenance if present)
                    const_meta = {}
                    try:
                        if isinstance(const.get("meta"), dict):
                            const_meta.update(const.get("meta") or {})
                    except Exception:
                        pass
                    try:
                        if isinstance(cgp.get("meta"), dict):
                            for k in ("namespace", "pack_id", "pack_version", "population_id", "builder_pack"):
                                v = cgp["meta"].get(k)
                                if v is not None:
                                    const_meta[k] = v
                    except Exception:
                        pass
                    cur.execute(
                        """
                        INSERT INTO public.constellations(anchor_id, summary, radial_min, radial_max, spectrum, meta)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (anchor_id, summary, radial[0] if radial else None, radial[1] if radial else None, spectrum, json.dumps(const_meta))
                    )
                    constellation_id = cur.fetchone()[0]
                    # insert points
                    pts = const.get("points", []) or []
                    for p in pts:
                        modality = p.get("modality") or p.get("mod") or 'text'
                        ref_id = p.get("ref_id") or p.get("video_id") or p.get("doc_id") or ''
                        cur.execute(
                            """
                            INSERT INTO public.shape_points(
                              constellation_id, modality, ref_id, t_start, t_end, frame_idx, token_start, token_end, proj, conf, meta)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                              constellation_id, modality, ref_id,
                              p.get("t_start"), p.get("t_end"), p.get("frame_idx"),
                              p.get("token_start"), p.get("token_end"),
                              p.get("proj"), p.get("conf"), json.dumps({k:v for k,v in p.items() if k not in {
                                'id','modality','mod','ref_id','video_id','doc_id','t_start','t_end','frame_idx','token_start','token_end','proj','conf','text'
                              }})
                            )
                        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FastAPI lifespan context manager
# ---------------------------------------------------------------------------
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Hi-RAG Gateway lifespan with geometry realtime and swarm workers."""
    global _geometry_realtime_task, _geometry_swarm_task, _geometry_swarm_stop

    # Startup
    if shape_store is None:
        logger.info("ShapeStore unavailable; geometry cache warm skipped")
    else:
        await _warm_shapes_from_supabase()
        if _geometry_realtime_task is None:
            ws_url = _derive_realtime_url()
            api_key = SUPABASE_REALTIME_KEY
            if ws_url and api_key:
                _geometry_realtime_task = asyncio.create_task(_geometry_realtime_worker(ws_url, api_key))
                logger.info("Supabase realtime geometry listener started (url=%s)", ws_url)
            else:
                logger.info("Supabase realtime subscription skipped; missing URL or API key")
        if _geometry_swarm_task is None and NATS_URL:
            if hasattr(nats, "connect"):
                _geometry_swarm_task = asyncio.create_task(_geometry_swarm_worker())
                logger.info("NATS geometry.swarm.meta listener started (url=%s)", NATS_URL)
            else:
                logger.info("NATS client unavailable; geometry.swarm.meta listener skipped")

    yield

    # Shutdown
    if _geometry_realtime_task is not None:
        _geometry_realtime_task.cancel()
        with contextlib.suppress(Exception):
            await _geometry_realtime_task
        _geometry_realtime_task = None
    if _geometry_swarm_stop is not None:
        _geometry_swarm_stop.set()
    if _geometry_swarm_task is not None:
        _geometry_swarm_task.cancel()
        with contextlib.suppress(Exception):
            await _geometry_swarm_task
        _geometry_swarm_task = None
    _geometry_swarm_stop = None
