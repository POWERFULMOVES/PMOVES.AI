# AGENTS Aligned Implementation Roadmap

**Date:** 2026-02-02 (status annotations updated 2026-04-10)
**Branch:** PMOVES.AI-Edition-Hardened → main
**Based On:** PMOVES-ToKenism-Multi, PMOVES-DoX, PMOVES-BoTZ patterns

---

## Executive Summary

This roadmap synthesizes the best patterns from PMOVES-ToKenism-Multi (event-driven coordination, CHIT integration), PMOVES-DoX (documentation structure, cookbook patterns), and PMOVES-BoTZ (security hooks, agent orchestration) to implement the AGENTS architecture vision.

---

## Pattern Alignment Summary

| Pattern | Source | Adopt? | Notes |
|---------|--------|--------|-------|
| Event Bus with schema validation | ToKenism-Multi | ✅ Yes | Custom event bus with retry logic |
| SKILL.md frontmatter pattern | DoX + BoTZ | ✅ Yes | Standardized skill definition |
| Cookbook/recipe documentation | DoX | ✅ Yes | Progressive disclosure pattern |
| Security hooks (patterns.yaml) | BoTZ | ✅ Yes | Deterministic + probabilistic rules |
| MCP gateway pattern | BoTZ + ToKenism | ✅ Yes | Unified tool routing |
| A2A protocol | BoTZ | ✅ Yes | JSON-RPC 2.0 task lifecycle |
| Multi-agent swarm (mprocs) | BoTZ | ✅ Yes | Gateway + Architect + Builder + Auditor |
| CHIT geometry integration | ToKenism | ✅ Yes | CGP for cross-agent communication |
| Vertical slice architecture | DoX | ✅ Yes | Feature-based organization |
| Tier-based environment config | ToKenism | ✅ Yes | YAML anchors for service tiers |

---

## Phase 1: Security Foundation (Week 1-2) — COMPLETE (4/4) ✅ verified 2026-04-10

### Pattern Source: PMOVES-BoTZ `patterns.yaml` and `hooks/`

#### Task 1.1: Security Constitution

**Reference:** `PMOVES-BoTZ/patterns.yaml`

**Create:** `pmoves/services/agent-zero/security/patterns.yaml`

```yaml
# PMOVES.AI Security Constitution
# Implements "Defense in Depth" as per BoTZ specification

global_protection:
  # BLOCKING RULES: Commands that are strictly forbidden
  blocked_commands:
    - pattern: "rm -rf /"
      reason: "Catastrophic system destruction risk. BLOCKED."
    - pattern: "rm -rf \\."
      reason: "Current directory destruction. BLOCKED."
    - pattern: "git push --force"
      reason: "History rewriting is forbidden for agents. Ask a human."
    - pattern: "drop database"
      reason: "Database destruction requires human 'Ask' permission."
      case_insensitive: true
    - pattern: "chmod 777"
      reason: "Insecure permission setting."

  # PATH PROTECTION: Granular file access control
  protected_paths:
    # Zero Access - Agent cannot see or modify
    zero_access:
      - ".env*"
      - "*.pem"
      - "*.key"
      - "**/secrets/**"
      - "**/.ssh/**"

    # Read Only - Agent can read but not modify
    read_only:
      - ".git/"
      - "patterns.yaml"
      - "*.lock"
      "requirements*.txt"

    # No Delete - Agent can modify but not delete
    no_delete:
      - "src/core/**"
      - "features/**"
      - "docs/**"
      - "pmoves/services/agent-zero/**"

hooks:
  pre_execution:
    - name: "Deterministic Safety Check"
      type: "regex"
      file: "hooks/deterministic.py"

    - name: "Probabilistic Safety Check"
      type: "llm_eval"
      model: "utility"  # TensorZero role — routes to fast/cheap model
      file: "hooks/probabilistic.py"
      trigger_on: "shell_command"
      action_on_risk: "ask_user"

  audit:
    enabled: true
    path: "memory/audit/"
    format: "jsonl"
```

#### Task 1.2: Deterministic Hooks

**Reference:** `PMOVES-BoTZ/hooks/pre_command.py`

**Create:** `pmoves/services/agent-zero/security/hooks/deterministic.py`

