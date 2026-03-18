#!/usr/bin/env python3
"""
PMOVES E2B DANGER ROOM & X-MEN PERSONA MAPPING
----------------------------------------------
This script demonstrates the multimodal interaction for the Genie LTX Desktop when
the PMOVES E2B Danger Room (Firecracker VMs) initializes.

It natively routes the X-Men Theme through the Flute Gateway, syncs the visual BPM,
and projects match percentages between PMOVES Agents and X-Men Personas to the desktop.
"""

import asyncio
import aiohttp
import nats
import json
import random

FLUTE_GATEWAY_URL = "http://localhost:8055"
NATS_URL = "nats://nats:pmoves@localhost:4222"

# Example mapping of PMOVES agents to X-Men Personas
PERSONA_MAP = {
    "Agent Zero": {"persona": "Professor X", "base_match": 95},
    "Archon": {"persona": "Beast", "base_match": 88},
    "Gateway Agent": {"persona": "Cyclops", "base_match": 92},
    "Supaserch": {"persona": "Jean Grey", "base_match": 85},
    "Crush": {"persona": "Wolverine", "base_match": 90}
}

async def trigger_xmen_theme(session):
    """Route the X-Men Danger Room theme through Flute Gateway."""
    print("[*] Firecracker VM starting. Dispatching X-Men Theme to Flute Gateway...")
    
    # In a full flow, pmoves.yt acquires the audio stream; kitten_tts provides playback.
    payload = {"text": "Playing X-Men Animated Series Theme.", "engine": "kitten_tts"}
    
    try:
        async with session.post(f"{FLUTE_GATEWAY_URL}/v1/voice/synthesize/audio", json=payload) as resp:
            if resp.status == 200:
                print("[+] Flute Gateway acknowledged Danger Room audio stream.")
            else:
                print(f"[!] Flute Gateway Warning: {resp.status} - Ensure Flute is running.")
    except Exception as e:
        print(f"[!] Flute Gateway unreachable: {e}. (Is Port 8055 open?)")

async def publish_desktop_sync(nc):
    """Publish geometry and BPM sync events for LTX Studio desktop visualizers."""
    print("[*] Publishing Genie LTX visual sync events to NATS...")
    
    # 1. Prosodic BPM Event (Syncs the X-Men theme beat with the visual environment)
    bpm_payload = json.dumps({
        "theme": "X-Men Danger Room",
        "bpm": 130, # Upbeat action tempo for the theme
        "action": "start_visuals",
        "target": "genie_ltx_desktop"
    }).encode()
    
    await nc.publish("tokenism.prosodic.bpm.v1", bpm_payload)
    print("  -> Published: tokenism.prosodic.bpm.v1 (Action cadence sync)")

    # 2. Geometry Event (Initializes the Danger Room grid overlay)
    geometry_payload = json.dumps({
        "namespace": "pmoves.desktop.genie",
        "modality": "audiovisual",
        "provider": "e2b_danger_room",
        "scene_geometry": "danger_room_grid",
        "status": "active"
    }).encode()

    await nc.publish("tokenism.geometry.event.v1", geometry_payload)
    print("  -> Published: tokenism.geometry.event.v1 (Danger Room projection initialized)")

async def publish_persona_match(nc, agent_name):
    """Publish the fluctuating match percentage between the Agent and its X-Men Persona."""
    mapping = PERSONA_MAP.get(agent_name)
    if not mapping:
        return

    # Simulate fluctuating match based on current "workload alignment"
    current_match = min(100, max(0, mapping["base_match"] + random.uniform(-5.0, 5.0)))
    
    match_payload = json.dumps({
        "agent": agent_name,
        "xmen_persona": mapping["persona"],
        "match_percentage": round(current_match, 1),
        "ui_element": "hud_overlay"
    }).encode()
    
    await nc.publish("tokenism.persona.match.v1", match_payload)
    print(f"  -> Published: tokenism.persona.match.v1 ({agent_name} aligns {round(current_match,1)}% with {mapping['persona']})")

async def main():
    print("==========================================================")
    print("   GENIE LTX DESKTOP: DANGER ROOM & X-MEN PERSONA MAPPING")
    print("==========================================================")
    
    try:
        nc = await nats.connect(NATS_URL)
        print("[+] Connected to PMOVES NATS Nervous System.")
    except Exception as e:
        print(f"[!] Could not connect to NATS: {e}. Running in dry-run mode.")
        nc = None

    async with aiohttp.ClientSession() as session:
        # Step 1: Simulate Firecracker VM Boot triggering the Audio
        await trigger_xmen_theme(session)
        
        # Step 2: Trigger the visualizer sync and Danger Room grid
        if nc:
            await publish_desktop_sync(nc)
            
            print("\n[*] Initializing Agent Workloads in the Danger Room...")
            # Simulate agents entering the sandbox and finding their persona match
            for agent in ["Agent Zero", "Archon", "Gateway Agent"]:
                await asyncio.sleep(1) # Dramatic pause
                await publish_persona_match(nc, agent)
            
            await nc.close()
            
    print("\n[+] Protocol Complete. The LTX Desktop is now projecting the Danger Room and Persona HUD.")

if __name__ == "__main__":
    asyncio.run(main())
