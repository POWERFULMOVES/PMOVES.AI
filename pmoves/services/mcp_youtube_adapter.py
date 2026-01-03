#!/usr/bin/env python3
"""
MCP YouTube Adapter - Bridges PMOVES.yt transcript corpus with Jellyfin backfill.

Provides semantic search endpoints for YouTube transcripts stored in Supabase,
enabling content linking between Jellyfin media and related YouTube videos.

Usage:
  # Standalone server
  uvicorn pmoves.services.mcp_youtube_adapter:app --host 0.0.0.0 --port 8081
  
  # Or integrate into existing MCP Docker service
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from fastapi import FastAPI, HTTPException, Query
    from contextlib import asynccontextmanager
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise SystemExit(
        "FastAPI and pydantic are required. Install with: pip install fastapi pydantic uvicorn"
    ) from exc

try:
    import httpx
except ImportError as exc:
    raise SystemExit("httpx is required. Install with: pip install httpx") from exc

try:
    import numpy as np
except ImportError as exc:
    raise SystemExit("numpy is required. Install with: pip install numpy") from exc

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    SentenceTransformerType = SentenceTransformer
except ImportError:
    SentenceTransformer = None  # Optional when using remote or non-sentence-transformer models
    SentenceTransformerType = Any


# Environment configuration
SUPABASE_URL = os.environ.get("SUPA_REST_URL", "http://localhost:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
EMBEDDING_MODEL = os.environ.get("YOUTUBE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_API_URL = os.environ.get("YOUTUBE_EMBEDDING_API_URL")


def _resolve_embedding_target(model_name: str) -> tuple[str, int]:
    """Resolve Supabase column and dimension for supported embedding backends.

    Determines which Supabase column to use for storing embeddings and the
    expected vector dimension based on the embedding model family.

    Args:
        model_name: Name of the embedding model (e.g., 'sentence-transformers/all-MiniLM-L6-v2').

    Returns:
        A tuple of (column_name, dimension) where:
            - column_name: Supabase column name for embeddings (e.g., 'embedding_st', 'embedding_qwen')
            - dimension: Expected vector dimension (e.g., 384, 2560, 768)

    Examples:
        >>> _resolve_embedding_target("sentence-transformers/all-MiniLM-L6-v2")
        ('embedding_st', 384)
        >>> _resolve_embedding_target("qwen2-embedding")
        ('embedding_qwen', 2560)
    """
    normalized = (model_name or "").lower()

    if "qwen3-embedding" in normalized or "qwen2-embedding" in normalized or "qwen-embedding" in normalized:
        # Qwen embedding families expose 2560-d vectors (Matryoshka variants can be truncated)
        return "embedding_qwen", 2560
    if "embeddinggemma" in normalized or "embedding-gecko" in normalized:
        # Google embedding models default to 768 dims
        return "embedding_gemma", 768
    # Default to sentence-transformers style 384-d vectors
    return "embedding_st", 384


_DEFAULT_COLUMN, _DEFAULT_DIM = _resolve_embedding_target(EMBEDDING_MODEL)
EMBEDDING_COLUMN = os.environ.get("YOUTUBE_EMBEDDING_COLUMN", _DEFAULT_COLUMN)
EMBEDDING_DIM = int(os.environ.get("YOUTUBE_EMBEDDING_DIM", str(_DEFAULT_DIM)))

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan, handling startup and shutdown events.

    Initializes embedding models and HTTP clients on startup, and properly
    closes connections on shutdown to prevent resource leaks.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded back to the application during its lifetime.

    Raises:
        Exception: Propagates exceptions that occur during startup initialization.
    """
    # Startup
    # Initialize services on startup.
    print("🚀 MCP YouTube Adapter starting up...")
    print(f"   Supabase: {SUPABASE_URL}")
    print(f"   Embedding Model: {EMBEDDING_MODEL}")
    print(f"   Embedding Column: {EMBEDDING_COLUMN} (dim={EMBEDDING_DIM})")

    # Pre-load embedding model
    if EMBEDDING_API_URL:
        print(f"   Using remote embedding API: {EMBEDDING_API_URL}")
    else:
        try:
            model = get_embedding_model()
            dim = getattr(model, "get_sentence_embedding_dimension", lambda: None)()
            if dim:
                print(f"   ✅ Loaded {EMBEDDING_MODEL} ({dim} dimensions)")
            else:
                print(f"   ✅ Loaded {EMBEDDING_MODEL}")
        except Exception as exc:
            print(f"   ⚠️  Failed to load embedding model: {exc}")
    yield
    # Shutdown
    # Cleanup on shutdown.
    global _supabase_client, _embedding_api_client
    if _supabase_client:
        await _supabase_client.aclose()
    if _embedding_api_client:
        await _embedding_api_client.aclose()
    print("👋 MCP YouTube Adapter shut down")


