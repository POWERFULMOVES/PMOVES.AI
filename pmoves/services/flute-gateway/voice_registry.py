"""Voice "S1" profile registry for Flute-Gateway.

Lifespan-preloaded, TTL-cached, NATS-invalidated registry that maps a
requested ``voice`` slug -> ``(provider_name, params)`` using the
``pmoves_core.voice_profiles`` table (v5_16 voice catalog) read via raw
PostgREST (the same pattern as ``main.py``'s healthz / personas calls).

Design invariants:
    * No import of ``main`` (``main`` imports this module).
    * Graceful degradation: any httpx error / 404 / table-absent / non-2xx
      response leaves the cache empty, marks the registry unhealthy, logs a
      WARNING, and returns ``False``. ``load()`` NEVER raises.
    * Providers have FIXED signatures (no ``synth_kwargs`` merge):
        - vibevoice_provider.synthesize(text, voice)
        - ultimate_tts_provider.synthesize(text, voice, engine)
        - voicebox_provider.synthesize(text, voice, engine)
      so ``select_provider_and_params`` does EXPLICIT per-engine translation
      of ``engine_specific`` into the ``(voice, engine)`` request fields the
      ``main.py`` if/elif dispatch actually reads.
    * ``pmoves_core``-schema tables (voice_profiles, personas,
      consciousness_theories) require ``Accept-Profile: pmoves_core`` on reads
      and ``Content-Profile: pmoves_core`` on writes, else PostgREST 404s.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import httpx

logger = logging.getLogger("flute-gateway.voice_registry")


def _env_int(name: str, default: int) -> int:
    """Parse an int env var, falling back (with a WARNING) on malformed input.

    A bad ``VOICE_REGISTRY_TTL_SECONDS`` must not crash module import before
    graceful degradation can even run.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning("voice_registry: invalid %s=%r; using %d", name, raw, default)
        return default


def _is_uuid(value: Any) -> bool:
    """Local UUID well-formedness check (avoids a PostgREST 400 on uuid columns)."""
    try:
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


# --- constants ---------------------------------------------------------------

DEFAULT_TTL_SECONDS = _env_int("VOICE_REGISTRY_TTL_SECONDS", 300)  # 5-min TTL
VOICE_PROFILES_TABLE = "voice_profiles"        # pmoves_core.voice_profiles via PostgREST
PMOVES_CORE_SCHEMA = "pmoves_core"             # PostgREST Accept-Profile / Content-Profile
REGISTRY_UPDATE_SUBJECT = "voice.registry.update.v1"  # NATS invalidation subject
ENGINE_VALUES = ("omnivoice", "vibevoice", "voicebox", "ultimate_tts")  # v5_16 engine_chk

# engine enum -> provider_name string understood by main.py's if/elif dispatch.
# All four engines now have a real dispatch branch on origin/main (the OmniVoice
# branch landed via the omnivoice-4090 work: synthesize(text, voice, instruct=...)).
ENGINE_TO_PROVIDER = {
    "vibevoice": "vibevoice",
    "voicebox": "voicebox",
    "ultimate_tts": "ultimate_tts",
    "omnivoice": "omnivoice",
}

# PostgREST "relation/table does not exist" markers -> treat as absent, degrade quietly.
_TABLE_ABSENT_CODES = {"PGRST205", "PGRST204", "42P01"}

# Canonical grounding contract (spec §3). Keys resolve to real substrate PKs.
GROUNDING_PK_RESOLVERS = {
    # grounding key -> (pmoves_core table, primary-key column)
    "persona_ids": ("personas", "persona_id"),               # v5_12
    "consciousness_theory_id": ("consciousness_theories", "id"),  # v5_15
}
# Allowed but not yet backed by a table/resolver -> surfaced as warnings, not errors.
GROUNDING_DEFERRED_KEYS = {"paradigm", "paradigm_proponent_ids", "proponents", "blend"}
# v5_15 has NO "shape" column -> use consciousness_theory_id instead.
GROUNDING_FORBIDDEN_KEYS = {"consciousness_shape"}


# --- value object ------------------------------------------------------------

