# Feature Branch Development Guide

When working on a feature branch for PMOVES.AI skills, follow this structured approach to ensure high-quality, maintainable implementations.

## Mindset

You are building a production feature that will be deployed to a sophisticated multi-agent orchestration platform. Your work should be:

- **Production-ready**: Not a prototype or proof-of-concept
- **Integrated**: Leveraging existing PMOVES.AI services, not duplicating functionality
- **Observable**: Including proper logging, metrics, and health checks
- **Tested**: With both unit and integration tests
- **Documented**: Clear SKILL.md, docstrings, and usage examples

## Development Workflow

### 1. Analysis Phase

Before writing any code:

- **Understand the requirement**: What problem are you solving?
- **Check existing services**: Can this be done with Hi-RAG, TensorZero, Agent Zero MCP, etc.?
- **Review NATS subjects**: What events should you publish/subscribe to?
- **Plan integration points**: APIs, databases, message bus connections

**Questions to answer**:
- Does this duplicate existing functionality? (If yes, use existing service instead)
- What NATS subjects should be used? (See `.claude/context/nats-subjects.md`)
- Which services will this interact with? (Agent Zero, TensorZero, etc.)
- What metrics need to be tracked? (Prometheus metrics at `/metrics`)

### 2. Design Phase

Create a minimal design document addressing:

- **Architecture**: How does this fit into PMOVES.AI?
- **Data flow**: NATS events → Processing → Storage/Publishing
- **Error handling**: What can fail? How should it be handled?
- **Observability**: Logging levels, metrics, health checks
- **Testing**: Unit tests, integration tests, smoke tests

**Key principles**:
- Fail gracefully with proper error messages
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Expose `/healthz` endpoint
- Publish metrics for Prometheus
- Use NATS for async coordination

### 3. Implementation Phase

Follow PMOVES.AI patterns:

**Service Structure**:
```python
# tools/my_feature.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MyFeature:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("Initialized MyFeature")

    def execute(self, **params) -> Dict[str, Any]:
        """Execute feature with proper error handling."""
        try:
            # Validate inputs
            self._validate(params)

            # Do work
            result = self._do_work(params)

            # Log success
            logger.info(f"Feature executed successfully: {result}")

            return {
                "success": True,
                "result": result,
                "metadata": {}
            }

        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            return {"success": False, "error": str(e)}

        except Exception as e:
            logger.error(f"Feature execution failed: {e}")
            return {"success": False, "error": str(e)}
```

**NATS Integration**:
```python
import asyncio
from nats.aio.client import Client as NATS

async def publish_event(subject: str, data: dict):
    """Publish event to NATS message bus."""
    nc = NATS()
    try:
        await nc.connect(servers=["nats://localhost:4222"])
        await nc.publish(subject, json.dumps(data).encode())
        logger.debug(f"Published to {subject}: {data}")
    finally:
        await nc.close()
```

**Health Check**:
```python
from flask import Flask

app = Flask(__name__)

@app.route('/healthz')
def health_check():
    """Health check endpoint for orchestration."""
    return {"status": "healthy"}, 200

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint."""
    # Return metrics in Prometheus format
    return prometheus_metrics()
```

### 4. Testing Phase

**Unit Tests**:
```python
import pytest
from pmoves.services.agent_zero.skills.my_feature import MyFeature

def test_basic_execution():
    feature = MyFeature(config={})
    result = feature.execute(param="value")
    assert result['success'] is True

def test_invalid_input():
    feature = MyFeature(config={})
    result = feature.execute(invalid_param="bad")
    assert result['success'] is False
```

**Integration Tests**:
```python
@pytest.mark.asyncio
async def test_nats_integration():
    # Test NATS publishing
    await publish_event("test.subject", {"test": "data"})
    # Verify event was received
```

**Smoke Tests**:
```python
def test_service_health():
    """Test service is running and healthy."""
    response = requests.get("http://localhost:8080/healthz")
    assert response.status_code == 200
```

### 5. Documentation Phase

**SKILL.md Frontmatter** (REQUIRED):
```yaml
---
name: My Feature Skill
description: Brief description of what this skill does
keywords: keyword1, keyword2, keyword3
version: 1.0.0
category: Category/Subcategory
---
```

**SKILL.md Sections** (ALL REQUIRED):
- Overview: What does this skill do?
- Capabilities: Key features with emoji markers
- Skill Structure: Directory layout
- Trigger Phrases: Natural language → Action mapping table
- Tools: Detailed tool documentation
- Configuration: Required environment variables/settings
- Cookbook: Usage examples (with code)
- Quick Reference: Command reference table
- Integration Points: NATS, APIs, databases, MCP servers
- Troubleshooting: Common issues and solutions
- See Also: Related skills and documentation

