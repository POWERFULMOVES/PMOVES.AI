---
name: minimax-agent-trails
description: Execute AGENT TRAILS roguelike visualization framework for PMOVES agent navigation. This skill should be used when visualizing agent execution lanes, navigating time crystals, or operating in the Transformers/Bumblebee energy framework.
keywords: [agent-trails, roguelike, visualization, lanes, time-crystal, transformer]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Agent Trails

Execute AGENT TRAILS roguelike visualization framework for PMOVES agent navigation with MiniMax tactical inference.

## Purpose

Navigate PMOVES agent execution through the AGENT TRAILS roguelike visualization framework. Implement parallel execution lanes, time crystal context snapshots, and signal switching for autonomous agent operations.

## Capabilities

- 🛤️ Parallel execution lane visualization
- 💎 Time crystal context snapshots
- 🔀 Signal switching at decision points
- 👁️ Double slit observation mechanics
- 🎮 8-bit → 16-bit → PS2 visual evolution

## Integration Points

- **AGENT TRAILS Docs**: `pmoves/docs/AGENT_TRAILS.md`
- **PMOVES-ClawZ**: Kinetic CLI (the Claw)
- **BoTZ Framework**: Gateway auto-routing
- **MiniMax**: Fast tactical partner inference
- **NATS Subject**: `pmoves.agent.trails.v1`

## Theme Architecture

```
┌─────────────────────────────────────────────────────┐
│                    AGENT TRAILS                      │
│           (Transformers meets Bumblebee)            │
├─────────────────────────────────────────────────────┤
│                                                      │
│   🛤️ Lanes ──── Parallel execution tracks           │
│              with signal switching                   │
│                                                      │
│   💎 Time Crystals ─── Context snapshots             │
│                    for rewind/shift                  │
│                                                      │
│   👁️ Double Slit ─── Observation affects            │
│                   behavior                           │
│                                                      │
│   🎮 Evolution ─── 8-bit → 16-bit → PS2              │
│                                                      │
│   ⚡ Hotrod/Spotlight ─── BoTZ tactical dynamics     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Workflow

### 1. Initialize Agent Lane

```yaml
# Lane configuration
lane:
  id: lane_<uuid>
  position: [x, y]
  energy: 100
  context_snapshot: <time_crystal_id>
```

### 2. Execute Lane Navigation

```bash
# Navigate through lane
./scripts/agent-trails-navigate.py \
  --lane-id <id> \
  --action <move|attack|shift|rewind> \
  --context-snapshot <time_crystal>
```

### 3. Capture Time Crystal

```bash
# Save context snapshot
./scripts/time-crystal-save.py \
  --run-id <task_id> \
  --context <snapshot_data>
```

### 4. Execute Rewind/Shift

```bash
# Rewind to previous state
./scripts/time-crystal-rewind.py \
  --crystal-id <time_crystal_id>

# Shift to parallel lane
./scripts/lane-shift.py \
  --from-lane <source> \
  --to-lane <target>
```

## Double Slit Mechanics

Per `pmoves/docs/AGENT_TRAILS.md`:

| Observation | Effect |
|-------------|--------|
| Watched lane | Deterministic collapse |
| Unwatched lane | Quantum superposition |
| Shift observation | Path interference |

## Visual Evolution Tiers

| Tier | Style | Context |
|------|-------|---------|
| 8-bit | Retro arcade | Debug/audit logs |
| 16-bit | Animated sprites | Active navigation |
| PS2 | 3D rendered | Production visualization |

## Example Usage

```
User: "Navigate agent through time crystal rewind"

Agent:
1. Captures current context as time crystal
2. Rewinds to previous state
3. Executes alternate path
4. Captures new time crystal
5. Compares outcomes
```

## Trigger Phrases

- "agent trails navigation"
- "time crystal rewind"
- "execute lane shift"
- "double slit observation"
- "visualize agent execution"