@dataclass(frozen=True)
class VoiceProfile:
    """One resolvable voice (one row of pmoves_core.voice_profiles)."""

    name: str
    engine: str
    engine_specific: dict = field(default_factory=dict)
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: tuple[str, ...] = ()
    grounding: dict = field(default_factory=dict)
    ref_audio_path: Optional[str] = None
    sample_rate_hz: int = 24000
    rights_basis: Optional[str] = None
    is_active: bool = True
    raw: dict = field(default_factory=dict)  # original row for API echo

    @classmethod
    def from_row(cls, row: dict) -> "VoiceProfile":
        return cls(
            name=row["name"],
            engine=row["engine"],
            engine_specific=row.get("engine_specific") or {},
            display_name=row.get("display_name"),
            description=row.get("description"),
            tags=tuple(row.get("tags") or ()),
            grounding=row.get("grounding") or {},
            ref_audio_path=row.get("ref_audio_path"),
            sample_rate_hz=row.get("sample_rate_hz") or 24000,
            rights_basis=row.get("rights_basis"),
            is_active=row.get("is_active", True),
            raw=row,
        )


# --- registry cache ----------------------------------------------------------

class VoiceRegistry:
    """In-memory, TTL-refreshed cache of voice profiles."""

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._url = (supabase_url or "").rstrip("/")
        self._key = supabase_key or ""
        self._ttl = max(int(ttl_seconds), 1)
        self._cache: dict[str, VoiceProfile] = {}
        self._healthy = False
        self._loaded_at: Optional[float] = None

    # --- read headers ---
    def _read_headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            # pmoves_core schema is NOT exposed on the default public profile.
            "Accept-Profile": PMOVES_CORE_SCHEMA,
        }

    # --- loading (never raises; sets _healthy) ---
    async def load(self) -> bool:
        """Fetch all is_active=true profiles into cache. Returns _healthy.

        On httpx error / table-absent / 404 / non-2xx -> cache={}, _healthy=False,
        log WARNING, return False. NEVER raises (safe to call from lifespan).
        """
        if not self._url or not self._key:
            logger.warning("voice_registry: SUPABASE_URL/KEY unset — registry disabled")
            self._cache = {}
            self._healthy = False
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._url}/rest/v1/{VOICE_PROFILES_TABLE}",
                    headers=self._read_headers(),
                    # The service-role key bypasses the voice_profiles_read RLS
                    # predicate that excludes soft-deleted rows, so honor the
                    # soft-delete lifecycle explicitly: deleted_at IS NULL.
                    params={
                        "is_active": "eq.true",
                        "deleted_at": "is.null",
                        "select": "*",
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning("voice_registry: Supabase unreachable (%s) — registry disabled", exc)
            self._cache = {}
            self._healthy = False
            return False

        # table not migrated yet -> 404 or a PostgREST "relation absent" code
        if resp.status_code == 404 or self._is_table_absent(resp):
            logger.warning(
                "voice_registry: %s.%s absent (status=%s) — registry disabled",
                PMOVES_CORE_SCHEMA, VOICE_PROFILES_TABLE, resp.status_code,
            )
            self._cache = {}
            self._healthy = False
            return False

        if resp.status_code != 200:
            logger.warning(
                "voice_registry: load failed status=%s body=%s — registry disabled",
                resp.status_code, (resp.text or "")[:200],
            )
            self._cache = {}
            self._healthy = False
            return False

        try:
            rows = resp.json()
        except (ValueError, TypeError) as exc:
            logger.warning("voice_registry: malformed JSON (%s) — registry disabled", exc)
            self._cache = {}
            self._healthy = False
            return False

        if not isinstance(rows, list):
            logger.warning("voice_registry: unexpected payload shape — registry disabled")
            self._cache = {}
            self._healthy = False
            return False

        cache: dict[str, VoiceProfile] = {}
        for row in rows:
            try:
                profile = VoiceProfile.from_row(row)
            except (KeyError, TypeError) as exc:
                logger.warning("voice_registry: skipping malformed row (%s)", exc)
                continue
            cache[profile.name] = profile
        self._cache = cache
        self._healthy = True
        self._loaded_at = time.time()
        logger.info("voice_registry: loaded %d profiles", len(cache))
        return True

    @staticmethod
    def _is_table_absent(resp: httpx.Response) -> bool:
        try:
            body = resp.json()
        except (ValueError, TypeError):
            return False
        if isinstance(body, dict):
            code = body.get("code")
            if code in _TABLE_ABSENT_CODES:
                return True
        return False

    async def refresh(self) -> bool:
        """Alias of load() — used by the TTL loop and the NATS invalidation hook."""
        return await self.load()

    # --- reads (sync, in-memory only) ---
    def get(self, name: str) -> Optional[VoiceProfile]:
        if not name:
            return None
        return self._cache.get(name)

    def list(
        self,
        *,
        engine: Optional[str] = None,
        tag: Optional[str] = None,
        rights: Optional[str] = None,
    ) -> list[VoiceProfile]:
        out: list[VoiceProfile] = []
        for profile in self._cache.values():
            if engine is not None and profile.engine != engine:
                continue
            if tag is not None and tag not in profile.tags:
                continue
            if rights is not None and profile.rights_basis != rights:
                continue
            out.append(profile)
        return out

    def upsert_local(self, profile: VoiceProfile) -> None:
        """Warm the cache after a successful POST create (no DB round-trip)."""
        self._cache[profile.name] = profile

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def count(self) -> int:
        return len(self._cache)

    @property
    def loaded_at(self) -> Optional[float]:
        return self._loaded_at

    # --- background refresh + invalidation ---
    async def run_ttl_loop(self) -> None:
        """Periodically refresh the cache. Cancellable background task."""
        try:
            while True:
                await asyncio.sleep(self._ttl)
                await self.refresh()
        except asyncio.CancelledError:
            raise

    async def subscribe(self, nats_client) -> None:
        """Subscribe to REGISTRY_UPDATE_SUBJECT; refresh on any message.

        No-op when nats_client is None. Never raises out of startup.
        """
        if nats_client is None:
            return

        async def _on_update(_msg) -> None:
            logger.info("voice_registry: invalidation received on %s", REGISTRY_UPDATE_SUBJECT)
            await self.refresh()

        try:
            await nats_client.subscribe(REGISTRY_UPDATE_SUBJECT, cb=_on_update)
            logger.info("voice_registry: subscribed to %s", REGISTRY_UPDATE_SUBJECT)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("voice_registry: NATS subscribe failed (%s)", exc)


# --- provider/param translation ---------------------------------------------

def select_provider_and_params(
    profile: VoiceProfile,
    default_provider: str,
) -> tuple[str, dict]:
    """Map a registry row -> (provider_name, params) for main.py's dispatch.

    Providers have FIXED signatures, so this performs EXPLICIT per-engine
    translation of ``engine_specific`` into the request fields the dispatch
    reads. ``params`` only ever contains the keys ``voice`` and/or ``engine``
    (the caller copies them onto the request object before
    ``provider_name = request.provider or DEFAULT_PROVIDER`` runs).

    Per-engine ``engine_specific`` shapes (spec §3):
        * vibevoice    {voice_preset}                       -> voice
        * voicebox     {profile_id, voice_type, language}   -> voice(+engine)
        * ultimate_tts {primary_engine, <engine>_voice, ...} -> (engine, voice)
        * omnivoice    {ref_audio, instruct, ref_text}      -> (voice=ref_audio, engine=instruct)

    The omnivoice dispatch is synthesize(text, voice, instruct=request.engine),
    so ref_audio maps to ``voice`` and instruct maps to the ``engine`` slot.
    """
    es = dict(profile.engine_specific or {})
    engine = profile.engine
    params: dict[str, Any] = {}

    if engine == "vibevoice":
        provider = ENGINE_TO_PROVIDER["vibevoice"]
        voice = es.get("voice_preset")
        if voice:
            params["voice"] = voice

    elif engine == "voicebox":
        provider = ENGINE_TO_PROVIDER["voicebox"]
        voice = es.get("profile_id") or es.get("voice_type")
        if voice:
            params["voice"] = voice
        if es.get("voice_type"):
            params["engine"] = es["voice_type"]
        # NOTE: engine_specific.language has no slot in the fixed voicebox
        # dispatch signature (text, voice, engine) and is intentionally dropped.

    elif engine == "ultimate_tts":
        provider = ENGINE_TO_PROVIDER["ultimate_tts"]
        primary = es.get("primary_engine")
        if primary:
            params["engine"] = primary
            voice = es.get(f"{primary}_voice")
            if voice:
                params["voice"] = voice

    elif engine == "omnivoice":
        provider = ENGINE_TO_PROVIDER["omnivoice"]
        # main.py's omnivoice dispatch is synthesize(text, voice, instruct=request.engine):
        # ref_audio -> voice (clone reference), instruct -> engine slot (design prompt).
        ref = es.get("ref_audio") or profile.ref_audio_path
        if ref:
            params["voice"] = ref
        if es.get("instruct"):
            params["engine"] = es["instruct"]

    else:
        # unknown engine -> safest fallback (should not happen; DB CHECK enforces enum)
        provider = default_provider

    # Inject ref_audio from ref_audio_path when an engine left voice unset.
    if "voice" not in params and profile.ref_audio_path:
        params["voice"] = profile.ref_audio_path

    return provider, params


# --- validation --------------------------------------------------------------

def validate_capability(engine: str, engine_specific: dict) -> list[str]:
    """Lightweight capability-matrix check. Returns a list of error strings."""
    errors: list[str] = []
    if engine not in ENGINE_VALUES:
        errors.append(f"engine '{engine}' is not one of {ENGINE_VALUES}")
        return errors

    es = engine_specific or {}
    if not isinstance(es, dict):
        errors.append("engine_specific must be a JSON object")
        return errors

    if engine == "vibevoice":
        if not es.get("voice_preset"):
            errors.append("vibevoice requires engine_specific.voice_preset")
    elif engine == "voicebox":
        if not (es.get("profile_id") or es.get("voice_type")):
            errors.append("voicebox requires engine_specific.profile_id or engine_specific.voice_type")
    elif engine == "ultimate_tts":
        primary = es.get("primary_engine")
        if not primary:
            errors.append("ultimate_tts requires engine_specific.primary_engine")
        elif not es.get(f"{primary}_voice"):
            # select_provider_and_params reads engine_specific[f"{primary}_voice"];
            # without it the profile resolves with no provider voice.
            errors.append(f"ultimate_tts requires engine_specific.{primary}_voice")
    elif engine == "omnivoice":
        if not (es.get("ref_audio") or es.get("instruct")):
            errors.append("omnivoice requires engine_specific.ref_audio (clone) or engine_specific.instruct (design)")
    return errors


async def _resolve_pks(
    table: str,
    pk_column: str,
    values: list[str],
    *,
    supabase_url: str,
    supabase_key: str,
) -> tuple[str, set[str]]:
    """Resolve values against pmoves_core.<table>.<pk_column>.

    Returns ``(status, resolved_set)`` where status is one of:
        * ``"ok"``           — query succeeded; resolved_set holds matches.
        * ``"unreachable"``  — network error / 5xx / unconfigured → caller WARNS
                               (transient; not a rejection).
        * ``"client_error"`` — PostgREST 4xx (bad input/filter, e.g. malformed
                               UUID) → caller treats as a hard validation error.
    """
    if not values:
        return "ok", set()
    if not supabase_url or not supabase_key:
        return "unreachable", set()
    url = supabase_url.rstrip("/")
    in_list = ",".join(str(v) for v in values)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{url}/rest/v1/{table}",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Accept-Profile": PMOVES_CORE_SCHEMA,
                },
                params={pk_column: f"in.({in_list})", "select": pk_column},
            )
    except httpx.HTTPError:
        return "unreachable", set()
    if 400 <= resp.status_code < 500:
        # Bad client input (malformed filter/value) — reject, don't excuse it.
        return "client_error", set()
    if resp.status_code != 200:
        return "unreachable", set()
    try:
        rows = resp.json()
    except (ValueError, TypeError):
        return "unreachable", set()
    if not isinstance(rows, list):
        return "unreachable", set()
    return "ok", {str(r.get(pk_column)) for r in rows if isinstance(r, dict)}


