"""Smoke test conftest — ensures the smoke directory is importable."""

import sys
from pathlib import Path

# Add the smoke directory to sys.path so _smoke_helpers can be imported
_smoke_dir = str(Path(__file__).resolve().parent)
if _smoke_dir not in sys.path:
    sys.path.insert(0, _smoke_dir)
