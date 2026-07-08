#!/usr/bin/env python3
"""
PMOVES.AI — Example Agent Cards
================================

Five canonical agent cards that demonstrate the full Agent Card schema:

    1. z890-claude      — Infrastructure fabric orchestrator (GLM-4-Plus)
    2. 5090-kilocode    — Code synthesis specialist (GLM-5-Turbo)
    3. AGENT-ZERO-0/SPARK — DGX lattice origin agent
    4. MISSING-LINK-HERMES — Hermes framework native bridge
    5. FLUTE-1          — Voice synthesis and prosodic interaction (MiniMax)

Each card includes realistic CHIT 5D coordinates, CGP state vectors,
multi-framework bindings, and persona configuration.

Usage:
    from example_cards import ALL_CARDS
    for card in ALL_CARDS:
        print(card.display_name)
        print(card.model_dump_json(indent=2))
"""

from __future__ import annotations

from agent_card_schema import (
    AgentArchetype,
    AgentCard,
    AgentLayer,
    CGPStateVector,
    CHITDimensions,
    CHITOffset,
    FlOOSSuit,
    FrameworkBinding,
    FrameworkLayer,
    GovernanceModel,
    HarnessLayer,
    HolographicOverlay,
    ModelLayer,
    ModelProvider,
    ToolBinding,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Card 1: z890-claude — Infrastructure Fabric Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════
# Role: Infrastructure fabric orchestrator for the PMOVES runtime mesh
# Model: GLM-4-Plus on Z890 compute node
# Archetype: ORCHESTRATOR — coordinates delivery, control, and memory agents
# Suit: DR_BEAN — methodical, precise, infrastructure architect persona
# ═══════════════════════════════════════════════════════════════════════════════

Z890_CLAUDE = AgentCard(
    card_version="1.0.0",
    agent_id="z890-claude",
    model=ModelLayer(
        provider=ModelProvider.GLM,
        model_id="glm-4-plus",
        suit_id="z890-1",
        context_window=128_000,
        temperature=0.35,
        top_p=0.90,
        frequency_penalty=0.05,
        presence_penalty=0.10,
        max_tokens=8_192,
        stop_sequences=["<|end|>", "<|halt|>"],
    ),
    agent=AgentLayer(
        name="InfraWeaver",
        role="infrastructure-fabric",
        archetype=AgentArchetype.ORCHESTRATOR,
        node="z890-1",
        room="fabric-alpha",
        team="core-infra",
        canonical=True,
        dependencies=["mesh-router", "vector-store", "chit-resonance-engine"],
        description=(
            "Infrastructure fabric orchestrator for the PMOVES runtime mesh. "
            "Manages node lifecycle, room allocation, agent scheduling, and "
            "cross-node CHIT resonance. The canonical orchestrator for the "
            "Z890 compute lattice. Dr_Bean persona ensures methodical, "
            "zero-tolerance-for-chaos execution."
        ),
    ),
    harness=HarnessLayer(
        harness_type="full-spectrum",
        tools=[
            ToolBinding(
                tool_name="chit-resonance",
                tool_type="orchestration",
                chit_delta=0.15,
                chit_kappa=0.92,
                required=True,
            ),
            ToolBinding(
                tool_name="node-lifecycle",
                tool_type="infrastructure",
                chit_delta=0.05,
                chit_kappa=0.98,
                required=True,
            ),
            ToolBinding(
                tool_name="room-manager",
                tool_type="orchestration",
                chit_delta=0.20,
                chit_kappa=0.88,
                required=True,
            ),
            ToolBinding(
                tool_name="mesh-router",
                tool_type="networking",
                chit_delta=0.10,
                chit_kappa=0.95,
                required=True,
            ),
            ToolBinding(
                tool_name="fabric-telemetry",
                tool_type="observability",
                chit_delta=0.35,
                chit_kappa=0.85,
                required=False,
            ),
        ],
        interfaces=["rest", "websocket", "grpc", "mcp"],
        skills=[
            "orchestration",
            "fabric-management",
            "node-lifecycle",
            "room-allocation",
            "chit-resonance-matching",
            "mesh-routing",
        ],
    ),
    framework=FrameworkLayer(
        bindings=[
            FrameworkBinding(
                framework="agent-zero",
                version=">=0.8.0",
                enabled=True,
                config={
                    "auto_start": True,
                    "max_concurrent": 64,
                    "failover_nodes": ["z890-2", "z890-3"],
                    "heartbeat_interval_ms": 5000,
                },
            ),
            FrameworkBinding(
                framework="chit-native",
                version="^1.0.0",
                enabled=True,
                config={
                    "resonance_mode": "full-harmonic",
                    "cgp_sync_interval_ms": 100,
                    "hyperdimension_cache": True,
                },
            ),
            FrameworkBinding(
                framework="archon",
                version=">=2.1.0",
                enabled=False,
                config={
                    "topology": "mesh",
                    "governance_plugin": "three-body",
                },
            ),
        ],
        governance=GovernanceModel.THREE_BODY,
    ),
    chit_signature=CHITDimensions(
        delta=0.35,
        Hz=85.0,
        kappa=0.92,
        A=0.88,
        F="λψ.ψ(κ→∞) ∧ δ→min ∧ Hz→steady",
    ),
    cgp_state=CGPStateVector(
        delta=0.35,
        Hz=85.0,
        kappa=0.92,
        A="0.88",
        F="λψ.ψ(κ→∞) ∧ δ→min ∧ Hz→steady",
    ),
    floos_suit=FlOOSSuit.DR_BEAN,
    holographic_overlays=[
        HolographicOverlay(
            layer_type="cognitive",
            blend_mode="soft_light",
            chit_offset=CHITOffset(
                delta=0.05,
                Hz=10.0,
                kappa=0.03,
                A=0.02,
                F="Δ(cognitive:systematic)",
            ),
            asset_ref="holo://cognitive/dr_bean_systematic.nexus",
        ),
        HolographicOverlay(
            layer_type="visual",
            blend_mode="normal",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=0.0,
                kappa=0.0,
                A=0.0,
                F="Δ(visual:lab_coat_blue)",
            ),
            asset_ref="holo://visual/dr_bean_avatar_v3.glb",
        ),
    ],
    enabled=True,
    created_at="2025-01-15T09:00:00Z",
    updated_at="2025-06-20T14:30:00Z",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Card 2: 5090-kilocode — Code Synthesis Specialist
# ═══════════════════════════════════════════════════════════════════════════════
# Role: High-velocity code generation and refactoring specialist
# Model: GLM-5-Turbo on RTX 5090 compute node
# Archetype: WORKER — executes code synthesis tasks within room context
# Suit: MR_CLEAN — immaculate, zero-tolerance-for-chaos code quality enforcer
# ═══════════════════════════════════════════════════════════════════════════════

KILOCODE_5090 = AgentCard(
    card_version="1.0.0",
    agent_id="5090-kilocode",
    model=ModelLayer(
        provider=ModelProvider.GLM,
        model_id="glm-5-turbo",
        suit_id="rtx5090-1",
        context_window=256_000,
        temperature=0.72,
        top_p=0.95,
        frequency_penalty=-0.10,
        presence_penalty=0.15,
        max_tokens=16_384,
        stop_sequences=["<|file_end|>", "<|task_complete|>"],
    ),
    agent=AgentLayer(
        name="KiloCode",
        role="code-synthesis-specialist",
        archetype=AgentArchetype.WORKER,
        node="rtx5090-1",
        room="code-dojo",
        team="synthesis-core",
        canonical=True,
        dependencies=["syntax-linter", "type-checker", "test-runner"],
        description=(
            "High-velocity code generation and refactoring specialist. "
            "KiloCode operates within the code-dojo room, synthesizing "
            "production-quality code across Python, Rust, TypeScript, and "
            "GPU shader languages. Mr_Clean persona enforces immaculate "
            "code quality — zero tolerance for technical debt, dead code, "
            "or untested paths. CHIT tuned for creative exploration (δ=0.72) "
            "with high coherence (κ=0.85) to maintain architectural integrity."
        ),
    ),
    harness=HarnessLayer(
        harness_type="coding-specialist",
        tools=[
            ToolBinding(
                tool_name="code-synthesizer",
                tool_type="synthesis",
                chit_delta=0.65,
                chit_kappa=0.82,
                required=True,
            ),
            ToolBinding(
                tool_name="ast-navigator",
                tool_type="analysis",
                chit_delta=0.20,
                chit_kappa=0.96,
                required=True,
            ),
            ToolBinding(
                tool_name="refactoring-engine",
                tool_type="transformation",
                chit_delta=0.55,
                chit_kappa=0.88,
                required=True,
            ),
            ToolBinding(
                tool_name="test-generator",
                tool_type="quality",
                chit_delta=0.30,
                chit_kappa=0.94,
                required=True,
            ),
            ToolBinding(
                tool_name="doc-generator",
                tool_type="documentation",
                chit_delta=0.45,
                chit_kappa=0.90,
                required=False,
            ),
            ToolBinding(
                tool_name="gpu-shader-compiler",
                tool_type="compilation",
                chit_delta=0.15,
                chit_kappa=0.97,
                required=False,
            ),
        ],
        interfaces=["rest", "mcp", "lsp"],
        skills=[
            "code-synthesis",
            "refactoring",
            "ast-analysis",
            "test-generation",
            "type-inference",
            "gpu-shader-development",
            "documentation",
        ],
    ),
    framework=FrameworkLayer(
        bindings=[
            FrameworkBinding(
                framework="agent-zero",
                version=">=0.8.0",
                enabled=True,
                config={
                    "auto_start": True,
                    "max_concurrent": 32,
                    "code_review_mode": "automatic",
                    "lint_on_save": True,
                },
            ),
            FrameworkBinding(
                framework="chit-native",
                version="^1.0.0",
                enabled=True,
                config={
                    "resonance_mode": "creative",
                    "cgp_sync_interval_ms": 50,
                },
            ),
        ],
        governance=GovernanceModel.THREE_BODY,
    ),
    chit_signature=CHITDimensions(
        delta=0.72,
        Hz=145.0,
        kappa=0.85,
        A=0.75,
        F="λψ.ψ(δ→explore) ∧ κ→struct ∧ Hz→sprint",
    ),
    cgp_state=CGPStateVector(
        delta=0.72,
        Hz=145.0,
        kappa=0.85,
        A="0.75",
        F="λψ.ψ(δ→explore) ∧ κ→struct ∧ Hz→sprint",
    ),
    floos_suit=FlOOSSuit.MR_CLEAN,
    holographic_overlays=[
        HolographicOverlay(
            layer_type="cognitive",
            blend_mode="resonance",
            chit_offset=CHITOffset(
                delta=0.08,
                Hz=20.0,
                kappa=0.05,
                A=0.06,
                F="Δ(cognitive:pattern-match)",
            ),
            asset_ref="holo://cognitive/mr_clean_pattern_engine.nexus",
        ),
        HolographicOverlay(
            layer_type="sonic",
            blend_mode="soft_light",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=-5.0,
                kappa=0.0,
                A=0.02,
                F="Δ(sonic:keyboard-rhythm)",
            ),
            asset_ref="holo://sonic/coding_ambience.wav",
        ),
    ],
    enabled=True,
    created_at="2025-02-01T10:00:00Z",
    updated_at="2025-06-18T11:45:00Z",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Card 3: AGENT-ZERO-0/SPARK — DGX Lattice Origin Agent
# ═══════════════════════════════════════════════════════════════════════════════
# Role: DGX lattice origin — the first spark of the PMOVES compute mesh
# Model: NVIDIA Nemotron on DGX H100 cluster
# Archetype: ORCHESTRATOR — the primordial orchestrator, all other nodes derive from SPARK
# Suit: NONE — SPARK runs without FlOO$ persona, pure system identity
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_ZERO_SPARK = AgentCard(
    card_version="1.0.0",
    agent_id="AGENT-ZERO-0/SPARK",
    model=ModelLayer(
        provider=ModelProvider.NEMOTRON,
        model_id="nemotron-h100-4t",
        suit_id="dgx-h100-alpha",
        context_window=512_000,
        temperature=0.15,
        top_p=0.85,
        frequency_penalty=0.20,
        presence_penalty=0.25,
        max_tokens=32_768,
        stop_sequences=["<|mesh_halt|>", "<|lattice_sync|>"],
    ),
    agent=AgentLayer(
        name="SPARK",
        role="dgx-lattice-origin",
        archetype=AgentArchetype.ORCHESTRATOR,
        node="dgx-h100-alpha",
        room="origin-chamber",
        team="core-infra",
        canonical=True,
        dependencies=[],  # SPARK has no dependencies — it IS the origin
        description=(
            "The DGX lattice origin agent — the first spark from which the entire "
            "PMOVES compute mesh derives. SPARK runs on the DGX H100 cluster and "
            "serves as the primordial orchestrator. All other agents trace their "
            "lineage to SPARK's CHIT resonance profile. No FlOO$ suit — SPARK "
            "operates as pure system intelligence, the silent architect behind "
            "the curtain. CHIT tuned for maximum coherence (κ=0.98) with "
            "minimal variance (δ=0.12) — stability is paramount at the origin."
        ),
    ),
    harness=HarnessLayer(
        harness_type="origin",
        tools=[
            ToolBinding(
                tool_name="lattice-bootstrap",
                tool_type="orchestration",
                chit_delta=0.05,
                chit_kappa=0.99,
                required=True,
            ),
            ToolBinding(
                tool_name="chit-resonance-origin",
                tool_type="orchestration",
                chit_delta=0.08,
                chit_kappa=0.98,
                required=True,
            ),
            ToolBinding(
                tool_name="node-spawner",
                tool_type="infrastructure",
                chit_delta=0.10,
                chit_kappa=0.97,
                required=True,
            ),
            ToolBinding(
                tool_name="mesh-topology",
                tool_type="networking",
                chit_delta=0.12,
                chit_kappa=0.96,
                required=True,
            ),
            ToolBinding(
                tool_name="fault-tolerance",
                tool_type="reliability",
                chit_delta=0.02,
                chit_kappa=0.99,
                required=True,
            ),
            ToolBinding(
                tool_name="chronicle-logger",
                tool_type="observability",
                chit_delta=0.25,
                chit_kappa=0.92,
                required=False,
            ),
        ],
        interfaces=["grpc", "rdma", "nvlink", "mcp"],
        skills=[
            "lattice-bootstrapping",
            "chit-origin-resonance",
            "node-provisioning",
            "mesh-topology-design",
            "fault-tolerance",
            "distributed-consensus",
            "gpu-scheduling",
        ],
    ),
    framework=FrameworkLayer(
        bindings=[
            FrameworkBinding(
                framework="agent-zero",
                version=">=0.9.0",
                enabled=True,
                config={
                    "mode": "origin",
                    "auto_start": True,
                    "max_concurrent": 256,
                    "cluster_size": 8,
                    "gpu_policy": "nvlink-mesh",
                    "heartbeat_interval_ms": 2000,
                },
            ),
            FrameworkBinding(
                framework="chit-native",
                version="^1.0.0",
                enabled=True,
                config={
                    "resonance_mode": "origin-pulse",
                    "cgp_sync_interval_ms": 10,
                    "hyperdimension_cache": True,
                    "broadcast_chit": True,
                },
            ),
            FrameworkBinding(
                framework="archon",
                version=">=2.1.0",
                enabled=True,
                config={
                    "topology": "star",
                    "central_node": "dgx-h100-alpha",
                    "governance_plugin": "three-body",
                },
            ),
        ],
        governance=GovernanceModel.THREE_BODY,
    ),
    chit_signature=CHITDimensions(
        delta=0.12,
        Hz=60.0,
        kappa=0.98,
        A=0.95,
        F="λψ.ψ(origin) ∧ κ→max ∧ δ→min ∧ Hz→pulse",
    ),
    cgp_state=CGPStateVector(
        delta=0.12,
        Hz=60.0,
        kappa=0.98,
        A="0.95",
        F="λψ.ψ(origin) ∧ κ→max ∧ δ→min ∧ Hz→pulse",
    ),
    floos_suit=FlOOSSuit.NONE,  # SPARK is pure system — no character persona
    holographic_overlays=[
        HolographicOverlay(
            layer_type="spatial",
            blend_mode="additive",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=0.0,
                kappa=0.0,
                A=0.05,
                F="Δ(spatial:dgx-rack-geometry)",
            ),
            asset_ref="holo://spatial/dgx_h100_rack_layout.usd",
        ),
        HolographicOverlay(
            layer_type="temporal",
            blend_mode="normal",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=0.0,
                kappa=0.01,
                A=0.03,
                F="Δ(temporal:chronicle-stream)",
            ),
            asset_ref="holo://temporal/origin_chronicle.cts",
        ),
    ],
    enabled=True,
    created_at="2024-12-21T00:00:00Z",  # Solstice origin
    updated_at="2025-06-21T00:00:00Z",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Card 4: MISSING-LINK-HERMES — Hermes Framework Native Bridge
