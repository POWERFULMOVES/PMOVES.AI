"""
PMOVES.AI Qdrant Integration
High-performance vector search alongside Supabase
Optimized for CoCa embeddings and hybrid RAG
"""

import os
import sys
from pathlib import Path
import asyncio
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import json
from datetime import datetime
import hashlib
import logging

# Qdrant imports
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    Filter, FieldCondition, MatchValue,
    SearchRequest, SearchParams, ScoreModifier,
    CollectionInfo, OptimizersConfigDiff,
    CreateCollection, UpdateCollection,
    PointIdsList, PointGroups, Record
)
from qdrant_client.http import models

# Async database support
import asyncpg
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PMOVES.Qdrant")

@dataclass
class PMOVESConfig:
    """Configuration for PMOVES.AI Qdrant integration"""
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    qdrant_https: bool = os.getenv("QDRANT_HTTPS", "false").lower() == "true"
    
    supabase_url: str = os.getenv("SUPABASE_URL")
    supabase_key: str = os.getenv("SUPABASE_KEY")
    supabase_db_url: str = os.getenv("SUPABASE_DB_URL")  # Direct PostgreSQL connection
    
    embedding_dim: int = 3584  # Hugging Face dimension
    collection_name: str = "pmoves_youtube_coca"
    batch_size: int = 100
    
    # Performance settings
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_search_results: int = 20
    similarity_threshold: float = 0.3

