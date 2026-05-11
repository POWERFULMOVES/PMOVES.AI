#!/usr/bin/env python3
"""
Wealth to CGP Bridge (Wealth Tokenism)

Converts raw wealth metrics (Compute Burn, Token Accrual, Stake Weight, ROI) into 
CGP (Consciousness Geometry Protocol) v0.2 packets for the Geometry Bus.
"""

import json
import math
import time
import hashlib
import argparse
from typing import Dict, List, Any

def _stable_id(seed: str) -> str:
    """Generate a stable 12-char ID from a string."""
    return hashlib.md5(seed.encode()).hexdigest()[:12]

def normalize(val: float, min_v: float, max_v: float) -> float:
    """Normalize value to [0, 1]."""
    if val <= min_v: return 0.0
    if val >= max_v: return 1.0
    return (val - min_v) / (max_v - min_v)

def parse_wealth_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    """Map raw wealth metrics to CGP state vector parameters."""
    # delta: Velocity of money/Compute -> Map from Transaction Volume (0 - 1000 tokens)
    vol = metrics.get("tx_volume", 100)
    delta = normalize(vol, 0, 1000)
    
    # kappa: Capital retention/Curvature -> Map from Savings Rate (0 - 100%) -> inverted
    retention = metrics.get("retention_rate", 50)
    kappa = -1 * normalize(retention, 0, 100)
    
    # Hz: Burn rate / Density -> Map from API Calls/Compute Cost (0 - 5000)
    burn = metrics.get("compute_burn", 1000)
    hz = normalize(burn, 0, 5000)
    
    # A: Stake weight -> Map from Total Staked (0 - 10000)
    stake = metrics.get("staked_tokens", 1000)
    a = normalize(stake, 0, 10000)
    
    # F: ROI / Swarm Fitness -> Derived from the others
    f = (delta + (1 + kappa) + hz + a) / 4.0
    
    return {
        "delta": round(delta, 4),
        "kappa": round(kappa, 4),
        "Hz": round(hz, 4),
        "A": round(a, 4),
        "F": round(f, 4)
    }

def convert_to_cgp(group_name: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a series of wealth events into a CGP payload."""
    points = []
    
    # Calculate group averages
    avg_delta = sum(parse_wealth_metrics(m)["delta"] for m in events) / len(events) if events else 0
    avg_hz = sum(parse_wealth_metrics(m)["Hz"] for m in events) / len(events) if events else 0
    avg_f = sum(parse_wealth_metrics(m)["F"] for m in events) / len(events) if events else 0
    
    # Group Anchor Position
    theta = avg_delta * math.pi
    phi = avg_hz * 2 * math.pi
    r = 10 + avg_f * 5
    anchor = [
        round(r * math.sin(theta) * math.cos(phi), 3),
        round(r * math.sin(theta) * math.sin(phi), 3),
        round(r * math.cos(theta), 3),
    ]

    for event in events:
        sv = parse_wealth_metrics(event)
        offset = [
            sv["delta"] * 2 - 1,
            sv["Hz"] * 2 - 1,
            sv["kappa"],
        ]
        points.append({
            "id": _stable_id(event.get("tx_id", str(time.time()))),
            "label": f"TX: {event.get('tx_id', 'Unknown')}",
            "modality": "wealth_metric",
            "proj": [sv["Hz"], sv["delta"], abs(sv["kappa"])],
            "conf": sv["A"],
            "sv": sv,
            "offset": offset,
            "tx_type": event.get("type", "transfer")
        })

    payload = {
        "spec": "chit.cgp.v0.2",
        "type": "geometry.wealth.v1",
        "id": _stable_id(group_name),
        "label": group_name,
        "source": "wealth_economy_agent",
        "ts": time.time(),
        "super_nodes": [{
            "id": _stable_id(f"sn_{group_name}"),
            "label": f"Economy Cluster: {group_name}",
            "x": 0, "y": 0, "r": 100,
            "constellations": [{
                "id": _stable_id(f"c_{group_name}"),
                "anchor": anchor,
                "points": points
            }]
        }],
        "control_plane": {
            "state_vector": {
                "delta": round(avg_delta, 4),
                "kappa": round(-1 * avg_f, 4),
                "Hz": round(avg_hz, 4),
                "A": 0.0,
                "F": round(avg_f, 4)
            }
        }
    }
    return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wealth to CGP Bridge")
    parser.add_argument("--mock", action="store_true", help="Generate mock data to dump")
    args = parser.parse_args()
    
    if args.mock:
        # Generate mock transactions
        mock_events = [
            {"tx_id": f"TX-00{i}", "tx_volume": 100 * i, "retention_rate": 80 - i, "compute_burn": 200 * i, "staked_tokens": 5000}
            for i in range(1, 8)
        ]
        cgp = convert_to_cgp("Swarm_Economy_Week1", mock_events)
        print(json.dumps(cgp, indent=2))
