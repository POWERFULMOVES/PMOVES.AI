#!/usr/bin/env python3
"""
Test PMOVES.YT n8n Workflow

Usage:
    python test_n8n_workflow.py [youtube_url]

Example:
    python test_n8n_workflow.py https://youtube.com/watch?v=dQw4w9WgXcQ
"""

import sys
import json
import time
import requests

def test_workflow(youtube_url: str, namespace: str = "pmoves"):
    """Test the n8n YouTube ingestion workflow"""
    
    webhook_url = "http://localhost:5678/webhook/youtube-ingest"
    
    payload = {
        "url": youtube_url,
        "namespace": namespace,
        "bucket": "assets"
    }
    
    print(f"🚀 Triggering n8n workflow for: {youtube_url}")
    print(f"📡 Webhook URL: {webhook_url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    print("\n⏳ Waiting for response (this may take 3-7 minutes)...\n")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=420  # 7 minutes max
        )
        
        elapsed = time.time() - start_time
        
        print(f"✅ Response received in {elapsed:.2f} seconds")
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200 and response.json().get("success"):
            print("\n🎉 SUCCESS! Video ingested and indexed.")
            result = response.json()
            print(f"   Video ID: {result.get('video_id')}")
            print(f"   Title: {result.get('title')}")
            print(f"   Chunks Indexed: {result.get('chunks_indexed')}")
            print(f"   Summary Generated: {result.get('summary_generated')}")
        else:
            print("\n❌ FAILURE! Check n8n executions for details.")
            print(f"   Access n8n UI: http://localhost:5678")
            
    except requests.Timeout:
        print(f"⏰ Timeout after {time.time() - start_time:.2f} seconds")
        print("   The workflow may still be running.")
        print("   Check n8n executions: http://localhost:5678")
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        print("   Is n8n running? Check: docker ps | grep n8n")
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response: {response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_n8n_workflow.py [youtube_url]")
        print("\nExample:")
        print("  python test_n8n_workflow.py https://youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    test_workflow(youtube_url)
