# Event Bus Quick Start Guide

## Overview

The PMOVES.AI Event Bus provides event-driven coordination for agents via NATS message bus. This enables loose coupling between services and scalable async communication.

## Installation

No additional installation required if you have `nats-py`:

```bash
pip install nats-py
# Optional: for full JSON schema validation
pip install jsonschema
```

## Basic Usage

### 1. Get the Event Bus

```python
from pmoves.services.agent_zero.python.events import get_event_bus

# Get singleton instance
bus = await get_event_bus()
```

### 2. Publish Events

```python
from pmoves.services.agent_zero.python.events.subjects import AGENT_STARTED

await bus.publish(
    subject=AGENT_STARTED,  # "pmoves.agent.started.v1"
    event_type="AGENT_STARTED",
    data={
        "agent_id": "agent-zero",
        "capabilities": ["code_generation", "mcp_tools"],
        "version": "1.0.0"
    },
    source="agent-zero",
    correlation_id="request-123"  # Optional
)
```

### 3. Subscribe to Events

```python
from pmoves.services.agent_zero.python.events.subjects import ALL_AGENT_EVENTS

async def on_agent_event(event):
    print(f"Agent {event.data.get('agent_id')}: {event.type}")

# Subscribe to all agent events
await bus.subscribe(ALL_AGENT_EVENTS, on_agent_event)
```

### 4. Use Wildcards

```python
# Subscribe to all PMOVES events
await bus.subscribe("pmoves.>", handler)

# Subscribe to all work/task events
await bus.subscribe("pmoves.work.>", handler)
```

## Event Subjects

### Agent Lifecycle
- `AGENT_STARTED` - Agent process started
- `AGENT_STOPPED` - Agent process stopped
- `AGENT_ERROR` - Agent encountered error

### Task/Work
- `TASK_CREATED` - New task created
- `TASK_ASSIGNED` - Task assigned to worker
- `TASK_COMPLETED` - Task completed successfully
- `TASK_FAILED` - Task failed

### Tool Execution
- `TOOL_STARTED` - Tool invocation started
- `TOOL_COMPLETED` - Tool completed successfully
- `TOOL_FAILED` - Tool failed

### A2A Coordination
- `A2A_TASK_SUBMITTED` - Task submitted via A2A protocol
- `A2A_TASK_RECEIVED` - A2A task received
- `A2A_ARTIFACT_READY` - Artifact produced

### CHIT Geometry
- `GEOMETRY_PUBLISHED` - Geometry published
- `CGP_READY` - CGP primitive ready

## Schema Validation

Events can be validated against JSON schemas:

```python
from pmoves.services.agent_zero.python.events.schema import (
    SchemaValidator,
    AGENT_STARTED_SCHEMA
)

# Register validator
validator = SchemaValidator(AGENT_STARTED_SCHEMA)
bus.validators["AGENT_STARTED"] = validator

# Now publishing will validate
await bus.publish(
    subject=AGENT_STARTED,
    event_type="AGENT_STARTED",
    data={"agent_id": "required-field"}  # Must match schema
)
```

## Request-Reply Pattern

For synchronous-style communication:

```python
response = await bus.request(
    subject="pmoves.agent.query.v1",
    event_type="AGENT_QUERY",
    data={"query": "status"},
    timeout=5.0
)

if response:
    print(f"Response: {response.data}")
```

## Metrics

Track event bus activity:

```python
metrics = bus.get_metrics()
print(f"Published: {metrics['events_published']}")
print(f"Processed: {metrics['events_processed']}")
print(f"Failed: {metrics['events_failed']}")
```

## Best Practices

1. **Use wildcards for flexibility**: Subscribe to `pmoves.>` to catch all events
2. **Add correlation IDs**: Trace related events across services
3. **Validate schemas**: Ensure data integrity
4. **Handle errors gracefully**: Use try-except in handlers
5. **Use queue groups**: For load balancing, use same queue name across instances

```python
# Multiple instances, each gets a subset of events
await bus.subscribe("pmoves.work.>", handler, queue_group="workers")
```

## Testing

Run the test suite:

```bash
# Start NATS
docker compose up -d nats

# Run tests
python pmoves/services/agent-zero/python/events/test_bus.py
```

## Integration with Existing Services

The event bus integrates with existing PMOVES.AI services:

- **Agent Zero**: Publishes agent lifecycle events
- **TensorZero**: Publishes tool execution events
- **Archon**: Subscribes to A2A events for coordination
- **Work Marshaling**: Subscribes to task events for distribution

## Troubleshooting

### Connection Issues

```python
# Check NATS is running
curl http://localhost:8222/varz

# Custom NATS URL
bus = await get_event_bus(nats_url="nats://nats.example.com:4222")
```

### No Events Received

- Verify subject format: `pmoves.{service}.{event}.v1`
- Check NATS connection status
- Ensure handler is async function
- Check wildcard patterns

### Schema Validation Errors

```python
# Temporarily disable validation
bus.validators = {}  # Clears all validators
```

## See Also

- [PMOVES.AI NATS Subjects](../../../../../.claude/context/nats-subjects.md)
- [Event Bus Implementation](./bus.py)
- [Test Suite](./test_bus.py)
- [Aligned Implementation Roadmap](../../../../../docs/AGENTS/ALIGNED_IMPLEMENTATION_ROADMAP.md)