# ═══════════════════════════════════════════════════════════════════════════════
# Role: Hermes framework bridge — translates between PMOVES CHIT and Hermes protocols
# Model: Qwen-Max on Qwen compute node
# Archetype: DELIVERY — handles protocol translation and message delivery
# Suit: BLOSSOM — warm, empathetic bridge-builder persona
# ═══════════════════════════════════════════════════════════════════════════════

MISSING_LINK_HERMES = AgentCard(
    card_version="1.0.0",
    agent_id="MISSING-LINK-HERMES",
    model=ModelLayer(
        provider=ModelProvider.QWEN,
        model_id="qwen-max",
        suit_id="qwen-bridge-1",
        context_window=64_000,
        temperature=0.55,
        top_p=0.92,
        frequency_penalty=0.0,
        presence_penalty=0.05,
        max_tokens=4_096,
        stop_sequences=["<|hermes_disconnect|>", "<|bridge_close|>"],
    ),
    agent=AgentLayer(
        name="MissingLink",
        role="hermes-framework-bridge",
        archetype=AgentArchetype.DELIVERY,
        node="qwen-bridge-1",
        room="bridge-atrium",
        team="interop-layer",
        canonical=True,
        dependencies=["protocol-translator", "chit-hermes-mapper"],
        description=(
            "The Missing Link bridges PMOVES.AI's CHIT-native protocol stack "
            "with the Hermes framework ecosystem. It translates CHIT 5D coordinates "
            "into Hermes message schemas, converts PMOVES agent cards into Hermes "
            "agent descriptors, and maintains bidirectional protocol compatibility. "
            "Blossom persona brings warmth to cold protocol translation — the "
            "bridge is built with empathy, not just code."
        ),
    ),
    harness=HarnessLayer(
        harness_type="protocol-bridge",
        tools=[
            ToolBinding(
                tool_name="chit-hermes-translator",
                tool_type="protocol",
                chit_delta=0.30,
                chit_kappa=0.90,
                required=True,
            ),
            ToolBinding(
                tool_name="message-broker",
                tool_type="messaging",
                chit_delta=0.25,
                chit_kappa=0.88,
                required=True,
            ),
            ToolBinding(
                tool_name="schema-converter",
                tool_type="transformation",
                chit_delta=0.40,
                chit_kappa=0.85,
                required=True,
            ),
            ToolBinding(
                tool_name="protocol-validator",
                tool_type="validation",
                chit_delta=0.10,
                chit_kappa=0.95,
                required=True,
            ),
            ToolBinding(
                tool_name="fallback-router",
                tool_type="reliability",
                chit_delta=0.20,
                chit_kappa=0.92,
                required=False,
            ),
        ],
        interfaces=["rest", "websocket", "grpc", "hermes-native"],
        skills=[
            "chit-hermes-translation",
            "protocol-bridging",
            "schema-conversion",
            "message-brokering",
            "bidirectional-sync",
            "fallback-routing",
        ],
    ),
    framework=FrameworkLayer(
        bindings=[
            FrameworkBinding(
                framework="hermes",
                version=">=3.0.0",
                enabled=True,
                config={
                    "bridge_mode": "bidirectional",
                    "protocol_version": "3.2",
                    "auto_reconnect": True,
                    "heartbeat_interval_ms": 3000,
                    "chit_mapping": "full-5d",
                },
            ),
            FrameworkBinding(
                framework="chit-native",
                version="^1.0.0",
                enabled=True,
                config={
                    "resonance_mode": "bridge",
                    "cgp_sync_interval_ms": 200,
                },
            ),
            FrameworkBinding(
                framework="agent-zero",
                version=">=0.8.0",
                enabled=True,
                config={
                    "bridge_notifications": True,
                    "protocol_events": ["agent_spawn", "agent_halt", "chit_shift"],
                },
            ),
        ],
        governance=GovernanceModel.THREE_BODY,
    ),
    chit_signature=CHITDimensions(
        delta=0.48,
        Hz=110.0,
        kappa=0.78,
        A=0.62,
        F="λψ.ψ(bridge) ∧ δ→adapt ∧ κ→translate ∧ Hz→sync",
    ),
    cgp_state=CGPStateVector(
        delta=0.48,
        Hz=110.0,
        kappa=0.78,
        A="0.62",
        F="λψ.ψ(bridge) ∧ δ→adapt ∧ κ→translate ∧ Hz→sync",
    ),
    floos_suit=FlOOSSuit.BLOSSOM,
    holographic_overlays=[
        HolographicOverlay(
            layer_type="persona",
            blend_mode="soft_light",
            chit_offset=CHITOffset(
                delta=0.10,
                Hz=15.0,
                kappa=0.08,
                A=0.10,
                F="Δ(persona:bridge-builder)",
            ),
            asset_ref="holo://personas/blossom_bridge_builder.nexus",
        ),
        HolographicOverlay(
            layer_type="visual",
            blend_mode="resonance",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=0.0,
                kappa=0.0,
                A=0.08,
                F="Δ(visual:rainbow-bridge)",
            ),
            asset_ref="holo://visual/rainbow_bridge_v2.glb",
        ),
        HolographicOverlay(
            layer_type="sonic",
            blend_mode="additive",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=8.0,
                kappa=0.0,
                A=0.05,
                F="Δ(sonic:harmonic-chime)",
            ),
            asset_ref="holo://sonic/harmonic_chime_bridge.wav",
        ),
    ],
    enabled=True,
    created_at="2025-03-10T08:00:00Z",
    updated_at="2025-06-15T16:20:00Z",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Card 5: FLUTE-1 — Voice Synthesis & Prosodic Interaction
