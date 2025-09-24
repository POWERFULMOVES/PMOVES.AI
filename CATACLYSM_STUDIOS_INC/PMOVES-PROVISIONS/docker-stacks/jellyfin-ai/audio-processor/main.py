
import asyncio
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
import json
import time

import httpx
from supabase import create_client, Client
from neo4j import GraphDatabase
import redis
from pydub import AudioSegment
import librosa
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JellyfinAuthError(Exception):
    """Raised when Jellyfin authentication fails."""


class MediaProcessor:
    def __init__(self):
        self.jellyfin_url = os.getenv("JELLYFIN_URL", "http://jellyfin:8096")
        self.jellyfin_username = os.getenv("JELLYFIN_USERNAME")
        self.jellyfin_password = os.getenv("JELLYFIN_PASSWORD")
        self.jellyfin_api_key = os.getenv("JELLYFIN_API_KEY")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "mediapassword123")
        self.qwen_url = os.getenv("QWEN_AUDIO_URL", "http://qwen-audio:8000")

        # Initialize clients
        self.supabase: Optional[Client] = None
        if self.supabase_url and self.supabase_key:
            self.supabase = create_client(self.supabase_url, self.supabase_key)

        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri,

class MediaProcessor:
    def __init__(self):

        self.jellyfin_url = os.getenv("JELLYFIN_URL", "http://jellyfin:8096")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "mediapassword123")
        self.qwen_url = os.getenv("QWEN_AUDIO_URL", "http://qwen-audio:8000")

        self.jellyfin_url = os.getenv("JELLYFIN_URL", "http://jellyfin:8096")
        self.jellyfin_username = os.getenv("JELLYFIN_USERNAME")
        self.jellyfin_password = os.getenv("JELLYFIN_PASSWORD")
        self.jellyfin_api_key = os.getenv("JELLYFIN_API_KEY")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "mediapassword123")
        self.qwen_url = os.getenv("QWEN_AUDIO_URL", "http://qwen-audio:8000")
        self._jellyfin_headers: Optional[Dict[str, str]] = None


        # Initialize clients
        self.supabase: Optional[Client] = None
        if self.supabase_url and self.supabase_key:
            self.supabase = create_client(self.supabase_url, self.supabase_key)

        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri,

            auth=(self.neo4j_user, self.neo4j_password)
        )

        self.redis_client = redis.Redis(host='redis', port=6379, db=0)


    async def _build_jellyfin_headers(self, client: httpx.AsyncClient) -> Dict[str, str]:
        """Create headers for authenticated Jellyfin requests."""
        if self.jellyfin_api_key:
            return {"X-Emby-Token": self.jellyfin_api_key}

        if not self.jellyfin_username or not self.jellyfin_password:
            raise JellyfinAuthError(
                "Jellyfin credentials are not configured. Set JELLYFIN_USERNAME and "
                "JELLYFIN_PASSWORD or provide JELLYFIN_API_KEY."
            )

        try:
            auth_response = await client.post(
                f"{self.jellyfin_url}/Users/AuthenticateByName",
                json={"Username": self.jellyfin_username, "Pw": self.jellyfin_password}
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
            raise JellyfinAuthError("Jellyfin authentication response did not include an access token.")

        return {"X-Emby-Token": token}

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Attempt to extract a helpful error message from a Jellyfin response."""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("ErrorMessage") or payload.get("Message")
                if message:
                    return message
        except ValueError:
            pass

        return response.text or "Unknown error"

    async def get_jellyfin_library(self) -> List[Dict]:
        """Fetch media library from Jellyfin"""
        try:
            async with httpx.AsyncClient() as client:
                headers = await self._build_jellyfin_headers(client)

                items_response = await client.get(
                    f"{self.jellyfin_url}/Items",
                    headers=headers,
                    params={"Recursive": True, "IncludeItemTypes": "Audio"}
                )

                if items_response.status_code == 200:
                    return items_response.json().get("Items", [])

                logger.error(
                    "Failed to fetch Jellyfin library (%s): %s",
                    items_response.status_code,
                    self._extract_error_detail(items_response)
                )

        except JellyfinAuthError as auth_error:
            logger.error(str(auth_error))
        except Exception as e:
            logger.error(f"Error fetching Jellyfin library: {e}")

        return []

    async def _get_jellyfin_headers(self, client: httpx.AsyncClient) -> Optional[Dict[str, str]]:
        """Authenticate with Jellyfin and return auth headers."""
        if self._jellyfin_headers:
            return self._jellyfin_headers

        if self.jellyfin_api_key:
            self._jellyfin_headers = {"X-MediaBrowser-Token": self.jellyfin_api_key}
            return self._jellyfin_headers

        if not self.jellyfin_username or not self.jellyfin_password:
            logger.error(
                "Jellyfin credentials are not configured. Set JELLYFIN_USERNAME and JELLYFIN_PASSWORD or provide JELLYFIN_API_KEY."
            )
            return None

        try:
            auth_response = await client.post(
                f"{self.jellyfin_url}/Users/AuthenticateByName",
                json={"Username": self.jellyfin_username, "Pw": self.jellyfin_password}
            )

            if auth_response.status_code == 200:
                data = auth_response.json()
                token = data.get("AccessToken")
                if not token:
                    logger.error("Jellyfin authentication succeeded but no access token was returned.")
                    return None

                self._jellyfin_headers = {"X-MediaBrowser-Token": token}
                return self._jellyfin_headers

            logger.error(
                "Failed to authenticate with Jellyfin (status %s): %s",
                auth_response.status_code,
                auth_response.text
            )
        except Exception as exc:
            logger.error(f"Error authenticating with Jellyfin: {exc}")

        return None

    async def get_jellyfin_library(self) -> List[Dict]:
        """Fetch media library from Jellyfin"""
        try:
            async with httpx.AsyncClient() as client:
                headers = await self._get_jellyfin_headers(client)
                if not headers:
                    return []

                items_response = await client.get(
                    f"{self.jellyfin_url}/Items",
                    headers=headers,
                    params={"Recursive": True, "IncludeItemTypes": "Audio"}
                )

                if items_response.status_code == 200:
                    return items_response.json().get("Items", [])

                logger.error(
                    "Failed to fetch Jellyfin items (status %s): %s",
                    items_response.status_code,
                    items_response.text
                )

        except Exception as e:
            logger.error(f"Error fetching Jellyfin library: {e}")

        return []


    async def analyze_audio_with_qwen(self, audio_path: str) -> Dict:
        """Send audio to Qwen for analysis"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(audio_path, 'rb') as audio_file:
                    files = {'audio': audio_file}
                    data = {
                        'prompt': 'Analyze this audio content. Describe the genre, mood, instruments, vocals, and any notable characteristics.',
                        'max_tokens': 500
                    }

                    response = await client.post(
                        f"{self.qwen_url}/analyze",
                        files=files,
                        data=data
                    )

                    if response.status_code == 200:
                        return response.json()

        except Exception as e:
            logger.error(f"Error analyzing audio with Qwen: {e}")

        return {}

    def extract_audio_features(self, audio_path: str) -> Dict:
        """Extract technical audio features using librosa"""
        try:
            y, sr = librosa.load(audio_path)

            # Extract features
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)

            return {
                'tempo': float(tempo),
                'duration': float(len(y) / sr),
                'mfcc_mean': mfccs.mean(axis=1).tolist(),
                'spectral_centroid_mean': float(spectral_centroids.mean()),
                'spectral_rolloff_mean': float(spectral_rolloff.mean()),
                'zero_crossing_rate_mean': float(zero_crossing_rate.mean()),
                'sample_rate': int(sr)
            }

        except Exception as e:
            logger.error(f"Error extracting audio features: {e}")
            return {}

    def store_in_neo4j(self, media_data: Dict, analysis_data: Dict, features: Dict):
        """Store media and analysis data in Neo4j"""
        try:
            with self.neo4j_driver.session() as session:
                # Create media node
                session.run("""
                    MERGE (m:Media {id: $media_id})
                    SET m.name = $name,
                        m.path = $path,
                        m.type = $type,
                        m.duration = $duration,
                        m.created_at = datetime()
                """, 
                media_id=media_data.get('Id'),
                name=media_data.get('Name'),
                path=media_data.get('Path'),
                type=media_data.get('Type'),
                duration=features.get('duration', 0)
                )

                # Create analysis node
                if analysis_data:
                    session.run("""
                        MATCH (m:Media {id: $media_id})
                        MERGE (a:Analysis {media_id: $media_id})
                        SET a.ai_description = $description,
                            a.ai_analysis = $analysis,
                            a.created_at = datetime()
                        MERGE (m)-[:HAS_ANALYSIS]->(a)
                    """,
                    media_id=media_data.get('Id'),
                    description=analysis_data.get('description', ''),
                    analysis=json.dumps(analysis_data)
                    )

                # Create features node
                if features:
                    session.run("""
                        MATCH (m:Media {id: $media_id})
                        MERGE (f:AudioFeatures {media_id: $media_id})
                        SET f += $features,
                            f.created_at = datetime()
                        MERGE (m)-[:HAS_FEATURES]->(f)
                    """,
                    media_id=media_data.get('Id'),
                    features=features
                    )

        except Exception as e:
            logger.error(f"Error storing in Neo4j: {e}")

    def store_in_supabase(self, media_data: Dict, analysis_data: Dict, features: Dict):
        """Store data in Supabase"""
        try:
            if not self.supabase:
                logger.info("Supabase client not configured; skipping Supabase storage.")
                return

            # Store in media table
            media_record = {
                'jellyfin_id': media_data.get('Id'),
                'name': media_data.get('Name'),
                'path': media_data.get('Path'),
                'type': media_data.get('Type'),
                'duration': features.get('duration', 0),
                'created_at': 'now()'
            }

            result = self.supabase.table('media').upsert(media_record).execute()

            if result.data and analysis_data:
                media_id = result.data[0]['id']

                # Store analysis
                analysis_record = {
                    'media_id': media_id,
                    'ai_description': analysis_data.get('description', ''),
                    'ai_analysis': analysis_data,
                    'audio_features': features,
                    'created_at': 'now()'
                }

                self.supabase.table('media_analysis').insert(analysis_record).execute()

        except Exception as e:
            logger.error(f"Error storing in Supabase: {e}")

    async def process_media_item(self, item: Dict):
        """Process a single media item"""
        try:
            media_path = item.get('Path', '')
            if not media_path or not os.path.exists(media_path):
                logger.warning(f"Media file not found: {media_path}")
                return

            logger.info(f"Processing: {item.get('Name', 'Unknown')}")

            # Check if already processed
            cache_key = f"processed:{item.get('Id')}"
            if self.redis_client.get(cache_key):
                logger.info(f"Already processed: {item.get('Name')}")
                return

            # Extract audio features
            features = self.extract_audio_features(media_path)

            # Analyze with AI
            analysis = await self.analyze_audio_with_qwen(media_path)

            # Store in databases
            self.store_in_neo4j(item, analysis, features)
            self.store_in_supabase(item, analysis, features)

            # Mark as processed
            self.redis_client.setex(cache_key, 86400, "1")  # Cache for 24 hours

            logger.info(f"Completed processing: {item.get('Name')}")

        except Exception as e:
            logger.error(f"Error processing media item: {e}")

    async def run(self):
        """Main processing loop"""
        logger.info("Starting media processor...")

        while True:
            try:
                # Get media library from Jellyfin
                media_items = await self.get_jellyfin_library()
                logger.info(f"Found {len(media_items)} media items")

                # Process items
                for item in media_items:
                    await self.process_media_item(item)
                    await asyncio.sleep(1)  # Rate limiting

                # Wait before next scan
                interval = int(os.getenv("PROCESSING_INTERVAL", "300"))
                logger.info(f"Waiting {interval} seconds before next scan...")
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    processor = MediaProcessor()
    asyncio.run(processor.run())
