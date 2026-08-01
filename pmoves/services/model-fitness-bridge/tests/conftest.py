import sys
import os

# Hyphenated dir names aren't valid Python modules — add to sys.path directly
_service_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _service_dir not in sys.path:
    sys.path.insert(0, _service_dir)