app = FastAPI(
    title="PMOVES.yt MCP Adapter",
    description="YouTube transcript search and metadata API for Jellyfin backfill",
    version="0.1.0",
    lifespan=lifespan
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")

# Global state
_embedding_model: Optional[SentenceTransformerType] = None
_supabase_client: Optional[httpx.AsyncClient] = None
_embedding_api_client: Optional[httpx.AsyncClient] = None


def get_embedding_model() -> SentenceTransformerType:
    """Lazy-load the sentence transformer embedding model.

    Loads the model on first call and caches it globally for subsequent calls.
    Uses the model specified by the YOUTUBE_EMBEDDING_MODEL environment variable.

    Returns:
        The loaded SentenceTransformer model instance.

    Raises:
        RuntimeError: If sentence-transformers is not installed and no
            remote embedding API URL is configured.
    """
    if SentenceTransformer is None:
        raise RuntimeError(
            "sentence-transformers not installed. Install it or set YOUTUBE_EMBEDDING_API_URL "
            "to use an external embedding endpoint."
        )
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_supabase_client() -> httpx.AsyncClient:
    """Get or create a configured Supabase HTTP client.

    Creates an httpx AsyncClient with proper authentication headers for
    Supabase PostgREST API access. The client is cached globally for reuse.

    Returns:
        A configured httpx.AsyncClient instance with Supabase authentication headers.

    Raises:
        RuntimeError: If SUPABASE_SERVICE_ROLE_KEY environment variable is not set.
    """
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not set")
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        _supabase_client = httpx.AsyncClient(
            base_url=SUPABASE_URL.rstrip("/"),
            headers=headers,
            timeout=30.0
        )
    return _supabase_client


async def get_embedding_api_client() -> httpx.AsyncClient:
    """Get or create an HTTP client for remote embedding services.

    Creates an httpx AsyncClient for calling external embedding APIs
    (when YOUTUBE_EMBEDDING_API_URL is configured). The client is cached globally.

    Returns:
        A configured httpx.AsyncClient instance with 30-second timeout.
    """
    global _embedding_api_client
    if _embedding_api_client is None:
        _embedding_api_client = httpx.AsyncClient(timeout=30.0)
    return _embedding_api_client


async def encode_query_text(text: str) -> np.ndarray:
    """Generate a query embedding using either local model or remote embedding service.

    Supports two modes:
    1. Remote API: Calls YOUTUBE_EMBEDDING_API_URL for embeddings
    2. Local model: Uses sentence-transformers model loaded in-memory

    Args:
        text: The query text to encode into an embedding vector.

    Returns:
        A numpy array of shape (embedding_dim,) containing the normalized
        embedding vector as float32.

    Raises:
        HTTPException: If the remote embedding API request fails or returns
            an invalid response (status 502).
    """
    if EMBEDDING_API_URL:
        client = await get_embedding_api_client()
        try:
            resp = await client.post(
                EMBEDDING_API_URL,
                json={"model": EMBEDDING_MODEL, "inputs": [text]},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Embedding API request failed: {exc}") from exc
        embeddings = data.get("embeddings") or data.get("data")
        if not embeddings:
            raise HTTPException(status_code=502, detail="Embedding API response missing 'embeddings' or 'data'")
        # embeddings[0] works for both "embeddings" and "data" response formats
        vector = np.asarray(embeddings[0], dtype=np.float32)
    else:
        model = get_embedding_model()
        vector = model.encode([text], normalize_embeddings=True)[0]
        vector = np.asarray(vector, dtype=np.float32)
    return vector


def adjust_vector_dimension(vector: np.ndarray, target_dim: int) -> np.ndarray:
    """Adjust vector dimension by padding or truncating.

    Ensures embedding vectors have consistent dimensions for cosine similarity
    computation. Pads with zeros if smaller, truncates if larger.

    Args:
        vector: Input embedding vector as numpy array.
        target_dim: Target dimension for the output vector.

    Returns:
        A numpy array with shape (target_dim,) containing the adjusted vector.
        If the input is larger, it is truncated. If smaller, it is zero-padded.

    Examples:
        >>> adjust_vector_dimension(np.array([1.0, 2.0]), 4)
        array([1., 2., 0., 0.])
        >>> adjust_vector_dimension(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
        array([1., 2., 3.])
    """
    if vector.size > target_dim:
        return vector[:target_dim]
    if vector.size < target_dim:
        return np.pad(vector, (0, target_dim - vector.size))
    return vector


# Request/Response models
class YouTubeSearchRequest(BaseModel):
    """Request model for YouTube transcript semantic search.

    Attributes:
        query: Search query text (must be at least 1 character).
        limit: Maximum number of results to return (1-50, default 5).
        threshold: Minimum cosine similarity score (0.0-1.0, default 0.70).
    """

    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(5, ge=1, le=50, description="Maximum results to return")
    threshold: float = Field(0.70, ge=0.0, le=1.0, description="Cosine similarity threshold")


class YouTubeResult(BaseModel):
    """Single YouTube video search result with transcript match.

    Attributes:
        video_id: YouTube video identifier.
        title: Video title.
        url: Full YouTube video URL.
        similarity: Cosine similarity score (0.0-1.0).
        excerpt: Text excerpt from the transcript matching the query.
        channel: YouTube channel name (optional).
        published_at: ISO 8601 publication timestamp (optional).
        duration: Video duration in seconds (optional).
    """

    video_id: str
    title: str
    url: str
    similarity: float
    excerpt: str
    channel: Optional[str] = None
    published_at: Optional[str] = None
    duration: Optional[float] = None


class YouTubeSearchResponse(BaseModel):
    """Response model for YouTube transcript search results.

    Attributes:
        query: The original search query.
        results: List of matching YouTube videos ranked by similarity.
        total: Number of results returned (may be less than requested).
        threshold: The similarity threshold used for filtering.
    """

    query: str
    results: List[YouTubeResult]
    total: int
    threshold: float


class YouTubeVideoMetadata(BaseModel):
    """Complete metadata for a YouTube video including transcript and embedding.

    Attributes:
        video_id: YouTube video identifier.
        title: Video title.
        description: Video description text (optional).
        channel: YouTube channel name (optional).
        url: Full YouTube video URL.
        published_at: ISO 8601 publication timestamp (optional).
        duration: Video duration in seconds (optional).
        transcript: Full transcript text (optional).
        embedding: Embedding vector as list of floats (optional).
        embedding_column: Supabase column name for the embedding (optional).
    """

    video_id: str
    title: str
    description: Optional[str] = None
    channel: Optional[str] = None
    url: str
    published_at: Optional[str] = None
    duration: Optional[float] = None
    transcript: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_column: Optional[str] = None


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring service availability.

    Returns:
        A dictionary containing:
            - status: Service health status ('ok').
            - service: Service identifier ('mcp-youtube-adapter').
            - timestamp: ISO 8601 timestamp of the health check in UTC.
    """
    return {"status": "ok", "service": "mcp-youtube-adapter", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/youtube/search", response_model=YouTubeSearchResponse)
async def search_youtube_transcripts(request: YouTubeSearchRequest):
    """Semantic search across YouTube transcript corpus.

    Performs vector similarity search by encoding the query text and comparing
    against pre-computed embeddings in Supabase. Results are ranked by cosine
    similarity and filtered by the threshold parameter.

    Args:
        request: Search request containing query text, result limit, and similarity threshold.

    Returns:
        YouTubeSearchResponse containing:
            - query: The original search query.
            - results: Ranked list of YouTube videos with similarity scores and excerpts.
            - total: Number of results returned.
            - threshold: The similarity threshold applied.

    Raises:
        HTTPException: If Supabase query fails (502) or any other error occurs (500).
    """
    try:
        # Generate query embedding
        query_embedding = await encode_query_text(request.query)
        query_embedding = adjust_vector_dimension(query_embedding, EMBEDDING_DIM)
        
        # Search Supabase for similar transcripts (assuming youtube_transcripts table exists)
        client = get_supabase_client()
        
        # Fetch all transcripts (in production, use pgvector for efficient similarity search)
        # For now, we'll do client-side similarity computation
        resp = await client.get(
            "/youtube_transcripts",
            params={
                "select": f"video_id,title,channel,url,published_at,duration,transcript,{EMBEDDING_COLUMN}",
                "limit": "100"  # Fetch top 100 for client-side ranking
            }
        )
        resp.raise_for_status()
        transcripts = resp.json()
        
        # Compute similarities
        results = []
        for transcript in transcripts:
            embedding_values = transcript.get(EMBEDDING_COLUMN)
            if not embedding_values:
                continue
            
            # Compute cosine similarity
            stored_embedding = np.asarray(embedding_values, dtype=np.float32)
            stored_embedding = adjust_vector_dimension(stored_embedding, EMBEDDING_DIM)
            
            denom = (np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding))
            if denom == 0.0:
                continue
            similarity = float(np.dot(query_embedding, stored_embedding) / denom)
            
            if similarity >= request.threshold:
                # Extract relevant excerpt from transcript
                transcript_text = transcript.get("transcript", "")
                excerpt = transcript_text[:300] + "..." if len(transcript_text) > 300 else transcript_text
                
                results.append(YouTubeResult(
                    video_id=transcript["video_id"],
                    title=transcript.get("title", "Unknown"),
                    url=transcript.get("url", f"https://youtube.com/watch?v={transcript['video_id']}"),
                    similarity=round(similarity, 4),
                    excerpt=excerpt,
                    channel=transcript.get("channel"),
                    published_at=transcript.get("published_at"),
                    duration=transcript.get("duration")
                ))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x.similarity, reverse=True)
        results = results[:request.limit]
        
        return YouTubeSearchResponse(
            query=request.query,
            results=results,
            total=len(results),
            threshold=request.threshold
        )
    
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Supabase error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(exc)}")


@app.get("/youtube/video/{video_id}", response_model=YouTubeVideoMetadata)
async def get_youtube_video(video_id: str):
    """Fetch YouTube video metadata and transcript by video ID.

    Retrieves complete video information from Supabase including metadata,
    full transcript, and embedding vector.

    Args:
        video_id: YouTube video identifier (11-character string).

    Returns:
        YouTubeVideoMetadata containing:
            - video_id, title, description, channel, url
            - published_at, duration
            - transcript: Full transcript text
            - embedding: Pre-computed embedding vector
            - embedding_column: Supabase column name for the embedding

    Raises:
        HTTPException: If video not found (404), Supabase query fails (502),
            or any other error occurs (500).
    """
    try:
        client = get_supabase_client()
        
        resp = await client.get(
            "/youtube_transcripts",
            params={
                "video_id": f"eq.{video_id}",
                "select": f"video_id,title,description,channel,url,published_at,duration,transcript,{EMBEDDING_COLUMN}"
            }
        )
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found in corpus")
        
        video = data[0]
        return YouTubeVideoMetadata(
            video_id=video["video_id"],
            title=video.get("title", "Unknown"),
            description=video.get("description"),
            channel=video.get("channel"),
            url=video.get("url", f"https://youtube.com/watch?v={video_id}"),
            published_at=video.get("published_at"),
            duration=video.get("duration"),
            transcript=video.get("transcript"),
            embedding=video.get(EMBEDDING_COLUMN),
            embedding_column=EMBEDDING_COLUMN
        )
    
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Supabase error: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {str(exc)}")


@app.post("/youtube/ingest")
async def ingest_youtube_video(
    url: str = Query(..., description="YouTube video URL"),
    extract_transcript: bool = Query(True, description="Extract transcript")
):
    """Ingest a YouTube video into the transcript corpus.

    Extracts the video ID from a YouTube URL and initiates ingestion workflow.
    Currently returns a placeholder response with deployment instructions.

    Args:
        url: Full YouTube video URL (youtube.com or youtu.be format).
        extract_transcript: Whether to extract the transcript (currently unused).

    Returns:
        A dictionary containing:
            - status: Ingestion status ('success').
            - video_id: Extracted YouTube video identifier.
            - message: Status message with next steps.
            - next_steps: List of deployment and configuration instructions.

    Raises:
        HTTPException: If URL is invalid (400) or ingestion fails (500).
    """
    try:
        # Extract video ID from URL
        parsed = urlparse(url)
        video_id = None
        if "youtube.com" in parsed.netloc:
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            video_id = query_params.get("v", [None])[0]
        elif "youtu.be" in parsed.netloc:
            video_id = parsed.path.lstrip("/")
        
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        # TODO: Call MCP Docker YouTube tools to extract metadata and transcript
        # For now, return placeholder response
        return {
            "status": "success",
            "video_id": video_id,
            "message": "Video ingestion not yet implemented. Deploy PMOVES.yt batch processor first.",
            "next_steps": [
                "Deploy docker-compose.yml from docs/PMOVES.yt/batch_docker_coolify.md",
                "Configure n8n workflow for transcript extraction",
                "Enable MCP Docker YouTube tools integration"
            ]
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(exc)}")



