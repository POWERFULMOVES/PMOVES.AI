#!/usr/bin/env python3
"""
Integration test for PMOVES.yt + Jellyfin Bridge workflow.

Tests the complete pipeline:
1. YouTube video ingestion
2. Transcript extraction
3. Hi-RAG indexing
4. AI summarization
5. Jellyfin auto-mapping
6. Event publishing

Usage:
    python test_integration.py [youtube_url]

Example:
    python test_integration.py https://youtube.com/watch?v=dQw4w9WgXcQ
"""

import sys
import time
import json
import httpx
from typing import Dict, Any, Optional

# Service endpoints
PMOVES_YT_URL = "http://localhost:8077"
JELLYFIN_BRIDGE_URL = "http://localhost:8093"
HIRAG_URL = "http://localhost:8086"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/youtube-ingest"

def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_result(step: str, success: bool, details: str = ""):
    """Print test step result"""
    icon = "✅" if success else "❌"
    print(f"{icon} {step}")
    if details:
        print(f"   {details}")

def extract_video_metadata(data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract standardized video metadata from API responses."""
    video = data.get("video") if isinstance(data, dict) else None
    if not isinstance(video, dict):
        video = {}

    video_id = (
        video.get("video_id")
        or video.get("id")
        or (data.get("video_id") if isinstance(data, dict) else None)
    )
    title = video.get("title") if video else None
    if not title and isinstance(data, dict):
        title = data.get("title")
    namespace = video.get("namespace") if video else None
    if not namespace and isinstance(data, dict):
        namespace = data.get("namespace")

    return {
        "video_id": video_id,
        "title": title,
        "namespace": namespace or "pmoves",
    }

def test_service_health() -> bool:
    """Test all service health endpoints"""
    print_section("1. Service Health Checks")
    
    services = {
        "PMOVES.yt": f"{PMOVES_YT_URL}/healthz",
        "Jellyfin Bridge": f"{JELLYFIN_BRIDGE_URL}/healthz",
        "Hi-RAG Gateway": f"{HIRAG_URL}/health",
    }
    
    all_healthy = True
    for name, url in services.items():
        try:
            resp = httpx.get(url, timeout=5.0)
            healthy = resp.status_code == 200
            print_result(f"{name:20s}", healthy, f"{url}")
            all_healthy = all_healthy and healthy
        except Exception as e:
            print_result(f"{name:20s}", False, f"Error: {e}")
            all_healthy = False
    
    return all_healthy

def test_youtube_info(video_url: str) -> Optional[Dict[str, Any]]:
    """Test YouTube video info extraction"""
    print_section("2. YouTube Video Info")
    
    try:
        resp = httpx.post(
            f"{PMOVES_YT_URL}/yt/info",
            json={"url": video_url},
            timeout=15.0
        )
        resp.raise_for_status()
        data = resp.json()
        
        video_id = data.get("id")
        title = data.get("title")
        duration = data.get("duration")
        
        print_result("Video Info Retrieved", True)
        print(f"   Video ID: {video_id}")
        print(f"   Title: {title}")
        print(f"   Duration: {duration}s")
        
        return data
        
    except Exception as e:
        print_result("Video Info Retrieved", False, f"Error: {e}")
        return None

def test_full_ingest(video_url: str) -> Optional[Dict[str, Optional[str]]]:
    """Test full YouTube ingestion pipeline"""
    print_section("3. Full Video Ingestion")

    print("⏳ Starting ingestion (this may take 1-3 minutes)...")
    start_time = time.time()
    
    try:
        resp = httpx.post(
            f"{PMOVES_YT_URL}/yt/ingest",
            json={"url": video_url, "namespace": "pmoves", "bucket": "assets"},
            timeout=300.0  # 5 minutes max
        )
        resp.raise_for_status()
        data = resp.json()

        elapsed = time.time() - start_time
        metadata = extract_video_metadata(data)
        video_id = metadata.get("video_id")
        title = metadata.get("title")
        namespace = metadata.get("namespace")

        if not video_id:
            print_result(
                "Video Ingested",
                False,
                "Missing video_id in ingestion response",
            )
            return None

        print_result("Video Ingested", True, f"Completed in {elapsed:.2f}s")
        print(f"   Video ID: {video_id}")
        if title:
            print(f"   Title: {title}")
        print(f"   Namespace: {namespace}")

        return metadata

    except Exception as e:
        print_result("Video Ingested", False, f"Error: {e}")
        return None

def test_hirag_emit(video_id: str, namespace: Optional[str]) -> bool:
    """Test Hi-RAG chunk emission"""
    print_section("4. Hi-RAG Indexing")

    print("⏳ Emitting chunks to Hi-RAG (this may take 30-60 seconds)...")
    start_time = time.time()

    try:
        resp = httpx.post(
            f"{PMOVES_YT_URL}/yt/emit",
            json={"video_id": video_id, "namespace": namespace or "pmoves"},
            timeout=180.0  # 3 minutes max
        )
        resp.raise_for_status()
        data = resp.json()

        elapsed = time.time() - start_time
        chunks = data.get("chunks", 0)

        print_result(
            "Chunks Indexed",
            True,
            f"{chunks} chunks for {video_id} in namespace '{namespace or 'pmoves'}' in {elapsed:.2f}s",
        )

        return True

    except Exception as e:
        print_result("Chunks Indexed", False, f"Error: {e}")
        return False

def test_summarization(video_id: str, title: Optional[str] = None) -> bool:
    """Test AI summarization"""
    print_section("5. AI Summarization")

    print("⏳ Generating summary (this may take 30-60 seconds)...")
    start_time = time.time()
    
    try:
        resp = httpx.post(
            f"{PMOVES_YT_URL}/yt/summarize",
            json={"video_id": video_id, "style": "long", "provider": "ollama"},
            timeout=120.0  # 2 minutes max
        )
        resp.raise_for_status()
        data = resp.json()
        
        elapsed = time.time() - start_time
        summary = data.get("summary", "")

        print_result("Summary Generated", True, f"Completed in {elapsed:.2f}s")
        if title:
            print(f"   Title: {title}")
        print(f"   Provider: {data.get('provider', 'ollama')}")
        print(f"   Summary length: {len(summary)} chars")
        print(f"   Preview: {summary[:100]}...")

        return True
        
    except Exception as e:
        print_result(
            "Summary Generated",
            False,
            f"Error for video {video_id}: {e}",
        )
        return False

def test_jellyfin_mapping(
    video_id: str,
    title: Optional[str] = None,
    namespace: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Test Jellyfin auto-mapping"""
    print_section("6. Jellyfin Auto-Mapping")

    try:
        resp = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/map-by-title",
            json={"video_id": video_id},
            timeout=15.0
        )
        resp.raise_for_status()
        data = resp.json()
        
        mapped = data.get("mapped", {})
        jellyfin_item_id = mapped.get("jellyfin_item_id")
        jellyfin_name = mapped.get("name")

        print_result("Jellyfin Mapped", True)
        print(f"   Video ID: {video_id}")
        if title:
            print(f"   Title: {title}")
        if namespace:
            print(f"   Namespace: {namespace}")
        print(f"   Jellyfin Item ID: {jellyfin_item_id}")
        print(f"   Jellyfin Name: {jellyfin_name}")

        return mapped

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print_result(
                "Jellyfin Mapped",
                False,
                f"No matching Jellyfin item found for video {video_id}",
            )
        elif e.response.status_code == 412:
            print_result("Jellyfin Mapped", False, "Jellyfin credentials not configured")
        else:
            print_result(
                "Jellyfin Mapped",
                False,
                f"Error for video {video_id}: {e}",
            )
        return None
    except Exception as e:
        print_result(
            "Jellyfin Mapped",
            False,
            f"Error for video {video_id}: {e}",
        )
        return None

