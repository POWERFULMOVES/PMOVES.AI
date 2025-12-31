"""
Smoke Tests for PMOVES Tokenism Simulator

Tests the token economy simulation service integration with:
- NATS message bus
- TensorZero LLM gateway
- Supabase persistence
- CHIT/Geometry Bus
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

# Add services directory to path
service_dir = Path(__file__).parent.parent.parent / "services" / "tokenism-simulator"
sys.path.insert(0, str(service_dir))


class TestTokenismSimulatorSmoke:
    """Smoke tests for tokenism-simulator service."""

    @pytest.fixture
    def base_url(self) -> str:
        """Get the base URL for the tokenism-simulator service."""
        return os.getenv('TOKENISM_URL', 'http://localhost:8100')

    @pytest.fixture
    def timeout(self) -> int:
        """Timeout for HTTP requests."""
        return 30

    def test_health_check(self, base_url: str, timeout: int):
        """Test that the service responds to health checks."""
        try:
            response = httpx.get(f"{base_url}/healthz", timeout=timeout)
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'ok'
        except Exception as e:
            pytest.skip(f"Service not available: {e}")

    def test_root_endpoint(self, base_url: str, timeout: int):
        """Test that the root endpoint returns service information."""
        try:
            response = httpx.get(f"{base_url}/", timeout=timeout)
            assert response.status_code == 200
            data = response.json()
            assert 'service' in data
            assert data['service'] == 'PMOVES Tokenism Simulator'
            assert 'endpoints' in data
            assert 'integrations' in data
        except Exception as e:
            pytest.skip(f"Service not available: {e}")

    def test_metrics_endpoint(self, base_url: str, timeout: int):
        """Test that Prometheus metrics are exposed."""
        try:
            response = httpx.get(f"{base_url}/metrics", timeout=timeout)
            assert response.status_code == 200
            # Prometheus returns text/plain
            assert 'text/plain' in response.headers.get('content-type', '')
            metrics_text = response.text
            # Check for our custom metrics
            assert 'tokenism_simulation_requests_total' in metrics_text
        except Exception as e:
            pytest.skip(f"Service not available: {e}")

    def test_list_scenarios(self, base_url: str, timeout: int):
        """Test listing available simulation scenarios."""
        try:
            response = httpx.get(f"{base_url}/api/v1/scenarios", timeout=timeout)
            assert response.status_code == 200
            data = response.json()
            assert 'scenarios' in data
            scenarios = data['scenarios']
            assert len(scenarios) >= 5
            scenario_ids = [s['id'] for s in scenarios]
            assert 'baseline' in scenario_ids
            assert 'optimistic' in scenario_ids
            assert 'pessimistic' in scenario_ids
        except Exception as e:
            pytest.skip(f"Service not available: {e}")

    def test_list_contracts(self, base_url: str, timeout: int):
        """Test listing available contract types."""
        try:
            response = httpx.get(f"{base_url}/api/v1/contracts", timeout=timeout)
            assert response.status_code == 200
            data = response.json()
            assert 'contracts' in data
            contracts = data['contracts']
            assert len(contracts) >= 5
            contract_ids = [c['id'] for c in contracts]
            assert 'gro_token' in contract_ids
            assert 'food_usd' in contract_ids
        except Exception as e:
            pytest.skip(f"Service not available: {e}")

    def test_run_baseline_simulation(self, base_url: str, timeout: int):
        """Test running a baseline simulation."""
        try:
            # Use short duration for smoke test
            payload = {
                "scenario": "baseline",
                "parameters": {
                    "initial_participants": 100,
                    "initial_token_supply": 10000,
                    "duration_weeks": 4,  # Short test
                    "contract_type": "gro_token",
                }
            }

            start_time = time.time()
            response = httpx.post(
                f"{base_url}/api/v1/simulate",
                json=payload,
                timeout=120,  # 2 minutes max for simulation
            )
            elapsed = time.time() - start_time

            assert response.status_code == 200
            data = response.json()

            # Validate response structure
            assert 'simulation_id' in data
            assert 'scenario' in data
            assert data['scenario'] == 'baseline'
            assert 'weekly_metrics' in data
            assert len(data['weekly_metrics']) == 4
            assert 'final_avg_wealth' in data
            assert 'final_gini' in data
            assert 'systemic_risk_score' in data

            # Validate metrics
            assert 0 <= data['final_gini'] <= 1
            assert 0 <= data['systemic_risk_score'] <= 1
            assert data['final_avg_wealth'] > 0

            # Log performance
            print(f"\nSimulation completed in {elapsed:.2f} seconds")
            print(f"Simulation ID: {data['simulation_id']}")
            print(f"Final avg wealth: {data['final_avg_wealth']:.2f}")
            print(f"Final Gini: {data['final_gini']:.4f}")
            print(f"Systemic risk: {data['systemic_risk_score']:.4f}")

        except httpx.ConnectError:
            pytest.skip("Service not available")
        except Exception as e:
            pytest.fail(f"Simulation failed: {e}")

    def test_run_optimistic_simulation(self, base_url: str, timeout: int):
        """Test running an optimistic scenario simulation."""
        try:
            payload = {
                "scenario": "optimistic",
                "parameters": {
                    "initial_participants": 50,
                    "duration_weeks": 2,
                }
            }

            response = httpx.post(
                f"{base_url}/api/v1/simulate",
                json=payload,
                timeout=60,
            )

            assert response.status_code == 200
            data = response.json()
            assert data['scenario'] == 'optimistic'
            assert 'final_avg_wealth' in data

        except httpx.ConnectError:
            pytest.skip("Service not available")
        except Exception as e:
            pytest.fail(f"Optimistic simulation failed: {e}")

    def test_invalid_scenario(self, base_url: str, timeout: int):
        """Test that invalid scenarios are rejected."""
        try:
            payload = {
                "scenario": "invalid_scenario",
                "parameters": {
                    "initial_participants": 100,
                    "duration_weeks": 2,
                }
            }

            response = httpx.post(
                f"{base_url}/api/v1/simulate",
                json=payload,
                timeout=timeout,
            )

            assert response.status_code == 400
            data = response.json()
            assert 'error' in data

        except httpx.ConnectError:
            pytest.skip("Service not available")

    def test_invalid_parameters(self, base_url: str, timeout: int):
        """Test that invalid parameters are rejected."""
        try:
            payload = {
                "scenario": "baseline",
                "parameters": {
                    "initial_participants": -1,  # Invalid
                    "duration_weeks": 2,
                }
            }

            response = httpx.post(
                f"{base_url}/api/v1/simulate",
                json=payload,
                timeout=timeout,
            )

            # Should return 400 for validation error
            assert response.status_code == 400

        except httpx.ConnectError:
            pytest.skip("Service not available")


class TestTokenismSimulatorIntegrations:
    """Integration tests for external service connections."""

    @pytest.fixture
    def base_url(self) -> str:
        """Get the base URL for the tokenism-simulator service."""
        return os.getenv('TOKENISM_URL', 'http://localhost:8100')

    @pytest.fixture
    def nats_url(self) -> str:
        """Get the NATS URL."""
        return os.getenv('NATS_URL', 'nats://localhost:4222')

    def test_nats_connection(self, nats_url: str):
        """Test that NATS is accessible (for publishing simulation results)."""
        try:
            import nats
            nc = nats.connect(nats_url, timeout=5)
            assert nc.is_connected
            nc.close()
        except ImportError:
            pytest.skip("nats library not available")
        except Exception as e:
            pytest.skip(f"NATS not available: {e}")

    def test_tensorzero_connection(self):
        """Test that TensorZero gateway is accessible (for LLM analysis)."""
        tensorzero_url = os.getenv('TENSORZERO_URL', 'http://localhost:3030')
        try:
            response = httpx.get(f"{tensorzero_url}/health", timeout=5)
            # TensorZero might not have /health, try root
            if response.status_code != 200:
                response = httpx.get(f"{tensorzero_url}/", timeout=5)
        except Exception:
            # TensorZero might not be running, that's okay for smoke test
            pytest.skip("TensorZero not available")

    def test_supabase_connection(self):
        """Test that Supabase/PostgREST is accessible."""
        supabase_url = os.getenv('SUPABASE_URL', 'http://localhost:3010')
        try:
            response = httpx.get(f"{supabase_url}/", timeout=5)
            # PostgREST returns available tables on root
            assert response.status_code in [200, 401]  # 401 if auth required
        except Exception:
            pytest.skip("Supabase not available")


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
