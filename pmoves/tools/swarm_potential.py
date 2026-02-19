#!/usr/bin/env python3
"""
Swarm Potential Metric Calculator

Metric: active_agents x indexed_content x connection_density

Published to Prometheus for Grafana dashboard widget.

Thread 6.3: Swarm Potential Metric

Usage:
    python pmoves/tools/swarm_potential.py [--json] [--prometheus]

Make target:
    make -C pmoves swarm-potential
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class SwarmMetrics:
    """Individual metrics that compose the swarm potential."""

    active_agents: int = 0
    indexed_chunks: int = 0
    neo4j_nodes: int = 0
    neo4j_edges: int = 0
    nats_active_subjects: int = 0
    supabase_records: int = 0
    models_onboarded: int = 0

    @property
    def connection_density(self) -> float:
        """Connection density: edges / max_possible_edges."""
        if self.neo4j_nodes < 2:
            return 0.0
        max_edges = self.neo4j_nodes * (self.neo4j_nodes - 1) / 2
        return min(1.0, self.neo4j_edges / max_edges) if max_edges > 0 else 0.0

    @property
    def swarm_potential(self) -> float:
        """Composite metric: agents x content x density."""
        content_score = (self.indexed_chunks + self.supabase_records) / 1000
        density_score = self.connection_density * 100
        agent_score = self.active_agents

        return round(agent_score * content_score * max(1, density_score), 2)


def fetch_agent_count() -> int:
    """Count active agents from Agent Zero."""
    try:
        resp = httpx.get("http://localhost:8080/healthz", timeout=5)
        if resp.status_code == 200:
            return 1  # At least Agent Zero is up
    except Exception:
        pass
    return 0


def fetch_indexed_chunks() -> int:
    """Count indexed chunks in Qdrant."""
    try:
        resp = httpx.get(
            "http://localhost:6333/collections/pmoves_chunks",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("result", {}).get("points_count", 0)
    except Exception:
        pass
    return 0


def fetch_neo4j_stats() -> tuple:
    """Get node and edge counts from Neo4j."""
    try:
        resp = httpx.post(
            "http://localhost:7474/db/neo4j/tx/commit",
            json={
                "statements": [
                    {"statement": "MATCH (n) RETURN count(n) AS nodes"},
                    {"statement": "MATCH ()-[r]->() RETURN count(r) AS edges"},
                ]
            },
            headers={"Authorization": "Basic bmVvNGo6bmVvNGo="},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            nodes = results[0]["data"][0]["row"][0] if len(results) > 0 else 0
            edges = results[1]["data"][0]["row"][0] if len(results) > 1 else 0
            return nodes, edges
    except Exception:
        pass
    return 0, 0


def fetch_supabase_count() -> int:
    """Count records in Supabase pmoves_core tables."""
    try:
        supabase_url = os.environ.get("SUPABASE_URL", "http://localhost:3010")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_key:
            return 0
        resp = httpx.get(
            f"{supabase_url}/rest/v1/living_pages?select=count",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Prefer": "count=exact",
            },
            timeout=5,
        )
        count = int(resp.headers.get("content-range", "0-0/0").split("/")[-1])
        return count
    except Exception:
        pass
    return 0


def collect_metrics() -> SwarmMetrics:
    """Collect all swarm metrics from services."""
    metrics = SwarmMetrics()

    metrics.active_agents = fetch_agent_count()
    metrics.indexed_chunks = fetch_indexed_chunks()
    nodes, edges = fetch_neo4j_stats()
    metrics.neo4j_nodes = nodes
    metrics.neo4j_edges = edges
    metrics.supabase_records = fetch_supabase_count()

    return metrics


def format_prometheus(metrics: SwarmMetrics) -> str:
    """Format metrics as Prometheus exposition."""
    lines = [
        "# HELP pmoves_swarm_potential Composite swarm potential metric",
        "# TYPE pmoves_swarm_potential gauge",
        f"pmoves_swarm_potential {metrics.swarm_potential}",
        "",
        "# HELP pmoves_active_agents Number of active agents",
        "# TYPE pmoves_active_agents gauge",
        f"pmoves_active_agents {metrics.active_agents}",
        "",
        "# HELP pmoves_indexed_chunks Total indexed content chunks",
        "# TYPE pmoves_indexed_chunks gauge",
        f"pmoves_indexed_chunks {metrics.indexed_chunks}",
        "",
        "# HELP pmoves_connection_density Graph connection density ratio",
        "# TYPE pmoves_connection_density gauge",
        f"pmoves_connection_density {metrics.connection_density}",
        "",
        "# HELP pmoves_neo4j_nodes Total Neo4j nodes",
        "# TYPE pmoves_neo4j_nodes gauge",
        f"pmoves_neo4j_nodes {metrics.neo4j_nodes}",
        "",
        "# HELP pmoves_neo4j_edges Total Neo4j edges",
        "# TYPE pmoves_neo4j_edges gauge",
        f"pmoves_neo4j_edges {metrics.neo4j_edges}",
        "",
        "# HELP pmoves_supabase_records Total Supabase records",
        "# TYPE pmoves_supabase_records gauge",
        f"pmoves_supabase_records {metrics.supabase_records}",
    ]
    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Swarm Potential Calculator")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--prometheus", action="store_true", help="Output as Prometheus metrics")

    args = parser.parse_args()
    metrics = collect_metrics()

    if args.prometheus:
        print(format_prometheus(metrics))
    elif args.json:
        print(json.dumps({
            "swarm_potential": metrics.swarm_potential,
            "active_agents": metrics.active_agents,
            "indexed_chunks": metrics.indexed_chunks,
            "connection_density": round(metrics.connection_density, 4),
            "neo4j_nodes": metrics.neo4j_nodes,
            "neo4j_edges": metrics.neo4j_edges,
            "supabase_records": metrics.supabase_records,
            "models_onboarded": metrics.models_onboarded,
        }, indent=2))
    else:
        print(f"Swarm Potential: {metrics.swarm_potential}")
        print(f"  Active Agents:      {metrics.active_agents}")
        print(f"  Indexed Chunks:     {metrics.indexed_chunks}")
        print(f"  Connection Density: {metrics.connection_density:.4f}")
        print(f"  Neo4j Nodes:        {metrics.neo4j_nodes}")
        print(f"  Neo4j Edges:        {metrics.neo4j_edges}")
        print(f"  Supabase Records:   {metrics.supabase_records}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