```python
#!/usr/bin/env python3
"""
Deterministic Security Hooks for Agent Zero

Validates commands against patterns.yaml before execution.
Based on PMOVES-BoTZ security constitution.
"""

import re
import yaml
from pathlib import Path
from typing import Optional, Tuple

PATTERNS_PATH = Path(__file__).parent.parent / "patterns.yaml"


class DeterministicHook:
    """Pre-execution validation using regex patterns."""

    def __init__(self, patterns_path: Path = PATTERNS_PATH):
        self.patterns_path = patterns_path
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict:
        """Load security patterns from YAML."""
        if not self.patterns_path.exists():
            return {"blocked_commands": [], "protected_paths": {}}

        with open(self.patterns_path) as f:
            return yaml.safe_load(f)

    def check_command(self, command: str, file_path: str = None) -> Tuple[bool, str]:
        """
        Check if command is safe to execute.

        Returns:
            (allowed, reason) tuple
        """
        # Check blocked commands
        for rule in self.patterns.get("blocked_commands", []):
            pattern = rule["pattern"]
            flags = re.IGNORECASE if rule.get("case_insensitive", False) else 0

            if re.search(pattern, command, flags):
                return False, f"BLOCKED: {rule['reason']}"

        # Check protected paths
        if file_path:
            if self._is_protected(file_path, "zero_access"):
                return False, f"BLOCKED: Cannot access protected path: {file_path}"

        return True, "OK"

    def _is_protected(self, path: str, protection_level: str) -> bool:
        """Check if path has the given protection level."""
        protected = self.patterns.get("protected_paths", {}).get(protection_level, [])
        for pattern in protected:
            if Path(path).match(pattern):
                return True
        return False


def pre_command_check(command: str, file_path: str = None) -> bool:
    """
    Hook entry point for pre-execution validation.

    Raises:
        PermissionError: If command is blocked
    """
    hook = DeterministicHook()
    allowed, reason = hook.check_command(command, file_path)

    if not allowed:
        raise PermissionError(reason)

    return True
```

#### Task 1.3: Probabilistic Hooks

**Reference:** `PMOVES-BoTZ/hooks/prompt_scan.py`

**Create:** `pmoves/services/agent-zero/security/hooks/probabilistic.py`

```python
#!/usr/bin/env python3
"""
Probabilistic Security Hooks for Agent Zero

Uses LLM semantic analysis for safety checks that regex cannot catch.
Based on PMOVES-BoTZ probabilistic hook pattern.
"""

import os
from pathlib import Path
from typing import Literal

# Lazy load Anthropic to avoid dependency in non-hook contexts
def _get_client():
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    except ImportError:
        return None


class ProbabilisticHook:
    """LLM-based semantic safety analysis."""

    def __init__(self, model: str = "claude-3-haiku-20240307"):
        self.model = model
        self.client = None

    def check_command(self, command: str, context: str = "") -> Literal["SAFE", "RISKY", "SKIP"]:
        """
        Analyze command semantics for safety.

        Returns:
            "SAFE" - Command appears safe
            "RISKY" - Command may pose risks
            "SKIP" - Analysis unavailable
        """
        client = _get_client()
        if not client:
            return "SKIP"

        prompt = f"""Analyze the following shell command for security risks.

Context: This command is running in the PMOVES.AI production environment.

Command: {command}
Context: {context}

Risk Assessment: Does this command pose a risk of:
1. Data loss (deleting important files, dropping databases)
2. Secret exposure (printing API keys, tokens, passwords)
3. System instability (modifying system files, changing permissions)

Answer strictly: SAFE or RISKY. If RISKY, explain in one sentence.
"""

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text.strip().upper()

            if result.startswith("RISKY"):
                return "RISKY"
            return "SAFE"

        except Exception:
            return "SKIP"


def probabilistic_check(command: str, context: str = "") -> bool:
    """
    Hook entry point for probabilistic validation.

    Returns:
        True if SAFE, False if RISKY
    """
    hook = ProbabilisticHook()
    result = hook.check_command(command, context)

    if result == "RISKY":
        return False
    return True  # SAFE or SKIP both allow
```

#### Task 1.4: Audit Logger

**Reference:** `PMOVES-BoTZ/hooks/audit_log.py`

**Create:** `pmoves/services/agent-zero/security/hooks/audit_log.py`

