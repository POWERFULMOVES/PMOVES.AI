"""
PMOVES.AI smoke test suite.

Quick health checks (5-30s execution time) for validating service endpoints
and basic functionality.

Run all smoke tests:
    pytest pmoves/tests/smoke/ -v -m smoke

Run in parallel:
    pytest pmoves/tests/smoke/ -v -m smoke -n auto

Run specific test file:
    pytest pmoves/tests/smoke/test_health_endpoints.py -v
"""
