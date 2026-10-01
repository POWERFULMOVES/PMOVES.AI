"""The URL-credential dataflow sweep stays clean: no new sink, no stale allowlist row."""

import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "url_credential_sink_sweep.py"


def test_sweep_reports_no_unredacted_sinks():
    proc = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout
    summary = proc.stdout.splitlines()[0]
    # Guard against a vacuous pass (the sweep once scanned zero files from a dotted path).
    files = int(summary.split("files=")[1].split()[0])
    assert files > 500, summary
