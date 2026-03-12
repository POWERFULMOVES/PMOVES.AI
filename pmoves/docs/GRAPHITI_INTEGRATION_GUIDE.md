# Graphiti Integration Guide

**Layer:** L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> How to add Graphiti trail signing to a new PMOVES.AI service. Includes Python and TypeScript integration patterns, NATS emission, and validation.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Python Integration](#python-integration)
3. [TypeScript Integration](#typescript-integration)
4. [NATS Emission Pattern](#nats-emission-pattern)
5. [Hook-Based Auto-Signing](#hook-based-auto-signing)
6. [Testing](#testing)
7. [Checklist](#checklist)
8. [Cross-References](#cross-references)

---

## Prerequisites

Before integrating Graphiti:

1. **Agent registered**: Your agent's identity must exist in `pmoves/config/agent_signatures.yaml`
2. **NATS connectivity**: Service must connect to `nats://nats:pmoves@nats:4222`
3. **Optional**: `CHIT_PASSPHRASE` environment variable for signed payloads
4. **Optional**: JSON Schema for validation (`pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json`)

---

## Python Integration

### Minimal Integration (5 lines)

```python
from pmoves.tools.sign_trail import build_payload
from pmoves.tools.chit_security import sign_cgp
import os, json

def sign_work(summary: str, agent_id: str = "claude-opus"):
    payload = build_payload(agent_id=agent_id, summary=summary, phase="Phase H")
    passphrase = os.environ.get("CHIT_PASSPHRASE")
    if passphrase:
        payload = sign_cgp(payload, passphrase)
    return payload
```

### Full Integration with NATS Emission

```python
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List

import nats

from pmoves.tools.sign_trail import build_payload
from pmoves.tools.chit_security import sign_cgp


class GraphitiTrailEmitter:
    """Emit Graphiti trail entries to NATS with optional HMAC signing."""

    NATS_SUBJECT = "agent.graphiti.signed.v1"

    def __init__(
        self,
        agent_id: str,
        nats_url: str = "nats://nats:pmoves@nats:4222",
        passphrase: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.nats_url = nats_url
        self.passphrase = passphrase or os.environ.get("CHIT_PASSPHRASE")
        self._nc: Optional[nats.NATS] = None

    async def connect(self):
        """Connect to NATS."""
        self._nc = nats.NATS()
        await self._nc.connect(self.nats_url)

    async def close(self):
        """Disconnect from NATS."""
        if self._nc:
            await self._nc.close()

    async def emit(
        self,
        summary: str,
        phase: str = "Phase H",
        resonance: Optional[List[str]] = None,
        handoff: Optional[dict] = None,
    ) -> dict:
        """Build, sign, and emit a trail entry.

        Args:
            summary: One-line work summary (max 200 chars)
            phase: Project phase label
            resonance: Override default resonance domains
            handoff: Optional handoff context for next agent

        Returns:
            The signed (or unsigned) payload that was emitted
        """
        # Build payload
        payload = build_payload(
            agent_id=self.agent_id,
            summary=summary,
            phase=phase,
            resonance=resonance,
        )

        # Add handoff if provided
        if handoff:
            payload["handoff"] = handoff

        # Sign if passphrase available
        if self.passphrase:
            payload = sign_cgp(payload, self.passphrase)
        else:
            import sys
            print(
                "[warn] CHIT_PASSPHRASE not set — payload is unsigned",
                file=sys.stderr,
            )

        # Emit to NATS
        if self._nc and self._nc.is_connected:
            await self._nc.publish(
                self.NATS_SUBJECT,
                json.dumps(payload).encode(),
            )

        return payload


# Usage in a FastAPI service
from fastapi import FastAPI
from contextlib import asynccontextmanager

emitter = GraphitiTrailEmitter(agent_id="my-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await emitter.connect()
    yield
    # Sign trail on shutdown
    await emitter.emit(
        summary="Service shutting down gracefully",
        resonance=["lifecycle"],
    )
    await emitter.close()

app = FastAPI(lifespan=lifespan)

@app.post("/task/complete")
async def complete_task(task_id: str, result: str):
    # ... do work ...
    await emitter.emit(
        summary=f"Completed task {task_id}",
        resonance=["task-completion"],
    )
    return {"status": "ok"}
```

### Using subprocess (No Python Import)

For services that can't import PMOVES Python modules:

```python
import subprocess
import json
import os

def sign_trail_subprocess(summary: str, agent_id: str = "claude-opus") -> dict:
    env = os.environ.copy()
    result = subprocess.run(
        [
            "python", "pmoves/tools/sign_trail.py",
            "--agent-id", agent_id,
            "--summary", summary,
            "--phase", "Phase H",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return json.loads(result.stdout)
```

---

## TypeScript Integration

### Using NATS.js

```typescript
import { connect, StringCodec } from 'nats';
import * as crypto from 'crypto';

interface TrailPayload {
  agent_id: string;
  glyph: string;
  color: string;
  phase: string;
  timestamp: string;
  summary: string;
  resonance?: string[];
  sig?: {
    alg: string;
    kid: string;
    hmac: string;
  };
}

class GraphitiEmitter {
  private sc = StringCodec();

  constructor(
    private agentId: string,
    private glyph: string,
    private color: string,
    private natsUrl: string = 'nats://nats:pmoves@nats:4222',
    private passphrase?: string,
  ) {
    this.passphrase = passphrase || process.env.CHIT_PASSPHRASE;
  }

  async emit(summary: string, phase: string = 'Phase H'): Promise<TrailPayload> {
    const payload: TrailPayload = {
      agent_id: this.agentId,
      glyph: this.glyph,
      color: this.color,
      phase,
      timestamp: new Date().toISOString(),
      summary: summary.slice(0, 200),
    };

    // Sign if passphrase available
    if (this.passphrase) {
      const kid = crypto
        .createHash('sha256')
        .update(this.passphrase)
        .digest('hex')
        .slice(0, 16);

      const canonical = JSON.stringify(
        payload,
        Object.keys(payload).sort(),
      ).replace(/\s/g, '');

      // Proper canonical: sorted keys, no whitespace
      const sortedPayload = this.sortObject(payload);
      const canonicalStr = JSON.stringify(sortedPayload);

      const hmacDigest = crypto
        .createHmac('sha256', this.passphrase)
        .update(canonicalStr)
        .digest('base64');

      payload.sig = {
        alg: 'HMAC-SHA256',
        kid,
        hmac: hmacDigest,
      };
    }

    // Publish to NATS
    const nc = await connect({ servers: this.natsUrl });
    nc.publish(
      'agent.graphiti.signed.v1',
      this.sc.encode(JSON.stringify(payload)),
    );
    await nc.flush();
    await nc.close();

    return payload;
  }

  private sortObject(obj: Record<string, unknown>): Record<string, unknown> {
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(obj).sort()) {
      const val = obj[key];
      if (val && typeof val === 'object' && !Array.isArray(val)) {
        sorted[key] = this.sortObject(val as Record<string, unknown>);
      } else {
        sorted[key] = val;
      }
    }
    return sorted;
  }
}

// Usage
const emitter = new GraphitiEmitter('my-service', '▸', '#8B5CF6');
await emitter.emit('Processed 150 documents');
```

---

## NATS Emission Pattern

### Subject Convention

All trail entries go to `agent.graphiti.signed.v1` regardless of signing status.

### Message Format

- **Encoding:** UTF-8 JSON
- **Headers:** None required (payload is self-describing via `agent_id`)
- **Size limit:** NATS default (1MB) — trail entries are typically < 1KB

### JetStream Configuration

For durable trail storage:

```bash
nats stream add GRAPHITI_TRAILS \
  --subjects "agent.graphiti.signed.v1" \
  --storage file \
  --retention limits \
  --max-msgs 1000000 \
  --max-age 365d
```

### Consumer Pattern

```python
# Subscribe to all trail entries
async def consume_trails():
    nc = nats.NATS()
    await nc.connect("nats://nats:pmoves@nats:4222")

    sub = await nc.subscribe("agent.graphiti.signed.v1")
    async for msg in sub.messages:
        trail = json.loads(msg.data)
        agent = trail["agent_id"]
        summary = trail["summary"]
        signed = "sig" in trail
        print(f"{trail['glyph']} {agent}: {summary} [signed={signed}]")
```

---

## Hook-Based Auto-Signing

### PostToolUse Hook

Claude Code CLI hooks trigger auto-signing when:

1. The `Edit` or `Write` tool modifies a file
2. The file path contains `AGENT_TRAIL` or `graphiti` (case-insensitive)
3. `sign_trail.py` is invoked with summary `"Auto-signed trail write: <filename>"`

### Hook Configuration

Hooks are defined in `.claude/hooks/` and execute automatically. No manual setup needed for trail file auto-signing.

### Disabling Auto-Signing

Auto-signing is controlled by the PostToolUse hook definitions in `.claude/hooks/`, which trigger on file path patterns (`AGENT_TRAIL` or `graphiti`). To disable, remove or comment out the relevant hook entry — there is no environment variable toggle.

---

## Testing

### Unit Test: Payload Construction

```python
def test_build_payload():
    payload = build_payload(
        agent_id="claude-opus",
        summary="Test summary",
        phase="Phase H",
    )
    assert payload["agent_id"] == "claude-opus"
    assert payload["glyph"] == "◆"
    assert len(payload["summary"]) <= 200
    assert "timestamp" in payload
```

### Unit Test: Signing Round-Trip

```python
def test_sign_verify():
    payload = build_payload(agent_id="claude-opus", summary="Test")
    signed = sign_cgp(payload, "test-passphrase")
    assert "sig" in signed
    assert signed["sig"]["alg"] == "HMAC-SHA256"
    assert verify_cgp(signed, "test-passphrase")
    assert not verify_cgp(signed, "wrong-passphrase")
```

### Integration Test: NATS Emission

```python
import asyncio

async def test_nats_emission():
    emitter = GraphitiTrailEmitter(agent_id="test-agent")
    await emitter.connect()

    # Subscribe first
    received = []
    nc = nats.NATS()
    await nc.connect("nats://nats:pmoves@nats:4222")
    sub = await nc.subscribe("agent.graphiti.signed.v1")

    # Emit
    await emitter.emit("Integration test trail")

    # Check received
    msg = await sub.next_msg(timeout=5)
    trail = json.loads(msg.data)
    assert trail["agent_id"] == "test-agent"
    assert trail["summary"] == "Integration test trail"

    await emitter.close()
    await nc.close()
```

---

## Checklist

Before deploying Graphiti integration:

- [ ] Agent ID registered in `pmoves/config/agent_signatures.yaml`
- [ ] NATS URL includes credentials (`nats://nats:pmoves@nats:4222`)
- [ ] Payload fields match `signature.v1.schema.json`
- [ ] Summary capped at 200 characters
- [ ] Timestamp is ISO 8601 with timezone
- [ ] Signing works when `CHIT_PASSPHRASE` is set
- [ ] Unsigned mode works gracefully when passphrase is absent
- [ ] NATS subject is exactly `agent.graphiti.signed.v1`
- [ ] Trail is emitted at appropriate trigger points (see [When to Sign](#when-to-sign))
- [ ] Unit tests pass for build, sign, verify
- [ ] Integration test confirms NATS emission
- [ ] Update [GRAPHITI_AGENT_REGISTRY.md](GRAPHITI_AGENT_REGISTRY.md) if new agent added

---

## Cross-References

- [GRAPHITI_PROTOCOL_REFERENCE.md](GRAPHITI_PROTOCOL_REFERENCE.md) — Full protocol specification
- [GRAPHITI_AGENT_REGISTRY.md](GRAPHITI_AGENT_REGISTRY.md) — Agent identity catalog
- [chit_security.py](../tools/chit_security.py) — `sign_cgp()`, `verify_cgp()` implementation
- [sign_trail.py](../tools/sign_trail.py) — CLI tool and `build_payload()` function
- [signature.v1.schema.json](../contracts/schemas/agent-graphiti/signature.v1.schema.json) — JSON Schema

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