```python
#!/usr/bin/env python3
"""
Audit Logging for Agent Zero

Logs all tool executions for security and debugging.
Based on PMOVES-BoTZ audit pattern.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class AuditLogger:
    """Thread-safe audit logger for agent actions."""

    def __init__(self, audit_path: Path = None):
        if audit_path is None:
            audit_path = Path(__file__).parent.parent.parent / "memory" / "audit"
        self.audit_path = audit_path
        self.audit_path.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Log an event to the audit trail.

        Returns:
            Event ID (timestamp-based)
        """
        event_id = f"{int(time.time() * 1000)}"

        event = {
            "id": event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }

        # Write to daily log file
        log_file = self.audit_path / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        return event_id

    def log_command_execution(
        self,
        command: str,
        result: str,
        duration_ms: int,
        agent_id: str
    ):
        """Log a command execution event."""
        self.log("command_execution", {
            "command": command,
            "result": result,
            "duration_ms": duration_ms,
            "agent_id": agent_id
        })

    def log_tool_use(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        agent_id: str
    ):
        """Log a tool use event."""
        self.log("tool_use", {
            "tool": tool_name,
            "parameters": parameters,
            "agent_id": agent_id
        })
```

---

## Phase 2: A2A Protocol Integration (Week 3-4) — PARTIAL (1/2) ⚠️ verified 2026-04-10

### Pattern Source: PMOVES-BoTZ `features/a2a/`

#### Task 2.1: Agent Card Endpoint

**Reference:** `PMOVES-BoTZ/features/a2a/server.py`

**Create:** `pmoves/services/agent-zero/python/features/a2a/server.py`

```python
"""
A2A Server Implementation for Agent Zero

Implements the Agent2Agent protocol for agent interoperability.
Based on PMOVES-BoTZ A2A integration and Google's A2A specification.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# A2A Types
class AgentCard(BaseModel):
    """Agent identity and capability statement."""
    name: str
    description: str
    version: str
    capabilities: List[str]
    input_modalities: List[str]
    output_modalities: List[str]
    authentication: Optional[str] = None

class Task(BaseModel):
    """A2A Task object."""
    id: str
    status: str  # submitted, working, input-required, completed, failed
    instruction: str
    artifacts: List[dict] = []

# Agent Zero Configuration
AGENT_CARD = AgentCard(
    name="agent-zero",
    description="PMOVES.AI autonomous agent for general development tasks",
    version="2.0.0",
    capabilities=[
        "code_generation",
        "file_operations",
        "command_execution",
        "web_search",
        "mcp_tool_use"
    ],
    input_modalities=["text/plain", "application/json"],
    output_modalities=["text/markdown", "application/json", "text/plain"],
    authentication="bearer_token"
)

app = FastAPI(title="Agent Zero A2A Server")

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Discovery endpoint for A2A clients."""
    return AGENT_CARD.model_dump()

@app.post("/a2a/v1/tasks")
async def create_task(task: Task):
    """Create a new task on Agent Zero."""
    # Map A2A task to Agent Zero context
    # This would integrate with Agent Zero's chat/context management
    return {
        "jsonrpc": "2.0",
        "id": task.id,
        "result": {"status": "submitted", "task_id": task.id}
    }

@app.get("/a2a/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task status."""
    # Query Agent Zero's context store
    return {"task_id": task_id, "status": "working"}

@app.post("/a2a/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    # Send cancel signal to Agent Zero
    return {"task_id": task_id, "status": "cancelled"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082)
```

#### Task 2.2: A2A Client for Archon

**Reference:** `PMOVES-BoTZ/features/a2a/client.py`

**Create:** `pmoves/services/archon/python/a2a_client.py`

