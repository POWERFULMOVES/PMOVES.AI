"""Global pytest fixture bridge for per-service test runs.

CI executes service suites in isolation (one pytest invocation per path). Import
only the shared fixtures needed by service tests to avoid path-collision side
effects from autouse helpers in the broader test conftest.
"""

from tests.conftest import load_service_module, stub_external_modules  # noqa: F401
