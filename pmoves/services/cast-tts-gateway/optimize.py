"""
Performance Optimization

Connection pooling, request batching, and audio caching for improved performance.
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class CacheEntry:
    """Audio cache entry."""

    key: str
    audio_data: bytes
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0

    def __post_init__(self):
        """Calculate size after initialization."""
        self.size_bytes = len(self.audio_data)

    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if entry is expired."""
        return (time.time() - self.created_at) > ttl_seconds

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
            "last_accessed": self.last_accessed,
            "last_accessed_iso": datetime.fromtimestamp(self.last_accessed).isoformat() + "Z",
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "size_kb": round(self.size_bytes / 1024, 2),
        }


class AudioCache:
    """LRU cache for synthesized audio."""

    def __init__(self, max_size: int = 100, ttl_seconds: float = 3600):
        """
        Initialize audio cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for cache entries
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    def _generate_key(self, text: str, voice: str = "default") -> str:
        """
        Generate cache key from text and voice.

        Args:
            text: Text content
            voice: Voice identifier

        Returns:
            Cache key (SHA256 hash)
        """
        content = f"{text}:{voice}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, text: str, voice: str = "default") -> Optional[bytes]:
        """
        Get audio from cache.

        Args:
            text: Text content
            voice: Voice identifier

        Returns:
            Audio data if cached, None otherwise
        """
        async with self._lock:
            key = self._generate_key(text, voice)

            entry = self.cache.get(key)
            if entry:
                # Check if expired
                if entry.is_expired(self.ttl_seconds):
                    del self.cache[key]
                    return None

                # Update access info
                entry.touch()

                # Move to end (most recently used)
                self.cache.move_to_end(key)

                return entry.audio_data

            return None

    async def put(self, text: str, audio_data: bytes, voice: str = "default") -> dict:
        """
        Put audio in cache with O(1) LRU eviction.

        Args:
            text: Text content
            audio_data: Audio data
            voice: Voice identifier

        Returns:
            Result dict
        """
        async with self._lock:
            key = self._generate_key(text, voice)

            # Check if cache is full, evict oldest entry (FIFO)
            if len(self.cache) >= self.max_size:
                # O(1) eviction: remove first (oldest) item
                if self.cache:
                    self.cache.popitem(last=False)

            # Add entry (automatically placed at end as most recent)
            entry = CacheEntry(key=key, audio_data=audio_data)
            self.cache[key] = entry

            return {
                "key": key,
                "size_bytes": entry.size_bytes,
                "cache_size": len(self.cache),
            }

    async def invalidate(self, text: str, voice: str = "default") -> bool:
        """
        Invalidate cache entry.

        Args:
            text: Text content
            voice: Voice identifier

        Returns:
            True if invalidated, False if not found
        """
        async with self._lock:
            key = self._generate_key(text, voice)

            if key in self.cache:
                del self.cache[key]
                return True

            return False

    async def clear(self) -> dict:
        """
        Clear all cache entries.

        Returns:
            Result dict
        """
        async with self._lock:
            cleared = len(self.cache)
            self.cache.clear()

            return {
                "cleared": cleared,
                "message": f"Cleared {cleared} cache entries",
            }

    async def cleanup_expired(self) -> dict:
        """
        Remove expired cache entries.

        Returns:
            Result dict
        """
        async with self._lock:
            expired_keys = [
                key
                for key, entry in self.cache.items()
                if entry.is_expired(self.ttl_seconds)
            ]

            for key in expired_keys:
                del self.cache[key]

            return {
                "expired": len(expired_keys),
                "remaining": len(self.cache),
            }

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Cache stats dict
        """
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        total_accesses = sum(entry.access_count for entry in self.cache.values())

        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "ttl_seconds": self.ttl_seconds,
            "total_accesses": total_accesses,
            "hit_rate": 0.0,  # Would need miss tracking
        }


class ConnectionPool:
    """HTTP connection pool manager."""

    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 10,
        keepalive_expiry: float = 5.0,
    ):
        """
        Initialize connection pool.

        Args:
            max_connections: Maximum connections per host
            max_keepalive_connections: Maximum keepalive connections
            keepalive_expiry: Keepalive connection expiry time
        """
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self._pools: dict[str, Any] = {}

    def get_pool(self, base_url: str) -> Any:
        """
        Get or create connection pool for base URL.

        Args:
            base_url: Base URL for pool

        Returns:
            HTTP client with connection pooling
        """
        if base_url not in self._pools:
            try:
                import httpx

                self._pools[base_url] = httpx.AsyncClient(
                    limits=httpx.Limits(
                        max_connections=self.max_connections,
                        max_keepalive_connections=self.max_keepalive_connections,
                        keepalive_expiry=self.keepalive_expiry,
                    ),
                    timeout=120.0,
                )

            except ImportError:
                # Fallback to aiohttp
                from aiohttp import ClientSession, TCPConnector

                self._pools[base_url] = ClientSession(
                    connector=TCPConnector(
                        limit=self.max_connections,
                        keepalive_timeout=self.keepalive_expiry,
                    )
                )

        return self._pools[base_url]

    async def close_all(self):
        """Close all connection pools."""
        for pool in self._pools.values():
            if hasattr(pool, "aclose"):
                await pool.aclose()
            elif hasattr(pool, "close"):
                await pool.close()

        self._pools.clear()

    def get_stats(self) -> dict:
        """
        Get connection pool stats.

        Returns:
            Pool stats dict
        """
        return {
            "pools": len(self._pools),
            "max_connections": self.max_connections,
            "max_keepalive_connections": self.max_keepalive_connections,
            "keepalive_expiry": self.keepalive_expiry,
            "hosts": list(self._pools.keys()),
        }