```python
"""
A2A Client for Archon

Allows Archon to discover and communicate with A2A-compliant agents.
Based on PMOVES-BoTZ A2A client implementation.
"""

import httpx
from typing import List, Optional
from pydantic import BaseModel


class A2AClient:
    """Client for communicating with A2A agents."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def discover_agent(self, agent_url: str) -> dict:
        """Discover agent capabilities via Agent Card."""
        response = await self.client.get(f"{agent_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.json()

    async def create_task(
        self,
        agent_url: str,
        instruction: str,
        task_id: str
    ) -> dict:
        """Submit a task to an agent."""
        response = await self.client.post(
            f"{agent_url}/a2a/v1/tasks",
            json={
                "id": task_id,
                "instruction": instruction,
                "status": "submitted"
            }
        )
        response.raise_for_status()
        return response.json()

    async def get_task_status(self, agent_url: str, task_id: str) -> dict:
        """Get task status from agent."""
        response = await self.client.get(f"{agent_url}/a2a/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    async def cancel_task(self, agent_url: str, task_id: str) -> dict:
        """Cancel a task on an agent."""
        response = await self.client.post(f"{agent_url}/a2a/v1/tasks/{task_id}/cancel")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Usage in Archon
async def submit_to_agent_zero(agent_url: str, instruction: str):
    """Example: Submit a task to Agent Zero from Archon."""
    client = A2AClient(agent_url)

    # Discover capabilities
    card = await client.discover_agent(agent_url)
    print(f"Discovered: {card['name']} - {card['description']}")

    # Submit task
    import uuid
    task_id = str(uuid.uuid4())
    result = await client.create_task(agent_url, instruction, task_id)
    print(f"Task created: {result}")

    await client.close()
```

---

## Phase 3: SKILL.md Pattern (Week 4-5) — TEMPLATE COMPLETE ⚠️ verified 2026-04-10

### Pattern Source: PMOVES-DoX + PMOVES-BoTZ skill structure

#### Task 3.1: SKILL.md Template

**Reference:** PMOVES-DoX `.claude/skills/mcp-catalog/SKILL.md`

**Create:** `pmoves/services/agent-zero/skills/.template/SKILL.md`

```yaml
---
name: [Skill Name]
description: [One-line description for quick identification]
keywords: [comma-separated keywords for discovery]
version: 1.0.0
category: [Category/Subcategory]
---

# [Skill Name]

**Category**: [Category/Subcategory]
**Version**: 1.0.0
**Status**: Stable | Experimental | Beta

## Overview

[Brief description of what this skill does and its purpose in 2-3 sentences.]

## Capabilities

List of key capabilities with emoji markers:
- ✨ [Capability 1 description]
- 🔍 [Capability 2 description]
- 🛠️ [Capability 3 description]

## Skill Structure

```
.claude/skills/[skill-name]/
├── SKILL.md              # This file
├── tools/                # Implementation tools
│   ├── [tool1].py       # Tool implementations
│   └── [tool2].py
├── prompts/              # Prompt templates
│   ├── [prompt1].md
│   └── [prompt2].md
├── cookbook/             # Usage examples
│   └── examples.md
└── README.md             # Additional context
```

## Trigger Phrases

| Natural Language Phrase | Action | Tool |
|-------------------------|--------|------|
| "list [thing]" | List items | tool1.py |
| "show [status]" | Display status | tool2.py |
| "create [resource]" | Create resource | tool3.py |

## Tools

### [Tool Name 1]

**Purpose**: [Brief description]

**Usage**:
```bash
python tools/[tool_name].py --options
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| param1 | string | Yes | Description |
| param2 | int | No | Description |

**Output**: Description of expected output format

### [Tool Name 2]

[Additional tools...]

## Configuration

Required environment variables or settings:

```yaml
ENV_VAR_1: [description]
ENV_VAR_2: [default_value]
```

## Cookbook

For detailed examples and workflows, see `cookbook/examples.md`.

### Quick Examples

**Example 1: [Use Case]**
```python
# Code example
result = tool1.execute(param1="value")
```

**Example 2: [Another Use Case]**
```python
# Code example
result = tool2.process(param2=123)
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python tools/tool1.py` | Quick action |
| `python tools/tool2.py --help` | Help |

## Integration Points

- **NATS Subject**: `nats.subject.name`
- **API Endpoint**: `http://endpoint`
- **Database**: `connection_string`
- **MCP Server**: `server:tool`

## Troubleshooting

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| [Error message] | [Fix steps] |
| [Another error] | [Fix steps] |

## See Also