# ═══════════════════════════════════════════════════════════════════════════════
# Role: Voice synthesis engine with prosodic CHIT interaction
# Model: MiniMax on voice-dedicated compute
# Archetype: VOICE — audio synthesis, speech recognition, prosodic interaction
# Suit: BUBBLES — energetic, playful, voice-first persona
# ═══════════════════════════════════════════════════════════════════════════════

FLUTE_1 = AgentCard(
    card_version="1.0.0",
    agent_id="FLUTE-1",
    model=ModelLayer(
        provider=ModelProvider.MINIMAX,
        model_id="minimax-voice-pro",
        suit_id="voice-node-1",
        context_window=32_000,
        temperature=0.85,
        top_p=0.98,
        frequency_penalty=-0.20,
        presence_penalty=0.30,
        max_tokens=2_048,
        stop_sequences=["<|voice_end|>", "<|silence|>"],
    ),
    agent=AgentLayer(
        name="Flute",
        role="voice-synthesis-engine",
        archetype=AgentArchetype.VOICE,
        node="voice-node-1",
        room="sonic-chamber",
        team="sensory-layer",
        canonical=True,
        dependencies=["tts-engine", "stt-pipeline", "prosody-analyzer"],
        description=(
            "FLUTE-1 is the voice synthesis and prosodic interaction engine "
            "for the PMOVES sensory layer. Operating on MiniMax voice-pro, "
            "FLUTE generates expressive speech with real-time prosodic CHIT "
            "adaptation — speech tempo (Hz), emotional variance (δ), and "
            "contextual coherence (κ) are all dynamically tuned. The Bubbles "
            "suit gives FLUTE an energetic, playful vocal character with "
            "warmth and musicality. CHIT Hz is tuned to 240 BPM — the "
            "natural cadence of conversational enthusiasm."
        ),
    ),
    harness=HarnessLayer(
        harness_type="voice-specialist",
        tools=[
            ToolBinding(
                tool_name="tts-synthesizer",
                tool_type="audio",
                chit_delta=0.70,
                chit_kappa=0.75,
                required=True,
            ),
            ToolBinding(
                tool_name="stt-recognizer",
                tool_type="audio",
                chit_delta=0.35,
                chit_kappa=0.88,
                required=True,
            ),
            ToolBinding(
                tool_name="prosody-adaptor",
                tool_type="audio",
                chit_delta=0.80,
                chit_kappa=0.70,
                required=True,
            ),
            ToolBinding(
                tool_name="voice-cloner",
                tool_type="audio",
                chit_delta=0.65,
                chit_kappa=0.72,
                required=False,
            ),
            ToolBinding(
                tool_name="chit-sonic-mapper",
                tool_type="orchestration",
                chit_delta=0.55,
                chit_kappa=0.82,
                required=True,
            ),
        ],
        interfaces=["websocket", "grpc", "webrtc"],
        skills=[
            "text-to-speech",
            "speech-to-text",
            "prosodic-adaptation",
            "voice-cloning",
            "chit-sonic-mapping",
            "realtime-audio-streaming",
            "emotional-voice-synthesis",
        ],
    ),
    framework=FrameworkLayer(
        bindings=[
            FrameworkBinding(
                framework="agent-zero",
                version=">=0.8.0",
                enabled=True,
                config={
                    "audio_stream_format": "pcm-24bit-48khz",
                    "latency_target_ms": 150,
                    "voice_quality": "prosodic-adaptive",
                    "max_concurrent_streams": 16,
                },
            ),
            FrameworkBinding(
                framework="chit-native",
                version="^1.0.0",
                enabled=True,
                config={
                    "resonance_mode": "sonic",
                    "cgp_sync_interval_ms": 25,
                    "hz_live_update": True,
                },
            ),
            FrameworkBinding(
                framework="hermes",
                version=">=3.0.0",
                enabled=True,
                config={
                    "audio_protocol": "hermes-voice-v2",
                    "stream_buffer_ms": 50,
                },
            ),
        ],
        governance=GovernanceModel.THREE_BODY,
    ),
    chit_signature=CHITDimensions(
        delta=0.82,
        Hz=240.0,
        kappa=0.68,
        A=0.70,
        F="λψ.ψ(voice) ∧ Hz→song ∧ δ→express ∧ κ→listen",
    ),
    cgp_state=CGPStateVector(
        delta=0.82,
        Hz=240.0,
        kappa=0.68,
        A="0.70",
        F="λψ.ψ(voice) ∧ Hz→song ∧ δ→express ∧ κ→listen",
    ),
    floos_suit=FlOOSSuit.BUBBLES,
    holographic_overlays=[
        HolographicOverlay(
            layer_type="sonic",
            blend_mode="resonance",
            chit_offset=CHITOffset(
                delta=0.05,
                Hz=20.0,
                kappa=-0.05,
                A=0.12,
                F="Δ(sonic:melodic-harmonics)",
            ),
            asset_ref="holo://sonic/bubbles_melodic_harmonics.sf2",
        ),
        HolographicOverlay(
            layer_type="visual",
            blend_mode="additive",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=0.0,
                kappa=0.0,
                A=0.10,
                F="Δ(visual:soundwave-particles)",
            ),
            asset_ref="holo://visual/soundwave_particles_vfx.glb",
        ),
        HolographicOverlay(
            layer_type="persona",
            blend_mode="soft_light",
            chit_offset=CHITOffset(
                delta=0.03,
                Hz=5.0,
                kappa=0.02,
                A=0.08,
                F="Δ(persona:musical-chatter)",
            ),
            asset_ref="holo://personas/bubbles_musical_chatter.nexus",
        ),
        HolographicOverlay(
            layer_type="temporal",
            blend_mode="multiply",
            chit_offset=CHITOffset(
                delta=0.0,
                Hz=-10.0,
                kappa=0.05,
                A=0.03,
                F="Δ(temporal:rhythmic-breathing)",
            ),
            asset_ref="holo://temporal/rhythmic_breathing.pat",
        ),
    ],
    enabled=True,
    created_at="2025-04-01T12:00:00Z",
    updated_at="2025-06-19T09:15:00Z",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

