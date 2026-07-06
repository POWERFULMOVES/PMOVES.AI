"""Test config for botz-gateway — make the service module importable in isolation.

Follows the PMOVES service-test convention: fixtures/modules live at the service
root and are imported via importlib. Keeping this scoped to the service dir avoids
the common ``main.py`` name-shadow across services.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# The gateway fails closed without a service-role key (C-04). Provide a dummy so
# the module can be imported for unit tests; no Supabase call is made in these tests.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