class QdrantPMOVESManager:
    """
    Manages Qdrant collections for PMOVES.AI YouTube RAG system
    Provides high-performance vector search with CoCa embeddings
    """
    
    def __init__(self, config: PMOVESConfig):
        self.config = config
        
        # Initialize Qdrant clients
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            api_key=config.qdrant_api_key,
            https=config.qdrant_https
        )
        
        self.async_client = AsyncQdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            api_key=config.qdrant_api_key,
            https=config.qdrant_https
        )
        
        # Collections for different embedding types
        self.collections = {
            "text": f"{config.collection_name}_text",
            "context": f"{config.collection_name}_context",
            "contrastive": f"{config.collection_name}_contrastive",
            "combined": f"{config.collection_name}_combined",
            "summaries": f"{config.collection_name}_summaries"
        }
        
        # Cache for recent searches
        self.search_cache = {} if config.enable_cache else None
        
        logger.info(f"Initialized PMOVES Qdrant Manager with collections: {self.collections}")
    
    async def initialize_collections(self):
        """Create and configure all Qdrant collections"""
        
        for collection_type, collection_name in self.collections.items():
            try:
                # Check if collection exists
                collections = await self.async_client.get_collections()
                exists = any(c.name == collection_name for c in collections.collections)
                
                if not exists:
                    # Create collection with optimized settings
                    await self.async_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.config.embedding_dim,
                            distance=Distance.COSINE,
                            on_disk=False  # Keep in memory for speed
                        ),
                        optimizers_config=OptimizersConfigDiff(
                            indexing_threshold=10000,
                            flush_interval_sec=5,
                            memmap_threshold=50000
                        ),
                        on_disk_payload=False  # Keep payload in memory
                    )
                    
                    logger.info(f"Created collection: {collection_name}")
                    
                    # Create indexes for metadata filtering
                    await self.async_client.create_field_index(
                        collection_name=collection_name,
                        field_name="video_id",
                        field_type="keyword"
                    )
                    
                    await self.async_client.create_field_index(
                        collection_name=collection_name,
                        field_name="segment_id",
                        field_type="integer"
                    )
                    
                    if collection_type == "summaries":
                        await self.async_client.create_field_index(
                            collection_name=collection_name,
                            field_name="chunk_id",
                            field_type="integer"
                        )
                else:
                    # Update collection settings if needed
                    info = await self.async_client.get_collection(collection_name)
                    logger.info(f"Collection {collection_name} exists with {info.points_count} points")
                    
            except Exception as e:
                logger.error(f"Error initializing collection {collection_name}: {e}")
                raise
    
    async def sync_from_supabase(self, full_sync: bool = False):
        """
        Sync embeddings from Supabase to Qdrant
        
        Args:
            full_sync: If True, sync all data. If False, sync only new/updated
        """
        
        logger.info(f"Starting {'full' if full_sync else 'incremental'} sync from Supabase")
        
        # Connect to Supabase PostgreSQL directly
        conn = await asyncpg.connect(self.config.supabase_db_url)
        
        try:
            # Determine sync query
            if full_sync:
                query = """
                    SELECT 
                        id, video_id, segment_id, text,
                        timestamped_url, start_seconds, end_seconds,
                        text_embedding, context_embedding,
                        contrastive_embedding, combined_embedding,
                        embedding_generated_at
                    FROM pmoves.youtube_segments
                    WHERE text_embedding IS NOT NULL
                    ORDER BY video_id, segment_id
                """
            else:
                # Get last sync time from Qdrant metadata
                last_sync = await self._get_last_sync_time()
                query = """
                    SELECT 
                        id, video_id, segment_id, text,
                        timestamped_url, start_seconds, end_seconds,
                        text_embedding, context_embedding,
                        contrastive_embedding, combined_embedding,
                        embedding_generated_at
                    FROM pmoves.youtube_segments
                    WHERE text_embedding IS NOT NULL
                    AND created_at > $1
                    ORDER BY video_id, segment_id
                """
                
            # Fetch data
            rows = await conn.fetch(query) if full_sync else await conn.fetch(query, last_sync)
            
            logger.info(f"Found {len(rows)} segments to sync")
            
            # Process in batches
            for i in range(0, len(rows), self.config.batch_size):
                batch = rows[i:i + self.config.batch_size]
                await self._process_sync_batch(batch)
                
                if (i + self.config.batch_size) % 500 == 0:
                    logger.info(f"Processed {i + self.config.batch_size} segments")
            
            # Sync summaries
            await self._sync_summaries(conn, full_sync)
            
            # Update sync timestamp
            await self._update_last_sync_time()
            
            logger.info("Sync completed successfully")
            
        finally:
            await conn.close()
    
    async def _process_sync_batch(self, batch: List[asyncpg.Record]):
        """Process a batch of records for syncing to Qdrant"""
        
        # Prepare points for each embedding type
        points = {
            "text": [],
            "context": [],
            "contrastive": [],
            "combined": []
        }
        
        for record in batch:
            # Create unique point ID
            point_id = self._generate_point_id(record['video_id'], record['segment_id'])
            
            # Common payload
            payload = {
                "video_id": record['video_id'],
                "segment_id": record['segment_id'],
                "text": record['text'],
                "timestamped_url": record['timestamped_url'],
                "start_seconds": float(record['start_seconds']),
                "end_seconds": float(record['end_seconds']),
                "db_id": record['id']
            }
            
            # Add points for each embedding type
            if record['text_embedding']:
                points["text"].append(PointStruct(
                    id=point_id,
                    vector=record['text_embedding'],
                    payload={**payload, "embedding_type": "text"}
                ))
            
            if record['context_embedding']:
                points["context"].append(PointStruct(
                    id=point_id,
                    vector=record['context_embedding'],
                    payload={**payload, "embedding_type": "context"}
                ))
            
            if record['contrastive_embedding']:
                points["contrastive"].append(PointStruct(
                    id=point_id,
                    vector=record['contrastive_embedding'],
                    payload={**payload, "embedding_type": "contrastive"}
                ))
            
            if record['combined_embedding']:
                points["combined"].append(PointStruct(
                    id=point_id,
                    vector=record['combined_embedding'],
                    payload={**payload, "embedding_type": "combined"}
                ))
        
        # Upsert points to respective collections
        for embedding_type, point_list in points.items():
            if point_list:
                await self.async_client.upsert(
                    collection_name=self.collections[embedding_type],
                    points=point_list,
                    wait=True
                )
    
    async def coca_search(
        self,
        query_embeddings: Dict[str, np.ndarray],
        search_params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Perform CoCa-enhanced search across multiple embedding spaces
        
        Args:
            query_embeddings: Dict with keys 'text', 'context', 'contrastive', 'combined'
            search_params: Optional search parameters
        
        Returns:
            List of search results with scores
        """
        
        # Check cache first
        cache_key = self._generate_cache_key(query_embeddings, search_params)
        if self.search_cache and cache_key in self.search_cache:
            cached_result, cached_time = self.search_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.config.cache_ttl:
                logger.debug("Returning cached search results")
                return cached_result
        
        # Default search parameters
        params = {
            "limit": self.config.max_search_results,
            "score_threshold": self.config.similarity_threshold,
            "with_payload": True,
            "with_vectors": False
        }
        if search_params:
            params.update(search_params)
        
        # Perform parallel searches across collections
        search_tasks = []
        weights = {
            "text": 0.4,
            "context": 0.2,
            "contrastive": 0.2,
            "combined": 0.2
        }
        
        for embedding_type, query_vector in query_embeddings.items():
            if query_vector is not None and embedding_type in self.collections:
                search_tasks.append(
                    self._search_collection(
                        collection_name=self.collections[embedding_type],
                        query_vector=query_vector.tolist(),
                        params=params,
                        weight=weights.get(embedding_type, 0.25)
                    )
                )
        
        # Execute searches in parallel
        search_results = await asyncio.gather(*search_tasks)
        
        # Combine and re-rank results
        combined_results = self._combine_search_results(search_results)
        
        # Apply diversity filtering
        final_results = self._apply_diversity_filter(combined_results)
        
        # Cache results
        if self.search_cache:
            self.search_cache[cache_key] = (final_results, datetime.now())
        
        return final_results
    
    async def _search_collection(
        self,
        collection_name: str,
        query_vector: List[float],
        params: Dict,
        weight: float
    ) -> Tuple[str, List[Dict], float]:
        """Search a single collection"""
        
        try:
            results = await self.async_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=params["limit"],
                score_threshold=params["score_threshold"],
                with_payload=params["with_payload"],
                with_vectors=params["with_vectors"]
            )
            
            # Convert results to dict format with weighted scores
            formatted_results = []
            for hit in results:
                result = {
                    "id": hit.id,
                    "score": hit.score * weight,
                    "collection": collection_name,
                    **hit.payload
                }
                formatted_results.append(result)
            
            return (collection_name, formatted_results, weight)
            
        except Exception as e:
            logger.error(f"Error searching collection {collection_name}: {e}")
            return (collection_name, [], weight)
    
    def _combine_search_results(
        self,
        search_results: List[Tuple[str, List[Dict], float]]
    ) -> List[Dict]:
        """Combine results from multiple collections with score aggregation"""
        
        # Aggregate scores by unique segments
        segment_scores = {}
        
        for collection, results, weight in search_results:
            for result in results:
                key = f"{result['video_id']}_{result['segment_id']}"
                
                if key not in segment_scores:
                    segment_scores[key] = {
                        **result,
                        "scores_by_type": {},
                        "combined_score": 0
                    }
                
                # Track individual scores
                embedding_type = collection.split('_')[-1]
                segment_scores[key]["scores_by_type"][embedding_type] = result["score"]
                segment_scores[key]["combined_score"] += result["score"]
        
        # Sort by combined score
        sorted_results = sorted(
            segment_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:self.config.max_search_results]
    
    def _apply_diversity_filter(
        self,
        results: List[Dict],
        diversity_threshold: float = 0.7
    ) -> List[Dict]:
        """Apply diversity filtering to prevent redundant results"""
        
        filtered_results = []
        seen_videos = {}
        
        for result in results:
            video_id = result["video_id"]
            segment_id = result["segment_id"]
            
            # Check if we've seen too many segments from this video
            if video_id in seen_videos:
                # Check temporal proximity to existing segments
                is_diverse = True
                for seen_segment in seen_videos[video_id]:
                    if abs(segment_id - seen_segment) <= 2:  # Within 2 segments
                        is_diverse = False
                        break
                
                if is_diverse:
                    filtered_results.append(result)
                    seen_videos[video_id].append(segment_id)
            else:
                filtered_results.append(result)
                seen_videos[video_id] = [segment_id]
        
        return filtered_results
    
    async def add_feedback(
        self,
        query_id: str,
        result_id: str,
        feedback_type: str,
        score: float
    ):
        """Add user feedback for result improvement"""
        
        # Store feedback in Qdrant metadata
        feedback_data = {
            "query_id": query_id,
            "result_id": result_id,
            "feedback_type": feedback_type,
            "score": score,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update point metadata with feedback
        for collection in self.collections.values():
            try:
                await self.async_client.set_payload(
                    collection_name=collection,
                    points=[result_id],
                    payload={"feedback": feedback_data},
                    wait=False
                )
            except:
                pass  # Point might not exist in all collections
    
    def _generate_point_id(self, video_id: str, segment_id: int) -> str:
        """Generate unique point ID"""
        return hashlib.md5(f"{video_id}_{segment_id}".encode()).hexdigest()
    
    def _generate_cache_key(self, embeddings: Dict, params: Optional[Dict]) -> str:
        """Generate cache key for search results"""
        key_parts = []
        
        for embed_type, vector in embeddings.items():
            if vector is not None:
                # Use first few dimensions for cache key
                key_parts.append(f"{embed_type}_{hash(vector.tobytes())}")
        
        if params:
            key_parts.append(str(sorted(params.items())))
        
        return hashlib.md5("_".join(key_parts).encode()).hexdigest()
    
    async def _get_last_sync_time(self) -> datetime:
        """Get last sync timestamp from Qdrant metadata"""
        try:
            # Store sync metadata in a special collection
            metadata = await self.async_client.get_collection("pmoves_metadata")
            # Implementation would retrieve actual timestamp
            return datetime.now() - timedelta(days=1)  # Default to 1 day ago
        except:
            return datetime.min
    
    async def _update_last_sync_time(self):
        """Update last sync timestamp in Qdrant"""
        # Store current timestamp in metadata collection
        pass
    
    async def _sync_summaries(self, conn: asyncpg.Connection, full_sync: bool):
        """Sync summary embeddings from Supabase"""
        
        query = """
            SELECT 
                id, video_id, chunk_id, summary_text,
                segment_ids, start_seconds, end_seconds,
                summary_embedding
            FROM pmoves.youtube_summaries
            WHERE summary_embedding IS NOT NULL
            ORDER BY video_id, chunk_id
        """
        
        rows = await conn.fetch(query)
        
        points = []
        for record in rows:
            point_id = self._generate_point_id(
                f"{record['video_id']}_summary",
                record['chunk_id']
            )
            
            points.append(PointStruct(
                id=point_id,
                vector=record['summary_embedding'],
                payload={
                    "video_id": record['video_id'],
                    "chunk_id": record['chunk_id'],
                    "summary_text": record['summary_text'],
                    "segment_ids": record['segment_ids'],
                    "start_seconds": float(record['start_seconds']),
                    "end_seconds": float(record['end_seconds']),
                    "embedding_type": "summary"
                }
            ))
        
        if points:
            await self.async_client.upsert(
                collection_name=self.collections["summaries"],
                points=points,
                wait=True
            )
            logger.info(f"Synced {len(points)} summaries")


# Docker Compose addition for Qdrant
QDRANT_DOCKER_COMPOSE = """
# Add this to your existing docker-compose.yml

  qdrant:
    image: qdrant/qdrant:latest
    container_name: pmoves-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"  # gRPC port
    volumes:
      - qdrant_data:/qdrant/storage
      - ./qdrant_config.yaml:/qdrant/config/production.yaml
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
      - QDRANT__SERVICE__HOST=0.0.0.0
      - QDRANT__LOG_LEVEL=INFO
    networks:
      - rag_network
    restart: unless-stopped
    labels:
      - "coolify.managed=true"
      - "coolify.type=database"
      - "coolify.name=qdrant-vector-db"

volumes:
  qdrant_data:
"""

# Qdrant configuration file
QDRANT_CONFIG = """
# qdrant_config.yaml
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334

storage:
  storage_path: /qdrant/storage
  optimizers:
    default_segment_number: 2
    indexing_ram_limit_mb: 1000

cluster:
  enabled: false

telemetry:
  disabled: true

log_level: INFO
"""


# Integration with existing PMOVES.AI workflow
class PMOVESQdrantIntegration:
    """
    Integrates Qdrant with your existing PMOVES.AI setup
    Works alongside Supabase for optimal performance
    """
    
    def __init__(self):
        self.config = PMOVESConfig()
        self.manager = QdrantPMOVESManager(self.config)
        
    async def initialize(self):
        """Initialize Qdrant collections and sync data"""
        await self.manager.initialize_collections()
        await self.manager.sync_from_supabase(full_sync=False)
        
    async def search(self, query: str, embedding_service) -> List[Dict]:
        """
        Perform search using Qdrant for vectors and Supabase for metadata
        
        Args:
            query: Search query text
            embedding_service: Service to generate embeddings
            
        Returns:
            Search results with full metadata
        """
        
        # Generate CoCa embeddings for query
        query_embeddings = await embedding_service.generate_coca_embeddings(query)
        
        # Search Qdrant
        qdrant_results = await self.manager.coca_search(query_embeddings)
        
        # Enhance with Supabase metadata if needed
        enhanced_results = await self._enhance_with_metadata(qdrant_results)
        
        return enhanced_results
    
    async def _enhance_with_metadata(self, results: List[Dict]) -> List[Dict]:
        """Enhance Qdrant results with additional metadata from Supabase"""
        
        # Get video IDs
        video_ids = list(set(r['video_id'] for r in results))
        
        # Fetch video metadata from Supabase
        async with aiohttp.ClientSession() as session:
            headers = {
                "apikey": self.config.supabase_key,
                "Authorization": f"Bearer {self.config.supabase_key}"
            }
            
            url = f"{self.config.supabase_url}/rest/v1/youtube_videos"
            params = {"video_id": f"in.({','.join(video_ids)})"}
            
            async with session.get(url, headers=headers, params=params) as response:
                videos = await response.json()
        
        # Create video lookup
        video_lookup = {v['video_id']: v for v in videos}
        
        # Enhance results
        for result in results:
            video_id = result['video_id']
            if video_id in video_lookup:
                result['video_metadata'] = video_lookup[video_id]
        
        return results


# Usage example
async def main():
    """Example usage of PMOVES Qdrant integration"""
    
    # Initialize integration
    integration = PMOVESQdrantIntegration()
    await integration.initialize()
    
    # Perform search
    results = await integration.search(
        query="how to create knowledge graphs with LangExtract",
        embedding_service=None  # Your embedding service
    )
    
    print(f"Found {len(results)} results")
    for result in results[:5]:
        print(f"- {result['video_metadata']['title']}: {result['text'][:100]}...")
        print(f"  Score: {result['combined_score']:.3f}")
        print(f"  URL: {result['timestamped_url']}")


if __name__ == "__main__":
    asyncio.run(main())