class RequestBatcher:
    """Batch multiple requests for efficiency."""

    def __init__(
        self,
        max_batch_size: int = 10,
        max_batch_delay: float = 0.5,
    ):
        """
        Initialize request batcher.

        Args:
            max_batch_size: Maximum requests per batch
            max_batch_delay: Maximum delay before flushing batch
        """
        self.max_batch_size = max_batch_size
        self.max_batch_delay = max_batch_delay
        self._batches: dict[str, list] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def add_request(
        self,
        batch_key: str,
        request_fn,
        *args,
        **kwargs,
    ) -> Any:
        """
        Add request to batch.

        Args:
            batch_key: Key to group requests (e.g., device name)
            request_fn: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        # Create batch-specific lock if needed
        if batch_key not in self._locks:
            self._locks[batch_key] = asyncio.Lock()

        async with self._locks[batch_key]:
            # Add to batch
            if batch_key not in self._batches:
                self._batches[batch_key] = []

            self._batches[batch_key].append((request_fn, args, kwargs))

            # Flush if batch is full
            if len(self._batches[batch_key]) >= self.max_batch_size:
                return await self._flush_batch(batch_key)

            # Schedule delayed flush
            if batch_key not in self._tasks or self._tasks[batch_key].done():
                self._tasks[batch_key] = asyncio.create_task(
                    self._delayed_flush(batch_key)
                )

            # Wait for batch to complete
            return await self._wait_for_batch(batch_key)

    async def _delayed_flush(self, batch_key: str):
        """Delayed flush of batch."""
        await asyncio.sleep(self.max_batch_delay)
        await self._flush_batch(batch_key)

    async def _flush_batch(self, batch_key: str) -> list[Any]:
        """Flush all requests in batch."""
        if batch_key not in self._batches or not self._batches[batch_key]:
            return []

        batch = self._batches[batch_key]
        self._batches[batch_key] = []

        # Execute all requests in parallel
        results = await asyncio.gather(
            *[fn(*args, **kwargs) for fn, args, kwargs in batch],
            return_exceptions=True,
        )

        return results

    async def _wait_for_batch(self, batch_key: str) -> Any:
        """Wait for batch to complete."""
        # Simple implementation - just execute immediately
        # In production, you'd want proper batch coordination
        if batch_key in self._batches and self._batches[batch_key]:
            request_fn, args, kwargs = self._batches[batch_key].pop(0)
            return await request_fn(*args, **kwargs)

        return None

    def get_stats(self) -> dict:
        """
        Get batcher stats.

        Returns:
            Batcher stats dict
        """
        return {
            "batches": len(self._batches),
            "max_batch_size": self.max_batch_size,
            "max_batch_delay": self.max_batch_delay,
            "pending_requests": sum(len(batch) for batch in self._batches.values()),
        }


class OptimizationManager:
    """Manage all optimization strategies."""

    def __init__(self):
        """Initialize optimization manager."""
        self.audio_cache = AudioCache()
        self.connection_pool = ConnectionPool()
        self.request_batcher = RequestBatcher()

    async def get_cached_audio(self, text: str, voice: str = "default") -> Optional[bytes]:
        """Get audio from cache."""
        return await self.audio_cache.get(text, voice)

    async def cache_audio(self, text: str, audio_data: bytes, voice: str = "default") -> dict:
        """Cache audio data."""
        return await self.audio_cache.put(text, audio_data, voice)

    async def invalidate_cache(self, text: str, voice: str = "default") -> bool:
        """Invalidate cache entry."""
        return await self.audio_cache.invalidate(text, voice)

    async def clear_cache(self) -> dict:
        """Clear all cache entries."""
        return await self.audio_cache.clear()

    async def cleanup_cache(self) -> dict:
        """Remove expired cache entries."""
        return await self.audio_cache.cleanup_expired()

    def get_connection_pool(self, base_url: str) -> Any:
        """Get connection pool for URL."""
        return self.connection_pool.get_pool(base_url)

    async def close_connection_pools(self):
        """Close all connection pools."""
        await self.connection_pool.close_all()

    async def batch_request(
        self,
        batch_key: str,
        request_fn,
        *args,
        **kwargs,
    ) -> Any:
        """Add request to batch."""
        return await self.request_batcher.add_request(
            batch_key,
            request_fn,
            *args,
            **kwargs,
        )

    def get_optimization_stats(self) -> dict:
        """Get all optimization stats."""
        return {
            "audio_cache": self.audio_cache.get_stats(),
            "connection_pool": self.connection_pool.get_stats(),
            "request_batcher": self.request_batcher.get_stats(),
        }
