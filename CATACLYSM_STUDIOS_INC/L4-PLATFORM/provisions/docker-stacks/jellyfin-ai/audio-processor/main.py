import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
import librosa
import redis
from neo4j import GraphDatabase
from supabase import Client, create_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_PROMPT = (
    "Analyze this audio content. Describe the genre, mood, instruments, "
    "vocals, and any notable characteristics."
)


class JellyfinAuthError(Exception):
    """Raised when Jellyfin authentication fails."""


class AIProviderError(Exception):
    """Raised when an audio AI provider request fails."""


def _build_auth_payload(username: str, password: str) -> Dict[str, str]:
    device_name = os.getenv("JELLYFIN_CLIENT_DEVICE", "pmoves-jellyfin-audio-processor")
    device_id = os.getenv("JELLYFIN_CLIENT_DEVICE_ID", device_name)
    return {
        "Username": username,
        "Pw": password,
        "App": os.getenv("JELLYFIN_CLIENT_APP", "PMOVES Audio Processor"),
        "Device": device_name,
        "DeviceId": device_id,
        "DeviceName": device_name,
        "Version": os.getenv("JELLYFIN_CLIENT_VERSION", "0.0.0"),
    }


class MediaProcessor:
    def __init__(self, skip_external_clients: bool = False):
        self.jellyfin_url = os.getenv("JELLYFIN_URL", "http://jellyfin:8096").rstrip("/")
        self.jellyfin_username = os.getenv("JELLYFIN_USERNAME")
        self.jellyfin_password = os.getenv("JELLYFIN_PASSWORD")
        self.jellyfin_api_key = os.getenv("JELLYFIN_API_KEY")
        self._jellyfin_headers: Optional[Dict[str, str]] = None

        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://jellyfin-neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "mediapassword123")
        self.redis_host = os.getenv("REDIS_HOST", "jellyfin-redis")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))

        self.audio_provider = os.getenv("AUDIO_AI_PROVIDER", "auto").strip().lower()
        self.allow_cross_fallback = os.getenv("AUDIO_AI_ALLOW_CROSS_FALLBACK", "1") == "1"
        self.analysis_timeout = float(os.getenv("AUDIO_AI_TIMEOUT_SECONDS", "300"))
        self.analysis_prompt = os.getenv("AUDIO_ANALYSIS_PROMPT", DEFAULT_ANALYSIS_PROMPT)
        self.max_tokens = int(os.getenv("AUDIO_ANALYSIS_MAX_TOKENS", "500"))

        self.ollama_url = (
            os.getenv("QWEN_AUDIO_URL")
            or os.getenv("OLLAMA_AUDIO_URL")
            or "http://jellyfin-qwen-audio:11434"
        ).rstrip("/")
        self.ollama_model = (
            os.getenv("QWEN_MODEL_NAME")
            or os.getenv("OLLAMA_MODEL_NAME")
            or "hf.co/second-state/Qwen2-Audio-7B-Instruct-GGUF:Q4_K_M"
        )
        self.ollama_analyze_path = os.getenv("OLLAMA_AUDIO_ANALYZE_PATH", "/analyze")

        self.hf_audio_url = os.getenv("HUGGINGFACE_AUDIO_URL", "").strip().rstrip("/")
        self.hf_model_id = os.getenv("HUGGINGFACE_MODEL_ID", "openai/whisper-large-v3")
        self.hf_api_token = os.getenv("HUGGINGFACE_API_TOKEN") or os.getenv("HF_TOKEN")
        self.hf_wait_for_model = os.getenv("HUGGINGFACE_WAIT_FOR_MODEL", "1") == "1"
        self.hf_task = os.getenv("HUGGINGFACE_AUDIO_TASK", "auto")

        self.supabase: Optional[Client] = None
        self.neo4j_driver = None
        self.redis_client = None

        if not skip_external_clients:
            self._init_clients()

    def _init_clients(self) -> None:
        if self.supabase_url and self.supabase_key:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as exc:
                logger.warning("Supabase client disabled due to configuration error: %s", exc)
                self.supabase = None

        try:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
        except Exception as exc:
            logger.warning("Neo4j client disabled due to configuration error: %s", exc)
            self.neo4j_driver = None

        try:
            self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, db=0)
            self.redis_client.ping()
        except Exception as exc:
            logger.warning("Redis client disabled due to configuration error: %s", exc)
            self.redis_client = None

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("ErrorMessage") or payload.get("Message")
                if message:
                    return str(message)
        except ValueError:
            pass
        return response.text or "Unknown error"

    @staticmethod
    def _normalize_provider_response(payload: Any, provider: str) -> Dict[str, Any]:
        if isinstance(payload, dict):
            text = (
                payload.get("description")
                or payload.get("text")
                or payload.get("generated_text")
                or payload.get("summary")
            )
            if not text and isinstance(payload.get("result"), dict):
                text = payload["result"].get("text") or payload["result"].get("description")
            return {
                "provider": provider,
                "description": text or "",
                "analysis": payload,
            }
        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                return MediaProcessor._normalize_provider_response(payload[0], provider)
            return {"provider": provider, "description": "", "analysis": payload}
        if isinstance(payload, str):
            return {"provider": provider, "description": payload, "analysis": {"text": payload}}
        return {"provider": provider, "description": "", "analysis": {"raw": payload}}

    async def _get_jellyfin_headers(self, client: httpx.AsyncClient) -> Dict[str, str]:
        if self._jellyfin_headers:
            return self._jellyfin_headers

        if self.jellyfin_api_key:
            self._jellyfin_headers = {"X-Emby-Token": self.jellyfin_api_key}
            return self._jellyfin_headers

        if not self.jellyfin_username or not self.jellyfin_password:
            raise JellyfinAuthError(
                "Set JELLYFIN_USERNAME/JELLYFIN_PASSWORD or JELLYFIN_API_KEY."
            )

        try:
            auth_response = await client.post(
                f"{self.jellyfin_url}/Users/AuthenticateByName",
                json=_build_auth_payload(self.jellyfin_username, self.jellyfin_password),
                # Jellyfin 10.9+ rejects AuthenticateByName without a
                # MediaBrowser authorization header (400, not 401).
                headers={
                    "X-Emby-Authorization": (
                        'MediaBrowser Client="pmoves-audio-processor", '
                        'Device="audio-processor", '
                        'DeviceId="pmoves-audio-processor", Version="1.0"'
                    )
                },
            )
        except httpx.HTTPError as exc:
            raise JellyfinAuthError(f"Failed to reach Jellyfin for authentication: {exc}") from exc

        if auth_response.status_code != 200:
            detail = self._extract_error_detail(auth_response)
            raise JellyfinAuthError(
                f"Jellyfin authentication failed ({auth_response.status_code}): {detail}"
            )

        token = auth_response.json().get("AccessToken")
        if not token:
            raise JellyfinAuthError("Jellyfin authentication succeeded without access token.")

        self._jellyfin_headers = {"X-Emby-Token": token}
        return self._jellyfin_headers

    async def get_jellyfin_library(self) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.analysis_timeout) as client:
                headers = await self._get_jellyfin_headers(client)
                items_response = await client.get(
                    f"{self.jellyfin_url}/Items",
                    headers=headers,
                    params={"Recursive": True, "IncludeItemTypes": "Audio"},
                )

                if items_response.status_code == 200:
                    return items_response.json().get("Items", [])

                logger.error(
                    "Failed to fetch Jellyfin library (%s): %s",
                    items_response.status_code,
                    self._extract_error_detail(items_response),
                )
        except JellyfinAuthError as auth_error:
            logger.error("Jellyfin auth error: %s", auth_error)
        except Exception as exc:
            logger.error("Error fetching Jellyfin library: %s", exc)

        return []

    def _provider_order(self) -> List[str]:
        provider = self.audio_provider
        if provider == "auto":
            return ["ollama", "huggingface"]
        if provider == "ollama":
            return ["ollama", "huggingface"] if self.allow_cross_fallback else ["ollama"]
        if provider == "huggingface":
            return ["huggingface", "ollama"] if self.allow_cross_fallback else ["huggingface"]
        logger.warning("Unknown AUDIO_AI_PROVIDER=%s. Falling back to auto.", provider)
        return ["ollama", "huggingface"]

    async def _analyze_with_ollama(self, audio_path: str) -> Dict[str, Any]:
        analyze_url = f"{self.ollama_url}{self.ollama_analyze_path}"
        try:
            async with httpx.AsyncClient(timeout=self.analysis_timeout) as client:
                with open(audio_path, "rb") as audio_file:
                    files = {"audio": audio_file}
                    data = {"prompt": self.analysis_prompt, "max_tokens": str(self.max_tokens)}
                    response = await client.post(analyze_url, files=files, data=data)

                if response.status_code >= 400:
                    raise AIProviderError(
                        f"Ollama analyze endpoint failed ({response.status_code}): "
                        f"{self._extract_error_detail(response)}"
                    )

                payload = response.json()
                return self._normalize_provider_response(payload, "ollama")
        except FileNotFoundError as exc:
            raise AIProviderError(f"Audio file missing: {audio_path}") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIProviderError("Ollama returned invalid JSON.") from exc

    async def _analyze_with_huggingface(self, audio_path: str) -> Dict[str, Any]:
        headers: Dict[str, str] = {}
        if self.hf_api_token:
            headers["Authorization"] = f"Bearer {self.hf_api_token}"

        try:
            async with httpx.AsyncClient(timeout=self.analysis_timeout) as client:
                if self.hf_audio_url:
                    with open(audio_path, "rb") as audio_file:
                        files = {"audio": audio_file}
                        data = {
                            "prompt": self.analysis_prompt,
                            "max_tokens": str(self.max_tokens),
                            "task": self.hf_task,
                            "model": self.hf_model_id,
                        }
                        response = await client.post(
                            self.hf_audio_url, headers=headers, files=files, data=data
                        )
                else:
                    infer_url = f"https://api-inference.huggingface.co/models/{self.hf_model_id}"
                    params = {"wait_for_model": "true" if self.hf_wait_for_model else "false"}
                    with open(audio_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                    response = await client.post(
                        infer_url,
                        headers=headers,
                        params=params,
                        content=audio_bytes,
                    )

                if response.status_code >= 400:
                    raise AIProviderError(
                        f"HuggingFace request failed ({response.status_code}): "
                        f"{self._extract_error_detail(response)}"
                    )

                payload = response.json()
                return self._normalize_provider_response(payload, "huggingface")
        except FileNotFoundError as exc:
            raise AIProviderError(f"Audio file missing: {audio_path}") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"HuggingFace request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIProviderError("HuggingFace returned invalid JSON.") from exc

    async def analyze_audio_with_ai(self, audio_path: str) -> Dict[str, Any]:
        errors: List[str] = []
        for provider in self._provider_order():
            try:
                if provider == "ollama":
                    result = await self._analyze_with_ollama(audio_path)
                else:
                    result = await self._analyze_with_huggingface(audio_path)
                if result.get("description") or result.get("analysis"):
                    return result
            except AIProviderError as exc:
                msg = f"{provider}:{exc}"
                errors.append(msg)
                logger.warning("Audio provider failed (%s), trying fallback if available.", msg)
            except Exception as exc:
                msg = f"{provider}:unexpected:{exc}"
                errors.append(msg)
                logger.warning("Unexpected provider error (%s), trying fallback if available.", msg)

        return {
            "provider": "none",
            "description": "",
            "analysis": {"errors": errors},
        }

    def extract_audio_features(self, audio_path: str) -> Dict[str, Any]:
        try:
            y, sr = librosa.load(audio_path)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
            return {
                "tempo": float(tempo),
                "duration": float(len(y) / sr),
                "mfcc_mean": mfccs.mean(axis=1).tolist(),
                "spectral_centroid_mean": float(spectral_centroids.mean()),
                "spectral_rolloff_mean": float(spectral_rolloff.mean()),
                "zero_crossing_rate_mean": float(zero_crossing_rate.mean()),
                "sample_rate": int(sr),
            }
        except Exception as exc:
            logger.error("Error extracting audio features: %s", exc)
            return {}

    def _is_processed(self, media_id: Optional[str]) -> bool:
        if not self.redis_client or not media_id:
            return False
        try:
            return bool(self.redis_client.get(f"processed:{media_id}"))
        except Exception as exc:
            logger.warning("Redis read failed: %s", exc)
            return False

    def _mark_processed(self, media_id: Optional[str]) -> None:
        if not self.redis_client or not media_id:
            return
        try:
            self.redis_client.setex(f"processed:{media_id}", 86400, "1")
        except Exception as exc:
            logger.warning("Redis write failed: %s", exc)

    def store_in_neo4j(self, media_data: Dict[str, Any], analysis_data: Dict[str, Any], features: Dict[str, Any]) -> None:
        if not self.neo4j_driver:
            logger.info("Neo4j client not configured; skipping Neo4j storage.")
            return
        try:
            with self.neo4j_driver.session() as session:
                session.run(
                    """
                    MERGE (m:Media {id: $media_id})
                    SET m.name = $name,
                        m.path = $path,
                        m.type = $type,
                        m.duration = $duration,
                        m.created_at = datetime()
                    """,
                    media_id=media_data.get("Id"),
                    name=media_data.get("Name"),
                    path=media_data.get("Path"),
                    type=media_data.get("Type"),
                    duration=features.get("duration", 0),
                )

                if analysis_data:
                    session.run(
                        """
                        MATCH (m:Media {id: $media_id})
                        MERGE (a:Analysis {media_id: $media_id})
                        SET a.ai_description = $description,
                            a.ai_analysis = $analysis,
                            a.provider = $provider,
                            a.created_at = datetime()
                        MERGE (m)-[:HAS_ANALYSIS]->(a)
                        """,
                        media_id=media_data.get("Id"),
                        description=analysis_data.get("description", ""),
                        analysis=json.dumps(analysis_data.get("analysis", analysis_data)),
                        provider=analysis_data.get("provider", "unknown"),
                    )

                if features:
                    session.run(
                        """
                        MATCH (m:Media {id: $media_id})
                        MERGE (f:AudioFeatures {media_id: $media_id})
                        SET f += $features,
                            f.created_at = datetime()
                        MERGE (m)-[:HAS_FEATURES]->(f)
                        """,
                        media_id=media_data.get("Id"),
                        features=features,
                    )
        except Exception as exc:
            logger.error("Error storing in Neo4j: %s", exc)

    def store_in_supabase(self, media_data: Dict[str, Any], analysis_data: Dict[str, Any], features: Dict[str, Any]) -> None:
        if not self.supabase:
            logger.info("Supabase client not configured; skipping Supabase storage.")
            return

        try:
            media_record = {
                "jellyfin_id": media_data.get("Id"),
                "name": media_data.get("Name"),
                "path": media_data.get("Path"),
                "type": media_data.get("Type"),
                "duration": features.get("duration", 0),
                "created_at": "now()",
            }
            result = self.supabase.table("media").upsert(media_record).execute()

            if result.data and analysis_data:
                media_id = result.data[0]["id"]
                analysis_record = {
                    "media_id": media_id,
                    "ai_description": analysis_data.get("description", ""),
                    "ai_analysis": analysis_data.get("analysis", analysis_data),
                    "audio_features": features,
                    "provider": analysis_data.get("provider", "unknown"),
                    "created_at": "now()",
                }
                self.supabase.table("media_analysis").insert(analysis_record).execute()
        except Exception as exc:
            logger.error("Error storing in Supabase: %s", exc)

    async def process_media_item(self, item: Dict[str, Any]) -> None:
        try:
            media_path = item.get("Path", "")
            if not media_path or not os.path.exists(media_path):
                logger.warning("Media file not found: %s", media_path)
                return

            media_id = item.get("Id")
            if self._is_processed(media_id):
                logger.info("Already processed: %s", item.get("Name"))
                return

            logger.info("Processing: %s", item.get("Name", "Unknown"))
            features = self.extract_audio_features(media_path)
            analysis = await self.analyze_audio_with_ai(media_path)
            self.store_in_neo4j(item, analysis, features)
            self.store_in_supabase(item, analysis, features)
            self._mark_processed(media_id)
            logger.info("Completed processing: %s", item.get("Name", "Unknown"))
        except Exception as exc:
            logger.error("Error processing media item: %s", exc)

    async def run(self) -> None:
        logger.info(
            "Starting media processor with AUDIO_AI_PROVIDER=%s (cross_fallback=%s)",
            self.audio_provider,
            self.allow_cross_fallback,
        )
        while True:
            try:
                media_items = await self.get_jellyfin_library()
                logger.info("Found %d media items", len(media_items))
                for item in media_items:
                    await self.process_media_item(item)
                    await asyncio.sleep(1)

                interval = int(os.getenv("PROCESSING_INTERVAL", "300"))
                logger.info("Waiting %d seconds before next scan...", interval)
                await asyncio.sleep(interval)
            except Exception as exc:
                logger.error("Error in main loop: %s", exc)
                await asyncio.sleep(60)

    def shutdown(self) -> None:
        if self.neo4j_driver:
            try:
                self.neo4j_driver.close()
            except Exception as exc:
                logger.warning("Neo4j shutdown warning: %s", exc)

        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as exc:
                logger.warning("Redis shutdown warning: %s", exc)


async def main() -> None:
    processor = MediaProcessor()
    try:
        await processor.run()
    finally:
        processor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
