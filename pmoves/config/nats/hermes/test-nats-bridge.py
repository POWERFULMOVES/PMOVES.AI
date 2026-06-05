#!/usr/bin/env python3
"""NATS Bridge Test Script for Elder-Melchor Node"""
import sys
import json
import time
import socket

def test_nats_connectivity():
    """Test NATS server connectivity."""
    hosts = [
        ("pmoves-nats", 4222),
        ("<TAILSCALE_IP_ELDER_MELCHOR>", 4222),  # Tailscale fallback
    ]
    
    for host, port in hosts:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            print(f"✓ NATS reachable at {host}:{port}")
            return True, host, port
        except Exception as e:
            print(f"✗ NATS unreachable at {host}:{port} -- {e}")
    
    return False, None, None

def test_publish(subject, payload):
    """Simulate publishing to NATS subject."""
    print(f"Publishing to {subject}: {json.dumps(payload)}")
    # In real implementation, use async-nats or nats-py
    return True

def test_subscribe(subject):
    """Simulate subscribing to NATS subject."""
    print(f"Subscribing to {subject} (simulated)")
    return True

def main():
    print("=== PMOVES NATS Bridge Test: Elder-Melchor ===")
    print(f"Node: elder-melchor")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test connectivity
    ok, host, port = test_nats_connectivity()
    if not ok:
        print("\nNATS connectivity failed. Ensure pmoves-nats is running or Tailscale is up.")
        sys.exit(1)
    
    print()
    
    # Test publish subjects
    publish_subjects = [
        ("hermes.gateway.launched.v1", {"node_id": "elder-melchor", "port": 7700}),
        ("hermes.gateway.health.v1", {"node_id": "elder-melchor", "status": "healthy"}),
    ]
    
    for subject, payload in publish_subjects:
        test_publish(subject, payload)
    
    print()
    
    # Test subscribe subjects
    subscribe_subjects = [
        "p7.nats.launch",
        "mesh.node.announce.v1",
    ]
    
    for subject in subscribe_subjects:
        test_subscribe(subject)
    
    print("\n=== Test Complete ===")
    print("Note: This is a connectivity simulation.")
    print("For full NATS integration, install: uv pip install nats-py")

if __name__ == "__main__":
    main()
