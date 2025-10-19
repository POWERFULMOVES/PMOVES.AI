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
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    raise SystemExit(
        "sentence-transformers is required. Install with: pip install sentence-transformers"
    ) from exc


# Environment configuration
SUPABASE_URL = os.environ.get("SUPA_REST_URL", "http://localhost:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
EMBEDDING_MODEL = os.environ.get("YOUTUBE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension

# FastAPI app
app = FastAPI(
    title="PMOVES.yt MCP Adapter",
    description="YouTube transcript search and metadata API for Jellyfin backfill",
    version="0.1.0"
)

# Global state
_embedding_model: Optional[SentenceTransformer] = None
_supabase_client: Optional[httpx.AsyncClient] = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_supabase_client() -> httpx.AsyncClient:
    """Get configured Supabase HTTP client."""
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


# Request/Response models
class YouTubeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(5, ge=1, le=50, description="Maximum results to return")
    threshold: float = Field(0.70, ge=0.0, le=1.0, description="Cosine similarity threshold")


class YouTubeResult(BaseModel):
    video_id: str
    title: str
    url: str
    similarity: float
    excerpt: str
    channel: Optional[str] = None
    published_at: Optional[str] = None
    duration: Optional[float] = None


class YouTubeSearchResponse(BaseModel):
    query: str
    results: List[YouTubeResult]
    total: int
    threshold: float


class YouTubeVideoMetadata(BaseModel):
    video_id: str
    title: str
    description: Optional[str] = None
    channel: Optional[str] = None
    url: str
    published_at: Optional[str] = None
    duration: Optional[float] = None
    transcript: Optional[str] = None
    embedding: Optional[List[float]] = None


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "mcp-youtube-adapter", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/youtube/search", response_model=YouTubeSearchResponse)
async def search_youtube_transcripts(request: YouTubeSearchRequest):
    """
    Semantic search across YouTube transcript corpus.
    
    Returns videos with transcripts semantically similar to the query,
    ranked by cosine similarity score.
    """
    try:
        # Generate query embedding
        model = get_embedding_model()
        query_embedding = model.encode([request.query], normalize_embeddings=True)[0]
        
        # Search Supabase for similar transcripts (assuming youtube_transcripts table exists)
        client = get_supabase_client()
        
        # Fetch all transcripts (in production, use pgvector for efficient similarity search)
        # For now, we'll do client-side similarity computation
        resp = await client.get(
            "/youtube_transcripts",
            params={
                "select": "video_id,title,channel,url,published_at,duration,transcript,embedding",
                "limit": "100"  # Fetch top 100 for client-side ranking
            }
        )
        resp.raise_for_status()
        transcripts = resp.json()
        
        # Compute similarities
        results = []
        for transcript in transcripts:
            if not transcript.get("embedding"):
                continue
            
            # Compute cosine similarity
            stored_embedding = np.array(transcript["embedding"], dtype=np.float32)
            query_emb = np.array(query_embedding, dtype=np.float32)
            
            similarity = float(np.dot(query_emb, stored_embedding) / 
                             (np.linalg.norm(query_emb) * np.linalg.norm(stored_embedding)))
            
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
    """
    Fetch YouTube video metadata and transcript by video ID.
    """
    try:
        client = get_supabase_client()
        
        resp = await client.get(
            "/youtube_transcripts",
            params={
                "video_id": f"eq.{video_id}",
                "select": "video_id,title,description,channel,url,published_at,duration,transcript,embedding"
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
            embedding=video.get("embedding")
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
    """
    Ingest a YouTube video into the corpus.
    
    Fetches metadata, extracts transcript, generates embedding, and stores in Supabase.
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


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("🚀 MCP YouTube Adapter starting up...")
    print(f"   Supabase: {SUPABASE_URL}")
    print(f"   Embedding Model: {EMBEDDING_MODEL}")
    
    # Pre-load embedding model
    try:
        model = get_embedding_model()
        print(f"   ✅ Loaded {EMBEDDING_MODEL} ({model.get_sentence_embedding_dimension()} dimensions)")
    except Exception as exc:
        print(f"   ⚠️  Failed to load embedding model: {exc}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _supabase_client
    if _supabase_client:
        await _supabase_client.aclose()
    print("👋 MCP YouTube Adapter shut down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