async def validate_grounding(
    grounding: dict,
    *,
    supabase_url: str,
    supabase_key: str,
) -> tuple[list[str], list[str]]:
    """Validate the grounding JSONB contract.

    Returns ``(errors, warnings)``. ``errors`` empty == valid.
        * forbidden key present (consciousness_shape) -> error
        * persona_ids[] each must resolve in pmoves_core.personas
        * consciousness_theory_id must resolve in pmoves_core.consciousness_theories
        * deferred keys (paradigm/proponents/blend/...) -> warnings
        * malformed persona UUID or PostgREST 4xx -> hard error (rejected input)
        * substrate unreachable / 5xx while resolving a PK -> warning (transient)
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(grounding, dict):
        errors.append("grounding must be a JSON object")
        return errors, warnings

    for key in grounding:
        if key in GROUNDING_FORBIDDEN_KEYS:
            errors.append(
                f"grounding key '{key}' is forbidden "
                "(v5_15 has no shape column — use consciousness_theory_id)"
            )
        elif key in GROUNDING_DEFERRED_KEYS:
            warnings.append(
                f"grounding key '{key}' has no backing table yet (deferred, not validated)"
            )

    # persona_ids[] -> personas.persona_id (uuid). Validate UUIDs locally first so
    # bad input is a hard error rather than a PostgREST 400 excused as "unreachable".
    persona_ids = grounding.get("persona_ids")
    if persona_ids is not None:
        if not isinstance(persona_ids, list):
            errors.append("grounding.persona_ids must be an array")
        elif persona_ids:
            malformed = [str(v) for v in persona_ids if not _is_uuid(v)]
            if malformed:
                errors.append(f"grounding.persona_ids contains malformed UUID(s): {malformed}")
            else:
                table, pk = GROUNDING_PK_RESOLVERS["persona_ids"]
                status, resolved = await _resolve_pks(
                    table, pk, [str(v) for v in persona_ids],
                    supabase_url=supabase_url, supabase_key=supabase_key,
                )
                if status == "client_error":
                    errors.append("grounding.persona_ids rejected by substrate (invalid input)")
                elif status == "unreachable":
                    warnings.append("grounding.persona_ids unverifiable (substrate unreachable)")
                else:
                    missing = [str(v) for v in persona_ids if str(v) not in resolved]
                    if missing:
                        errors.append(f"grounding.persona_ids do not resolve in personas: {missing}")

    # consciousness_theory_id -> consciousness_theories.id (text; no UUID pre-check)
    theory_id = grounding.get("consciousness_theory_id")
    if theory_id is not None:
        if not isinstance(theory_id, str):
            errors.append("grounding.consciousness_theory_id must be a string")
        else:
            table, pk = GROUNDING_PK_RESOLVERS["consciousness_theory_id"]
            status, resolved = await _resolve_pks(
                table, pk, [theory_id],
                supabase_url=supabase_url, supabase_key=supabase_key,
            )
            if status == "client_error":
                errors.append("grounding.consciousness_theory_id rejected by substrate (invalid input)")
            elif status == "unreachable":
                warnings.append(
                    "grounding.consciousness_theory_id unverifiable (substrate unreachable)"
                )
            elif theory_id not in resolved:
                errors.append(
                    f"grounding.consciousness_theory_id does not resolve in "
                    f"consciousness_theories: {theory_id}"
                )

    return errors, warnings


def grounding_contract() -> dict:
    """Introspection payload for GET /v1/voice/validate."""
    return {
        "engines": list(ENGINE_VALUES),
        "grounding_resolved_keys": {k: {"table": v[0], "pk": v[1]} for k, v in GROUNDING_PK_RESOLVERS.items()},
        "grounding_deferred_keys": sorted(GROUNDING_DEFERRED_KEYS),
        "forbidden_keys": sorted(GROUNDING_FORBIDDEN_KEYS),
    }
