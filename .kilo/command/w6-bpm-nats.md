Implement NATS publish model for bpm_encoder.py (W6-P2 sub-item). This is a handoff from 4090-CLAUDE field brief — all analysis done, exact code specified below.

## Context

`pmoves/tools/bpm_encoder.py` builds CGP v0.2 packets via `build_cgp_packet()` (line 398) but never publishes them. This is the same pull-model gap that `beats_to_voice.py` had before PR #1402. The pattern is proven — this is a straight port.

**Issue:** #1411 (W6-P2 [5090]: bpm_encoder NATS publish gap)
**Branch:** `feat/w6-tokenism-nats-5090`
**Village Rule:** one scope, one commit, one PR

## What currently exists in bpm_encoder.py

- `build_cgp_packet()` at line 398 — full CGP v0.2 packet, docstring says "NATS publish" but never does it
- `_cmd_encode()` at line 487 — builds packet on `--cgp` flag, prints stdout only
- No `asyncio` import, no `os` import, no `NATS_URL` constant, no `NATS_SUBJECT` constant
- Total file: 572 lines

## Exact Changes

### Step 1: Add imports (after `import time` at line 34)

```python
import asyncio
import os
```

### Step 2: Add constants (after `BOUNDARY_PAUSE_MS` block, ~line 66)

```python
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
NATS_SUBJECT = "tokenism.prosodic.bpm.v1"
```

### Step 3: Add publish function (after `build_cgp_packet()`, before `# CLI (argparse)` comment)

```python
async def _nats_publish_cgp(cgp_packet: dict, nats_url: str = NATS_URL) -> bool:
    """Publish CGP packet to tokenism.prosodic.bpm.v1. Returns True on success."""
    try:
        import nats as natspy
        nc = await natspy.connect(nats_url)
        await nc.publish(NATS_SUBJECT, json.dumps(cgp_packet).encode("utf-8"))
        await nc.drain()
        return True
    except Exception as e:
        sys.stderr.write(f"[bpm_encoder] NATS publish skipped: {e}\n")
        return False
```

### Step 4: Modify `_cmd_encode()` (after `print(json.dumps(packet, indent=2))` at line 494)

```python
    if args.cgp and getattr(args, "publish_nats", False):
        published = asyncio.run(_nats_publish_cgp(packet, args.nats_url))
        if not published:
            sys.stderr.write("[bpm_encoder] CGP not published to NATS\n")
```

### Step 5: Add CLI flags to encode subparser (after `--agent-id` arg, ~line 546)

```python
    p_enc.add_argument("--publish-nats", action="store_true",
                        help="Publish CGP packet to NATS after encoding")
    p_enc.add_argument("--nats-url", type=str, default=NATS_URL,
                        help="NATS server URL")
```

## Test File to Create

**File:** `pmoves/tools/test_bpm_encoder_nats.py`

```python
"""Tests for bpm_encoder NATS publish."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpm_encoder


class TestNatsPublishCgp(unittest.IsolatedAsyncioTestCase):
    async def test_publish_success(self):
        mock_nc = AsyncMock()
        mock_nats = MagicMock()
        mock_nats.connect = AsyncMock(return_value=mock_nc)
        with patch.dict("sys.modules", {"nats": mock_nats}):
            result = await bpm_encoder._nats_publish_cgp({"spec": "chit.cgp.v0.2"})
        assert result is True
        mock_nc.publish.assert_awaited_once()
        subject_used = mock_nc.publish.call_args[0][0]
        assert subject_used == bpm_encoder.NATS_SUBJECT

    async def test_publish_nats_unavailable(self):
        with patch.dict("sys.modules", {"nats": None}):
            result = await bpm_encoder._nats_publish_cgp({"spec": "chit.cgp.v0.2"})
        assert result is False


if __name__ == "__main__":
    unittest.main()
```

## Verification

```bash
# 1. Tests pass (no live NATS needed)
python -m pytest pmoves/tools/test_bpm_encoder_nats.py -v

# 2. CLI still works (no regression)
python pmoves/tools/bpm_encoder.py encode --bpm 120 --pattern "hello world" --cgp

# 3. New flag appears
python pmoves/tools/bpm_encoder.py encode --help

# 4. Graceful NATS miss (not crash)
python pmoves/tools/bpm_encoder.py encode --bpm 120 --pattern "test" --cgp --publish-nats --nats-url nats://localhost:9999
```

## Pattern Reference

`pmoves/tools/beats_to_voice.py` — identical pattern, already on main via PR #1402.
`pmoves/tools/test_beats_to_voice_nats.py` — test reference (5/5 passing).

## Co-author

```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```