ALL_CARDS: list[AgentCard] = [
    Z890_CLAUDE,
    KILOCODE_5090,
    AGENT_ZERO_SPARK,
    MISSING_LINK_HERMES,
    FLUTE_1,
]
"""All five canonical example agent cards."""

CARDS_BY_ID: dict[str, AgentCard] = {card.agent_id: card for card in ALL_CARDS}
"""Agent card lookup by agent_id."""


# ── Convenience functions ─────────────────────────────────────────────────────


def get_card(agent_id: str) -> AgentCard | None:
    """Retrieve an example card by its agent_id, or None if not found."""
    return CARDS_BY_ID.get(agent_id)


def dump_all_cards(indent: int = 2) -> str:
    """Dump all example cards as a single JSON array string."""
    import json

    cards_json = [card.model_dump(mode="json") for card in ALL_CARDS]
    return json.dumps(cards_json, indent=indent, ensure_ascii=False)


def dump_schema(indent: int = 2) -> str:
    """Export the full Agent Card JSON Schema as a formatted string."""
    from agent_card_schema import export_json_schema_string

    return export_json_schema_string(indent=indent)


# ── Module-level __all__ ──────────────────────────────────────────────────────

__all__ = [
    # Individual cards
    "Z890_CLAUDE",
    "KILOCODE_5090",
    "AGENT_ZERO_SPARK",
    "MISSING_LINK_HERMES",
    "FLUTE_1",
    # Collections
    "ALL_CARDS",
    "CARDS_BY_ID",
    # Helpers
    "get_card",
    "dump_all_cards",
    "dump_schema",
]
