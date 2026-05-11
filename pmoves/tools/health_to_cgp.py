#!/usr/bin/env python3
"""
Health to CGP Bridge (Health Tokenism)

Converts raw health metrics (BPM, HRV, Activity, Sleep) into 
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

def parse_health_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    """Map raw health metrics to CGP state vector parameters."""
    # delta: Velocity/Activity -> Map from Daily Steps (0 - 20000)
    steps = metrics.get("steps", 5000)
    delta = normalize(steps, 0, 20000)
    
    # kappa: Curvature/Sleep -> Map from Sleep Score (0 - 100) -> inverted for curvature
    sleep = metrics.get("sleep_score", 50)
    kappa = -1 * normalize(sleep, 0, 100)
    
    # Hz: Metabolic Burn / Entropy -> Map from Active Calories (0 - 2000)
    cals = metrics.get("active_calories", 500)
    hz = normalize(cals, 0, 2000)
    
    # A: Dietary Adherence -> Map from Diet Score (0 - 100)
    diet = metrics.get("diet_score", 50)
    a = normalize(diet, 0, 100)
    
    # F: Overall Vitality -> Derived from the others
    f = (delta + (1 + kappa) + hz + a) / 4.0
    
    return {
        "delta": round(delta, 4),
        "kappa": round(kappa, 4),
        "Hz": round(hz, 4),
        "A": round(a, 4),
        "F": round(f, 4)
    }

def convert_to_cgp(group_name: str, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a series of daily logs into a CGP payload."""
    points = []
    
    # Calculate group averages
    avg_delta = sum(parse_health_metrics(m)["delta"] for m in logs) / len(logs) if logs else 0
    avg_kappa = sum(parse_health_metrics(m)["kappa"] for m in logs) / len(logs) if logs else 0
    avg_hz = sum(parse_health_metrics(m)["Hz"] for m in logs) / len(logs) if logs else 0
    avg_a = sum(parse_health_metrics(m)["A"] for m in logs) / len(logs) if logs else 0
    avg_f = sum(parse_health_metrics(m)["F"] for m in logs) / len(logs) if logs else 0
    
    # Group Anchor Position
    theta = avg_delta * math.pi
    phi = avg_hz * 2 * math.pi
    r = 10 + avg_f * 5
    anchor = [
        round(r * math.sin(theta) * math.cos(phi), 3),
        round(r * math.sin(theta) * math.sin(phi), 3),
        round(r * math.cos(theta), 3),
    ]

    for log in logs:
        sv = parse_health_metrics(log)
        offset = [
            sv["delta"] * 2 - 1,
            sv["Hz"] * 2 - 1,
            sv["kappa"],
        ]
        points.append({
            "id": _stable_id(log.get("date", str(time.time()))),
            "label": f"Daily Log: {log.get('date', 'Unknown')}",
            "modality": "health_metric",
            "proj": [sv["Hz"], sv["delta"], abs(sv["kappa"])],
            "conf": sv["A"],
            "sv": sv,
            "offset": offset,
            "date": log.get("date", "")
        })

    payload = {
        "spec": "chit.cgp.v0.2",
        "type": "geometry.health.v1",
        "id": _stable_id(group_name),
        "label": group_name,
        "source": "health_vitality_agent",
        "ts": time.time(),
        "super_nodes": [{
            "id": _stable_id(f"sn_{group_name}"),
            "label": f"Health Cluster: {group_name}",
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
                "kappa": round(avg_kappa, 4),
                "Hz": round(avg_hz, 4),
                "A": round(avg_a, 4),
                "F": round(avg_f, 4)
            }
        }
    }
    return payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Health to CGP Bridge")
    parser.add_argument("--mock", action="store_true", help="Generate mock data to dump")
    args = parser.parse_args()
    
    if args.mock:
        # Generate mock 7-day logs
        mock_logs = [
            {"date": f"2026-05-0{i}", "steps": 5000 + i*1000, "sleep_score": 70 + i*2, "active_calories": 500 + i*50, "diet_score": 80}
            for i in range(1, 8)
        ]
        cgp = convert_to_cgp("User_Vitality_Week1", mock_logs)
        print(json.dumps(cgp, indent=2))