def test_semantic_search(video_id: str, query: str = "music") -> bool:
    """Test semantic search via /yt/search"""
    print_section("7. Semantic Search")
    
    try:
        resp = httpx.post(
            f"{PMOVES_YT_URL}/yt/search",
            json={"query": query, "limit": 5, "threshold": 0.3},
            timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()
        
        results = data.get("results", [])
        found = any(r.get("video_id") == video_id for r in results)
        
        print_result("Search Results", len(results) > 0, f"Found {len(results)} matches")
        if found:
            print(f"   ✅ Ingested video found in search results")
        else:
            print(f"   ⚠️  Ingested video not in top {len(results)} results (may need lower threshold)")
        
        return len(results) > 0
        
    except Exception as e:
        print_result("Search Results", False, f"Error: {e}")
        return False

def test_n8n_workflow(video_url: str) -> bool:
    """Test complete n8n workflow"""
    print_section("8. n8n Workflow (End-to-End)")
    
    print("⏳ Triggering n8n workflow (this may take 3-7 minutes)...")
    start_time = time.time()
    
    try:
        resp = httpx.post(
            N8N_WEBHOOK_URL,
            json={"url": video_url, "namespace": "pmoves", "bucket": "assets"},
            timeout=420.0  # 7 minutes max
        )
        resp.raise_for_status()
        data = resp.json()
        
        elapsed = time.time() - start_time
        
        metadata = extract_video_metadata(data)
        print_result("n8n Workflow", data.get("success", False), f"Completed in {elapsed:.2f}s")
        print(f"   Video ID: {metadata.get('video_id')}")
        if metadata.get("title"):
            print(f"   Title: {metadata.get('title')}")
        print(f"   Namespace: {metadata.get('namespace')}")
        print(f"   Chunks Indexed: {data.get('chunks_indexed')}")
        print(f"   Summary Generated: {data.get('summary_generated')}")
        print(f"   Jellyfin Mapped: {data.get('jellyfin_mapped', False)}")
        if data.get('jellyfin_item_id'):
            print(f"   Jellyfin Item ID: {data.get('jellyfin_item_id')}")
        
        return data.get("success", False)
        
    except httpx.TimeoutException:
        print_result("n8n Workflow", False, "Timeout - workflow may still be running")
        print("   Check n8n UI: http://localhost:5678")
        return False
    except Exception as e:
        print_result("n8n Workflow", False, f"Error: {e}")
        return False

def run_manual_tests(video_url: str):
    """Run manual step-by-step tests"""
    print("\n" + "="*60)
    print("  PMOVES.YT + Jellyfin Bridge Integration Test")
    print("  Manual Step-by-Step Mode")
    print("="*60)
    print(f"\nTesting with: {video_url}\n")
    
    # Step 1: Health checks
    if not test_service_health():
        print("\n❌ Service health checks failed. Ensure all services are running:")
        print("   docker-compose ps")
        return
    
    # Step 2: Video info
    video_info = test_youtube_info(video_url)
    if not video_info:
        print("\n❌ Failed to fetch video info. Check YouTube URL.")
        return
    
    # Step 3: Full ingestion
    metadata = test_full_ingest(video_url)
    if not metadata:
        print("\n❌ Failed to ingest video. Check pmoves-yt logs:")
        print("   docker logs pmoves-pmoves-yt-1 --tail 50")
        return
    video_id = metadata.get("video_id")
    namespace = metadata.get("namespace")
    title = metadata.get("title")

    # Step 4: Hi-RAG indexing
    if not test_hirag_emit(video_id, namespace):
        print("\n⚠️  Hi-RAG indexing failed, but continuing...")

    # Step 5: Summarization
    if not test_summarization(video_id, title):
        print("\n⚠️  Summarization failed, but continuing...")

    # Step 6: Jellyfin mapping
    jellyfin_mapping = test_jellyfin_mapping(video_id, title, namespace)
    if not jellyfin_mapping:
        print("\n⚠️  Jellyfin mapping failed (may not have matching item in library)")
    
    # Step 7: Semantic search
    test_semantic_search(video_id)
    
    # Final summary
    print_section("Test Summary")
    print("✅ Manual integration test completed!")
    print(f"   Video ID: {video_id}")
    if title:
        print(f"   Title: {title}")
    if namespace:
        print(f"   Namespace: {namespace}")
    print(f"   Services: All operational")
    print(f"   Pipeline: Ingestion → Indexing → Summarization → Mapping")
    print("\nNext steps:")
    print("   1. Verify video in Supabase:")
    print(f"      SELECT * FROM videos WHERE video_id='{video_id}';")
    print("   2. Test semantic search in Hi-RAG")
    print("   3. Check Jellyfin mapping if applicable")

def run_n8n_test(video_url: str):
    """Run n8n workflow test"""
    print("\n" + "="*60)
    print("  PMOVES.YT + Jellyfin Bridge Integration Test")
    print("  n8n Workflow Mode")
    print("="*60)
    print(f"\nTesting with: {video_url}\n")
    
    # Quick health check
    if not test_service_health():
        print("\n❌ Service health checks failed.")
        return
    
    # Run n8n workflow
    test_n8n_workflow(video_url)
    
    print("\n✅ n8n workflow test completed!")
    print("   Check n8n execution logs: http://localhost:5678")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_integration.py [youtube_url] [--n8n]")
        print("\nExamples:")
        print("  # Manual step-by-step test")
        print("  python test_integration.py https://youtube.com/watch?v=dQw4w9WgXcQ")
        print("\n  # Test via n8n workflow")
        print("  python test_integration.py https://youtube.com/watch?v=dQw4w9WgXcQ --n8n")
        sys.exit(1)
    
    video_url = sys.argv[1]
    use_n8n = "--n8n" in sys.argv
    
    if use_n8n:
        run_n8n_test(video_url)
    else:
        run_manual_tests(video_url)
