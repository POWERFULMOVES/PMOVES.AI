"""Bootstrap sys.path so ssh_surface imports work from any pytest rootdir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
