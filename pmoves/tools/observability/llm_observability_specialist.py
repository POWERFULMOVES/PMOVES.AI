#!/usr/bin/env python3
"""
TensorZero LLM Observability Specialist - Observability Layer Agent

Analyzes LLM performance metrics, costs, and model usage patterns from TensorZero ClickHouse.
Provides insights for model selection optimization and cost management.

.. warning::
   **NON-FUNCTIONAL IN THIS DEPLOYMENT — do not treat its output as cost truth,
   and do not "fix" it by tweaking the SQL.** Two independent reasons:

   1. TensorZero observability is disabled by policy
      (``pmoves/tensorzero/config/tensorzero.toml`` ``[gateway.observability]``,
      Cyber Defence Initiative 2026-04-25 — enabling it stores full prompt and
      response text with no TTL). Verified live: the ClickHouse instance has no
      ``tensorzero`` database and zero tables. Nothing writes inference data.
   2. All four queries below read ``FROM requests``. No migration in this repo
      creates a ``requests`` table, and TensorZero does not create one — so these
      queries would not resolve even if observability were switched on.

   Additionally the cost rates below are hardcoded placeholders, and the cost
   query groups only by ``model_name``/``provider_name`` — it never selects
   ``function_name``, so results could not be attributed to an agent or lane
   even with data present.

   **The supported path for agent cost metering is the content-free
   ``chit.economics.usage.v1`` NATS subject** (registered in
   ``.claude/context/nats-subjects.md``), which carries counts and never prompt
   text — satisfying the tokenomics requirement without re-creating the
   retention hazard the policy exists to prevent. See
   ``pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md`` §2 and §8.

Usage:
    python pmoves/tools/observability/llm_observability_specialist.py query <sql>
    python pmoves/tools/observability/llm_observability_specialist.py performance --model <model_name>
    python pmoves/tools/observability/llm_observability_specialist.py cost --hours 24
    python pmoves/tools/observability/llm_observability_specialist.py compare <model1> <model2>

Environment:
    TENSORZERO_CLICKHOUSE_URL - ClickHouse URL (default: http://localhost:8123)
    TENSORZERO_CLICKHOUSE_USER - ClickHouse user (default: tensorzero)
    TENSORZERO_CLICKHOUSE_PASSWORD - ClickHouse password (default: tensorzero)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import requests

# Add repo root to path
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class TensorZeroObservabilitySpecialist:
    """Specialist agent for TensorZero LLM performance and cost analysis."""

    def __init__(
        self,
        clickhouse_url: str | None = None,
        user: str | None = None,
        password: str | None = None
    ):
        """Initialize ClickHouse client.

        Args:
            clickhouse_url: ClickHouse server URL
            user: ClickHouse username
            password: ClickHouse password
        """
        self.clickhouse_url = clickhouse_url or os.getenv(
            "TENSORZERO_CLICKHOUSE_URL", "http://localhost:8123"
        )
        self.user = user or os.getenv("TENSORZERO_CLICKHOUSE_USER", "tensorzero")
        self.password = password or os.getenv("TENSORZERO_CLICKHOUSE_PASSWORD", "tensorzero")

    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query on ClickHouse.

        Args:
            sql: SQL query

        Returns:
            Query results as list of dicts
        """
        params = {
            "query": sql,
            "database": "default",
            "format": "JSON"
        }

        response = requests.get(
            self.clickhouse_url,
            params=params,
            auth=(self.user, self.password),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def get_model_performance(
        self,
        model: str | None = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get LLM performance metrics.

        Args:
            model: Optional model name filter
            hours: Analysis period in hours

        Returns:
            Performance metrics
        """
        end = datetime.now()
        end - timedelta(hours=hours)

        model_filter = f"AND model_name = '{model}'" if model else ""

        sql = f"""
        SELECT
            model_name,
            count() as total_requests,
            avg(latency) as avg_latency_ms,
            quantile(0.50)(latency) as p50_latency_ms,
            quantile(0.95)(latency) as p95_latency_ms,
            quantile(0.99)(latency) as p99_latency_ms,
            sum(prompt_tokens) as total_prompt_tokens,
            sum(completion_tokens) as total_completion_tokens
        FROM requests
        WHERE start_time >= now() - INTERVAL {hours} HOUR
          {model_filter}
        GROUP BY model_name
        ORDER BY total_requests DESC
        """

        results = self.query(sql)

        if not results:
            return {"error": "No data found for the specified period"}

        return {
            "period_hours": hours,
            "models": results
        }

    def get_cost_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze LLM costs by model and provider.

        Args:
            hours: Analysis period in hours

        Returns:
            Cost breakdown
        """
        sql = f"""
        SELECT
            model_name,
            provider_name,
            count() as total_requests,
            sum(prompt_tokens) as total_prompt_tokens,
            sum(completion_tokens) as total_completion_tokens,
            sum(prompt_tokens + completion_tokens) as total_tokens
        FROM requests
        WHERE start_time >= now() - INTERVAL {hours} HOUR
        GROUP BY model_name, provider_name
        ORDER BY total_tokens DESC
        """

        results = self.query(sql)

        # Estimate costs (approximate pricing)
        # These are placeholder rates - actual rates vary by provider
        cost_per_1k_tokens = {
            "claude-opus-4-5": 15.0,
            "claude-sonnet-4-5": 3.0,
            "claude-haiku-4-5": 0.25,
            "gpt-4": 30.0,
            "gpt-3.5-turbo": 0.5,
            "default": 1.0
        }

        total_estimated_cost = 0.0

        for row in results:
            model = row.get("model_name", "default")
            total_tokens = row.get("total_tokens", 0)

            # Get cost rate (use default if not found)
            rate = cost_per_1k_tokens.get(model, cost_per_1k_tokens["default"])

            # Calculate estimated cost
            estimated_cost = (total_tokens / 1000) * rate
            row["estimated_cost_usd"] = estimated_cost
            total_estimated_cost += estimated_cost

        return {
            "period_hours": hours,
            "total_estimated_cost_usd": total_estimated_cost,
            "models": results
        }

    def compare_models(
        self,
        model1: str,
        model2: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Compare performance between two models.

        Args:
            model1: First model name
            model2: Second model name
            hours: Analysis period

        Returns:
            Model comparison
        """
        sql = f"""
        SELECT
            model_name,
            count() as total_requests,
            avg(latency) as avg_latency_ms,
            quantile(0.95)(latency) as p95_latency_ms,
            sum(prompt_tokens) as total_prompt_tokens,
            sum(completion_tokens) as total_completion_tokens,
            sum(prompt_tokens + completion_tokens) as total_tokens
        FROM requests
        WHERE start_time >= now() - INTERVAL {hours} HOUR
          AND model_name IN ('{model1}', '{model2}')
        GROUP BY model_name
        """

        results = self.query(sql)

        comparison = {
            "model1": model1,
            "model2": model2,
            "period_hours": hours,
            "models": {}
        }

        for row in results:
            model = row.get("model_name", "unknown")
            comparison["models"][model] = row

        # Calculate differences
        if len(results) == 2:
            m1_data = comparison["models"].get(model1, {})
            m2_data = comparison["models"].get(model2, {})

            comparison["comparison"] = {
                "latency_diff_ms": m2_data.get("avg_latency_ms", 0) - m1_data.get("avg_latency_ms", 0),
                "token_diff": m2_data.get("total_tokens", 0) - m1_data.get("total_tokens", 0),
                "request_count_diff": m2_data.get("total_requests", 0) - m1_data.get("total_requests", 0)
            }

        return comparison

    def get_slowest_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest LLM requests.

        Args:
            limit: Number of results

        Returns:
            Slowest requests
        """
        sql = f"""
        SELECT
            model_name,
            latency,
            prompt_tokens,
            completion_tokens,
            substring(request_payload, 1, 100) as request_preview
        FROM requests
        ORDER BY latency DESC
        LIMIT {limit}
        """

        return self.query(sql)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TensorZero LLM Observability Specialist - Observability Layer Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Query command
    query_parser = subparsers.add_parser("query", help="Execute SQL query")
    query_parser.add_argument("sql", help="SQL query")

    # Performance command
    perf_parser = subparsers.add_parser("performance", help="Get model performance")
    perf_parser.add_argument("--model", help="Model name filter")
    perf_parser.add_argument("--hours", type=int, default=24, help="Analysis period")

    # Cost command
    cost_parser = subparsers.add_parser("cost", help="Analyze costs")
    cost_parser.add_argument("--hours", type=int, default=24, help="Analysis period")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare models")
    compare_parser.add_argument("model1", help="First model")
    compare_parser.add_argument("model2", help="Second model")
    compare_parser.add_argument("--hours", type=int, default=24, help="Analysis period")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    specialist = TensorZeroObservabilitySpecialist()

    try:
        if args.command == "query":
            results = specialist.query(args.sql)
            print(f"[+] Query results ({len(results)} rows):")
            for row in results[:20]:
                print(f"  {row}")
            if len(results) > 20:
                print(f"  ... and {len(results) - 20} more")

        elif args.command == "performance":
            perf = specialist.get_model_performance(args.model, args.hours)
            if "error" in perf:
                print(f"[!] {perf['error']}")
            else:
                print(f"[+] Model Performance (last {perf['period_hours']}h):")
                for model in perf['models']:
                    print(f"\n  Model: {model['model_name']}")
                    print(f"    Requests: {model['total_requests']}")
                    print(f"    Avg Latency: {model['avg_latency_ms']:.2f}ms")
                    print(f"    P95 Latency: {model['p95_latency_ms']:.2f}ms")
                    print(f"    P99 Latency: {model['p99_latency_ms']:.2f}ms")
                    print(f"    Total Tokens: {model['total_prompt_tokens'] + model['total_completion_tokens']}")

        elif args.command == "cost":
            cost = specialist.get_cost_analysis(args.hours)
            print(f"[+] Cost Analysis (last {cost['period_hours']}h):")
            print(f"\n  Total Estimated Cost: ${cost['total_estimated_cost_usd']:.2f} USD")
            print("\n  Breakdown by Model:")
            for model in cost['models']:
                model_name = model['model_name']
                provider = model.get('provider_name', 'unknown')
                requests = model['total_requests']
                tokens = model['total_tokens']
                est_cost = model['estimated_cost_usd']
                print(f"    {model_name} ({provider}):")
                print(f"      Requests: {requests}")
                print(f"      Tokens: {tokens:,}")
                print(f"      Est Cost: ${est_cost:.4f} USD")

        elif args.command == "compare":
            comp = specialist.compare_models(args.model1, args.model2, args.hours)
            print(f"[+] Model Comparison (last {comp['period_hours']}h):")

            for model_name, data in comp.get("models", {}).items():
                print(f"\n  {model_name}:")
                print(f"    Requests: {data['total_requests']}")
                print(f"    Avg Latency: {data['avg_latency_ms']:.2f}ms")
                print(f"    P95 Latency: {data['p95_latency_ms']:.2f}ms")
                print(f"    Total Tokens: {data['total_tokens']:,}")

            if "comparison" in comp:
                c = comp['comparison']
                print("\n  Differences:")
                print(f"    Latency: {c['latency_diff_ms']:+.2f}ms")
                print(f"    Tokens: {c['token_diff']:+,}")
                print(f"    Requests: {c['request_count_diff']:+,}")

        return 0

    except requests.RequestException as e:
        print(f"[!] ClickHouse query failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        return 130
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
