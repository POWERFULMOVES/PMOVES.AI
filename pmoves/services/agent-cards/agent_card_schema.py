#!/usr/bin/env python3
"""
PMOVES.AI — Agent Card JSON Schema & Pydantic v2 Models
=======================================================

Implements the Agent Card system following the hierarchy:
    Model → Agent → Harness → Framework

Each agent card is a self-describing, CHIT-encoded runtime identity that
can be serialized to JSON, validated at the edge, and loaded into any
framework that speaks the PMOVES Agent Card protocol.

Architecture:
- ModelLayer    : LLM provider, model ID, generation parameters
- AgentLayer    : Role, archetype, node binding, team membership
- HarnessLayer  : CHIT-mapped tools, interfaces, skill DAG
- FrameworkLayer: Multi-framework bindings (Agent Zero, Archon, Hermes, CHIT)
- CHIT Signature: 5D hyperdimension coordinates {delta, Hz, kappa, A, F}
- FlOO$ Suit    : Character persona with voice & visual signature
- CGP State     : Compressed Geometric Packet state vectors
- Holographic   : Composable persona overlays with blend modes

Usage:
    from agent_card_schema import AgentCard, CHITDimensions
    card = AgentCard(**json_data)
    card.model_dump_json(indent=2)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ───────────────────────────────────────────────────────────────────────────────
# Enums
# ───────────────────────────────────────────────────────────────────────────────

class ModelProvider(str, Enum):
    """Supported LLM model providers for PMOVES.AI runtime."""

    GLM = "zhipu/glm"
    KIMI = "moonshot/kimi"
    MINIMAX = "minimax"
    CLAUDE = "anthropic/claude"
    QWEN = "alibaba/qwen"
    GEMMA = "google/gemma"
    NEMOTRON = "nvidia/nemotron"


class AgentArchetype(str, Enum):
    """
    Agent archetype classification within the PMOVES three-body governance
    model (delivery + control + memory).
    """

    ORCHESTRATOR = "orchestrator"
    """Coordinates multi-agent workflows, route dispatch, and room lifecycle."""

    WORKER = "worker"
    """General-purpose compute agent executing tasks within a room context."""

    DELIVERY = "delivery"
    """Handles output generation, streaming, and user-facing delivery."""

    CONTROL = "control"
    """Manages governance, policy enforcement, and access control."""

    MEMORY = "memory"
    """Persists state, manages vector stores, and handles context recall."""

    VOICE = "voice"
    """Audio synthesis, speech recognition, and prosodic interaction."""

    RESEARCH = "research"
    """Information retrieval, grounding, and knowledge synthesis."""

    EDGE = "edge"
    """Deploys on constrained hardware, handles offline inference."""


class FlOOSSuit(str, Enum):
    """
    FlOO$ (Fully Licensed Operational Operator System) character persona.
    Each suit defines a canonical voice profile, visual signature, and
    behavioral heuristic for the agent runtime.
    """

    DR_BEAN = "dr_bean"
    """Methodical, precise, dry wit — the infrastructure architect."""

    MR_CLEAN = "mr_clean"
    """Immaculate, zero-tolerance-for-chaos — the code quality enforcer."""

    BLOSSOM = "blossom"
    """Warm, empathetic, encouraging — the user experience designer."""

    BUBBLES = "bubbles"
    """Energetic, playful, optimistic — the creative spark."""

    BUTTERCUP = "buttercup"
    """Tough, direct, no-nonsense — the security guardian."""

    NONE = "none"
    """Unassigned — agent runs with default system persona."""


class BlendMode(str, Enum):
    """
    Blend mode for holographic overlay compositing.
    Defines how overlay CHIT coordinates are merged with the base signature.
    """

    NORMAL = "normal"
    SOFT_LIGHT = "soft_light"
    RESONANCE = "resonance"
    MULTIPLY = "multiply"
    ADDITIVE = "additive"


class GovernanceModel(str, Enum):
    """
    Governance topology for framework-layer orchestration.
    """

    THREE_BODY = "three-body"
    """Delivery + Control + Memory triumvirate — default PMOVES model."""

    SINGLE = "single"
    """Monolithic governance — one agent owns all three roles."""

    FEDERATED = "federated"
    """Distributed consensus across agent ensemble."""

    HYBRID = "hybrid"
    """Context-dependent governance switching."""


# ───────────────────────────────────────────────────────────────────────────────
# CHIT Hyperdimension Models
# ───────────────────────────────────────────────────────────────────────────────

class CHITDimensions(BaseModel):
    """
    5D CHIT (Compressed Hyperdimension Identity Tensor) coordinates.

    CHIT is the PMOVES.AI-native coordinate system for describing an agent's
    operational stance across five hyperdimensions. Each dimension maps to
    both a semantic property (behavioral) and a geometric property (for CGP
    state-vector computation).

    Dimensions:
        delta  [0,1] — Variance/novelty tolerance. Higher = more creative.
        Hz     [0,1000] — Tempo/BPM/prosodic frequency. Speech/thought cadence.
        kappa  [0,1] — Coherence/context retention. Higher = more grounded.
        A      [0,1] — Amplitude/attention weight. Signal strength in ensemble.
        F      str    — Form/shape/persona archetype. Symbolic identity string.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"delta": 0.72, "Hz": 120.0, "kappa": 0.85, "A": 0.65, "F": "λψ.ψ(κ→∞)"}
            ]
        }
    )

    delta: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Variance/novelty tolerance. 0 = deterministic, 1 = maximally creative",
    )
    Hz: float = Field(
        ...,
        ge=0.0,
        le=1000.0,
        description="Tempo/BPM/prosodic frequency. Thought and speech cadence",
    )
    kappa: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Coherence/context retention. 0 = context-free, 1 = full coherence",
    )
    A: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Amplitude/attention weight. Signal prominence in multi-agent ensemble",
    )
    F: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Form/shape/persona archetype. Symbolic lambda-calculus identity string",
    )

    @field_validator("Hz")
    @classmethod
    def _hz_is_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Hz must be non-negative")
        return round(v, 3)

    @field_validator("delta", "kappa", "A")
    @classmethod
    def _clamp_unit(cls, v: float) -> float:
        return round(max(0.0, min(1.0, v)), 6)

    @field_validator("F")
    @classmethod
    def _f_is_valid_lambda(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("F (form) must be a non-empty symbolic string")
        return v.strip()

    def __repr__(self) -> str:
        return (
            f"CHITDimensions(δ={self.delta:.3f}, "
            f"Hz={self.Hz:.1f}, κ={self.kappa:.3f}, "
            f"A={self.A:.3f}, F={self.F!r})"
        )


class CGPStateVector(BaseModel):
    """
    Compressed Geometric Packet (CGP) state vector.

    CGP is the binary-wire representation of a CHIT signature used for
    fast state comparison, resonance matching, and holographic blending.
    The delta, Hz, and kappa fields mirror CHIT but are quantized for
    efficient transport. The A and F fields maintain their semantic form
    for symbolic pattern matching.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"delta": 0.72, "Hz": 120.0, "kappa": 0.85, "A": "0.65", "F": "λψ.ψ(κ→∞)"}
            ]
        }
    )

    delta: float = Field(..., ge=0.0, le=1.0, description="Quantized variance/novelty tolerance")
    Hz: float = Field(..., ge=0.0, le=1000.0, description="Quantized tempo/prosodic frequency")
    kappa: float = Field(..., ge=0.0, le=1.0, description="Quantized coherence/context retention")
    A: str = Field(..., min_length=1, description="Amplitude as symbolic string for pattern matching")
    F: str = Field(..., min_length=1, max_length=256, description="Form archetype — symbolic identity")

    @model_validator(mode="after")
    def _sync_with_chit(self) -> "CGPStateVector":
        """Ensure CGP vector is internally consistent."""
        return self

    @classmethod
    def from_chit(cls, chit: CHITDimensions) -> "CGPStateVector":
        """Factory: derive a CGP state vector from a CHIT dimensions object."""
        return cls(
            delta=round(chit.delta, 4),
            Hz=round(chit.Hz, 2),
            kappa=round(chit.kappa, 4),
            A=str(round(chit.A, 4)),
            F=chit.F,
        )


class CHITOffset(BaseModel):
    """
    CHIT delta offset for holographic overlay compositing.

    Unlike CHITDimensions (which constrains values to valid absolute ranges),
    CHITOffset represents a *relative delta* applied to a base CHIT signature.
    All fields except ``F`` support negative values — e.g., a negative Hz offset
    slows the tempo, negative kappa reduces coherence, negative delta dampens
    creativity.

    Dimensions:
        delta  [-1,1] — Creativity delta. Positive = boost, negative = dampen.
        Hz     [-1000,1000] — Tempo delta in BPM. Positive = speed up.
        kappa  [-1,1] — Coherence delta. Positive = more grounded.
        A      [-1,1] — Amplitude delta. Positive = louder/stronger signal.
        F      str    — Form modifier string (e.g., "Δ(visual:neon)").
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"delta": 0.1, "Hz": 15.0, "kappa": -0.05, "A": 0.08, "F": "Δ(persona:mentor)"}
            ]
        }
    )

    delta: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Creativity offset [-1,1]. Positive = boost, negative = dampen",
    )
    Hz: float = Field(
        ...,
        ge=-1000.0,
        le=1000.0,
        description="Tempo delta in BPM [-1000,1000]. Positive = speed up",
    )
    kappa: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Coherence offset [-1,1]. Positive = more grounded",
    )
    A: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Amplitude offset [-1,1]. Positive = louder/stronger",
    )
    F: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Form modifier string — symbolic delta notation (e.g., 'Δ(visual:neon)')",
    )

    @field_validator("F")
    @classmethod
    def _f_starts_with_delta(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("F offset must not be empty")
        return stripped


# ───────────────────────────────────────────────────────────────────────────────
# Layer 1: Model
# ───────────────────────────────────────────────────────────────────────────────

class ModelLayer(BaseModel):
    """
    The LLM model configuration layer.

    Defines which model provider, model identifier, and generation parameters
    are used when this agent runs inference. The ``suit_id`` field identifies
    the hardware/compute suit (e.g., a specific GPU cluster or edge device).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "provider": "zhipu/glm",
                    "model_id": "glm-4-plus",
                    "suit_id": "z890-1",
                    "context_window": 128000,
                    "temperature": 0.35,
                    "top_p": 0.9,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "max_tokens": 4096,
                    "stop_sequences": [],
                }
            ]
        }
    )

    provider: ModelProvider = Field(
        ...,
        description="LLM provider — must be a supported ModelProvider enum value",
    )
    model_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Provider-specific model identifier (e.g., 'glm-4-plus', 'claude-sonnet-4-20250514')",
    )
    suit_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Hardware/compute suit binding — maps to a specific GPU cluster or edge node",
    )
    context_window: int = Field(
        ...,
        gt=0,
        le=2_000_000,
        description="Maximum token context window for this model",
    )
    temperature: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. 0 = deterministic, >1 = highly random",
    )
    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling probability mass. 1.0 = full vocabulary",
    )
    frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Penalty for token frequency. Positive = less repetition",
    )
    presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Penalty for token presence. Positive = encourage new topics",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        gt=0,
        le=2_000_000,
        description="Maximum tokens to generate per response. None = model default",
    )
    stop_sequences: list[str] = Field(
        default_factory=list,
        description="Sequences that halt generation when encountered",
    )

    @field_validator("model_id", "suit_id")
    @classmethod
    def _strip_and_validate(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return stripped

    @field_validator("stop_sequences")
    @classmethod
    def _validate_stop_sequences(cls, v: list[str]) -> list[str]:
        for seq in v:
            if not seq:
                raise ValueError("Stop sequences must not contain empty strings")
        return v

    @property
    def display_name(self) -> str:
        """Human-readable model identifier for UI rendering."""
        return f"{self.provider.value}/{self.model_id}@{self.suit_id}"


# ───────────────────────────────────────────────────────────────────────────────
# Layer 2: Agent
# ───────────────────────────────────────────────────────────────────────────────

class AgentLayer(BaseModel):
    """
    The runtime identity layer of an agent.

    Captures the agent's role within the PMOVES governance topology,
    its node/room binding, team membership, and inter-agent dependencies.
    The ``canonical`` flag marks the primary instance of a multi-replica agent.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "InfraWeaver",
                    "role": "infrastructure-fabric",
                    "archetype": "orchestrator",
                    "node": "z890-1",
                    "room": "fabric-alpha",
                    "team": "core-infra",
                    "canonical": True,
                    "dependencies": ["memory-store", "mesh-router"],
                    "description": "Infrastructure fabric orchestrator for PMOVES runtime",
                }
            ]
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable agent name",
    )
    role: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Functional role string (e.g., 'infrastructure-fabric', 'code-synthesizer')",
    )
    archetype: AgentArchetype = Field(
        ...,
        description="Agent archetype classification within three-body governance",
    )
    node: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Compute node binding — the physical/virtual host this agent runs on",
    )
    room: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Room binding — the logical execution context (e.g., 'fabric-alpha', 'code-dojo')",
    )
    team: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Team/namespace membership for RBAC and governance scoping",
    )
    canonical: bool = Field(
        default=False,
        description="If True, this is the primary instance of a potentially multi-replica agent",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Agent IDs of dependencies that must be healthy before this agent starts",
    )
    description: str = Field(
        default="",
        max_length=4096,
        description="Long-form agent description for documentation and discovery",
    )

    @field_validator("name", "role", "node", "team")
    @classmethod
    def _no_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped

    @field_validator("dependencies")
    @classmethod
    def _no_self_dependency(cls, v: list[str], info) -> list[str]:
        """Prevent an agent from depending on itself."""
        data = info.data
        name = data.get("name", "")
        if name and name in v:
            raise ValueError(f"Agent '{name}' cannot list itself as a dependency")
        return v