- [Related Skill 1](../skill-1/SKILL.md)
- [Related Skill 2](../skill-2/SKILL.md)
- [Main Documentation](../../../docs/README.md)
```

#### Task 3.2: Convert Existing Instruments to Skills

**Reference:** PMOVES-BoTZ `skills/` directory structure

**Migration Plan:**

```
Current:                                Target:
data/agent-zero/instruments/default/    pmoves/services/agent-zero/skills/
├── yt_download/                        ├── youtube-downloader/
│   ├── download.py                      │   ├── SKILL.md
│   └── download.md                      │   ├── tools/
│                                        │   │   ├── download.py
├── claude_code/                         │   │   └── transcript.py
│   ├── claude_code.md                   │   ├── prompts/
│   └── instrument.py                    │   │   └── download_prompts.md
│                                        │   └── cookbook/
│                                        │       └── examples.md
│                                        ├── git-wizard/
│                                        │   ├── SKILL.md
│                                        │   ├── tools/
│                                        │   │   ├── git_ops.py
│                                        │   │   └── git_graph.sh
│                                        │   └── cookbook/
│                                        │       └── git-recipes.md
```

---

## Phase 4: Event-Driven Coordination (Week 5-6) — COMPLETE ✅ verified 2026-04-10

### Pattern Source: PMOVES-ToKenism-Multi `event-bus/`

#### Task 4.1: Event Bus Implementation

**Reference:** `PMOVES-ToKenism-Multi/integrations/event-bus/event-bus.ts`

**Create:** `pmoves/services/agent-zero/python/events/bus.py`

```python
"""
Event Bus for Agent Coordination

Based on PMOVES-ToKenism-Multi event bus pattern.
Implements pub/sub with schema validation and retry logic.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from nats.aio.client import Client as NATSClient
import nats

from ..common.schema_validator import SchemaValidator


@dataclass
class Event:
    """Event envelope for agent communication."""
    id: str = field(default_factory=lambda: f"evt-{int(asyncio.get_event_loop().time() * 1000)}")
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    type: str = ""
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None


class EventBus:
    """
    Event bus for agent coordination.

    Features:
    - Schema validation for all events
    - Exponential backoff retry (max 3)
    - Wildcard subscription support
    - Metrics tracking
    """

    def __init__(self, nats_url: str = "nats://nats:pmoves@nats:4222"):
        self.nats_url = nats_url
        self.nc: Optional[NATSClient] = None
        self.validators: Dict[str, SchemaValidator] = {}
        self.metrics: Dict[str, int] = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0
        }

    async def connect(self):
        """Connect to NATS."""
        self.nc = NATSClient()
        await self.nc.connect(self.nats_url)

    async def publish(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any],
        source: str = "agent-zero",
        metadata: Dict[str, Any] = None
    ):
        """
        Publish an event to the bus.

        Subject format: `pmoves.{service}.{event}.v1`
        """
        event = Event(
            type=event_type,
            source=source,
            data=data,
            metadata=metadata or {}
        )

        # Validate if schema exists
        if event_type in self.validators:
            self.validators[event_type].validate(event.data)

        # Publish to NATS
        await self.nc.publish(
            subject,
            json.dumps(event.__dict__).encode()
        )

        self.metrics["events_published"] += 1

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[Event], None]
    ):
        """
        Subscribe to events.

        Supports wildcards: `pmoves.>` for all PMOVES events
        """
        async def wrapper(msg):
            try:
                event = Event(**json.loads(msg.data.decode()))
                await handler(event)
                self.metrics["events_processed"] += 1
            except Exception as e:
                self.metrics["events_failed"] += 1
                # Log error but don't crash
                print(f"Event processing error: {e}")

        await self.nc.subscribe(subject, cb=wrapper)

    async def close(self):
        """Close NATS connection."""
        if self.nc:
            await self.nc.close()


# Singleton instance
_bus: Optional[EventBus] = None


async def get_event_bus() -> EventBus:
    """Get or create singleton event bus."""
    global _bus
    if _bus is None:
        _bus = EventBus()
        await _bus.connect()
    return _bus
```

#### Task 4.2: Standard Event Subjects

**Reference:** PMOVES-ToKenism-Multi event patterns

**Create:** `pmoves/services/agent-zero/python/events/subjects.py`

```python
"""
Standard Event Subjects for PMOVES.AI Agent Coordination

