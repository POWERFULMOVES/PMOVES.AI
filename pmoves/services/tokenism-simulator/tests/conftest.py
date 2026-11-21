"""Collection-time dev shim for the tokenism-simulator test directory.

config/__init__.py instantiates ServiceConfig() at import time and — after
the fail-closed fix — raises when it finds neither SECRET_KEY nor an
explicit dev signal. Test modules import config at module level (during
pytest collection, before any monkeypatch can run), so without this shim
CI collection itself crashes on every module that imports config.

One setdefault, no logic: it only supplies the floor for IMPORT. The
production-raises test deletes the var explicitly before reloading, so the
shim cannot mask the fail-closed contract it exists to let us test.
"""

import os

os.environ.setdefault("TOKENISM_DEV", "1")
