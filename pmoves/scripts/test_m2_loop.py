#!/usr/bin/env python3
"""
Test the M2 automation loop: Supabase → Agent Zero → Discord
Creates a test approval row and monitors its processing.
"""
import json
import os
import sys
import time
import requests
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_REST_URL", "http://127.0.0.1:54321/rest/v1")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
)

def create_approval_row():
    """Create a test approval row in Supabase"""
    print("Creating test approval row...")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    
    payload = {
        "title": f"M2 Test Approval {datetime.now().strftime('%H:%M:%S')}",
        "content_url": "s3://test-bucket/m2-automation-test.png",
        "namespace": "pmoves",
        "status": "approved",
        "meta": {
            "description": "Testing M2 automation loop end-to-end",
            "tags": ["m2-test", "automation", "smoke"],
            "thumbnail_url": "https://via.placeholder.com/150",
        }
    }
    
    resp = requests.post(
        f"{SUPABASE_URL}/studio_board",
        headers=headers,
        json=payload,
        timeout=10,
    )
    
    if resp.status_code in (200, 201):
        row = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
        print(f"✓ Created row ID: {row['id']}")
        print(f"  Title: {row['title']}")
        print(f"  Status: {row['status']}")
        return row['id']
    else:
        print(f"✗ Failed to create row: {resp.status_code}")
        print(resp.text)
        return None

def check_row_status(row_id, max_wait=90):
    """Monitor the row until it's processed or timeout"""
    print(f"\nMonitoring row {row_id} for processing...")
    print(f"(n8n polls every minute, waiting up to {max_wait}s)")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    
    start = time.time()
    last_status = None
    
    while time.time() - start < max_wait:
        resp = requests.get(
            f"{SUPABASE_URL}/studio_board?id=eq.{row_id}&select=id,status,meta",
            headers=headers,
            timeout=10,
        )
        
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                row = rows[0]
                meta = row.get("meta", {})
                publish_sent = meta.get("publish_event_sent_at")
                current_status = row.get("status")
                
                if current_status != last_status or publish_sent:
                    elapsed = int(time.time() - start)
                    print(f"[{elapsed:3d}s] Status: {current_status}, Event sent: {publish_sent or 'Not yet'}")
                    last_status = current_status
                    
                    if publish_sent:
                        print(f"\n✓ Row processed! Status: {current_status}")
                        print(f"  Event sent at: {publish_sent}")
                        return True
        
        time.sleep(5)
    
    print(f"\n✗ Timeout after {max_wait}s - row not processed")
    return False

def main():
    print("=" * 60)
    print("M2 Automation Loop Test")
    print("=" * 60)
    
    # Step 1: Create approval row
    row_id = create_approval_row()
    if not row_id:
        print("\n✗ Test failed: Could not create approval row")
        return 1
    
    # Step 2: Monitor for processing
    success = check_row_status(row_id)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ M2 AUTOMATION LOOP TEST PASSED")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Check Agent Zero logs for event receipt")
        print("2. Check Discord channel for notification")
        print("3. Verify Supabase row status updated to 'published'")
        return 0
    else:
        print("\n" + "=" * 60)
        print("✗ M2 AUTOMATION LOOP TEST FAILED")
        print("=" * 60)
        print("\nDebugging steps:")
        print("1. Check n8n workflow is active and running")
        print("2. Check n8n execution logs in UI (http://localhost:5678)")
        print("3. Verify AGENT_ZERO_EVENTS_TOKEN is set")
        print("4. Check Agent Zero is running and accessible")
        return 1

if __name__ == "__main__":
    sys.exit(main())