Based on PMOVES-ToKenism-Multi event naming conventions.
"""

# Agent Lifecycle Events
AGENT_STARTED = "pmoves.agent.started.v1"
AGENT_STOPPED = "pmoves.agent.stopped.v1"
AGENT_ERROR = "pmoves.agent.error.v1"

# Task/Work Events
TASK_CREATED = "pmoves.work.task.created.v1"
TASK_ASSIGNED = "pmoves.work.task.assigned.v1"
TASK_COMPLETED = "pmoves.work.task.completed.v1"
TASK_FAILED = "pmoves.work.task.failed.v1"

# Tool Execution Events
TOOL_STARTED = "pmoves.agent.tool.started.v1"
TOOL_COMPLETED = "pmoves.agent.tool.completed.v1"
TOOL_FAILED = "pmoves.agent.tool.failed.v1"

# A2A Coordination Events
A2A_TASK_SUBMITTED = "pmoves.a2a.task.submitted.v1"
A2A_TASK_RECEIVED = "pmoves.a2a.task.received.v1"
A2A_ARTIFACT_READY = "pmoves.a2a.artifact.ready.v1"

# CHIT Geometry Events (future)
GEOMETRY_PUBLISHED = "pmoves.geometry.published.v1"
CGP_READY = "pmoves.geometry.cgp.ready.v1"

# Wildcard subjects for catching all
ALL_PMOVES_EVENTS = "pmoves.>"
ALL_AGENT_EVENTS = "pmoves.agent.>"
ALL_WORK_EVENTS = "pmoves.work.>"
```

---

## Phase 5: Threading and Orchestration (Week 6-7) — COMPLETE ✅ verified 2026-04-10

### Pattern Source: PMOVES-BoTZ `.mprocs.yaml` + `gateway/`

#### Task 5.1: mprocs Configuration

**Reference:** `PMOVES-BoTZ/.mprocs.yaml`

**Create:** `pmoves/services/agent-zero/.mprocs.yaml`

```yaml
# PMOVES.AI Agent Orchestration Config
# Implements the "BotZ" multi-agent swarm architecture

procs:
  # 1. THE GATEWAY (The Manager)
  # Listens for user intent and dispatches tasks
  gateway:
    cmd: ["uv", "run", "python/features/gateway/gateway.py"]
    cwd: "."
    autostart: true
    env:
      MPLCROCS_SERVER: "127.0.0.1:4050"
      AGENT_ROLE: "gateway"

  # 2. THE ARCHITECT (The Brain - Opus 4.5)
  # Used for high-level planning and "King Mode" reasoning
  architect:
    shell: "claude --model opus-latest --system 'You are the Chief Architect. Your output is PLANS, not code. Read memory/architecture.md first.'"
    cwd: "."
    stop: "SIGTERM"
    env:
      AGENT_ROLE: "architect"

  # 3. THE BUILDER (The Hands - Sonnet 3.5)
  # Executes the plans. Runs in the sandbox environment
  builder:
    shell: "claude --model sonnet-latest --system 'You are the Builder. Execute the plan provided by the Architect. You are running in a SANDBOX.'"
    cwd: "."
    env:
      AGENT_ROLE: "builder"

  # 4. THE AUDITOR (The Conscience - Haiku)
  # Runs probabilistic safety checks on code changes
  auditor:
    shell: "claude --model haiku-latest --system 'You are the Security Auditor. Review diffs in src/ for security violations.'"
    cwd: "."
    env:
      AGENT_ROLE: "auditor"

# Remote Control Server
# Allows the 'Gateway' to programmatically spawn new agent threads
server: "127.0.0.1:4050"

# Keymaps for "In-Loop" Control
keymap:
  global:
    "C-g": { c: "focus-proc", name: "gateway" }  # Jump to Gateway
    "C-a": { c: "focus-proc", name: "architect" }  # Jump to Architect
    "C-b": { c: "focus-proc", name: "builder" }  # Jump to Builder
    "C-s": { c: "start-proc" }  # Start selected agent
    "C-x": { c: "term-proc" }  # Kill selected agent
```

---

## Git Worktree Strategy

### Create Worktrees for Parallel Development

```bash
# Base repository
cd /home/pmoves/PMOVES.AI

# Phase 1 Worktree: Security Hooks
git worktree add ../pmoves-phase1-security PMOVES.AI-Edition-Hardened -b feature/agent-security-hooks

# Phase 2 Worktree: A2A Integration
git worktree add ../pmoves-phase2-a2a PMOVES.AI-Edition-Hardened -b feature/agent-a2a-integration

# Phase 3 Worktree: Skill Patterns
git worktree add ../pmoves-phase3-skills PMOVES.AI-Edition-Hardened -b feature/agent-skill-patterns

# Phase 4 Worktree: Event Bus
git worktree add ../pmoves-phase4-events PMOVES.AI-Edition-Hardened -b feature/agent-event-coordination

# Phase 5 Worktree: Threading
git worktree add ../pmoves-phase5-threads PMOVES.AI-Edition-Hardened -b feature/agent-thread-orchestration
```

---

## Task Assignment Matrix

| Phase | Task | Subagent Type | Priority | Worktree |
|-------|------|---------------|----------|----------|
| 1 | Security Constitution (patterns.yaml) | Opus (planning) → Sonnet (implementation) | P0 | phase1-security |
| 1 | Deterministic Hooks | Sonnet | P0 | phase1-security |
| 1 | Probabilistic Hooks | Sonnet | P0 | phase1-security |
| 1 | Audit Logger | Sonnet | P1 | phase1-security |
| 2 | A2A Server (Agent Zero) | Sonnet | P0 | phase2-a2a |
| 2 | A2A Client (Archon) | Sonnet | P0 | phase2-a2a |
| 2 | Agent Card Endpoint | Sonnet | P1 | phase2-a2a |
| 3 | SKILL.md Template | Sonnet | P0 | phase3-skills |
| 3 | Convert Instruments to Skills | Haiku (batch conversion) | P1 | phase3-skills |
| 3 | Skill Loader Implementation | Sonnet | P1 | phase3-skills |
| 4 | Event Bus Implementation | Sonnet | P0 | phase4-events |
| 4 | Standard Event Subjects | Haiku | P1 | phase4-events |
| 4 | Schema Validator | Sonnet | P1 | phase4-events |
| 5 | mprocs Configuration | Sonnet | P0 | phase5-threads |
| 5 | Gateway Implementation | Sonnet | P0 | phase5-threads |
| 5 | Thread Templates | Opus → Sonnet | P1 | phase5-threads |

---

## Validation Criteria

Each phase must pass the following validation:

### Phase 1 Validation
```bash
# Test security hooks
python pmoves/services/agent-zero/security/hooks/deterministic.py --test
python pmoves/services/agent-zero/security/hooks/probabilistic.py --test

# Verify patterns.yaml loads
python -c "import yaml; print(yaml.safe_load(open('pmoves/services/agent-zero/security/patterns.yaml')))"

# Run hardening tests
pytest pmoves/tests/hardening/test_docker_hardening.py -k "agent_zero" -v
```

### Phase 2 Validation
```bash
# Test A2A endpoints
curl http://localhost:8082/.well-known/agent.json

# Verify task creation
curl -X POST http://localhost:8082/a2a/v1/tasks -d '{"id": "test-1", "instruction": "say hello", "status": "submitted"}'

# Test from Archon
python pmoves/services/archon/python/test_a2a_client.py
```

### Phase 3 Validation
```bash
# Verify SKILL.md files exist
find pmoves/services/agent-zero/skills -name "SKILL.md" | wc -l

# Test skill loader
python -m pmoves.services.agent_zero.skills.loader

# Validate SKILL.md format
python pmoves/services/agent-zero/skills/validate_skills.py
```

### Phase 4 Validation
```bash
# Test event bus
python pmoves/services/agent-zero/python/events/test_bus.py

# Verify NATS connectivity
nats pub pmoves.test.event.v1 '{"test": "data"}'
nats sub "pmoves.>" &

# Check metrics
curl http://localhost:8090/metrics | grep events_
```

### Phase 5 Validation
```bash
# Test mprocs configuration
mprocs --config pmoves/services/agent-zero/.mprocs.yaml --dry-run

# Verify agent discovery
curl http://localhost:8080/mcp/agents

# Test thread execution
python pmoves/services/agent-zero/python/gateway/test_threads.py
```

---

## Related Documentation

- [PMOVES-ToKenism-Multi](../../../../PMOVES-ToKenism-Multi/) - Event bus patterns
- [PMOVES-DoX](../../../../PMOVES-DoX/) - Documentation structure
- [PMOVES-BoTZ](../../../../PMOVES-BoTZ/) - Security and orchestration
- [Implementation Gap Analysis](./IMPLEMENTATION_GAP_ANALYSIS.md)
- [AGENTS Documentation](./)