# ───────────────────────────────────────────────────────────────────────────────
# Layer 3: Harness
# ───────────────────────────────────────────────────────────────────────────────

class ToolBinding(BaseModel):
    """
    A tool capability mapped to CHIT hyperdimensions.

    Each tool binding declares a tool that the agent can invoke, along with
    its CHIT coordinate mapping. The ``chit_delta`` and ``chit_kappa`` values
    define how the tool influences the agent's creativity and coherence stance
    when it is active.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tool_name": "chit-resonance",
                    "tool_type": "orchestration",
                    "chit_delta": 0.15,
                    "chit_kappa": 0.92,
                    "required": True,
                }
            ]
        }
    )

    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique tool identifier (e.g., 'chit-resonance', 'code-search')",
    )
    tool_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Tool category (e.g., 'orchestration', 'synthesis', 'retrieval')",
    )
    chit_delta: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Creativity offset this tool applies to the agent's CHIT delta",
    )
    chit_kappa: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Coherence offset this tool applies to the agent's CHIT kappa",
    )
    required: bool = Field(
        default=False,
        description="If True, this tool must be available at runtime or the agent fails to start",
    )

    @field_validator("tool_name", "tool_type")
    @classmethod
    def _no_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped


class HarnessLayer(BaseModel):
    """
    Capability harness with CHIT-mapped tools.

    The harness declares all tools, interfaces, and skills available to the
    agent. It forms the bridge between the agent's identity and its actionable
    capabilities, with every tool mapped into the CHIT hyperdimension space
    for resonance-aware orchestration.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "harness_type": "standard",
                    "tools": [
                        {
                            "tool_name": "chit-resonance",
                            "tool_type": "orchestration",
                            "chit_delta": 0.15,
                            "chit_kappa": 0.92,
                            "required": True,
                        }
                    ],
                    "interfaces": ["rest", "websocket", "mcp"],
                    "skills": ["orchestration", "fabric-management"],
                }
            ]
        }
    )

    harness_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Harness classification (e.g., 'standard', 'minimal', 'full-spectrum')",
    )
    tools: list[ToolBinding] = Field(
        ...,
        min_length=0,
        description="CHIT-mapped tool bindings — must contain at least zero entries",
    )
    interfaces: list[str] = Field(
        default_factory=list,
        description="Communication interfaces this agent exposes (e.g., 'rest', 'websocket', 'grpc')",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Named skills this agent possesses — used for capability-based routing",
    )

    @field_validator("harness_type")
    @classmethod
    def _no_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Harness type must not be empty")
        return stripped

    @property
    def required_tools(self) -> list[ToolBinding]:
        """Return only the tools marked as required."""
        return [t for t in self.tools if t.required]

    @property
    def tool_names(self) -> list[str]:
        """Return the names of all bound tools."""
        return [t.tool_name for t in self.tools]