**Docstrings** (REQUIRED):
- Google style docstrings for all classes and functions
- Type hints for all parameters
- Examples in docstrings
- Raises documentation for exceptions

**Code Coverage**:
- Minimum 80% docstring coverage on new/modified Python code
- All public APIs documented
- Complex logic explained in comments

## Integration Checklist

Before submitting PR:

- [ ] No duplicate functionality (uses existing services)
- [ ] NATS subjects follow naming convention (`.v1` suffix)
- [ ] `/healthz` endpoint implemented
- [ ] `/metrics` endpoint for Prometheus
- [ ] Proper logging at appropriate levels
- [ ] Error handling with specific exceptions
- [ ] Unit tests with >80% coverage
- [ ] Integration tests for external dependencies
- [ ] SKILL.md complete with all sections
- [ ] Docstrings on all classes/functions
- [ ] Type hints on all parameters
- [ ] Cookbook examples in `cookbook/examples.md`
- [ ] No hardcoded credentials or secrets
- [ ] Environment variables documented
- [ ] Git commit messages follow conventions

## Common Patterns

### LLM Calls via TensorZero
```python
import requests

def call_llm(prompt: str) -> str:
    """Call LLM through TensorZero gateway."""
    response = requests.post(
        "http://localhost:3030/v1/chat/completions",
        json={
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    return response.json()['choices'][0]['message']['content']
```

### Knowledge Retrieval via Hi-RAG
```python
def query_knowledge(query: str, top_k: int = 10) -> list:
    """Query knowledge base via Hi-RAG v2."""
    response = requests.post(
        "http://localhost:8086/hirag/query",
        json={"query": query, "top_k": top_k, "rerank": True}
    )
    return response.json()['results']
```

### Agent Orchestration via Agent Zero MCP
```python
def delegate_to_agent(task: str, agent_id: str) -> dict:
    """Delegate task to another agent via MCP."""
    response = requests.post(
        "http://localhost:8080/mcp/command",
        json={"command": task, "agent_id": agent_id}
    )
    return response.json()
```

## Anti-Patterns to Avoid

❌ **Don't** build new RAG systems → Use Hi-RAG v2
❌ **Don't** create new message buses → Use NATS
❌ **Don't** implement new LLM gateways → Use TensorZero
❌ **Don't** hardcode configuration → Use environment variables
❌ **Don't** skip health checks → Expose `/healthz`
❌ **Don't** ignore errors → Handle and log appropriately
❌ **Don't** skip documentation → SKILL.md + docstrings required
❌ **Don't** forget tests → Unit + integration + smoke

## Example Workflow

**Scenario**: Add a skill that processes natural language queries and retrieves relevant documents from the knowledge base.

**Analysis**:
- Requirement: Process queries and retrieve documents
- Existing service: Hi-RAG v2 already does this
- Solution: Create skill that wraps Hi-RAG v2 API

**Implementation**:
```python
class QueryProcessor:
    def __init__(self):
        self.hirag_url = "http://localhost:8086/hirag/query"

    def process(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Process query via Hi-RAG v2."""
        try:
            response = requests.post(
                self.hirag_url,
                json={"query": query, "top_k": top_k, "rerank": True}
            )
            results = response.json()['results']

            logger.info(f"Retrieved {len(results)} documents for query")

            return {
                "success": True,
                "results": results,
                "metadata": {"query": query, "count": len(results)}
            }

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {"success": False, "error": str(e)}
```

**Testing**:
```python
def test_query_processing():
    processor = QueryProcessor()
    result = processor.process("test query", top_k=5)
    assert result['success'] is True
    assert len(result['results']) <= 5
```

**Documentation**: Complete SKILL.md with all required sections, cookbook examples, and integration points.

## Resources

- PMOVES.AI Architecture: `.claude/CLAUDE.md`
- NATS Subjects: `.claude/context/nats-subjects.md`
- Services Catalog: `.claude/context/services-catalog.md`
- Testing Strategy: `.claude/context/testing-strategy.md`
- TensorZero: `.claude/context/tensorzero.md`
- MCP API: `.claude/context/mcp-api.md`

## Success Criteria

A feature branch is complete when:

1. ✅ All tests pass (unit, integration, smoke)
2. ✅ SKILL.md is complete and validated
3. ✅ Docstring coverage ≥80%
4. ✅ Health checks pass (`/healthz`, `/metrics`)
5. ✅ Integration with existing services verified
6. ✅ No code quality issues (no linting errors)
7. ✅ Cookbook has practical examples
8. ✅ Code review approved

Remember: You're building for production. Quality and integration matter more than speed.
