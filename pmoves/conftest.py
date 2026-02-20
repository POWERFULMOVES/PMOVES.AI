"""Global pytest fixture bridge for per-service test runs.

CI executes service suites in isolation (one pytest invocation per path). Importing
the shared fixtures here ensures every service test tree still receives the common
stubs/helpers from ``pmoves/tests/conftest.py``.
"""

from tests.conftest import *  # noqa: F401,F403