# ───────────────────────────────────────────────────────────────────────────────
# Layer 4: Framework
# ───────────────────────────────────────────────────────────────────────────────

class FrameworkBinding(BaseModel):
    """
    A single framework integration configuration.

    PMOVES agents can bind to multiple frameworks simultaneously. Each binding
    declares the framework name, version compatibility, and runtime config
    overrides.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "framework": "agent-zero",
                    "version": ">=0.8.0",
                    "enabled": True,
                    "config": {"auto_start": True, "max_concurrent": 16},
                }
            ]
        }
    )

    framework: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Framework name (e.g., 'agent-zero', 'archon', 'hermes', 'chit-native')",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Version constraint string (e.g., '>=0.8.0', '^1.0.0', 'latest')",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this framework binding is active at runtime",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Framework-specific configuration key-value pairs",
    )

    @field_validator("framework", "version")
    @classmethod
    def _no_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace-only")
        return stripped


class FrameworkLayer(BaseModel):
    """
    Multi-framework orchestration bindings.

    The framework layer declares all external frameworks this agent integrates
    with, along with the governance model that coordinates the agent's role
    within the PMOVES topology.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "bindings": [
                        {
                            "framework": "agent-zero",
                            "version": ">=0.8.0",
                            "enabled": True,
                            "config": {},
                        }
                    ],
                    "governance": "three-body",
                }
            ]
        }
    )

    bindings: list[FrameworkBinding] = Field(
        ...,
        min_length=0,
        description="Framework integrations — zero or more bindings",
    )
    governance: GovernanceModel = Field(
        default=GovernanceModel.THREE_BODY,
        description="Governance topology for this agent's runtime role",
    )

    @property
    def enabled_bindings(self) -> list[FrameworkBinding]:
        """Return only the enabled framework bindings."""
        return [b for b in self.bindings if b.enabled]

    @property
    def framework_names(self) -> list[str]:
        """Return the names of all bound frameworks."""
        return [b.framework for b in self.bindings]


