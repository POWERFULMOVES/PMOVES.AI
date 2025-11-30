#!/usr/bin/env python3
"""
Update n8n workflow with proper schema compliance.
Fetches current versionId, strips disallowed fields, and performs PUT.

Usage:
  python3 update_workflow.py <workflow_file.json>
  python3 update_workflow.py  # defaults to pmoves/n8n/flows/approval_poller.json
"""
import json
import os
import sys
import requests

N8N_URL = os.environ.get("N8N_URL", "http://localhost:5678").rstrip("/")
API_KEY = os.environ.get("N8N_KEY")

# Fields allowed by n8n Public API workflow update schema
# Based on API testing - only these fields should be sent in PUT
ALLOWED_FIELDS = {
    "name",
    "nodes",
    "connections",
    "settings",
    "staticData",
}

def strip_payload(raw: dict) -> dict:
    """Keep only allowed fields for PUT /workflows/:id"""
    return {k: v for k, v in raw.items() if k in ALLOWED_FIELDS}

def main():
    if not API_KEY:
        print("ERROR: N8N_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Step 1: Load local workflow definition to get ID
    local_path = sys.argv[1] if len(sys.argv) > 1 else "pmoves/n8n/flows/approval_poller.json"
    
    if not os.path.exists(local_path):
        print(f"ERROR: Workflow file not found: {local_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(local_path, "r", encoding="utf-8") as fh:
        desired = json.load(fh)
    
    # Try workflowId field first (custom field), then id if it looks like a workflow ID
    workflow_id = desired.get("workflowId")
    if not workflow_id:
        candidate = desired.get("id", "")
        # n8n workflow IDs are 16-char alphanumeric
        if len(candidate) == 16 and candidate.replace("-", "").isalnum():
            workflow_id = candidate
    
    if not workflow_id:
        print("ERROR: Workflow file missing 'workflowId' field or valid 'id'", file=sys.stderr)
        print("Add a 'workflowId' field with the n8n workflow ID (e.g., 'iduu9yTMifft1p47')", file=sys.stderr)
        sys.exit(1)
    
    print(f"Workflow: {desired.get('name', 'Unnamed')}")
    print(f"ID: {workflow_id}")
    print(f"Source: {local_path}")
    
    headers = {
        "X-N8N-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }
    
    # Step 2: GET current workflow to grab versionId
    print(f"\nFetching remote workflow...")
    resp = requests.get(
        f"{N8N_URL}/api/v1/workflows/{workflow_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: GET failed with {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)
    
    remote = resp.json()
    print(f"Current versionId: {remote.get('versionId')}")
    print(f"Active: {remote.get('active')}")
    
    # Step 3: Merge server metadata with local changes
    desired["versionId"] = remote["versionId"]
    desired["id"] = workflow_id
    desired["name"] = remote.get("name", "PMOVES • Supabase Approval Poller v1")
    
    # Preserve server-only fields if present
    for key in ("tags", "sharing", "active"):
        if key in remote and key not in desired:
            desired[key] = remote[key]
    
    # Step 4: Strip to allowed fields only
    payload = strip_payload(desired)
    
    print(f"\nPayload fields: {sorted(payload.keys())}")
    print(f"Node count: {len(payload.get('nodes', []))}")
    
    # Step 5: PUT update
    print(f"\nUpdating workflow...")
    update = requests.put(
        f"{N8N_URL}/api/v1/workflows/{workflow_id}",
        headers=headers,
        json=payload,
        timeout=30,
    )
    
    if update.status_code == 200:
        print("✓ Workflow updated successfully")
        result = update.json()
        print(f"New versionId: {result.get('versionId')}")
        return 0
    else:
        print(f"ERROR: PUT failed with {update.status_code}", file=sys.stderr)
        print(update.text, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
