"""
MACA TensorZero Integration - Multi-Agent Consensus via LLM Gateway

Integrates MACA (Multi-Agent Consensus Alignment) with TensorZero gateway
for LLM-backed consensus voting on geometry packets.

This module provides:
1. LLM-based voting on geometric proposals
2. Consensus validation through structured outputs
3. Multi-agent coordination via TensorZero chat completions
4. Observability via ClickHouse metrics collection

Usage:
    from pmoves.tools.maca_tensorzero import MACATensorZeroConsensus

    maca_tz = MACATensorZeroConsensus(
        agent_id="agent-1",
        tensorzero_url="http://localhost:3030"
    )

    # Get LLM-backed vote on a proposal
    result = await maca_tz.llm_vote(
        packet=geometry_packet,
        context={"theory": "Integrated Information Theory"}
    )
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Service discovery integration
try:
    from pmoves.services.common.service_registry import get_service_url_sync
    SERVICE_REGISTRY_AVAILABLE = True
except ImportError:
    SERVICE_REGISTRY_AVAILABLE = False

    def get_service_url_sync(slug: str, *, default_port: int = 80) -> str:
        """Fallback when service registry is not available."""
        return f"http://{slug}:{default_port}"


@dataclass
class MACAVote:
    """A single vote in MACA consensus."""
    agent_id: str
    score: float  # -1.0 to 1.0
    transformation: Optional[Dict[str, Any]] = None
    entropy_delta: float = 0.0
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MACAConsensusResult:
    """Result of MACA consensus process."""
    packet_id: str
    accepted: bool
    final_score: float
    entropy_reduction: float
    votes: List[MACAVote] = field(default_factory=list)
    rounds: int = 0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "packet_id": self.packet_id,
            "accepted": self.accepted,
            "final_score": self.final_score,
            "entropy_reduction": self.entropy_reduction,
            "votes": [
                {
                    "agent_id": v.agent_id,
                    "score": v.score,
                    "transformation": v.transformation,
                    "entropy_delta": v.entropy_delta,
                    "reasoning": v.reasoning,
                    "timestamp": v.timestamp,
                }
                for v in self.votes
            ],
            "rounds": self.rounds,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


class MACATensorZeroConsensus:
    """
    MACA Consensus with TensorZero LLM-backed voting.

    Uses TensorZero gateway (port 3030) for:
    - LLM-based consensus voting on geometric proposals
    - Structured output parsing for transformation suggestions
    - Observability via ClickHouse metrics collection

    Service URL resolution:
        If tensorzero_url is None or "auto", the URL is resolved via:
        1. TENSORZERO_URL environment variable
        2. Service catalog (Supabase) via service registry
        3. Docker DNS fallback (http://tensorzero:3030)

    Attributes:
        agent_id: This agent's identifier for voting
        tensorzero_url: TensorZero gateway URL
        model: Model to use for consensus voting
        threshold: Acceptance threshold for consensus

    Example:
        >>> maca = MACATensorZeroConsensus(agent_id="agent-1")
        >>> result = await maca.propose_and_vote(packet)
        >>> if result.accepted:
        ...     print("Consensus reached!")
    """

    # System prompt for consensus voting
    CONSENSUS_SYSTEM_PROMPT = """You are a consensus agent evaluating geometric proposals for the CHIT (Cymatic Holographic Information Theory) system.

Your role is to:
1. Evaluate geometric packets based on coherence, entropy reduction, and alignment
2. Provide a score from -1.0 (strong reject) to 1.0 (strong accept)
3. Suggest transformations if the proposal needs adjustment
4. Reason about your decision clearly

Geometric packets represent:
- Theories encoded as 3D constellation coordinates
- Spectral distributions representing dimension weights
- Entropy measurements (lower = more ordered/converged)

Evaluation criteria:
- Coherence: Do the coordinates form a meaningful pattern?
- Entropy reduction: Does the proposal reduce uncertainty (ΔS > 0)?
- Alignment: Does it align with established knowledge?

Response format (JSON):
{
    "score": <float between -1.0 and 1.0>,
    "reasoning": "<brief explanation>",
    "transformation": {
        "scale": <float, optional>,
        "rotate": <float radians, optional>,
        "translate": <float or array, optional>
    }
}"""

    def __init__(
        self,
        agent_id: str,
        tensorzero_url: str | None = None,
        model: str = "claude-sonnet-4-5",
        threshold: float = 0.6,
        max_rounds: int = 10,
        timeout: float = 30.0,
    ):
        """Initialize MACA TensorZero Consensus.

        Args:
            agent_id: This agent's identifier
            tensorzero_url: TensorZero gateway URL. If None, uses service discovery.
            model: Model name for consensus voting
            threshold: Acceptance threshold (0-1)
            max_rounds: Maximum consensus rounds
            timeout: Request timeout in seconds
        """
        self.agent_id = agent_id
        self.model = model
        self.threshold = threshold
        self.max_rounds = max_rounds
        self.timeout = timeout

        # Resolve TensorZero URL via service discovery if not provided
        if tensorzero_url is None or tensorzero_url == "auto":
            tensorzero_url = os.getenv("TENSORZERO_URL")
            if not tensorzero_url:
                tensorzero_url = get_service_url_sync("tensorzero", default_port=3030)

        self._base_url = tensorzero_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

        # Active proposals tracking
        self._proposals: Dict[str, Dict[str, Any]] = {}
        self._votes: Dict[str, List[MACAVote]] = {}

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close HTTP client resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def llm_vote(
        self,
        packet: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        voter_id: Optional[str] = None,
    ) -> MACAVote:
        """
        Get an LLM-backed vote on a geometric proposal.

        Args:
            packet: CGP packet to evaluate
            context: Additional context for voting
            voter_id: Voter's agent ID (default: self.agent_id)

        Returns:
            MACAVote with score, transformation, and reasoning
        """
        client = await self._ensure_client()
        voter = voter_id or self.agent_id

        # Extract packet information for LLM
        packet_info = self._extract_packet_info(packet)

        # Build user prompt with packet details
        user_prompt = self._build_vote_prompt(packet_info, context)

        try:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.CONSENSUS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,  # Lower temperature for consistent voting
                    "response_format": {"type": "json_object"},
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            # Parse JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: extract JSON from markdown code block
                import re

                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Parse as key-value pairs
                    result = self._parse_fallback_json(content)

            score = float(result.get("score", 0.0))
            score = max(-1.0, min(1.0, score))  # Clamp to [-1, 1]

            vote = MACAVote(
                agent_id=voter,
                score=score,
                transformation=result.get("transformation"),
                reasoning=result.get("reasoning", ""),
            )

            logger.debug(
                f"MACA LLM vote: {voter} -> score={score:.2f}, "
                f"transformation={vote.transformation is not None}"
            )

            return vote

        except httpx.HTTPStatusError as e:
            logger.error(f"TensorZero HTTP error during LLM vote: {e.response.status_code}")
            # Return neutral vote on error
            return MACAVote(
                agent_id=voter,
                score=0.0,
                reasoning=f"Error during vote: {e}",
            )
        except Exception as e:
            logger.error(f"Error during LLM vote: {e}")
            return MACAVote(
                agent_id=voter,
                score=0.0,
                reasoning=f"Error during vote: {e}",
            )

    async def propose_and_vote(
        self,
        packet: Dict[str, Any],
        participants: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MACAConsensusResult:
        """
        Propose a packet and run consensus with LLM-backed voting.

        Args:
            packet: CGP packet to propose
            participants: List of agent IDs to participate (if None, uses self only)
            context: Additional context for voting

        Returns:
            MACAConsensusResult with final determination
        """
        import time

        start_time = time.time()

        # Extract packet ID
        packet_id = packet.get("super_nodes", [{}])[0].get("constellations", [{}])[0].get("id", "unknown")

        # Initialize proposal tracking
        self._proposals[packet_id] = {
            "packet": packet,
            "participants": participants or [self.agent_id],
            "initial_entropy": self._calculate_packet_entropy(packet),
        }
        self._votes[packet_id] = []

        # Collect votes from all participants
        votes: List[MACAVote] = []
        for participant in self._proposals[packet_id]["participants"]:
            # Simulate multi-agent voting by calling LLM for each participant
            # In production, each agent would vote independently
            vote = await self.llm_vote(
                packet=packet,
                context={**(context or {}), "voter": participant},
                voter_id=participant,
            )
            votes.append(vote)
            self._votes[packet_id].append(vote)

        # Calculate aggregate score
        if votes:
            avg_score = sum(v.score for v in votes) / len(votes)
        else:
            avg_score = 0.0

        # Calculate entropy reduction
        final_entropy = self._calculate_final_entropy(packet, votes)
        entropy_reduction = self._proposals[packet_id]["initial_entropy"] - final_entropy

        # Determine acceptance
        accepted = avg_score >= self.threshold and entropy_reduction > 0

        duration_ms = int((time.time() - start_time) * 1000)

        result = MACAConsensusResult(
            packet_id=packet_id,
            accepted=accepted,
            final_score=avg_score,
            entropy_reduction=entropy_reduction,
            votes=votes,
            rounds=1,
            duration_ms=duration_ms,
        )

        # Cleanup
        self._proposals.pop(packet_id, None)
        self._votes.pop(packet_id, None)

        logger.info(
            f"MACA consensus: {packet_id} "
            f"(accepted: {accepted}, score: {avg_score:.2f}, ΔS: {entropy_reduction:.4f})"
        )

        return result

    async def multi_round_consensus(
        self,
        packet: Dict[str, Any],
        participants: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        max_rounds: Optional[int] = None,
    ) -> MACAConsensusResult:
        """
        Run multi-round consensus with transformation aggregation.

        Args:
            packet: CGP packet to propose
            participants: List of agent IDs to participate
            context: Additional context for voting
            max_rounds: Maximum rounds (default: self.max_rounds)

        Returns:
            MACAConsensusResult with final determination
        """
        import time

        max_r = max_rounds if max_rounds is not None else self.max_rounds
        start_time = time.time()

        current_packet = packet
        all_votes: List[MACAVote] = []

        for round_num in range(max_r):
            # Get votes for current packet
            round_votes: List[MACAVote] = []
            for participant in (participants or [self.agent_id]):
                vote = await self.llm_vote(
                    packet=current_packet,
                    context={**(context or {}), "round": round_num + 1, "voter": participant},
                    voter_id=participant,
                )
                round_votes.append(vote)
                all_votes.append(vote)

            # Calculate aggregate
            avg_score = sum(v.score for v in round_votes) / len(round_votes)

            # Check for early acceptance
            if avg_score >= self.threshold:
                # Apply transformations from positive votes
                current_packet = self._apply_transformations(current_packet, round_votes)

                final_entropy = self._calculate_packet_entropy(current_packet)
                entropy_reduction = self._calculate_packet_entropy(packet) - final_entropy

                duration_ms = int((time.time() - start_time) * 1000)

                result = MACAConsensusResult(
                    packet_id=packet.get("id", "unknown"),
                    accepted=True,
                    final_score=avg_score,
                    entropy_reduction=entropy_reduction,
                    votes=all_votes,
                    rounds=round_num + 1,
                    duration_ms=duration_ms,
                )

                logger.info(f"MACA multi-round: consensus reached at round {round_num + 1}")
                return result

            # Apply transformations for next round
            current_packet = self._apply_transformations(current_packet, round_votes)

        # Max rounds reached without consensus
        duration_ms = int((time.time() - start_time) * 1000)
        final_score = sum(v.score for v in all_votes) / len(all_votes) if all_votes else 0.0

        return MACAConsensusResult(
            packet_id=packet.get("id", "unknown"),
            accepted=False,
            final_score=final_score,
            entropy_reduction=0.0,
            votes=all_votes,
            rounds=max_r,
            duration_ms=duration_ms,
        )

    async def stream_consensus(
        self,
        packet: Dict[str, Any],
        participants: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[MACAVote]:
        """
        Stream votes as they arrive (simulated streaming).

        Args:
            packet: CGP packet to propose
            participants: List of agent IDs to participate
            context: Additional context for voting

        Yields:
            MACAVote objects as they arrive
        """
        for participant in (participants or [self.agent_id]):
            vote = await self.llm_vote(
                packet=packet,
                context={**(context or {}), "voter": participant},
                voter_id=participant,
            )
            yield vote

    def _extract_packet_info(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant information from a CGP packet for LLM evaluation."""
        info = {
            "spec": packet.get("spec", "unknown"),
            "summary": packet.get("summary", ""),
        }

        # Extract super nodes
        super_nodes = packet.get("super_nodes", [])
        if super_nodes:
            sn = super_nodes[0]
            info["super_node"] = {
                "id": sn.get("id"),
                "label": sn.get("label"),
                "summary": sn.get("summary"),
                "position": {"x": sn.get("x"), "y": sn.get("y"), "r": sn.get("r")},
            }

            # Extract constellations
            constellations = sn.get("constellations", [])
            if constellations:
                constellation = constellations[0]
                info["constellation"] = {
                    "id": constellation.get("id"),
                    "summary": constellation.get("summary"),
                    "spectrum": constellation.get("spectrum", []),
                    "points_count": len(constellation.get("points", [])),
                }

        # Extract metadata
        meta = packet.get("meta", {})
        if meta:
            info["meta"] = {
                "source": meta.get("source"),
                "tags": meta.get("tags", []),
            }

        return info

    def _build_vote_prompt(
        self,
        packet_info: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the user prompt for LLM voting."""
        prompt_parts = [
            "Evaluate the following geometric proposal:\n",
        ]

        # Add packet summary
        prompt_parts.append(f"Specification: {packet_info.get('spec', 'unknown')}")
        prompt_parts.append(f"Summary: {packet_info.get('summary', 'No summary')}")

        # Add super node info
        if "super_node" in packet_info:
            sn = packet_info["super_node"]
            prompt_parts.append(
                f"\nSuper Node: {sn.get('label')} at ({sn['position']['x']}, {sn['position']['y']})"
            )
            prompt_parts.append(f"  {sn.get('summary', '')}")

        # Add constellation info
        if "constellation" in packet_info:
            c = packet_info["constellation"]
            prompt_parts.append(
                f"\nConstellation: {c.get('id')}\n"
                f"  Spectrum: {c.get('spectrum', [])}\n"
                f"  Points: {c.get('points_count', 0)}"
            )

        # Add metadata
        if "meta" in packet_info:
            m = packet_info["meta"]
            prompt_parts.append(f"\nSource: {m.get('source', 'unknown')}")
            prompt_parts.append(f"Tags: {', '.join(m.get('tags', []))}")

        # Add context
        if context:
            prompt_parts.append("\nAdditional Context:")
            for key, value in context.items():
                if key != "voter":  # Don't include voter in prompt
                    prompt_parts.append(f"  {key}: {value}")

        prompt_parts.append(
            "\n\nProvide your evaluation as JSON with score, reasoning, and optional transformation."
        )

        return "\n".join(prompt_parts)

    def _calculate_packet_entropy(self, packet: Dict[str, Any]) -> float:
        """Calculate entropy of a packet based on its spectrum."""
        import math

        # Extract spectrum from first constellation
        super_nodes = packet.get("super_nodes", [])
        if not super_nodes:
            return 0.0

        constellations = super_nodes[0].get("constellations", [])
        if not constellations:
            return 0.0

        spectrum = constellations[0].get("spectrum", [])
        if not spectrum:
            return 0.0

        # Calculate Shannon entropy
        entropy = 0.0
        for value in spectrum:
            if value > 0:
                entropy -= value * math.log2(value)

        return entropy

    def _calculate_final_entropy(self, packet: Dict[str, Any], votes: List[MACAVote]) -> float:
        """Calculate entropy after applying transformations from votes."""
        # For now, return same entropy (transformations not applied in this simple version)
        # In full implementation, would apply transformations before calculating
        return self._calculate_packet_entropy(packet)

    def _apply_transformations(
        self,
        packet: Dict[str, Any],
        votes: List[MACAVote],
    ) -> Dict[str, Any]:
        """Apply transformations from positive votes to create new packet."""
        from copy import deepcopy

        result = deepcopy(packet)

        # Collect transformations with positive votes
        positive_transforms = [
            (v.transformation, v.score)
            for v in votes
            if v.transformation and v.score > 0
        ]

        if not positive_transforms:
            return result

        # Apply weighted average of transformations
        total_weight = sum(score for _, score in positive_transforms)
        if total_weight == 0:
            return result

        # This is a simplified version - full implementation would apply
        # transformations to actual coordinates
        return result

    def _parse_fallback_json(self, content: str) -> Dict[str, Any]:
        """Parse JSON from unstructured text as fallback."""
        import re

        result = {}

        # Extract score
        score_match = re.search(r'score["\s:]+(-?\d+\.?\d*)', content)
        if score_match:
            result["score"] = float(score_match.group(1))

        # Extract reasoning
        reasoning_match = re.search(r'reasoning["\s:]+["\']([^"\']+)["\']', content, re.IGNORECASE)
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1)

        return result

    def get_pending_proposals(self) -> List[str]:
        """Get list of pending proposal IDs."""
        return list(self._proposals.keys())

    def get_proposal_status(self, packet_id: str) -> Dict[str, Any]:
        """Get current status of a proposal."""
        if packet_id not in self._proposals:
            return {"error": "Proposal not found"}

        proposal = self._proposals[packet_id]
        votes = self._votes.get(packet_id, [])

        return {
            "packet_id": packet_id,
            "participants": proposal.get("participants", []),
            "vote_count": len(votes),
            "current_score": sum(v.score for v in votes) / len(votes) if votes else 0,
            "votes": [
                {
                    "agent_id": v.agent_id,
                    "score": v.score,
                    "reasoning": v.reasoning,
                }
                for v in votes
            ],
        }


# Convenience functions

async def vote_on_packet(
    packet: Dict[str, Any],
    agent_id: str,
    tensorzero_url: Optional[str] = None,
    model: str = "claude-sonnet-4-5",
) -> MACAVote:
    """
    Convenience function to get an LLM vote on a packet.

    Args:
        packet: CGP packet to evaluate
        agent_id: Agent ID for the voter
        tensorzero_url: TensorZero gateway URL (optional)
        model: Model to use for voting

    Returns:
        MACAVote with score, transformation, and reasoning
    """
    maca = MACATensorZeroConsensus(agent_id=agent_id, tensorzero_url=tensorzero_url, model=model)
    try:
        return await maca.llm_vote(packet)
    finally:
        await maca.close()


async def run_consensus(
    packet: Dict[str, Any],
    agent_id: str,
    participants: Optional[List[str]] = None,
    tensorzero_url: Optional[str] = None,
    model: str = "claude-sonnet-4-5",
    threshold: float = 0.6,
) -> MACAConsensusResult:
    """
    Convenience function to run full consensus on a packet.

    Args:
        packet: CGP packet to evaluate
        agent_id: Agent ID for the proposer
        participants: List of agent IDs to participate
        tensorzero_url: TensorZero gateway URL (optional)
        model: Model to use for voting
        threshold: Acceptance threshold

    Returns:
        MACAConsensusResult with final determination
    """
    maca = MACATensorZeroConsensus(
        agent_id=agent_id,
        tensorzero_url=tensorzero_url,
        model=model,
        threshold=threshold,
    )
    try:
        return await maca.propose_and_vote(packet, participants=participants)
    finally:
        await maca.close()


__all__ = [
    "MACAVote",
    "MACAConsensusResult",
    "MACATensorZeroConsensus",
    "vote_on_packet",
    "run_consensus",
]
