#!/usr/bin/env python3
"""
PMOVES E2B DANGER ROOM, X-MEN PERSONA MAPPING & HYPERDIMENSIONS
---------------------------------------------------------------
This script demonstrates the multimodal interaction bridging the PMOVES E2B
Danger Room (Firecracker VMs) to the Hyperdimensions Geometry visualizer.

It dynamically maps PMOVES Agents to X-Men Personas based on skill profiles
and generates a 'geometry.visualization.request.v1' (CGP) packet for
Pmoves-hyperdimensions to render mathematically.
"""

import asyncio
import os

import aiohttp
from aiohttp import ClientError, ClientTimeout
import nats
import json
import random
import time

FLUTE_GATEWAY_URL = os.getenv("FLUTE_GATEWAY_URL", "http://localhost:8055")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Agent Skill Profiles (0-100)
AGENTS = {
    "Agent Zero": {"logic": 95, "combat": 70, "empathy": 80, "leadership": 95},
    "Archon": {"logic": 90, "combat": 40, "empathy": 50, "leadership": 60},
    "Gateway Agent": {"logic": 85, "combat": 85, "empathy": 60, "leadership": 90},
    "Supaserch": {"logic": 88, "combat": 60, "empathy": 95, "leadership": 70},
    "Crush": {"logic": 80, "combat": 98, "empathy": 40, "leadership": 50}
}

# X-Men Persona Archetypes (0-100)
XMEN = {
    "Professor X": {"logic": 98, "combat": 10, "empathy": 95, "leadership": 98},
    "Beast": {"logic": 95, "combat": 80, "empathy": 70, "leadership": 50},
    "Cyclops": {"logic": 80, "combat": 90, "empathy": 60, "leadership": 95},
    "Jean Grey": {"logic": 85, "combat": 95, "empathy": 100, "leadership": 75},
    "Wolverine": {"logic": 60, "combat": 100, "empathy": 30, "leadership": 60}
}

def calculate_match(agent_skills, xmen_skills):
    """Dynamically calculates the match percentage based on trait differences."""
    total_diff = 0
    max_diff = len(agent_skills) * 100
    
    for trait in agent_skills:
        diff = abs(agent_skills[trait] - xmen_skills[trait])
        total_diff += diff
        
    match_score = ((max_diff - total_diff) / max_diff) * 100
    
    # Add a slight temporal fluctuation simulating current "workload"
    fluctuation = random.uniform(-3.0, 3.0)
    return round(max(0, min(100, match_score + fluctuation)), 1)

def find_best_xmen_match(agent_name):
    """Finds the X-Men persona that mathematically aligns best with the agent."""
    best_match = None
    best_score = -1
    agent_data = AGENTS[agent_name]

    for xmen_name, xmen_data in XMEN.items():
        score = calculate_match(agent_data, xmen_data)
        if score > best_score:
            best_score = score
            best_match = xmen_name
            
    return best_match, best_score

async def trigger_xmen_theme(session):
    """Route the X-Men Danger Room theme through Flute Gateway."""
    print("[*] Firecracker VM starting. Dispatching X-Men Theme to Flute Gateway...")
    
    payload = {
        "text": "Playing X-Men Animated Series Theme. Danger Room Active.",
        "provider": "kitten_tts",
        "voice": None,
        "output_format": "wav",
    }
    try:
        timeout = ClientTimeout(total=10)
        async with session.post(
            f"{FLUTE_GATEWAY_URL}/v1/voice/synthesize/audio",
            json=payload,
            timeout=timeout,
        ) as resp:
            if resp.status == 200:
                print("[+] Flute Gateway acknowledged Danger Room audio stream.")
            else:
                print(f"[!] Flute Gateway Warning: {resp.status} - Ensure Flute is running.")
    except (ClientError, asyncio.TimeoutError) as e:
        print(f"[!] Flute Gateway unreachable: {e}. (Is Port 8055 open?)")

async def publish_hyperdimensions_geometry(nc, agent_name, xmen_match, match_score):
    """Publish a CGP packet to Hyperdimensions for geometric mapping of the persona logic."""
    print("[*] Publishing CHIT Geometry to Hyperdimensions UI...")
    
    # 1. Provide the structural visualization command (consumed by Pmoves-hyperdimensions)
    cgp_payload = json.dumps({
        "type": "cgp_v0.2",
        "timestamp": int(time.time()),
        "source": "danger_room_evaluator",
        "geometry": {
            "manifold": "poincare_disk", # The Hyperdimensions math canvas
            "nodes": [
                {"id": agent_name, "type": "agent", "radius": 1.0, "color": "blue"},
                {"id": xmen_match, "type": "persona", "radius": 1.0, "color": "gold"}
            ],
            "edges": [
                {"source": agent_name, "target": xmen_match, "weight": match_score / 100.0, "label": f"{match_score}% Match"}
            ],
            "render_flags": {
                "theme": "x-men",
                "pulse_bpm": 130 # tied to the prosodic audio theme
            }
        }
    }).encode()
    
    # Publish to the established PMOVES Geometry Bus
    await nc.publish("geometry.visualization.request.v1", cgp_payload)
    print("  -> Published: geometry.visualization.request.v1")
    print(f"     [Geometry Nodes]: {agent_name} <== {match_score}% ==> {xmen_match}")

async def main():
    print("==========================================================")
    print("   GENIE LTX DESKTOP: DANGER ROOM & HYPERDIMENSIONS")
    print("==========================================================")
    
    try:
        nc = await nats.connect(NATS_URL)
        print("[+] Connected to PMOVES NATS Nervous System.")
    except OSError as e:
        print(f"[!] Could not connect to NATS: {e}. Running in dry-run mode.")
        nc = None

    async with aiohttp.ClientSession() as session:
        # Step 1: Simulate Firecracker VM Boot triggering Audio
        await trigger_xmen_theme(session)
        
        # Step 2: Dynamically calculate and publish geometric mappings
        if nc:
            print("\n[*] Initializing Agent Workloads in the Danger Room...")
            for agent in AGENTS.keys():
                await asyncio.sleep(1.5) # Dramatic mapping pause
                best_match, score = find_best_xmen_match(agent)
                await publish_hyperdimensions_geometry(nc, agent, best_match, score)
            
            await nc.close()
            
    print("\n[+] Protocol Complete. Hyperdimensions UI is now rendering the Persona mappings.")

if __name__ == "__main__":
    asyncio.run(main())