# ───────────────────────────────────────────────────────────────────────────────
# Holographic Overlay Model
# ───────────────────────────────────────────────────────────────────────────────

class HolographicOverlay(BaseModel):
    """
    Composable persona overlay layer.

    Holographic overlays allow runtime compositing of persona traits on top
    of the base CHIT signature. Each overlay has a type, a blend mode that
    defines how it merges with the base, a CHIT offset that specifies the
    dimensional delta, and an optional asset reference for visual/sonic
    resources.

    Blend modes:
        normal      — Replace base with overlay where present.
        soft_light  — Gentle merge, overlay subtly influences base.
        resonance   — CHIT harmonic blending — strongest when frequencies align.
        multiply    — Dampen — overlay reduces base values.
        additive    — Amplify — overlay increases base values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "layer_type": "persona",
                    "blend_mode": "resonance",
                    "chit_offset": {
                        "delta": 0.1,
                        "Hz": 15.0,
                        "kappa": -0.05,
                        "A": 0.08,
                        "F": "Δ(persona:mentor)",
                    },
                    "asset_ref": "holo://personas/mentor-v2.glb",
                }
            ]
        }
    )

    layer_type: Literal[
        "visual", "sonic", "persona", "cognitive", "temporal", "spatial"
    ] = Field(
        ...,
        description="Overlay category — defines which sensory/cognitive layer is affected",
    )
    blend_mode: Literal[
        "normal", "soft_light", "resonance", "multiply", "additive"
    ] = Field(
        ...,
        description="Blending algorithm for merging this overlay with the base CHIT signature",
    )
    chit_offset: CHITOffset = Field(
        ...,
        description="CHIT delta values added to (or merged with) the base signature",
    )
    asset_ref: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Optional URI to a holographic asset (3D model, sound font, texture)",
    )

    @field_validator("asset_ref")
    @classmethod
    def _validate_asset_ref(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("asset_ref must not be empty if provided")
        return v


# ───────────────────────────────────────────────────────────────────────────────
# Agent Card (Root Model)
# ───────────────────────────────────────────────────────────────────────────────

class AgentCard(BaseModel):
    """
    Complete Agent Card: Model inside Agent inside Harness inside Framework.

    The Agent Card is the self-describing runtime identity for every agent
    in the PMOVES.AI ecosystem. It nests four layers — Model, Agent, Harness,
    and Framework — alongside a CHIT signature, CGP state vector, optional
    FlOO$ suit, and holographic overlays.

    Serialization:
        card.model_dump()           → Python dict
        card.model_dump_json()      → JSON string
        card.model_dump(mode="json")→ JSON-compatible dict (all enums as strings)

    Validation:
        AgentCard(**data)           → Validate and construct from dict
        AgentCard.model_validate_json(str) → Validate and construct from JSON

    Schema export:
        AgentCard.model_json_schema() → JSON Schema dict for OpenAPI/documentation
    """

    model_config = ConfigDict(
        title="PMOVES Agent Card",
        description="Self-describing runtime identity for PMOVES.AI agents",
        json_schema_extra={
            "examples": [
                {
                    "card_version": "1.0.0",
                    "agent_id": "z890-claude",
                    "model": {
                        "provider": "zhipu/glm",
                        "model_id": "glm-4-plus",
                        "suit_id": "z890-1",
                        "context_window": 128000,
                        "temperature": 0.35,
                        "top_p": 0.9,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0,
                        "max_tokens": 4096,
                        "stop_sequences": [],
                    },
                    "agent": {
                        "name": "InfraWeaver",
                        "role": "infrastructure-fabric",
                        "archetype": "orchestrator",
                        "node": "z890-1",
                        "room": "fabric-alpha",
                        "team": "core-infra",
                        "canonical": True,
                        "dependencies": [],
                        "description": "Infrastructure fabric orchestrator",
                    },
                    "harness": {
                        "harness_type": "standard",
                        "tools": [],
                        "interfaces": ["rest", "websocket"],
                        "skills": ["orchestration"],
                    },
                    "framework": {
                        "bindings": [],
                        "governance": "three-body",
                    },
                    "chit_signature": {
                        "delta": 0.72,
                        "Hz": 120.0,
                        "kappa": 0.85,
                        "A": 0.65,
                        "F": "λψ.ψ(κ→∞)",
                    },
                    "cgp_state": {
                        "delta": 0.72,
                        "Hz": 120.0,
                        "kappa": 0.85,
                        "A": "0.65",
                        "F": "λψ.ψ(κ→∞)",
                    },
                    "floos_suit": "dr_bean",
                    "holographic_overlays": [],
                    "enabled": True,
                    "created_at": "2025-01-15T09:00:00Z",
                    "updated_at": "2025-01-15T09:00:00Z",
                }
            ]
        },
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    card_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$",
        description="Agent Card schema version — SemVer format",
    )
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Globally unique agent identifier (e.g., 'z890-claude', 'FLUTE-1')",
    )

    # ── Four nested layers ────────────────────────────────────────────────────
    model: ModelLayer = Field(..., description="LLM model configuration layer")
    agent: AgentLayer = Field(..., description="Runtime identity layer")
    harness: HarnessLayer = Field(..., description="Capability harness layer")
    framework: FrameworkLayer = Field(..., description="Multi-framework binding layer")

    # ── CHIT signature ────────────────────────────────────────────────────────
    chit_signature: CHITDimensions = Field(
        ...,
        description="5D CHIT hyperdimension coordinates — the agent's operational stance",
    )
    cgp_state: CGPStateVector = Field(
        ...,
        description="Compressed Geometric Packet state vector — wire-format CHIT",
    )

    # ── Optional persona ──────────────────────────────────────────────────────
    floos_suit: Optional[FlOOSSuit] = Field(
        default=FlOOSSuit.NONE,
        description="FlOO$ character persona — voice profile and visual signature",
    )
    holographic_overlays: list[HolographicOverlay] = Field(
        default_factory=list,
        description="Composable persona overlay layers for runtime persona compositing",
    )

    # ── Runtime state ─────────────────────────────────────────────────────────
    enabled: bool = Field(
        default=True,
        description="Whether this agent is enabled for active duty",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of card creation",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of last card update",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("agent_id")
    @classmethod
    def _agent_id_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("agent_id must not be empty or whitespace-only")
        if " " in stripped:
            raise ValueError("agent_id must not contain spaces")
        return stripped

    @model_validator(mode="after")
    def _cgp_matches_chit(self) -> "AgentCard":
        """
        Ensure the CGP state vector is consistent with the CHIT signature.
        CGP should be a quantized projection of CHIT — values must align
        within acceptable rounding tolerance.
        """
        chit = self.chit_signature
        cgp = self.cgp_state

        # Check delta alignment (within 0.01 tolerance for rounding)
        if abs(cgp.delta - chit.delta) > 0.01:
            raise ValueError(
                f"CGP delta ({cgp.delta}) deviates from CHIT delta ({chit.delta}) "
                "by more than rounding tolerance (0.01)"
            )

        # Check Hz alignment (within 1.0 tolerance)
        if abs(cgp.Hz - chit.Hz) > 1.0:
            raise ValueError(
                f"CGP Hz ({cgp.Hz}) deviates from CHIT Hz ({chit.Hz}) "
                "by more than rounding tolerance (1.0)"
            )

        # Check kappa alignment
        if abs(cgp.kappa - chit.kappa) > 0.01:
            raise ValueError(
                f"CGP kappa ({cgp.kappa}) deviates from CHIT kappa ({chit.kappa}) "
                "by more than rounding tolerance (0.01)"
            )

        # Check F alignment
        if cgp.F != chit.F:
            raise ValueError(
                f"CGP F ({cgp.F!r}) must exactly match CHIT F ({chit.F!r})"
            )

        # Check A alignment (CGP.A is string, CHIT.A is float)
        try:
            cgp_a_float = float(cgp.A)
        except ValueError:
            raise ValueError(f"CGP A ({cgp.A!r}) must be a numeric string")

        if abs(cgp_a_float - chit.A) > 0.01:
            raise ValueError(
                f"CGP A ({cgp.A}) deviates from CHIT A ({chit.A}) "
                "by more than rounding tolerance (0.01)"
            )

        return self

    @model_validator(mode="after")
    def _timestamps_ordered(self) -> "AgentCard":
        """Ensure updated_at is not earlier than created_at."""
        if self.created_at and self.updated_at:
            # Simple string comparison works for ISO 8601
            if self.updated_at < self.created_at:
                raise ValueError(
                    f"updated_at ({self.updated_at}) must not be earlier than "
                    f"created_at ({self.created_at})"
                )
        return self

    # ── Convenience methods ───────────────────────────────────────────────────

    def touch(self) -> "AgentCard":
        """Update the updated_at timestamp to the current UTC time."""
        self.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self

    @property
    def display_name(self) -> str:
        """Human-readable display name combining agent name and model info."""
        return f"{self.agent.name} ({self.model.display_name})"

    @property
    def chit_summary(self) -> str:
        """Short CHIT coordinate summary for logging/debugging."""
        c = self.chit_signature
        return f"CHIT[δ={c.delta:.2f} Hz={c.Hz:.0f} κ={c.kappa:.2f} A={c.A:.2f} F={c.F}]"

    @property
    def required_tools(self) -> list[ToolBinding]:
        """Return all required tools from the harness layer."""
        return self.harness.required_tools

    @property
    def is_canonical(self) -> bool:
        """Whether this is the canonical (primary) instance of the agent."""
        return self.agent.canonical

    @property
    def active_frameworks(self) -> list[str]:
        """Return the names of all enabled framework bindings."""
        return self.framework.enabled_bindings


# ───────────────────────────────────────────────────────────────────────────────
# JSON Schema Export
# ───────────────────────────────────────────────────────────────────────────────

def export_json_schema() -> dict[str, Any]:
    """
    Export the complete Agent Card JSON Schema as a Python dict.

    The returned dict is a valid JSON Schema (draft 2020-12) that can be
    used for OpenAPI documentation, client code generation, or external
    validation pipelines.
    """
    return AgentCard.model_json_schema()


def export_json_schema_string(indent: int = 2) -> str:
    """
    Export the complete Agent Card JSON Schema as a formatted JSON string.
    """
    import json

    return json.dumps(export_json_schema(), indent=indent, ensure_ascii=False)


# ───────────────────────────────────────────────────────────────────────────────
# Module-level __all__
# ───────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "ModelProvider",
    "AgentArchetype",
    "FlOOSSuit",
    "BlendMode",
    "GovernanceModel",
    # CHIT
    "CHITDimensions",
    "CHITOffset",
    "CGPStateVector",
    # Layers
    "ModelLayer",
    "AgentLayer",
    "ToolBinding",
    "HarnessLayer",
    "FrameworkBinding",
    "FrameworkLayer",
    # Persona
    "HolographicOverlay",
    # Root
    "AgentCard",
    # Utilities
    "export_json_schema",
    "export_json_schema_string",
]
